"""Adversarial tests for the Darwin LC_UUID post-link normalizer."""

from __future__ import annotations

import hashlib
import os
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
) -> bytes:
    cpu = normalize.CPU_BY_ARCH[arch]
    commands = [_uuid_cmd(uuid), _dylib_cmd(normalize.LC_ID_DYLIB, install_name)]
    for dep in dependents:
        commands.append(_dylib_cmd(normalize.LC_LOAD_DYLIB, dep))
    commands.extend(extra_cmds or [])
    blob = b""
    if signature is not None:
        commands.append(_signature_cmd(0, len(signature)))
        blob = signature
    load = b"".join(commands)
    if signature is not None:
        dataoff = normalize.HEADER_SIZE + len(load)
        commands[-1] = _signature_cmd(dataoff, len(signature))
        load = b"".join(commands)
    ncmds = ncmds_override if ncmds_override is not None else len(commands)
    sizeofcmds = sizeofcmds_override if sizeofcmds_override is not None else len(load)
    header = struct.pack(
        "<IiiiIIII",
        magic if magic is not None else normalize.MH_MAGIC_64,
        cpu,
        0,
        filetype,
        ncmds,
        sizeofcmds,
        0,
        0,
    )
    data = header + load + blob
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
        missing = build_thin_dylib(extra_cmds=[])
        # Drop the UUID command by rebuilding without it.
        cpu = normalize.CPU_TYPE_ARM64
        load = _dylib_cmd(normalize.LC_ID_DYLIB, INSTALL) + _dylib_cmd(
            normalize.LC_LOAD_DYLIB, LIBSYSTEM
        )
        header = struct.pack("<IiiiIIII", normalize.MH_MAGIC_64, cpu, 0, normalize.MH_DYLIB, 2, len(load), 0, 0)
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
            "<IiiiIIII",
            normalize.MH_MAGIC_64,
            normalize.CPU_TYPE_ARM64,
            0,
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
        self.assertEqual(parsed.install_name, INSTALL)
        self.assertIsNone(parsed.signature)
        self.assertFalse(record["signed"])


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
        second = normalize.normalize_dylib(path, expected_arch="arm64")
        self.assertEqual(first["uuid"], second["uuid"])
        self.assertEqual(first["output_sha256"], second["output_sha256"])
        self.assertTrue(first["signed"])
        self.assertTrue(second["already_normalized"])
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
        self.assertEqual(parsed.install_name, INSTALL)

    def test_x86_64_normalize_keeps_arch_symbol_and_install_name(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        path = root / "libkardano_ed25519_bip32_signing.dylib"
        self._compile("x86_64", path)
        record = normalize.normalize_dylib(path, expected_arch="x86_64")
        parsed = normalize.parse_thin_dylib(path.read_bytes())
        self.assertEqual(parsed.arch, "x86_64")
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


if __name__ == "__main__":
    unittest.main()
