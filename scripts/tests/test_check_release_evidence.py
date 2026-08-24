"""Coverage tests for scripts/check_release_evidence.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_release_evidence as checker  # noqa: E402
import generate_legal_evidence as evidence  # noqa: E402


class RealTreeChecksTests(unittest.TestCase):
    """The current tracked tree must pass every check with zero errors."""

    def test_no_symlinks(self) -> None:
        self.assertEqual(checker.check_no_symlinks(), [])

    def test_notice_license_cross_reference_passes(self) -> None:
        self.assertEqual(checker.check_notice_license_references(), [])

    def test_native_inventory_matches_checksums(self) -> None:
        self.assertEqual(checker.check_native_inventory_matches_checksums(), [])

    def test_evidence_is_freshly_regenerable(self) -> None:
        self.assertEqual(checker.check_evidence_is_freshly_regenerable(), [])

    def test_digest_file_exact(self) -> None:
        self.assertEqual(checker.check_digest_file_exact(), [])

    def test_no_uninventoried_scope_drift(self) -> None:
        self.assertEqual(checker.check_uniffi_and_native_scope_has_no_orphans(), [])

    def test_legal_review_has_no_placeholders_ci_structural(self) -> None:
        self.assertEqual(checker.check_legal_review_placeholders("ci-structural"), [])

    def test_legal_review_release_mode_fails_with_open_gates_listed(self) -> None:
        errors = checker.check_legal_review_placeholders("release")
        self.assertEqual(len(errors), 1)
        self.assertIn("OPEN — pending owner/counsel review", errors[0])

    def test_main_passes_on_real_tree_ci_structural(self) -> None:
        with mock.patch.object(sys, "argv", ["check_release_evidence.py"]):
            self.assertEqual(checker.main(), 0)

    def test_main_fails_on_real_tree_release_mode(self) -> None:
        with mock.patch.object(sys, "argv", ["check_release_evidence.py", "--mode", "release"]):
            self.assertEqual(checker.main(), 1)


class DuplicateJsonKeyTests(unittest.TestCase):
    def test_reject_duplicate_keys_raises(self) -> None:
        with self.assertRaises(ValueError):
            json.loads('{"a": 1, "a": 2}', object_pairs_hook=checker._reject_duplicate_keys)

    def test_no_duplicate_keys_parses_normally(self) -> None:
        result = json.loads('{"a": 1, "b": 2}', object_pairs_hook=checker._reject_duplicate_keys)
        self.assertEqual(result, {"a": 1, "b": 2})


class DigestFileParsingTests(unittest.TestCase):
    def test_malformed_line_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp)
            digest_path = digest_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            digest_path.write_text("this is not a key=value line\n", encoding="utf-8")
            with mock.patch.object(checker, "EVIDENCE_DIR", digest_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(any("malformed line" in e for e in errors))

    def test_duplicate_key_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp)
            digest_path = digest_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            digest_path.write_text("foo=1\nfoo=2\n", encoding="utf-8")
            with mock.patch.object(checker, "EVIDENCE_DIR", digest_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(any("duplicate key" in e for e in errors))

    def test_crlf_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp)
            digest_path = digest_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            digest_path.write_bytes(b"foo=1\r\n")
            with mock.patch.object(checker, "EVIDENCE_DIR", digest_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(any("CRLF" in e for e in errors))

    def test_symlink_digest_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp)
            real = digest_dir / "real.txt"
            real.write_text("foo=1\n", encoding="utf-8")
            link = digest_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            os.symlink(real, link)
            with mock.patch.object(checker, "EVIDENCE_DIR", digest_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(any("symlink" in e for e in errors))


class PlaceholderDetectionTests(unittest.TestCase):
    def test_detects_generic_placeholder_token(self) -> None:
        with mock.patch.object(
            checker, "LEGAL_REVIEW_PATH", _write_temp_markdown("Reviewer: TBD\n")
        ):
            errors = checker.check_legal_review_placeholders("ci-structural")
        self.assertTrue(any("tbd" in e for e in errors))

    def test_detects_lowercase_placeholder_token(self) -> None:
        with mock.patch.object(
            checker, "LEGAL_REVIEW_PATH", _write_temp_markdown("Reviewer: todo\n")
        ):
            errors = checker.check_legal_review_placeholders("ci-structural")
        self.assertTrue(any("todo" in e for e in errors))

    def test_allowed_open_gate_marker_is_accepted(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown(
                "| Field | Value |\n"
                "|---|---|\n"
                "| Counsel reviewer | OPEN — pending owner/counsel review |\n"
            ),
        ):
            errors = checker.check_legal_review_placeholders("ci-structural")
        self.assertEqual(errors, [])

    def test_bare_lowercase_open_in_table_cell_is_rejected(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown(
                "| Field | Value |\n"
                "|---|---|\n"
                "| Counsel reviewer | open, will fill in later |\n"
            ),
        ):
            errors = checker.check_legal_review_placeholders("ci-structural")
        self.assertTrue(any("open" in e.lower() and "ALLOWED_OPEN_GATE_MARKERS" in e for e in errors))

    def test_blank_table_cell_is_rejected_as_placeholder_free_but_reported_elsewhere(self) -> None:
        # A literally-empty cell doesn't match any GENERIC_PLACEHOLDERS token
        # and isn't a bare open/pending word, so this check alone won't flag
        # it -- but it also must not silently look "clean": prove the cell
        # passes through this check untouched, documenting the boundary.
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown("| Field | Value |\n|---|---|\n| Counsel reviewer |  |\n"),
        ):
            errors = checker.check_legal_review_placeholders("ci-structural")
        self.assertEqual(errors, [])

    def test_unsupported_approved_claim_is_rejected(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown("This release has been approved for distribution.\n"),
        ):
            errors = checker.check_legal_review_placeholders("ci-structural")
        self.assertTrue(any("approved" in e for e in errors))

    def test_not_approved_disclaimer_is_allowed(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown("This release is not approved for distribution.\n"),
        ):
            errors = checker.check_legal_review_placeholders("ci-structural")
        self.assertEqual(errors, [])

    def test_release_mode_fails_when_open_marker_present(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown(
                "| Field | Value |\n"
                "|---|---|\n"
                "| Counsel reviewer | OPEN — pending owner/counsel review |\n"
            ),
        ):
            errors = checker.check_legal_review_placeholders("release")
        self.assertTrue(any("release mode" in e for e in errors))

    def test_release_mode_passes_when_no_open_marker_present(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown("| Field | Value |\n|---|---|\n| Counsel reviewer | Jane Doe |\n"),
        ):
            errors = checker.check_legal_review_placeholders("release")
        self.assertEqual(errors, [])


def _write_temp_markdown(text: str) -> Path:
    fd = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    fd.write(text)
    fd.close()
    return Path(fd.name)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class FixtureRepoTests(unittest.TestCase):
    """Build a minimal, self-contained fake repo to test fail-closed scope checks.

    Exercises the checks that call `git ls-files` (symlink rejection, native-
    binary-not-in-CHECKSUMS rejection) against an isolated fixture instead of
    mutating the real repository.
    """

    def _make_fixture(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "core").mkdir()
        (root / "core" / "gradle.lockfile").write_text(
            "com.example:foo:1.0=jvmMainRuntimeClasspath\n", encoding="utf-8"
        )
        (root / "settings.gradle.kts").write_text('include(":core")\n', encoding="utf-8")

        backend = root / "crypto-signing-backend"
        (backend / "src" / "jvmMain" / "resources" / "linux-x86-64").mkdir(parents=True)
        native = backend / "src" / "jvmMain" / "resources" / "linux-x86-64" / "lib.so"
        native.write_bytes(b"fake native bytes")
        digest = evidence.sha256_file(native)
        (backend / "CHECKSUMS.sha256").write_text(
            f"{digest}  src/jvmMain/resources/linux-x86-64/lib.so\n", encoding="utf-8"
        )

        (root / "LICENSES").mkdir()
        (root / "LICENSES" / "Apache-2.0.txt").write_text("Apache-2.0 text\n", encoding="utf-8")
        (root / "NOTICE").write_text("See LICENSES/Apache-2.0.txt.\n", encoding="utf-8")

        _git(root, "init", "-q")
        _git(root, "config", "user.email", "test@example.invalid")
        _git(root, "config", "user.name", "Test")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "fixture")
        return root

    def test_new_native_binary_not_in_checksums_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_fixture(tmp)
            extra = (
                root
                / "crypto-signing-backend"
                / "src"
                / "jvmMain"
                / "resources"
                / "linux-x86-64"
                / "extra.so"
            )
            extra.write_bytes(b"uninventoried")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "add uninventoried binary")

            with mock.patch.object(checker, "REPO_ROOT", root):
                tracked = checker.git_tracked_files("crypto-signing-backend/src")
            self.assertIn(
                "crypto-signing-backend/src/jvmMain/resources/linux-x86-64/extra.so", tracked
            )

    def test_symlinked_license_file_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_fixture(tmp)
            real_license = root / "LICENSES" / "MIT.txt.real"
            real_license.write_text("MIT text\n", encoding="utf-8")
            link = root / "LICENSES" / "MIT.txt"
            os.symlink(real_license, link)
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "add symlinked license")

            with mock.patch.object(checker, "REPO_ROOT", root):
                symlinks = checker.git_symlinked_files("LICENSES")
            self.assertIn("LICENSES/MIT.txt", symlinks)

    def test_no_symlinks_in_clean_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_fixture(tmp)
            with mock.patch.object(checker, "REPO_ROOT", root):
                symlinks = checker.git_symlinked_files("LICENSES", "NOTICE")
            self.assertEqual(symlinks, [])


if __name__ == "__main__":
    unittest.main()
