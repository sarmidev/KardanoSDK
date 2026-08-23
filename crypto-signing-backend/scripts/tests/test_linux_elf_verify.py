"""Adversarial tests for the Linux x86-64 ELF64 cdylib verifier."""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    e_version: int = elf.EV_CURRENT,
    needed: tuple[str, ...] = (LIBC,),
    soname: str = SONAME,
    symbol: str = SIGN,
    symbol_bind: int = elf.STB_GLOBAL,
    symbol_type: int = elf.STT_FUNC,
    symbol_vis: int = elf.STV_DEFAULT,
    symbol_shndx: int = 1,
    symbol_value: int = 0x1000,
    rpath: str | None = None,
    runpath: str | None = None,
    debug_section: str | None = None,
    build_id: bytes | None = None,
    truncate: int | None = None,
    skip_soname: bool = False,
    skip_symbol: bool = False,
    extra_symbol: str | None = None,
    extra_sign: bool = False,
    shnum_override: int | None = None,
    glibc_versions: tuple[str, ...] = ("GLIBC_2.2.5", "GLIBC_2.35"),
    skip_verneed: bool = False,
    duplicate_verneed_tag: bool = False,
    duplicate_strtab: bool = False,
    duplicate_glibc: bool = False,
    verneed_version: int = elf.VER_NEED_CURRENT,
    loader_verneed: bool = False,
    filesz_gt_memsz: bool = False,
    align_mismatch: bool = False,
    section_overflow: bool = False,
    unterminated_dynstr: bool = False,
    embed: bytes = b"",
    skip_verneed_section: bool = False,
    extra_dynamic_section: bool = False,
    extra_verneed_section: bool = False,
    verneed_num_override: int | None = None,
    dynamic_entsize: int | None = None,
    dynamic_link: int | None = None,
    section0_nonzero: bool = False,
    zero_sh_addralign: bool = False,
    alloc_outside_load: bool = False,
    vn_next_final: int | None = None,
    vna_next_final: int | None = None,
    vn_aux: int | None = None,
    vn_next_nonfinal: int | None = None,
    vna_next_nonfinal: int | None = None,
    verneed_cycle: bool = False,
    vernaux_overlap: bool = False,
    skip_versym_tag: bool = False,
    skip_versym_section: bool = False,
    extra_versym_section: bool = False,
    verdef_tag_only: bool = False,
    verdefnum_only: bool = False,
    stray_verdef_section: bool = False,
    include_verdef: bool = False,
    layout: dict | None = None,
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
    version_offs = [add_str(name) for name in glibc_versions]
    loader_name_off = add_str("ld-linux-x86-64.so.2") if loader_verneed else None
    dynstr = b"".join(dynstr_entries)
    if unterminated_dynstr:
        dynstr = dynstr[:-1]

    dyn_tags: list[tuple[int, int]] = []
    dyn_tags.append((elf.DT_STRTAB, 0))
    if duplicate_strtab:
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
    verneed_num = (
        verneed_num_override
        if verneed_num_override is not None
        else (2 if loader_verneed else 1)
    )
    if not skip_verneed and version_offs:
        dyn_tags.append((elf.DT_VERNEED, 0))
        if duplicate_verneed_tag:
            dyn_tags.append((elf.DT_VERNEED, 0))
        dyn_tags.append((elf.DT_VERNEEDNUM, verneed_num))
        if not skip_versym_tag:
            dyn_tags.append((elf.DT_VERSYM, 0))
    if include_verdef:
        dyn_tags.append((elf.DT_VERDEF, 0))
        dyn_tags.append((elf.DT_VERDEFNUM, 1))
    elif verdef_tag_only:
        dyn_tags.append((elf.DT_VERDEF, 0))
    elif verdefnum_only:
        dyn_tags.append((elf.DT_VERDEFNUM, 1))
    dyn_tags.append((elf.DT_NULL, 0))
    dynamic = b"".join(struct.pack("<qQ", tag, value) for tag, value in dyn_tags)

    def pack_sym(name_off: int, bind: int, typ: int, vis: int, shndx: int, value: int) -> bytes:
        return struct.pack("<IBBHQQ", name_off, (bind << 4) | typ, vis, shndx, value, 16)

    symbols = [struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0)]
    if not skip_symbol:
        symbols.append(
            pack_sym(symbol_off, symbol_bind, symbol_type, symbol_vis, symbol_shndx, symbol_value)
        )
        if extra_sign:
            symbols.append(
                pack_sym(symbol_off, elf.STB_GLOBAL, elf.STT_FUNC, elf.STV_DEFAULT, 1, 0x2000)
            )
    if extra_off is not None:
        symbols.append(pack_sym(extra_off, elf.STB_GLOBAL, elf.STT_FUNC, elf.STV_DEFAULT, 1, 0x1010))
    dynsym = b"".join(symbols)

    aux_names = list(version_offs)
    if duplicate_glibc and aux_names:
        aux_names.append(aux_names[0])
    verneed = b""
    if not skip_verneed and aux_names:
        libc_off = offsets.get(LIBC, add_str(LIBC))
        aux_blob = b""
        for index, name_off in enumerate(aux_names):
            nxt = elf.ELF64_VERNAUX_SIZE if index + 1 < len(aux_names) else 0
            aux_blob += struct.pack("<IHHII", 0, 0, index + 2, name_off, nxt)
        first_next = (
            elf.ELF64_VERNEED_SIZE + len(aux_blob) if loader_verneed else 0
        )
        verneed = (
            struct.pack(
                "<HHIII",
                verneed_version,
                len(aux_names),
                libc_off,
                elf.ELF64_VERNEED_SIZE,
                first_next,
            )
            + aux_blob
        )
        if loader_verneed:
            shared = version_offs[0]
            verneed += struct.pack(
                "<HHIII",
                verneed_version,
                1,
                loader_name_off,
                elf.ELF64_VERNEED_SIZE,
                0,
            ) + struct.pack("<IHHII", 0, 0, 9, shared, 0)
        buf = bytearray(verneed)
        if vn_aux is not None:
            struct.pack_into("<I", buf, 8, vn_aux)
        if vn_next_final is not None:
            last = 0 if not loader_verneed else (
                elf.ELF64_VERNEED_SIZE + len(aux_blob)
            )
            struct.pack_into("<I", buf, last + 12, vn_next_final)
        if vn_next_nonfinal is not None and loader_verneed:
            struct.pack_into("<I", buf, 12, vn_next_nonfinal)
        if vna_next_final is not None:
            last_aux = elf.ELF64_VERNEED_SIZE + (len(aux_names) - 1) * elf.ELF64_VERNAUX_SIZE
            struct.pack_into("<I", buf, last_aux + 12, vna_next_final)
        if vna_next_nonfinal is not None and len(aux_names) > 1:
            struct.pack_into("<I", buf, elf.ELF64_VERNEED_SIZE + 12, vna_next_nonfinal)
        if verneed_cycle and loader_verneed:
            second = elf.ELF64_VERNEED_SIZE + len(aux_blob)
            struct.pack_into("<I", buf, second + 12, 4)
        if vernaux_overlap and len(aux_names) > 1:
            struct.pack_into("<I", buf, elf.ELF64_VERNEED_SIZE + 12, 4)
        verneed = bytes(buf)

    verdef = b""
    if include_verdef:
        name_off = soname_off if soname_off is not None else offsets.get(soname, 0)
        verdef = struct.pack("<HHHHIII", 1, 0, 1, 1, 0, elf.ELF64_VERDEF_SIZE, 0) + struct.pack(
            "<II", name_off, 0
        )

    shstr_names = [b"\x00", b".dynstr\x00", b".dynamic\x00", b".dynsym\x00", b".shstrtab\x00"]
    if debug_section:
        shstr_names.append(debug_section.encode("utf-8") + b"\x00")
    if build_id is not None:
        shstr_names.append(b".note.gnu.build-id\x00")
    if embed:
        shstr_names.append(b".comment\x00")
    if not skip_verneed and version_offs and not skip_verneed_section:
        shstr_names.append(b".gnu.version_r\x00")
    if extra_dynamic_section:
        shstr_names.append(b".dynamic2\x00")
    if extra_verneed_section:
        shstr_names.append(b".gnu.version_r2\x00")
    have_versym_section = bool(
        not skip_verneed and version_offs and not skip_versym_section and not skip_versym_tag
    )
    if have_versym_section:
        shstr_names.append(b".gnu.version\x00")
    if extra_versym_section:
        shstr_names.append(b".gnu.version2\x00")
    have_verdef_section = bool(include_verdef or stray_verdef_section)
    if have_verdef_section:
        shstr_names.append(b".gnu.version_d\x00")
    if alloc_outside_load:
        shstr_names.append(b".outside\x00")
    shstrtab = b"".join(shstr_names)

    def shstr_off(name: bytes) -> int:
        return shstrtab.index(name)

    note = b""
    if build_id is not None:
        name = b"GNU\x00"
        note = (
            struct.pack("<III", len(name), len(build_id), elf.NT_GNU_BUILD_ID)
            + _pad4(name)
            + _pad4(build_id)
        )

    phnum = 3 if note else 2
    cursor = elf.ELF64_EHDR_SIZE + phnum * elf.ELF64_PHDR_SIZE
    dynstr_off = cursor
    cursor += len(dynstr)
    dynamic_off = cursor
    cursor += len(dynamic)
    dynsym_off = cursor
    cursor += len(dynsym)
    symbol_count = len(dynsym) // elf.ELF64_SYM_SIZE
    versym = b"\x00\x00" * symbol_count if have_versym_section else b""
    versym_off = cursor
    cursor += len(versym)
    verdef_pad = b"\x00" * ((4 - (cursor % 4)) % 4)
    cursor += len(verdef_pad)
    verdef_off = cursor
    cursor += len(verdef)
    verneed_pad = b"\x00" * ((4 - (cursor % 4)) % 4)
    cursor += len(verneed_pad)
    verneed_off = cursor
    cursor += len(verneed)
    note_off = cursor
    cursor += len(note)
    embed_off = cursor
    cursor += len(embed)
    shstr_off_file = cursor
    cursor += len(shstrtab)
    shoff = cursor

    patched = []
    for tag, value in dyn_tags:
        if tag == elf.DT_STRTAB:
            value = dynstr_off
        elif tag == elf.DT_SYMTAB:
            value = dynsym_off
        elif tag == elf.DT_VERNEED:
            value = verneed_off
        elif tag == elf.DT_VERSYM:
            value = versym_off
        elif tag == elf.DT_VERDEF:
            value = verdef_off
        patched.append(struct.pack("<qQ", tag, value))
    dynamic = b"".join(patched)

    have_verneed_section = bool(not skip_verneed and version_offs and not skip_verneed_section)
    shnum = 5
    shnum += 1 if have_versym_section else 0
    shnum += 1 if have_verneed_section else 0
    shnum += 1 if have_verdef_section else 0
    shnum += 1 if extra_versym_section else 0
    shnum += 1 if debug_section else 0
    shnum += 1 if note else 0
    shnum += 1 if embed or section_overflow else 0
    shnum += 1 if extra_dynamic_section else 0
    shnum += 1 if extra_verneed_section else 0
    shnum += 1 if alloc_outside_load else 0
    if shnum_override is not None:
        shnum = shnum_override
    shstrndx = 4
    load_filesz = shoff + shnum * elf.ELF64_SHDR_SIZE
    load_memsz = load_filesz - 1 if filesz_gt_memsz else load_filesz

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
        e_version,
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

    def phdr(p_type: int, offset: int, filesz: int, memsz: int, flags: int = 4, align: int = 1) -> bytes:
        if align_mismatch and p_type == elf.PT_LOAD:
            align = 4096
            vaddr = offset + 1
        else:
            vaddr = offset
        return struct.pack("<IIQQQQQQ", p_type, flags, offset, vaddr, offset, filesz, memsz, align)

    phdrs = phdr(elf.PT_LOAD, 0, load_filesz, load_memsz, 5, 1) + phdr(
        elf.PT_DYNAMIC, dynamic_off, len(dynamic), len(dynamic), 4, 1
    )
    if note:
        phdrs += phdr(elf.PT_NOTE, note_off, len(note), len(note), 4, 1)

    def shdr(
        name: bytes,
        sh_type: int,
        offset: int,
        size: int,
        entsize: int = 0,
        link: int = 0,
        flags: int = 0,
        addr: int | None = None,
        align: int = 1,
        info: int = 0,
    ) -> bytes:
        if addr is None:
            addr = offset if flags & elf.SHF_ALLOC else 0
        return struct.pack(
            "<IIQQQQIIQQ",
            shstr_off(name),
            sh_type,
            flags,
            addr,
            offset,
            size,
            link,
            info,
            align,
            entsize,
        )

    comment_size = len(embed)
    if section_overflow:
        comment_size = 0xFFFFFFF0
    section0 = struct.pack("<IIQQQQIIQQ", 0, 1 if section0_nonzero else 0, 0, 0, 0, 0, 0, 0, 0, 0)
    dynstr_align = 0 if zero_sh_addralign else 1
    dyn_entsize = elf.ELF64_DYN_SIZE if dynamic_entsize is None else dynamic_entsize
    dyn_link = 1 if dynamic_link is None else dynamic_link
    sections = [
        section0,
        shdr(
            b".dynstr\x00",
            elf.SHT_STRTAB,
            dynstr_off,
            len(dynstr),
            flags=elf.SHF_ALLOC,
            align=dynstr_align,
        ),
        shdr(
            b".dynamic\x00",
            elf.SHT_DYNAMIC,
            dynamic_off,
            len(dynamic),
            dyn_entsize,
            dyn_link,
            flags=elf.SHF_ALLOC,
        ),
        shdr(
            b".dynsym\x00",
            elf.SHT_DYNSYM,
            dynsym_off,
            len(dynsym),
            elf.ELF64_SYM_SIZE,
            1,
            flags=elf.SHF_ALLOC,
        ),
        shdr(b".shstrtab\x00", elf.SHT_STRTAB, shstr_off_file, len(shstrtab)),
    ]
    if have_versym_section:
        sections.append(
            shdr(
                b".gnu.version\x00",
                elf.SHT_GNU_VERSYM,
                versym_off,
                len(versym),
                elf.ELF64_VERSYM_SIZE,
                3,
                flags=elf.SHF_ALLOC,
            )
        )
    if have_verneed_section:
        sections.append(
            shdr(
                b".gnu.version_r\x00",
                elf.SHT_GNU_VERNEED,
                verneed_off,
                len(verneed),
                link=1,
                flags=elf.SHF_ALLOC,
                info=verneed_num,
            )
        )
    if have_verdef_section:
        sections.append(
            shdr(
                b".gnu.version_d\x00",
                elf.SHT_GNU_VERDEF,
                verdef_off,
                len(verdef) or 20,
                link=1,
                flags=elf.SHF_ALLOC,
                info=1 if include_verdef else 0,
            )
        )
    if debug_section:
        sections.append(shdr(debug_section.encode("utf-8") + b"\x00", elf.SHT_PROGBITS, 0, 0))
    if note:
        sections.append(shdr(b".note.gnu.build-id\x00", elf.SHT_NOTE, note_off, len(note)))
    if embed or section_overflow:
        sections.append(
            shdr(b".comment\x00", elf.SHT_PROGBITS, embed_off if embed else shoff, comment_size)
        )
    if extra_dynamic_section:
        sections.append(
            shdr(
                b".dynamic2\x00",
                elf.SHT_DYNAMIC,
                dynamic_off,
                len(dynamic),
                elf.ELF64_DYN_SIZE,
                1,
                flags=elf.SHF_ALLOC,
            )
        )
    if extra_verneed_section:
        sections.append(
            shdr(
                b".gnu.version_r2\x00",
                elf.SHT_GNU_VERNEED,
                verneed_off,
                len(verneed),
                link=1,
                flags=elf.SHF_ALLOC,
                info=verneed_num,
            )
        )
    if extra_versym_section:
        sections.append(
            shdr(
                b".gnu.version2\x00",
                elf.SHT_GNU_VERSYM,
                versym_off,
                len(versym) or 2,
                elf.ELF64_VERSYM_SIZE,
                3,
                flags=elf.SHF_ALLOC,
            )
        )
    if alloc_outside_load:
        sections.append(
            shdr(
                b".outside\x00",
                elf.SHT_PROGBITS,
                0,
                8,
                flags=elf.SHF_ALLOC,
                addr=0x80000000,
            )
        )

    blob = (
        bytes(ehdr)
        + phdrs
        + dynstr
        + dynamic
        + dynsym
        + versym
        + verdef_pad
        + verdef
        + verneed_pad
        + verneed
        + note
        + embed
        + shstrtab
        + b"".join(sections)
    )
    if layout is not None:
        layout.clear()
        indexes = {".dynstr": 1, ".dynamic": 2, ".dynsym": 3, ".shstrtab": 4}
        next_index = 5
        if have_versym_section:
            indexes[".gnu.version"] = next_index
            next_index += 1
        if have_verneed_section:
            indexes[".gnu.version_r"] = next_index
            next_index += 1
        if have_verdef_section:
            indexes[".gnu.version_d"] = next_index
        layout.update(
            {
                "dynstr_off": dynstr_off,
                "dynstr_size": len(dynstr),
                "dynamic_off": dynamic_off,
                "dynamic_size": len(dynamic),
                "dynsym_off": dynsym_off,
                "versym_off": versym_off,
                "verneed_off": verneed_off,
                "verdef_off": verdef_off,
                "e_shoff": shoff,
                "e_phoff": elf.ELF64_EHDR_SIZE,
                "section_index": indexes,
                "verneed_num": verneed_num,
            }
        )
    if truncate is not None:
        return blob[:truncate]
    return blob


class LinuxElfVerifyTests(unittest.TestCase):
    def test_accepted_libsystem_equivalent_fixture(self) -> None:
        record = elf.parse_elf64_le_x86_64_dso(build_elf())
        self.assertEqual(record.soname, SONAME)
        self.assertEqual(record.needed, [LIBC])
        self.assertIn(SIGN, record.symbols)
        self.assertEqual(record.glibc_requirements, ["GLIBC_2.2.5", "GLIBC_2.35"])
        self.assertIn(".gnu.version", record.section_names)
        self.assertIn(".gnu.version_r", record.section_names)
        self.assertEqual(len(record.sign_exports), 1)

    def test_wrong_class_endian_machine_type_are_rejected(self) -> None:
        cases = (
            (dict(ei_class=1), "ELFCLASS64"),
            (dict(ei_data=2), "ELFDATA2LSB"),
            (dict(e_machine=3), "EM_X86_64"),
            (dict(e_machine=elf.EM_AARCH64), "EM_AARCH64"),
            (dict(e_type=2), "ET_DYN"),
            (dict(e_version=0), "e_version"),
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

    def test_rejected_symbol_forms(self) -> None:
        cases = (
            (dict(symbol_bind=elf.STB_LOCAL), "binding"),
            (dict(symbol_vis=elf.STV_HIDDEN), "visibility"),
            (dict(symbol_vis=elf.STV_INTERNAL), "visibility"),
            (dict(symbol_type=elf.STT_OBJECT), "STT_FUNC"),
            (dict(symbol_type=elf.STT_NOTYPE), "STT_FUNC"),
            (dict(symbol_shndx=elf.SHN_UNDEF, symbol_value=0), "undefined"),
            (dict(symbol_value=0), "value is zero"),
            (dict(extra_sign=True), "duplicate or ambiguous"),
        )
        for kwargs, needle in cases:
            with self.subTest(needle):
                with self.assertRaisesRegex(elf.ElfError, needle):
                    elf.parse_elf64_le_x86_64_dso(build_elf(**kwargs))

    def test_weak_and_protected_exports_are_accepted(self) -> None:
        weak = elf.parse_elf64_le_x86_64_dso(build_elf(symbol_bind=elf.STB_WEAK))
        self.assertEqual(weak.sign_exports[0]["bind"], elf.STB_WEAK)
        protected = elf.parse_elf64_le_x86_64_dso(build_elf(symbol_vis=elf.STV_PROTECTED))
        self.assertEqual(protected.sign_exports[0]["visibility"], elf.STV_PROTECTED)

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

    def test_debug_material_is_rejected(self) -> None:
        cases = (
            (".debug_info", "debug section"),
            (".zdebug_info", "debug section"),
            (".gnu_debuglink", "debug-link section"),
            (".gnu_debugaltlink", "debug-link section"),
            (".gnu_debugdata", "debug-link section"),
        )
        for name, needle in cases:
            with self.subTest(name):
                with self.assertRaisesRegex(elf.ElfError, needle):
                    elf.parse_elf64_le_x86_64_dso(build_elf(debug_section=name))
        with self.assertRaisesRegex(elf.ElfError, "NT_GNU_BUILD_ID"):
            elf.parse_elf64_le_x86_64_dso(build_elf(build_id=b"\x11" * 16))

    def test_truncated_overflow_and_duplicate_headers_are_rejected(self) -> None:
        with self.assertRaisesRegex(elf.ElfError, "truncated ELF header"):
            elf.parse_elf64_le_x86_64_dso(build_elf(truncate=20))
        with self.assertRaisesRegex(elf.ElfError, "missing ELF magic"):
            elf.parse_elf64_le_x86_64_dso(b"not-elf" + b"\x00" * 80)
        with self.assertRaisesRegex(elf.ElfError, "e_shnum"):
            elf.parse_elf64_le_x86_64_dso(build_elf(shnum_override=0))
        with self.assertRaisesRegex(elf.ElfError, "p_filesz exceeds p_memsz"):
            elf.parse_elf64_le_x86_64_dso(build_elf(filesz_gt_memsz=True))
        with self.assertRaisesRegex(elf.ElfError, "alignment mismatch"):
            elf.parse_elf64_le_x86_64_dso(build_elf(align_mismatch=True))
        with self.assertRaisesRegex(elf.ElfError, "file range exceeds"):
            elf.parse_elf64_le_x86_64_dso(build_elf(section_overflow=True, embed=b"x"))
        with self.assertRaisesRegex(elf.ElfError, "duplicate dynamic tag"):
            elf.parse_elf64_le_x86_64_dso(build_elf(duplicate_strtab=True))
        with self.assertRaisesRegex(elf.ElfError, "unterminated string"):
            elf.parse_elf64_le_x86_64_dso(build_elf(unterminated_dynstr=True))

    def test_missing_libc_is_rejected(self) -> None:
        with self.assertRaisesRegex(elf.ElfError, "missing required DT_NEEDED"):
            elf.parse_elf64_le_x86_64_dso(build_elf(needed=("libgcc_s.so.1",), skip_verneed=True))

    def test_glibc_version_policy(self) -> None:
        lower = elf.parse_elf64_le_x86_64_dso(build_elf(glibc_versions=("GLIBC_2.2.5",)))
        self.assertEqual(lower.glibc_requirements, ["GLIBC_2.2.5"])
        shared = elf.parse_elf64_le_x86_64_dso(
            build_elf(
                needed=(LIBC, "ld-linux-x86-64.so.2"),
                loader_verneed=True,
            )
        )
        self.assertEqual(shared.glibc_requirements, ["GLIBC_2.2.5", "GLIBC_2.35"])
        with self.assertRaisesRegex(elf.ElfError, "exceeds documented baseline"):
            elf.parse_elf64_le_x86_64_dso(build_elf(glibc_versions=("GLIBC_2.2.5", "GLIBC_2.36")))
        with self.assertRaisesRegex(elf.ElfError, "duplicate (GNU version|GLIBC)"):
            elf.parse_elf64_le_x86_64_dso(build_elf(duplicate_glibc=True))
        with self.assertRaisesRegex(elf.ElfError, "duplicate dynamic tag"):
            elf.parse_elf64_le_x86_64_dso(build_elf(duplicate_verneed_tag=True))
        with self.assertRaisesRegex(elf.ElfError, "VER_NEED_CURRENT"):
            elf.parse_elf64_le_x86_64_dso(build_elf(verneed_version=2))
        with self.assertRaisesRegex(elf.ElfError, "DT_VERNEED"):
            elf.parse_elf64_le_x86_64_dso(build_elf(skip_verneed=True))
        malformed = (
            ("GLIBC_2.36x", "unparseable"),
            ("GLIBC_999", "unparseable"),
            ("GLIBC_2.35.0.1", "unparseable"),
            ("GLIBC_PRIVATE", "GLIBC_PRIVATE"),
            ("GLIBC_+2.35", "unparseable"),
            ("GLIBC_02.35", "unparseable"),
        )
        for label, needle in malformed:
            with self.subTest(label):
                with self.assertRaisesRegex(elf.ElfError, needle):
                    elf.parse_elf64_le_x86_64_dso(build_elf(glibc_versions=(label,)))
        boundary = elf.parse_elf64_le_x86_64_dso(build_elf(glibc_versions=("GLIBC_2.35",)))
        self.assertEqual(boundary.glibc_requirements, ["GLIBC_2.35"])
        three = elf.parse_elf64_le_x86_64_dso(build_elf(glibc_versions=("GLIBC_2.2.5",)))
        self.assertEqual(three.glibc_requirements, ["GLIBC_2.2.5"])

    def test_glibc_helpers(self) -> None:
        self.assertEqual(elf.parse_glibc_version("GLIBC_2.35"), (2, 35, 0))
        self.assertEqual(elf.parse_glibc_version("GLIBC_2.2.5"), (2, 2, 5))
        self.assertEqual(elf.parse_glibc_version("GLIBC_2.35.0"), (2, 35, 0))
        self.assertIsNone(elf.parse_glibc_version("GLIBC_2.36x"))
        self.assertIsNone(elf.parse_glibc_version("GLIBC_999"))
        self.assertIsNone(elf.parse_glibc_version("GLIBC_2.35.0.1"))
        self.assertIsNone(elf.parse_glibc_version("GLIBC_02.35"))
        self.assertIsNone(elf.parse_glibc_version("GLIBC_+2.35"))
        self.assertIsNone(elf.parse_glibc_version("GLIBC_2."))
        self.assertIsNone(elf.parse_glibc_version("GLIBC_2.35."))
        self.assertIsNone(elf.parse_glibc_version("GLIBC_"))
        self.assertIsNone(elf.parse_glibc_version("GLIBC_PRIVATE"))
        self.assertTrue(elf.glibc_requirement_allowed("GLIBC_2.35"))
        self.assertTrue(elf.glibc_requirement_allowed("GLIBC_2.2.5"))
        self.assertFalse(elf.glibc_requirement_allowed("GLIBC_2.36"))
        self.assertFalse(elf.glibc_requirement_allowed("GLIBC_2.36x"))
        self.assertFalse(elf.glibc_requirement_allowed("GLIBC_999"))
        self.assertFalse(elf.glibc_requirement_allowed("GLIBC_2.35.0.1"))
        self.assertFalse(elf.glibc_requirement_allowed("GLIBC_PRIVATE"))
        with self.assertRaisesRegex(elf.ElfError, "unparseable"):
            elf.require_parsed_glibc("GLIBC_2.36x")
        with self.assertRaisesRegex(elf.ElfError, "unparseable"):
            elf.require_parsed_glibc("GLIBC_999")
        with self.assertRaisesRegex(elf.ElfError, "unparseable"):
            elf.require_parsed_glibc("GLIBC_2.35.0.1")
        with self.assertRaisesRegex(elf.ElfError, "GLIBC_PRIVATE"):
            elf.require_parsed_glibc("GLIBC_PRIVATE")
        self.assertEqual(elf.require_parsed_glibc("GLIBC_2.35"), (2, 35, 0))
        self.assertEqual(elf.require_parsed_glibc("GLIBC_2.2.5"), (2, 2, 5))
        self.assertEqual(
            elf.parse_ldd_glibc_version("ldd (Ubuntu GLIBC 2.35-0ubuntu3.8) 2.35\n"),
            (2, 35, 0),
        )

    def test_embedded_host_paths_are_fatal_near_misses_are_not(self) -> None:
        cases = (
            b"/home/runner/work/KardanoSDK/KardanoSDK",
            b"/Users/sarmidev/StudioProjects/KardanoSDK",
            b"/opt/hostedtoolcache/Python/3.10.12",
            b"/home/sarmidev/.cargo/registry",
        )
        for payload in cases:
            with self.subTest(payload):
                with self.assertRaisesRegex(elf.ElfError, "embedded host-absolute"):
                    elf.parse_elf64_le_x86_64_dso(build_elf(embed=payload + b"\x00"))
        benign = elf.parse_elf64_le_x86_64_dso(
            build_elf(
                embed=b"home/runner/not-absolute /home/rebuild/src Users/relative /kardano/src\x00"
            )
        )
        self.assertEqual(benign.forbidden_paths, [])
        extra = (b"/tmp/kardano-linux-a",)
        with self.assertRaisesRegex(elf.ElfError, "embedded host-absolute"):
            elf.parse_elf64_le_x86_64_dso(
                build_elf(embed=b"/tmp/kardano-linux-a/cargo-target\x00"),
                extra_forbidden_roots=extra,
            )

    def test_nm_posix_is_exact_not_substring(self) -> None:
        with self.assertRaisesRegex(elf.ElfError, "missing from nm"):
            elf.require_exact_sign_nm(
                elf.parse_posix_nm_defined(
                    f"not_{SIGN} T 1000 10\n"
                    f"prefix{SIGN} T 2000 10\n"
                )
            )
        with self.assertRaisesRegex(elf.ElfError, "ambiguous"):
            elf.require_exact_sign_nm(
                elf.parse_posix_nm_defined(f"{SIGN} T 1000 10\n{SIGN} T 2000 10\n")
            )
        with self.assertRaisesRegex(elf.ElfError, "nm type"):
            elf.require_exact_sign_nm(elf.parse_posix_nm_defined(f"{SIGN} D 1000 10\n"))
        record = elf.require_exact_sign_nm(
            elf.parse_posix_nm_defined(f"{SIGN} T 0000000000001000 0000000000000010\n")
        )
        self.assertEqual(record.type_code, "T")

    def test_verify_path_round_trip_without_host_tools(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        path = root / SONAME
        path.write_bytes(build_elf())
        record = elf.verify_linux_x86_64_cdylib(path, require_tools=False, readelf=None, nm=None)
        self.assertEqual(record.soname, SONAME)
        self.assertEqual(path.read_bytes(), build_elf())

    def test_verneed_chain_malformations_are_rejected(self) -> None:
        cases = (
            (dict(skip_verneed_section=True), "exactly one .gnu.version_r"),
            (dict(extra_verneed_section=True), "exactly one .gnu.version_r"),
            (dict(vn_next_final=16), "final vn_next"),
            (dict(vna_next_final=16), "final vna_next"),
            (dict(loader_verneed=True, needed=(LIBC, "ld-linux-x86-64.so.2"), vn_next_nonfinal=0), "truncated"),
            (dict(vna_next_nonfinal=0), "truncated"),
            (dict(vn_aux=0), "vn_aux is missing"),
            (dict(vn_aux=4), "overlaps"),
            (dict(vernaux_overlap=True), "overlaps"),
            (dict(verneed_num_override=2), "truncated"),
            (
                dict(
                    loader_verneed=True,
                    needed=(LIBC, "ld-linux-x86-64.so.2"),
                    verneed_num_override=1,
                ),
                "final vn_next",
            ),
            (dict(vna_next_nonfinal=2), "not 4-byte aligned"),
            (dict(vna_next_nonfinal=0xFFFFFFF0), "outside the SHT_GNU_verneed"),
            (
                dict(
                    loader_verneed=True,
                    needed=(LIBC, "ld-linux-x86-64.so.2"),
                    verneed_num_override=3,
                    verneed_cycle=True,
                ),
                "overlaps|outside|forward|revisited",
            ),
        )
        for kwargs, needle in cases:
            with self.subTest(needle):
                with self.assertRaisesRegex(elf.ElfError, needle):
                    elf.parse_elf64_le_x86_64_dso(build_elf(**kwargs))

    def test_section_and_program_structure_is_fail_closed(self) -> None:
        with self.assertRaisesRegex(elf.ElfError, "canonical SHT_NULL"):
            elf.parse_elf64_le_x86_64_dso(build_elf(section0_nonzero=True))
        with self.assertRaisesRegex(elf.ElfError, "exactly one .dynamic"):
            elf.parse_elf64_le_x86_64_dso(build_elf(extra_dynamic_section=True))
        with self.assertRaisesRegex(elf.ElfError, "sh_entsize"):
            elf.parse_elf64_le_x86_64_dso(build_elf(dynamic_entsize=8))
        with self.assertRaisesRegex(elf.ElfError, "sh_link"):
            elf.parse_elf64_le_x86_64_dso(build_elf(dynamic_link=4))
        with self.assertRaisesRegex(elf.ElfError, "sh_addralign is zero"):
            elf.parse_elf64_le_x86_64_dso(build_elf(zero_sh_addralign=True))
        with self.assertRaisesRegex(elf.ElfError, "not contained in a PT_LOAD"):
            elf.parse_elf64_le_x86_64_dso(build_elf(alloc_outside_load=True))
        blob = bytearray(build_elf())
        struct.pack_into("<H", blob, 56, elf.PN_XNUM)
        with self.assertRaisesRegex(elf.ElfError, "PN_XNUM"):
            elf.parse_elf64_le_x86_64_dso(bytes(blob))
        blob = bytearray(build_elf())
        struct.pack_into("<H", blob, 62, elf.SHN_XINDEX)
        with self.assertRaisesRegex(elf.ElfError, "SHN_XINDEX"):
            elf.parse_elf64_le_x86_64_dso(bytes(blob))

    def test_absolute_path_allowlist(self) -> None:
        for prefix in elf.ALLOWED_ABSOLUTE_PREFIXES:
            with self.subTest(prefix):
                record = elf.parse_elf64_le_x86_64_dso(
                    build_elf(embed=f"{prefix}/ok\x00".encode("ascii"))
                )
                self.assertEqual(record.forbidden_paths, [])
        rustc_dep = elf.parse_elf64_le_x86_64_dso(
            build_elf(embed=b"/rust/deps/gimli-0.32.3/src/read/abbrev.rs\x00")
        )
        self.assertEqual(rustc_dep.forbidden_paths, [])
        near_misses = (
            b"/cargo-evil\x00",
            b"/home/rebuild-extra\x00",
            b"/lib64-extra\x00",
            b"/rust/deps-evil\x00",
            b"/rust/not-deps\x00",
            b"/proc-evil\x00",
            b"/usr/local/private-build\x00",
            b"/tmp/untracked-host\x00",
            b"/home/runner\x00",
            b"/home/runner/work\x00",
        )
        for payload in near_misses:
            with self.subTest(payload):
                with self.assertRaisesRegex(elf.ElfError, "embedded host-absolute"):
                    elf.parse_elf64_le_x86_64_dso(build_elf(embed=payload))
        benign = elf.parse_elf64_le_x86_64_dso(
            build_elf(embed=b"foo/bar not-a-path GLIBC_2.35 slash/text\x00/0\x00/N\x00")
        )
        self.assertEqual(benign.forbidden_paths, [])
        self.assertFalse(elf.is_absolute_path_like("/0"))
        self.assertFalse(elf.is_absolute_path_like("/N"))
        self.assertFalse(elf.is_absolute_path_like("//cargo"))
        self.assertTrue(elf.is_absolute_path_like("/tmp/untracked-host"))
        self.assertTrue(elf.is_absolute_path_like("/cargo-evil"))
        with self.assertRaisesRegex(elf.ElfError, "embedded host-absolute"):
            elf.parse_elf64_le_x86_64_dso(
                build_elf(embed=b"note\x00/tmp/untracked-host\x00more\x00")
            )

    def test_readelf_corroboration_is_fail_closed(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        path = root / SONAME
        path.write_bytes(build_elf())

        class _Result:
            def __init__(self, stdout: str = "", returncode: int = 0) -> None:
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = ""

        def run_with(version_text: str):
            def _run(command: list[str]) -> _Result:
                if "--version-info" in command:
                    return _Result(version_text)
                return _Result("Dynamic section")
            return _run

        matching = "  Name: GLIBC_2.2.5\n  Name: GLIBC_2.35\n"
        with patch.object(elf, "_run", run_with(matching)):
            record = elf.verify_linux_x86_64_cdylib(path, readelf="readelf", nm=None)
            self.assertEqual(record.glibc_requirements, ["GLIBC_2.2.5", "GLIBC_2.35"])
        for label, needle in (
            ("GLIBC_2.36x", "unparseable"),
            ("GLIBC_999", "unparseable"),
            ("GLIBC_2.35.0.1", "unparseable"),
            ("GLIBC_PRIVATE", "GLIBC_PRIVATE"),
            ("GLIBC_2.36", "does not match the parser"),
        ):
            with self.subTest(label):
                with patch.object(elf, "_run", run_with(f"  Name: {label}\n")):
                    with self.assertRaisesRegex(elf.ElfError, needle):
                        elf.verify_linux_x86_64_cdylib(path, readelf="readelf", nm=None)

    def test_raw_and_slash_path_detection(self) -> None:
        cases = (
            b"prefix /home/runner/path\x00",
            b"/home/runner/unterminated",
            b"/home/runner/\xc3\xa9\x00",
            b"/home/runner/\xff\xfe\x00",
            b"/home/runner/path\nmore",
            b"/home/runner/path\tmore",
            b"xxxx/home/runner/embedded\x00",
            b"/cargo-evil\x00",
            b"/usr/local/private-build\x00",
            b"/Users/sarmidev\x00",
            b"/tmp/untracked-host\x00",
        )
        for payload in cases:
            with self.subTest(payload):
                with self.assertRaisesRegex(elf.ElfError, "embedded host-absolute"):
                    elf.parse_elf64_le_x86_64_dso(build_elf(embed=payload))
        self.assertIn("/home/runner/path", elf.scan_linux_forbidden_paths(b"aa/home/runner/path"))
        self.assertIn("/Users/x", elf.scan_linux_forbidden_paths(b"zz/Users/x"))
        allowed = elf.parse_elf64_le_x86_64_dso(
            build_elf(
                embed=b"/cargo/registry\x00/lib64/ld-linux-x86-64.so.2\x00/proc/self/exe\x00"
            )
        )
        self.assertEqual(allowed.forbidden_paths, [])
        benign = elf.parse_elf64_le_x86_64_dso(
            build_elf(embed=b"foo/bar slash/text /0 /N\x00")
        )
        self.assertEqual(benign.forbidden_paths, [])
        noise = (
            b"/d\x86\x00",
            b"/c'\xc4\x00",
            b"/c\xa8\xa6\x8ag\x00",
            b"/X\xa4\x9e\xaar\x00",
            b"/B\x85\x00",
            b"/.\x80\x82\x00",
            b"/I\x83\xc3\xb8M)\xebH\x00",
        )
        for payload in noise:
            with self.subTest(("noise", payload)):
                record = elf.parse_elf64_le_x86_64_dso(build_elf(embed=payload))
                self.assertEqual(record.forbidden_paths, [])
                self.assertEqual(elf.scan_linux_forbidden_paths(payload), [])
        with self.assertRaisesRegex(elf.ElfError, "embedded host-absolute"):
            elf.parse_elf64_le_x86_64_dso(build_elf(embed=b"/usr/local/foo\xff\xfe\x00"))
        with self.assertRaisesRegex(elf.ElfError, "embedded host-absolute"):
            elf.parse_elf64_le_x86_64_dso(build_elf(embed=b"/d\x86/unapproved\x00"))
        with self.assertRaisesRegex(elf.ElfError, "embedded host-absolute"):
            elf.parse_elf64_le_x86_64_dso(build_elf(embed=b"/proc-evil\x00"))

    def test_dynamic_version_relations_are_mutated_closed(self) -> None:
        layout: dict = {}
        blob = bytearray(build_elf(layout=layout))
        self.assertTrue(elf.parse_elf64_le_x86_64_dso(bytes(blob)))

        def shoff(name: str) -> int:
            return layout["e_shoff"] + layout["section_index"][name] * elf.ELF64_SHDR_SIZE

        dynstr_hdr = shoff(".dynstr")
        mutated = bytearray(blob)
        struct.pack_into("<Q", mutated, dynstr_hdr + 32, layout["dynstr_size"] + 8)
        with self.assertRaisesRegex(elf.ElfError, "sh_size does not equal DT_STRSZ"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        mutated = bytearray(blob)
        struct.pack_into("<Q", mutated, dynstr_hdr + 16, layout["dynstr_off"] + 1)
        with self.assertRaisesRegex(elf.ElfError, "DT_STRTAB does not equal"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        version_r = shoff(".gnu.version_r")
        mutated = bytearray(blob)
        struct.pack_into("<I", mutated, version_r + 44, layout["verneed_num"] + 1)
        with self.assertRaisesRegex(elf.ElfError, "sh_info does not equal DT_VERNEEDNUM"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        mutated = bytearray(blob)
        struct.pack_into("<Q", mutated, version_r + 8, 0)
        with self.assertRaisesRegex(elf.ElfError, "not SHF_ALLOC"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        mutated = bytearray(blob)
        struct.pack_into("<Q", mutated, version_r + 16, layout["verneed_off"] + 16)
        with self.assertRaisesRegex(elf.ElfError, "DT_VERNEED does not equal"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        dynamic_hdr = shoff(".dynamic")
        mutated = bytearray(blob)
        struct.pack_into("<Q", mutated, dynamic_hdr + 8, 0)
        with self.assertRaisesRegex(elf.ElfError, "not SHF_ALLOC"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        pt_dynamic = layout["e_phoff"] + elf.ELF64_PHDR_SIZE
        mutated = bytearray(blob)
        struct.pack_into("<Q", mutated, pt_dynamic + 40, layout["dynamic_size"] + 16)
        with self.assertRaisesRegex(elf.ElfError, "p_memsz does not equal p_filesz"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        mutated = bytearray(blob)
        struct.pack_into("<Q", mutated, pt_dynamic + 48, 8)
        with self.assertRaisesRegex(elf.ElfError, "p_align does not equal"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        mutated = bytearray(blob)
        struct.pack_into("<Q", mutated, pt_dynamic + 16, layout["dynamic_off"] + 8)
        with self.assertRaisesRegex(elf.ElfError, "p_vaddr does not equal"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        versym = shoff(".gnu.version")
        mutated = bytearray(blob)
        struct.pack_into("<Q", mutated, versym + 32, 2)
        with self.assertRaisesRegex(elf.ElfError, "size does not match .dynsym count"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        mutated = bytearray(blob)
        struct.pack_into("<I", mutated, versym + 40, 1)
        with self.assertRaisesRegex(elf.ElfError, "sh_link does not point at .dynsym"):
            elf.parse_elf64_le_x86_64_dso(bytes(mutated))

        with self.assertRaisesRegex(elf.ElfError, "DT_VERSYM is required"):
            elf.parse_elf64_le_x86_64_dso(build_elf(skip_versym_tag=True))
        with self.assertRaisesRegex(elf.ElfError, "exactly one .gnu.version"):
            elf.parse_elf64_le_x86_64_dso(build_elf(skip_versym_section=True))
        with self.assertRaisesRegex(elf.ElfError, "exactly one .gnu.version"):
            elf.parse_elf64_le_x86_64_dso(build_elf(extra_versym_section=True))
        with self.assertRaisesRegex(elf.ElfError, "both be present"):
            elf.parse_elf64_le_x86_64_dso(build_elf(verdef_tag_only=True))
        with self.assertRaisesRegex(elf.ElfError, "both be present"):
            elf.parse_elf64_le_x86_64_dso(build_elf(verdefnum_only=True))
        with self.assertRaisesRegex(elf.ElfError, "stray .gnu.version_d"):
            elf.parse_elf64_le_x86_64_dso(build_elf(stray_verdef_section=True))
        record = elf.parse_elf64_le_x86_64_dso(build_elf(include_verdef=True))
        self.assertEqual(record.soname, SONAME)
