"""Adversarial tests for the Darwin LC_UUID post-link normalizer."""

from __future__ import annotations

import hashlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import darwin_uuid_normalize as normalize  # noqa: E402
from native_toolchain import STABLE_INSTALL_NAME  # noqa: E402

INSTALL = STABLE_INSTALL_NAME
LIBSYSTEM = "/usr/lib/libSystem.B.dylib"
SYMBOL = normalize.SIGN_SYMBOL


def _pad8(payload: bytes) -> bytes:
    return payload + b"\x00" * ((8 - (len(payload) % 8)) % 8)


def _dylib_cmd(cmd: int, name: str, *, timestamp: int = 1) -> bytes:
    encoded = name.encode("utf-8") + b"\x00"
    name_off = 24
    body = struct.pack("<IIII", name_off, timestamp, 0, 0) + encoded
    cmdsize = 8 + len(_pad8(body))
    return struct.pack("<II", cmd, cmdsize) + _pad8(body)


def _uuid_cmd(uuid: bytes) -> bytes:
    assert len(uuid) == 16
    return struct.pack("<II", normalize.LC_UUID, 24) + uuid


def _signature_cmd(dataoff: int, datasize: int) -> bytes:
    return struct.pack("<IIII", normalize.LC_CODE_SIGNATURE, 16, dataoff, datasize)


def _segment64(
    name: str,
    fileoff: int,
    filesize: int,
    *,
    vmsize: int | None = None,
    vmaddr: int = 0,
) -> bytes:
    vmsize = filesize if vmsize is None else vmsize
    padded = name.encode("utf-8") + b"\x00" * (16 - len(name))
    return struct.pack("<II", normalize.LC_SEGMENT_64, 72) + padded + struct.pack(
        "<QQQQIIII", vmaddr, vmsize, fileoff, filesize, 0, 0, 0, 0
    )


def build_thin_dylib(
    *,
    arch: str = "arm64",
    uuid: bytes = b"\x11" * 16,
    install_name: str = INSTALL,
    dependents: tuple[str, ...] = (LIBSYSTEM,),
    extra_cmds: list[bytes] | None = None,
    signature: bytes | None = None,
    filetype: int = normalize.MH_DYLIB,
    magic: int | None = None,
    ncmds_override: int | None = None,
    sizeofcmds_override: int | None = None,
    truncate: int | None = None,
    cpusubtype: int | None = None,
    trailing: bytes = b"",
    signature_dataoff: int | None = None,
    linkedit: bool | None = None,
    text_filesize: int | None = None,
) -> bytes:
    cpu = normalize.CPU_BY_ARCH[arch]
    subtype = (
        normalize.CPU_SUBTYPE_BY_ARCH[arch] if cpusubtype is None else cpusubtype
    )
    include_linkedit = linkedit if linkedit is not None else signature is not None
    commands: list[bytes] = []
    if include_linkedit:
        commands.append(_segment64("__TEXT", 0, 0))
        commands.append(_segment64("__LINKEDIT", 0, 0))
    commands.append(_uuid_cmd(uuid))
    commands.append(_dylib_cmd(normalize.LC_ID_DYLIB, install_name))
    for dep in dependents:
        commands.append(_dylib_cmd(normalize.LC_LOAD_DYLIB, dep))
    commands.extend(extra_cmds or [])
    blob = b""
    if signature is not None:
        commands.append(_signature_cmd(0, len(signature)))
        blob = signature
    load = b"".join(commands)
    dataoff = normalize.HEADER_SIZE + len(load)
    if signature is not None:
        if signature_dataoff is not None:
            dataoff = signature_dataoff
        commands[-1] = _signature_cmd(dataoff, len(signature))
        if include_linkedit:
            text_size = text_filesize if text_filesize is not None else dataoff
            link_off = text_size
            link_size = max(0, dataoff + len(signature) - link_off)
            commands[0] = _segment64("__TEXT", 0, text_size)
            commands[1] = _segment64(
                "__LINKEDIT",
                link_off,
                link_size,
                vmsize=normalize._align_up(link_size, normalize.PAGE_SIZE_BY_ARCH[arch]),
            )
        load = b"".join(commands)
        if signature_dataoff is None:
            dataoff = normalize.HEADER_SIZE + len(load)
            commands[-1] = _signature_cmd(dataoff, len(signature))
            if include_linkedit:
                text_size = text_filesize if text_filesize is not None else dataoff
                link_off = text_size
                link_size = max(0, dataoff + len(signature) - link_off)
                commands[0] = _segment64("__TEXT", 0, text_size)
                commands[1] = _segment64(
                    "__LINKEDIT",
                    link_off,
                    link_size,
                    vmsize=normalize._align_up(
                        link_size, normalize.PAGE_SIZE_BY_ARCH[arch]
                    ),
                )
            load = b"".join(commands)
            dataoff = normalize.HEADER_SIZE + len(load)
            commands[-1] = _signature_cmd(dataoff, len(signature))
            load = b"".join(commands)
        padding = b"\x00" * max(0, dataoff - (normalize.HEADER_SIZE + len(load)))
        blob = padding + signature
    elif include_linkedit:
        text_size = text_filesize if text_filesize is not None else normalize.HEADER_SIZE + len(load)
        commands[0] = _segment64("__TEXT", 0, text_size)
        commands[1] = _segment64("__LINKEDIT", text_size, 16, vmsize=normalize.PAGE_SIZE_BY_ARCH[arch])
        load = b"".join(commands)
        blob = b"\x00" * 16
    ncmds = ncmds_override if ncmds_override is not None else len(commands)
    sizeofcmds = sizeofcmds_override if sizeofcmds_override is not None else len(load)
    header = struct.pack(
        "<IIIIIIII",
        magic if magic is not None else normalize.MH_MAGIC_64,
        cpu,
        subtype,
        filetype,
        ncmds,
        sizeofcmds,
        0,
        0,
    )
    data = header + load + blob + trailing
    if truncate is not None:
        return data[:truncate]
    return data


def _nm_ok(_path: Path) -> str:
    return f"0000000000000000 T _{SYMBOL}\n"


class ParseAndNormalizeTests(unittest.TestCase):
    def test_identical_canonical_content_normalizes_identically(self) -> None:
        left = build_thin_dylib(uuid=b"\x01" * 16)
        right = build_thin_dylib(uuid=b"\x02" * 16)
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        a = root / "a.dylib"
        b = root / "b.dylib"
        a.write_bytes(left)
        b.write_bytes(right)
        ra = normalize.normalize_dylib(
            a, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
        )
        rb = normalize.normalize_dylib(
            b, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
        )
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(ra["uuid"], rb["uuid"])
        self.assertEqual(ra["canonical_sha256"], rb["canonical_sha256"])

    def test_repeated_normalization_is_idempotent(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "lib.dylib"
        path.write_bytes(build_thin_dylib(uuid=b"\xab" * 16))
        first = normalize.normalize_dylib(
            path, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
        )
        second = normalize.normalize_dylib(
            path, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
        )
        self.assertEqual(first["uuid"], second["uuid"])
        self.assertEqual(first["output_sha256"], second["output_sha256"])
        self.assertEqual(path.read_bytes(), path.read_bytes())

    def test_only_uuid_bytes_change(self) -> None:
        original = build_thin_dylib(uuid=b"\xcd" * 16)
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "lib.dylib"
        path.write_bytes(original)
        normalize.normalize_dylib(
            path, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
        )
        after = path.read_bytes()
        parsed = normalize.parse_thin_dylib(original)
        assert parsed.uuid_offset is not None
        changed = [
            i for i, (x, y) in enumerate(zip(original, after)) if x != y
        ]
        self.assertTrue(changed)
        self.assertTrue(all(parsed.uuid_offset <= i < parsed.uuid_offset + 16 for i in changed))

    def test_digest_is_stdlib_sha256_with_rfc9562_v8(self) -> None:
        data = build_thin_dylib(uuid=b"\x03" * 16)
        parsed = normalize.parse_thin_dylib(data)
        assert parsed.uuid_offset is not None
        canonical = normalize.canonical_unsigned(data, parsed.uuid_offset)
        digest = hashlib.sha256(canonical).digest()
        expected = bytearray(digest[:16])
        expected[6] = (expected[6] & 0x0F) | 0x80
        expected[8] = (expected[8] & 0x3F) | 0x80
        self.assertEqual(normalize.digest_uuid(canonical), bytes(expected))

    def test_fat_binary_is_rejected(self) -> None:
        fat = struct.pack(">II", normalize.FAT_MAGIC, 1) + b"\x00" * 20
        with self.assertRaisesRegex(normalize.NormalizeError, "fat"):
            normalize.parse_thin_dylib(fat)

    def test_missing_and_duplicate_uuid_are_rejected(self) -> None:
        cpu = normalize.CPU_TYPE_ARM64
        load = _dylib_cmd(normalize.LC_ID_DYLIB, INSTALL) + _dylib_cmd(
            normalize.LC_LOAD_DYLIB, LIBSYSTEM
        )
        header = struct.pack(
            "<IIIIIIII",
            normalize.MH_MAGIC_64,
            cpu,
            normalize.CPU_SUBTYPE_ARM64_ALL,
            normalize.MH_DYLIB,
            2,
            len(load),
            0,
            0,
        )
        with self.assertRaisesRegex(normalize.NormalizeError, "LC_UUID is missing"):
            normalize.parse_thin_dylib(header + load)
        dup = build_thin_dylib(extra_cmds=[_uuid_cmd(b"\x44" * 16)])
        with self.assertRaisesRegex(normalize.NormalizeError, "exactly one LC_UUID"):
            normalize.parse_thin_dylib(dup)

    def test_truncated_and_overlapping_commands_are_rejected(self) -> None:
        data = build_thin_dylib()
        with self.assertRaisesRegex(normalize.NormalizeError, "truncated"):
            normalize.parse_thin_dylib(data[:20])
        with self.assertRaisesRegex(normalize.NormalizeError, "sizeofcmds"):
            normalize.parse_thin_dylib(build_thin_dylib(sizeofcmds_override=8))

    def test_wrong_arch_install_name_and_dependent_are_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        wrong_arch = root / "arch.dylib"
        wrong_arch.write_bytes(build_thin_dylib(arch="x86_64"))
        with self.assertRaisesRegex(normalize.NormalizeError, "architecture"):
            normalize.normalize_dylib(
                wrong_arch, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
            )
        wrong_name = root / "name.dylib"
        wrong_name.write_bytes(build_thin_dylib(install_name="/tmp/host.dylib"))
        with self.assertRaisesRegex(normalize.NormalizeError, "LC_ID_DYLIB"):
            normalize.normalize_dylib(
                wrong_name, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
            )
        extra_dep = root / "dep.dylib"
        extra_dep.write_bytes(build_thin_dylib(dependents=(LIBSYSTEM, "/usr/lib/libz.1.dylib")))
        with self.assertRaisesRegex(normalize.NormalizeError, "unexpected dependent"):
            normalize.normalize_dylib(
                extra_dep, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
            )

    def test_each_dependency_command_with_malicious_path_is_rejected(self) -> None:
        evil = "/tmp/evil.dylib"
        for cmd, form in normalize.DEPENDENCY_COMMANDS.items():
            data = build_thin_dylib(
                extra_cmds=[_dylib_cmd(cmd, evil)] if cmd != normalize.LC_LOAD_DYLIB else None,
                dependents=(evil,) if cmd == normalize.LC_LOAD_DYLIB else (LIBSYSTEM,),
            )
            parsed = normalize.parse_thin_dylib(data)
            names = [dep.name for dep in parsed.dependents]
            self.assertIn(evil, names, form)
            root = Path(tempfile.mkdtemp())
            self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
            path = root / f"{form}.dylib"
            path.write_bytes(data)
            with self.assertRaisesRegex(normalize.NormalizeError, "unexpected dependent|unexpected dependency form"):
                normalize.normalize_dylib(
                    path, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
                )

    def test_alternate_dependency_forms_of_libsystem_are_rejected(self) -> None:
        for cmd, form in normalize.DEPENDENCY_COMMANDS.items():
            if cmd == normalize.LC_LOAD_DYLIB:
                continue
            data = build_thin_dylib(extra_cmds=[_dylib_cmd(cmd, LIBSYSTEM)])
            parsed = normalize.parse_thin_dylib(data)
            self.assertTrue(any(dep.cmd == cmd for dep in parsed.dependents), form)
            root = Path(tempfile.mkdtemp())
            self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
            path = root / f"{form}.dylib"
            path.write_bytes(data)
            with self.assertRaisesRegex(normalize.NormalizeError, "unexpected dependency form"):
                normalize.normalize_dylib(
                    path, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
                )

    def test_single_load_dylib_libsystem_is_accepted(self) -> None:
        data = build_thin_dylib()
        parsed = normalize.parse_thin_dylib(data)
        self.assertEqual(len(parsed.dependents), 1)
        self.assertEqual(parsed.dependents[0].cmd, normalize.LC_LOAD_DYLIB)
        self.assertEqual(parsed.dependents[0].name, LIBSYSTEM)

    def test_malformed_dependency_req_dyld_variants_are_rejected(self) -> None:
        malformed = (
            (normalize.LC_LOAD_DYLIB | normalize.LC_REQ_DYLD, "LC_LOAD_DYLIB"),
            (normalize.LC_LOAD_DYLIB | 0x40000000, "LC_LOAD_DYLIB"),
            (0x18, "LC_LOAD_WEAK_DYLIB"),
            (0x1F, "LC_REEXPORT_DYLIB"),
            (normalize.LC_LAZY_LOAD_DYLIB | normalize.LC_REQ_DYLD, "LC_LAZY_LOAD_DYLIB"),
            (0x23, "LC_LOAD_UPWARD_DYLIB"),
            (normalize.LC_LOAD_WEAK_DYLIB | 0x40000000, "LC_LOAD_WEAK_DYLIB"),
        )
        for cmd, name in malformed:
            data = build_thin_dylib(extra_cmds=[_dylib_cmd(cmd, LIBSYSTEM)])
            with self.assertRaisesRegex(normalize.NormalizeError, "illegal flag combination"):
                normalize.parse_thin_dylib(data)

    def test_truncated_dependency_name_and_command_are_rejected(self) -> None:
        short = struct.pack("<II", normalize.LC_LOAD_WEAK_DYLIB, 8)
        with self.assertRaisesRegex(normalize.NormalizeError, "dylib command is shorter"):
            normalize.parse_thin_dylib(build_thin_dylib(extra_cmds=[short]))
        body = struct.pack("<IIII", 24, 1, 0, 0) + b"nonulxxx"
        cmdsize = 8 + len(body)
        unterminated = struct.pack("<II", normalize.LC_REEXPORT_DYLIB, cmdsize) + body
        with self.assertRaisesRegex(normalize.NormalizeError, "unterminated"):
            normalize.parse_thin_dylib(build_thin_dylib(extra_cmds=[unterminated]))
        name_off = 64
        body = struct.pack("<IIII", name_off, 1, 0, 0) + b"x\x00"
        cmdsize = 8 + len(_pad8(body))
        bad_off = struct.pack("<II", normalize.LC_LAZY_LOAD_DYLIB, cmdsize) + _pad8(body)
        with self.assertRaisesRegex(normalize.NormalizeError, "name offset"):
            normalize.parse_thin_dylib(build_thin_dylib(extra_cmds=[bad_off]))

    def test_duplicate_load_dylib_is_rejected(self) -> None:
        data = build_thin_dylib(dependents=(LIBSYSTEM, LIBSYSTEM))
        parsed = normalize.parse_thin_dylib(data)
        self.assertEqual(len(parsed.dependents), 2)
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "dup.dylib"
        path.write_bytes(data)
        with self.assertRaisesRegex(normalize.NormalizeError, "exactly one LC_LOAD_DYLIB"):
            normalize.normalize_dylib(
                path, expected_arch="arm64", sign=False, nm=_nm_ok, skip_codesign=True
            )

    def test_committed_darwin_binaries_still_pass(self) -> None:
        module = SCRIPT_DIR.parent
        arm = (
            module
            / "src/jvmMain/resources/darwin-aarch64/libkardano_ed25519_bip32_signing.dylib"
        )
        x86 = (
            module
            / "src/jvmMain/resources/darwin-x86-64/libkardano_ed25519_bip32_signing.dylib"
        )
        for path, arch in ((arm, "arm64"), (x86, "x86_64")):
            original = path.read_bytes()
            parsed = normalize.parse_thin_dylib(original)
            self.assertEqual([dep.cmd for dep in parsed.dependents], [normalize.LC_LOAD_DYLIB])
            self.assertEqual([dep.name for dep in parsed.dependents], [LIBSYSTEM])
            # codesign / host nm live on Darwin. Ubuntu catalog jobs still
            # parse every dependency command and apply the allowlist.
            if sys.platform == "darwin":
                if arch == "arm64":
                    expected = normalize.verify_signed_canonical_uuid(
                        path, expected_arch=arch
                    )
                    self.assertEqual(parsed.uuid, expected)
                else:
                    root = Path(tempfile.mkdtemp())
                    self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
                    copy = root / path.name
                    copy.write_bytes(original)
                    record = normalize.normalize_dylib(copy, expected_arch=arch, sign=False)
                    self.assertFalse(record["mutated"])
                    self.assertEqual(copy.read_bytes(), original)
            self.assertEqual(path.read_bytes(), original)

    def test_missing_symbol_is_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "lib.dylib"
        path.write_bytes(build_thin_dylib())
        with self.assertRaisesRegex(normalize.NormalizeError, "not exported"):
            normalize.normalize_dylib(
                path,
                expected_arch="arm64",
                sign=False,
                nm=lambda _p: "00000000 T _other\n",
                skip_codesign=True,
            )

    def test_unexpected_signature_layout_is_rejected(self) -> None:
        load = (
            _uuid_cmd(b"\x11" * 16)
            + _dylib_cmd(normalize.LC_ID_DYLIB, INSTALL)
            + _dylib_cmd(normalize.LC_LOAD_DYLIB, LIBSYSTEM)
            + _signature_cmd(8, 4)
        )
        header = struct.pack(
            "<IIIIIIII",
            normalize.MH_MAGIC_64,
            normalize.CPU_TYPE_ARM64,
            normalize.CPU_SUBTYPE_ARM64_ALL,
            normalize.MH_DYLIB,
            4,
            len(load),
            0,
            0,
        )
        with self.assertRaisesRegex(normalize.NormalizeError, "LC_CODE_SIGNATURE"):
            normalize.parse_thin_dylib(header + load)

    def test_x86_64_layout_is_accepted_without_signing(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "lib.dylib"
        path.write_bytes(build_thin_dylib(arch="x86_64", uuid=b"\x99" * 16))
        record = normalize.normalize_dylib(
            path, expected_arch="x86_64", sign=False, nm=_nm_ok, skip_codesign=True
        )
        parsed = normalize.parse_thin_dylib(path.read_bytes())
        self.assertEqual(parsed.arch, "x86_64")
        self.assertEqual(parsed.cpusubtype, normalize.CPU_SUBTYPE_X86_64_ALL)
        self.assertEqual(parsed.install_name, INSTALL)
        self.assertIsNone(parsed.signature)
        self.assertFalse(record["signed"])

    def test_uuid_req_dyld_flag_is_rejected(self) -> None:
        data = build_thin_dylib()
        parsed = normalize.parse_thin_dylib(data)
        mutated = bytearray(data)
        struct.pack_into(
            "<I", mutated, parsed.commands[0].offset, normalize.LC_UUID | normalize.LC_REQ_DYLD
        )
        # UUID may not be command 0 when LINKEDIT is absent; find it.
        for command in parsed.commands:
            if command.cmd == normalize.LC_UUID:
                struct.pack_into(
                    "<I",
                    mutated,
                    command.offset,
                    normalize.LC_UUID | normalize.LC_REQ_DYLD,
                )
                break
        with self.assertRaisesRegex(normalize.NormalizeError, "illegal flag combination"):
            normalize.parse_thin_dylib(bytes(mutated))

    def test_code_signature_req_dyld_flag_is_rejected(self) -> None:
        data = build_thin_dylib(signature=b"\xaa" * 32)
        parsed = normalize.parse_thin_dylib(data)
        assert parsed.signature is not None
        mutated = bytearray(data)
        struct.pack_into(
            "<I",
            mutated,
            parsed.signature.offset,
            normalize.LC_CODE_SIGNATURE | normalize.LC_REQ_DYLD,
        )
        with self.assertRaisesRegex(normalize.NormalizeError, "illegal flag combination"):
            normalize.parse_thin_dylib(bytes(mutated))

    def test_id_dylib_req_dyld_flag_is_rejected(self) -> None:
        data = build_thin_dylib()
        parsed = normalize.parse_thin_dylib(data)
        mutated = bytearray(data)
        for command in parsed.commands:
            if command.cmd == normalize.LC_ID_DYLIB:
                struct.pack_into(
                    "<I",
                    mutated,
                    command.offset,
                    normalize.LC_ID_DYLIB | normalize.LC_REQ_DYLD,
                )
                break
        with self.assertRaisesRegex(normalize.NormalizeError, "illegal flag combination"):
            normalize.parse_thin_dylib(bytes(mutated))

    def test_arm64e_subtype_is_rejected(self) -> None:
        data = build_thin_dylib(cpusubtype=normalize.CPU_SUBTYPE_ARM64E)
        with self.assertRaisesRegex(normalize.NormalizeError, "cpusubtype"):
            normalize.parse_thin_dylib(data)

    def test_x86_64_lib64_capability_is_rejected(self) -> None:
        data = build_thin_dylib(
            arch="x86_64",
            cpusubtype=normalize.CPU_SUBTYPE_X86_64_ALL | normalize.CPU_SUBTYPE_LIB64,
        )
        with self.assertRaisesRegex(normalize.NormalizeError, "cpusubtype"):
            normalize.parse_thin_dylib(data)

    def test_x86_64_all_zero_subtype_is_rejected(self) -> None:
        data = build_thin_dylib(arch="x86_64", cpusubtype=0)
        with self.assertRaisesRegex(normalize.NormalizeError, "cpusubtype"):
            normalize.parse_thin_dylib(data)

    def test_duplicate_id_dylib_is_rejected(self) -> None:
        data = build_thin_dylib(extra_cmds=[_dylib_cmd(normalize.LC_ID_DYLIB, INSTALL)])
        with self.assertRaisesRegex(normalize.NormalizeError, "exactly one LC_ID_DYLIB"):
            normalize.parse_thin_dylib(data)

    def test_duplicate_code_signature_is_rejected(self) -> None:
        data = build_thin_dylib(
            signature=b"\xab" * 16,
            extra_cmds=[_signature_cmd(4096, 16)],
        )
        with self.assertRaisesRegex(normalize.NormalizeError, "multiple LC_CODE_SIGNATURE"):
            normalize.parse_thin_dylib(data)

    def test_middle_of_file_signature_is_rejected(self) -> None:
        data = build_thin_dylib(signature=b"\xcd" * 16, trailing=b"\xff" * 32)
        with self.assertRaisesRegex(normalize.NormalizeError, "end exactly at EOF"):
            normalize.parse_thin_dylib(data)

    def test_trailing_bytes_after_linkedit_are_rejected(self) -> None:
        data = build_thin_dylib(signature=b"\xef" * 24, trailing=b"\x00\x01")
        with self.assertRaisesRegex(normalize.NormalizeError, "end exactly at EOF"):
            normalize.parse_thin_dylib(data)

    def test_signature_overlapping_text_is_rejected(self) -> None:
        data = build_thin_dylib(
            signature=b"\x11" * 16,
            signature_dataoff=8,
            text_filesize=64,
        )
        with self.assertRaisesRegex(normalize.NormalizeError, "LC_CODE_SIGNATURE"):
            normalize.parse_thin_dylib(data)

    def test_invalid_dataoff_and_datasize_are_rejected(self) -> None:
        load = (
            _segment64("__TEXT", 0, 64)
            + _segment64("__LINKEDIT", 64, 16)
            + _uuid_cmd(b"\x11" * 16)
            + _dylib_cmd(normalize.LC_ID_DYLIB, INSTALL)
            + _dylib_cmd(normalize.LC_LOAD_DYLIB, LIBSYSTEM)
            + _signature_cmd(10_000, 16)
        )
        header = struct.pack(
            "<IIIIIIII",
            normalize.MH_MAGIC_64,
            normalize.CPU_TYPE_ARM64,
            normalize.CPU_SUBTYPE_ARM64_ALL,
            normalize.MH_DYLIB,
            6,
            len(load),
            0,
            0,
        )
        with self.assertRaisesRegex(normalize.NormalizeError, "LC_CODE_SIGNATURE"):
            normalize.parse_thin_dylib(header + load + b"\x00" * 16)

    def test_zero_datasize_is_rejected(self) -> None:
        load = (
            _segment64("__TEXT", 0, 80)
            + _segment64("__LINKEDIT", 80, 8)
            + _uuid_cmd(b"\x11" * 16)
            + _dylib_cmd(normalize.LC_ID_DYLIB, INSTALL)
            + _dylib_cmd(normalize.LC_LOAD_DYLIB, LIBSYSTEM)
            + _signature_cmd(80, 0)
        )
        header = struct.pack(
            "<IIIIIIII",
            normalize.MH_MAGIC_64,
            normalize.CPU_TYPE_ARM64,
            normalize.CPU_SUBTYPE_ARM64_ALL,
            normalize.MH_DYLIB,
            6,
            len(load),
            0,
            0,
        )
        with self.assertRaisesRegex(normalize.NormalizeError, "datasize"):
            normalize.parse_thin_dylib(header + load)

    def test_prefixed_and_suffixed_identifiers_are_rejected(self) -> None:
        text = (
            "Identifier=evil.org.sarmidev.kardano.ed25519-bip32-signing\n"
            "Signature=adhoc\n"
            "TeamIdentifier=not set\n"
            "CodeDirectory v=20400 size=1 flags=0x2(adhoc) hashes=1+2 location=embedded\n"
        )
        display = normalize.parse_codesign_display(text)
        with self.assertRaisesRegex(normalize.NormalizeError, "Identifier"):
            normalize.require_expected_ad_hoc(display)
        text = (
            f"Identifier={normalize.STABLE_IDENTIFIER}.suffix\n"
            "Signature=adhoc\n"
            "TeamIdentifier=not set\n"
            "CodeDirectory v=20400 size=1 flags=0x2(adhoc) hashes=1+2 location=embedded\n"
        )
        display = normalize.parse_codesign_display(text)
        with self.assertRaisesRegex(normalize.NormalizeError, "Identifier"):
            normalize.require_expected_ad_hoc(display)

    def test_timestamped_and_non_adhoc_displays_are_rejected(self) -> None:
        base = (
            f"Identifier={normalize.STABLE_IDENTIFIER}\n"
            "Signature=adhoc\n"
            "TeamIdentifier=not set\n"
            "CodeDirectory v=20400 size=1 flags=0x2(adhoc) hashes=1+2 location=embedded\n"
        )
        display = normalize.parse_codesign_display(base + "Timestamp=1 Jan 2026\n")
        with self.assertRaisesRegex(normalize.NormalizeError, "Timestamp"):
            normalize.require_expected_ad_hoc(display)
        display = normalize.parse_codesign_display(
            base + "Authority=Developer ID Application: Example\n"
            "Authority=Timestamp Apple\n"
        )
        with self.assertRaisesRegex(normalize.NormalizeError, "timestamp"):
            normalize.require_expected_ad_hoc(display)
        display = normalize.parse_codesign_display(
            f"Identifier={normalize.STABLE_IDENTIFIER}\n"
            "Signature=CMS\n"
            "TeamIdentifier=ABCD123456\n"
            "CodeDirectory v=20400 size=1 flags=0x0() hashes=1+2 location=embedded\n"
        )
        with self.assertRaisesRegex(normalize.NormalizeError, "adhoc"):
            normalize.require_expected_ad_hoc(display)

    def test_exact_identifier_display_is_accepted(self) -> None:
        display = normalize.parse_codesign_display(
            f"Identifier={normalize.STABLE_IDENTIFIER}\n"
            "Signature=adhoc\n"
            "TeamIdentifier=not set\n"
            "CodeDirectory v=20400 size=1 flags=0x2(adhoc) hashes=1+2 location=embedded\n"
        )
        normalize.require_expected_ad_hoc(display)

    def test_canonical_signed_image_zeros_only_documented_fields(self) -> None:
        signed = build_thin_dylib(uuid=b"\x22" * 16, signature=b"\x33" * 64)
        parsed = normalize.parse_thin_dylib(signed)
        canonical = normalize.canonical_image(parsed)
        unsigned = normalize.unsigned_image(parsed)
        self.assertEqual(len(canonical), parsed.signature_dataoff)
        self.assertIsNone(normalize.parse_thin_dylib(unsigned).signature)
        self.assertEqual(unsigned[parsed.uuid_offset : parsed.uuid_offset + 16], b"\x22" * 16)
        self.assertEqual(canonical[parsed.uuid_offset : parsed.uuid_offset + 16], b"\x00" * 16)
        normalize.assert_unsigned_mutations_documented(signed, unsigned, parsed)

    def test_unexpected_unsigned_mutation_is_rejected(self) -> None:
        signed = build_thin_dylib(uuid=b"\x22" * 16, signature=b"\x33" * 64)
        parsed = normalize.parse_thin_dylib(signed)
        unsigned = bytearray(normalize.unsigned_image(parsed))
        assert parsed.uuid_offset is not None
        unsigned[parsed.uuid_offset] ^= 0xFF
        with self.assertRaisesRegex(normalize.NormalizeError, "unexpected unsigned mutation"):
            normalize.assert_unsigned_mutations_documented(signed, bytes(unsigned), parsed)


@unittest.skipUnless(sys.platform == "darwin" and shutil.which("cc"), "Darwin cc required")
class LiveDarwinNormalizeTests(unittest.TestCase):
    def _compile(self, arch: str, dest: Path) -> None:
        src = dest.with_suffix(".c")
        src.write_text(
            "void uniffi_kardano_ed25519_bip32_signing_fn_func_sign(void) {}\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                "cc",
                "-dynamiclib",
                "-arch",
                arch,
                f"-Wl,-install_name,{INSTALL}",
                "-o",
                str(dest),
                str(src),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_arm64_normalize_verifies_and_loads(self) -> None:
        import ctypes

        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "libkardano_ed25519_bip32_signing.dylib"
        self._compile("arm64", path)
        first = normalize.normalize_dylib(path, expected_arch="arm64")
        first_bytes = path.read_bytes()
        second = normalize.normalize_dylib(path, expected_arch="arm64")
        self.assertEqual(first["uuid"], second["uuid"])
        self.assertEqual(first["output_sha256"], second["output_sha256"])
        self.assertEqual(first_bytes, path.read_bytes())
        self.assertTrue(first["signed"])
        self.assertTrue(second["signed"])
        self.assertFalse(second["mutated"])
        self.assertTrue(first["mutated"])
        verify = subprocess.run(
            ["codesign", "--verify", "--strict", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(verify.returncode, 0, verify.stderr)
        ctypes.CDLL(str(path))
        parsed = normalize.parse_thin_dylib(path.read_bytes())
        self.assertEqual(parsed.arch, "arm64")
        self.assertEqual(parsed.cpusubtype, normalize.CPU_SUBTYPE_ARM64_ALL)
        self.assertEqual(parsed.install_name, INSTALL)
        expected = normalize.verify_signed_canonical_uuid(path, expected_arch="arm64")
        self.assertEqual(parsed.uuid, expected)

    def test_x86_64_normalize_keeps_arch_symbol_and_install_name(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "libkardano_ed25519_bip32_signing.dylib"
        self._compile("x86_64", path)
        record = normalize.normalize_dylib(path, expected_arch="x86_64")
        parsed = normalize.parse_thin_dylib(path.read_bytes())
        self.assertEqual(parsed.arch, "x86_64")
        self.assertEqual(parsed.cpusubtype, normalize.CPU_SUBTYPE_X86_64_ALL)
        self.assertEqual(parsed.install_name, INSTALL)
        self.assertIsNone(parsed.signature)
        self.assertFalse(record["signed"])
        nm = subprocess.run(
            ["nm", "-gU", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(nm.returncode, 0, nm.stderr)
        self.assertIn(SYMBOL, nm.stdout)

    def test_suffixed_identifier_is_rewritten_then_verified(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "libkardano_ed25519_bip32_signing.dylib"
        self._compile("arm64", path)
        normalize.normalize_dylib(path, expected_arch="arm64")
        completed = subprocess.run(
            [
                "codesign",
                "--force",
                "-s",
                "-",
                "--identifier",
                f"{normalize.STABLE_IDENTIFIER}.suffix",
                "--timestamp=none",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        with self.assertRaisesRegex(normalize.NormalizeError, "Identifier"):
            normalize.verify_signed_canonical_uuid(path, expected_arch="arm64")
        # Foreign identifier is stripped and re-signed, not accepted as done.
        record = normalize.normalize_dylib(path, expected_arch="arm64")
        self.assertTrue(record["mutated"])
        display = normalize.parse_codesign_display(record["codesign_display"])
        self.assertEqual(display.identifier, normalize.STABLE_IDENTIFIER)

    def test_prefixed_identifier_is_not_accepted_as_normalized(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "libkardano_ed25519_bip32_signing.dylib"
        self._compile("arm64", path)
        normalize.normalize_dylib(path, expected_arch="arm64")
        completed = subprocess.run(
            [
                "codesign",
                "--force",
                "-s",
                "-",
                "--identifier",
                f"evil.{normalize.STABLE_IDENTIFIER}",
                "--timestamp=none",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        with self.assertRaisesRegex(normalize.NormalizeError, "Identifier"):
            normalize.verify_signed_canonical_uuid(path, expected_arch="arm64")

    def test_exact_identifier_with_arbitrary_uuid_is_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "libkardano_ed25519_bip32_signing.dylib"
        self._compile("arm64", path)
        normalize.normalize_dylib(path, expected_arch="arm64")
        parsed = normalize.parse_thin_dylib(path.read_bytes())
        assert parsed.uuid_offset is not None
        mutated = bytearray(path.read_bytes())
        mutated[parsed.uuid_offset : parsed.uuid_offset + 16] = b"\x99" * 16
        path.write_bytes(mutated)
        completed = subprocess.run(
            [
                "codesign",
                "--force",
                "-s",
                "-",
                "--identifier",
                normalize.STABLE_IDENTIFIER,
                "--timestamp=none",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        verify = subprocess.run(
            ["codesign", "--verify", "--strict", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(verify.returncode, 0, verify.stderr)
        with self.assertRaisesRegex(normalize.NormalizeError, "canonical digest"):
            normalize.verify_signed_canonical_uuid(path, expected_arch="arm64")
        with self.assertRaisesRegex(normalize.NormalizeError, "canonical digest"):
            normalize.normalize_dylib(path, expected_arch="arm64")

    def test_tampered_signature_is_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "libkardano_ed25519_bip32_signing.dylib"
        self._compile("arm64", path)
        normalize.normalize_dylib(path, expected_arch="arm64")
        parsed = normalize.parse_thin_dylib(path.read_bytes())
        assert parsed.signature_dataoff is not None
        mutated = bytearray(path.read_bytes())
        mutated[parsed.signature_dataoff] ^= 0xFF
        path.write_bytes(mutated)
        verify = subprocess.run(
            ["codesign", "--verify", "--strict", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(verify.returncode, 0, verify.stderr)
        with self.assertRaisesRegex(normalize.NormalizeError, "codesign"):
            normalize.normalize_dylib(path, expected_arch="arm64")

    def test_non_adhoc_team_display_is_rejected_if_constructible(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "libkardano_ed25519_bip32_signing.dylib"
        self._compile("arm64", path)
        normalize.normalize_dylib(path, expected_arch="arm64")
        # --timestamp requires Apple's timestamp service; treat failure as
        # "not constructible" and keep the synthetic parser coverage.
        completed = subprocess.run(
            [
                "codesign",
                "--force",
                "-s",
                "-",
                "--identifier",
                normalize.STABLE_IDENTIFIER,
                "--timestamp",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            self.skipTest(f"timestamped signature not constructible: {completed.stderr}")
        display = normalize.parse_codesign_display(normalize.display_signature(path))
        detectable = display.timestamp not in {None, "", "none", "not set"} or any(
            "timestamp" in item.lower() for item in display.authorities
        )
        if not detectable:
            self.skipTest(
                "ad-hoc --timestamp left Signature=adhoc with no Timestamp field"
            )
        with self.assertRaisesRegex(normalize.NormalizeError, "Timestamp|timestamp|adhoc"):
            normalize.verify_signed_canonical_uuid(path, expected_arch="arm64")


if __name__ == "__main__":
    unittest.main()
