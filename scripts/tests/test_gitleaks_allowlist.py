"""Match-level allowlist tests for the cited CIP-19 Gitleaks false positive."""

from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_gitleaks  # noqa: E402
import gitleaks_allowlist as allowlist  # noqa: E402
import install_gitleaks  # noqa: E402

ALLOWED_WALLET = (
    "wallet/src/jvmTest/kotlin/org/sarmidev/kardano/wallet/"
    "ReadOnlyWalletRestoreDesktopTest.kt"
)
ALLOWED_CURRENT = (
    "crypto/src/androidDeviceTest/kotlin/org/sarmidev/kardano/crypto/"
    "derivation/PublicKeyProjectionDeviceTest.kt"
)
ALLOWED_HISTORICAL = (
    "crypto/src/androidDeviceTest/kotlin/org/sarmidev/kardano/crypto/"
    "PublicKeyProjectionDeviceTest.kt"
)
OTHER_PATH = "wallet/src/commonMain/kotlin/org/sarmidev/kardano/wallet/Phase1FixtureIdentity.kt"
# Same length and similar entropy as the cited vector, but a different value.
# Confirmed independently to still match generic-api-key.
DIFFERENT_HEX = "c1b2a3948576d0e1f2a3b4c5d6e708192a3b4c5d6e708192a3b4c5d6"
CITED = allowlist.CITED_CIP19_PAYMENT_CREDENTIAL


def _assignment(value: str) -> str:
    return f'    private val cip19PaymentCredential = "{value}"\n'


class AllowlistLogicTests(unittest.TestCase):
    def test_cited_value_on_exact_paths_is_allowlisted(self) -> None:
        for path in (ALLOWED_WALLET, ALLOWED_CURRENT, ALLOWED_HISTORICAL):
            self.assertTrue(allowlist.is_allowlisted(CITED, path), path)

    def test_different_value_on_allowed_path_is_not_allowlisted(self) -> None:
        self.assertFalse(allowlist.is_allowlisted(DIFFERENT_HEX, ALLOWED_WALLET))
        self.assertNotEqual(DIFFERENT_HEX, CITED)

    def test_cited_value_outside_allowed_paths_is_not_allowlisted(self) -> None:
        self.assertFalse(allowlist.is_allowlisted(CITED, OTHER_PATH))
        self.assertFalse(allowlist.is_allowlisted(CITED, "README.md"))


class GitleaksIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.binary = install_gitleaks.DEFAULT_DEST
        if not cls.binary.is_file():
            cls.binary = install_gitleaks.install()

    def _scan_fixture(self, relative: str, value: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_text(_assignment(value), encoding="utf-8")
            (root / ".gitleaks.toml").write_text(
                (REPO_ROOT / ".gitleaks.toml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            command = check_gitleaks.build_command(
                binary=self.binary,
                source=root,
                config=root / ".gitleaks.toml",
                no_git=True,
            )
            completed = subprocess.run(
                command, cwd=root, capture_output=True, text=True
            )
            return completed.returncode

    def test_cited_value_on_allowed_path_passes(self) -> None:
        self.assertEqual(self._scan_fixture(ALLOWED_WALLET, CITED), 0)

    def test_different_value_on_allowed_path_fails(self) -> None:
        self.assertNotEqual(self._scan_fixture(ALLOWED_WALLET, DIFFERENT_HEX), 0)

    def test_cited_value_on_other_path_fails(self) -> None:
        self.assertNotEqual(self._scan_fixture(OTHER_PATH, CITED), 0)


class InstallHelperTests(unittest.TestCase):
    def test_archive_name_for_supported_platforms(self) -> None:
        self.assertIn("darwin_arm64", install_gitleaks.archive_name_for("Darwin", "arm64"))
        self.assertIn("linux_x64", install_gitleaks.archive_name_for("Linux", "x86_64"))
        self.assertIn("linux_arm64", install_gitleaks.archive_name_for("Linux", "aarch64"))

    def test_unsupported_platform_raises(self) -> None:
        with self.assertRaises(install_gitleaks.InstallError):
            install_gitleaks.archive_name_for("Windows", "amd64")

    def test_checksum_mismatch_is_rejected(self) -> None:
        with self.assertRaises(install_gitleaks.InstallError):
            install_gitleaks.verify_checksum(b"not-the-file", "00" * 32, "label")

    def test_checksums_file_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "gitleaks"
            with self.assertRaises(install_gitleaks.InstallError):
                install_gitleaks.install(
                    dest=dest,
                    system="Linux",
                    machine="x86_64",
                    checksums_bytes=b"not-the-official-checksums\n",
                    archive_bytes=b"unused",
                )

    def test_extracts_verified_archive(self) -> None:
        archive_name = install_gitleaks.archive_name_for("Linux", "x86_64")
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "payload"
            payload.mkdir()
            (payload / "gitleaks").write_bytes(b"#!/bin/sh\necho fixture\n")
            archive_path = Path(tmp) / archive_name
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(payload / "gitleaks", arcname="gitleaks")
            archive_bytes = archive_path.read_bytes()
            listed = install_gitleaks.sha256_bytes(archive_bytes)
            checksums = f"{listed}  {archive_name}\n".encode("ascii")
            dest = Path(tmp) / "out" / "gitleaks"
            original_checksums = install_gitleaks.CHECKSUMS_SHA256
            original_archive = install_gitleaks.ARCHIVE_SHA256[archive_name]
            try:
                install_gitleaks.CHECKSUMS_SHA256 = install_gitleaks.sha256_bytes(checksums)
                install_gitleaks.ARCHIVE_SHA256[archive_name] = listed
                installed = install_gitleaks.install(
                    dest=dest,
                    system="Linux",
                    machine="x86_64",
                    checksums_bytes=checksums,
                    archive_bytes=archive_bytes,
                )
            finally:
                install_gitleaks.CHECKSUMS_SHA256 = original_checksums
                install_gitleaks.ARCHIVE_SHA256[archive_name] = original_archive
            self.assertTrue(installed.is_file())
            self.assertEqual(installed.read_bytes(), b"#!/bin/sh\necho fixture\n")


if __name__ == "__main__":
    unittest.main()
