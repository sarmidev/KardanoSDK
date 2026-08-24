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
REPRO_HASH32 = bytes(range(32))


def repro_hash_payload(digest: bytes = REPRO_HASH32) -> bytes:
    return struct.pack("<I", len(digest)) + digest


def pogo_payload(
    *,
    signature: int = pe.IMAGE_DEBUG_POGO_SIGNATURE_LTCG,
    entries: tuple[tuple[int, int, str], ...] = ((0x1010, 4, ".text"),),
) -> bytes:
    body = b""
    for rva, size, name in entries:
        body += struct.pack("<II", rva, size) + name.encode("ascii") + b"\x00"
        body += b"\x00" * ((4 - (len(body) % 4)) % 4)
    return struct.pack("<I", signature) + body


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
    size_of_image: int = 0x3000,
    text_chars: int | None = None,
    rdata_chars: int | None = None,
    directories_override: dict[int, tuple[int, int]] | None = None,
    exception_entries: tuple[tuple[int, int, int], ...] | None = None,
    reloc_block: bytes | None = None,
    iat_directory: bool = True,
    oft_zero: bool = False,
    export_directory_size: int | None = None,
    iat_directory_size: int | None = None,
    divergent_iat: bool = False,
    omit_iat_terminator: bool = False,
    omit_ilt_terminator: bool = False,
    thunk_reserved_bits: bool = False,
    overlap_iat_with_ilt: bool = False,
    debug_payload: bytes = b"",
    debug_size_of_data: int | None = None,
    debug_address: int | None = None,
    debug_pointer: int | None = None,
    debug_duplicate: bool = False,
    resource_blob: bytes | None = None,
    tls_callbacks: tuple[int, ...] | None = None,
    tls_unterminated: bool = False,
    tls_inconsistent_raw: bool = False,
) -> bytes:
    file_align = 0x200
    sect_align = 0x1000
    text_va = 0x1000
    rdata_va = 0x2000
    text_raw = 0x200
    rdata_raw = 0x400
    image_base = 0x180000000
    text = bytearray(0x200)
    text[0x10:0x14] = b"\x90\x90\x90\xC3"
    rdata = bytearray(0x400)
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
    export_size = cursor if export_directory_size is None else export_directory_size

    ilt_rvas: list[int] = []
    iat_rvas: list[int] = []
    iat_sizes: list[int] = []
    import_name_rvas: list[int] = []
    for dll_name, funcs in import_dlls:
        thunk_sentinel = struct.pack("<Q", 1 << 32)
        if ordinal_only_import:
            thunk_word = struct.pack("<Q", (1 << 63) | 1)
            ilt_blob = thunk_word + (
                thunk_sentinel if omit_ilt_terminator else b"\x00" * 8
            )
            iat_blob = thunk_word + (
                thunk_sentinel if omit_iat_terminator else b"\x00" * 8
            )
        else:
            ibn_rvas = []
            for func in funcs:
                ibn_rvas.append(place(struct.pack("<H", 0) + func.encode("ascii") + b"\x00", 2))
            words = list(ibn_rvas)
            if thunk_reserved_bits:
                words = [rva | (1 << 32) for rva in words]
            ilt_term = thunk_sentinel if omit_ilt_terminator else b"\x00" * 8
            ilt_blob = b"".join(struct.pack("<Q", rva) for rva in words) + ilt_term
            iat_words = list(words)
            if divergent_iat:
                iat_words = [0xFFFFFFFFFFFFFFFF for _ in words]
            iat_term = thunk_sentinel if omit_iat_terminator else b"\x00" * 8
            iat_blob = b"".join(struct.pack("<Q", rva) for rva in iat_words) + iat_term
        if oft_zero and omit_iat_terminator:
            ilt_blob = ilt_blob[:-8] + thunk_sentinel
        ilt_rva = place(ilt_blob, 8)
        if oft_zero:
            iat_rva = ilt_rva
            iat_blob_size = len(ilt_blob)
        else:
            iat_rva = place(iat_blob, 8)
            iat_blob_size = len(iat_blob)
        if overlap_iat_with_ilt and not oft_zero:
            iat_rva = ilt_rva + 8
        ilt_rvas.append(ilt_rva)
        iat_rvas.append(iat_rva)
        iat_sizes.append(iat_blob_size)
        import_name_rvas.append(place(dll_name.encode("ascii") + b"\x00"))

    descriptors = bytearray()
    for ilt_rva, iat_rva, name_rva in zip(ilt_rvas, iat_rvas, import_name_rvas):
        oft = 0 if oft_zero else ilt_rva
        descriptors += struct.pack("<IIIII", oft, 0, 0, name_rva, iat_rva)
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
        payload_rva = 0
        pointer = 0
        size = 0
        payload = debug_payload
        if (
            debug_type == pe.IMAGE_DEBUG_TYPE_POGO
            and not payload
            and debug_size_of_data is None
        ):
            payload = pogo_payload()
        if payload:
            payload_rva = place(payload)
            pointer = rdata_raw + (payload_rva - rdata_va)
            size = len(payload)
        if debug_size_of_data is not None:
            size = debug_size_of_data
        addr = payload_rva if debug_address is None else debug_address
        ptr = pointer if debug_pointer is None else debug_pointer
        entry = struct.pack("<IIHHIIII", 0, 0, 0, 0, debug_type, size, addr, ptr)
        if debug_duplicate:
            entry += entry
        debug_rva = place(entry, 4)
        debug_size = len(entry)

    exception_rva = 0
    exception_size = 0
    if exception_entries:
        blob = b"".join(struct.pack("<III", *item) for item in exception_entries)
        exception_rva = place(blob, 4)
        exception_size = len(blob)

    reloc_rva = 0
    reloc_size = 0
    if reloc_block is not None:
        reloc_rva = place(reloc_block, 4)
        reloc_size = len(reloc_block)

    resource_rva = 0
    resource_size = 0
    if resource_blob is not None:
        resource_rva = place(resource_blob, 4)
        resource_size = len(resource_blob)

    tls_rva = 0
    tls_size = 0
    if tls_callbacks is not None or tls_inconsistent_raw:
        callback_rvas = tls_callbacks or ()
        entries = [struct.pack("<Q", image_base + rva) for rva in callback_rvas]
        if not tls_unterminated:
            entries.append(b"\x00" * 8)
        elif cursor < len(rdata):
            # Keep walking from hitting accidental zeros.
            pass
        cb_rva = place(b"".join(entries) if entries else b"\x00" * 8, 8)
        if tls_unterminated:
            # Nonzero unmapped VA so the walk cannot treat later zeros as a terminator.
            extra = struct.pack("<Q", image_base + 0x00FFFF00)
            rel = cb_rva - rdata_va + 8 * len(callback_rvas)
            if rel + 8 <= len(rdata):
                rdata[rel : rel + 8] = extra
                cursor = max(cursor, rel + 8)
        idx_rva = place(b"\x00" * 4, 4)
        start_va = image_base + 0x2100 if tls_inconsistent_raw else 0
        end_va = 0
        tls = struct.pack(
            "<QQQQII",
            start_va,
            end_va,
            image_base + idx_rva,
            image_base + cb_rva,
            0,
            0,
        )
        tls_rva = place(tls, 4)
        tls_size = pe.TLS_DIRECTORY64_SIZE

    directories = [(0, 0)] * 16
    directories[pe.DIR_EXPORT] = (export_rva, export_size)
    directories[pe.DIR_IMPORT] = (import_rva, import_size)
    directories[pe.DIR_DELAY_IMPORT] = (delay_rva, delay_size)
    directories[pe.DIR_DEBUG] = (debug_rva, debug_size)
    directories[pe.DIR_SECURITY] = (cert_rva, cert_size)
    directories[pe.DIR_EXCEPTION] = (exception_rva, exception_size)
    directories[pe.DIR_BASERELOC] = (reloc_rva, reloc_size)
    directories[pe.DIR_RESOURCE] = (resource_rva, resource_size)
    directories[pe.DIR_TLS] = (tls_rva, tls_size)
    if iat_directory and iat_rvas:
        first = min(iat_rvas)
        last = max(rva + size for rva, size in zip(iat_rvas, iat_sizes))
        iat_size = last - first if iat_directory_size is None else iat_directory_size
        directories[pe.DIR_IAT] = (first, iat_size)
    if directories_override:
        for index, value in directories_override.items():
            directories[index] = value

    opt = bytearray(pe.OPTIONAL_HEADER64_SIZE)
    struct.pack_into("<H", opt, 0, magic)
    struct.pack_into("<I", opt, 0x10, text_va + 0x10)
    struct.pack_into("<Q", opt, 0x18, image_base)
    struct.pack_into("<I", opt, 0x20, sect_align)
    struct.pack_into("<I", opt, 0x24, file_align)
    struct.pack_into("<H", opt, 0x28, 6)
    struct.pack_into("<H", opt, 0x30, 6)
    struct.pack_into("<I", opt, 0x38, size_of_image)
    struct.pack_into("<I", opt, 0x3C, 0x200)
    struct.pack_into("<H", opt, 0x44, subsystem)
    struct.pack_into("<H", opt, 0x46, dll_characteristics)
    struct.pack_into("<I", opt, 0x6C, number_of_rva)
    for index, (rva, size) in enumerate(directories):
        struct.pack_into("<II", opt, 0x70 + index * 8, rva, size)

    if text_chars is None:
        text_chars = pe.IMAGE_SCN_CNT_CODE | pe.IMAGE_SCN_MEM_EXECUTE | pe.IMAGE_SCN_MEM_READ
    if rdata_chars is None:
        rdata_chars = pe.IMAGE_SCN_CNT_INITIALIZED_DATA | pe.IMAGE_SCN_MEM_READ
    rdata_raw_ptr = 0x400
    rdata_raw_size = 0x400
    if section_raw_overflow:
        rdata_raw_size = 0xFFFF0000
    sections = _pack_section(b".text", 0x200, text_va, 0x200, text_raw, text_chars)
    sections += _pack_section(
        b".rdata", 0x400, rdata_va, rdata_raw_size, rdata_raw_ptr, rdata_chars
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


def _optional_off(data: bytes) -> int:
    return struct.unpack_from("<I", data, 0x3C)[0] + 24


def _section_table_off(data: bytes) -> int:
    return _optional_off(data) + pe.OPTIONAL_HEADER64_SIZE


def mutate_u32(data: bytes, offset: int, value: int) -> bytes:
    out = bytearray(data)
    struct.pack_into("<I", out, offset, value)
    return bytes(out)


def mutate_size_of_image(data: bytes, value: int) -> bytes:
    return mutate_u32(data, _optional_off(data) + 0x38, value)


def mutate_section_chars(data: bytes, index: int, chars: int) -> bytes:
    return mutate_u32(data, _section_table_off(data) + index * 40 + 36, chars)


def mutate_directory(data: bytes, index: int, rva: int, size: int) -> bytes:
    out = bytearray(data)
    struct.pack_into("<II", out, _optional_off(data) + 0x70 + index * 8, rva, size)
    return bytes(out)


def mutate_export_func_rva(data: bytes, rva: int) -> bytes:
    record = pe.parse_pe32_plus_x86_64_dll(data)
    export = record.directories[pe.DIR_EXPORT]
    off = pe.rva_to_offset(record.sections, export.rva, pe.EXPORT_DIRECTORY_SIZE)
    funcs_rva = struct.unpack_from("<I", data, off + 28)[0]
    func_off = pe.rva_to_offset(record.sections, funcs_rva, 4)
    return mutate_u32(data, func_off, rva)


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
        pogo = _write(build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_POGO))
        pe.verify_windows_x86_64_dll(pogo, require_tools=False)


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
            pe.parse_pe32_plus_x86_64_dll(build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_VC_FEATURE))
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
        path = _write(build_pe(embed=b"/\x01\xffA"))
        pe.verify_windows_x86_64_dll(path, require_tools=False)
        path = _write(build_pe(embed=b"\\\xffJf\xffE"))
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
            good + "          1    0          uniffi_kardano_ed25519_bip32_signing_fn_func_sign (forwarded to kernel32.Foo)\n",
            good.replace("00001010", "00002010"),
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
        self.assertEqual(pe._align_up(0x201, 0x200), 0x400)
        with self.assertRaises(pe.PeError):
            pe._align_up(1, 3)
        with self.assertRaises(pe.PeError):
            pe._align_up(pe.UINT32_MAX, 0x1000)


class ExportTargetTests(unittest.TestCase):
    def test_valid_text_export_is_accepted(self) -> None:
        record = pe.parse_pe32_plus_x86_64_dll(build_pe())
        self.assertEqual(record.sign_exports[0].rva, 0x1010)
        section = pe.require_code_export_target(
            record.sections, record.sign_exports[0].rva, record.directories[pe.DIR_EXPORT]
        )
        self.assertEqual(section.name, ".text")

    def test_rdata_target_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(export_func_rvas=(0x21F0,)))
        self.assertIn("IMAGE_SCN_CNT_CODE", str(caught.exception))

    def test_writable_exec_text_is_rejected(self) -> None:
        fixture = build_pe()
        mutated = mutate_section_chars(
            fixture,
            0,
            pe.IMAGE_SCN_CNT_CODE | pe.IMAGE_SCN_MEM_EXECUTE | pe.IMAGE_SCN_MEM_WRITE,
        )
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(mutated)
        self.assertIn("writable", str(caught.exception))

    def test_forwarder_rva_inside_export_directory_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(export_func_rvas=(0x2000,)))
        self.assertIn("forwarder", str(caught.exception))

    def test_section_boundary_rva_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(export_func_rvas=(0x1200,)))

    def test_zero_and_overflow_rva_are_rejected(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(zero_export_rva=True))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(export_func_rvas=(0x5000,)))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(export_func_rvas=(0xFFFFFFFF,)))

    def test_mutated_export_rva_to_rdata_is_rejected(self) -> None:
        fixture = build_pe()
        mutated = mutate_export_func_rva(fixture, 0x21F0)
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(mutated)

    def test_dumpbin_corroborates_text_rva_and_rejects_rdata_or_forwarder(self) -> None:
        record = pe.parse_pe32_plus_x86_64_dll(build_pe())
        good = (
            "             8664 machine (x64)\n"
            "                 DLL\n"
            "             20B magic # (PE32+)\n"
            "          1    0 00001010 uniffi_kardano_ed25519_bip32_signing_fn_func_sign\n"
            "    kernel32.dll\n"
        )
        pe.require_dumpbin_corroboration(record, good)
        with self.assertRaises(pe.PeError):
            pe.require_dumpbin_corroboration(
                record, good.replace("00001010", "00002010")
            )
        with self.assertRaises(pe.PeError):
            pe.require_dumpbin_corroboration(
                record,
                good
                + "          1    0          uniffi_kardano_ed25519_bip32_signing_fn_func_sign (forwarded to kernel32.Foo)\n",
            )


class CanonicalDirectoryTests(unittest.TestCase):
    def test_mutated_size_of_image_is_rejected(self) -> None:
        fixture = build_pe()
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(mutate_size_of_image(fixture, 0x4000))
        self.assertIn("SizeOfImage", str(caught.exception))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(mutate_size_of_image(fixture, 0x2000))

    def test_unimplemented_nonempty_directory_fails(self) -> None:
        fixture = build_pe()
        mutated = mutate_directory(fixture, pe.DIR_ARCHITECTURE, 0x2000, 8)
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(mutated)
        mutated = mutate_directory(fixture, pe.DIR_CLR, 0x2000, 8)
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(mutated)
        mutated = mutate_directory(fixture, pe.DIR_BOUND_IMPORT, 0x2000, 8)
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(mutated)

    def test_security_directory_stays_empty(self) -> None:
        fixture = mutate_directory(build_pe(), pe.DIR_SECURITY, 0x400, 8)
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(fixture)

    def test_debug_repro_only_codeview_rejected_on_mutated_fixture(self) -> None:
        pe.parse_pe32_plus_x86_64_dll(build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_REPRO))
        pe.parse_pe32_plus_x86_64_dll(build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_POGO))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_CODEVIEW)
            )

    def test_exception_range_must_be_executable_nonoverlapping(self) -> None:
        good = build_pe(exception_entries=((0x1010, 0x1014, 0x1010),))
        pe.parse_pe32_plus_x86_64_dll(good)
        inverted = build_pe(exception_entries=((0x1014, 0x1010, 0x1010),))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(inverted)
        overlap = build_pe(
            exception_entries=((0x1010, 0x1020, 0x1010), (0x1018, 0x1030, 0x1010))
        )
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(overlap)
        rdata_target = build_pe(exception_entries=((0x21F0, 0x21F4, 0x21F0),))
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(rdata_target)
        padded = bytearray(build_pe(exception_entries=((0x1010, 0x1300, 0x1010),)))
        # Enlarge .text VirtualSize so EndAddress can sit in virtual-only padding.
        struct.pack_into("<I", padded, _section_table_off(bytes(padded)) + 8, 0x400)
        pe.parse_pe32_plus_x86_64_dll(bytes(padded))

    def test_reloc_malformed_and_unaligned_blocks(self) -> None:
        good_block = struct.pack("<II", 0x1000, 12) + struct.pack("<H", 0) + b"\x00\x00"
        pe.parse_pe32_plus_x86_64_dll(build_pe(reloc_block=good_block))
        short = struct.pack("<II", 0x1000, 4)
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(reloc_block=short))
        unaligned = struct.pack("<II", 0x1001, 8)
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(reloc_block=unaligned))

    def test_iat_first_thunk_must_land_inside_directory(self) -> None:
        pe.parse_pe32_plus_x86_64_dll(build_pe(iat_directory=True))
        fixture = build_pe(iat_directory=True)
        mutated = mutate_directory(fixture, pe.DIR_IAT, 0x21F0, 8)
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(mutated)

    def test_load_config_size_field_must_match(self) -> None:
        cfg = bytearray(0x40)
        struct.pack_into("<I", cfg, 0, 0x40)
        image = build_pe()
        # Place by mutating a nonempty load-config directory onto existing .rdata padding.
        placed = build_pe(
            directories_override={pe.DIR_LOAD_CONFIG: (0x21C0, 4)},
        )
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(placed)
        del image


class WindowsPathScanTests(unittest.TestCase):
    def _hits(self, payload: bytes) -> list[str]:
        return pe.scan_windows_forbidden_paths(payload)

    def test_drive_root_ascii_case_and_slash(self) -> None:
        for blob in (
            b"C:\\Users\\runneradmin\\work",
            b"c:\\users\\runneradmin\\work",
            b"C:/Users/runneradmin/work",
            b"d:\\a\\KardanoSDK\\KardanoSDK",
        ):
            with self.subTest(blob=blob):
                self.assertTrue(self._hits(blob), blob)

    def test_unc_ascii_and_slash(self) -> None:
        self.assertTrue(self._hits(b"\\\\server\\share\\obj"))
        self.assertTrue(self._hits(b"//server/share/obj"))
        self.assertFalse(self._hits(b"\\server\\share"))
        self.assertFalse(self._hits(b"\\\\server"))

    def test_utf16le_drive_and_unc(self) -> None:
        drive = "C:\\Users\\runner".encode("utf-16le")
        unc = "\\\\server\\share\\x".encode("utf-16le")
        self.assertTrue(self._hits(drive))
        self.assertTrue(self._hits(unc))
        self.assertFalse(self._hits("C:Users".encode("utf-16le")))

    def test_embedded_unterminated_and_control_adjacency(self) -> None:
        self.assertTrue(self._hits(b"xxC:\\Users\\x"))
        self.assertTrue(self._hits(b"C:\\Users\\x\x00more"))
        self.assertTrue(self._hits(b"C:\\Users\\x\x01more"))
        self.assertTrue(self._hits(b"C:\\Users\\\xff"))
        # Binary "\\" plus non-ASCII is not a UNC (run 32718908858).
        self.assertFalse(self._hits(b"\\\xffJf\xffE\xff\x00\xffBf"))
        self.assertFalse(self._hits(b"\\\\\xffserver\\share"))

    def test_prefixes_and_near_misses(self) -> None:
        self.assertFalse(self._hits(b"C:Users\\x"))
        self.assertFalse(self._hits(b"C:"))
        self.assertFalse(self._hits(b"not a path"))
        self.assertTrue(self._hits(b"prefixC:\\Windows\\x"))

    def test_allowed_remap_is_not_a_hit(self) -> None:
        self.assertFalse(any("cargo-target" in hit for hit in self._hits(b"/cargo-target/release/out")))

    def test_embedded_drive_in_pe_fixture_is_rejected(self) -> None:
        path = _write(build_pe(embed=b"C:\\Users\\runneradmin\\work\\x"))
        with self.assertRaises(pe.PeError):
            pe.verify_windows_x86_64_dll(path, require_tools=False)
        path = _write(build_pe(embed="D:\\a\\repo\\x".encode("utf-16le")))
        with self.assertRaises(pe.PeError):
            pe.verify_windows_x86_64_dll(path, require_tools=False)


def _resource_tree(
    *,
    named: bool = False,
    name: str = "NAME",
    name_offset: int | None = None,
    id_value: int = 16,
    data_rva: int = 0x1010,
    data_size: int = 4,
    codepage: int = 0,
    reserved: int = 0,
    cycle: bool = False,
    truncate_leaf: bool = False,
    subdirectory: int | None = None,
) -> bytes:
    named_count = 1 if named else 0
    id_count = 0 if named else 1
    header = struct.pack("<IIHHHH", 0, 0, 0, 0, named_count, id_count)
    name_field = id_value
    if named:
        name_field = (40 if name_offset is None else name_offset) | 0x80000000
    if cycle:
        return header + struct.pack("<II", name_field, 0x80000000)
    if subdirectory is not None:
        return header + struct.pack("<II", name_field, subdirectory | 0x80000000)
    blob = header + struct.pack("<II", name_field, 24)
    if not truncate_leaf:
        blob += struct.pack("<IIII", data_rva, data_size, codepage, reserved)
    if named:
        encoded = name.encode("utf-16-le")
        blob = blob.ljust(40, b"\x00")
        blob += struct.pack("<H", len(encoded) // 2) + encoded
    return blob


class ImportExactnessTests(unittest.TestCase):
    def test_oft_zero_valid_uses_iat_as_ilt(self) -> None:
        pe.parse_pe32_plus_x86_64_dll(build_pe(oft_zero=True))

    def test_divergent_iat_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(divergent_iat=True))
        self.assertTrue(
            "diverge" in str(caught.exception).lower()
            or "reserved" in str(caught.exception).lower(),
            caught.exception,
        )

    def test_short_iat_directory_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(iat_directory_size=8))
        self.assertIn("IAT", str(caught.exception))

    def test_iat_terminator_outside_directory_is_rejected(self) -> None:
        fixture = build_pe()
        record = pe.parse_pe32_plus_x86_64_dll(fixture)
        iat = record.directories[pe.DIR_IAT]
        mutated = mutate_directory(fixture, pe.DIR_IAT, iat.rva, iat.size - 8)
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(mutated)
        self.assertIn("terminator", str(caught.exception).lower())

    def test_oft_zero_invalid_missing_terminator(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(oft_zero=True, omit_iat_terminator=True)
            )

    def test_ordinal_name_mismatch_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(divergent_iat=True))

    def test_missing_ilt_terminator_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(build_pe(omit_ilt_terminator=True))

    def test_reserved_bits_and_overlap_are_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(thunk_reserved_bits=True))
        self.assertIn("reserved", str(caught.exception).lower())
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(overlap_iat_with_ilt=True))
        self.assertTrue(
            "overlap" in str(caught.exception).lower()
            or "diverge" in str(caught.exception).lower(),
            caught.exception,
        )

    def test_missing_iat_directory_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(iat_directory=False))
        self.assertIn("IAT", str(caught.exception))


class ExportContainmentTests(unittest.TestCase):
    def test_baseline_export_directory_covers_tables_and_names(self) -> None:
        fixture = build_pe()
        record = pe.parse_pe32_plus_x86_64_dll(fixture)
        export = record.directories[pe.DIR_EXPORT]
        self.assertGreater(export.size, pe.EXPORT_DIRECTORY_SIZE)
        off = pe.rva_to_offset(record.sections, export.rva, pe.EXPORT_DIRECTORY_SIZE)
        funcs_rva = struct.unpack_from("<I", fixture, off + 28)[0]
        self.assertGreaterEqual(funcs_rva, export.rva)
        self.assertLess(funcs_rva, export.rva + export.size)

    def test_table_outside_export_directory_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(export_directory_size=pe.EXPORT_DIRECTORY_SIZE)
            )
        self.assertIn("outside the data directory", str(caught.exception))

    def test_exact_export_boundary_is_accepted(self) -> None:
        pe.parse_pe32_plus_x86_64_dll(build_pe())

    def test_overlapping_export_tables_are_rejected(self) -> None:
        fixture = build_pe()
        record = pe.parse_pe32_plus_x86_64_dll(fixture)
        export = record.directories[pe.DIR_EXPORT]
        off = pe.rva_to_offset(record.sections, export.rva, pe.EXPORT_DIRECTORY_SIZE)
        # Point AddressOfNames at AddressOfFunctions.
        funcs_rva = struct.unpack_from("<I", fixture, off + 28)[0]
        mutated = mutate_u32(fixture, off + 32, funcs_rva)
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(mutated)
        self.assertIn("overlap", str(caught.exception).lower())

    def test_function_rva_inside_export_span_is_forwarder(self) -> None:
        fixture = build_pe()
        record = pe.parse_pe32_plus_x86_64_dll(fixture)
        export = record.directories[pe.DIR_EXPORT]
        mutated = mutate_export_func_rva(fixture, export.rva + 8)
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(mutated)
        self.assertIn("forwarder", str(caught.exception))


class DebugReferenceTests(unittest.TestCase):
    def test_zero_size_requires_zero_pointers(self) -> None:
        pe.parse_pe32_plus_x86_64_dll(build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_REPRO))
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(
                    debug_type=pe.IMAGE_DEBUG_TYPE_REPRO,
                    debug_size_of_data=0,
                    debug_address=0x2100,
                    debug_pointer=0,
                )
            )
        self.assertIn("zero-size", str(caught.exception))

    def test_one_zero_one_nonzero_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(
                    debug_type=pe.IMAGE_DEBUG_TYPE_REPRO,
                    debug_payload=b"repro",
                    debug_pointer=0,
                )
            )
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(
                    debug_type=pe.IMAGE_DEBUG_TYPE_REPRO,
                    debug_payload=b"repro",
                    debug_address=0,
                )
            )

    def test_address_pointer_mismatch_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(
                    debug_type=pe.IMAGE_DEBUG_TYPE_REPRO,
                    debug_payload=repro_hash_payload(),
                    debug_pointer=0x480,
                )
            )
        self.assertIn("does not map", str(caught.exception))

    def test_duplicate_debug_type_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_REPRO, debug_duplicate=True)
            )
        self.assertIn("duplicate", str(caught.exception))

    def test_empty_and_hash32_repro_are_accepted(self) -> None:
        empty = pe.parse_pe32_plus_x86_64_dll(build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_REPRO))
        self.assertEqual(empty.debug_entries[0].detail, "empty")
        hashed = pe.parse_pe32_plus_x86_64_dll(
            build_pe(
                debug_type=pe.IMAGE_DEBUG_TYPE_REPRO,
                debug_payload=repro_hash_payload(),
            )
        )
        self.assertTrue(hashed.debug_entries[0].detail.startswith("hash-32"))

    def test_arbitrary_repro_bytes_are_rejected(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_REPRO, debug_payload=b"repro")
            )
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(
                    debug_type=pe.IMAGE_DEBUG_TYPE_REPRO,
                    debug_payload=struct.pack("<I", 16) + b"\x00" * 16,
                )
            )
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(
                    debug_type=pe.IMAGE_DEBUG_TYPE_REPRO,
                    debug_payload=repro_hash_payload() + b"\x00",
                )
            )

    def test_valid_ltcg_pogo_is_accepted(self) -> None:
        record = pe.parse_pe32_plus_x86_64_dll(build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_POGO))
        self.assertIn("entries=1", record.debug_entries[0].detail)

    def test_pogo_malformed_signature_and_entries_are_rejected(self) -> None:
        cases = [
            pogo_payload(signature=0x41414141),
            pogo_payload(entries=((0x1010, 4, ".text"),))[:-1],
            struct.pack("<I", pe.IMAGE_DEBUG_POGO_SIGNATURE_LTCG)
            + struct.pack("<II", 0x1010, 4)
            + b"text",
            pogo_payload(entries=((0x1010, 4, ".text"),)) + b"\x01\x00\x00\x00",
            pogo_payload(entries=((0x5000, 4, ".text"),)),
            pogo_payload(entries=((0x1010, 4, ".text"), (0x1010, 4, ".text"))),
            pogo_payload(entries=((0x1010, 8, ".text"), (0x1014, 8, ".rdata"))),
        ]
        for blob in cases:
            with self.subTest(blob=blob[:8]):
                with self.assertRaises(pe.PeError):
                    pe.parse_pe32_plus_x86_64_dll(
                        build_pe(debug_type=pe.IMAGE_DEBUG_TYPE_POGO, debug_payload=blob)
                    )


class ResourceTreeTests(unittest.TestCase):
    def test_id_leaf_is_accepted(self) -> None:
        pe.parse_pe32_plus_x86_64_dll(build_pe(resource_blob=_resource_tree()))

    def test_named_utf16_is_accepted(self) -> None:
        pe.parse_pe32_plus_x86_64_dll(
            build_pe(resource_blob=_resource_tree(named=True, name="OK"))
        )

    def test_malformed_named_offset_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(resource_blob=_resource_tree(named=True, name_offset=0x200))
            )

    def test_cycle_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(resource_blob=_resource_tree(cycle=True)))
        self.assertIn("cycle", str(caught.exception))

    def test_truncated_leaf_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(resource_blob=_resource_tree(truncate_leaf=True))
            )

    def test_reserved_and_codepage_must_be_zero(self) -> None:
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(resource_blob=_resource_tree(reserved=1))
            )
        with self.assertRaises(pe.PeError):
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(resource_blob=_resource_tree(codepage=1252))
            )

    def test_name_offsets_into_header_or_table_are_rejected(self) -> None:
        for offset in (0, 8, 16):
            with self.subTest(offset=offset):
                with self.assertRaises(pe.PeError) as caught:
                    pe.parse_pe32_plus_x86_64_dll(
                        build_pe(
                            resource_blob=_resource_tree(named=True, name_offset=offset)
                        )
                    )
                self.assertIn("overlap", str(caught.exception))

    def test_exact_shared_data_entry_is_allowed(self) -> None:
        header = struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 2)
        entries = struct.pack("<II", 1, 32) + struct.pack("<II", 2, 32)
        leaf = struct.pack("<IIII", 0x1010, 4, 0, 0)
        pe.parse_pe32_plus_x86_64_dll(build_pe(resource_blob=header + entries + leaf))

    def test_exact_reuse_kind_mismatch_is_rejected(self) -> None:
        # Data-entry offset 0 reuses the directory header interval.
        header = struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1)
        entry = struct.pack("<II", 1, 0)
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(resource_blob=header + entry))
        self.assertTrue(
            "overlap" in str(caught.exception) or "kind" in str(caught.exception),
            caught.exception,
        )

    def test_partial_data_entry_overlap_is_rejected(self) -> None:
        header = struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 2)
        entries = struct.pack("<II", 1, 32) + struct.pack("<II", 2, 40)
        leafs = struct.pack("<IIII", 0x1010, 4, 0, 0) + struct.pack(
            "<IIII", 0x1010, 4, 0, 0
        )
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(resource_blob=header + entries + leafs))
        self.assertIn("overlap", str(caught.exception))

    def test_nested_subdirectory_overlapping_parent_table_is_rejected(self) -> None:
        header = struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1)
        entry = struct.pack("<II", 1, 8 | 0x80000000)
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(resource_blob=header + entry))
        self.assertTrue(
            "overlap" in str(caught.exception) or "cycle" in str(caught.exception),
            caught.exception,
        )


class TlsCallbackTests(unittest.TestCase):
    def test_terminated_code_callback_is_accepted(self) -> None:
        pe.parse_pe32_plus_x86_64_dll(build_pe(tls_callbacks=(0x1010,)))

    def test_missing_terminator_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(
                build_pe(tls_callbacks=(0x1010,), tls_unterminated=True)
            )
        self.assertTrue(
            "terminated" in str(caught.exception).lower()
            or "out of range" in str(caught.exception).lower()
            or "not in" in str(caught.exception).lower(),
            caught.exception,
        )

    def test_callback_in_data_section_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(tls_callbacks=(0x2100,)))
        self.assertIn("executable", str(caught.exception))

    def test_inconsistent_raw_range_is_rejected(self) -> None:
        with self.assertRaises(pe.PeError) as caught:
            pe.parse_pe32_plus_x86_64_dll(build_pe(tls_inconsistent_raw=True))
        self.assertIn("inconsistent", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
