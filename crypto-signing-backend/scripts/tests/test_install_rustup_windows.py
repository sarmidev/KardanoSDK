"""Host-triple coverage for the pinned rustup-init installer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import install_rustup as rustup  # noqa: E402


class HostTripleTests(unittest.TestCase):
    def test_windows_x86_64_maps_to_msvc(self) -> None:
        self.assertEqual(
            rustup.host_triple("Windows", "AMD64"),
            "x86_64-pc-windows-msvc",
        )
        self.assertEqual(
            rustup.rustup_init_filename("x86_64-pc-windows-msvc"),
            "rustup-init.exe",
        )
        self.assertIn("x86_64-pc-windows-msvc", rustup.RUSTUP_INIT_SHA256)

    def test_windows_arm_is_rejected(self) -> None:
        with self.assertRaises(rustup.InstallError):
            rustup.host_triple("Windows", "ARM64")

    def test_rustc_release_is_exact_token(self) -> None:
        self.assertEqual(
            rustup.parse_rustc_release("rustc 1.97.0 (2d8144b78 2026-07-07)"),
            "1.97.0",
        )
        self.assertEqual(
            rustup.parse_rustc_release("rustc 1.97.1 (8bab26f4f 2026-07-14)"),
            "1.97.1",
        )
        self.assertNotEqual(
            rustup.parse_rustc_release("rustc 1.97.1 (8bab26f4f 2026-07-14)"),
            "1.97.0",
        )


if __name__ == "__main__":
    unittest.main()
