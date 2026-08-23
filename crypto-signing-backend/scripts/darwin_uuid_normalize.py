"""Post-link Darwin LC_UUID normalizer for existing-family JVM dylibs.

Apple TN3178: there is no supported Apple command that sets LC_UUID after
link. ld -no_uuid is refused by macos-26 dyld; -Wl,-reproducible still
emits a host-OS-bound UUID. This module is the documented rematch step
that runs *after* link-time remapping and the stable @rpath install name.

It does not implement a hash algorithm. Canonical bytes are digested with
Python's hashlib.sha256 (OpenSSL/system backend). The UUID is the first
16 bytes of that digest with RFC 9562 version 8 and RFC 4122 variant bits.

Scope is fail-closed and narrow:
- thin little-endian 64-bit MH_DYLIB only (arm64 or x86_64);
- reject fat, big-endian, truncated, unknown magic, or overlapping commands;
- exactly one LC_UUID; at most one LC_CODE_SIGNATURE;
- strip an existing ad-hoc signature with Apple codesign --remove-signature;
- patch only the 16 UUID bytes; all other unsigned bytes must stay identical;
- refuse unexpected architecture, LC_ID_DYLIB, dependents, or missing sign symbol.

Link determinism, UUID normalization, ad-hoc signature bytes, CHECKSUMS
identity, and source provenance are separate facts. A matching checksum
does not prove the bytes were produced from the visible Rust sources.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from native_toolchain import STABLE_INSTALL_NAME

SIGN_SYMBOL = "uniffi_kardano_ed25519_bip32_signing_fn_func_sign"
STABLE_IDENTIFIER = "org.sarmidev.kardano.ed25519-bip32-signing"
ALLOWED_DEPENDENTS = frozenset({"/usr/lib/libSystem.B.dylib"})

MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE
MH_MAGIC = 0xFEEDFACE
MH_CIGAM = 0xCEFAEDFE
FAT_MAGIC = 0xCAFEBABE
FAT_CIGAM = 0xBEBAFECA
FAT_MAGIC_64 = 0xCAFEBEEF
FAT_CIGAM_64 = 0xEFBEBAFE

MH_DYLIB = 0x6
CPU_TYPE_X86_64 = 0x01000007
CPU_TYPE_ARM64 = 0x0100000C
CPU_ARCH_ABI64 = 0x01000000

LC_REQ_DYLIB = 0x80000000
LC_UUID = 0x1B
LC_CODE_SIGNATURE = 0x1D
LC_ID_DYLIB = 0x0D
LC_LOAD_DYLIB = 0x0C
LC_LOAD_WEAK_DYLIB = 0x18
LC_REEXPORT_DYLIB = 0x1F
LC_LOAD_UPWARD_DYLIB = 0x23
LC_LAZY_LOAD_DYLIB = 0x20
LC_LOAD_DYLINKER = 0x0E

DYLIB_COMMANDS = {
    LC_LOAD_DYLIB,
    LC_LOAD_WEAK_DYLIB,
    LC_REEXPORT_DYLIB,
    LC_LOAD_UPWARD_DYLIB,
    LC_LAZY_LOAD_DYLIB,
}

HEADER_SIZE = 32
ARCH_BY_CPU = {
    CPU_TYPE_ARM64: "arm64",
    CPU_TYPE_X86_64: "x86_64",
}
CPU_BY_ARCH = {name: cpu for cpu, name in ARCH_BY_CPU.items()}


class NormalizeError(RuntimeError):
    pass


@dataclass
class LoadCommand:
    cmd: int
    cmdsize: int
    offset: int


@dataclass
class ThinDylib:
    data: bytes
    cputype: int
    arch: str
    ncmds: int
    sizeofcmds: int
    commands: list[LoadCommand] = field(default_factory=list)
    uuid_offset: int | None = None
    uuid: bytes | None = None
    signature: LoadCommand | None = None
    install_name: str | None = None
    dependents: list[str] = field(default_factory=list)


def _u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise NormalizeError(f"truncated u32 at {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def _i32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise NormalizeError(f"truncated i32 at {offset}")
    return struct.unpack_from("<i", data, offset)[0]


def _cstring(data: bytes, start: int, end: int) -> str:
    if start < 0 or end > len(data) or start >= end:
        raise NormalizeError("string field is out of bounds")
    raw = data[start:end]
    nul = raw.find(b"\x00")
    if nul < 0:
        raise NormalizeError("unterminated string field")
    return raw[:nul].decode("utf-8", errors="strict")


def parse_thin_dylib(data: bytes) -> ThinDylib:
    if len(data) < 4:
        raise NormalizeError("truncated Mach-O magic")
    magic = _u32(data, 0)
    if magic in {FAT_MAGIC, FAT_CIGAM, FAT_MAGIC_64, FAT_CIGAM_64}:
        raise NormalizeError("fat Mach-O is not supported")
    if magic in {MH_CIGAM_64, MH_MAGIC, MH_CIGAM}:
        raise NormalizeError("only thin little-endian 64-bit Mach-O is supported")
    if magic != MH_MAGIC_64:
        raise NormalizeError(f"unknown Mach-O magic {magic:#x}")
    if len(data) < HEADER_SIZE:
        raise NormalizeError("truncated Mach-O header")
    cputype = _i32(data, 4)
    filetype = _u32(data, 12)
    ncmds = _u32(data, 16)
    sizeofcmds = _u32(data, 20)
    if filetype != MH_DYLIB:
        raise NormalizeError(f"filetype {filetype} is not MH_DYLIB")
    arch = ARCH_BY_CPU.get(cputype)
    if arch is None:
        raise NormalizeError(f"unsupported cputype {cputype:#x}")
    if ncmds == 0:
        raise NormalizeError("ncmds is zero")
    if HEADER_SIZE + sizeofcmds > len(data):
        raise NormalizeError("sizeofcmds extends past the file")
    parsed = ThinDylib(
        data=data,
        cputype=cputype,
        arch=arch,
        ncmds=ncmds,
        sizeofcmds=sizeofcmds,
    )
    cursor = HEADER_SIZE
    limit = HEADER_SIZE + sizeofcmds
    uuid_cmds: list[LoadCommand] = []
    signature_cmds: list[LoadCommand] = []
    id_names: list[str] = []
    for _ in range(ncmds):
        if cursor + 8 > limit:
            raise NormalizeError("load command header exceeds sizeofcmds")
        cmd = _u32(data, cursor)
        cmdsize = _u32(data, cursor + 4)
        if cmdsize < 8 or cmdsize % 8 != 0:
            raise NormalizeError(f"invalid cmdsize {cmdsize} at {cursor}")
        if cursor + cmdsize > limit:
            raise NormalizeError("load command exceeds sizeofcmds")
        record = LoadCommand(cmd=cmd, cmdsize=cmdsize, offset=cursor)
        parsed.commands.append(record)
        cmd_kind = cmd & ~LC_REQ_DYLIB
        if cmd_kind == LC_UUID:
            if cmdsize != 24:
                raise NormalizeError(f"LC_UUID cmdsize {cmdsize} != 24")
            uuid_cmds.append(record)
            parsed.uuid_offset = cursor + 8
            parsed.uuid = bytes(data[cursor + 8 : cursor + 24])
        elif cmd_kind == LC_CODE_SIGNATURE:
            if cmdsize != 16:
                raise NormalizeError(f"LC_CODE_SIGNATURE cmdsize {cmdsize} != 16")
            dataoff = _u32(data, cursor + 8)
            datasize = _u32(data, cursor + 12)
            if dataoff < limit or datasize == 0 or dataoff + datasize > len(data):
                raise NormalizeError("LC_CODE_SIGNATURE blob is out of bounds")
            signature_cmds.append(record)
        elif cmd_kind == LC_ID_DYLIB:
            id_names.append(_dylib_name(data, record))
        elif cmd_kind in DYLIB_COMMANDS:
            parsed.dependents.append(_dylib_name(data, record))
        cursor += cmdsize
    if cursor != limit:
        raise NormalizeError("load commands do not fill sizeofcmds")
    if len(uuid_cmds) == 0:
        raise NormalizeError("LC_UUID is missing")
    if len(uuid_cmds) != 1:
        raise NormalizeError(f"expected exactly one LC_UUID, found {len(uuid_cmds)}")
    if len(signature_cmds) > 1:
        raise NormalizeError("multiple LC_CODE_SIGNATURE commands")
    if signature_cmds:
        parsed.signature = signature_cmds[0]
    if len(id_names) != 1:
        raise NormalizeError(f"expected exactly one LC_ID_DYLIB, found {len(id_names)}")
    parsed.install_name = id_names[0]
    return parsed


def _dylib_name(data: bytes, command: LoadCommand) -> str:
    if command.cmdsize < 24:
        raise NormalizeError("dylib command is shorter than 24 bytes")
    name_off = _u32(data, command.offset + 8)
    if name_off < 24 or name_off >= command.cmdsize:
        raise NormalizeError("dylib name offset is out of bounds")
    return _cstring(data, command.offset + name_off, command.offset + command.cmdsize)


def digest_uuid(canonical: bytes) -> bytes:
    digest = hashlib.sha256(canonical).digest()
    uuid = bytearray(digest[:16])
    # RFC 9562 UUID version 8 (custom) + RFC 4122 variant 10xx.
    uuid[6] = (uuid[6] & 0x0F) | 0x80
    uuid[8] = (uuid[8] & 0x3F) | 0x80
    return bytes(uuid)


def format_uuid(value: bytes) -> str:
    hexed = value.hex()
    return (
        f"{hexed[0:8]}-{hexed[8:12]}-{hexed[12:16]}-"
        f"{hexed[16:20]}-{hexed[20:32]}"
    ).upper()


def canonical_unsigned(data: bytes, uuid_offset: int) -> bytes:
    if uuid_offset + 16 > len(data):
        raise NormalizeError("LC_UUID payload is out of bounds")
    out = bytearray(data)
    out[uuid_offset : uuid_offset + 16] = b"\x00" * 16
    return bytes(out)


def assert_only_uuid_changed(before: bytes, after: bytes, uuid_offset: int) -> None:
    if len(before) != len(after):
        raise NormalizeError(
            f"unsigned size changed {len(before)} -> {len(after)}"
        )
    for index, (left, right) in enumerate(zip(before, after)):
        in_uuid = uuid_offset <= index < uuid_offset + 16
        if left != right and not in_uuid:
            raise NormalizeError(f"non-UUID byte changed at {index}")
        if in_uuid and left == right:
            # Allowed when the derived UUID happens to match the old one.
            continue


def _already_normalized(
    path: Path,
    parsed: ThinDylib,
    *,
    codesign: Path | None,
) -> bool:
    """True when this file already has our ad-hoc identifier and a UUID.

    codesign --remove-signature is not a perfect inverse of ad-hoc signing,
    so a second pass would hash different unsigned bytes. Treat an already
    verified signature with STABLE_IDENTIFIER as the normalized form.
    """
    text = display_signature(path, codesign=codesign)
    return (
        parsed.uuid is not None
        and f"Identifier={STABLE_IDENTIFIER}" in text
        and "Signature=adhoc" in text
    )


def resolve_codesign() -> Path:
    xcrun = shutil.which("xcrun")
    if xcrun is not None:
        completed = subprocess.run(
            [xcrun, "--find", "codesign"],
            capture_output=True,
            text=True,
            check=False,
        )
        path = (completed.stdout or "").strip()
        if completed.returncode == 0 and path:
            found = Path(path)
            if found.is_file():
                return found
    fallback = shutil.which("codesign")
    if fallback:
        return Path(fallback)
    raise NormalizeError("pinned Xcode codesign is required")


def run_codesign(args: list[str], *, codesign: Path | None = None) -> subprocess.CompletedProcess[str]:
    binary = codesign or resolve_codesign()
    completed = subprocess.run(
        [str(binary), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = ((completed.stderr or "") + (completed.stdout or "")).strip()
        raise NormalizeError(
            f"codesign {' '.join(args)} exited {completed.returncode}: {detail}"
        )
    return completed


def display_signature(path: Path, *, codesign: Path | None = None) -> str:
    binary = codesign or resolve_codesign()
    completed = subprocess.run(
        [str(binary), "-d", "--verbose=4", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return ((completed.stderr or "") + (completed.stdout or "")).strip()


def _require_expected_layout(parsed: ThinDylib, expected_arch: str) -> None:
    if parsed.arch != expected_arch:
        raise NormalizeError(f"architecture {parsed.arch} != {expected_arch}")
    if parsed.install_name != STABLE_INSTALL_NAME:
        raise NormalizeError(
            f"LC_ID_DYLIB {parsed.install_name!r} != {STABLE_INSTALL_NAME!r}"
        )
    unexpected = [name for name in parsed.dependents if name not in ALLOWED_DEPENDENTS]
    if unexpected:
        raise NormalizeError(f"unexpected dependent dylibs: {unexpected}")
    if not parsed.dependents:
        raise NormalizeError("dylib has no LC_LOAD_DYLIB dependents")


def _require_symbol(path: Path, nm: Callable[[Path], str] | None) -> str:
    if nm is not None:
        text = nm(path)
    else:
        llvm_nm = _llvm_nm()
        completed = subprocess.run(
            [llvm_nm, "-gU", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise NormalizeError(f"nm exited {completed.returncode}")
        text = (completed.stdout or "") + (completed.stderr or "")
    if SIGN_SYMBOL not in text:
        raise NormalizeError(f"{SIGN_SYMBOL} is not exported")
    return text


def _llvm_nm() -> str:
    completed = subprocess.run(
        ["rustc", "--print", "sysroot"],
        capture_output=True,
        text=True,
        check=False,
    )
    sysroot = ((completed.stdout or "") + (completed.stderr or "")).splitlines()
    if completed.returncode == 0 and sysroot:
        host = subprocess.run(
            ["rustc", "-vV"],
            capture_output=True,
            text=True,
            check=False,
        )
        host_triple = ""
        for line in (host.stdout or "").splitlines():
            if line.startswith("host:"):
                host_triple = line.split(":", 1)[1].strip()
        candidate = (
            Path(sysroot[0].strip())
            / "lib"
            / "rustlib"
            / host_triple
            / "bin"
            / "llvm-nm"
        )
        if candidate.is_file():
            return str(candidate)
    nm = shutil.which("llvm-nm") or shutil.which("nm")
    if nm is None:
        raise NormalizeError("nm/llvm-nm is required")
    return nm


def normalize_dylib(
    path: Path,
    *,
    expected_arch: str,
    sign: bool | None = None,
    nm: Callable[[Path], str] | None = None,
    codesign: Path | None = None,
    skip_codesign: bool = False,
) -> dict[str, object]:
    """Normalize LC_UUID from unsigned canonical bytes; sign arm64 ad hoc.

    ``sign`` defaults to True for arm64 and False for x86_64. Tests may
    inject ``nm`` or set ``skip_codesign`` to exercise the parser without
    Apple tools.
    """
    if expected_arch not in CPU_BY_ARCH:
        raise NormalizeError(f"unsupported expected arch {expected_arch}")
    original = path.read_bytes()
    parsed = parse_thin_dylib(original)
    _require_expected_layout(parsed, expected_arch)
    if sign is None:
        sign = expected_arch == "arm64"

    if (
        sign
        and not skip_codesign
        and parsed.signature is not None
        and _already_normalized(path, parsed, codesign=codesign)
    ):
        _require_symbol(path, nm)
        run_codesign(["--verify", "--strict", str(path)], codesign=codesign)
        assert parsed.uuid is not None
        return {
            "path": str(path),
            "arch": expected_arch,
            "removed_signature": False,
            "signed": True,
            "already_normalized": True,
            "identifier": STABLE_IDENTIFIER,
            "uuid": format_uuid(parsed.uuid),
            "canonical_sha256": None,
            "output_sha256": hashlib.sha256(original).hexdigest(),
            "unsigned_size": None,
            "output_size": len(original),
            "install_name": STABLE_INSTALL_NAME,
            "codesign_display": display_signature(path, codesign=codesign),
            "digest": "hashlib.sha256 first-16 RFC9562-v8",
        }

    removed_signature = False
    if parsed.signature is not None:
        if skip_codesign:
            raise NormalizeError("LC_CODE_SIGNATURE present but codesign is disabled")
        run_codesign(["--remove-signature", str(path)], codesign=codesign)
        removed_signature = True
        unsigned = path.read_bytes()
        parsed = parse_thin_dylib(unsigned)
        _require_expected_layout(parsed, expected_arch)
        if parsed.signature is not None:
            raise NormalizeError("codesign --remove-signature left LC_CODE_SIGNATURE")
    else:
        unsigned = original

    assert parsed.uuid_offset is not None
    before = bytes(unsigned)
    canonical = canonical_unsigned(before, parsed.uuid_offset)
    new_uuid = digest_uuid(canonical)
    patched = bytearray(before)
    patched[parsed.uuid_offset : parsed.uuid_offset + 16] = new_uuid
    assert_only_uuid_changed(before, bytes(patched), parsed.uuid_offset)
    path.write_bytes(patched)
    _require_symbol(path, nm)

    signature_text = ""
    signed = False
    if sign:
        if skip_codesign:
            raise NormalizeError("arm64 ad-hoc signing requires Apple codesign")
        run_codesign(
            [
                "--force",
                "-s",
                "-",
                "--identifier",
                STABLE_IDENTIFIER,
                "--timestamp=none",
                str(path),
            ],
            codesign=codesign,
        )
        run_codesign(["--verify", "--strict", str(path)], codesign=codesign)
        signature_text = display_signature(path, codesign=codesign)
        signed = True
        after = parse_thin_dylib(path.read_bytes())
        if after.uuid != new_uuid:
            raise NormalizeError("codesign changed LC_UUID")
        if after.install_name != STABLE_INSTALL_NAME:
            raise NormalizeError("codesign changed LC_ID_DYLIB")
        if after.arch != expected_arch:
            raise NormalizeError("codesign changed architecture")

    return {
        "path": str(path),
        "arch": expected_arch,
        "removed_signature": removed_signature,
        "signed": signed,
        "already_normalized": False,
        "identifier": STABLE_IDENTIFIER if signed else None,
        "uuid": format_uuid(new_uuid),
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
        "output_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "unsigned_size": len(patched),
        "output_size": path.stat().st_size,
        "install_name": STABLE_INSTALL_NAME,
        "codesign_display": signature_text,
        "digest": "hashlib.sha256 first-16 RFC9562-v8",
    }


def write_normalize_evidence(record: dict[str, object], dest: Path, artifact_id: str) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{artifact_id}.normalize.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
