"""Fail-closed PE32+ verifier for the Windows x86-64 JVM signing DLL.

Numeric encodings are from the Microsoft PE/COFF specification
(revision 11 / Windows Authenticode). This module does not invent
magic numbers. Scope is the JNA 5.19.1 resource
``win32-x86-64/kardano_ed25519_bip32_signing.dll`` only — Windows ARM
(``win32-aarch64``), PE32, and EXE images are out of scope.

JNA 5.19.1 ``Platform.getNativeLibraryResourcePrefix(WINDOWS, x86_64)``
is ``win32-`` plus canonical arch ``x86-64``.
``NativeLibrary.mapSharedLibraryName`` on Windows appends ``.dll`` and
does not add a ``lib`` prefix. Generated UniFFI bindings call
``Native.register(..., "kardano_ed25519_bip32_signing")``.

Policy (documented, not a strength claim):

- DOS ``MZ``, ``e_lfanew`` in bounds, PE signature ``PE\\0\\0``
- COFF ``IMAGE_FILE_MACHINE_AMD64``, ``IMAGE_FILE_DLL``,
  ``IMAGE_FILE_EXECUTABLE_IMAGE``
- Optional magic ``PE32+`` (``0x20B``), ``NumberOfRvaAndSizes == 16``
- checked header/section/directory/RVA→file mapping; no overlap or
  wrap; no unexpected overlay past the last section raw end
- required UniFFI sign export is exact, defined, unique, named, and
  maps to a non-zero in-image RVA; ``dumpbin /EXPORTS`` must match
- import DLLs are a non-empty subset of the rustc 1.97 MSVC system
  allowlist (case-insensitive); delay-load and Authenticode directories
  are empty; no unexpected import names
- no CODEVIEW/PDB debug directory, no ``RSDS``/``.pdb``, no embedded
  workspace/home/temp roots. ``/Brepro`` may emit ``IMAGE_DEBUG_TYPE_REPRO``
  (and other non-PDB MSVC metadata types). COFF ``TimeDateStamp`` is
  recorded; VS 2022 ``/Brepro`` may emit a hash, not 0; A==B is the
  reproducibility gate
- subsystem ``IMAGE_SUBSYSTEM_WINDOWS_GUI`` as rustc 1.97.0 + MSVC
  emit for this cdylib; DLL characteristics include ``DYNAMIC_BASE``
  and ``NX_COMPAT`` and only the documented extra bits
"""

from __future__ import annotations

import glob
import re
import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SIGN_SYMBOL = "uniffi_kardano_ed25519_bip32_signing_fn_func_sign"
# rustc cdylib for crate kardano-ed25519-bip32-signing on MSVC.
STABLE_DLL_NAME = "kardano_ed25519_bip32_signing.dll"
JNA_RESOURCE_PREFIX = "win32-x86-64"
JNA_RESOURCE_RELATIVE = f"src/jvmMain/resources/{JNA_RESOURCE_PREFIX}/{STABLE_DLL_NAME}"

# Microsoft PE/COFF.
DOS_MAGIC = b"MZ"
PE_SIGNATURE = b"PE\x00\x00"
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_MACHINE_I386 = 0x014C
IMAGE_FILE_MACHINE_ARM64 = 0xAA64
IMAGE_FILE_EXECUTABLE_IMAGE = 0x0002
IMAGE_FILE_LARGE_ADDRESS_AWARE = 0x0020
IMAGE_FILE_DLL = 0x2000
IMAGE_FILE_SYSTEM = 0x1000
IMAGE_NT_OPTIONAL_HDR64_MAGIC = 0x20B
IMAGE_NT_OPTIONAL_HDR32_MAGIC = 0x10B
IMAGE_SUBSYSTEM_WINDOWS_GUI = 2
IMAGE_SUBSYSTEM_WINDOWS_CUI = 3
IMAGE_DLLCHARACTERISTICS_HIGH_ENTROPY_VA = 0x0020
IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE = 0x0040
IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY = 0x0080
IMAGE_DLLCHARACTERISTICS_NX_COMPAT = 0x0100
IMAGE_DLLCHARACTERISTICS_NO_ISOLATION = 0x0200
IMAGE_DLLCHARACTERISTICS_NO_SEH = 0x0400
IMAGE_DLLCHARACTERISTICS_NO_BIND = 0x0800
IMAGE_DLLCHARACTERISTICS_APPCONTAINER = 0x1000
IMAGE_DLLCHARACTERISTICS_WDM_DRIVER = 0x2000
IMAGE_DLLCHARACTERISTICS_GUARD_CF = 0x4000
IMAGE_DLLCHARACTERISTICS_TERMINAL_SERVER_AWARE = 0x8000

REQUIRED_DLL_CHARACTERISTICS = (
    IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE | IMAGE_DLLCHARACTERISTICS_NX_COMPAT
)
ALLOWED_EXTRA_DLL_CHARACTERISTICS = (
    IMAGE_DLLCHARACTERISTICS_HIGH_ENTROPY_VA
    | IMAGE_DLLCHARACTERISTICS_NO_ISOLATION
    | IMAGE_DLLCHARACTERISTICS_NO_SEH
    | IMAGE_DLLCHARACTERISTICS_GUARD_CF
    | IMAGE_DLLCHARACTERISTICS_TERMINAL_SERVER_AWARE
)

DIR_EXPORT = 0
DIR_IMPORT = 1
DIR_RESOURCE = 2
DIR_EXCEPTION = 3
DIR_SECURITY = 4
DIR_BASERELOC = 5
DIR_DEBUG = 6
DIR_ARCHITECTURE = 7
DIR_GLOBALPTR = 8
DIR_TLS = 9
DIR_LOAD_CONFIG = 10
DIR_BOUND_IMPORT = 11
DIR_IAT = 12
DIR_DELAY_IMPORT = 13
DIR_CLR = 14
DIR_RESERVED = 15
IMAGE_NUMBEROF_DIRECTORY_ENTRIES = 16

IMAGE_SCN_CNT_CODE = 0x00000020
IMAGE_SCN_MEM_EXECUTE = 0x20000000

DOS_HEADER_SIZE = 64
COFF_HEADER_SIZE = 20
OPTIONAL_HEADER64_SIZE = 240
SECTION_HEADER_SIZE = 40
EXPORT_DIRECTORY_SIZE = 40
IMPORT_DESCRIPTOR_SIZE = 20
IMAGE_DEBUG_DIRECTORY_SIZE = 28
IMAGE_DEBUG_TYPE_CODEVIEW = 2
IMAGE_DEBUG_TYPE_VC_FEATURE = 12
IMAGE_DEBUG_TYPE_POGO = 13
IMAGE_DEBUG_TYPE_ILTCG = 14
IMAGE_DEBUG_TYPE_REPRO = 16
IMAGE_DEBUG_TYPE_EX_DLLCHARACTERISTICS = 20
# rustc 1.97 + VS 2022 /DEBUG:NONE /Brepro. CODEVIEW/PDB is refused.
ALLOWED_DEBUG_TYPES = frozenset(
    {
        IMAGE_DEBUG_TYPE_REPRO,
        IMAGE_DEBUG_TYPE_VC_FEATURE,
        IMAGE_DEBUG_TYPE_POGO,
        IMAGE_DEBUG_TYPE_ILTCG,
        IMAGE_DEBUG_TYPE_EX_DLLCHARACTERISTICS,
    }
)
DATA_DIRECTORY_SIZE = 8
UINT32_MAX = 0xFFFFFFFF
UINT64_MAX = 0xFFFFFFFFFFFFFFFF

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_SECTIONS = 96
MAX_EXPORTS = 4096
MAX_IMPORT_DLLS = 64
MAX_IMPORT_NAMES = 4096
MAX_PATH_CANDIDATE = 4096
MAX_PATH_DISPLAY = 160

# rustc 1.97 x86_64-pc-windows-msvc cdylib system/UCRT set. Extra names fail.
# Refined only from Windows-runner dumpbin output, never guessed at promotion.
ALLOWED_IMPORT_DLLS = frozenset(
    {
        "kernel32.dll",
        "ntdll.dll",
        "advapi32.dll",
        "bcrypt.dll",
        "bcryptprimitives.dll",
        "ws2_32.dll",
        "userenv.dll",
        "crypt32.dll",
        "secur32.dll",
        "ncrypt.dll",
        "iphlpapi.dll",
        "psapi.dll",
        "ole32.dll",
        "shell32.dll",
        "shlwapi.dll",
        "user32.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll",
        "concrt140.dll",
        "api-ms-win-crt-runtime-l1-1-0.dll",
        "api-ms-win-crt-heap-l1-1-0.dll",
        "api-ms-win-crt-stdio-l1-1-0.dll",
        "api-ms-win-crt-string-l1-1-0.dll",
        "api-ms-win-crt-math-l1-1-0.dll",
        "api-ms-win-crt-convert-l1-1-0.dll",
        "api-ms-win-crt-environment-l1-1-0.dll",
        "api-ms-win-crt-locale-l1-1-0.dll",
        "api-ms-win-crt-filesystem-l1-1-0.dll",
        "api-ms-win-crt-time-l1-1-0.dll",
        "api-ms-win-crt-utility-l1-1-0.dll",
        "api-ms-win-crt-process-l1-1-0.dll",
        "api-ms-win-crt-conio-l1-1-0.dll",
        # Observed on windows-2022 rustc 1.97.0 MSVC candidate A/B
        # (run 32713976878); not guessed.
        "api-ms-win-core-synch-l1-2-0.dll",
    }
)

FORBIDDEN_DEBUG_MARKERS = (b"RSDS", b".pdb", b".PDB")
FORBIDDEN_BUILD_ROOTS = (
    b"C:\\Users",
    b"C:/Users",
    b"D:\\a\\",
    b"D:/a/",
    b"/Users/",
    b"\\Users\\",
    b"/home/runner",
    b"/opt/hostedtoolcache",
    b"/private/var/folders",
    b"/var/folders",
    b"/opt/homebrew",
    b"C:\\Program Files\\Microsoft Visual Studio",
    b"C:/Program Files/Microsoft Visual Studio",
)
ALLOWED_REMAP_PREFIXES = (
    "/cargo-target",
    "/kardano",
    "/rustc",
    "/rust/deps",
    "/rustup",
    "/cargo",
    "/home/rebuild",
    "/runner-temp",
    "/runner-workspace",
)

DUMPBIN_MACHINE_RE = re.compile(r"\b8664 machine \(x64\)", re.IGNORECASE)
DUMPBIN_PE32PLUS_RE = re.compile(r"\b20B magic #\s*\(PE32\+\)", re.IGNORECASE)
DUMPBIN_DLL_RE = re.compile(r"^\s+DLL\s*$", re.MULTILINE)
DUMPBIN_EXPORT_RE = re.compile(
    r"^\s+\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(\S+)\s*$",
    re.MULTILINE,
)
DUMPBIN_DEPENDENT_RE = re.compile(r"^\s+([\w\-]+\.dll)\s*$", re.IGNORECASE | re.MULTILINE)


class PeError(RuntimeError):
    pass


@dataclass
class Section:
    name: str
    virtual_size: int
    virtual_address: int
    size_of_raw_data: int
    pointer_to_raw_data: int
    characteristics: int


@dataclass
class DataDirectory:
    index: int
    rva: int
    size: int


@dataclass
class ExportRecord:
    name: str
    ordinal: int
    rva: int


@dataclass
class ImportDll:
    name: str
    functions: list[str]


@dataclass
class PeRecord:
    path: str
    size: int
    machine: int
    characteristics: int
    timestamp: int
    magic: int
    subsystem: int
    dll_characteristics: int
    image_base: int
    section_alignment: int
    file_alignment: int
    size_of_image: int
    size_of_headers: int
    number_of_rva_and_sizes: int
    sections: list[Section] = field(default_factory=list)
    directories: list[DataDirectory] = field(default_factory=list)
    exports: list[ExportRecord] = field(default_factory=list)
    imports: list[ImportDll] = field(default_factory=list)
    sign_exports: list[ExportRecord] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    dumpbin_text: str = ""
    dumpbin_returncode: int | None = None
    documented_jna_prefix: str = JNA_RESOURCE_PREFIX


def _checked_add(left: int, right: int, *, limit: int = UINT64_MAX) -> int:
    if left < 0 or right < 0:
        raise PeError("checked add rejected a negative operand")
    total = left + right
    if total > limit:
        raise PeError("checked add overflowed")
    return total


def _checked_mul(left: int, right: int, *, limit: int = UINT64_MAX) -> int:
    if left < 0 or right < 0:
        raise PeError("checked mul rejected a negative operand")
    total = left * right
    if total > limit:
        raise PeError("checked mul overflowed")
    return total


def _u16(data: bytes, offset: int) -> int:
    end = _checked_add(offset, 2, limit=len(data))
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    end = _checked_add(offset, 4, limit=len(data))
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    end = _checked_add(offset, 8, limit=len(data))
    return struct.unpack_from("<Q", data, offset)[0]


def _slice(data: bytes, offset: int, size: int) -> bytes:
    end = _checked_add(offset, size, limit=len(data))
    return data[offset:end]


def _ascii_z(data: bytes, offset: int, *, limit: int = 512) -> str:
    if offset < 0 or offset >= len(data):
        raise PeError("string offset is outside the image")
    end = offset
    while end < len(data) and end - offset < limit and data[end] != 0:
        end += 1
    if end >= len(data) or data[end] != 0:
        raise PeError("unterminated PE string")
    try:
        return data[offset:end].decode("ascii")
    except UnicodeDecodeError as error:
        raise PeError("non-ASCII PE string") from error


def rva_to_offset(sections: list[Section], rva: int, size: int = 1) -> int:
    if rva == 0:
        raise PeError("RVA 0 cannot be mapped")
    last = _checked_add(rva, size - 1 if size else 0, limit=UINT32_MAX)
    for section in sections:
        va_end = _checked_add(section.virtual_address, max(section.virtual_size, 1) - 1, limit=UINT32_MAX)
        if section.virtual_address <= rva <= va_end:
            delta = rva - section.virtual_address
            if delta >= section.size_of_raw_data:
                raise PeError("RVA lands in virtual-only section padding")
            raw_end = _checked_add(delta, size if size else 1, limit=UINT32_MAX)
            if raw_end > section.size_of_raw_data:
                raise PeError("RVA range exceeds section raw data")
            return _checked_add(section.pointer_to_raw_data, delta, limit=UINT32_MAX)
    raise PeError(f"RVA 0x{rva:x} is not in any section")


def _require_empty_directory(directories: list[DataDirectory], index: int, label: str) -> None:
    entry = directories[index]
    if entry.rva != 0 or entry.size != 0:
        raise PeError(f"{label} data directory must be empty")


def _require_debug_directory(
    data: bytes, sections: list[Section], entry: DataDirectory
) -> None:
    if entry.rva == 0 and entry.size == 0:
        return
    if entry.rva == 0 or entry.size == 0:
        raise PeError("debug data directory is truncated")
    if entry.size % IMAGE_DEBUG_DIRECTORY_SIZE != 0:
        raise PeError("debug data directory size is not a multiple of 28")
    count = entry.size // IMAGE_DEBUG_DIRECTORY_SIZE
    if count == 0 or count > 16:
        raise PeError("debug data directory entry count is out of range")
    base = rva_to_offset(sections, entry.rva, entry.size)
    for index in range(count):
        off = _checked_add(base, _checked_mul(index, IMAGE_DEBUG_DIRECTORY_SIZE, limit=UINT32_MAX))
        debug_type = _u32(data, off + 12)
        size_of_data = _u32(data, off + 16)
        address_of_raw = _u32(data, off + 20)
        pointer_to_raw = _u32(data, off + 24)
        if debug_type == IMAGE_DEBUG_TYPE_CODEVIEW:
            raise PeError("CODEVIEW/PDB debug directory is not allowed")
        if debug_type not in ALLOWED_DEBUG_TYPES:
            raise PeError(f"unexpected debug directory type {debug_type}")
        if size_of_data:
            if pointer_to_raw:
                end = _checked_add(pointer_to_raw, size_of_data, limit=len(data))
                if end > len(data):
                    raise PeError("debug payload PointerToRawData is out of range")
            elif address_of_raw:
                rva_to_offset(sections, address_of_raw, size_of_data)


def parse_elf_style_ranges(ranges: list[tuple[int, int]], label: str) -> None:
    ordered = sorted(ranges)
    for index, (start, end) in enumerate(ordered):
        if start < 0 or end < start:
            raise PeError(f"{label} range is inverted")
        if index == 0:
            continue
        prev_start, prev_end = ordered[index - 1]
        if start < prev_end and end > prev_start:
            raise PeError(f"{label} ranges overlap")


def parse_pe32_plus_x86_64_dll(data: bytes) -> PeRecord:
    if len(data) > MAX_INPUT_BYTES:
        raise PeError(f"image exceeds MAX_INPUT_BYTES ({MAX_INPUT_BYTES})")
    if len(data) < DOS_HEADER_SIZE:
        raise PeError("truncated DOS header")
    if data[0:2] != DOS_MAGIC:
        raise PeError("DOS magic is not MZ")
    e_lfanew = _u32(data, 0x3C)
    if e_lfanew < DOS_HEADER_SIZE:
        raise PeError("e_lfanew overlaps the DOS header")
    pe_end = _checked_add(e_lfanew, 4 + COFF_HEADER_SIZE + OPTIONAL_HEADER64_SIZE, limit=len(data))
    if data[e_lfanew : e_lfanew + 4] != PE_SIGNATURE:
        raise PeError("PE signature is missing")
    coff = e_lfanew + 4
    machine = _u16(data, coff)
    nsections = _u16(data, coff + 2)
    timestamp = _u32(data, coff + 4)
    ptr_sym = _u32(data, coff + 8)
    nsyms = _u32(data, coff + 12)
    opt_size = _u16(data, coff + 16)
    characteristics = _u16(data, coff + 18)
    if machine != IMAGE_FILE_MACHINE_AMD64:
        raise PeError(f"COFF machine 0x{machine:x} is not AMD64")
    if machine in {IMAGE_FILE_MACHINE_I386, IMAGE_FILE_MACHINE_ARM64}:
        raise PeError("rejected non-x86-64 COFF machine")
    if nsections == 0 or nsections > MAX_SECTIONS:
        raise PeError("invalid NumberOfSections")
    if opt_size != OPTIONAL_HEADER64_SIZE:
        raise PeError("SizeOfOptionalHeader is not PE32+ 240")
    if ptr_sym != 0 or nsyms != 0:
        raise PeError("COFF symbol table must be absent")
    if characteristics & IMAGE_FILE_SYSTEM:
        raise PeError("IMAGE_FILE_SYSTEM is not allowed")
    if not (characteristics & IMAGE_FILE_DLL):
        raise PeError("IMAGE_FILE_DLL is required")
    if not (characteristics & IMAGE_FILE_EXECUTABLE_IMAGE):
        raise PeError("IMAGE_FILE_EXECUTABLE_IMAGE is required")

    optional = coff + COFF_HEADER_SIZE
    magic = _u16(data, optional)
    if magic == IMAGE_NT_OPTIONAL_HDR32_MAGIC:
        raise PeError("PE32 (0x10B) is out of scope")
    if magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC:
        raise PeError(f"optional magic 0x{magic:x} is not PE32+")
    entry = _u32(data, optional + 0x10)
    image_base = _u64(data, optional + 0x18)
    section_alignment = _u32(data, optional + 0x20)
    file_alignment = _u32(data, optional + 0x24)
    size_of_image = _u32(data, optional + 0x38)
    size_of_headers = _u32(data, optional + 0x3C)
    subsystem = _u16(data, optional + 0x44)
    dll_characteristics = _u16(data, optional + 0x46)
    number_of_rva = _u32(data, optional + 0x6C)
    if section_alignment == 0 or file_alignment == 0:
        raise PeError("section/file alignment is zero")
    if file_alignment > section_alignment:
        raise PeError("FileAlignment exceeds SectionAlignment")
    if file_alignment & (file_alignment - 1) or section_alignment & (section_alignment - 1):
        raise PeError("alignments must be powers of two")
    if size_of_headers == 0 or size_of_headers > len(data):
        raise PeError("SizeOfHeaders is out of range")
    if size_of_headers % file_alignment != 0:
        raise PeError("SizeOfHeaders is not FileAlignment-aligned")
    if size_of_image == 0:
        raise PeError("SizeOfImage is zero")
    if number_of_rva != IMAGE_NUMBEROF_DIRECTORY_ENTRIES:
        raise PeError("NumberOfRvaAndSizes must be 16")
    if subsystem != IMAGE_SUBSYSTEM_WINDOWS_GUI:
        raise PeError(f"subsystem {subsystem} is not WINDOWS_GUI")
    if dll_characteristics & REQUIRED_DLL_CHARACTERISTICS != REQUIRED_DLL_CHARACTERISTICS:
        raise PeError("DYNAMIC_BASE and NX_COMPAT are required")
    extra = dll_characteristics & ~REQUIRED_DLL_CHARACTERISTICS
    if extra & ~ALLOWED_EXTRA_DLL_CHARACTERISTICS:
        raise PeError(f"unexpected DllCharacteristics bits 0x{dll_characteristics:x}")

    directories: list[DataDirectory] = []
    dir_off = optional + 0x70
    for index in range(IMAGE_NUMBEROF_DIRECTORY_ENTRIES):
        item_off = _checked_add(dir_off, _checked_mul(index, DATA_DIRECTORY_SIZE, limit=UINT32_MAX))
        directories.append(
            DataDirectory(index=index, rva=_u32(data, item_off), size=_u32(data, item_off + 4))
        )

    section_off = _checked_add(optional, OPTIONAL_HEADER64_SIZE, limit=len(data))
    header_end = _checked_add(
        section_off,
        _checked_mul(nsections, SECTION_HEADER_SIZE, limit=UINT32_MAX),
        limit=len(data),
    )
    if header_end > size_of_headers:
        raise PeError("section headers exceed SizeOfHeaders")

    sections: list[Section] = []
    raw_ranges: list[tuple[int, int]] = []
    va_ranges: list[tuple[int, int]] = []
    last_raw_end = size_of_headers
    for index in range(nsections):
        off = _checked_add(section_off, _checked_mul(index, SECTION_HEADER_SIZE, limit=UINT32_MAX))
        raw_name = _slice(data, off, 8)
        name = raw_name.split(b"\x00", 1)[0].decode("ascii", errors="strict")
        section = Section(
            name=name,
            virtual_size=_u32(data, off + 8),
            virtual_address=_u32(data, off + 12),
            size_of_raw_data=_u32(data, off + 16),
            pointer_to_raw_data=_u32(data, off + 20),
            characteristics=_u32(data, off + 36),
        )
        if section.virtual_address == 0 or section.virtual_address % section_alignment != 0:
            raise PeError(f"section {name!r} VirtualAddress is unaligned")
        va_end = _checked_add(section.virtual_address, max(section.virtual_size, 1), limit=UINT32_MAX)
        va_ranges.append((section.virtual_address, va_end))
        if section.size_of_raw_data:
            if section.pointer_to_raw_data == 0 or section.pointer_to_raw_data % file_alignment != 0:
                raise PeError(f"section {name!r} PointerToRawData is unaligned")
            raw_end = _checked_add(
                section.pointer_to_raw_data, section.size_of_raw_data, limit=len(data)
            )
            if section.pointer_to_raw_data < size_of_headers:
                raise PeError(f"section {name!r} raw data overlaps headers")
            raw_ranges.append((section.pointer_to_raw_data, raw_end))
            last_raw_end = max(last_raw_end, raw_end)
        sections.append(section)
    parse_elf_style_ranges(raw_ranges, "section raw")
    parse_elf_style_ranges(va_ranges, "section VA")
    if last_raw_end != len(data):
        if last_raw_end > len(data):
            raise PeError("section raw data extends past the file")
        trailing = data[last_raw_end:]
        if any(trailing):
            raise PeError("unexpected non-zero overlay/trailing data")
        raise PeError("unexpected overlay/trailing data after last section")

    _require_empty_directory(directories, DIR_SECURITY, "Authenticode/certificate")
    _require_debug_directory(data, sections, directories[DIR_DEBUG])
    _require_empty_directory(directories, DIR_ARCHITECTURE, "architecture")
    _require_empty_directory(directories, DIR_GLOBALPTR, "global pointer")
    _require_empty_directory(directories, DIR_BOUND_IMPORT, "bound import")
    _require_empty_directory(directories, DIR_DELAY_IMPORT, "delay-load import")
    _require_empty_directory(directories, DIR_CLR, "CLR")
    if directories[DIR_RESERVED].rva or directories[DIR_RESERVED].size:
        raise PeError("reserved data directory must be empty")

    exports = _parse_exports(data, sections, directories[DIR_EXPORT])
    imports = _parse_imports(data, sections, directories[DIR_IMPORT])
    sign = [item for item in exports if item.name == SIGN_SYMBOL]
    if len(sign) != 1:
        raise PeError("required sign export is missing, duplicated, or hidden")
    if sign[0].rva == 0:
        raise PeError("sign export RVA is zero")
    rva_to_offset(sections, sign[0].rva, 1)

    dll_names = [item.name.lower() for item in imports]
    if not dll_names:
        raise PeError("import table is empty")
    if len(dll_names) != len(set(dll_names)):
        raise PeError("duplicate import DLL name")
    unexpected = [name for name in dll_names if name not in ALLOWED_IMPORT_DLLS]
    if unexpected:
        raise PeError(
            f"unexpected import DLL(s): {unexpected}; observed={sorted(dll_names)}"
        )
    for item in imports:
        if not item.functions:
            raise PeError(f"import DLL {item.name} has no named functions")
        if any(not func for func in item.functions):
            raise PeError(f"import DLL {item.name} has an unnamed/ordinal-only import")

    if entry != 0:
        rva_to_offset(sections, entry, 1)

    return PeRecord(
        path="",
        size=len(data),
        machine=machine,
        characteristics=characteristics,
        timestamp=timestamp,
        magic=magic,
        subsystem=subsystem,
        dll_characteristics=dll_characteristics,
        image_base=image_base,
        section_alignment=section_alignment,
        file_alignment=file_alignment,
        size_of_image=size_of_image,
        size_of_headers=size_of_headers,
        number_of_rva_and_sizes=number_of_rva,
        sections=sections,
        directories=directories,
        exports=exports,
        imports=imports,
        sign_exports=sign,
    )


def _parse_exports(
    data: bytes, sections: list[Section], directory: DataDirectory
) -> list[ExportRecord]:
    if directory.rva == 0 or directory.size < EXPORT_DIRECTORY_SIZE:
        raise PeError("export directory is missing")
    off = rva_to_offset(sections, directory.rva, EXPORT_DIRECTORY_SIZE)
    name_rva = _u32(data, off + 12)
    ordinal_base = _u32(data, off + 16)
    nfuncs = _u32(data, off + 20)
    nnames = _u32(data, off + 24)
    funcs_rva = _u32(data, off + 28)
    names_rva = _u32(data, off + 32)
    ords_rva = _u32(data, off + 36)
    if nfuncs == 0 or nnames == 0 or nfuncs > MAX_EXPORTS or nnames > MAX_EXPORTS:
        raise PeError("invalid export counts")
    if nnames > nfuncs:
        raise PeError("NumberOfNames exceeds NumberOfFunctions")
    if ordinal_base == 0:
        raise PeError("export Base is zero")
    dll_name = _ascii_z(data, rva_to_offset(sections, name_rva, 1))
    if dll_name.lower() != STABLE_DLL_NAME.lower():
        raise PeError(f"export DLL name {dll_name!r} != {STABLE_DLL_NAME!r}")
    func_off = rva_to_offset(sections, funcs_rva, _checked_mul(nfuncs, 4, limit=UINT32_MAX))
    name_off = rva_to_offset(sections, names_rva, _checked_mul(nnames, 4, limit=UINT32_MAX))
    ord_off = rva_to_offset(sections, ords_rva, _checked_mul(nnames, 2, limit=UINT32_MAX))
    seen_names: set[str] = set()
    seen_ordinals: set[int] = set()
    exports: list[ExportRecord] = []
    for index in range(nnames):
        export_name_rva = _u32(data, _checked_add(name_off, _checked_mul(index, 4, limit=UINT32_MAX)))
        name_index = _u16(data, _checked_add(ord_off, _checked_mul(index, 2, limit=UINT32_MAX)))
        if name_index >= nfuncs:
            raise PeError("export name ordinal is out of range")
        func_rva = _u32(data, _checked_add(func_off, _checked_mul(name_index, 4, limit=UINT32_MAX)))
        name = _ascii_z(data, rva_to_offset(sections, export_name_rva, 1))
        if not name or name in seen_names:
            raise PeError("export name is empty or duplicated")
        ordinal = _checked_add(ordinal_base, name_index, limit=UINT32_MAX)
        if ordinal in seen_ordinals:
            raise PeError("export ordinal is duplicated")
        seen_names.add(name)
        seen_ordinals.add(ordinal)
        if func_rva == 0:
            raise PeError(f"export {name} has a zero RVA")
        exports.append(ExportRecord(name=name, ordinal=ordinal, rva=func_rva))
    return exports


def _parse_imports(
    data: bytes, sections: list[Section], directory: DataDirectory
) -> list[ImportDll]:
    if directory.rva == 0 or directory.size < IMPORT_DESCRIPTOR_SIZE:
        raise PeError("import directory is missing")
    imports: list[ImportDll] = []
    for index in range(MAX_IMPORT_DLLS + 1):
        desc_rva = _checked_add(
            directory.rva, _checked_mul(index, IMPORT_DESCRIPTOR_SIZE, limit=UINT32_MAX)
        )
        off = rva_to_offset(sections, desc_rva, IMPORT_DESCRIPTOR_SIZE)
        raw = _slice(data, off, IMPORT_DESCRIPTOR_SIZE)
        if raw == b"\x00" * IMPORT_DESCRIPTOR_SIZE:
            break
        if index == MAX_IMPORT_DLLS:
            raise PeError("too many import descriptors")
        ilt_rva = _u32(data, off)
        name_rva = _u32(data, off + 12)
        iat_rva = _u32(data, off + 16)
        if name_rva == 0:
            raise PeError("import descriptor Name RVA is zero")
        dll_name = _ascii_z(data, rva_to_offset(sections, name_rva, 1)).lower()
        if not dll_name.endswith(".dll"):
            raise PeError(f"import name {dll_name!r} is not a DLL")
        thunk_rva = ilt_rva or iat_rva
        if thunk_rva == 0:
            raise PeError(f"import {dll_name} has no ILT/IAT")
        functions = _parse_thunks(data, sections, thunk_rva)
        imports.append(ImportDll(name=dll_name, functions=functions))
    else:
        raise PeError("import directory is not terminated")
    return imports


def _parse_thunks(data: bytes, sections: list[Section], thunk_rva: int) -> list[str]:
    names: list[str] = []
    for index in range(MAX_IMPORT_NAMES + 1):
        item_rva = _checked_add(thunk_rva, _checked_mul(index, 8, limit=UINT32_MAX))
        off = rva_to_offset(sections, item_rva, 8)
        value = _u64(data, off)
        if value == 0:
            break
        if index == MAX_IMPORT_NAMES:
            raise PeError("too many import thunks")
        if value & (1 << 63):
            raise PeError("ordinal-only import is not allowed")
        name_rva = value & ((1 << 63) - 1)
        if name_rva > UINT32_MAX:
            raise PeError("import-by-name RVA exceeds 32 bits")
        # IMAGE_IMPORT_BY_NAME: Hint (2) + name
        name_off = rva_to_offset(sections, name_rva, 3)
        names.append(_ascii_z(data, name_off + 2))
    else:
        raise PeError("import thunks are not terminated")
    return names


def _is_allowed_remap(path: str) -> bool:
    for prefix in ALLOWED_REMAP_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def scan_windows_forbidden_paths(
    data: bytes, extra_forbidden_roots: tuple[bytes, ...] = ()
) -> list[str]:
    hits: list[str] = []
    for marker in FORBIDDEN_DEBUG_MARKERS:
        if marker in data:
            display = marker.decode("ascii", errors="replace")
            if display not in hits:
                hits.append(display)
    roots = FORBIDDEN_BUILD_ROOTS + extra_forbidden_roots
    for root in roots:
        start = 0
        while True:
            index = data.find(root, start)
            if index < 0:
                break
            end = index
            while end < len(data) and end - index < MAX_PATH_CANDIDATE:
                byte = data[end]
                if byte < 32:
                    break
                end += 1
            fragment = data[index:end].decode("ascii", errors="replace")[:MAX_PATH_DISPLAY]
            if fragment and fragment not in hits:
                hits.append(fragment)
            start = index + 1
    # Slash-byte pass: a '/' starts a path only after a stop byte or BOF.
    start = 0
    while True:
        index = data.find(b"/", start)
        if index < 0:
            break
        prev = data[index - 1] if index else 0
        if index and prev >= 32 and prev not in {0x20, ord("\\")}:
            start = index + 1
            continue
        end = index
        while end < len(data) and end - index < MAX_PATH_CANDIDATE:
            byte = data[end]
            if byte < 32 or byte in {0x20, ord("\\")}:
                break
            end += 1
        try:
            candidate = data[index:end].decode("ascii")
        except UnicodeDecodeError:
            raw = data[index:end]
            # Binary `/` plus non-ASCII is not a path unless it contains a
            # documented build root or a later `/` (absolute-looking).
            if any(root in raw for root in roots) or b"/" in raw[1:]:
                display = raw.decode("ascii", errors="replace")[:MAX_PATH_DISPLAY]
                if display not in hits:
                    hits.append(display)
            start = index + 1
            continue
        if len(candidate) >= 2 and not _is_allowed_remap(candidate):
            if candidate[1:2].isalpha() and candidate not in hits:
                # "/letter..." without a later slash is not treated as a path.
                if "/" in candidate[1:]:
                    hits.append(candidate[:MAX_PATH_DISPLAY])
        start = index + 1
    return hits


def build_forbidden_roots(*paths: Path) -> tuple[bytes, ...]:
    roots: list[bytes] = []
    for path in paths:
        text = str(path)
        if text:
            roots.append(text.encode("utf-8", errors="replace"))
            roots.append(text.replace("/", "\\").encode("utf-8", errors="replace"))
            roots.append(text.replace("\\", "/").encode("utf-8", errors="replace"))
    return tuple(dict.fromkeys(roots))


def find_dumpbin() -> str | None:
    for name in ("dumpbin", "dumpbin.exe"):
        found = shutil.which(name)
        if found:
            return found
    vswhere = shutil.which("vswhere") or (
        r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    )
    if Path(vswhere).is_file():
        completed = subprocess.run(
            [
                vswhere,
                "-latest",
                "-products",
                "*",
                "-find",
                r"**\Hostx64\x64\dumpbin.exe",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
        if completed.returncode == 0 and lines and Path(lines[-1]).is_file():
            return lines[-1]
    matches = sorted(
        glob.glob(
            r"C:\Program Files\Microsoft Visual Studio\2022\*\VC\Tools\MSVC\*\bin\Hostx64\x64\dumpbin.exe"
        )
    )
    return matches[-1] if matches else None


def parse_dumpbin_exports(text: str) -> list[str]:
    names = DUMPBIN_EXPORT_RE.findall(text)
    if not names:
        raise PeError("dumpbin /EXPORTS listed no names")
    return names


def parse_dumpbin_dependents(text: str) -> list[str]:
    return [item.lower() for item in DUMPBIN_DEPENDENT_RE.findall(text)]


def require_dumpbin_corroboration(record: PeRecord, text: str) -> None:
    if not DUMPBIN_MACHINE_RE.search(text):
        raise PeError("dumpbin headers do not report 8664 machine (x64)")
    if not DUMPBIN_PE32PLUS_RE.search(text):
        raise PeError("dumpbin headers do not report PE32+")
    if not DUMPBIN_DLL_RE.search(text):
        raise PeError("dumpbin headers do not report DLL")
    if "delay" in text.lower() and "delay load" in text.lower():
        raise PeError("dumpbin reports delay-load imports")
    exports = parse_dumpbin_exports(text)
    sign_hits = [name for name in exports if name == SIGN_SYMBOL]
    if len(sign_hits) != 1:
        raise PeError("dumpbin sign export is missing, duplicated, or renamed")
    if any(name != SIGN_SYMBOL and name == sign_hits[0] for name in exports):
        raise PeError("dumpbin sign export is not unique")
    parsed_names = {item.name for item in record.exports}
    if SIGN_SYMBOL not in parsed_names:
        raise PeError("parser/dumpbin sign export mismatch")
    dependents = parse_dumpbin_dependents(text)
    if not dependents:
        raise PeError("dumpbin /DEPENDENTS listed no DLLs")
    parsed_dlls = {item.name.lower() for item in record.imports}
    extra = [name for name in dependents if name not in parsed_dlls]
    missing = [name for name in parsed_dlls if name not in set(dependents)]
    if extra or missing:
        raise PeError(
            f"dumpbin dependents {dependents} != parsed imports {sorted(parsed_dlls)}"
        )
    unexpected = [name for name in dependents if name not in ALLOWED_IMPORT_DLLS]
    if unexpected:
        raise PeError(f"dumpbin unexpected dependents: {unexpected}")


def run_dumpbin(path: Path, dumpbin: str) -> str:
    completed = subprocess.run(
        [dumpbin, "/HEADERS", "/EXPORTS", "/IMPORTS", "/DEPENDENTS", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    text = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if completed.returncode != 0:
        raise PeError(f"dumpbin exited {completed.returncode}")
    return text


def verify_windows_x86_64_dll(
    path: Path,
    *,
    require_tools: bool = False,
    dumpbin: str | None = None,
    extra_forbidden_roots: tuple[bytes, ...] = (),
    expected_resource_prefix: str = JNA_RESOURCE_PREFIX,
) -> PeRecord:
    if expected_resource_prefix != JNA_RESOURCE_PREFIX:
        raise PeError(
            f"resource prefix {expected_resource_prefix!r} != {JNA_RESOURCE_PREFIX!r} "
            "(Windows ARM is out of scope)"
        )
    if path.name != STABLE_DLL_NAME:
        raise PeError(f"filename {path.name!r} != {STABLE_DLL_NAME!r}")
    data = path.read_bytes()
    record = parse_pe32_plus_x86_64_dll(data)
    record.path = str(path)
    record.forbidden_paths = scan_windows_forbidden_paths(data, extra_forbidden_roots)
    if record.forbidden_paths:
        raise PeError("forbidden path/PDB/debug bytes: " + "; ".join(record.forbidden_paths[:8]))
    if require_tools:
        tool = dumpbin or find_dumpbin()
        if tool is None:
            raise PeError("dumpbin is required and was not found")
        record.dumpbin_text = run_dumpbin(path, tool)
        record.dumpbin_returncode = 0
        require_dumpbin_corroboration(record, record.dumpbin_text)
    return record
