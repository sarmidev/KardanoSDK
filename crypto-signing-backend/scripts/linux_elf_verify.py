"""Fail-closed ELF64 verifier for the Linux x86-64 JVM signing cdylib.

Numeric encodings are from glibc ``elf.h`` / LSB Core (ELF64). This
module does not invent command numbers. Scope is the JNA resource
``linux-x86-64/libkardano_ed25519_bip32_signing.so`` only — Linux ARM,
musl, and older-than-baseline glibc are out of scope and rejected.

Policy (documented, not a strength claim):

- ELFCLASS64, ELFDATA2LSB, ``e_version == EV_CURRENT``, ET_DYN, EM_X86_64
- SONAME exactly ``libkardano_ed25519_bip32_signing.so``
- DT_NEEDED names are a non-empty subset of the glibc/libgcc allowlist
  and must include ``libc.so.6``
- DT_RPATH and DT_RUNPATH are absent
- NT_GNU_BUILD_ID is absent (link with ``-Wl,--build-id=none``)
- no ``.debug_*``, ``.zdebug_*``, ``.gnu_debuglink``, ``.gnu_debugaltlink``,
  or ``.gnu_debugdata`` sections
- required UniFFI sign symbol is an exact ``.dynsym`` export: defined,
  ``STT_FUNC``, ``STB_GLOBAL`` or ``STB_WEAK``, ``STV_DEFAULT`` or
  ``STV_PROTECTED``, valid nonzero section/value; ``nm -D --defined-only
  --format=posix`` must corroborate an exact record (never substring)
- GNU version requirements (``DT_VERNEED`` plus ``readelf --version-info``)
  accept only full-string authoritative ``GLIBC_<major>.<minor>`` or
  legacy ``GLIBC_<major>.<minor>.<patch>`` labels (no leading zeros,
  signs, suffixes, empty components, or more than three components).
  ``GLIBC_PRIVATE`` and every unparseable ``GLIBC_*`` label fail.
  Comparison is the numeric tuple against baseline ``(2, 35, 0)``.
- ``DT_VERNEED`` / ``DT_VERNEEDNUM`` bind to exactly one
  ``SHT_GNU_verneed`` (``.gnu.version_r``) range; chains must terminate
  with ``vn_next == 0`` / ``vna_next == 0`` and reject overlap, cycles,
  and out-of-section offsets
- section 0 is the canonical ``SHT_NULL``; extended numbering is
  rejected; ``.dynamic`` is exactly one ``SHT_DYNAMIC`` with
  ``Elf64_Dyn`` entsize, ``sh_link`` to ``.dynstr``, and exact file
  correspondence with the single ``PT_DYNAMIC``
- printable NUL-terminated absolute path-like strings (leading ``/``,
  first component starts with a letter/``_``/``.``, and is either at
  least two characters or followed by ``/``) may use only documented
  remap prefixes (including rustc ``/rust/deps``) and the listed
  runtime prefixes, matched as ``path == prefix`` or
  ``path.startswith(prefix + "/")``. Fragments such as ``/0`` and
  ``/N`` are not paths.
"""

from __future__ import annotations

import re
import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SIGN_SYMBOL = "uniffi_kardano_ed25519_bip32_signing_fn_func_sign"
STABLE_SONAME = "libkardano_ed25519_bip32_signing.so"
JNA_RESOURCE_PREFIX = "linux-x86-64"

# glibc elf.h
ELFMAG = b"\x7fELF"
EI_CLASS = 4
ELFCLASS64 = 2
EI_DATA = 5
ELFDATA2LSB = 1
EI_VERSION = 6
EV_CURRENT = 1
ET_DYN = 3
EM_X86_64 = 62
EM_AARCH64 = 183
PT_LOAD = 1
PT_DYNAMIC = 2
PT_NOTE = 4
SHT_NULL = 0
SHT_PROGBITS = 1
SHT_STRTAB = 3
SHT_DYNAMIC = 6
SHT_NOTE = 7
SHT_NOBITS = 8
SHT_DYNSYM = 11
SHT_GNU_VERDEF = 0x6FFFFFFD
SHT_GNU_VERNEED = 0x6FFFFFFE
SHT_GNU_VERSYM = 0x6FFFFFFF
SHF_ALLOC = 0x2
DT_NULL = 0
DT_NEEDED = 1
DT_STRTAB = 5
DT_SYMTAB = 6
DT_STRSZ = 10
DT_SYMENT = 11
DT_SONAME = 14
DT_RPATH = 15
DT_RUNPATH = 29
DT_VERSYM = 0x6FFFFFF0
DT_VERDEF = 0x6FFFFFFC
DT_VERDEFNUM = 0x6FFFFFFD
DT_VERNEED = 0x6FFFFFFE
DT_VERNEEDNUM = 0x6FFFFFFF
NT_GNU_BUILD_ID = 3
STB_LOCAL = 0
STB_GLOBAL = 1
STB_WEAK = 2
STT_NOTYPE = 0
STT_OBJECT = 1
STT_FUNC = 2
STV_DEFAULT = 0
STV_INTERNAL = 1
STV_HIDDEN = 2
STV_PROTECTED = 3
SHN_UNDEF = 0
SHN_LORESERVE = 0xFF00
PN_XNUM = 0xFFFF
SHN_XINDEX = 0xFFFF
VER_NEED_CURRENT = 1

ELF64_EHDR_SIZE = 64
ELF64_PHDR_SIZE = 56
ELF64_SHDR_SIZE = 64
ELF64_DYN_SIZE = 16
ELF64_SYM_SIZE = 24
ELF64_VERNEED_SIZE = 16
ELF64_VERNAUX_SIZE = 16

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_PHNUM = 128
MAX_SHNUM = 256
MAX_DYNAMIC_TAGS = 256
MAX_NEEDED = 16
MAX_NOTE_BYTES = 4096
MAX_DYNSYM = 4096
MAX_VERNEED = 16
MAX_VERNAUX = 32

# Typical rustc 1.97 x86_64-unknown-linux-gnu cdylib DT_NEEDED set.
# Extra names fail. Linux ARM loader names are not listed.
ALLOWED_NEEDED = frozenset(
    {
        "libc.so.6",
        "libgcc_s.so.1",
        "libm.so.6",
        "ld-linux-x86-64.so.2",
        "libpthread.so.0",
        "librt.so.1",
        "libdl.so.2",
    }
)
REQUIRED_NEEDED = frozenset({"libc.so.6"})

# Documented consumer floor: Ubuntu 22.04 glibc. Measured at rebuild time.
DOCUMENTED_GLIBC_BASELINE = (2, 35, 0)
DOCUMENTED_GLIBC_BASELINE_LABEL = "2.35"

SINGLETON_DYNAMIC_TAGS = frozenset(
    {
        DT_STRTAB,
        DT_STRSZ,
        DT_SYMTAB,
        DT_SYMENT,
        DT_SONAME,
        DT_RPATH,
        DT_RUNPATH,
        DT_VERSYM,
        DT_VERDEF,
        DT_VERDEFNUM,
        DT_VERNEED,
        DT_VERNEEDNUM,
    }
)

FORBIDDEN_DEBUG_SECTIONS = frozenset(
    {
        ".gnu_debuglink",
        ".gnu_debugaltlink",
        ".gnu_debugdata",
    }
)
DEBUG_SECTION_PREFIXES = (".debug_", ".zdebug_")

# rustc --remap-path-prefix destinations used by native_toolchain.remap_pairs.
ALLOWED_REMAP_PREFIXES = (
    "/cargo-target",  # staging-owned CARGO_TARGET_DIR
    "/kardano",  # repository / module root
    "/rustc",  # rustc sysroot (our --remap-path-prefix)
    "/rust/deps",  # rustc 1.97 compiler-crate remap (panic/backtrace)
    "/rustup",  # RUSTUP_HOME
    "/cargo",  # CARGO_HOME
    "/home/rebuild",  # $HOME
    "/runner-temp",  # GHA RUNNER_TEMP (not always under the repo)
    "/runner-workspace",  # GHA RUNNER_WORKSPACE
)
# Runtime/system prefixes that a glibc x86-64 ET_DYN may embed (PT_INTERP
# and multiarch loader/libgcc realpaths). /usr/local and /tmp are not listed.
ALLOWED_RUNTIME_PREFIXES = (
    "/lib64",
    "/lib",
    "/usr/lib",
    "/usr/lib64",
)
ALLOWED_ABSOLUTE_PREFIXES = ALLOWED_REMAP_PREFIXES + ALLOWED_RUNTIME_PREFIXES

NM_DEFINED_FUNC_TYPES = frozenset({"T", "W"})
# Authoritative glibc labels: two components, or legacy three (GLIBC_2.2.5).
# No leading zeros, signs, empty components, suffixes, or >3 components.
_GLIBC_COMPONENT = r"(?:0|[1-9]\d*)"
GLIBC_NAME_RE = re.compile(
    rf"^GLIBC_({_GLIBC_COMPONENT})\.({_GLIBC_COMPONENT})(?:\.({_GLIBC_COMPONENT}))?$"
)
LDD_GLIBC_RE = re.compile(
    r"(?:GLIBC|GNU libc)\s+(\d+)\.(\d+)(?:\.(\d+))?",
    re.IGNORECASE,
)
READELF_VER_NAME_RE = re.compile(r"\bName:\s+(\S+)")


class ElfError(RuntimeError):
    pass


@dataclass
class LoadSegment:
    offset: int
    filesz: int
    vaddr: int
    memsz: int


@dataclass
class Section:
    index: int
    name: str
    sh_type: int
    sh_addr: int
    sh_offset: int
    sh_size: int
    sh_flags: int
    sh_link: int
    sh_info: int
    sh_entsize: int
    sh_addralign: int


@dataclass
class DynSymbol:
    name: str
    bind: int
    type: int
    visibility: int
    shndx: int
    value: int
    size: int


@dataclass
class PosixNmRecord:
    name: str
    type_code: str
    value: str
    size: str


@dataclass
class ElfRecord:
    path: str
    size: int
    soname: str | None = None
    needed: list[str] = field(default_factory=list)
    rpath: list[str] = field(default_factory=list)
    runpath: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    section_names: list[str] = field(default_factory=list)
    has_build_id: bool = False
    readelf_returncode: int | None = None
    nm_returncode: int | None = None
    readelf_text: str = ""
    readelf_version_text: str = ""
    nm_text: str = ""
    gnu_versions: list[str] = field(default_factory=list)
    glibc_requirements: list[str] = field(default_factory=list)
    sign_exports: list[dict[str, object]] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    documented_glibc_baseline: str = DOCUMENTED_GLIBC_BASELINE_LABEL


def _u16(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        raise ElfError(f"truncated u16 at {offset}")
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise ElfError(f"truncated u32 at {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    if offset + 8 > len(data):
        raise ElfError(f"truncated u64 at {offset}")
    return struct.unpack_from("<Q", data, offset)[0]


def _i64(data: bytes, offset: int) -> int:
    if offset + 8 > len(data):
        raise ElfError(f"truncated i64 at {offset}")
    return struct.unpack_from("<q", data, offset)[0]


def _checked_range(offset: int, size: int, limit: int, what: str) -> None:
    if offset < 0 or size < 0:
        raise ElfError(f"{what} has a negative file range")
    if offset > limit or size > limit - offset:
        raise ElfError(f"{what} file range exceeds the file")


def _table_end(offset: int, count: int, entsize: int, limit: int, what: str) -> int:
    if count <= 0:
        raise ElfError(f"{what} count is missing")
    if entsize <= 0:
        raise ElfError(f"{what} entry size is invalid")
    if count > limit or entsize > limit:
        raise ElfError(f"{what} count or entry size exceeds the file")
    if count > (limit // entsize):
        raise ElfError(f"{what} count*entsize overflows")
    if offset > limit:
        raise ElfError(f"{what} offset is out of bounds")
    end = offset + count * entsize
    if end > limit:
        raise ElfError(f"{what} table is out of bounds")
    return end


def _cstring(data: bytes, start: int, limit: int) -> str:
    if start < 0 or start >= limit or start >= len(data):
        raise ElfError("string offset is out of bounds")
    end = start
    while end < limit and end < len(data) and data[end] != 0:
        end += 1
    if end >= limit or end >= len(data) or data[end] != 0:
        raise ElfError("unterminated string field")
    return data[start:end].decode("utf-8", errors="strict")


def _vaddr_to_offset(segments: list[LoadSegment], vaddr: int) -> int:
    for seg in segments:
        if seg.vaddr <= vaddr < seg.vaddr + seg.memsz:
            delta = vaddr - seg.vaddr
            if delta >= seg.filesz:
                raise ElfError(f"vaddr {vaddr:#x} is past the PT_LOAD file size")
            return seg.offset + delta
    raise ElfError(f"vaddr {vaddr:#x} is not in a PT_LOAD segment")


def _checked_add(left: int, right: int, what: str) -> int:
    if left < 0 or right < 0:
        raise ElfError(f"{what} offset underflow")
    total = left + right
    if total < left:
        raise ElfError(f"{what} offset overflow")
    return total


def _ranges_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a


def _claim_range(occupied: list[tuple[int, int]], start: int, size: int, what: str) -> None:
    end = _checked_add(start, size, what)
    for other_start, other_end in occupied:
        if _ranges_overlap(start, end, other_start, other_end):
            raise ElfError(f"{what} overlaps another Verneed/Vernaux entry")
    occupied.append((start, end))


def _section_in_compatible_load(section: Section, segments: list[LoadSegment]) -> bool:
    if section.sh_size == 0:
        return True
    end_addr = _checked_add(section.sh_addr, section.sh_size, f"section {section.name} vaddr")
    end_off = None
    if section.sh_type != SHT_NOBITS:
        end_off = _checked_add(section.sh_offset, section.sh_size, f"section {section.name} file")
    for seg in segments:
        virt_end = _checked_add(seg.vaddr, seg.memsz, "PT_LOAD memsz")
        if section.sh_addr < seg.vaddr or end_addr > virt_end:
            continue
        if section.sh_type != SHT_NOBITS:
            file_end = _checked_add(seg.offset, seg.filesz, "PT_LOAD filesz")
            if section.sh_offset < seg.offset or end_off > file_end:
                continue
        return True
    return False


def _named_sections(sections: list[Section], name: str) -> list[Section]:
    return [item for item in sections if item.name == name]


def _typed_sections(sections: list[Section], sh_type: int) -> list[Section]:
    return [item for item in sections if item.sh_type == sh_type]


def _require_unique_named_type(
    sections: list[Section],
    name: str,
    sh_type: int,
    *,
    unique_type: bool = True,
) -> Section:
    named = _named_sections(sections, name)
    if len(named) != 1:
        raise ElfError(f"exactly one {name} section is required")
    section = named[0]
    if section.sh_type != sh_type:
        raise ElfError(f"{name} type/name mismatch")
    if unique_type:
        typed = _typed_sections(sections, sh_type)
        if len(typed) != 1 or typed[0].index != section.index:
            raise ElfError(f"exactly one {name} typed section is required")
    return section


def _validate_section_program_links(
    sections: list[Section],
    segments: list[LoadSegment],
    dynamic_off: int,
    dynamic_size: int,
    e_shnum: int,
) -> None:
    if not sections or sections[0].index != 0:
        raise ElfError("section 0 is missing")
    dynamic = _require_unique_named_type(sections, ".dynamic", SHT_DYNAMIC)
    if dynamic.sh_entsize != ELF64_DYN_SIZE:
        raise ElfError(".dynamic sh_entsize is not Elf64_Dyn")
    if dynamic.sh_size != dynamic_size or dynamic.sh_offset != dynamic_off:
        raise ElfError("SHT_DYNAMIC does not correspond to the single PT_DYNAMIC")
    if dynamic.sh_link == 0 or dynamic.sh_link >= e_shnum:
        raise ElfError(".dynamic sh_link is out of range")
    dynstr = _require_unique_named_type(sections, ".dynstr", SHT_STRTAB, unique_type=False)
    if dynamic.sh_link != dynstr.index:
        raise ElfError(".dynamic sh_link does not point at .dynstr")

    dynsym = _require_unique_named_type(sections, ".dynsym", SHT_DYNSYM)
    if dynsym.sh_entsize != ELF64_SYM_SIZE:
        raise ElfError(".dynsym sh_entsize is not Elf64_Sym")
    if dynsym.sh_link != dynstr.index:
        raise ElfError(".dynsym sh_link does not point at .dynstr")

    versyms = _named_sections(sections, ".gnu.version") + _typed_sections(sections, SHT_GNU_VERSYM)
    if versyms:
        versym = _require_unique_named_type(sections, ".gnu.version", SHT_GNU_VERSYM)
        if versym.sh_entsize != 2:
            raise ElfError(".gnu.version sh_entsize is not Elf64_Half")
        if versym.sh_link != dynsym.index:
            raise ElfError(".gnu.version sh_link does not point at .dynsym")
        expected = (dynsym.sh_size // ELF64_SYM_SIZE) * 2
        if versym.sh_size != expected:
            raise ElfError(".gnu.version size does not match .dynsym count")

    verneeds = _named_sections(sections, ".gnu.version_r") + _typed_sections(
        sections, SHT_GNU_VERNEED
    )
    if verneeds:
        verneed = _require_unique_named_type(sections, ".gnu.version_r", SHT_GNU_VERNEED)
        if verneed.sh_link != dynstr.index:
            raise ElfError(".gnu.version_r sh_link does not point at .dynstr")

    verdefs = _named_sections(sections, ".gnu.version_d") + _typed_sections(
        sections, SHT_GNU_VERDEF
    )
    if verdefs:
        verdef = _require_unique_named_type(sections, ".gnu.version_d", SHT_GNU_VERDEF)
        if verdef.sh_link != dynstr.index:
            raise ElfError(".gnu.version_d sh_link does not point at .dynstr")

    for section in sections[1:]:
        if section.sh_flags & SHF_ALLOC and not _section_in_compatible_load(section, segments):
            raise ElfError(f"SHF_ALLOC section {section.name} is not contained in a PT_LOAD")


def parse_glibc_version(name: str) -> tuple[int, int, int] | None:
    if not isinstance(name, str):
        return None
    match = GLIBC_NAME_RE.fullmatch(name)
    if match is None:
        return None
    major, minor, patch = match.group(1), match.group(2), match.group(3) or "0"
    return int(major), int(minor), int(patch)


def require_parsed_glibc(name: str) -> tuple[int, int, int]:
    if name == "GLIBC_PRIVATE":
        raise ElfError("GLIBC_PRIVATE is not an allowed version requirement")
    parsed = parse_glibc_version(name)
    if parsed is None:
        raise ElfError(f"unparseable GLIBC version label {name!r}")
    return parsed


def format_glibc_version(version: tuple[int, int, int]) -> str:
    major, minor, patch = version
    if patch:
        return f"{major}.{minor}.{patch}"
    return f"{major}.{minor}"


def parse_ldd_glibc_version(text: str) -> tuple[int, int, int] | None:
    match = LDD_GLIBC_RE.search(text)
    if match is None:
        return None
    patch = match.group(3) or "0"
    return int(match.group(1)), int(match.group(2)), int(patch)


def glibc_requirement_allowed(
    name: str,
    *,
    baseline: tuple[int, int, int] = DOCUMENTED_GLIBC_BASELINE,
) -> bool:
    try:
        parsed = require_parsed_glibc(name)
    except ElfError:
        return False
    return parsed <= baseline


def _matches_allowed_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def is_allowed_remap_prefix(path: str) -> bool:
    return any(_matches_allowed_prefix(path, prefix) for prefix in ALLOWED_REMAP_PREFIXES)


def is_allowed_absolute_path(path: str) -> bool:
    return any(_matches_allowed_prefix(path, prefix) for prefix in ALLOWED_ABSOLUTE_PREFIXES)


def is_absolute_path_like(text: str) -> bool:
    """True for an absolute filesystem-like path, not a slash fragment.

    The first component must start with an ASCII letter, underscore, or
    dot. A one-character component is path-like only when a later ``/``
    follows (``/n/foo``), so ``/0`` and ``/N`` are not treated as paths.
    """
    if len(text) < 2 or not text.startswith("/"):
        return False
    first, sep, _remainder = text[1:].partition("/")
    if not first:
        return False
    head = first[0]
    if not head.isascii() or not (head.isalpha() or head in "._"):
        return False
    return len(first) >= 2 or bool(sep)


def extract_nul_terminated_strings(data: bytes) -> list[str]:
    strings: list[str] = []
    index = 0
    length = len(data)
    while index < length:
        if 32 <= data[index] < 127:
            end = index
            while end < length and 32 <= data[end] < 127:
                end += 1
            if end < length and data[end] == 0 and end > index:
                strings.append(data[index:end].decode("ascii"))
            index = end + 1 if end < length and data[end] == 0 else end
        else:
            index += 1
    return strings


def scan_linux_forbidden_paths(
    data: bytes,
    extra_roots: tuple[bytes, ...] = (),
) -> list[str]:
    hits: list[str] = []
    extra = tuple(root.decode("ascii", errors="ignore") for root in extra_roots if root)
    for text in extract_nul_terminated_strings(data):
        if not is_absolute_path_like(text):
            continue
        allowed = is_allowed_absolute_path(text)
        extra_hit = any(_matches_allowed_prefix(text, root) for root in extra if root)
        if extra_hit or not allowed:
            if text not in hits:
                hits.append(text)
    return hits


def build_forbidden_roots(*paths: Path) -> tuple[bytes, ...]:
    encoded: list[bytes] = []
    seen: set[bytes] = set()
    for path in paths:
        text = str(path)
        if not text.startswith("/") or is_allowed_absolute_path(text):
            continue
        raw = text.encode("utf-8")
        if raw not in seen:
            seen.add(raw)
            encoded.append(raw)
    return tuple(encoded)


def parse_posix_nm_defined(text: str) -> list[PosixNmRecord]:
    records: list[PosixNmRecord] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            raise ElfError(f"nm posix record {line_no} is malformed")
        records.append(
            PosixNmRecord(
                name=parts[0],
                type_code=parts[1],
                value=parts[2] if len(parts) > 2 else "",
                size=parts[3] if len(parts) > 3 else "",
            )
        )
    return records


def require_exact_sign_nm(records: list[PosixNmRecord]) -> PosixNmRecord:
    matches = [item for item in records if item.name == SIGN_SYMBOL]
    if not matches:
        raise ElfError(f"{SIGN_SYMBOL} missing from nm --defined-only posix records")
    if len(matches) > 1:
        raise ElfError(f"{SIGN_SYMBOL} is ambiguous in nm posix records")
    record = matches[0]
    if record.type_code not in NM_DEFINED_FUNC_TYPES:
        raise ElfError(f"{SIGN_SYMBOL} nm type {record.type_code!r} is not T or W")
    return record


def parse_readelf_version_names(text: str) -> list[str]:
    return [match.group(1) for match in READELF_VER_NAME_RE.finditer(text)]


def parse_elf64_le_x86_64_dso(
    data: bytes,
    *,
    extra_forbidden_roots: tuple[bytes, ...] = (),
) -> ElfRecord:
    if len(data) > MAX_INPUT_BYTES:
        raise ElfError(f"input exceeds MAX_INPUT_BYTES ({MAX_INPUT_BYTES})")
    if len(data) < ELF64_EHDR_SIZE:
        raise ElfError("truncated ELF header")
    if data[:4] != ELFMAG:
        raise ElfError("missing ELF magic")
    if data[EI_CLASS] != ELFCLASS64:
        raise ElfError(f"EI_CLASS {data[EI_CLASS]} is not ELFCLASS64")
    if data[EI_DATA] != ELFDATA2LSB:
        raise ElfError(f"EI_DATA {data[EI_DATA]} is not ELFDATA2LSB")
    if data[EI_VERSION] != EV_CURRENT:
        raise ElfError(f"EI_VERSION {data[EI_VERSION]} is not EV_CURRENT")
    e_type = _u16(data, 16)
    e_machine = _u16(data, 18)
    e_version = _u32(data, 20)
    if e_version != EV_CURRENT:
        raise ElfError(f"e_version {e_version} is not EV_CURRENT")
    if e_type != ET_DYN:
        raise ElfError(f"e_type {e_type} is not ET_DYN")
    if e_machine == EM_AARCH64:
        raise ElfError("EM_AARCH64 is out of scope (Linux x86-64 only)")
    if e_machine != EM_X86_64:
        raise ElfError(f"e_machine {e_machine} is not EM_X86_64")
    e_phoff = _u64(data, 32)
    e_shoff = _u64(data, 40)
    e_ehsize = _u16(data, 52)
    e_phentsize = _u16(data, 54)
    e_phnum = _u16(data, 56)
    e_shentsize = _u16(data, 58)
    e_shnum = _u16(data, 60)
    e_shstrndx = _u16(data, 62)
    if e_ehsize != ELF64_EHDR_SIZE:
        raise ElfError(f"e_ehsize {e_ehsize} != {ELF64_EHDR_SIZE}")
    if e_phentsize != ELF64_PHDR_SIZE:
        raise ElfError(f"e_phentsize {e_phentsize} != {ELF64_PHDR_SIZE}")
    if e_phnum == PN_XNUM:
        raise ElfError("PN_XNUM program header count is unsupported")
    if e_phnum == 0 or e_phnum > MAX_PHNUM:
        raise ElfError(f"e_phnum {e_phnum} is missing or exceeds MAX_PHNUM")
    _table_end(e_phoff, e_phnum, e_phentsize, len(data), "program header")
    if e_phoff < ELF64_EHDR_SIZE:
        raise ElfError("program header table overlaps the ELF header")

    segments: list[LoadSegment] = []
    dynamic_off: int | None = None
    dynamic_size = 0
    notes: list[tuple[int, int]] = []
    for index in range(e_phnum):
        off = e_phoff + index * e_phentsize
        p_type = _u32(data, off)
        p_offset = _u64(data, off + 8)
        p_vaddr = _u64(data, off + 16)
        p_filesz = _u64(data, off + 32)
        p_memsz = _u64(data, off + 40)
        p_align = _u64(data, off + 48)
        _checked_range(p_offset, p_filesz, len(data), f"program header {index}")
        if p_type == PT_LOAD:
            if p_filesz > p_memsz:
                raise ElfError(f"PT_LOAD {index} p_filesz exceeds p_memsz")
            if p_align == 0:
                raise ElfError(f"PT_LOAD {index} p_align is zero")
            if p_align > 1:
                if p_align & (p_align - 1):
                    raise ElfError(f"PT_LOAD {index} p_align is not a power of two")
                if (p_vaddr % p_align) != (p_offset % p_align):
                    raise ElfError(f"PT_LOAD {index} p_vaddr/p_offset alignment mismatch")
            segments.append(
                LoadSegment(offset=p_offset, filesz=p_filesz, vaddr=p_vaddr, memsz=p_memsz)
            )
        elif p_type == PT_DYNAMIC:
            if dynamic_off is not None:
                raise ElfError("multiple PT_DYNAMIC headers")
            dynamic_off = p_offset
            dynamic_size = p_filesz
        elif p_type == PT_NOTE:
            notes.append((p_offset, p_filesz))

    if dynamic_off is None:
        raise ElfError("PT_DYNAMIC is missing")
    if dynamic_size < ELF64_DYN_SIZE or dynamic_size % ELF64_DYN_SIZE != 0:
        raise ElfError("PT_DYNAMIC size is not a multiple of 16")
    tag_count = dynamic_size // ELF64_DYN_SIZE
    if tag_count > MAX_DYNAMIC_TAGS:
        raise ElfError("PT_DYNAMIC exceeds MAX_DYNAMIC_TAGS")

    tags: list[tuple[int, int]] = []
    seen_singletons: set[int] = set()
    saw_null = False
    for index in range(tag_count):
        tag = _i64(data, dynamic_off + index * ELF64_DYN_SIZE)
        value = _u64(data, dynamic_off + index * ELF64_DYN_SIZE + 8)
        if tag == DT_NULL:
            saw_null = True
            break
        if tag in SINGLETON_DYNAMIC_TAGS:
            if tag in seen_singletons:
                raise ElfError(f"duplicate dynamic tag {tag:#x}")
            seen_singletons.add(tag)
        tags.append((tag, value))
    if not saw_null:
        raise ElfError("PT_DYNAMIC is missing DT_NULL")

    values = {tag: value for tag, value in tags}
    strtab_vaddr = values.get(DT_STRTAB)
    strsz = values.get(DT_STRSZ)
    soname_off = values.get(DT_SONAME)
    needed_offs = [value for tag, value in tags if tag == DT_NEEDED]
    rpath_offs = [value for tag, value in tags if tag == DT_RPATH]
    runpath_offs = [value for tag, value in tags if tag == DT_RUNPATH]
    symtab_vaddr = values.get(DT_SYMTAB)
    syment = values.get(DT_SYMENT)
    verneed_vaddr = values.get(DT_VERNEED)
    verneed_num = values.get(DT_VERNEEDNUM)

    if strtab_vaddr is None or strsz is None:
        raise ElfError("DT_STRTAB/DT_STRSZ is missing")
    if strsz > MAX_INPUT_BYTES:
        raise ElfError("DT_STRSZ exceeds MAX_INPUT_BYTES")
    strtab_off = _vaddr_to_offset(segments, strtab_vaddr)
    _checked_range(strtab_off, strsz, len(data), "DT_STRTAB")
    strtab_end = strtab_off + strsz

    def dynstr(offset: int) -> str:
        if offset < 0 or offset >= strsz:
            raise ElfError("dynamic string offset is out of bounds")
        return _cstring(data, strtab_off + offset, strtab_end)

    record = ElfRecord(path="", size=len(data))
    if soname_off is None:
        raise ElfError("DT_SONAME is missing")
    record.soname = dynstr(soname_off)
    if record.soname != STABLE_SONAME:
        raise ElfError(f"DT_SONAME {record.soname!r} != {STABLE_SONAME!r}")
    if len(needed_offs) > MAX_NEEDED:
        raise ElfError("DT_NEEDED count exceeds MAX_NEEDED")
    record.needed = [dynstr(off) for off in needed_offs]
    if not record.needed:
        raise ElfError("DT_NEEDED is empty")
    unexpected = [name for name in record.needed if name not in ALLOWED_NEEDED]
    if unexpected:
        raise ElfError(f"unexpected DT_NEEDED: {unexpected}")
    missing = sorted(REQUIRED_NEEDED - set(record.needed))
    if missing:
        raise ElfError(f"missing required DT_NEEDED: {missing}")
    record.rpath = [dynstr(off) for off in rpath_offs]
    record.runpath = [dynstr(off) for off in runpath_offs]
    if record.rpath:
        raise ElfError(f"DT_RPATH is present: {record.rpath}")
    if record.runpath:
        raise ElfError(f"DT_RUNPATH is present: {record.runpath}")

    if e_shnum == 0 or e_shnum > MAX_SHNUM:
        raise ElfError(f"e_shnum {e_shnum} is missing or exceeds MAX_SHNUM")
    if e_shentsize != ELF64_SHDR_SIZE:
        raise ElfError(f"e_shentsize {e_shentsize} != {ELF64_SHDR_SIZE}")
    if e_shstrndx == SHN_XINDEX:
        raise ElfError("SHN_XINDEX section name index is unsupported")
    _table_end(e_shoff, e_shnum, e_shentsize, len(data), "section header")
    if e_shoff < ELF64_EHDR_SIZE:
        raise ElfError("section header table overlaps the ELF header")
    if e_shstrndx == 0 or e_shstrndx >= e_shnum:
        raise ElfError("e_shstrndx is out of range")
    shstr = e_shoff + e_shstrndx * e_shentsize
    shstr_off = _u64(data, shstr + 24)
    shstr_size = _u64(data, shstr + 32)
    _checked_range(shstr_off, shstr_size, len(data), ".shstrtab")

    sections: list[Section] = []
    for index in range(e_shnum):
        sh = e_shoff + index * e_shentsize
        name_off = _u32(data, sh)
        sh_type = _u32(data, sh + 4)
        sh_flags = _u64(data, sh + 8)
        sh_addr = _u64(data, sh + 16)
        sh_offset = _u64(data, sh + 24)
        sh_size = _u64(data, sh + 32)
        sh_link = _u32(data, sh + 40)
        sh_info = _u32(data, sh + 44)
        sh_addralign = _u64(data, sh + 48)
        sh_entsize = _u64(data, sh + 56)
        name = _cstring(data, shstr_off + name_off, shstr_off + shstr_size)
        record.section_names.append(name)
        if index == 0:
            if any(
                (
                    name,
                    sh_type,
                    sh_flags,
                    sh_addr,
                    sh_offset,
                    sh_size,
                    sh_link,
                    sh_info,
                    sh_addralign,
                    sh_entsize,
                )
            ):
                raise ElfError("section 0 is not the canonical SHT_NULL entry")
        else:
            if sh_addralign == 0:
                raise ElfError(f"section {name or index} sh_addralign is zero")
            if sh_addralign > 1 and sh_addralign & (sh_addralign - 1):
                raise ElfError(f"section {name or index} sh_addralign is not a power of two")
            if sh_addralign > 1 and sh_addr % sh_addralign != 0:
                raise ElfError(f"section {name or index} sh_addr is misaligned")
        if any(name.startswith(prefix) for prefix in DEBUG_SECTION_PREFIXES):
            raise ElfError(f"debug section {name} is present")
        if name in FORBIDDEN_DEBUG_SECTIONS:
            raise ElfError(f"debug-link section {name} is present")
        if sh_type not in {SHT_NULL, SHT_NOBITS} and sh_size:
            _checked_range(sh_offset, sh_size, len(data), f"section {name or index}")
        if sh_type == SHT_NOTE:
            notes.append((sh_offset, sh_size))
        sections.append(
            Section(
                index=index,
                name=name,
                sh_type=sh_type,
                sh_flags=sh_flags,
                sh_addr=sh_addr,
                sh_offset=sh_offset,
                sh_size=sh_size,
                sh_link=sh_link,
                sh_info=sh_info,
                sh_entsize=sh_entsize,
                sh_addralign=sh_addralign,
            )
        )
    _validate_section_program_links(sections, segments, dynamic_off, dynamic_size, e_shnum)

    for off, size in notes:
        if size > MAX_NOTE_BYTES:
            raise ElfError("note payload exceeds MAX_NOTE_BYTES")
        _checked_range(off, size, len(data), "note")
        if _note_has_build_id(data[off : off + size]):
            record.has_build_id = True
            raise ElfError("NT_GNU_BUILD_ID is present; policy is --build-id=none")

    if symtab_vaddr is None or syment is None:
        raise ElfError("DT_SYMTAB/DT_SYMENT is missing")
    if syment != ELF64_SYM_SIZE:
        raise ElfError(f"DT_SYMENT {syment} != {ELF64_SYM_SIZE}")
    dynsym_sections = [item for item in sections if item.sh_type == SHT_DYNSYM]
    if len(dynsym_sections) != 1:
        raise ElfError("exactly one SHT_DYNSYM section is required")
    dynsym = dynsym_sections[0]
    if dynsym.sh_entsize != ELF64_SYM_SIZE:
        raise ElfError("SHT_DYNSYM entsize is not ELF64_SYM")
    if dynsym.sh_size % ELF64_SYM_SIZE != 0:
        raise ElfError("SHT_DYNSYM size is not a multiple of ELF64_SYM")
    mapped_sym = _vaddr_to_offset(segments, symtab_vaddr)
    if mapped_sym != dynsym.sh_offset:
        raise ElfError("DT_SYMTAB does not match the SHT_DYNSYM file offset")
    if dynsym.sh_link == 0 or dynsym.sh_link >= e_shnum:
        raise ElfError("SHT_DYNSYM sh_link is out of range")
    linked_str = sections[dynsym.sh_link]
    if linked_str.sh_type != SHT_STRTAB:
        raise ElfError("SHT_DYNSYM is not linked to SHT_STRTAB")
    linked_str_off = _vaddr_to_offset(segments, linked_str.sh_addr) if linked_str.sh_addr else linked_str.sh_offset
    if linked_str_off != strtab_off:
        raise ElfError("DT_STRTAB does not match the linked .dynstr")
    count = dynsym.sh_size // ELF64_SYM_SIZE
    if count == 0 or count > MAX_DYNSYM:
        raise ElfError("SHT_DYNSYM count is missing or exceeds MAX_DYNSYM")
    _checked_range(dynsym.sh_offset, dynsym.sh_size, len(data), ".dynsym")

    parsed_symbols: list[DynSymbol] = []
    for index in range(count):
        entry = dynsym.sh_offset + index * ELF64_SYM_SIZE
        st_name = _u32(data, entry)
        st_info = data[entry + 4]
        st_other = data[entry + 5]
        st_shndx = _u16(data, entry + 6)
        st_value = _u64(data, entry + 8)
        st_size = _u64(data, entry + 16)
        bind = st_info >> 4
        typ = st_info & 0xF
        visibility = st_other & 0x3
        name = dynstr(st_name) if st_name else ""
        parsed_symbols.append(
            DynSymbol(
                name=name,
                bind=bind,
                type=typ,
                visibility=visibility,
                shndx=st_shndx,
                value=st_value,
                size=st_size,
            )
        )
        if name:
            record.symbols.append(name)

    _require_sign_export(parsed_symbols, e_shnum, record)

    if "libc.so.6" in record.needed:
        if verneed_vaddr is None or verneed_num is None:
            raise ElfError("DT_VERNEED/DT_VERNEEDNUM is required when libc.so.6 is needed")
        record.gnu_versions = _parse_verneed(
            data,
            segments,
            sections,
            e_shnum,
            verneed_vaddr=verneed_vaddr,
            verneed_num=verneed_num,
            dynstr=dynstr,
        )
        # The same GLIBC_* label may appear on libc.so.6 and ld-linux-*.
        # Duplicate policy is (file, name) in the Verneed walk, not the
        # flattened name list used for the baseline cap.
        record.glibc_requirements = sorted(
            {name for name in record.gnu_versions if name.startswith("GLIBC_")}
        )
        if not record.glibc_requirements:
            raise ElfError("no GLIBC_* version requirement was found")
        too_new: list[str] = []
        for name in record.glibc_requirements:
            parsed = require_parsed_glibc(name)
            if parsed > DOCUMENTED_GLIBC_BASELINE:
                too_new.append(name)
        if too_new:
            raise ElfError(
                f"GLIBC requirement {too_new} exceeds documented baseline "
                f"{DOCUMENTED_GLIBC_BASELINE_LABEL}"
            )

    record.forbidden_paths = scan_linux_forbidden_paths(data, extra_forbidden_roots)
    if record.forbidden_paths:
        raise ElfError(
            "embedded host-absolute paths: " + "; ".join(record.forbidden_paths[:8])
        )
    return record


def _require_sign_export(symbols: list[DynSymbol], e_shnum: int, record: ElfRecord) -> None:
    matches = [item for item in symbols if item.name == SIGN_SYMBOL]
    if not matches:
        raise ElfError(f"{SIGN_SYMBOL} is not exported")
    if len(matches) > 1:
        raise ElfError(f"{SIGN_SYMBOL} is duplicate or ambiguous in .dynsym")
    symbol = matches[0]
    if symbol.shndx == SHN_UNDEF:
        raise ElfError(f"{SIGN_SYMBOL} is undefined (SHN_UNDEF)")
    if symbol.shndx == 0 or symbol.shndx >= e_shnum or symbol.shndx >= SHN_LORESERVE:
        raise ElfError(f"{SIGN_SYMBOL} section index {symbol.shndx} is invalid")
    if symbol.type != STT_FUNC:
        raise ElfError(f"{SIGN_SYMBOL} type {symbol.type} is not STT_FUNC")
    if symbol.bind not in {STB_GLOBAL, STB_WEAK}:
        raise ElfError(f"{SIGN_SYMBOL} binding {symbol.bind} is not STB_GLOBAL/STB_WEAK")
    if symbol.visibility not in {STV_DEFAULT, STV_PROTECTED}:
        raise ElfError(
            f"{SIGN_SYMBOL} visibility {symbol.visibility} is not STV_DEFAULT/STV_PROTECTED"
        )
    if symbol.value == 0:
        raise ElfError(f"{SIGN_SYMBOL} value is zero")
    record.sign_exports = [
        {
            "name": symbol.name,
            "bind": symbol.bind,
            "type": symbol.type,
            "visibility": symbol.visibility,
            "shndx": symbol.shndx,
            "value": symbol.value,
        }
    ]


def _parse_verneed(
    data: bytes,
    segments: list[LoadSegment],
    sections: list[Section],
    e_shnum: int,
    *,
    verneed_vaddr: int,
    verneed_num: int,
    dynstr,
) -> list[str]:
    if verneed_num <= 0 or verneed_num > MAX_VERNEED:
        raise ElfError(f"DT_VERNEEDNUM {verneed_num} is missing or exceeds MAX_VERNEED")
    section = _require_unique_named_type(sections, ".gnu.version_r", SHT_GNU_VERNEED)
    if section.sh_link == 0 or section.sh_link >= e_shnum:
        raise ElfError(".gnu.version_r sh_link is out of range")
    if sections[section.sh_link].name != ".dynstr":
        raise ElfError(".gnu.version_r sh_link does not point at .dynstr")
    if section.sh_size < ELF64_VERNEED_SIZE:
        raise ElfError(".gnu.version_r is smaller than one Elf64_Verneed")
    section_start = section.sh_offset
    section_end = _checked_add(section.sh_offset, section.sh_size, ".gnu.version_r")
    mapped = _vaddr_to_offset(segments, verneed_vaddr)
    if mapped < section_start or mapped + ELF64_VERNEED_SIZE > section_end:
        raise ElfError("DT_VERNEED is outside the SHT_GNU_verneed section")
    if mapped != section_start:
        raise ElfError("DT_VERNEED does not start at the SHT_GNU_verneed section")

    def _in_section(offset: int, size: int, what: str) -> None:
        end = _checked_add(offset, size, what)
        if offset < section_start or end > section_end:
            raise ElfError(f"{what} is outside the SHT_GNU_verneed section")
        if offset % 4 != 0:
            raise ElfError(f"{what} is not 4-byte aligned")

    names: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()
    visited_vn: set[int] = set()
    visited_vna: set[int] = set()
    occupied: list[tuple[int, int]] = []
    cursor = mapped
    walked = 0
    for index in range(verneed_num):
        if cursor in visited_vn:
            raise ElfError("Elf64_Verneed entry was revisited")
        _in_section(cursor, ELF64_VERNEED_SIZE, "Elf64_Verneed")
        _claim_range(occupied, cursor, ELF64_VERNEED_SIZE, "Elf64_Verneed")
        visited_vn.add(cursor)
        vn_version = _u16(data, cursor)
        vn_cnt = _u16(data, cursor + 2)
        vn_file = _u32(data, cursor + 4)
        vn_aux = _u32(data, cursor + 8)
        vn_next = _u32(data, cursor + 12)
        if vn_version != VER_NEED_CURRENT:
            raise ElfError(f"vn_version {vn_version} is not VER_NEED_CURRENT")
        if vn_cnt == 0 or vn_cnt > MAX_VERNAUX:
            raise ElfError("vn_cnt is missing or exceeds MAX_VERNAUX")
        if vn_aux == 0:
            raise ElfError("vn_aux is missing")
        file_name = dynstr(vn_file)
        aux = _checked_add(cursor, vn_aux, "vn_aux")
        if aux <= cursor:
            raise ElfError("vn_aux is not a positive forward offset")
        walked_aux = 0
        for aux_index in range(vn_cnt):
            if aux in visited_vna:
                raise ElfError("Elf64_Vernaux entry was revisited")
            _in_section(aux, ELF64_VERNAUX_SIZE, "Elf64_Vernaux")
            _claim_range(occupied, aux, ELF64_VERNAUX_SIZE, "Elf64_Vernaux")
            visited_vna.add(aux)
            vna_name = _u32(data, aux + 8)
            vna_next = _u32(data, aux + 12)
            name = dynstr(vna_name)
            if not name:
                raise ElfError("empty GNU version name")
            pair = (file_name, name)
            if pair in seen_pairs:
                raise ElfError(f"duplicate GNU version requirement {file_name}:{name}")
            seen_pairs.add(pair)
            names.append(name)
            walked_aux += 1
            last_aux = aux_index + 1 == vn_cnt
            if last_aux:
                if vna_next != 0:
                    raise ElfError("final vna_next is not zero")
            else:
                if vna_next == 0:
                    raise ElfError("Elf64_Vernaux chain is truncated")
                if vna_next % 4 != 0:
                    raise ElfError("vna_next is not 4-byte aligned")
                nxt = _checked_add(aux, vna_next, "vna_next")
                if nxt <= aux:
                    raise ElfError("vna_next is not a positive forward offset")
                aux = nxt
        if walked_aux != vn_cnt:
            raise ElfError("Elf64_Vernaux count does not match vn_cnt")
        walked += 1
        last_vn = index + 1 == verneed_num
        if last_vn:
            if vn_next != 0:
                raise ElfError("final vn_next is not zero")
        else:
            if vn_next == 0:
                raise ElfError("Elf64_Verneed chain is truncated")
            if vn_next % 4 != 0:
                raise ElfError("vn_next is not 4-byte aligned")
            nxt = _checked_add(cursor, vn_next, "vn_next")
            if nxt <= cursor:
                raise ElfError("vn_next is not a positive forward offset")
            cursor = nxt
    if walked != verneed_num:
        raise ElfError("DT_VERNEEDNUM does not match the walked Verneed count")
    return names


def _note_has_build_id(blob: bytes) -> bool:
    cursor = 0
    while cursor + 12 <= len(blob):
        namesz = _u32(blob, cursor)
        descsz = _u32(blob, cursor + 4)
        ntype = _u32(blob, cursor + 8)
        cursor += 12
        name_end = cursor + namesz
        name_pad = (4 - (namesz % 4)) % 4
        desc_start = name_end + name_pad
        desc_end = desc_start + descsz
        desc_pad = (4 - (descsz % 4)) % 4
        if desc_end > len(blob):
            raise ElfError("truncated ELF note")
        name = blob[cursor:name_end]
        if ntype == NT_GNU_BUILD_ID and name.startswith(b"GNU"):
            return True
        cursor = desc_end + desc_pad
    return False


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def verify_linux_x86_64_cdylib(
    path: Path,
    *,
    require_tools: bool = False,
    readelf: str | None = None,
    nm: str | None = None,
    extra_forbidden_roots: tuple[bytes, ...] = (),
) -> ElfRecord:
    data = path.read_bytes()
    record = parse_elf64_le_x86_64_dso(data, extra_forbidden_roots=extra_forbidden_roots)
    record.path = str(path)
    readelf_bin = readelf
    nm_bin = nm
    if require_tools:
        readelf_bin = readelf_bin or shutil.which("readelf")
        nm_bin = nm_bin or shutil.which("nm")
        if not readelf_bin:
            raise ElfError("readelf is required")
        if not nm_bin:
            raise ElfError("nm is required")
    if readelf_bin:
        dynamic = _run([readelf_bin, "-d", str(path)])
        record.readelf_returncode = dynamic.returncode
        record.readelf_text = ((dynamic.stdout or "") + (dynamic.stderr or "")).strip()
        if dynamic.returncode != 0:
            raise ElfError(f"readelf -d exited {dynamic.returncode}")
        versions = _run([readelf_bin, "--version-info", str(path)])
        record.readelf_version_text = ((versions.stdout or "") + (versions.stderr or "")).strip()
        if versions.returncode != 0:
            raise ElfError(f"readelf --version-info exited {versions.returncode}")
        tool_names = parse_readelf_version_names(record.readelf_version_text)
        tool_glibc = [name for name in tool_names if name.startswith("GLIBC_")]
        for name in tool_glibc:
            require_parsed_glibc(name)
        if set(tool_glibc) != set(record.glibc_requirements):
            raise ElfError(
                "readelf --version-info GLIBC set does not match the parser: "
                f"{sorted(tool_glibc)} vs {sorted(record.glibc_requirements)}"
            )
        too_new = [
            name
            for name in tool_glibc
            if require_parsed_glibc(name) > DOCUMENTED_GLIBC_BASELINE
        ]
        if too_new:
            raise ElfError(
                f"readelf GLIBC requirement {too_new} exceeds documented baseline "
                f"{DOCUMENTED_GLIBC_BASELINE_LABEL}"
            )
    if nm_bin:
        completed = _run(
            [nm_bin, "-D", "--defined-only", "--format=posix", str(path)]
        )
        record.nm_returncode = completed.returncode
        record.nm_text = ((completed.stdout or "") + (completed.stderr or "")).strip()
        if completed.returncode != 0:
            raise ElfError(f"nm -D --defined-only --format=posix exited {completed.returncode}")
        require_exact_sign_nm(parse_posix_nm_defined(record.nm_text))
    return record
