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
- ``.dynstr.sh_size == DT_STRSZ`` and ``DT_STRTAB`` equals
  ``.dynstr.sh_addr`` and maps to its file range
- ``.gnu.version_r`` is ``SHF_ALLOC``, ``sh_info == DT_VERNEEDNUM``,
  and ``DT_VERNEED`` equals its ``sh_addr`` / file range
- ``.dynamic`` is ``SHF_ALLOC`` and matches the single ``PT_DYNAMIC``
  on offset, vaddr, filesz, memsz, and alignment
- ``DT_VERSYM`` binds to exactly one allocated ``.gnu.version``;
  ``DT_VERDEF``/``DT_VERDEFNUM`` and ``.gnu.version_d`` are all-or-nothing
- every ``.gnu.version`` entry is parsed; count equals dynsym count.
  Hidden bit ``0x8000`` is separated from the base index. Index 0 is
  only for dynsym entry 0, ``STB_LOCAL``, or the toolchain's undefined
  ``STB_WEAK`` unversioned import. Undefined ``STB_GLOBAL`` imports
  must not use 0. Base indices greater than 1 resolve uniquely to one
  ``vna_other`` or one ``vd_ndx``. Every ``vna_other`` is globally
  unique across files. Dynsym entry 0 is the canonical null symbol.
  ``readelf --version-info`` index maps and ``readelf --dyn-syms --wide``
  sign records must match exactly (``--wide`` avoids 80-column wraps).
  The required sign export is
  unhidden and uses global/unversioned or a matching Verdef
- ELF64 arithmetic uses ``UINT64_MAX``; ``_checked_add`` / ``_checked_mul``
  reject negatives and sums that exceed ``UINT64_MAX``
- raw-byte searches catch every documented forbidden build root at any
  offset when the following byte is ``/``, a path stop, or EOF; slash-byte
  scans extract path-like candidates through NUL/control/whitespace/EOF.
  Allowed prefixes use an exact component boundary (``path == prefix``
  or next byte ``/``). Invalid UTF-8 candidates fail when they contain a
  forbidden root or otherwise look like an unapproved absolute path;
  ``/letter`` plus non-ASCII continuation without a later slash is not a
  path. ``/proc`` is a runtime prefix (rustc/libstd ``/proc/self/exe``)
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
ELF64_VERSYM_SIZE = 2
ELF64_VERDEF_SIZE = 20
ELF64_VERDAUX_SIZE = 8
VER_DEF_CURRENT = 1
VER_NDX_LOCAL = 0
VER_NDX_GLOBAL = 1
VERSYM_HIDDEN = 0x8000
VERSYM_NDX_MASK = 0x7FFF
VER_NDX_UNSPECIFIED = 0x7FFF
UINT64_MAX = 0xFFFFFFFFFFFFFFFF

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_PHNUM = 128
MAX_SHNUM = 256
MAX_DYNAMIC_TAGS = 256
MAX_NEEDED = 16
MAX_NOTE_BYTES = 4096
MAX_DYNSYM = 4096
MAX_VERNEED = 16
MAX_VERNAUX = 32
MAX_VERDEF = 16
MAX_VERDAUX = 32
MAX_PATH_CANDIDATE = 4096
MAX_PATH_DISPLAY = 128

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
# Runtime/system prefixes that a glibc x86-64 ET_DYN may embed (PT_INTERP,
# multiarch loader/libgcc realpaths, and rustc/libstd current-exe).
# /usr/local and /tmp are not listed.
ALLOWED_RUNTIME_PREFIXES = (
    "/lib64",
    "/lib",
    "/usr/lib",
    "/usr/lib64",
    "/proc",
)
ALLOWED_ABSOLUTE_PREFIXES = ALLOWED_REMAP_PREFIXES + ALLOWED_RUNTIME_PREFIXES
# Raw-byte host/build roots. Matched at any offset, independent of NUL
# or printable context. /usr/local and /tmp are not runtime prefixes.
FORBIDDEN_BUILD_ROOTS = (
    b"/home/runner",
    b"/Users",
    b"/var/folders",
    b"/private/var/folders",
    b"/opt/homebrew",
    b"/opt/hostedtoolcache",
    b"/Volumes",
    b"/usr/local/private-build",
    b"/tmp/untracked-host",
)
_HOME_PREFIX = b"/home/"
_HOME_REBUILD = b"rebuild"
_PATH_STOP = frozenset(range(0x21)) | {0x20}  # NUL, controls, space

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
# GNU readelf --dyn-syms: Num Value Size Type Bind Vis [[other]] Ndx Name[@VER] [(index)]
READELF_DYNSYM_RE = re.compile(
    r"^\s*(\d+):\s+([0-9A-Fa-f]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)"
    r"(?:\s+\[(?:[^\]]*)\])?"
    r"\s+(\S+)(?:\s+(\S+)(?:\s+\((\d+)\))?)?\s*$"
)


class ElfError(RuntimeError):
    pass


@dataclass
class LoadSegment:
    offset: int
    filesz: int
    vaddr: int
    memsz: int


@dataclass
class DynamicPhdr:
    offset: int
    vaddr: int
    filesz: int
    memsz: int
    align: int


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
class ReadelfDynsymRecord:
    name: str
    type_name: str
    bind: str
    visibility: str
    ndx: str
    version: str | None
    version_index: int | None = None


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
    versym_values: list[int] = field(default_factory=list)
    verneed_indices: dict[int, str] = field(default_factory=dict)
    verdef_indices: dict[int, str] = field(default_factory=dict)


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


def _require_u64(value: int, what: str) -> int:
    if not isinstance(value, int) or value < 0 or value > UINT64_MAX:
        raise ElfError(f"{what} is outside 0..UINT64_MAX")
    return value


def _checked_add(left: int, right: int, what: str) -> int:
    _require_u64(left, what)
    _require_u64(right, what)
    if left > UINT64_MAX - right:
        raise ElfError(f"{what} offset overflow")
    return left + right


def _checked_mul(left: int, right: int, what: str) -> int:
    _require_u64(left, what)
    _require_u64(right, what)
    if right != 0 and left > UINT64_MAX // right:
        raise ElfError(f"{what} overflow")
    return left * right


def _checked_align_up(value: int, align: int, what: str) -> int:
    _require_u64(value, what)
    _require_u64(align, what)
    if align == 0:
        raise ElfError(f"{what} alignment is zero")
    remainder = value % align
    if remainder == 0:
        return value
    return _checked_add(value, align - remainder, what)


def _checked_range(offset: int, size: int, limit: int, what: str) -> None:
    _require_u64(offset, f"{what} offset")
    _require_u64(size, f"{what} size")
    _require_u64(limit, f"{what} limit")
    if offset > limit:
        raise ElfError(f"{what} file range exceeds the file")
    if size > limit - offset:
        raise ElfError(f"{what} file range exceeds the file")


def _table_end(offset: int, count: int, entsize: int, limit: int, what: str) -> int:
    if count <= 0:
        raise ElfError(f"{what} count is missing")
    if entsize <= 0:
        raise ElfError(f"{what} entry size is invalid")
    span = _checked_mul(count, entsize, f"{what} count*entsize")
    end = _checked_add(offset, span, what)
    _require_u64(limit, f"{what} limit")
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
    _require_u64(vaddr, "vaddr")
    for seg in segments:
        virt_end = _checked_add(seg.vaddr, seg.memsz, "PT_LOAD memsz")
        if seg.vaddr <= vaddr < virt_end:
            delta = vaddr - seg.vaddr
            if delta >= seg.filesz:
                raise ElfError(f"vaddr {vaddr:#x} is past the PT_LOAD file size")
            return _checked_add(seg.offset, delta, "vaddr map")
    raise ElfError(f"vaddr {vaddr:#x} is not in a PT_LOAD segment")


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


def _require_alloc(section: Section) -> None:
    if not (section.sh_flags & SHF_ALLOC):
        raise ElfError(f"{section.name} is not SHF_ALLOC")


def _require_vaddr_maps_section(
    segments: list[LoadSegment],
    vaddr: int,
    section: Section,
    tag_name: str,
) -> None:
    if vaddr != section.sh_addr:
        raise ElfError(f"{tag_name} does not equal {section.name} sh_addr")
    mapped = _vaddr_to_offset(segments, vaddr)
    if mapped != section.sh_offset:
        raise ElfError(f"{tag_name} does not map to {section.name} file offset")


def _validate_section_program_links(
    sections: list[Section],
    segments: list[LoadSegment],
    dynamic_phdr: DynamicPhdr,
    values: dict[int, int],
    e_shnum: int,
) -> None:
    if not sections or sections[0].index != 0:
        raise ElfError("section 0 is missing")
    dynamic = _require_unique_named_type(sections, ".dynamic", SHT_DYNAMIC)
    _require_alloc(dynamic)
    if dynamic.sh_entsize != ELF64_DYN_SIZE:
        raise ElfError(".dynamic sh_entsize is not Elf64_Dyn")
    if dynamic.sh_offset != dynamic_phdr.offset:
        raise ElfError("PT_DYNAMIC p_offset does not equal .dynamic sh_offset")
    if dynamic.sh_addr != dynamic_phdr.vaddr:
        raise ElfError("PT_DYNAMIC p_vaddr does not equal .dynamic sh_addr")
    if dynamic.sh_size != dynamic_phdr.filesz:
        raise ElfError("PT_DYNAMIC p_filesz does not equal .dynamic sh_size")
    if dynamic_phdr.memsz != dynamic_phdr.filesz:
        raise ElfError("PT_DYNAMIC p_memsz does not equal p_filesz")
    if dynamic_phdr.align == 0:
        raise ElfError("PT_DYNAMIC p_align is zero")
    if dynamic_phdr.align != dynamic.sh_addralign:
        raise ElfError("PT_DYNAMIC p_align does not equal .dynamic sh_addralign")
    if dynamic.sh_link == 0 or dynamic.sh_link >= e_shnum:
        raise ElfError(".dynamic sh_link is out of range")
    dynstr = _require_unique_named_type(sections, ".dynstr", SHT_STRTAB, unique_type=False)
    _require_alloc(dynstr)
    if dynamic.sh_link != dynstr.index:
        raise ElfError(".dynamic sh_link does not point at .dynstr")
    strtab = values.get(DT_STRTAB)
    strsz = values.get(DT_STRSZ)
    if strtab is None or strsz is None:
        raise ElfError("DT_STRTAB/DT_STRSZ is missing")
    if dynstr.sh_size != strsz:
        raise ElfError(".dynstr sh_size does not equal DT_STRSZ")
    _require_vaddr_maps_section(segments, strtab, dynstr, "DT_STRTAB")

    dynsym = _require_unique_named_type(sections, ".dynsym", SHT_DYNSYM)
    _require_alloc(dynsym)
    if dynsym.sh_entsize != ELF64_SYM_SIZE:
        raise ElfError(".dynsym sh_entsize is not Elf64_Sym")
    if dynsym.sh_link != dynstr.index:
        raise ElfError(".dynsym sh_link does not point at .dynstr")
    symtab = values.get(DT_SYMTAB)
    if symtab is None:
        raise ElfError("DT_SYMTAB is missing")
    _require_vaddr_maps_section(segments, symtab, dynsym, "DT_SYMTAB")

    versym_tag = values.get(DT_VERSYM)
    versyms = _named_sections(sections, ".gnu.version") + _typed_sections(sections, SHT_GNU_VERSYM)
    if versym_tag is None and versyms:
        raise ElfError("stray .gnu.version section without DT_VERSYM")
    if versym_tag is not None:
        versym = _require_unique_named_type(sections, ".gnu.version", SHT_GNU_VERSYM)
        _require_alloc(versym)
        if versym.sh_entsize != ELF64_VERSYM_SIZE:
            raise ElfError(".gnu.version sh_entsize is not Elf64_Half")
        if versym.sh_link != dynsym.index:
            raise ElfError(".gnu.version sh_link does not point at .dynsym")
        dynsym_count = dynsym.sh_size // ELF64_SYM_SIZE
        expected = _checked_mul(dynsym_count, ELF64_VERSYM_SIZE, ".gnu.version count*entsize")
        if versym.sh_size != expected:
            raise ElfError(".gnu.version size does not match .dynsym count")
        _require_vaddr_maps_section(segments, versym_tag, versym, "DT_VERSYM")

    verneed_tag = values.get(DT_VERNEED)
    verneed_num = values.get(DT_VERNEEDNUM)
    verneeds = _named_sections(sections, ".gnu.version_r") + _typed_sections(
        sections, SHT_GNU_VERNEED
    )
    if verneed_tag is None and verneeds:
        raise ElfError("stray .gnu.version_r section without DT_VERNEED")
    if verneed_tag is not None:
        if verneed_num is None:
            raise ElfError("DT_VERNEEDNUM is missing")
        verneed = _require_unique_named_type(sections, ".gnu.version_r", SHT_GNU_VERNEED)
        _require_alloc(verneed)
        if verneed.sh_link != dynstr.index:
            raise ElfError(".gnu.version_r sh_link does not point at .dynstr")
        if verneed.sh_info != verneed_num:
            raise ElfError(".gnu.version_r sh_info does not equal DT_VERNEEDNUM")
        _require_vaddr_maps_section(segments, verneed_tag, verneed, "DT_VERNEED")

    verdef_tag = values.get(DT_VERDEF)
    verdef_num = values.get(DT_VERDEFNUM)
    verdefs = _named_sections(sections, ".gnu.version_d") + _typed_sections(
        sections, SHT_GNU_VERDEF
    )
    if (verdef_tag is None) != (verdef_num is None):
        raise ElfError("DT_VERDEF and DT_VERDEFNUM must both be present or both absent")
    if verdef_tag is None and verdefs:
        raise ElfError("stray .gnu.version_d section without DT_VERDEF")
    if verdef_tag is not None:
        verdef = _require_unique_named_type(sections, ".gnu.version_d", SHT_GNU_VERDEF)
        _require_alloc(verdef)
        if verdef.sh_link != dynstr.index:
            raise ElfError(".gnu.version_d sh_link does not point at .dynstr")
        if verdef.sh_info != verdef_num:
            raise ElfError(".gnu.version_d sh_info does not equal DT_VERDEFNUM")
        _require_vaddr_maps_section(segments, verdef_tag, verdef, "DT_VERDEF")

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


def _matches_allowed_prefix_bytes(path: bytes, prefix: bytes) -> bool:
    return path == prefix or path.startswith(prefix + b"/")


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


def _is_allowed_prefix_near_miss(path: str) -> bool:
    if is_allowed_absolute_path(path):
        return False
    for prefix in ALLOWED_ABSOLUTE_PREFIXES:
        if path.startswith(prefix) and len(path) > len(prefix) and path[len(prefix)] != "/":
            return True
    return False


def _is_home_rebuild_tail(rest: bytes) -> bool:
    if not rest.startswith(_HOME_REBUILD):
        return False
    if len(rest) == len(_HOME_REBUILD):
        return True
    return rest[len(_HOME_REBUILD)] in _PATH_STOP or rest[len(_HOME_REBUILD)] == 0x2F


def _extract_through_stop(data: bytes, start: int, limit: int) -> bytes:
    end = start
    stop_at = min(len(data), start + limit)
    while end < stop_at and data[end] not in _PATH_STOP:
        end += 1
    return data[start:end]


def _display_fragment(data: bytes, start: int) -> str:
    raw = _extract_through_stop(data, start, MAX_PATH_DISPLAY)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def extract_slash_path_candidate(data: bytes, start: int) -> bytes:
    if start < 0 or start >= len(data) or data[start] != 0x2F:
        return b""
    return _extract_through_stop(data, start, MAX_PATH_CANDIDATE)


def _leading_ascii_text(raw: bytes) -> str:
    end = 0
    while end < len(raw) and raw[end] < 0x80:
        end += 1
    return raw[:end].decode("ascii")


def _root_boundary_follows(data: bytes, end: int) -> bool:
    if end == len(data):
        return True
    nxt = data[end]
    return nxt == 0x2F or nxt in _PATH_STOP


def _contains_raw_root(data: bytes, markers: tuple[bytes, ...]) -> bool:
    for marker in markers:
        if not marker:
            continue
        start = 0
        while True:
            index = data.find(marker, start)
            if index < 0:
                break
            if _root_boundary_follows(data, index + len(marker)):
                return True
            start = index + 1
    return False


def iter_raw_root_matches(data: bytes, marker: bytes):
    if not marker:
        return
    start = 0
    while True:
        index = data.find(marker, start)
        if index < 0:
            return
        if _root_boundary_follows(data, index + len(marker)):
            yield index
        start = index + 1


def _looks_unapproved_raw_path(raw: bytes) -> bool:
    """Fail-closed rule for invalid UTF-8 slash candidates.

    Binary ``/`` plus a letter and non-ASCII continuation is not a path.
    Fail when the candidate contains a documented build root, the leading
    ASCII prefix is an allowed-prefix near-miss, the ASCII prefix is a
    multi-component unapproved path, or a later ``/`` makes the blob
    look like an unapproved absolute path.
    """
    if not raw.startswith(b"/") or len(raw) < 2:
        return False
    if _contains_raw_root(raw, FORBIDDEN_BUILD_ROOTS):
        return True
    ascii_prefix = _leading_ascii_text(raw)
    trimmed = ascii_prefix.rstrip("/")
    if trimmed and is_allowed_absolute_path(trimmed):
        return False
    if ascii_prefix and _is_allowed_prefix_near_miss(ascii_prefix):
        return True
    if ascii_prefix and is_absolute_path_like(ascii_prefix) and "/" in ascii_prefix[1:]:
        return True
    if b"/" in raw[1:]:
        return True
    return False


def _is_path_start(data: bytes, index: int) -> bool:
    return index == 0 or data[index - 1] in _PATH_STOP


def _slash_candidate_is_forbidden(
    data: bytes,
    index: int,
    raw: bytes,
    extra_roots: tuple[bytes, ...],
) -> bool:
    if _contains_raw_root(raw, FORBIDDEN_BUILD_ROOTS + extra_roots):
        return True
    if not _is_path_start(data, index):
        return False
    home = raw.find(_HOME_PREFIX)
    if home >= 0 and not _is_home_rebuild_tail(raw[home + len(_HOME_PREFIX) :]):
        return True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _looks_unapproved_raw_path(raw)
    if is_allowed_absolute_path(text):
        return False
    if not is_absolute_path_like(text):
        return False
    if "/" in text[1:]:
        return True
    return _is_allowed_prefix_near_miss(text)


def scan_linux_forbidden_paths(
    data: bytes,
    extra_roots: tuple[bytes, ...] = (),
) -> list[str]:
    hits: list[str] = []

    def add(text: str) -> None:
        if text and text not in hits:
            hits.append(text)

    for marker in FORBIDDEN_BUILD_ROOTS + extra_roots:
        for index in iter_raw_root_matches(data, marker):
            add(_display_fragment(data, index))
    start = 0
    while True:
        index = data.find(_HOME_PREFIX, start)
        if index < 0:
            break
        if _is_path_start(data, index) and not _is_home_rebuild_tail(
            data[index + len(_HOME_PREFIX) :]
        ):
            add(_display_fragment(data, index))
        start = index + 1
    for index, byte in enumerate(data):
        if byte != 0x2F:
            continue
        raw = extract_slash_path_candidate(data, index)
        if len(raw) < 2:
            continue
        if _slash_candidate_is_forbidden(data, index, raw, extra_roots):
            add(_display_fragment(data, index))
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


def _readelf_field(line: str, label: str) -> str | None:
    tokens = line.split()
    needle = f"{label}:"
    for index, token in enumerate(tokens):
        if token == needle and index + 1 < len(tokens):
            return tokens[index + 1]
    return None


def parse_readelf_need_indices(text: str) -> dict[int, str]:
    """Exact per-line Name:/Version: Vernaux pairs from ``readelf --version-info``.

    Verneed file headers and Verdef ``Rev``/``Index`` rows are skipped.
    A ``Name:`` without ``Version:`` is a missing field. Duplicate
    ``Version`` indices fail even when the name matches.
    """
    parsed: dict[int, str] = {}
    for line_no, line in enumerate(text.splitlines(), start=1):
        tokens = line.split()
        name = _readelf_field(line, "Name")
        version = _readelf_field(line, "Version")
        if "File:" in tokens:
            continue
        if "Rev:" in tokens or _readelf_field(line, "Index") is not None:
            continue
        if name is None and version is None:
            continue
        if name is None or version is None:
            raise ElfError(
                f"readelf --version-info line {line_no} is missing a Name or Version field"
            )
        if not version.isdigit():
            raise ElfError(f"readelf Version field {version!r} is not an integer")
        index = int(version)
        if index in parsed:
            raise ElfError(f"duplicate readelf Version index {index}")
        parsed[index] = name
    return parsed


def parse_readelf_dynsym_records(text: str) -> list[ReadelfDynsymRecord]:
    """Parse GNU ``readelf --dyn-syms`` rows. No substring name search."""
    records: list[ReadelfDynsymRecord] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or not stripped[0].isdigit():
            continue
        if ":" not in stripped:
            raise ElfError(f"readelf --dyn-syms line {line_no} is malformed")
        match = READELF_DYNSYM_RE.fullmatch(line.rstrip("\n"))
        if match is None:
            raise ElfError(f"readelf --dyn-syms line {line_no} has malformed columns")
        raw_name = match.group(8) or ""
        ndx = match.group(7)
        if (
            match.group(4) == "FUNC"
            and match.group(5) in {"GLOBAL", "WEAK"}
            and ndx != "UND"
            and ndx.isdigit()
            and not raw_name
        ):
            raise ElfError(
                f"readelf --dyn-syms line {line_no} is missing a symbol name"
            )
        version = None
        name = raw_name
        if "@@" in raw_name:
            name, version = raw_name.split("@@", 1)
        elif "@" in raw_name:
            name, version = raw_name.split("@", 1)
        raw_index = match.group(9)
        records.append(
            ReadelfDynsymRecord(
                name=name,
                type_name=match.group(4),
                bind=match.group(5),
                visibility=match.group(6),
                ndx=match.group(7),
                version=version,
                version_index=int(raw_index) if raw_index is not None else None,
            )
        )
    return records


def require_exact_sign_readelf(
    records: list[ReadelfDynsymRecord],
    verdef_indices: dict[int, str],
) -> ReadelfDynsymRecord:
    matches = [item for item in records if item.name == SIGN_SYMBOL]
    if not matches:
        raise ElfError(f"{SIGN_SYMBOL} missing from readelf --dyn-syms records")
    if len(matches) > 1:
        raise ElfError(f"{SIGN_SYMBOL} is duplicate in readelf --dyn-syms records")
    record = matches[0]
    if record.type_name != "FUNC":
        raise ElfError(f"{SIGN_SYMBOL} readelf type {record.type_name!r} is not FUNC")
    if record.bind not in {"GLOBAL", "WEAK"}:
        raise ElfError(f"{SIGN_SYMBOL} readelf bind {record.bind!r} is not GLOBAL/WEAK")
    if record.visibility not in {"DEFAULT", "PROTECTED"}:
        raise ElfError(
            f"{SIGN_SYMBOL} readelf visibility {record.visibility!r} is not DEFAULT/PROTECTED"
        )
    if record.ndx == "UND" or not record.ndx.isdigit():
        raise ElfError(f"{SIGN_SYMBOL} readelf section {record.ndx!r} is not a defined section")
    if record.version is not None and record.version not in verdef_indices.values():
        raise ElfError(
            f"readelf --dyn-syms {SIGN_SYMBOL} version {record.version!r} "
            "is not a parsed Verdef name"
        )
    if record.version_index is not None:
        if record.version is None:
            if record.version_index != VER_NDX_GLOBAL:
                raise ElfError(
                    f"readelf --dyn-syms {SIGN_SYMBOL} version index "
                    f"{record.version_index} is not global"
                )
        elif record.version_index not in verdef_indices:
            raise ElfError(
                f"readelf --dyn-syms {SIGN_SYMBOL} version index "
                f"{record.version_index} is not a parsed Verdef"
            )
        elif verdef_indices[record.version_index] != record.version:
            raise ElfError(
                f"readelf --dyn-syms {SIGN_SYMBOL} version index "
                f"{record.version_index} does not match {record.version!r}"
            )
    return record


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
    dynamic_phdr: DynamicPhdr | None = None
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
            _checked_add(p_vaddr, p_memsz, "PT_LOAD memsz")
            _checked_add(p_offset, p_filesz, "PT_LOAD filesz")
            if p_align > 1:
                if p_align & (p_align - 1):
                    raise ElfError(f"PT_LOAD {index} p_align is not a power of two")
                if (p_vaddr % p_align) != (p_offset % p_align):
                    raise ElfError(f"PT_LOAD {index} p_vaddr/p_offset alignment mismatch")
            segments.append(
                LoadSegment(offset=p_offset, filesz=p_filesz, vaddr=p_vaddr, memsz=p_memsz)
            )
        elif p_type == PT_DYNAMIC:
            if dynamic_phdr is not None:
                raise ElfError("multiple PT_DYNAMIC headers")
            _checked_add(p_vaddr, p_memsz, "PT_DYNAMIC memsz")
            _checked_add(p_offset, p_filesz, "PT_DYNAMIC filesz")
            dynamic_phdr = DynamicPhdr(
                offset=p_offset,
                vaddr=p_vaddr,
                filesz=p_filesz,
                memsz=p_memsz,
                align=p_align,
            )
        elif p_type == PT_NOTE:
            notes.append((p_offset, p_filesz))

    if dynamic_phdr is None:
        raise ElfError("PT_DYNAMIC is missing")
    dynamic_off = dynamic_phdr.offset
    dynamic_size = dynamic_phdr.filesz
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
    verdef_vaddr = values.get(DT_VERDEF)
    verdef_num = values.get(DT_VERDEFNUM)

    if strtab_vaddr is None or strsz is None:
        raise ElfError("DT_STRTAB/DT_STRSZ is missing")
    if strsz > MAX_INPUT_BYTES:
        raise ElfError("DT_STRSZ exceeds MAX_INPUT_BYTES")
    _checked_add(strtab_vaddr, strsz, "DT_STRTAB")
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
    _validate_section_program_links(sections, segments, dynamic_phdr, values, e_shnum)

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
        entry = _checked_add(
            dynsym.sh_offset,
            _checked_mul(index, ELF64_SYM_SIZE, ".dynsym index"),
            ".dynsym entry",
        )
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
        if index == 0 and any(
            (st_name, st_info, st_other, st_shndx, st_value, st_size)
        ):
            raise ElfError("dynsym 0 is not the canonical null entry")

    _require_sign_export(parsed_symbols, e_shnum, record)

    if "libc.so.6" in record.needed:
        if verneed_vaddr is None or verneed_num is None:
            raise ElfError("DT_VERNEED/DT_VERNEEDNUM is required when libc.so.6 is needed")
        if values.get(DT_VERSYM) is None:
            raise ElfError("DT_VERSYM is required when libc.so.6 is needed")
        record.gnu_versions, record.verneed_indices = _parse_verneed(
            data,
            segments,
            sections,
            e_shnum,
            verneed_vaddr=verneed_vaddr,
            verneed_num=verneed_num,
            dynstr=dynstr,
            needed=record.needed,
        )
        # The same GLIBC_* label may appear on libc.so.6 and ld-linux-*
        # only with distinct vna_other values. Flattened names are used
        # for the baseline cap.
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

    if verdef_vaddr is not None and verdef_num is not None:
        record.verdef_indices = _parse_verdef(
            data,
            segments,
            sections,
            e_shnum,
            verdef_vaddr=verdef_vaddr,
            verdef_num=verdef_num,
            dynstr=dynstr,
        )
    _check_need_def_collisions(record.verneed_indices, record.verdef_indices)
    if values.get(DT_VERSYM) is not None:
        versym_section = _require_unique_named_type(sections, ".gnu.version", SHT_GNU_VERSYM)
        record.versym_values = _parse_versym_entries(data, versym_section, count)
        _resolve_versym(
            parsed_symbols,
            record.versym_values,
            record.verneed_indices,
            record.verdef_indices,
        )
        _require_sign_versym(parsed_symbols, record.versym_values, record.verdef_indices)

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


def _reject_reserved_version_index(index: int, what: str) -> None:
    if index in {VER_NDX_LOCAL, VER_NDX_GLOBAL}:
        raise ElfError(f"{what} uses reserved version index {index}")
    if index == VER_NDX_UNSPECIFIED:
        raise ElfError(f"{what} uses unresolved version index 0x7fff")


def _register_need_index(need_indices: dict[int, str], index: int, name: str) -> None:
    _reject_reserved_version_index(index, "vna_other")
    if index in need_indices:
        raise ElfError(f"duplicate vna_other {index} ({need_indices[index]!r} / {name!r})")
    need_indices[index] = name


def _register_def_index(def_indices: dict[int, str], index: int, name: str) -> None:
    _reject_reserved_version_index(index, "vd_ndx")
    existing = def_indices.get(index)
    if existing is not None and existing != name:
        raise ElfError(f"duplicate vd_ndx {index} for {existing!r} and {name!r}")
    def_indices[index] = name


def _check_need_def_collisions(need_indices: dict[int, str], def_indices: dict[int, str]) -> None:
    overlap = set(need_indices) & set(def_indices)
    if overlap:
        raise ElfError(f"version index collision between Verneed and Verdef: {sorted(overlap)}")


def _parse_versym_entries(data: bytes, section: Section, count: int) -> list[int]:
    if section.sh_entsize != ELF64_VERSYM_SIZE:
        raise ElfError(".gnu.version sh_entsize is not Elf64_Half")
    expected = _checked_mul(count, ELF64_VERSYM_SIZE, ".gnu.version count*entsize")
    if section.sh_size != expected:
        raise ElfError(".gnu.version size does not match .dynsym count")
    _checked_range(section.sh_offset, section.sh_size, len(data), ".gnu.version")
    values: list[int] = []
    for index in range(count):
        off = _checked_add(
            section.sh_offset,
            _checked_mul(index, ELF64_VERSYM_SIZE, ".gnu.version index"),
            ".gnu.version entry",
        )
        values.append(_u16(data, off))
    return values


def _resolve_versym(
    symbols: list[DynSymbol],
    raw_values: list[int],
    need_indices: dict[int, str],
    def_indices: dict[int, str],
) -> None:
    if len(raw_values) != len(symbols):
        raise ElfError(".gnu.version count does not equal dynsym count")
    for index, (symbol, raw) in enumerate(zip(symbols, raw_values)):
        hidden = bool(raw & VERSYM_HIDDEN)
        base = raw & VERSYM_NDX_MASK
        defined = symbol.shndx != SHN_UNDEF
        if base == VER_NDX_UNSPECIFIED:
            raise ElfError(f"unresolved versym 0x7fff on symbol {symbol.name or index}")
        if hidden and base in {VER_NDX_LOCAL, VER_NDX_UNSPECIFIED}:
            raise ElfError(f"hidden/inconsistent versym {raw:#x} on symbol {symbol.name or index}")
        if index == 0:
            if base != VER_NDX_LOCAL or hidden:
                raise ElfError("dynsym 0 versym is not VER_NDX_LOCAL")
            continue
        if base == VER_NDX_LOCAL:
            if defined:
                if symbol.bind != STB_LOCAL:
                    raise ElfError(
                        f"versym local index on defined non-local symbol {symbol.name or index}"
                    )
                continue
            if symbol.bind != STB_WEAK:
                raise ElfError(
                    f"versym local index on undefined non-weak symbol {symbol.name or index}"
                )
            continue
        if base == VER_NDX_GLOBAL:
            if symbol.bind == STB_LOCAL:
                raise ElfError(f"versym global index on local symbol {symbol.name or index}")
            continue
        if not defined:
            if base in def_indices:
                raise ElfError(f"imported versym {base} points at Verdef")
            if base not in need_indices:
                raise ElfError(f"imported versym {base} does not resolve to a Vernaux")
        else:
            if base in need_indices:
                raise ElfError(f"defined versym {base} points at Vernaux")
            if base not in def_indices:
                raise ElfError(f"defined versym {base} does not resolve to a Verdef")
        if symbol.name == SIGN_SYMBOL:
            if hidden:
                raise ElfError(f"{SIGN_SYMBOL} versym is hidden")
            if not defined:
                raise ElfError(f"{SIGN_SYMBOL} uses an import version")
            if base != VER_NDX_GLOBAL and base not in def_indices:
                raise ElfError(f"{SIGN_SYMBOL} versym {base} is not global or a Verdef")


def _require_sign_versym(symbols: list[DynSymbol], raw_values: list[int], def_indices: dict[int, str]) -> None:
    matches = [index for index, item in enumerate(symbols) if item.name == SIGN_SYMBOL]
    if not matches:
        raise ElfError(f"{SIGN_SYMBOL} is not exported")
    index = matches[0]
    raw = raw_values[index]
    hidden = bool(raw & VERSYM_HIDDEN)
    base = raw & VERSYM_NDX_MASK
    if hidden:
        raise ElfError(f"{SIGN_SYMBOL} versym is hidden")
    if base == VER_NDX_UNSPECIFIED:
        raise ElfError(f"{SIGN_SYMBOL} versym is unresolved")
    if base != VER_NDX_GLOBAL and base not in def_indices:
        raise ElfError(f"{SIGN_SYMBOL} versym {base} is not global or a matching Verdef")
    if base != VER_NDX_GLOBAL and base in def_indices:
        return
    if base == VER_NDX_GLOBAL:
        return
    raise ElfError(f"{SIGN_SYMBOL} uses an import version")


def _parse_verneed(
    data: bytes,
    segments: list[LoadSegment],
    sections: list[Section],
    e_shnum: int,
    *,
    verneed_vaddr: int,
    verneed_num: int,
    dynstr,
    needed: list[str],
) -> tuple[list[str], dict[int, str]]:
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
    mapped_end = _checked_add(mapped, ELF64_VERNEED_SIZE, "DT_VERNEED")
    if mapped < section_start or mapped_end > section_end:
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
    need_indices: dict[int, str] = {}
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
        if not file_name:
            raise ElfError("empty Verneed file identity")
        if file_name not in needed:
            raise ElfError(f"Verneed file {file_name!r} is not a DT_NEEDED name")
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
            vna_other = _u16(data, aux + 6)
            vna_name = _u32(data, aux + 8)
            vna_next = _u32(data, aux + 12)
            name = dynstr(vna_name)
            if not name:
                raise ElfError("empty GNU version name")
            _register_need_index(need_indices, vna_other, name)
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
    return names, need_indices


def _parse_verdef(
    data: bytes,
    segments: list[LoadSegment],
    sections: list[Section],
    e_shnum: int,
    *,
    verdef_vaddr: int,
    verdef_num: int,
    dynstr,
) -> dict[int, str]:
    if verdef_num <= 0 or verdef_num > MAX_VERDEF:
        raise ElfError(f"DT_VERDEFNUM {verdef_num} is missing or exceeds MAX_VERDEF")
    section = _require_unique_named_type(sections, ".gnu.version_d", SHT_GNU_VERDEF)
    if section.sh_link == 0 or section.sh_link >= e_shnum:
        raise ElfError(".gnu.version_d sh_link is out of range")
    if sections[section.sh_link].name != ".dynstr":
        raise ElfError(".gnu.version_d sh_link does not point at .dynstr")
    if section.sh_size < ELF64_VERDEF_SIZE:
        raise ElfError(".gnu.version_d is smaller than one Elf64_Verdef")
    section_start = section.sh_offset
    section_end = _checked_add(section.sh_offset, section.sh_size, ".gnu.version_d")
    mapped = _vaddr_to_offset(segments, verdef_vaddr)
    if mapped != section_start:
        raise ElfError("DT_VERDEF does not start at the SHT_GNU_verdef section")

    def _in_section(offset: int, size: int, what: str) -> None:
        end = _checked_add(offset, size, what)
        if offset < section_start or end > section_end:
            raise ElfError(f"{what} is outside the SHT_GNU_verdef section")
        if offset % 4 != 0:
            raise ElfError(f"{what} is not 4-byte aligned")

    visited: set[int] = set()
    occupied: list[tuple[int, int]] = []
    def_indices: dict[int, str] = {}
    cursor = mapped
    walked = 0
    for index in range(verdef_num):
        if cursor in visited:
            raise ElfError("Elf64_Verdef entry was revisited")
        _in_section(cursor, ELF64_VERDEF_SIZE, "Elf64_Verdef")
        _claim_range(occupied, cursor, ELF64_VERDEF_SIZE, "Elf64_Verdef")
        visited.add(cursor)
        vd_version = _u16(data, cursor)
        vd_ndx = _u16(data, cursor + 4)
        vd_cnt = _u16(data, cursor + 6)
        vd_aux = _u32(data, cursor + 12)
        vd_next = _u32(data, cursor + 16)
        if vd_version != VER_DEF_CURRENT:
            raise ElfError(f"vd_version {vd_version} is not VER_DEF_CURRENT")
        if vd_cnt == 0 or vd_cnt > MAX_VERDAUX:
            raise ElfError("vd_cnt is missing or exceeds MAX_VERDAUX")
        if vd_aux == 0:
            raise ElfError("vd_aux is missing")
        aux = _checked_add(cursor, vd_aux, "vd_aux")
        if aux <= cursor:
            raise ElfError("vd_aux is not a positive forward offset")
        first_name = ""
        for aux_index in range(vd_cnt):
            _in_section(aux, ELF64_VERDAUX_SIZE, "Elf64_Verdaux")
            _claim_range(occupied, aux, ELF64_VERDAUX_SIZE, "Elf64_Verdaux")
            vda_name = _u32(data, aux)
            vda_next = _u32(data, aux + 4)
            name = dynstr(vda_name)
            if not name:
                raise ElfError("empty GNU version definition name")
            if aux_index == 0:
                first_name = name
            last_aux = aux_index + 1 == vd_cnt
            if last_aux:
                if vda_next != 0:
                    raise ElfError("final vda_next is not zero")
            else:
                if vda_next == 0:
                    raise ElfError("Elf64_Verdaux chain is truncated")
                nxt = _checked_add(aux, vda_next, "vda_next")
                if nxt <= aux:
                    raise ElfError("vda_next is not a positive forward offset")
                aux = nxt
        _register_def_index(def_indices, vd_ndx, first_name)
        walked += 1
        last_vd = index + 1 == verdef_num
        if last_vd:
            if vd_next != 0:
                raise ElfError("final vd_next is not zero")
        else:
            if vd_next == 0:
                raise ElfError("Elf64_Verdef chain is truncated")
            nxt = _checked_add(cursor, vd_next, "vd_next")
            if nxt <= cursor:
                raise ElfError("vd_next is not a positive forward offset")
            cursor = nxt
    if walked != verdef_num:
        raise ElfError("DT_VERDEFNUM does not match the walked Verdef count")
    return def_indices


def _note_has_build_id(blob: bytes) -> bool:
    cursor = 0
    while _checked_add(cursor, 12, "ELF note header") <= len(blob):
        namesz = _u32(blob, cursor)
        descsz = _u32(blob, cursor + 4)
        ntype = _u32(blob, cursor + 8)
        cursor = _checked_add(cursor, 12, "ELF note header")
        name_end = _checked_add(cursor, namesz, "ELF note name")
        desc_start = _checked_align_up(name_end, 4, "ELF note name pad")
        desc_end = _checked_add(desc_start, descsz, "ELF note desc")
        if desc_end > len(blob):
            raise ElfError("truncated ELF note")
        name = blob[cursor:name_end]
        if ntype == NT_GNU_BUILD_ID and name.startswith(b"GNU"):
            return True
        cursor = _checked_align_up(desc_end, 4, "ELF note desc pad")
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
        if record.verneed_indices:
            tool_need = parse_readelf_need_indices(record.readelf_version_text)
            if not tool_need:
                raise ElfError("readelf --version-info version index map is empty")
            if tool_need != record.verneed_indices:
                raise ElfError(
                    "readelf --version-info Name/Version indices do not match the parser: "
                    f"{tool_need} vs {record.verneed_indices}"
                )
        dynsyms = _run([readelf_bin, "--dyn-syms", "--wide", str(path)])
        if dynsyms.returncode != 0:
            raise ElfError(f"readelf --dyn-syms --wide exited {dynsyms.returncode}")
        require_exact_sign_readelf(
            parse_readelf_dynsym_records((dynsyms.stdout or "") + (dynsyms.stderr or "")),
            record.verdef_indices,
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
