"""Tests for the pinned windows-2022 MSVC link.exe selection."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import native_toolchain as toolchain  # noqa: E402


def _fake_link(root: Path, toolset: str = toolchain.EXPECTED_MSVC_TOOLSET) -> Path:
    link = (
        root
        / "VS"
        / "VC"
        / "Tools"
        / "MSVC"
        / toolset
        / "bin"
        / toolchain.MSVC_HOST_ARCH
        / toolchain.MSVC_TARGET_ARCH
        / "link.exe"
    )
    link.parent.mkdir(parents=True, exist_ok=True)
    link.write_bytes(b"MZ")
    return link


class MsvcDiscoveryTests(unittest.TestCase):
    def test_parse_link_version_and_toolset_folder(self) -> None:
        self.assertEqual(
            toolchain.parse_link_version(
                "Microsoft (R) Incremental Linker Version 14.44.35221.0"
            ),
            "14.44.35221.0",
        )
        self.assertEqual(toolchain.parse_link_version("no version here"), "")
        link = Path(
            r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise"
            r"\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\link.exe"
        )
        self.assertEqual(toolchain.parse_msvc_toolset_from_path(link), "14.44.35207")

    def test_discover_selects_pinned_toolset_and_rejects_drift(self) -> None:
        root = Path(tempfile.mkdtemp())
        pinned = _fake_link(root)
        other = _fake_link(root, "14.43.34808")
        found = toolchain.discover_msvc_link(vswhere_output=str(pinned))
        self.assertEqual(found, pinned)
        with self.assertRaises(toolchain.ToolchainError):
            toolchain.discover_msvc_link(
                expected_toolset="14.44.35207",
                vswhere_output=str(other),
                glob_matches=[],
            )
        with self.assertRaises(toolchain.ToolchainError):
            toolchain.discover_msvc_link(vswhere_output="", glob_matches=[])


class MsvcActivateTests(unittest.TestCase):
    def test_activate_prepends_hostx64_and_records_image(self) -> None:
        root = Path(tempfile.mkdtemp())
        link = _fake_link(root)
        env = {"PATH": str(root / "other"), "ImageOS": "win22", "ImageVersion": "20220814.1"}
        info = toolchain.activate_pinned_msvc_linker(
            env,
            link_path=link,
            where_first=link,
            banner="Microsoft (R) Incremental Linker Version 14.44.35221.0",
            kits_root=root / "missing-kits",
        )
        self.assertTrue(env["PATH"].startswith(str(link.parent)))
        self.assertEqual(env["KARDANO_MSVC_LINK"], str(link))
        self.assertEqual(env["KARDANO_MSVC_TOOLSET"], "14.44.35207")
        self.assertEqual(env["CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER"], str(link))
        self.assertEqual(info["msvc_toolset"], "14.44.35207")
        self.assertEqual(info["link_version"], "14.44.35221.0")
        self.assertFalse(info["hosted_image_immutable"])
        self.assertEqual(info["where_link"], str(link))

    def test_activate_fails_when_where_first_differs(self) -> None:
        root = Path(tempfile.mkdtemp())
        link = _fake_link(root)
        other = root / "other" / "link.exe"
        other.parent.mkdir(parents=True)
        other.write_bytes(b"MZ")
        env = {"PATH": str(other.parent)}
        with self.assertRaises(toolchain.ToolchainError) as caught:
            toolchain.activate_pinned_msvc_linker(
                env,
                link_path=link,
                where_first=other,
                banner="Microsoft (R) Incremental Linker Version 14.44.35221.0",
            )
        self.assertIn("where.exe", str(caught.exception))

    def test_activate_fails_on_link_version_drift(self) -> None:
        root = Path(tempfile.mkdtemp())
        link = _fake_link(root)
        env = {"PATH": str(link.parent)}
        with self.assertRaises(toolchain.ToolchainError):
            toolchain.activate_pinned_msvc_linker(
                env,
                link_path=link,
                where_first=link,
                banner="Microsoft (R) Incremental Linker Version 14.43.34808.0",
            )


if __name__ == "__main__":
    unittest.main()
