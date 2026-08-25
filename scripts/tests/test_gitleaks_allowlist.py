"""Match-level allowlist and installer tests."""

from __future__ import annotations

import os
import stat
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
ALLOWED_HELPER = "scripts/gitleaks_allowlist.py"
OTHER_PATH = "wallet/src/commonMain/kotlin/org/sarmidev/kardano/wallet/Phase1FixtureIdentity.kt"
DIFFERENT_HEX = "c1b2a3948576d0e1f2a3b4c5d6e708192a3b4c5d6e708192a3b4c5d6"


def _cited() -> str:
    return allowlist.cited_vector()


def _assignment(value: str) -> str:
    return f'    private val cip19PaymentCredential = "{value}"\n'


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "review@example.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Review"], cwd=root, check=True)


class AllowlistLogicTests(unittest.TestCase):
    def test_cited_value_on_exact_paths_is_allowlisted(self) -> None:
        cited = _cited()
        for path in (ALLOWED_WALLET, ALLOWED_CURRENT, ALLOWED_HISTORICAL, ALLOWED_HELPER):
            self.assertTrue(allowlist.is_allowlisted(cited, path), path)

    def test_different_value_on_allowed_path_is_not_allowlisted(self) -> None:
        self.assertFalse(allowlist.is_allowlisted(DIFFERENT_HEX, ALLOWED_WALLET))
        self.assertNotEqual(DIFFERENT_HEX, _cited())

    def test_cited_value_outside_allowed_paths_is_not_allowlisted(self) -> None:
        cited = _cited()
        self.assertFalse(allowlist.is_allowlisted(cited, OTHER_PATH))
        self.assertFalse(allowlist.is_allowlisted(cited, "README.md"))

    def test_path_prefix_is_not_allowlisted(self) -> None:
        self.assertFalse(allowlist.is_allowlisted(_cited(), f"extra/{ALLOWED_WALLET}"))

    def test_path_suffix_is_not_allowlisted(self) -> None:
        self.assertFalse(allowlist.is_allowlisted(_cited(), f"{ALLOWED_WALLET}.bak"))

    def test_alternate_separator_is_not_allowlisted(self) -> None:
        windows = ALLOWED_WALLET.replace("/", "\\")
        self.assertFalse(allowlist.is_allowlisted(_cited(), windows))


class GitleaksIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.binary = install_gitleaks.DEFAULT_DEST
        if not cls.binary.is_file():
            cls.binary = install_gitleaks.install()

    def _scan_git_fixture(self, relative: str, value: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_text(_assignment(value), encoding="utf-8")
            (root / ".gitleaks.toml").write_bytes(
                (REPO_ROOT / ".gitleaks.toml").read_bytes()
            )
            _init_git_repo(root)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            command = check_gitleaks.build_command(
                binary=self.binary,
                source=root,
                config=root / ".gitleaks.toml",
                no_git=False,
            )
            completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
            return completed.returncode

    def test_cited_value_on_allowed_path_passes(self) -> None:
        self.assertEqual(self._scan_git_fixture(ALLOWED_WALLET, _cited()), 0)

    def test_cited_value_on_helper_path_passes(self) -> None:
        self.assertEqual(self._scan_git_fixture(ALLOWED_HELPER, _cited()), 0)

    def test_different_value_on_allowed_path_fails(self) -> None:
        self.assertNotEqual(self._scan_git_fixture(ALLOWED_WALLET, DIFFERENT_HEX), 0)

    def test_cited_value_on_other_path_fails(self) -> None:
        self.assertNotEqual(self._scan_git_fixture(OTHER_PATH, _cited()), 0)

    def test_cited_value_on_prefixed_path_fails(self) -> None:
        self.assertNotEqual(self._scan_git_fixture(f"extra/{ALLOWED_WALLET}", _cited()), 0)

    def test_cited_value_on_suffixed_path_fails(self) -> None:
        self.assertNotEqual(self._scan_git_fixture(f"{ALLOWED_WALLET}.bak", _cited()), 0)


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

    def _install_fixture(
        self,
        dest: Path,
        payload: bytes = b"#!/bin/sh\necho fixture\n",
        member_mode: int = 0o755,
        member_name: str = "gitleaks",
    ) -> Path:
        archive_name = install_gitleaks.archive_name_for("Linux", "x86_64")
        scratch = dest.parent if dest.parent.exists() else dest.parent.parent
        scratch.mkdir(parents=True, exist_ok=True)
        archive_path = scratch / archive_name
        with tarfile.open(archive_path, "w:gz") as archive:
            info = tarfile.TarInfo(name=member_name)
            info.size = len(payload)
            info.mode = member_mode
            import io

            archive.addfile(info, io.BytesIO(payload))
        archive_bytes = archive_path.read_bytes()
        listed = install_gitleaks.sha256_bytes(archive_bytes)
        checksums = f"{listed}  {archive_name}\n".encode("ascii")
        original_checksums = install_gitleaks.CHECKSUMS_SHA256
        original_archive = install_gitleaks.ARCHIVE_SHA256[archive_name]
        try:
            install_gitleaks.CHECKSUMS_SHA256 = install_gitleaks.sha256_bytes(checksums)
            install_gitleaks.ARCHIVE_SHA256[archive_name] = listed
            return install_gitleaks.install(
                dest=dest,
                system="Linux",
                machine="x86_64",
                checksums_bytes=checksums,
                archive_bytes=archive_bytes,
            )
        finally:
            install_gitleaks.CHECKSUMS_SHA256 = original_checksums
            install_gitleaks.ARCHIVE_SHA256[archive_name] = original_archive

    def test_extracts_verified_archive_with_exact_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out" / "gitleaks"
            installed = self._install_fixture(dest)
            self.assertTrue(installed.is_file())
            self.assertFalse(installed.is_symlink())
            self.assertEqual(installed.read_bytes(), b"#!/bin/sh\necho fixture\n")
            self.assertEqual(stat.S_IMODE(installed.stat().st_mode), 0o755)

    def test_refuses_destination_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real-binary"
            real.write_bytes(b"keep-me\n")
            dest = Path(tmp) / "gitleaks"
            dest.symlink_to(real)
            with self.assertRaises(install_gitleaks.InstallError):
                self._install_fixture(dest)
            self.assertEqual(real.read_bytes(), b"keep-me\n")
            self.assertTrue(dest.is_symlink())

    def test_world_writable_archive_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "gitleaks"
            with self.assertRaises(install_gitleaks.InstallError):
                self._install_fixture(dest, member_mode=0o777)
            self.assertFalse(dest.exists())

    def test_write_all_bytes_retries_partial_writes(self) -> None:
        chunks: list[bytes] = []

        def write_one(_fd: int, data) -> int:
            chunks.append(bytes(data[:1]))
            return 1

        payload = b"abcdef"
        install_gitleaks.write_all_bytes(3, payload, write=write_one)
        self.assertEqual(b"".join(chunks), payload)
        self.assertEqual(len(chunks), len(payload))

    def test_write_all_bytes_rejects_zero_progress(self) -> None:
        with self.assertRaises(install_gitleaks.InstallError):
            install_gitleaks.write_all_bytes(3, b"abc", write=lambda _fd, _data: 0)

    def test_write_all_bytes_rejects_negative_progress(self) -> None:
        with self.assertRaises(install_gitleaks.InstallError):
            install_gitleaks.write_all_bytes(3, b"abc", write=lambda _fd, _data: -1)

    def test_write_all_bytes_retries_interrupted(self) -> None:
        calls = {"n": 0}

        def write(_fd: int, data) -> int:
            calls["n"] += 1
            if calls["n"] == 1:
                raise InterruptedError
            return len(data)

        install_gitleaks.write_all_bytes(3, b"abc", write=write)
        self.assertEqual(calls["n"], 2)

    def test_write_failure_closes_and_unlinks_temp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "gitleaks"

            def boom(_fd: int, _data) -> int:
                raise OSError("disk full")

            with self.assertRaises(OSError):
                install_gitleaks._write_atomic_binary(dest, b"payload-bytes", write=boom)
            self.assertFalse(dest.exists())
            leftover = list(Path(tmp).glob(".gitleaks.*.tmp"))
            self.assertEqual(leftover, [])

    def test_partial_write_install_keeps_full_payload_and_mode(self) -> None:
        original = install_gitleaks.write_all_bytes

        def one_byte_write(fd: int, payload: bytes, write=os.write) -> None:
            def stepwise(_fd: int, data) -> int:
                return write(_fd, data[:1])

            original(fd, payload, write=stepwise)

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "gitleaks"
            payload = b"#!/bin/sh\necho fixture\n"
            try:
                install_gitleaks.write_all_bytes = one_byte_write  # type: ignore[method-assign]
                installed = self._install_fixture(dest, payload=payload)
            finally:
                install_gitleaks.write_all_bytes = original  # type: ignore[method-assign]
            self.assertEqual(installed.read_bytes(), payload)
            self.assertEqual(stat.S_IMODE(installed.stat().st_mode), 0o755)

    def test_missing_archive_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "gitleaks"
            with self.assertRaises(install_gitleaks.InstallError):
                self._install_fixture(dest, member_name="not-gitleaks")
            leftover = list(Path(tmp).glob(".gitleaks.*.tmp"))
            self.assertEqual(leftover, [])


if __name__ == "__main__":
    unittest.main()
