"""Adversarial tests for the fail-closed Windows PE32+ verifier."""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import windows_pe_verify as pe  # noqa: E402

SIGN = pe.SIGN_SYMBOL
DLL = pe.STABLE_DLL_NAME
IMPORT_FN = "GetCurrentProcessId"
KERNEL32 = "kernel32.dll"


def _pack_section(
    name: bytes,
    vsize: int,
    va: int,
    raw_size: int,
    raw_ptr: int,
    chars: int,
) -> bytes:
    padded = name[:8] + b"\x00" * (8 - len(name[:8]))
    return (
        padded
        + struct.pack("<IIIIII", vsize, va, raw_size, raw_ptr, 0, 0)
        + struct.pack("<HHI", 0, 0, chars)
    )


def build_pe(
    *,
    dos_magic: bytes = b"MZ",
    e_lfanew: int | None = None,
    pe_sig: bytes = b"PE\x00\x00",
    machine: int = pe.IMAGE_FILE_MACHINE_AMD64,
    nsections: int | None = None,
    timestamp: int = 0,
    ptr_sym: int = 0,
    nsyms: int = 0,
    opt_size: int = pe.OPTIONAL_HEADER64_SIZE,
    characteristics: int = (
        pe.IMAGE_FILE_DLL
        | pe.IMAGE_FILE_EXECUTABLE_IMAGE
        | pe.IMAGE_FILE_LARGE_ADDRESS_AWARE
    ),
    magic: int = pe.IMAGE_NT_OPTIONAL_HDR64_MAGIC,
    subsystem: int = pe.IMAGE_SUBSYSTEM_WINDOWS_GUI,
    dll_characteristics: int = (
        pe.IMAGE_DLLCHARACTERISTICS_HIGH_ENTROPY_VA
        | pe.IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE
        | pe.IMAGE_DLLCHARACTERISTICS_NX_COMPAT
    ),
    number_of_rva: int = 16,
    export_dll_name: str = DLL,
    export_names: tuple[str, ...] = (SIGN,),
    export_func_rvas: tuple[int, ...] | None = None,
    duplicate_export_ordinals: bool = False,
    zero_export_rva: bool = False,
    import_dlls: tuple[tuple[str, tuple[str, ...]], ...] = ((KERNEL32, (IMPORT_FN,)),),
    ordinal_only_import: bool = False,
    unterminated_imports: bool = False,
    delay_rva: int = 0,
    delay_size: int = 0,
    debug_rva: int = 0,
    debug_size: int = 0,
    debug_type: int | None = None,
    cert_rva: int = 0,
    cert_size: int = 0,
    embed: bytes = b"",
    overlay: bytes = b"",
    truncate: int | None = None,
    section_raw_overflow: bool = False,
) -> bytes:
    file_align = 0x200
    sect_align = 0x1000
    text_va = 0x1000
    rdata_va = 0x2000
    text_raw = 0x200
    rdata_raw = 0x400
    text = bytearray(0x200)
    text[0x10:0x14] = b"\x90\x90\x90\xC3"
    rdata = bytearray(0x200)
    cursor = 0

    def place(payload: bytes, align: int = 1) -> int:
        nonlocal cursor
        if align > 1 and cursor % align:
            cursor += align - (cursor % align)
        rva = rdata_va + cursor
        rdata[cursor : cursor + len(payload)] = payload
        cursor += len(payload)
        return rva

    func_rvas = list(export_func_rvas or (text_va + 0x10,) * len(export_names))
    if zero_export_rva:
        func_rvas = [0 for _ in export_names]
    if duplicate_export_ordinals:
        ordinals = b"\x00\x00" * len(export_names)
    else:
        ordinals = b"".join(struct.pack("<H", i) for i in range(len(export_names)))
    cursor = pe.EXPORT_DIRECTORY_SIZE
    functions_rva = place(b"".join(struct.pack("<I", rva) for rva in func_rvas), 4)
    name_rvas: list[int] = []
    for name in export_names:
        name_rvas.append(place(name.encode("ascii") + b"\x00"))
    names_table_rva = place(b"".join(struct.pack("<I", rva) for rva in name_rvas), 4)
    ords_rva = place(ordinals, 2)
    export_dll_rva = place(export_dll_name.encode("ascii") + b"\x00")
    export_dir = struct.pack(
        "<IIHHIIIIIII",
        0,
        0,
        0,
        0,
        export_dll_rva,
        1,
        len(func_rvas),
        len(export_names),
        functions_rva,
        names_table_rva,
        ords_rva,
    )
    rdata[0 : pe.EXPORT_DIRECTORY_SIZE] = export_dir
    export_rva = rdata_va
    export_size = pe.EXPORT_DIRECTORY_SIZE

    thunks_rva_list: list[int] = []
    import_name_rvas: list[int] = []
    for dll_name, funcs in import_dlls:
        if ordinal_only_import:
            thunk = struct.pack("<Q", (1 << 63) | 1)
            thunks_rva_list.append(place(thunk + b"\x00" * 8, 8))
        else:
            ibn_rvas = []
            for func in funcs:
                ibn_rvas.append(place(struct.pack("<H", 0) + func.encode("ascii") + b"\x00", 2))
            blob = b"".join(struct.pack("<Q", rva) for rva in ibn_rvas) + b"\x00" * 8
            thunks_rva_list.append(place(blob, 8))
        import_name_rvas.append(place(dll_name.encode("ascii") + b"\x00"))

    descriptors = bytearray()
    for thunk_rva, name_rva in zip(thunks_rva_list, import_name_rvas):
        descriptors += struct.pack("<IIIII", thunk_rva, 0, 0, name_rva, thunk_rva)
    if not unterminated_imports:
        descriptors += b"\x00" * pe.IMPORT_DESCRIPTOR_SIZE
    import_rva = place(bytes(descriptors), 4)
    if unterminated_imports:
        # Leave no all-zero descriptor in the remaining .rdata padding.
        if cursor < len(rdata):
            rdata[cursor:] = b"\x41" * (len(rdata) - cursor)
    import_size = len(descriptors)

    if embed:
        place(embed + b"\x00")

    if debug_type is not None:
        entry = struct.pack("<IIHHIIII", 0, 0, 0, 0, debug_type, 0, 0, 0)
        debug_rva = place(entry, 4)
        debug_size = pe.IMAGE_DEBUG_DIRECTORY_SIZE

    directories = [(0, 0)] * 16
    directories[pe.DIR_EXPORT] = (export_rva, export_size)
    directories[pe.DIR_IMPORT] = (import_rva, import_size)
    directories[pe.DIR_DELAY_IMPORT] = (delay_rva, delay_size)
    directories[pe.DIR_DEBUG] = (debug_rva, debug_size)
    directories[pe.DIR_SECURITY] = (cert_rva, cert_size)

    opt = bytearray(pe.OPTIONAL_HEADER64_SIZE)
    struct.pack_into("<H", opt, 0, magic)
    struct.pack_into("<I", opt, 0x10, text_va + 0x10)
    struct.pack_into("<Q", opt, 0x18, 0x180000000)
    struct.pack_into("<I", opt, 0x20, sect_align)
    struct.pack_into("<I", opt, 0x24, file_align)
    struct.pack_into("<H", opt, 0x28, 6)
    struct.pack_into("<H", opt, 0x30, 6)
    struct.pack_into("<I", opt, 0x38, 0x3000)
    struct.pack_into("<I", opt, 0x3C, 0x200)
    struct.pack_into("<H", opt, 0x44, subsystem)
    struct.pack_into("<H", opt, 0x46, dll_characteristics)
    struct.pack_into("<I", opt, 0x6C, number_of_rva)
    for index, (rva, size) in enumerate(directories):
        struct.pack_into("<II", opt, 0x70 + index * 8, rva, size)

    text_chars = pe.IMAGE_SCN_CNT_CODE | pe.IMAGE_SCN_MEM_EXECUTE | 0x40000000
    rdata_chars = 0x00000040 | 0x40000000
    rdata_raw_ptr = 0x400
    rdata_raw_size = 0x200
    if section_raw_overflow:
        rdata_raw_size = 0xFFFF0000
    sections = _pack_section(b".text", 0x200, text_va, 0x200, text_raw, text_chars)
    sections += _pack_section(
        b".rdata", 0x200, rdata_va, rdata_raw_size, rdata_raw_ptr, rdata_chars
    )
    used_sections = 2 if nsections is None else nsections

    coff = struct.pack(
        "<HHIIIHH",
        machine,
        used_sections,
        timestamp,
        ptr_sym,
        nsyms,
        opt_size,
        characteristics,
    )
    pe_off = 64 if e_lfanew is None else e_lfanew
    dos = bytearray(max(64, pe_off))
    dos[0:2] = dos_magic[:2] if len(dos_magic) >= 2 else dos_magic
    if len(dos_magic) > 2:
        dos[0 : len(dos_magic)] = dos_magic
    struct.pack_into("<I", dos, 0x3C, pe_off)
    headers = bytes(dos[:pe_off]) + pe_sig + coff + bytes(opt) + sections
    headers = headers.ljust(0x200, b"\x00")
    image = headers + bytes(text) + bytes(rdata)
    if overlay:
        image += overlay
    if truncate is not None:
        image = image[:truncate]
    return image


def _write(data: bytes) -> Path:
    root = Path(tempfile.mkdtemp())
    path = root / DLL
    path.write_bytes(data)
    return path


class JnaPrefixTests(unittest.TestCase):
    def test_prefix_matches_jna_5_19_1_windows_x86_64(self) -> None:
        # Platform.getNativeLibraryResourcePrefix(WINDOWS, x86_64) => win32-x86-64
        # NativeLibrary.mapSharedLibraryName("kardano_ed25519_bip32_signing") => *.dll
        self.assertEqual(pe.JNA_RESOURCE_PREFIX, "win32-x86-64")
        self.assertEqual(pe.STABLE_DLL_NAME, "kardano_ed25519_bip32_signing.dll")
        self.assertEqual(
            pe.JNA_RESOURCE_RELATIVE,
            "src/jvmMain/resources/win32-x86-64/kardano_ed25519_bip32_signing.dll",
        )
        self.assertNotIn("aarch64", pe.JNA_RESOURCE_PREFIX)
        self.assertNotIn("arm", pe.JNA_RESOURCE_PREFIX)


class ValidImageTests(unittest.TestCase):
    def test_minimal_policy_image_is_accepted_without_dumpbin(self) -> None:
        path = _write(build_pe())
        record = pe.verify_windows_x86_64_dll(path, require_tools=False)
        self.assertEqual(record.machine, pe.IMAGE_FILE_MACHINE_AMD64)
        self.assertEqual(record.magic, pe.IMAGE_NT_OPTIONAL_HDR64_MAGIC)
        self.assertEqual(len(record.sign_exports), 1)
        self.assertEqual(record.sign_exports[0].name, SIGN)
        self.assertEqual(record.imports[0].name, KERNEL32)
        self.assertEqual(record.timestamp, 0)
        hashed = _write(build_pe(timestamp=0xA1B2C3D4))
        hashed_record = pe.verify_windows_x86_64_dll(hashed, require_tools=False)
        self.assertEqual(hashed_record.timestamp, 0xA1B2C3D4)
        repro = _write(build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_REPRO))
        pe.verify_windows_x86_64_dll(repro, require_tools=False)


class AdversarialHeaderTests(unittest.TestCase):
    def test_truncated_and_bad_signatures(self) -> None:
        cases = [
            (build_pe(truncate=20), "truncated"),
            (build_pe(dos_magic=b"ZM"), "MZ"),
            (build_pe(pe_sig=b"PE\x00\x01"), "PE"),
            (build_pe(e_lfanew=8), "e_lfanew"),
            (build_pe(machine=pe.IMAGE_FILE_MACHINE_I386), "AMD64"),
            (build_pe(machine=pe.IMAGE_FILE_MACHINE_ARM64), "AMD64"),
            (build_pe(magic=pe.IMAGE_NT_OPTIONAL_HDR32_MAGIC), "PE32"),
            (
                build_pe(characteristics=pe.IMAGE_FILE_EXECUTABLE_IMAGE),
                "IMAGE_FILE_DLL",
            ),
            (
                build_pe(
                    characteristics=pe.IMAGE_FILE_DLL | pe.IMAGE_FILE_SYSTEM,
                ),
                "SYSTEM",
            ),
        ]
        for payload, needle in cases:
            with self.subTest(needle=needle):
                with self.assertRaises(pe.PeError) as caught:
                    pe.parse_pe32_plus_x86_64_dll(payload)
                self.assertTrue(
                    needle.lower() in str(caught.exception).lower()
                    or needle in str(caught.exception),
                    caught.exception,
                )

    def test_wrong_subsystem_and_flags_and_timestamp(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(subsystem=pe.IMAGE_SUBSYSTEM_WINDOWS_CUI)
            )
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(dll_characteristics=pe.IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE)
            )
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(
                    dll_characteristics=(
                        pe.REQUIRED_DLL_CHARACTERISTICS
                        | pe.IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY
                    )
                )
            )
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(number_of_rva=15))


class AdversarialSectionTests(unittest.TestCase):
    def test_section_raw_overflow_and_overlay(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(section_raw_overflow=True))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(overlay=b"TRAIL"))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(overlay=b"\x00\x00"))


class AdversarialExportTests(unittest.TestCase):
    def test_missing_duplicate_hidden_and_zero_rva(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(export_names=("other_symbol",)))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(export_names=(SIGN, SIGN)))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(zero_export_rva=True))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(export_names=(SIGN, "other"), duplicate_export_ordinals=True)
            )


class AdversarialImportTests(unittest.TestCase):
    def test_unexpected_delay_and_ordinal_imports(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(import_dlls=(("evil.dll", ("BadFunc",)),))
            )
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(ordinal_only_import=True))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(delay_rva=0x2000, delay_size=20))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(unterminated_imports=True))


class AdversarialDebugCertPathTests(unittest.TestCase):
    def test_debug_certificate_pdb_and_host_paths(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(debug_rva=0x2000, debug_size=16))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_CODEVIEW))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(debug_type=1))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(cert_rva=0x400, cert_size=8))
        path = _write(build_pe(embed=b"C:\\Users\\runneradmin\\work\\x"))
        with self.assertRaises(pe.PeError):
            pe.verify_windows_x86_64_dll(path, require_tools=False)
        path = _write(build_pe(embed=b"RSDS" + b"\x00" * 16 + b"out.pdb"))
        with self.assertRaises(pe.PeError):
            pe.verify_windows_x86_64_dll(path, require_tools=False)
        path = _write(build_pe(embed=b"/cargo-target/release/out"))
        pe.verify_windows_x86_64_dll(path, require_tools=False)

    def test_wrong_filename_and_arm_prefix_are_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        wrong = root / "libkardano_ed25519_bip32_signing.dll"
        wrong.write_bytes(build_pe())
        with self.assertRaises(pe.PeError):
            pe.verify_windows_x86_64_dll(wrong, require_tools=False)
        path = _write(build_pe())
        with self.assertRaises(pe.PeError):
            pe.verify_windows_x86_64_dll(
                path, require_tools=False, expected_resource_prefix="win32-aarch64"
            )


class DumpbinCorroborationTests(unittest.TestCase):
    def _record(self) -> pe.PeRecord:
        return pe.parse_pe32_plus_x86_64_dll(build_pe())

    def _dumpbin_ok(self) -> str:
        return (
            "             8664 machine (x64)\n"
            "                 DLL\n"
            "             20B magic # (PE32+)\n"
            "          1    0 00001010 uniffi_kardano_ed25519_bip32_signing_fn_func_sign\n"
            "    kernel32.dll\n"
        )

    def test_matching_dumpbin_passes(self) -> None:
        pe.require_dumpbin_corroboration(self._record(), self._dumpbin_ok())

    def test_dumpbin_mismatches_fail_closed(self) -> None:
        record = self._record()
        good = self._dumpbin_ok()
        cases = [
            good.replace("8664 machine (x64)", "14C machine (x86)"),
            good.replace("PE32+", "PE32"),
            good.replace("                 DLL\n", ""),
            good.replace(SIGN, "other_symbol"),
            good + "          2    1 00001020 uniffi_kardano_ed25519_bip32_signing_fn_func_sign\n",
            good.replace("    kernel32.dll\n", "    evil.dll\n"),
            good.replace("    kernel32.dll\n", ""),
            good + "    Delay Load Imports\n",
        ]
        for text in cases:
            with self.subTest(text=text[:40]):
                with self.assertRaises(pe.PeError):
                    pe.require_dumpbin_corroboration(record, text)

    def test_require_tools_without_dumpbin_fails(self) -> None:
        path = _write(build_pe())
        with self.assertRaises(pe.PeError):
            pe.verify_windows_x86_64_dll(path, require_tools=True, dumpbin=None)


class ArithmeticTests(unittest.TestCase):
    def test_checked_add_mul_reject_overflow_and_negatives(self) -> None:
        with self.assertRaises(pe.PeError):
            pe._checked_add(pe.UINT64_MAX, 1)
        with self.assertRaises(pe.PeError):
            pe._checked_mul(2, (pe.UINT64_MAX // 2) + 1)
        with self.assertRaises(pe.PeError):
            pe._checked_add(-1, 1)


if __name__ == "__main__":
    unittest.main()
