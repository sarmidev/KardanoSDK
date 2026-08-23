"""Fail-closed ELF64 verifier for the Linux x86-64 JVM signing cdylib.

Numeric encodings are from glibc elf.h / LSB Core (ELF64). This module
does not invent command numbers. Scope is the JNA resource
``linux-x86-64/libkardano_ed25519_bip32_signing.so`` only — Linux ARM
is out of scope and rejected.

Policy (documented, not a strength claim):

- ELFCLASS64, ELFDATA2LSB, ET_DYN, EM_X86_64
- SONAME exactly ``libkardano_ed25519_bip32_signing.so``
- DT_NEEDED names are a non-empty subset of the glibc/libgcc allowlist
  and must include ``libc.so.6``
- DT_RPATH and DT_RUNPATH are absent
- NT_GNU_BUILD_ID is absent (link with ``-Wl,--build-id=none``)
- no ``.debug_*`` section names
- exported UniFFI sign symbol is present
"""

from __future__ import annotations

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
SHT_NOTE = 7
DT_NULL = 0
DT_NEEDED = 1
DT_STRTAB = 5
DT_STRSZ = 10
DT_SONAME = 14
DT_RPATH = 15
DT_SYMTAB = 6
DT_SYMENT = 11
DT_RUNPATH = 29
NT_GNU_BUILD_ID = 3
STB_WEAK = 2
SHN_UNDEF = 0

ELF64_EHDR_SIZE = 64
ELF64_PHDR_SIZE = 56
ELF64_SHDR_SIZE = 64
ELF64_DYN_SIZE = 16
ELF64_SYM_SIZE = 24

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_PHNUM = 128
MAX_SHNUM = 256
MAX_DYNAMIC_TAGS = 256
MAX_NEEDED = 16
MAX_NOTE_BYTES = 4096
MAX_DYNSYM = 4096

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

DEBUG_SECTION_PREFIX = ".debug_"


class ElfError(RuntimeError):
    pass


@dataclass
class LoadSegment:
    offset: int
    filesz: int
    vaddr: int
    memsz: int


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
    nm_text: str = ""


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


def parse_elf64_le_x86_64_dso(data: bytes) -> ElfRecord:
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
    if e_phnum == 0 or e_phnum > MAX_PHNUM:
        raise ElfError(f"e_phnum {e_phnum} is missing or exceeds MAX_PHNUM")
    ph_end = e_phoff + e_phnum * ELF64_PHDR_SIZE
    if e_phoff < ELF64_EHDR_SIZE or ph_end > len(data):
        raise ElfError("program header table is out of bounds")

    segments: list[LoadSegment] = []
    dynamic_off: int | None = None
    dynamic_size = 0
    notes: list[tuple[int, int]] = []
    for index in range(e_phnum):
        off = e_phoff + index * ELF64_PHDR_SIZE
        p_type = _u32(data, off)
        p_offset = _u64(data, off + 8)
        p_vaddr = _u64(data, off + 16)
        p_filesz = _u64(data, off + 32)
        p_memsz = _u64(data, off + 40)
        if p_offset + p_filesz > len(data):
            raise ElfError(f"program header {index} file range exceeds the file")
        if p_type == PT_LOAD:
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
    saw_null = False
    for index in range(tag_count):
        tag = _i64(data, dynamic_off + index * ELF64_DYN_SIZE)
        value = _u64(data, dynamic_off + index * ELF64_DYN_SIZE + 8)
        if tag == DT_NULL:
            saw_null = True
            break
        tags.append((tag, value))
    if not saw_null:
        raise ElfError("PT_DYNAMIC is missing DT_NULL")

    strtab_vaddr = None
    strsz = None
    soname_off = None
    needed_offs: list[int] = []
    rpath_offs: list[int] = []
    runpath_offs: list[int] = []
    symtab_vaddr = None
    syment = None
    for tag, value in tags:
        if tag == DT_STRTAB:
            strtab_vaddr = value
        elif tag == DT_STRSZ:
            strsz = value
        elif tag == DT_SONAME:
            soname_off = value
        elif tag == DT_NEEDED:
            needed_offs.append(value)
        elif tag == DT_RPATH:
            rpath_offs.append(value)
        elif tag == DT_RUNPATH:
            runpath_offs.append(value)
        elif tag == DT_SYMTAB:
            symtab_vaddr = value
        elif tag == DT_SYMENT:
            syment = value

    if strtab_vaddr is None or strsz is None:
        raise ElfError("DT_STRTAB/DT_STRSZ is missing")
    if strsz > MAX_INPUT_BYTES:
        raise ElfError("DT_STRSZ exceeds MAX_INPUT_BYTES")
    strtab_off = _vaddr_to_offset(segments, strtab_vaddr)
    strtab_end = strtab_off + strsz
    if strtab_end > len(data):
        raise ElfError("DT_STRTAB range exceeds the file")

    def dynstr(offset: int) -> str:
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
    sh_end = e_shoff + e_shnum * ELF64_SHDR_SIZE
    if e_shoff < ELF64_EHDR_SIZE or sh_end > len(data):
        raise ElfError("section header table is out of bounds")
    if e_shstrndx == 0 or e_shstrndx >= e_shnum:
        raise ElfError("e_shstrndx is out of range")
    shstr = e_shoff + e_shstrndx * ELF64_SHDR_SIZE
    shstr_off = _u64(data, shstr + 24)
    shstr_size = _u64(data, shstr + 32)
    if shstr_off + shstr_size > len(data):
        raise ElfError(".shstrtab is out of bounds")
    for index in range(e_shnum):
        sh = e_shoff + index * ELF64_SHDR_SIZE
        name_off = _u32(data, sh)
        sh_type = _u32(data, sh + 4)
        sh_offset = _u64(data, sh + 24)
        sh_size = _u64(data, sh + 32)
        name = _cstring(data, shstr_off + name_off, shstr_off + shstr_size)
        record.section_names.append(name)
        if name.startswith(DEBUG_SECTION_PREFIX):
            raise ElfError(f"debug section {name} is present")
        if sh_type == SHT_NOTE:
            notes.append((sh_offset, sh_size))

    for off, size in notes:
        if size > MAX_NOTE_BYTES:
            raise ElfError("note payload exceeds MAX_NOTE_BYTES")
        if off + size > len(data):
            raise ElfError("note range exceeds the file")
        if _note_has_build_id(data[off : off + size]):
            record.has_build_id = True
            raise ElfError("NT_GNU_BUILD_ID is present; policy is --build-id=none")

    if symtab_vaddr is None or syment is None:
        raise ElfError("DT_SYMTAB/DT_SYMENT is missing")
    if syment != ELF64_SYM_SIZE:
        raise ElfError(f"DT_SYMENT {syment} != {ELF64_SYM_SIZE}")
    sym_off = _vaddr_to_offset(segments, symtab_vaddr)
    # Dynsym length is not in a required DT_* tag; walk until the mapped
    # segment ends or MAX_DYNSYM, requiring a defined SIGN_SYMBOL.
    remaining = 0
    for seg in segments:
        if seg.offset <= sym_off < seg.offset + seg.filesz:
            remaining = seg.offset + seg.filesz - sym_off
            break
    if remaining < ELF64_SYM_SIZE:
        raise ElfError("DT_SYMTAB is outside PT_LOAD")
    count = min(remaining // ELF64_SYM_SIZE, MAX_DYNSYM)
    for index in range(count):
        entry = sym_off + index * ELF64_SYM_SIZE
        st_name = _u32(data, entry)
        st_info = data[entry + 4]
        st_shndx = _u16(data, entry + 6)
        bind = st_info >> 4
        if st_name == 0 or st_shndx == SHN_UNDEF or bind > STB_WEAK:
            continue
        try:
            name = dynstr(st_name)
        except ElfError:
            continue
        record.symbols.append(name)
    if SIGN_SYMBOL not in record.symbols:
        raise ElfError(f"{SIGN_SYMBOL} is not exported")
    return record


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
        name = blob[cursor : name_end]
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
) -> ElfRecord:
    data = path.read_bytes()
    record = parse_elf64_le_x86_64_dso(data)
    record.path = str(path)
    readelf_bin = readelf or shutil.which("readelf")
    nm_bin = nm or shutil.which("nm")
    if require_tools:
        if not readelf_bin:
            raise ElfError("readelf is required")
        if not nm_bin:
            raise ElfError("nm is required")
    if readelf_bin:
        completed = _run([readelf_bin, "-d", str(path)])
        record.readelf_returncode = completed.returncode
        record.readelf_text = ((completed.stdout or "") + (completed.stderr or "")).strip()
        if completed.returncode != 0:
            raise ElfError(f"readelf -d exited {completed.returncode}")
    if nm_bin:
        completed = _run([nm_bin, "-D", str(path)])
        record.nm_returncode = completed.returncode
        record.nm_text = ((completed.stdout or "") + (completed.stderr or "")).strip()
        if completed.returncode != 0:
            raise ElfError(f"nm -D exited {completed.returncode}")
        if SIGN_SYMBOL not in record.nm_text:
            raise ElfError(f"{SIGN_SYMBOL} missing from nm -D output")
    return record
