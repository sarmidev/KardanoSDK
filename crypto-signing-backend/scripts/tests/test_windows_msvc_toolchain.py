"""Tests for the pinned windows-2022 MSVC link.exe selection."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import native_toolchain as toolchain  # noqa: E402


PINNED_LINK_BANNER = (
    f"Microsoft (R) Incremental Linker Version {toolchain.EXPECTED_MSVC_LINK_VERSION}"
)


def _fake_kits(
    root: Path, version: str = toolchain.EXPECTED_WINDOWS_SDK_VERSION
) -> Path:
    kits = root / "Kits"
    files = (
        kits / "Include" / version / "um" / "Windows.h",
        kits / "Include" / version / "ucrt" / "stdlib.h",
        kits / "Include" / version / "shared" / "winapifamily.h",
        kits / "Lib" / version / "um" / "x64" / "kernel32.lib",
        kits / "Lib" / version / "ucrt" / "x64" / "libucrt.lib",
    )
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    (kits / "bin" / version / "x64").mkdir(parents=True, exist_ok=True)
    return kits


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
                "Microsoft (R) Incremental Linker Version 14.44.35228.0"
            ),
            "14.44.35228.0",
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
        kits = _fake_kits(root)
        env = {"PATH": str(root / "other"), "ImageOS": "win22", "ImageVersion": "20220814.1"}
        info = toolchain.activate_pinned_msvc_linker(
            env,
            link_path=link,
            where_first=link,
            banner=PINNED_LINK_BANNER,
            kits_root=kits,
        )
        self.assertTrue(env["PATH"].startswith(str(link.parent)))
        self.assertEqual(env["KARDANO_MSVC_LINK"], str(link))
        self.assertEqual(env["KARDANO_MSVC_TOOLSET"], "14.44.35207")
        self.assertEqual(env["CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER"], str(link))
        self.assertEqual(env["KARDANO_WINDOWS_SDK_VERSION"], "10.0.26100.0")
        self.assertEqual(env["WindowsSDKVersion"], "10.0.26100.0\\")
        self.assertIn(str(kits / "Include" / "10.0.26100.0" / "um"), env["INCLUDE"])
        self.assertEqual(info["msvc_toolset"], "14.44.35207")
        self.assertEqual(info["link_version"], "14.44.35228.0")
        self.assertEqual(info["windows_sdk"]["version"], "10.0.26100.0")
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
                banner=PINNED_LINK_BANNER,
                kits_root=_fake_kits(root),
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
                kits_root=_fake_kits(root),
            )


class WindowsSdkPinTests(unittest.TestCase):
    def test_missing_kits_root_fails(self) -> None:
        root = Path(tempfile.mkdtemp())
        with self.assertRaises(toolchain.ToolchainError) as caught:
            toolchain.require_windows_sdk(kits_root=root / "missing-kits")
        self.assertIn("Windows Kits root is missing", str(caught.exception))

    def test_drifted_sdk_version_fails(self) -> None:
        root = Path(tempfile.mkdtemp())
        kits = _fake_kits(root, "10.0.22621.0")
        with self.assertRaises(toolchain.ToolchainError) as caught:
            toolchain.require_windows_sdk(kits_root=kits)
        self.assertIn("10.0.26100.0", str(caught.exception))

    def test_missing_required_header_fails(self) -> None:
        root = Path(tempfile.mkdtemp())
        kits = _fake_kits(root)
        (kits / "Include" / "10.0.26100.0" / "um" / "Windows.h").unlink()
        with self.assertRaises(toolchain.ToolchainError) as caught:
            toolchain.require_windows_sdk(kits_root=kits)
        self.assertIn("Windows.h", str(caught.exception))

    def test_activate_fails_when_sdk_paths_missing(self) -> None:
        root = Path(tempfile.mkdtemp())
        link = _fake_link(root)
        env = {"PATH": str(link.parent)}
        with self.assertRaises(toolchain.ToolchainError):
            toolchain.activate_pinned_msvc_linker(
                env,
                link_path=link,
                where_first=link,
                banner=PINNED_LINK_BANNER,
                kits_root=root / "missing-kits",
            )


if __name__ == "__main__":
    unittest.main()
