"""Adversarial tests for the Linux x86-64 ELF64 cdylib verifier."""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import linux_elf_verify as elf  # noqa: E402

SIGN = elf.SIGN_SYMBOL
SONAME = elf.STABLE_SONAME
LIBC = "libc.so.6"


def _pad4(payload: bytes) -> bytes:
    return payload + b"\x00" * ((4 - (len(payload) % 4)) % 4)


def build_elf(
    *,
    ei_class: int = elf.ELFCLASS64,
    ei_data: int = elf.ELFDATA2LSB,
    e_type: int = elf.ET_DYN,
    e_machine: int = elf.EM_X86_64,
    needed: tuple[str, ...] = (LIBC,),
    soname: str = SONAME,
    symbol: str = SIGN,
    rpath: str | None = None,
    runpath: str | None = None,
    debug_section: str | None = None,
    build_id: bytes | None = None,
    truncate: int | None = None,
    skip_soname: bool = False,
    skip_symbol: bool = False,
    extra_symbol: str | None = None,
    shnum_override: int | None = None,
) -> bytes:
    """Minimal ELF64 LE ET_DYN with PT_LOAD + PT_DYNAMIC + sections."""
    dynstr_entries = [b"\x00"]
    offsets: dict[str, int] = {}

    def add_str(text: str) -> int:
        if text in offsets:
            return offsets[text]
        off = sum(len(item) for item in dynstr_entries)
        dynstr_entries.append(text.encode("utf-8") + b"\x00")
        offsets[text] = off
        return off

    needed_offs = [add_str(name) for name in needed]
    soname_off = None if skip_soname else add_str(soname)
    symbol_off = add_str(symbol)
    extra_off = add_str(extra_symbol) if extra_symbol else None
    rpath_off = add_str(rpath) if rpath else None
    runpath_off = add_str(runpath) if runpath else None
    dynstr = b"".join(dynstr_entries)

    dyn_tags: list[tuple[int, int]] = []
    # Placeholder vaddrs filled after layout.
    dyn_tags.append((elf.DT_STRTAB, 0))
    dyn_tags.append((elf.DT_STRSZ, len(dynstr)))
    dyn_tags.append((elf.DT_SYMTAB, 0))
    dyn_tags.append((elf.DT_SYMENT, elf.ELF64_SYM_SIZE))
    for off in needed_offs:
        dyn_tags.append((elf.DT_NEEDED, off))
    if soname_off is not None:
        dyn_tags.append((elf.DT_SONAME, soname_off))
    if rpath_off is not None:
        dyn_tags.append((elf.DT_RPATH, rpath_off))
    if runpath_off is not None:
        dyn_tags.append((elf.DT_RUNPATH, runpath_off))
    dyn_tags.append((elf.DT_NULL, 0))
    dynamic = b"".join(struct.pack("<qQ", tag, value) for tag, value in dyn_tags)

    # null + defined sign symbol (+ optional extra)
    symbols = [struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0)]
    if not skip_symbol:
        symbols.append(struct.pack("<IBBHQQ", symbol_off, (1 << 4) | 2, 0, 1, 0x1000, 16))
    if extra_off is not None:
        symbols.append(struct.pack("<IBBHQQ", extra_off, (1 << 4) | 2, 0, 1, 0x1010, 8))
    dynsym = b"".join(symbols)

    shstr_names = [b"\x00", b".dynstr\x00", b".dynamic\x00", b".dynsym\x00", b".shstrtab\x00"]
    if debug_section:
        shstr_names.append(debug_section.encode("utf-8") + b"\x00")
    if build_id is not None:
        shstr_names.append(b".note.gnu.build-id\x00")
    shstrtab = b"".join(shstr_names)

    def shstr_off(name: bytes) -> int:
        return shstrtab.index(name)

    note = b""
    if build_id is not None:
        name = b"GNU\x00"
        note = struct.pack("<III", len(name), len(build_id), elf.NT_GNU_BUILD_ID) + _pad4(name) + _pad4(build_id)

    # Layout after header + 2 or 3 phdrs.
    phnum = 3 if note else 2
    cursor = elf.ELF64_EHDR_SIZE + phnum * elf.ELF64_PHDR_SIZE
    dynstr_off = cursor
    cursor += len(dynstr)
    dynamic_off = cursor
    cursor += len(dynamic)
    dynsym_off = cursor
    cursor += len(dynsym)
    note_off = cursor
    cursor += len(note)
    shstr_off_file = cursor
    cursor += len(shstrtab)
    shoff = cursor

    # Patch DT_STRTAB / DT_SYMTAB to file offsets (vaddr == offset).
    patched = []
    for tag, value in dyn_tags:
        if tag == elf.DT_STRTAB:
            value = dynstr_off
        elif tag == elf.DT_SYMTAB:
            value = dynsym_off
        patched.append(struct.pack("<qQ", tag, value))
    dynamic = b"".join(patched)

    shnum = 5 + (1 if debug_section else 0) + (1 if note else 0)
    if shnum_override is not None:
        shnum = shnum_override
    shstrndx = 4
    load_filesz = shoff + shnum * elf.ELF64_SHDR_SIZE

    ehdr = bytearray(elf.ELF64_EHDR_SIZE)
    ehdr[0:4] = elf.ELFMAG
    ehdr[elf.EI_CLASS] = ei_class
    ehdr[elf.EI_DATA] = ei_data
    ehdr[elf.EI_VERSION] = elf.EV_CURRENT
    struct.pack_into(
        "<HHIQQQIHHHHHH",
        ehdr,
        16,
        e_type,
        e_machine,
        1,
        0,
        elf.ELF64_EHDR_SIZE,
        shoff,
        0,
        elf.ELF64_EHDR_SIZE,
        elf.ELF64_PHDR_SIZE,
        phnum,
        elf.ELF64_SHDR_SIZE,
        shnum,
        shstrndx,
    )

    def phdr(p_type: int, offset: int, size: int, flags: int = 4) -> bytes:
        return struct.pack("<IIQQQQQQ", p_type, flags, offset, offset, offset, size, size, 1)

    phdrs = phdr(elf.PT_LOAD, 0, load_filesz, 5) + phdr(elf.PT_DYNAMIC, dynamic_off, len(dynamic), 4)
    if note:
        phdrs += phdr(elf.PT_NOTE, note_off, len(note), 4)

    def shdr(name: bytes, sh_type: int, offset: int, size: int, entsize: int = 0, link: int = 0) -> bytes:
        return struct.pack(
            "<IIQQQQIIQQ",
            shstr_off(name),
            sh_type,
            0,
            offset,
            offset,
            size,
            link,
            0,
            1,
            entsize,
        )

    sections = [
        struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        shdr(b".dynstr\x00", 3, dynstr_off, len(dynstr)),
        shdr(b".dynamic\x00", 6, dynamic_off, len(dynamic), elf.ELF64_DYN_SIZE, 1),
        shdr(b".dynsym\x00", 11, dynsym_off, len(dynsym), elf.ELF64_SYM_SIZE, 1),
        shdr(b".shstrtab\x00", 3, shstr_off_file, len(shstrtab)),
    ]
    if debug_section:
        sections.append(shdr(debug_section.encode("utf-8") + b"\x00", 1, 0, 0))
    if note:
        sections.append(shdr(b".note.gnu.build-id\x00", elf.SHT_NOTE, note_off, len(note)))

    blob = bytes(ehdr) + phdrs + dynstr + dynamic + dynsym + note + shstrtab + b"".join(sections)
    if truncate is not None:
        return blob[:truncate]
    return blob


class LinuxElfVerifyTests(unittest.TestCase):
    def test_accepted_libsystem_equivalent_fixture(self) -> None:
        record = elf.parse_elf64_le_x86_64_dso(build_elf())
        self.assertEqual(record.soname, SONAME)
        self.assertEqual(record.needed, [LIBC])
        self.assertIn(SIGN, record.symbols)

    def test_wrong_class_endian_machine_type_are_rejected(self) -> None:
        cases = (
            (dict(ei_class=1), "ELFCLASS64"),
            (dict(ei_data=2), "ELFDATA2LSB"),
            (dict(e_machine=3), "EM_X86_64"),
            (dict(e_machine=elf.EM_AARCH64), "EM_AARCH64"),
            (dict(e_type=2), "ET_DYN"),
        )
        for kwargs, needle in cases:
            with self.subTest(needle):
                with self.assertRaisesRegex(elf.ElfError, needle):
                    elf.parse_elf64_le_x86_64_dso(build_elf(**kwargs))

    def test_missing_and_extra_symbol_policy(self) -> None:
        with self.assertRaisesRegex(elf.ElfError, "not exported"):
            elf.parse_elf64_le_x86_64_dso(build_elf(skip_symbol=True))
        record = elf.parse_elf64_le_x86_64_dso(build_elf(extra_symbol="other_fn"))
        self.assertIn(SIGN, record.symbols)
        self.assertIn("other_fn", record.symbols)

    def test_unexpected_dependency_and_rpath_are_rejected(self) -> None:
        with self.assertRaisesRegex(elf.ElfError, "unexpected DT_NEEDED"):
            elf.parse_elf64_le_x86_64_dso(build_elf(needed=(LIBC, "libevil.so.1")))
        with self.assertRaisesRegex(elf.ElfError, "DT_RPATH"):
            elf.parse_elf64_le_x86_64_dso(build_elf(rpath="/tmp/evil"))
        with self.assertRaisesRegex(elf.ElfError, "DT_RUNPATH"):
            elf.parse_elf64_le_x86_64_dso(build_elf(runpath="/opt/host"))

    def test_wrong_soname_is_rejected(self) -> None:
        with self.assertRaisesRegex(elf.ElfError, "DT_SONAME"):
            elf.parse_elf64_le_x86_64_dso(build_elf(soname="libother.so"))
        with self.assertRaisesRegex(elf.ElfError, "DT_SONAME is missing"):
            elf.parse_elf64_le_x86_64_dso(build_elf(skip_soname=True))

    def test_debug_section_and_build_id_are_rejected(self) -> None:
        with self.assertRaisesRegex(elf.ElfError, "debug section"):
            elf.parse_elf64_le_x86_64_dso(build_elf(debug_section=".debug_info"))
        with self.assertRaisesRegex(elf.ElfError, "NT_GNU_BUILD_ID"):
            elf.parse_elf64_le_x86_64_dso(build_elf(build_id=b"\x11" * 16))

    def test_truncated_and_malformed_headers_are_rejected(self) -> None:
        with self.assertRaisesRegex(elf.ElfError, "truncated ELF header"):
            elf.parse_elf64_le_x86_64_dso(build_elf(truncate=20))
        with self.assertRaisesRegex(elf.ElfError, "missing ELF magic"):
            elf.parse_elf64_le_x86_64_dso(b"not-elf" + b"\x00" * 80)
        with self.assertRaisesRegex(elf.ElfError, "e_shnum"):
            elf.parse_elf64_le_x86_64_dso(build_elf(shnum_override=0))

    def test_missing_libc_is_rejected(self) -> None:
        with self.assertRaisesRegex(elf.ElfError, "missing required DT_NEEDED"):
            elf.parse_elf64_le_x86_64_dso(build_elf(needed=("libgcc_s.so.1",)))

    def test_verify_path_round_trip_without_host_tools(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        path = root / SONAME
        path.write_bytes(build_elf())
        record = elf.verify_linux_x86_64_cdylib(path, require_tools=False, readelf=None, nm=None)
        self.assertEqual(record.soname, SONAME)
        self.assertEqual(path.read_bytes(), build_elf())
