"""Post-link Darwin LC_UUID normalizer for existing-family JVM dylibs.

Apple TN3178: there is no supported Apple command that sets LC_UUID after
link. ld -no_uuid is refused by macos-26 dyld; -Wl,-reproducible still
emits a host-OS-bound UUID. This module is the documented rematch step
that runs *after* link-time remapping and the stable @rpath install name.

It does not implement a hash algorithm. Canonical bytes are digested with
Python's hashlib.sha256 (OpenSSL/system backend). The UUID is the first
16 bytes of that digest with RFC 9562 version 8 and RFC 4122 variant bits.

Canonical representation (the SHA-256 input), applied in memory to a
private copy — never by trusting codesign --remove-signature as a hash
inverse:

1. Parse a thin little-endian 64-bit MH_DYLIB (arm64 ALL or x86_64 ALL).
2. Zero the 16 LC_UUID payload bytes.
3. If exactly one validated LC_CODE_SIGNATURE is present, also:
   - require it is the last load command;
   - require its blob is a non-overlapping suffix of __LINKEDIT that ends
     at EOF;
   - decrement ncmds and sizeofcmds by that command;
   - zero the 16-byte LC_CODE_SIGNATURE command;
   - set __LINKEDIT filesize to exclude the blob and vmsize to the
     architecture page-aligned value of that filesize;
   - truncate the image at the blob dataoff.
4. Digest those bytes with hashlib.sha256.

codesign --remove-signature is not a perfect inverse of ad-hoc signing
(it leaves __LINKEDIT vmsize/filesize inconsistent). The representation
above is therefore the only digest input. A valid ad-hoc signature with
the exact stable identifier is never accepted unless LC_UUID equals the
digest of this canonical image.

Allowed mutation ranges (fail-closed outside them):

- signature strip / unsigned materialize: Mach-O header ncmds and
  sizeofcmds; the 16-byte LC_CODE_SIGNATURE command; __LINKEDIT
  filesize and vmsize; truncation of the trailing signature blob.
- UUID patch: the 16 LC_UUID payload bytes only.
- re-sign: header ncmds/sizeofcmds; the added LC_CODE_SIGNATURE
  command; __LINKEDIT filesize/vmsize; the appended blob. __TEXT /
  __DATA / __DATA_CONST section payloads stay byte-identical.

Scope is fail-closed and narrow:

- thin little-endian 64-bit MH_DYLIB only (arm64 or x86_64);
- reject fat, big-endian, truncated, unknown magic, or overlapping commands;
- inspected commands match only their exact encodings from Xcode 26.6
  loader.h (LC_REQ_DYLD is not masked). Every Apple dylib dependency
  command is parsed (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB,
  LC_LOAD_UPWARD_DYLIB, LC_LAZY_LOAD_DYLIB) and fed to the same allowlist;
  only one LC_LOAD_DYLIB of /usr/lib/libSystem.B.dylib is accepted;
- exactly one LC_UUID; at most one LC_CODE_SIGNATURE;
- refuse unexpected architecture, CPU subtype, LC_ID_DYLIB, dependents,
  or missing sign symbol.

Link determinism, UUID normalization, ad-hoc signature bytes, CHECKSUMS
identity, and source provenance are separate facts. A matching checksum
does not prove the bytes were produced from the visible Rust sources.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import subprocess
import tempfile
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

# cpusubtype: low 24 bits are the subtype; high 8 are capability bits.
CPU_SUBTYPE_MASK = 0xFF000000
CPU_SUBTYPE_ARM64_ALL = 0x0
CPU_SUBTYPE_ARM64_V8 = 0x1
CPU_SUBTYPE_ARM64E = 0x2
CPU_SUBTYPE_X86_64_ALL = 0x3
CPU_SUBTYPE_LIB64 = 0x80000000

# Exact encodings from Xcode 26.6 / 17F113
# MacOSX.sdk/usr/include/mach-o/loader.h:
#   LC_REQ_DYLD 0x80000000 (line 279)
#   LC_LOAD_DYLIB 0xc (line 293) — no LC_REQ_DYLD
#   LC_ID_DYLIB 0xd (line 294) — no LC_REQ_DYLD
#   LC_LOAD_WEAK_DYLIB (0x18 | LC_REQ_DYLD) (line 311)
#   LC_UUID 0x1b (line 316)
#   LC_CODE_SIGNATURE 0x1d (line 318)
#   LC_REEXPORT_DYLIB (0x1f | LC_REQ_DYLD) (line 320)
#   LC_LAZY_LOAD_DYLIB 0x20 (line 321) — no LC_REQ_DYLD
#   LC_LOAD_UPWARD_DYLIB (0x23 | LC_REQ_DYLD) (line 325)
LC_REQ_DYLD = 0x80000000
LC_SEGMENT_64 = 0x19
LC_UUID = 0x1B
LC_CODE_SIGNATURE = 0x1D
LC_ID_DYLIB = 0x0D
LC_LOAD_DYLIB = 0x0C
LC_LOAD_WEAK_DYLIB = 0x18 | LC_REQ_DYLD
LC_REEXPORT_DYLIB = 0x1F | LC_REQ_DYLD
LC_LAZY_LOAD_DYLIB = 0x20
LC_LOAD_UPWARD_DYLIB = 0x23 | LC_REQ_DYLD
LC_SYMTAB = 0x2
LC_DYSYMTAB = 0xB
LC_DYLD_INFO_ONLY = 0x80000022
LC_FUNCTION_STARTS = 0x26
LC_DATA_IN_CODE = 0x29
LC_SOURCE_VERSION = 0x2A
LC_BUILD_VERSION = 0x32
LC_VERSION_MIN_MACOSX = 0x24

# Exact encodings only. loader.h defines command numbers in the low
# 8 bits and LC_REQ_DYLD (0x80000000) as the only high flag. Identity
# is therefore cmd & 0xFF; any other combination is rejected.
DEPENDENCY_COMMANDS = {
    LC_LOAD_DYLIB: "LC_LOAD_DYLIB",
    LC_LOAD_WEAK_DYLIB: "LC_LOAD_WEAK_DYLIB",
    LC_REEXPORT_DYLIB: "LC_REEXPORT_DYLIB",
    LC_LAZY_LOAD_DYLIB: "LC_LAZY_LOAD_DYLIB",
    LC_LOAD_UPWARD_DYLIB: "LC_LOAD_UPWARD_DYLIB",
}
INSPECTED_EXACT = {
    LC_UUID: "LC_UUID",
    LC_CODE_SIGNATURE: "LC_CODE_SIGNATURE",
    LC_ID_DYLIB: "LC_ID_DYLIB",
    **DEPENDENCY_COMMANDS,
}
EXACT_BY_BASE = {cmd & 0xFF: cmd for cmd in INSPECTED_EXACT}

HEADER_SIZE = 32
ARCH_BY_CPU = {
    CPU_TYPE_ARM64: "arm64",
    CPU_TYPE_X86_64: "x86_64",
}
CPU_BY_ARCH = {name: cpu for cpu, name in ARCH_BY_CPU.items()}
CPU_SUBTYPE_BY_ARCH = {
    "arm64": CPU_SUBTYPE_ARM64_ALL,
    "x86_64": CPU_SUBTYPE_X86_64_ALL,
}
PAGE_SIZE_BY_ARCH = {
    "arm64": 0x4000,
    "x86_64": 0x1000,
}

CS_ADHOC = 0x2
CODEDIRECTORY_FLAGS_RE = re.compile(
    r"flags=0x([0-9a-fA-F]+)\(([^)]*)\)"
)
CANONICAL_DIGEST = "hashlib.sha256 first-16 RFC9562-v8"
CANONICAL_REPRESENTATION = (
    "zero LC_UUID; exclude validated LC_CODE_SIGNATURE command/blob "
    "and restore ncmds/sizeofcmds/__LINKEDIT filesize/vmsize"
)


class NormalizeError(RuntimeError):
    pass


@dataclass
class LoadCommand:
    cmd: int
    cmdsize: int
    offset: int


@dataclass
class DependentDylib:
    cmd: int
    form: str
    name: str


@dataclass
class Section64:
    name: str
    segname: str
    offset: int
    size: int


@dataclass
class Segment64:
    offset: int
    name: str
    vmaddr: int
    vmsize: int
    fileoff: int
    filesize: int
    nsects: int
    vmsize_offset: int
    filesize_offset: int
    sections: list[Section64] = field(default_factory=list)


@dataclass
class CodeSignDisplay:
    identifier: str
    signature: str
    team_identifier: str
    flags: int
    flags_names: str
    authorities: tuple[str, ...]
    timestamp: str | None
    raw: str


@dataclass
class ThinDylib:
    data: bytes
    cputype: int
    cpusubtype: int
    cpu_capability: int
    arch: str
    ncmds: int
    sizeofcmds: int
    commands: list[LoadCommand] = field(default_factory=list)
    segments: list[Segment64] = field(default_factory=list)
    uuid_offset: int | None = None
    uuid: bytes | None = None
    signature: LoadCommand | None = None
    signature_dataoff: int | None = None
    signature_datasize: int | None = None
    linkedit: Segment64 | None = None
    install_name: str | None = None
    dependents: list[DependentDylib] = field(default_factory=list)


def _u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise NormalizeError(f"truncated u32 at {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    if offset + 8 > len(data):
        raise NormalizeError(f"truncated u64 at {offset}")
    return struct.unpack_from("<Q", data, offset)[0]


def _cstring(data: bytes, start: int, end: int) -> str:
    if start < 0 or end > len(data) or start >= end:
        raise NormalizeError("string field is out of bounds")
    raw = data[start:end]
    nul = raw.find(b"\x00")
    if nul < 0:
        raise NormalizeError("unterminated string field")
    return raw[:nul].decode("utf-8", errors="strict")


def _fixed_name(data: bytes, start: int, length: int = 16) -> str:
    """Mach-O segname/sectname are fixed-width and may omit a trailing NUL."""
    if start < 0 or start + length > len(data):
        raise NormalizeError("name field is out of bounds")
    raw = data[start : start + length]
    nul = raw.find(b"\x00")
    if nul >= 0:
        raw = raw[:nul]
    return raw.decode("ascii", errors="strict")


def _align_up(value: int, align: int) -> int:
    if align <= 0 or align & (align - 1):
        raise NormalizeError(f"invalid page size {align}")
    return (value + align - 1) & ~(align - 1)


def _ranges_overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


def _reject_illegal_inspected_encoding(cmd: int) -> None:
    """Reject any LC_REQ_DYLD mismatch for inspected/dependency commands.

    Commands that include LC_REQ_DYLD in the Apple header must have that
    bit set exactly once (the header encoding). Commands that do not
    include it must not have the bit. Extra bits (including 0x40000000
    "double flag" variants) are also rejected: identity is cmd & 0xFF.
    """
    identity = cmd & 0xFF
    expected = EXACT_BY_BASE.get(identity)
    if expected is None:
        return
    if cmd != expected:
        name = INSPECTED_EXACT[expected]
        raise NormalizeError(
            f"illegal flag combination for {name}: {cmd:#x}"
        )


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
    cputype = _u32(data, 4)
    cpusubtype_raw = _u32(data, 8)
    filetype = _u32(data, 12)
    ncmds = _u32(data, 16)
    sizeofcmds = _u32(data, 20)
    if filetype != MH_DYLIB:
        raise NormalizeError(f"filetype {filetype} is not MH_DYLIB")
    arch = ARCH_BY_CPU.get(cputype)
    if arch is None:
        raise NormalizeError(f"unsupported cputype {cputype:#x}")
    capability = cpusubtype_raw & CPU_SUBTYPE_MASK
    subtype = cpusubtype_raw & ~CPU_SUBTYPE_MASK
    expected_subtype = CPU_SUBTYPE_BY_ARCH[arch]
    if capability != 0 or subtype != expected_subtype:
        raise NormalizeError(
            f"unsupported {arch} cpusubtype {cpusubtype_raw:#x} "
            f"(require ordinary {expected_subtype:#x} with no capability bits)"
        )
    if ncmds == 0:
        raise NormalizeError("ncmds is zero")
    if HEADER_SIZE + sizeofcmds > len(data):
        raise NormalizeError("sizeofcmds extends past the file")
    parsed = ThinDylib(
        data=data,
        cputype=cputype,
        cpusubtype=subtype,
        cpu_capability=capability,
        arch=arch,
        ncmds=ncmds,
        sizeofcmds=sizeofcmds,
    )
    cursor = HEADER_SIZE
    limit = HEADER_SIZE + sizeofcmds
    uuid_cmds: list[LoadCommand] = []
    signature_cmds: list[LoadCommand] = []
    id_names: list[str] = []
    linkedits: list[Segment64] = []
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
        _reject_illegal_inspected_encoding(cmd)
        if cmd == LC_SEGMENT_64:
            parsed.segments.append(_parse_segment64(data, record))
            if parsed.segments[-1].name == "__LINKEDIT":
                linkedits.append(parsed.segments[-1])
        elif cmd == LC_UUID:
            if cmdsize != 24:
                raise NormalizeError(f"LC_UUID cmdsize {cmdsize} != 24")
            uuid_cmds.append(record)
            parsed.uuid_offset = cursor + 8
            parsed.uuid = bytes(data[cursor + 8 : cursor + 24])
        elif cmd == LC_CODE_SIGNATURE:
            if cmdsize != 16:
                raise NormalizeError(f"LC_CODE_SIGNATURE cmdsize {cmdsize} != 16")
            dataoff = _u32(data, cursor + 8)
            datasize = _u32(data, cursor + 12)
            parsed.signature_dataoff = dataoff
            parsed.signature_datasize = datasize
            signature_cmds.append(record)
        elif cmd == LC_ID_DYLIB:
            id_names.append(_dylib_name(data, record))
        elif cmd in DEPENDENCY_COMMANDS:
            parsed.dependents.append(
                DependentDylib(
                    cmd=cmd,
                    form=DEPENDENCY_COMMANDS[cmd],
                    name=_dylib_name(data, record),
                )
            )
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
        _require_signature_range(parsed, linkedits)
    elif len(linkedits) > 1:
        raise NormalizeError("multiple __LINKEDIT segments")
    elif linkedits:
        parsed.linkedit = linkedits[0]
    if len(id_names) != 1:
        raise NormalizeError(f"expected exactly one LC_ID_DYLIB, found {len(id_names)}")
    parsed.install_name = id_names[0]
    return parsed


def _parse_segment64(data: bytes, command: LoadCommand) -> Segment64:
    if command.cmdsize < 72:
        raise NormalizeError("LC_SEGMENT_64 is shorter than 72 bytes")
    name = _fixed_name(data, command.offset + 8)
    vmaddr = _u64(data, command.offset + 24)
    vmsize = _u64(data, command.offset + 32)
    fileoff = _u64(data, command.offset + 40)
    filesize = _u64(data, command.offset + 48)
    nsects = _u32(data, command.offset + 64)
    expected = 72 + nsects * 80
    if command.cmdsize != expected:
        raise NormalizeError(
            f"LC_SEGMENT_64 cmdsize {command.cmdsize} != {expected}"
        )
    if fileoff + filesize > len(data):
        raise NormalizeError(f"segment {name} file range exceeds the file")
    segment = Segment64(
        offset=command.offset,
        name=name,
        vmaddr=vmaddr,
        vmsize=vmsize,
        fileoff=fileoff,
        filesize=filesize,
        nsects=nsects,
        vmsize_offset=command.offset + 32,
        filesize_offset=command.offset + 48,
    )
    for index in range(nsects):
        sect_off = command.offset + 72 + index * 80
        sect_name = _fixed_name(data, sect_off)
        segname = _fixed_name(data, sect_off + 16)
        size = _u64(data, sect_off + 40)
        offset = _u32(data, sect_off + 48)
        if size and offset + size > len(data):
            raise NormalizeError(f"section {sect_name} exceeds the file")
        segment.sections.append(
            Section64(name=sect_name, segname=segname, offset=offset, size=size)
        )
    return segment


def _require_signature_range(parsed: ThinDylib, linkedits: list[Segment64]) -> None:
    assert parsed.signature is not None
    assert parsed.signature_dataoff is not None
    assert parsed.signature_datasize is not None
    dataoff = parsed.signature_dataoff
    datasize = parsed.signature_datasize
    data = parsed.data
    limit = HEADER_SIZE + parsed.sizeofcmds
    if datasize == 0:
        raise NormalizeError("LC_CODE_SIGNATURE datasize is zero")
    if dataoff < limit:
        raise NormalizeError("LC_CODE_SIGNATURE overlaps load commands")
    if dataoff + datasize < dataoff:
        raise NormalizeError("LC_CODE_SIGNATURE dataoff/datasize overflow")
    if dataoff + datasize > len(data):
        raise NormalizeError("LC_CODE_SIGNATURE blob is out of bounds")
    if dataoff + datasize != len(data):
        raise NormalizeError("LC_CODE_SIGNATURE blob must end exactly at EOF")
    if parsed.signature.offset + parsed.signature.cmdsize != limit:
        raise NormalizeError("LC_CODE_SIGNATURE is not the last load command")
    if len(linkedits) == 0:
        raise NormalizeError("LC_CODE_SIGNATURE requires exactly one __LINKEDIT")
    if len(linkedits) != 1:
        raise NormalizeError("multiple __LINKEDIT segments")
    linkedit = linkedits[0]
    parsed.linkedit = linkedit
    link_end = linkedit.fileoff + linkedit.filesize
    if link_end != len(data):
        raise NormalizeError("__LINKEDIT file range must end exactly at EOF")
    if not (linkedit.fileoff <= dataoff and dataoff + datasize <= link_end):
        raise NormalizeError("LC_CODE_SIGNATURE blob is not inside __LINKEDIT")
    for segment in parsed.segments:
        if segment.name == "__LINKEDIT":
            continue
        if _ranges_overlap(
            segment.fileoff,
            segment.fileoff + segment.filesize,
            dataoff,
            dataoff + datasize,
        ):
            raise NormalizeError(
                f"LC_CODE_SIGNATURE overlaps segment {segment.name}"
            )


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


def canonical_image(parsed: ThinDylib) -> bytes:
    """Return the documented SHA-256 input for LC_UUID derivation."""
    if parsed.uuid_offset is None or parsed.uuid is None:
        raise NormalizeError("LC_UUID payload is missing")
    out = bytearray(parsed.data)
    out[parsed.uuid_offset : parsed.uuid_offset + 16] = b"\x00" * 16
    if parsed.signature is None:
        return bytes(out)
    if (
        parsed.signature_dataoff is None
        or parsed.signature_datasize is None
        or parsed.linkedit is None
    ):
        raise NormalizeError("LC_CODE_SIGNATURE layout is incomplete")
    new_ncmds = parsed.ncmds - 1
    new_sizeofcmds = parsed.sizeofcmds - parsed.signature.cmdsize
    struct.pack_into("<I", out, 16, new_ncmds)
    struct.pack_into("<I", out, 20, new_sizeofcmds)
    sig = parsed.signature
    out[sig.offset : sig.offset + sig.cmdsize] = b"\x00" * sig.cmdsize
    new_filesize = parsed.signature_dataoff - parsed.linkedit.fileoff
    if new_filesize < 0:
        raise NormalizeError("LC_CODE_SIGNATURE dataoff precedes __LINKEDIT")
    new_vmsize = _align_up(new_filesize, PAGE_SIZE_BY_ARCH[parsed.arch])
    struct.pack_into("<Q", out, parsed.linkedit.vmsize_offset, new_vmsize)
    struct.pack_into("<Q", out, parsed.linkedit.filesize_offset, new_filesize)
    return bytes(out[: parsed.signature_dataoff])


def unsigned_image(parsed: ThinDylib) -> bytes:
    """Valid unsigned Mach-O with the original UUID restored."""
    image = bytearray(canonical_image(parsed))
    assert parsed.uuid_offset is not None and parsed.uuid is not None
    if parsed.uuid_offset + 16 > len(image):
        raise NormalizeError("LC_UUID payload is outside the unsigned image")
    image[parsed.uuid_offset : parsed.uuid_offset + 16] = parsed.uuid
    return bytes(image)


def canonical_unsigned(data: bytes, uuid_offset: int) -> bytes:
    """Unsigned-only helper used by tests: zero LC_UUID, keep the rest."""
    parsed = parse_thin_dylib(data)
    if parsed.signature is not None:
        return canonical_image(parsed)
    if parsed.uuid_offset != uuid_offset:
        raise NormalizeError("uuid_offset does not match parsed LC_UUID")
    return canonical_image(parsed)


def changed_offsets(before: bytes, after: bytes) -> list[int]:
    changed = [index for index, (left, right) in enumerate(zip(before, after)) if left != right]
    if len(after) > len(before):
        changed.extend(range(len(before), len(after)))
    return changed


def _offset_in_ranges(index: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in ranges)


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


def unsigned_mutation_ranges(signed: ThinDylib) -> list[tuple[int, int]]:
    """Header / LC_CODE_SIGNATURE / __LINKEDIT fields plus the blob."""
    if signed.signature is None or signed.linkedit is None:
        return []
    ranges = [
        (16, 24),  # ncmds + sizeofcmds
        (signed.signature.offset, signed.signature.offset + signed.signature.cmdsize),
        (signed.linkedit.vmsize_offset, signed.linkedit.vmsize_offset + 8),
        (signed.linkedit.filesize_offset, signed.linkedit.filesize_offset + 8),
    ]
    assert signed.signature_dataoff is not None
    ranges.append((signed.signature_dataoff, len(signed.data)))
    return ranges


def assert_unsigned_mutations_documented(before: bytes, after: bytes, signed: ThinDylib) -> None:
    if signed.signature is None:
        if before != after:
            raise NormalizeError("unsigned image changed a file with no signature")
        return
    allowed = unsigned_mutation_ranges(signed)
    dataoff = signed.signature_dataoff
    if dataoff is None:
        raise NormalizeError("signed image is missing LC_CODE_SIGNATURE dataoff")
    if len(after) != dataoff:
        raise NormalizeError(
            f"unsigned image size {len(after)} != signature dataoff {dataoff}"
        )
    if len(before) < dataoff:
        raise NormalizeError("signed file is shorter than LC_CODE_SIGNATURE dataoff")
    for index, (left, right) in enumerate(zip(before[:dataoff], after)):
        if left != right and not _offset_in_ranges(index, allowed):
            raise NormalizeError(f"unexpected unsigned mutation at {index}")


def section_payload_ranges(parsed: ThinDylib) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    load_end = HEADER_SIZE + parsed.sizeofcmds
    for segment in parsed.segments:
        if segment.name == "__LINKEDIT":
            continue
        if segment.sections:
            for section in segment.sections:
                if section.size == 0:
                    continue
                if section.offset < load_end:
                    continue
                ranges.append((section.offset, section.offset + section.size))
        else:
            start = segment.fileoff
            end = segment.fileoff + segment.filesize
            if start < load_end:
                start = load_end
            if start < end:
                ranges.append((start, end))
    return ranges


def assert_sign_mutations_documented(
    before: bytes,
    after: bytes,
    unsigned: ThinDylib,
    signed: ThinDylib,
) -> None:
    if signed.signature is None:
        raise NormalizeError("re-sign did not produce LC_CODE_SIGNATURE")
    allowed = unsigned_mutation_ranges(signed)
    if len(after) < len(before):
        raise NormalizeError("re-sign shrank the file")
    for index, (left, right) in enumerate(zip(before, after)):
        if left != right and not _offset_in_ranges(index, allowed):
            raise NormalizeError(f"unexpected sign mutation at {index}")
    before_sections = section_payload_ranges(unsigned)
    after_parsed = signed
    after_sections = section_payload_ranges(after_parsed)
    if len(before_sections) != len(after_sections):
        raise NormalizeError("re-sign changed section layout")
    for (b0, b1), (a0, a1) in zip(before_sections, after_sections):
        if (b0, b1) != (a0, a1) or before[b0:b1] != after[a0:a1]:
            raise NormalizeError("re-sign changed a code/data/text section")


def parse_codesign_display(text: str) -> CodeSignDisplay:
    fields: dict[str, str] = {}
    authorities: list[str] = []
    flags = 0
    flags_names = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = CODEDIRECTORY_FLAGS_RE.search(line)
        if match:
            flags = int(match.group(1), 16)
            flags_names = match.group(2)
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "Authority":
            authorities.append(value)
            continue
        if key not in fields:
            fields[key] = value
    return CodeSignDisplay(
        identifier=fields.get("Identifier", ""),
        signature=fields.get("Signature", ""),
        team_identifier=fields.get("TeamIdentifier", ""),
        flags=flags,
        flags_names=flags_names,
        authorities=tuple(authorities),
        timestamp=fields.get("Timestamp"),
        raw=text,
    )


def require_expected_ad_hoc(display: CodeSignDisplay) -> None:
    if display.identifier != STABLE_IDENTIFIER:
        raise NormalizeError(
            f"codesign Identifier {display.identifier!r} != {STABLE_IDENTIFIER!r}"
        )
    if display.signature != "adhoc":
        raise NormalizeError(f"codesign Signature {display.signature!r} is not adhoc")
    if display.team_identifier != "not set":
        raise NormalizeError(
            f"codesign TeamIdentifier {display.team_identifier!r} is not 'not set'"
        )
    if display.flags & CS_ADHOC == 0 and "adhoc" not in display.flags_names.split(","):
        raise NormalizeError(
            f"codesign flags {display.flags:#x}({display.flags_names}) are not adhoc"
        )
    if display.timestamp not in {None, "", "none", "not set"}:
        raise NormalizeError(f"codesign Timestamp {display.timestamp!r} is not allowed")
    for authority in display.authorities:
        if "timestamp" in authority.lower():
            raise NormalizeError(f"codesign Authority includes timestamp: {authority!r}")


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
    unexpected = [dep.name for dep in parsed.dependents if dep.name not in ALLOWED_DEPENDENTS]
    if unexpected:
        raise NormalizeError(f"unexpected dependent dylibs: {unexpected}")
    unexpected_forms = [dep.form for dep in parsed.dependents if dep.cmd != LC_LOAD_DYLIB]
    if unexpected_forms:
        raise NormalizeError(f"unexpected dependency form: {unexpected_forms}")
    load_dylibs = [dep for dep in parsed.dependents if dep.cmd == LC_LOAD_DYLIB]
    if len(load_dylibs) != 1:
        raise NormalizeError(
            f"expected exactly one LC_LOAD_DYLIB, found {len(load_dylibs)}"
        )


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


def _record(
    *,
    path: Path,
    expected_arch: str,
    new_uuid: bytes,
    canonical: bytes,
    removed_signature: bool,
    signed: bool,
    mutated: bool,
    signature_text: str,
    output: bytes,
) -> dict[str, object]:
    return {
        "path": str(path),
        "arch": expected_arch,
        "removed_signature": removed_signature,
        "signed": signed,
        "mutated": mutated,
        "identifier": STABLE_IDENTIFIER if signed else None,
        "uuid": format_uuid(new_uuid),
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
        "canonical_representation": CANONICAL_REPRESENTATION,
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "unsigned_size": len(canonical) if not signed or mutated else None,
        "output_size": len(output),
        "install_name": STABLE_INSTALL_NAME,
        "codesign_display": signature_text,
        "digest": CANONICAL_DIGEST,
    }


def normalize_dylib(
    path: Path,
    *,
    expected_arch: str,
    sign: bool | None = None,
    nm: Callable[[Path], str] | None = None,
    codesign: Path | None = None,
    skip_codesign: bool = False,
) -> dict[str, object]:
    """Normalize LC_UUID from the documented canonical image; sign arm64 ad hoc.

    ``sign`` defaults to True for arm64 and False for x86_64. Tests may
    inject ``nm`` or set ``skip_codesign`` to exercise the parser without
    Apple tools. A signed input with the exact stable identifier is
    verified against the canonical digest on every pass; it is never
    accepted solely because codesign --verify succeeds.
    """
    if expected_arch not in CPU_BY_ARCH:
        raise NormalizeError(f"unsupported expected arch {expected_arch}")
    original = path.read_bytes()
    parsed = parse_thin_dylib(original)
    _require_expected_layout(parsed, expected_arch)
    if sign is None:
        sign = expected_arch == "arm64"

    # Private copy: hash the in-memory canonical image, never the file
    # after codesign --remove-signature, and never mutate ``path`` to
    # compute the expected UUID.
    canonical = canonical_image(parsed)
    new_uuid = digest_uuid(canonical)

    if parsed.signature is not None:
        if skip_codesign:
            raise NormalizeError("LC_CODE_SIGNATURE present but codesign is disabled")
        # Verify the blob before classifying the identifier. A tampered
        # signature must not be rewritten as if it were a linker signature.
        run_codesign(["--verify", "--strict", str(path)], codesign=codesign)
        display = parse_codesign_display(display_signature(path, codesign=codesign))
        if display.identifier == STABLE_IDENTIFIER:
            require_expected_ad_hoc(display)
            run_codesign(["--verify", "--strict", str(path)], codesign=codesign)
            if parsed.uuid != new_uuid:
                raise NormalizeError(
                    "LC_UUID does not match canonical digest; "
                    "valid ad-hoc exact-identifier signature is not sufficient"
                )
            if not sign:
                raise NormalizeError("signed input is not allowed when sign=False")
            _require_symbol(path, nm)
            return _record(
                path=path,
                expected_arch=expected_arch,
                new_uuid=new_uuid,
                canonical=canonical,
                removed_signature=False,
                signed=True,
                mutated=False,
                signature_text=display.raw,
                output=original,
            )
        # Foreign / linker signature: materialize the unsigned image.

    unsigned = unsigned_image(parsed)
    if parsed.signature is not None:
        assert_unsigned_mutations_documented(original, unsigned, parsed)
        stripped = parse_thin_dylib(unsigned)
        if stripped.signature is not None:
            raise NormalizeError("canonical unsigned image still has LC_CODE_SIGNATURE")
        _require_expected_layout(stripped, expected_arch)
    assert parsed.uuid_offset is not None
    patched = bytearray(unsigned)
    patched[parsed.uuid_offset : parsed.uuid_offset + 16] = new_uuid
    assert_only_uuid_changed(unsigned, bytes(patched), parsed.uuid_offset)
    mutated = bytes(patched) != original or bool(sign and parsed.signature is None)
    path.write_bytes(patched)
    _require_symbol(path, nm)

    signature_text = ""
    signed = False
    if sign:
        if skip_codesign:
            raise NormalizeError("arm64 ad-hoc signing requires Apple codesign")
        before_sign = bytes(patched)
        unsigned_parsed = parse_thin_dylib(before_sign)
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
        after_bytes = path.read_bytes()
        after = parse_thin_dylib(after_bytes)
        assert_sign_mutations_documented(before_sign, after_bytes, unsigned_parsed, after)
        if after.uuid != new_uuid:
            raise NormalizeError("codesign changed LC_UUID")
        if after.install_name != STABLE_INSTALL_NAME:
            raise NormalizeError("codesign changed LC_ID_DYLIB")
        if after.arch != expected_arch:
            raise NormalizeError("codesign changed architecture")
        display = parse_codesign_display(display_signature(path, codesign=codesign))
        require_expected_ad_hoc(display)
        if digest_uuid(canonical_image(after)) != new_uuid:
            raise NormalizeError("re-sign changed the canonical unsigned representation")
        signature_text = display.raw
        signed = True
        mutated = True

    output = path.read_bytes()
    return _record(
        path=path,
        expected_arch=expected_arch,
        new_uuid=new_uuid,
        canonical=canonical,
        removed_signature=parsed.signature is not None,
        signed=signed,
        mutated=mutated,
        signature_text=signature_text,
        output=output,
    )


def verify_signed_canonical_uuid(
    path: Path,
    *,
    expected_arch: str,
    codesign: Path | None = None,
) -> bytes:
    """Temp-copy strip/canonicalize a signed input and require LC_UUID.

    The original file is not written. Used by tests and as the signed-input
    path inside ``normalize_dylib``.
    """
    original = path.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / path.name
        copy.write_bytes(original)
        parsed = parse_thin_dylib(copy.read_bytes())
        _require_expected_layout(parsed, expected_arch)
        if parsed.signature is None:
            raise NormalizeError("expected a signed input")
        display = parse_codesign_display(display_signature(copy, codesign=codesign))
        require_expected_ad_hoc(display)
        run_codesign(["--verify", "--strict", str(copy)], codesign=codesign)
        expected = digest_uuid(canonical_image(parsed))
        if parsed.uuid != expected:
            raise NormalizeError(
                "LC_UUID does not match canonical digest; "
                "valid ad-hoc exact-identifier signature is not sufficient"
            )
        if copy.read_bytes() != original:
            raise NormalizeError("canonical verification mutated the temp copy unexpectedly")
    if path.read_bytes() != original:
        raise NormalizeError("canonical verification mutated the original file")
    return expected


def write_normalize_evidence(record: dict[str, object], dest: Path, artifact_id: str) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{artifact_id}.normalize.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
