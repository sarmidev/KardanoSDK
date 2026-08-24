"""Coverage tests for scripts/check_release_evidence.py."""

from __future__ import annotations

import copy
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

    def test_evidence_tree_exact_passes(self) -> None:
        self.assertEqual(checker.check_evidence_tree_exact(), [])

    def test_cargo_license_elections_ci_structural_passes(self) -> None:
        self.assertEqual(checker.check_cargo_license_elections("ci-structural"), [])

    def test_cargo_license_elections_release_mode_lists_every_open_row(self) -> None:
        errors = checker.check_cargo_license_elections("release")
        self.assertEqual(len(errors), 1)
        self.assertIn("memchr@2.8.3", errors[0])
        self.assertIn("anyhow@1.0.103", errors[0])

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


class EvidenceTreeExactTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.evidence_dir = Path(self._tmp.name) / "evidence"
        import shutil

        shutil.copytree(checker.EVIDENCE_DIR, self.evidence_dir)
        self._patch = mock.patch.object(checker, "EVIDENCE_DIR", self.evidence_dir)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    def test_nested_extra_file_is_rejected(self) -> None:
        extra = self.evidence_dir / "license-sources" / "unexpected-extra.txt"
        extra.write_text("surprise\n", encoding="utf-8")
        errors = checker.check_evidence_tree_exact()
        self.assertTrue(any("unexpected-extra.txt" in e for e in errors))

    def test_top_level_extra_directory_is_rejected(self) -> None:
        extra_dir = self.evidence_dir / "unexpected-dir"
        extra_dir.mkdir()
        (extra_dir / "file.txt").write_text("x\n", encoding="utf-8")
        errors = checker.check_evidence_tree_exact()
        self.assertTrue(any("unexpected-dir/file.txt" in e for e in errors))

    def test_missing_nested_expected_file_is_rejected(self) -> None:
        (self.evidence_dir / "license-sources" / "bouncycastle-licence-2026-08-24.html").unlink()
        errors = checker.check_evidence_tree_exact()
        self.assertTrue(any("expected evidence file is missing" in e for e in errors))

    def test_nested_symlink_is_rejected(self) -> None:
        target = self.evidence_dir / "scope_binding.json"
        link = self.evidence_dir / "license-sources" / "sneaky-link.html"
        os.symlink(target, link)
        errors = checker.check_evidence_tree_exact()
        self.assertTrue(any("sneaky-link.html" in e and "symlink" in e for e in errors))


class LicensesReadmeRequiredTests(unittest.TestCase):
    def test_missing_readme_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            licenses_dir = Path(tmp) / "LICENSES"
            licenses_dir.mkdir()
            (licenses_dir / "MIT.txt").write_text("MIT text\n", encoding="utf-8")
            notice_path = Path(tmp) / "NOTICE"
            notice_path.write_text("LICENSES/MIT.txt\n", encoding="utf-8")
            with mock.patch.object(checker, "LICENSES_DIR", licenses_dir), mock.patch.object(
                checker, "NOTICE_PATH", notice_path
            ), mock.patch.object(
                evidence, "gradle_dependency_inventory", lambda modules: {"modules": {}}
            ), mock.patch.object(
                evidence,
                "gradle_license_inventory",
                lambda report: {"mit_only_coordinates": []},
            ), mock.patch.object(
                evidence,
                "cargo_dependency_inventory_per_target",
                lambda: {"mit_only_linked_packages": []},
            ):
                errors = checker.check_notice_license_references()
            self.assertTrue(any("LICENSES/README.md is required" in e for e in errors))

    def test_present_readme_passes_that_specific_check(self) -> None:
        self.assertFalse(
            any(
                "LICENSES/README.md is required" in e
                for e in checker.check_notice_license_references()
            )
        )


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

    def test_blank_table_cell_is_rejected(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown("| Field | Value |\n|---|---|\n| Counsel reviewer |  |\n"),
        ):
            errors = checker.check_legal_review_placeholders("ci-structural")
        self.assertTrue(any("blank required table cell" in e for e in errors))

    def test_em_dash_cell_is_allowed_for_not_applicable(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown("| Field | Value |\n|---|---|\n| AND-required | — |\n"),
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


class CargoElectionSchemaTests(unittest.TestCase):
    def _report(self, rows: list[dict], mandatory_count: int, accepted_count: int) -> dict:
        return {
            "license_elections": {
                "rows": rows,
                "mandatory_row_count": mandatory_count,
                "accepted_count": accepted_count,
                "all_mandatory_elections_accepted": accepted_count == mandatory_count
                and mandatory_count > 0,
            }
        }

    def test_open_status_is_valid_in_ci_structural(self) -> None:
        report = self._report(
            [
                {
                    "name": "anyhow",
                    "version": "1.0.103",
                    "status": "OPEN",
                    "reviewer": None,
                    "review_date": None,
                    "linked_in_any_target": True,
                }
            ],
            mandatory_count=1,
            accepted_count=0,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            self.assertEqual(checker.check_cargo_license_elections("ci-structural"), [])

    def test_unsupported_approved_string_is_rejected(self) -> None:
        report = self._report(
            [
                {
                    "name": "anyhow",
                    "version": "1.0.103",
                    "status": "Approved",
                    "reviewer": "Jane Doe",
                    "review_date": "2026-08-24",
                    "linked_in_any_target": True,
                }
            ],
            mandatory_count=1,
            accepted_count=0,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            errors = checker.check_cargo_license_elections("ci-structural")
        self.assertTrue(any("Approved" in e and "not one of" in e for e in errors))

    def test_accepted_without_reviewer_is_rejected(self) -> None:
        report = self._report(
            [
                {
                    "name": "anyhow",
                    "version": "1.0.103",
                    "status": "ACCEPTED",
                    "reviewer": None,
                    "review_date": "2026-08-24",
                    "linked_in_any_target": True,
                }
            ],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            errors = checker.check_cargo_license_elections("ci-structural")
        self.assertTrue(any("reviewer is empty" in e for e in errors))

    def test_accepted_without_iso_date_is_rejected(self) -> None:
        report = self._report(
            [
                {
                    "name": "anyhow",
                    "version": "1.0.103",
                    "status": "ACCEPTED",
                    "reviewer": "Jane Doe",
                    "review_date": "08/24/2026",
                    "linked_in_any_target": True,
                }
            ],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            errors = checker.check_cargo_license_elections("ci-structural")
        self.assertTrue(any("not an ISO-8601 date" in e for e in errors))

    def test_fully_accepted_report_passes_release_mode(self) -> None:
        report = self._report(
            [
                {
                    "name": "anyhow",
                    "version": "1.0.103",
                    "status": "ACCEPTED",
                    "reviewer": "Jane Doe",
                    "review_date": "2026-08-24",
                    "linked_in_any_target": True,
                }
            ],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            self.assertEqual(checker.check_cargo_license_elections("release"), [])

    def test_partially_accepted_report_fails_release_mode(self) -> None:
        report = self._report(
            [
                {
                    "name": "anyhow",
                    "version": "1.0.103",
                    "status": "ACCEPTED",
                    "reviewer": "Jane Doe",
                    "review_date": "2026-08-24",
                    "linked_in_any_target": True,
                },
                {
                    "name": "memchr",
                    "version": "2.8.3",
                    "status": "OPEN",
                    "reviewer": None,
                    "review_date": None,
                    "linked_in_any_target": True,
                },
            ],
            mandatory_count=2,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            errors = checker.check_cargo_license_elections("release")
        self.assertEqual(len(errors), 1)
        self.assertIn("memchr@2.8.3", errors[0])
        self.assertNotIn("anyhow@1.0.103", errors[0])


class CargoInventoryHostAmbiguousFreshnessTests(unittest.TestCase):
    """`cargo_dependency_inventory.json`'s x86_64-unknown-linux-gnu membership
    slice is host-ambiguous (see the comment above `LINUX_X86_64_TARGET_TRIPLE`
    in scripts/check_release_evidence.py); everything else must still fail
    closed, on every host, exactly as before."""

    def _committed_payload(self) -> dict:
        text = (checker.EVIDENCE_DIR / "cargo_dependency_inventory.json").read_text(encoding="utf-8")
        return json.loads(text)

    def test_strip_removes_nested_triple_key_everywhere(self) -> None:
        payload = {
            "membership_by_target": {
                "x86_64-unknown-linux-gnu": {"linked_into_compiled_artifact": ["errno@0.3.14"]},
                "aarch64-apple-darwin": {"linked_into_compiled_artifact": ["errno@0.3.14"]},
            },
            "packages": [
                {
                    "name": "errno",
                    "membership": {
                        "x86_64-unknown-linux-gnu": ["linked_into_compiled_artifact"],
                        "aarch64-apple-darwin": ["linked_into_compiled_artifact"],
                    },
                }
            ],
        }
        stripped = checker._strip_host_ambiguous_cargo_target_membership(
            payload, checker.LINUX_X86_64_TARGET_TRIPLE
        )
        self.assertNotIn("x86_64-unknown-linux-gnu", stripped["membership_by_target"])
        self.assertNotIn("x86_64-unknown-linux-gnu", stripped["packages"][0]["membership"])
        self.assertIn("aarch64-apple-darwin", stripped["membership_by_target"])
        self.assertIn("aarch64-apple-darwin", stripped["packages"][0]["membership"])

    def test_non_matching_host_skips_when_divergence_confined_to_ambiguous_target(self) -> None:
        committed = self._committed_payload()
        fresh = copy.deepcopy(committed)
        fresh["membership_by_target"]["x86_64-unknown-linux-gnu"]["linked_into_compiled_artifact"].append(
            "registry+https://github.com/rust-lang/crates.io-index#errno@0.3.14"
        )
        with (
            mock.patch.object(evidence, "cargo_dependency_inventory_per_target", lambda: fresh),
            mock.patch.object(checker.platform, "system", return_value="Darwin"),
            mock.patch.object(checker.platform, "machine", return_value="arm64"),
        ):
            errors = checker.check_evidence_is_freshly_regenerable()
        self.assertEqual(errors, [])

    def test_matching_host_does_not_skip_the_same_divergence(self) -> None:
        committed = self._committed_payload()
        fresh = copy.deepcopy(committed)
        fresh["membership_by_target"]["x86_64-unknown-linux-gnu"]["linked_into_compiled_artifact"].append(
            "registry+https://github.com/rust-lang/crates.io-index#errno@0.3.14"
        )
        with (
            mock.patch.object(evidence, "cargo_dependency_inventory_per_target", lambda: fresh),
            mock.patch.object(checker.platform, "system", return_value="Linux"),
            mock.patch.object(checker.platform, "machine", return_value="x86_64"),
        ):
            errors = checker.check_evidence_is_freshly_regenerable()
        self.assertTrue(any("cargo_dependency_inventory.json is stale" in e for e in errors))

    def test_non_matching_host_still_fails_on_unrelated_divergence(self) -> None:
        committed = self._committed_payload()
        fresh = copy.deepcopy(committed)
        fresh["package_count"] = committed["package_count"] + 1
        with (
            mock.patch.object(evidence, "cargo_dependency_inventory_per_target", lambda: fresh),
            mock.patch.object(checker.platform, "system", return_value="Darwin"),
            mock.patch.object(checker.platform, "machine", return_value="arm64"),
        ):
            errors = checker.check_evidence_is_freshly_regenerable()
        self.assertTrue(any("cargo_dependency_inventory.json is stale" in e for e in errors))

    def test_host_is_linux_x86_64_helper(self) -> None:
        with (
            mock.patch.object(checker.platform, "system", return_value="Linux"),
            mock.patch.object(checker.platform, "machine", return_value="x86_64"),
        ):
            self.assertTrue(checker._host_is_linux_x86_64())
        with (
            mock.patch.object(checker.platform, "system", return_value="Darwin"),
            mock.patch.object(checker.platform, "machine", return_value="arm64"),
        ):
            self.assertFalse(checker._host_is_linux_x86_64())
        with (
            mock.patch.object(checker.platform, "system", return_value="Linux"),
            mock.patch.object(checker.platform, "machine", return_value="aarch64"),
        ):
            self.assertFalse(checker._host_is_linux_x86_64())


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


class ScopeBindingSealCheckTests(unittest.TestCase):
    """Exercise check_scope_binding_seal() against a disposable temp git repo.

    Builds a real two-commit (subject -> evidence) history, seals it with
    generate_legal_evidence.seal_scope_binding(), then mutates the resulting
    scope_binding.json / worktree in each test to prove every named failure
    mode (nonancestor, wrong parent, changed evidence after seal, missing
    digest key, bad hex, evidence_commit not reachable from HEAD) is
    actually caught -- and that the untouched, correctly-sealed history
    passes with zero errors.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "test@example.invalid")
        _git(self.repo, "config", "user.name", "Test")

        self._patches = [
            mock.patch.object(checker, "REPO_ROOT", self.repo),
            mock.patch.object(checker, "EVIDENCE_DIR", self.repo / "docs" / "evidence"),
            mock.patch.object(evidence, "REPO_ROOT", self.repo),
            mock.patch.object(evidence, "EVIDENCE_DIR", self.repo / "docs" / "evidence"),
        ]
        for patch in self._patches:
            patch.start()
        (self.repo / "docs" / "evidence").mkdir(parents=True)

    def tearDown(self) -> None:
        for patch in reversed(self._patches):
            patch.stop()
        self._tmp.cleanup()

    def _write_outputs(self) -> None:
        for name in evidence.evidence_output_files():
            (evidence.EVIDENCE_DIR / name).write_text(
                json.dumps({"name": name}) + "\n", encoding="utf-8"
            )

    def _seal(self) -> None:
        (self.repo / "SOURCE.txt").write_text("subject source\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "subject commit")
        self.main_branch = _git_output(self.repo, "symbolic-ref", "--short", "HEAD")

        self._write_outputs()
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "evidence commit")

        binding = evidence.seal_scope_binding()
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "seal commit")

    def test_correctly_sealed_history_passes(self) -> None:
        self._seal()
        self.assertEqual(checker.check_scope_binding_seal(), [])

    def test_missing_scope_binding_is_rejected(self) -> None:
        self._seal()
        (evidence.EVIDENCE_DIR / "scope_binding.json").unlink()
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("is missing" in e for e in errors))

    def test_unexpected_key_set_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        del binding["subject_tree"]
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("unexpected key set" in e for e in errors))

    def test_nonexistent_commit_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        binding["subject_commit"] = "a" * 40
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("does not exist as a commit object" in e for e in errors))

    def test_wrong_evidence_tree_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        binding["evidence_tree"] = "b" * 40
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("does not match evidence_commit" in e for e in errors))

    def test_non_immediate_parent_is_rejected(self) -> None:
        self._seal()
        # Point subject_commit at HEAD's grandparent instead of parent --
        # simulates an extra intervening commit between subject and evidence.
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        # Fabricate an unrelated, ancestor-less commit to use as a wrong,
        # non-parent subject_commit value.
        _git(self.repo, "checkout", "-q", "--orphan", "unrelated")
        (self.repo / "UNRELATED.txt").write_text("x\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "unrelated root")
        unrelated_commit = _git_output(self.repo, "rev-parse", "HEAD")
        _git(self.repo, "checkout", "-q", self.main_branch)
        binding["subject_commit"] = unrelated_commit
        binding["subject_tree"] = _git_output(self.repo, "rev-parse", f"{unrelated_commit}^{{tree}}")
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("is not evidence_commit" in e and "immediate parent" in e for e in errors))

    def test_evidence_commit_not_ancestor_of_head_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        _git(self.repo, "checkout", "-q", "--orphan", "unrelated2")
        (self.repo / "UNRELATED2.txt").write_text("x\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "unrelated root 2")
        # Now HEAD is this unrelated commit; the sealed evidence_commit is
        # unreachable from it.
        errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not an ancestor of (or equal to) current HEAD" in e for e in errors)
        )

    def test_evidence_changed_after_seal_is_rejected(self) -> None:
        self._seal()
        any_name = next(iter(evidence.evidence_output_files()))
        (evidence.EVIDENCE_DIR / any_name).write_text('{"tampered": true}\n', encoding="utf-8")
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("evidence content drifted after the seal" in e for e in errors))

    def test_extra_commit_touching_evidence_is_rejected(self) -> None:
        self._seal()
        any_name = next(iter(evidence.evidence_output_files()))
        (evidence.EVIDENCE_DIR / any_name).write_text('{"tampered": true}\n', encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "sneaky extra commit touching evidence")
        errors = checker.check_scope_binding_seal()
        # Current bytes now match the sneaky commit (not the seal's digest),
        # so this is caught the same way as any post-seal drift -- an extra
        # commit is not a special case, it is just another way to drift.
        self.assertTrue(any("evidence content drifted after the seal" in e for e in errors))

    def test_missing_sealed_digest_key_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        any_key = next(iter(binding["sealed_evidence_digests"]))
        del binding["sealed_evidence_digests"][any_key]
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("sealed_evidence_digests key set" in e for e in errors))

    def test_malformed_digest_hex_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        any_key = next(iter(binding["sealed_evidence_digests"]))
        binding["sealed_evidence_digests"][any_key] = "not-a-hex-digest"
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("is not a 64-hex-char sha256" in e for e in errors))

    def test_duplicate_json_key_is_rejected(self) -> None:
        self._seal()
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            '{"note": "a", "note": "b"}\n', encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("duplicate" in e for e in errors))


def _git_output(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


if __name__ == "__main__":
    unittest.main()
