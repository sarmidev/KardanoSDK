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


def _find_real_local_bcprov_jar() -> Path | None:
    """Best-effort local shortcut for tests that exercise the REAL,
    unmocked JAVA_CLASS_VERSION_EVIDENCE snapshot end to end: if this
    machine's own Gradle module cache already has the exact resolved
    org.bouncycastle:bcprov-jdk18on:1.85.2 .jar (true on most dev machines
    that have ever run ./gradlew), point KARDANO_LEGAL_EVIDENCE_BCPROV_JAR
    at it for the duration of the test so it does not need the network.
    Returns `None` if not found -- the test then falls back to
    live_verify_java_class_version_evidence()'s own real Maven Central
    fetch+verify, exactly the same code path CI itself exercises when its
    own dedicated bootstrap step has not already set the env var.
    """
    coordinate = evidence.JAVA_CLASS_VERSION_EVIDENCE["coordinate"]
    group, artifact, version = evidence.parse_gav(coordinate)
    for path in evidence.find_local_maven_artifacts(group, artifact, version):
        if path.suffix.lower() == ".jar":
            return path
    return None


class RealTreeChecksTests(unittest.TestCase):
    """The current tracked tree must pass every check with zero errors."""

    def setUp(self) -> None:
        self._bcprov_env_patch = None
        local_jar = _find_real_local_bcprov_jar()
        if local_jar is not None:
            self._bcprov_env_patch = mock.patch.dict(
                os.environ, {evidence.BCPROV_JAR_PATH_ENV_VAR: str(local_jar)}
            )
            self._bcprov_env_patch.start()

    def tearDown(self) -> None:
        if self._bcprov_env_patch is not None:
            self._bcprov_env_patch.stop()

    def test_no_symlinks(self) -> None:
        self.assertEqual(checker.check_no_symlinks(), [])

    def test_no_completed_election_wording(self) -> None:
        self.assertEqual(checker.check_no_completed_election_wording(), [])

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


class LiveBcprovVerificationNoSkipTests(unittest.TestCase):
    """Gap: 'exact-tip CI uses an empty Gradle cache and the live bcprov
    verifier currently returns success when the JAR is absent'. Proves the
    checker itself -- not just generate_legal_evidence.py in isolation --
    fails closed (never silently passes) when the real bcprov jar cannot be
    resolved at all: no explicit path, no env var, and a failing fetch.
    """

    def setUp(self) -> None:
        os.environ.pop(evidence.BCPROV_JAR_PATH_ENV_VAR, None)
        self._fetch_patch = mock.patch.object(
            evidence,
            "fetch_and_verify_bcprov_jar",
            side_effect=evidence.EvidenceError("no network in this test"),
        )
        self._fetch_patch.start()

    def tearDown(self) -> None:
        self._fetch_patch.stop()

    def test_freshness_check_reports_an_error_not_an_empty_list(self) -> None:
        errors = checker.check_evidence_is_freshly_regenerable()
        self.assertTrue(errors, "expected at least one error, got an empty (silently-passing) list")
        self.assertTrue(
            any("java_class_version_evidence" in e for e in errors),
            f"no error mentioned java_class_version_evidence.json: {errors}",
        )

    def test_main_fails_ci_structural_mode(self) -> None:
        with mock.patch.object(sys, "argv", ["check_release_evidence.py"]):
            self.assertEqual(checker.main(), 1)

    def test_main_fails_release_mode(self) -> None:
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

    def test_unrecognized_comment_line_is_rejected_as_byte_mismatch(self) -> None:
        # `digest_file_lines()` never emits any comment line beyond the
        # fixed `DIGEST_FILE_HEADER_LINES` block; a stray extra comment
        # anywhere (even a well-intentioned human note) must fail the
        # final byte-exact recomputation check rather than being silently
        # tolerated by the line-parsing loop that skips `#`-prefixed lines.
        # Uses a full copy of the real evidence tree (not just the digest
        # text file in isolation) so every OTHER field still recomputes
        # cleanly and only the injected comment line trips a failure.
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            evidence_dir = Path(tmp) / "evidence"
            shutil.copytree(checker.EVIDENCE_DIR, evidence_dir)
            digest_path = evidence_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            real_bytes = digest_path.read_bytes()
            digest_path.write_bytes(real_bytes.replace(b"\n\n", b"\n# ad hoc note\n\n", 1))
            with mock.patch.object(checker, "EVIDENCE_DIR", evidence_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(any("do not exactly match deterministic recomputation" in e for e in errors))

    def test_trailing_junk_after_last_key_is_rejected(self) -> None:
        real_bytes = (checker.EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp)
            digest_path = digest_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            digest_path.write_bytes(real_bytes.rstrip(b"\n") + b"\ntrailing_junk_not_a_real_key=1\n")
            with mock.patch.object(checker, "EVIDENCE_DIR", digest_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(any("unexpected/extra key" in e and "trailing_junk_not_a_real_key" in e for e in errors))

    def test_missing_expected_key_is_rejected(self) -> None:
        real_bytes = (checker.EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt").read_bytes()
        lines = real_bytes.decode("utf-8").split("\n")
        filtered = [ln for ln in lines if not ln.startswith("notice_sha256=")]
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp)
            digest_path = digest_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            digest_path.write_text("\n".join(filtered), encoding="utf-8")
            with mock.patch.object(checker, "EVIDENCE_DIR", digest_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(any("missing expected key" in e and "notice_sha256" in e for e in errors))

    def test_extra_ad_hoc_key_is_rejected(self) -> None:
        real_bytes = (checker.EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp)
            digest_path = digest_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            digest_path.write_bytes(real_bytes.rstrip(b"\n") + b"\nsome_ad_hoc_field=deadbeef\n")
            with mock.patch.object(checker, "EVIDENCE_DIR", digest_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(
                any(
                    "unexpected/extra key" in e and "some_ad_hoc_field" in e
                    for e in errors
                )
            )

    def test_duplicate_evidence_sha256_key_is_rejected(self) -> None:
        real_bytes = (checker.EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt").read_bytes()
        lines = real_bytes.decode("utf-8").split("\n")
        target = next(ln for ln in lines if ln.startswith("notice_sha256="))
        insert_at = lines.index(target) + 1
        lines.insert(insert_at, target)
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp)
            digest_path = digest_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            digest_path.write_text("\n".join(lines), encoding="utf-8")
            with mock.patch.object(checker, "EVIDENCE_DIR", digest_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(any("duplicate key" in e and "notice_sha256" in e for e in errors))

    def test_gradle_modules_mismatch_against_dynamic_discovery_is_rejected(self) -> None:
        real_bytes = (checker.EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt").read_bytes()
        lines = real_bytes.decode("utf-8").split("\n")
        replaced = [
            "gradle_modules=totally-made-up-module,another-fake-module" if ln.startswith("gradle_modules=") else ln
            for ln in lines
        ]
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp)
            digest_path = digest_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            digest_path.write_text("\n".join(replaced), encoding="utf-8")
            with mock.patch.object(checker, "EVIDENCE_DIR", digest_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(
                any(
                    "gradle_modules=" in e and "dynamically discovered from settings.gradle.kts" in e
                    for e in errors
                )
            )

    def test_malformed_sha256_value_is_rejected(self) -> None:
        real_bytes = (checker.EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt").read_bytes()
        lines = real_bytes.decode("utf-8").split("\n")
        replaced = [
            "notice_sha256=NOT-A-VALID-HEX-DIGEST" if ln.startswith("notice_sha256=") else ln for ln in lines
        ]
        with tempfile.TemporaryDirectory() as tmp:
            digest_dir = Path(tmp)
            digest_path = digest_dir / "LEGAL_EVIDENCE_DIGEST.txt"
            digest_path.write_text("\n".join(replaced), encoding="utf-8")
            with mock.patch.object(checker, "EVIDENCE_DIR", digest_dir):
                errors = checker.check_digest_file_exact()
            self.assertTrue(
                any("not a 64-hex-char lowercase SHA-256 value" in e for e in errors)
            )


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


class CompletedElectionWordingDetectionTests(unittest.TestCase):
    """OPEN elections must never be described in prose as already
    elected/accepted (Gap 1 of the 2026-08-24 final re-review)."""

    def _watch_single_file(self, text: str) -> Path:
        path = _write_temp_markdown(text)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_real_tracked_documents_use_no_completed_election_wording(self) -> None:
        self.assertEqual(checker.check_no_completed_election_wording(), [])

    def test_elected_branch_phrase_is_rejected(self) -> None:
        path = self._watch_single_file(
            "Apache-2.0 was the elected branch of this dual license.\n"
        )
        with mock.patch.object(checker, "ELECTION_WORDING_WATCHED_FILES", (str(path),)):
            errors = checker.check_no_completed_election_wording()
        self.assertEqual(len(errors), 1)
        self.assertIn("elected branch", errors[0])

    def test_sdk_elects_phrase_is_rejected(self) -> None:
        path = self._watch_single_file("Kardano SDK elects Apache-2.0 for this distribution.\n")
        with mock.patch.object(checker, "ELECTION_WORDING_WATCHED_FILES", (str(path),)):
            errors = checker.check_no_completed_election_wording()
        self.assertEqual(len(errors), 1)
        self.assertIn("sdk elects", errors[0])

    def test_has_elected_phrase_is_rejected(self) -> None:
        path = self._watch_single_file("The project has elected Apache-2.0 already.\n")
        with mock.patch.object(checker, "ELECTION_WORDING_WATCHED_FILES", (str(path),)):
            errors = checker.check_no_completed_election_wording()
        self.assertEqual(len(errors), 1)
        self.assertIn("has elected", errors[0])

    def test_bare_election_is_accepted_without_negation_is_rejected(self) -> None:
        path = self._watch_single_file("This election is accepted as of today.\n")
        with mock.patch.object(checker, "ELECTION_WORDING_WATCHED_FILES", (str(path),)):
            errors = checker.check_no_completed_election_wording()
        self.assertEqual(len(errors), 1)
        self.assertIn("election is accepted", errors[0])

    def test_negated_no_election_is_accepted_statement_is_allowed(self) -> None:
        path = self._watch_single_file(
            "No election is accepted until reviewer, date, and status are "
            "all recorded as ACCEPTED.\n"
        )
        with mock.patch.object(checker, "ELECTION_WORDING_WATCHED_FILES", (str(path),)):
            errors = checker.check_no_completed_election_wording()
        self.assertEqual(errors, [])

    def test_proposed_election_wording_is_allowed(self) -> None:
        path = self._watch_single_file(
            "Kardano SDK proposes electing Apache-2.0 for this distribution, "
            "but that election is not yet ACCEPTED.\n"
        )
        with mock.patch.object(checker, "ELECTION_WORDING_WATCHED_FILES", (str(path),)):
            errors = checker.check_no_completed_election_wording()
        self.assertEqual(errors, [])

    def test_missing_watched_file_is_reported(self) -> None:
        missing = "/nonexistent/path/does-not-exist-election-wording.md"
        with mock.patch.object(checker, "ELECTION_WORDING_WATCHED_FILES", (missing,)):
            errors = checker.check_no_completed_election_wording()
        self.assertEqual(len(errors), 1)
        self.assertIn("expected file is missing", errors[0])

    def test_multiple_offending_phrases_are_all_reported(self) -> None:
        path = self._watch_single_file(
            "Line one: is the elected choice.\n"
            "Line two: SDK elects Apache-2.0 outright.\n"
        )
        with mock.patch.object(checker, "ELECTION_WORDING_WATCHED_FILES", (str(path),)):
            errors = checker.check_no_completed_election_wording()
        self.assertEqual(len(errors), 2)

    # -- Gap 3 (2026-08-24 final round): grammar-local negation, not a
    # fixed-width lookback window. -----------------------------------

    def _errors_for(self, text: str) -> list[str]:
        path = self._watch_single_file(text)
        with mock.patch.object(checker, "ELECTION_WORDING_WATCHED_FILES", (str(path),)):
            return checker.check_no_completed_election_wording()

    def test_negation_before_a_clause_boundary_does_not_exempt_the_next_clause(self) -> None:
        # A `:` separates the negation clause from the affirmative one --
        # the negation must not leak across that boundary. This exact
        # sentence matches TWO phrases ("is the elected" AND "elected
        # branch" both appear in "it is the elected branch"), so both must
        # be reported, neither exempted.
        errors = self._errors_for("Not final: it is the elected branch.\n")
        self.assertEqual(len(errors), 2)
        joined = " ".join(errors)
        self.assertIn("is the elected", joined)
        self.assertIn("elected branch", joined)

    def test_negation_before_a_semicolon_does_not_exempt_the_next_clause(self) -> None:
        errors = self._errors_for("This is not rejected; SDK elects Apache.\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("sdk elects", errors[0])

    def test_negation_before_a_colon_does_not_exempt_election_is_accepted(self) -> None:
        errors = self._errors_for("Not disputed: election is accepted today.\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("election is accepted", errors[0])

    def test_negation_in_a_separate_sentence_does_not_exempt(self) -> None:
        errors = self._errors_for(
            "This is not the final word on anything. SDK elects Apache-2.0 outright.\n"
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("sdk elects", errors[0])

    def test_negation_in_a_separate_markdown_list_item_does_not_exempt(self) -> None:
        errors = self._errors_for(
            "- Not accepted anywhere in this document.\n"
            "- SDK elects Apache-2.0 for every dual-licensed component.\n"
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("sdk elects", errors[0])

    def test_negation_in_a_separate_paragraph_does_not_exempt(self) -> None:
        errors = self._errors_for(
            "No claims here are final.\n\n"
            "Apache-2.0 has elected status as the redistributed license.\n"
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("has elected", errors[0])

    def test_contraction_negation_in_same_clause_is_allowed_only_via_explicit_pattern(self) -> None:
        # A contraction ("isn't", "wasn't") in the SAME clause as the
        # phrase is still not one of the explicit allowed disclaimer
        # patterns, so it must still fail -- the fix is an explicit
        # allowlist, not a generic negation-word scan that would have
        # accidentally exempted this too.
        errors = self._errors_for("This election is accepted, though it isn't final yet.\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("election is accepted", errors[0])

    def test_case_insensitivity_of_both_phrase_and_disclaimer(self) -> None:
        errors = self._errors_for("SDK ELECTS APACHE-2.0 FOR THIS DISTRIBUTION.\n")
        self.assertEqual(len(errors), 1)
        errors = self._errors_for(
            "NO ELECTION IS ACCEPTED UNTIL REVIEWER, DATE, AND STATUS ARE RECORDED.\n"
        )
        self.assertEqual(errors, [])

    def test_markdown_emphasis_and_code_spans_around_disclaimer_still_exempt(self) -> None:
        errors = self._errors_for(
            "But `none of those elections is yet` **ACCEPTED** -- each remains "
            "an OPEN row pending reviewer, ISO-8601 date, and status.\n"
        )
        self.assertEqual(errors, [])

    def test_real_notice_style_not_yet_accepted_disclaimer_is_allowed(self) -> None:
        errors = self._errors_for(
            "Kardano SDK proposes electing Apache-2.0 for this distribution, but "
            "that election is not yet ACCEPTED -- see docs/LEGAL_REVIEW.md.\n"
        )
        self.assertEqual(errors, [])

    def test_real_third_party_notices_style_none_yet_accepted_disclaimer_is_allowed(self) -> None:
        errors = self._errors_for(
            "for all three, but none of those elections is yet ACCEPTED -- each "
            "remains an OPEN row.\n"
        )
        self.assertEqual(errors, [])

    def test_disclaimer_clause_boundary_inside_parentheses_is_still_scoped_correctly(self) -> None:
        # Mirrors the real LICENSES/README.md shape: the disclaimer clause
        # is inside parentheses and followed by a semicolon-separated
        # clause containing the actual "no election is accepted" text --
        # parentheses themselves are not clause boundaries, but the
        # semicolon before them still correctly separates this from an
        # unrelated PRECEDING clause.
        errors = self._errors_for(
            "This clause is not relevant; it is the proposed election (not yet "
            "ACCEPTED -- each remains OPEN; no election is accepted until all "
            "three are recorded).\n"
        )
        self.assertEqual(errors, [])

    def test_multiple_clauses_one_offending_one_disclaimed(self) -> None:
        errors = self._errors_for(
            "No election is accepted today. SDK elects Apache-2.0 regardless.\n"
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("sdk elects", errors[0])


class CargoElectionSchemaTests(unittest.TestCase):
    def _report(self, rows: list[dict], mandatory_count: int, accepted_count: int) -> dict:
        # Mirrors generate_legal_evidence.py's real
        # `all_mandatory_elections_accepted` formula: BOTH every mandatory
        # OR-election row AND every mandatory AND-component (across all
        # rows) must be ACCEPTED -- accepting one side never implicitly
        # satisfies the other.
        and_components = [
            c
            for r in rows
            if r.get("linked_in_any_target")
            for c in r.get("and_component_acceptance", [])
        ]
        all_and_accepted = all(c["status"] == "ACCEPTED" for c in and_components)
        return {
            "license_elections": {
                "rows": rows,
                "mandatory_row_count": mandatory_count,
                "accepted_count": accepted_count,
                "all_mandatory_elections_accepted": accepted_count == mandatory_count
                and mandatory_count > 0
                and all_and_accepted,
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

    def test_accepted_with_proposed_election_not_in_options_is_rejected(self) -> None:
        # Gap 3: an ACCEPTED row's proposed_election must be EXACTLY one of
        # its own or_election_options -- e.g. accepting "BSD-3-Clause" for a
        # package whose actual SPDX expression only offers MIT/Apache-2.0.
        report = self._report(
            [
                {
                    "name": "anyhow",
                    "version": "1.0.103",
                    "status": "ACCEPTED",
                    "reviewer": "Jane Doe",
                    "review_date": "2026-08-24",
                    "linked_in_any_target": True,
                    "proposed_election": "BSD-3-Clause",
                    "or_election_options": ["MIT", "Apache-2.0"],
                }
            ],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            errors = checker.check_cargo_license_elections("ci-structural")
        self.assertTrue(
            any(
                "proposed_election" in e and "BSD-3-Clause" in e and "or_election_options" in e
                for e in errors
            )
        )

    def test_accepted_with_missing_proposed_election_is_rejected(self) -> None:
        # memchr's real shape: proposed_election is deliberately None (no
        # blanket Unlicense-vs-MIT election). Accepting the row anyway
        # (status ACCEPTED, proposed_election still None) must fail even
        # though status/reviewer/review_date all look superficially valid.
        report = self._report(
            [
                {
                    "name": "memchr",
                    "version": "2.8.3",
                    "status": "ACCEPTED",
                    "reviewer": "Jane Doe",
                    "review_date": "2026-08-24",
                    "linked_in_any_target": True,
                    "proposed_election": None,
                    "or_election_options": ["Unlicense", "MIT"],
                }
            ],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            errors = checker.check_cargo_license_elections("ci-structural")
        self.assertTrue(any("memchr@2.8.3" in e and "not exactly one of" in e for e in errors))

    def test_and_component_missing_reviewer_is_rejected_even_though_or_side_accepted(
        self,
    ) -> None:
        # unicode-ident's real shape: MIT OR Apache-2.0 (OR side) AND
        # Unicode-3.0 (mandatory AND component). Accepting the OR side
        # must NOT implicitly accept the Unicode-3.0 AND component.
        report = self._report(
            [
                {
                    "name": "unicode-ident",
                    "version": "1.0.22",
                    "status": "ACCEPTED",
                    "reviewer": "Jane Doe",
                    "review_date": "2026-08-24",
                    "linked_in_any_target": True,
                    "proposed_election": "Apache-2.0",
                    "or_election_options": ["MIT", "Apache-2.0"],
                    "and_component_acceptance": [
                        {"component": "Unicode-3.0", "status": "ACCEPTED", "reviewer": None, "review_date": "2026-08-24"}
                    ],
                }
            ],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            errors = checker.check_cargo_license_elections("ci-structural")
        self.assertTrue(
            any("AND-component" in e and "Unicode-3.0" in e and "reviewer is empty" in e for e in errors)
        )

    def test_and_component_open_fails_release_mode_even_though_or_side_accepted(self) -> None:
        report = self._report(
            [
                {
                    "name": "unicode-ident",
                    "version": "1.0.22",
                    "status": "ACCEPTED",
                    "reviewer": "Jane Doe",
                    "review_date": "2026-08-24",
                    "linked_in_any_target": True,
                    "proposed_election": "Apache-2.0",
                    "or_election_options": ["MIT", "Apache-2.0"],
                    "and_component_acceptance": [
                        {"component": "Unicode-3.0", "status": "OPEN", "reviewer": None, "review_date": None}
                    ],
                }
            ],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            errors = checker.check_cargo_license_elections("release")
        self.assertTrue(any("AND components not accepted" in e and "Unicode-3.0" in e for e in errors))

    def test_and_component_fully_accepted_passes_release_mode(self) -> None:
        report = self._report(
            [
                {
                    "name": "unicode-ident",
                    "version": "1.0.22",
                    "status": "ACCEPTED",
                    "reviewer": "Jane Doe",
                    "review_date": "2026-08-24",
                    "linked_in_any_target": True,
                    "proposed_election": "Apache-2.0",
                    "or_election_options": ["MIT", "Apache-2.0"],
                    "and_component_acceptance": [
                        {"component": "Unicode-3.0", "status": "ACCEPTED", "reviewer": "Jane Doe", "review_date": "2026-08-24"}
                    ],
                }
            ],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "cargo_dependency_inventory_per_target", lambda: report
        ):
            self.assertEqual(checker.check_cargo_license_elections("release"), [])


class GradleElectionSchemaTests(unittest.TestCase):
    """Mirrors CargoElectionSchemaTests for the Gradle side (Gap 2),
    including JNA, using a synthetic gradle_license_inventory() report so
    these are fast, deterministic unit tests independent of the local
    Gradle module cache."""

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

    def _jna_row(self, **overrides) -> dict:
        row = {
            "coordinate": "net.java.dev.jna:jna:5.19.1",
            "status": "OPEN",
            "reviewer": None,
            "review_date": None,
            "proposed_election": "Apache-2.0",
            "or_election_options": ["Apache-2.0", "LGPL-2.1-or-later"],
        }
        row.update(overrides)
        return row

    def test_jna_open_status_is_valid_in_ci_structural(self) -> None:
        report = self._report([self._jna_row()], mandatory_count=1, accepted_count=0)
        with mock.patch.object(
            evidence, "gradle_dependency_inventory", lambda modules: {"modules": {}}
        ), mock.patch.object(evidence, "gradle_license_inventory", lambda gr: report):
            self.assertEqual(checker.check_gradle_license_elections("ci-structural"), [])

    def test_jna_missing_election_status_is_rejected(self) -> None:
        report = self._report([self._jna_row(status=None)], mandatory_count=1, accepted_count=0)
        with mock.patch.object(
            evidence, "gradle_dependency_inventory", lambda modules: {"modules": {}}
        ), mock.patch.object(evidence, "gradle_license_inventory", lambda gr: report):
            errors = checker.check_gradle_license_elections("ci-structural")
        self.assertTrue(any("jna" in e and "not one of" in e for e in errors))

    def test_jna_invalid_election_status_string_is_rejected(self) -> None:
        report = self._report([self._jna_row(status="Approved")], mandatory_count=1, accepted_count=0)
        with mock.patch.object(
            evidence, "gradle_dependency_inventory", lambda modules: {"modules": {}}
        ), mock.patch.object(evidence, "gradle_license_inventory", lambda gr: report):
            errors = checker.check_gradle_license_elections("ci-structural")
        self.assertTrue(any("Approved" in e and "not one of" in e for e in errors))

    def test_jna_accepted_without_reviewer_is_rejected(self) -> None:
        report = self._report(
            [self._jna_row(status="ACCEPTED", reviewer=None, review_date="2026-08-24")],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "gradle_dependency_inventory", lambda modules: {"modules": {}}
        ), mock.patch.object(evidence, "gradle_license_inventory", lambda gr: report):
            errors = checker.check_gradle_license_elections("ci-structural")
        self.assertTrue(any("reviewer is empty" in e for e in errors))

    def test_jna_accepted_with_invalid_date_is_rejected(self) -> None:
        report = self._report(
            [self._jna_row(status="ACCEPTED", reviewer="Jane Doe", review_date="24-08-2026")],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "gradle_dependency_inventory", lambda modules: {"modules": {}}
        ), mock.patch.object(evidence, "gradle_license_inventory", lambda gr: report):
            errors = checker.check_gradle_license_elections("ci-structural")
        self.assertTrue(any("not an ISO-8601 date" in e for e in errors))

    def test_jna_accepted_election_not_in_options_is_rejected(self) -> None:
        report = self._report(
            [
                self._jna_row(
                    status="ACCEPTED",
                    reviewer="Jane Doe",
                    review_date="2026-08-24",
                    proposed_election="MIT",
                )
            ],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "gradle_dependency_inventory", lambda modules: {"modules": {}}
        ), mock.patch.object(evidence, "gradle_license_inventory", lambda gr: report):
            errors = checker.check_gradle_license_elections("ci-structural")
        self.assertTrue(any("MIT" in e and "or_election_options" in e for e in errors))

    def test_jna_fully_accepted_passes_release_mode(self) -> None:
        report = self._report(
            [self._jna_row(status="ACCEPTED", reviewer="Jane Doe", review_date="2026-08-24")],
            mandatory_count=1,
            accepted_count=1,
        )
        with mock.patch.object(
            evidence, "gradle_dependency_inventory", lambda modules: {"modules": {}}
        ), mock.patch.object(evidence, "gradle_license_inventory", lambda gr: report):
            self.assertEqual(checker.check_gradle_license_elections("release"), [])

    def test_jna_still_open_fails_release_mode(self) -> None:
        report = self._report([self._jna_row()], mandatory_count=1, accepted_count=0)
        with mock.patch.object(
            evidence, "gradle_dependency_inventory", lambda modules: {"modules": {}}
        ), mock.patch.object(evidence, "gradle_license_inventory", lambda gr: report):
            errors = checker.check_gradle_license_elections("release")
        self.assertTrue(any("net.java.dev.jna:jna:5.19.1" in e for e in errors))

    def test_real_tree_jna_row_is_open_in_ci_structural(self) -> None:
        # Integration check against the real committed license_catalog.py:
        # JNA's real row must exist, be schema-valid, and currently be OPEN
        # (no blanket acceptance) -- this is the actual gap-2 regression
        # this class exists to prevent from silently reappearing.
        gradle_report = evidence.gradle_dependency_inventory(evidence.discover_gradle_modules())
        report = evidence.gradle_license_inventory(gradle_report)
        rows = report["license_elections"]["rows"]
        jna_rows = [r for r in rows if r["coordinate"].startswith("net.java.dev.jna:jna:")]
        self.assertEqual(len(jna_rows), 1)
        self.assertEqual(jna_rows[0]["status"], "OPEN")
        self.assertEqual(checker.check_gradle_license_elections("ci-structural"), [])
        release_errors = checker.check_gradle_license_elections("release")
        self.assertTrue(any("jna" in e for e in release_errors))


class CargoInventoryHostAmbiguousFreshnessTests(unittest.TestCase):
    """The ONLY permitted host-ambiguous difference in
    `cargo_dependency_inventory.json` is the single, exact `errno@0.3.14`
    `x86_64-unknown-linux-gnu` membership entry (see the comment above
    `LINUX_X86_64_TARGET_TRIPLE` in scripts/check_release_evidence.py);
    everything else -- a different package, a different triple, a wrong
    errno version/source/checksum, an inconsistent/partial version of the
    known diff, or any additional unrelated diff -- must still fail closed,
    on every host, exactly as before. The exception applies only when the
    ACTUAL `rustc -vV` host (not a spoofable `platform`/env value) is not
    itself `x86_64-unknown-linux-gnu`.
    """

    def _committed_payload(self) -> dict:
        """A small, self-contained synthetic payload -- deliberately NOT the
        real committed docs/evidence/cargo_dependency_inventory.json.

        The real file's errno@0.3.14 x86_64-unknown-linux-gnu membership
        reflects whatever this specific machine's `cargo tree` actually
        resolved at generation time, which empirically is NOT stable across
        environments/toolchain versions -- unlike the narrow, purely
        pairwise `_cargo_inventory_diff_is_known_errno_host_ambiguity()`
        logic under test here, which only cares about the SHAPE of a diff
        between two payloads, not which absolute state either one starts
        from. A synthetic fixture keeps this test class's outcome
        independent of the current host's own cargo resolution.
        """
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        other_triple = "aarch64-apple-darwin"
        other_pkg_id = "registry+https://github.com/rust-lang/crates.io-index#serde@1.0.228"
        return {
            "package_count": 2,
            "packages": [
                {
                    "name": checker.KNOWN_ERRNO_NAME,
                    "version": checker.KNOWN_ERRNO_VERSION,
                    "source": checker.KNOWN_ERRNO_SOURCE,
                    "cargo_lock_checksum": checker.KNOWN_ERRNO_CHECKSUM,
                    "membership": {},
                },
                {
                    "name": "serde",
                    "version": "1.0.228",
                    "source": "registry+https://github.com/rust-lang/crates.io-index",
                    "cargo_lock_checksum": "0" * 64,
                    "membership": {triple: ["linked_into_compiled_artifact"]},
                },
            ],
            "membership_by_target": {
                triple: {"linked_into_compiled_artifact": [other_pkg_id]},
                other_triple: {"linked_into_compiled_artifact": []},
            },
        }

    def _add_known_errno_diff(self, payload: dict) -> dict:
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        pkg_id = checker.KNOWN_ERRNO_HOST_AMBIGUOUS_PACKAGE_ID
        payload = copy.deepcopy(payload)
        linked = payload["membership_by_target"][triple]["linked_into_compiled_artifact"]
        if pkg_id not in linked:
            payload["membership_by_target"][triple]["linked_into_compiled_artifact"] = sorted(
                linked + [pkg_id]
            )
        errno_pkg = next(p for p in payload["packages"] if p["name"] == "errno")
        errno_pkg["membership"][triple] = ["linked_into_compiled_artifact"]
        return payload

    def test_exact_known_diff_matches(self) -> None:
        committed = self._committed_payload()
        fresh = self._add_known_errno_diff(committed)
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertTrue(matches, detail)

    def test_identical_payloads_are_not_reported_as_a_diff_match_target(self) -> None:
        # Not the scenario this function is called for in practice (the
        # caller only invokes it when fresh_text != committed_text), but it
        # must not crash and must not claim a match when nothing differs.
        committed = self._committed_payload()
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(
            committed, copy.deepcopy(committed)
        )
        self.assertFalse(matches)

    def test_unrelated_package_linux_membership_diff_fails(self) -> None:
        committed = self._committed_payload()
        fresh = copy.deepcopy(committed)
        fresh["membership_by_target"][checker.LINUX_X86_64_TARGET_TRIPLE][
            "linked_into_compiled_artifact"
        ].append("registry+https://github.com/rust-lang/crates.io-index#some_other_package@1.0.0")
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_errno_wrong_version_fails(self) -> None:
        committed = self._committed_payload()
        fresh = self._add_known_errno_diff(committed)
        next(p for p in fresh["packages"] if p["name"] == "errno")["version"] = "0.3.15"
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_errno_wrong_source_fails(self) -> None:
        committed = self._committed_payload()
        fresh = self._add_known_errno_diff(committed)
        next(p for p in fresh["packages"] if p["name"] == "errno")["source"] = "registry+https://example.invalid"
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_errno_wrong_checksum_fails(self) -> None:
        committed = self._committed_payload()
        fresh = self._add_known_errno_diff(committed)
        next(p for p in fresh["packages"] if p["name"] == "errno")["cargo_lock_checksum"] = "0" * 64
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_extra_path_alongside_known_diff_fails(self) -> None:
        committed = self._committed_payload()
        fresh = self._add_known_errno_diff(committed)
        fresh["package_count"] = committed["package_count"] + 1
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_inconsistent_partial_diff_fails(self) -> None:
        # membership_by_target says errno is linked for that target, but the
        # package's own membership dict disagrees -- not the known shape.
        committed = self._committed_payload()
        fresh = copy.deepcopy(committed)
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        pkg_id = checker.KNOWN_ERRNO_HOST_AMBIGUOUS_PACKAGE_ID
        fresh["membership_by_target"][triple]["linked_into_compiled_artifact"] = sorted(
            fresh["membership_by_target"][triple]["linked_into_compiled_artifact"] + [pkg_id]
        )
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_missing_membership_by_target_entry_fails(self) -> None:
        committed = self._committed_payload()
        fresh = copy.deepcopy(committed)
        del fresh["membership_by_target"][checker.LINUX_X86_64_TARGET_TRIPLE]["linked_into_compiled_artifact"]
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def _committed_payload_with_election_row(self) -> dict:
        """Same shape as `_committed_payload()`, plus the real payload's
        SEPARATE `license_elections.rows[]` mirror of errno's per-target
        membership (`target_membership`) -- the second JSON location the
        2026-08-24 Verify run 32756290850 found this same host ambiguity
        reappears in, which a hand-patch of only `packages[].membership`
        missed."""
        payload = self._committed_payload()
        payload["license_elections"] = {
            "rows": [
                {
                    "name": checker.KNOWN_ERRNO_NAME,
                    "version": checker.KNOWN_ERRNO_VERSION,
                    "target_membership": {},
                },
                {
                    "name": "serde",
                    "version": "1.0.228",
                    "target_membership": {
                        checker.LINUX_X86_64_TARGET_TRIPLE: ["linked_into_compiled_artifact"]
                    },
                },
            ]
        }
        return payload

    def _add_known_errno_diff_with_row(self, payload: dict) -> dict:
        payload = self._add_known_errno_diff(payload)
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        errno_row = next(
            r for r in payload["license_elections"]["rows"] if r["name"] == "errno"
        )
        errno_row["target_membership"][triple] = ["linked_into_compiled_artifact"]
        return payload

    def test_exact_known_diff_matches_when_election_row_mirror_also_toggled(self) -> None:
        committed = self._committed_payload_with_election_row()
        fresh = self._add_known_errno_diff_with_row(committed)
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertTrue(matches, detail)

    def test_election_row_mirror_left_stale_alongside_toggled_package_membership_fails(self) -> None:
        # Regression test for the exact real-world mistake this class exists
        # to catch: `packages[].membership` and `membership_by_target` are
        # toggled consistently, but the SEPARATE `license_elections.rows[]`
        # `target_membership` mirror is left on the OLD side -- not the
        # known shape, must fail closed rather than silently pass.
        committed = self._committed_payload_with_election_row()
        fresh = self._add_known_errno_diff(committed)  # note: row NOT updated
        fresh["license_elections"] = copy.deepcopy(committed["license_elections"])
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches, detail)

    def test_election_row_missing_entirely_when_section_present_fails(self) -> None:
        committed = self._committed_payload_with_election_row()
        fresh = self._add_known_errno_diff_with_row(committed)
        del fresh["license_elections"]["rows"][0]  # drop the errno row entirely
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_election_row_wrong_target_membership_value_fails(self) -> None:
        committed = self._committed_payload_with_election_row()
        fresh = self._add_known_errno_diff_with_row(committed)
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        errno_row = next(r for r in fresh["license_elections"]["rows"] if r["name"] == "errno")
        errno_row["target_membership"][triple] = ["build_dependency_only"]
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_absent_license_elections_section_on_both_sides_skips_row_check(self) -> None:
        # Backward-compatible with the plain _committed_payload() fixture
        # (no "license_elections" key at all) used by every other test in
        # this class.
        committed = self._committed_payload()
        fresh = self._add_known_errno_diff(committed)
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertTrue(matches, detail)

    # -- Gap 2: normalization must preserve every unrelated array order/
    # value exactly, never sort beyond the generator's own canonical
    # serialization, and reject multiple/duplicate errno entries. --

    def _committed_payload_with_three_unrelated_packages(self) -> dict:
        """Like `_committed_payload()`, but with THREE deliberately
        non-alphabetically-ordered unrelated package ids in the one list
        `normalized()` touches, so a test can prove their relative order
        survives errno's own presence/absence being toggled -- and that
        reversing/reordering them (with no errno involvement at all) is
        never silently tolerated."""
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        other_triple = "aarch64-apple-darwin"
        zzz_pkg_id = "registry+https://github.com/rust-lang/crates.io-index#zzz-crate@1.0.0"
        mmm_pkg_id = "registry+https://github.com/rust-lang/crates.io-index#mmm-crate@1.0.0"
        aaa_pkg_id = "registry+https://github.com/rust-lang/crates.io-index#aaa-crate@1.0.0"
        return {
            "package_count": 4,
            "packages": [
                {
                    "name": checker.KNOWN_ERRNO_NAME,
                    "version": checker.KNOWN_ERRNO_VERSION,
                    "source": checker.KNOWN_ERRNO_SOURCE,
                    "cargo_lock_checksum": checker.KNOWN_ERRNO_CHECKSUM,
                    "membership": {},
                },
                {"name": "zzz-crate", "version": "1.0.0", "membership": {triple: ["linked_into_compiled_artifact"]}},
                {"name": "mmm-crate", "version": "1.0.0", "membership": {triple: ["linked_into_compiled_artifact"]}},
                {"name": "aaa-crate", "version": "1.0.0", "membership": {triple: ["linked_into_compiled_artifact"]}},
            ],
            "membership_by_target": {
                # Deliberately NOT alphabetically sorted -- this is the
                # generator's own (unspecified-here) canonical order, and
                # normalized() must never impose sorted() on top of it.
                triple: {"linked_into_compiled_artifact": [zzz_pkg_id, mmm_pkg_id, aaa_pkg_id]},
                other_triple: {"linked_into_compiled_artifact": []},
            },
        }

    def test_errno_inserted_in_the_middle_without_reordering_others_still_matches(self) -> None:
        # Proves the fix directly: errno's id can be inserted at ANY
        # position in the list (not just appended/sorted-in) without
        # disturbing the other three ids' relative order, and the
        # narrow exception still recognizes this as the known diff.
        committed = self._committed_payload_with_three_unrelated_packages()
        fresh = copy.deepcopy(committed)
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        pkg_id = checker.KNOWN_ERRNO_HOST_AMBIGUOUS_PACKAGE_ID
        linked = fresh["membership_by_target"][triple]["linked_into_compiled_artifact"]
        linked.insert(1, pkg_id)  # between zzz and mmm -- not sorted, not appended
        fresh["packages"][0]["membership"][triple] = ["linked_into_compiled_artifact"]
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertTrue(matches, detail)
        # And the untouched list's relative order (zzz, mmm, aaa) is
        # exactly what a byte-canonical re-serialization would still show.
        self.assertEqual(
            [p for p in linked if p != pkg_id],
            committed["membership_by_target"][triple]["linked_into_compiled_artifact"],
        )

    def test_reversed_unrelated_package_membership_list_with_no_errno_involvement_fails(self) -> None:
        committed = self._committed_payload_with_three_unrelated_packages()
        fresh = copy.deepcopy(committed)
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        fresh["membership_by_target"][triple]["linked_into_compiled_artifact"] = list(
            reversed(fresh["membership_by_target"][triple]["linked_into_compiled_artifact"])
        )
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_reversed_unrelated_list_alongside_the_known_errno_diff_still_fails(self) -> None:
        # The known errno diff is present AND an unrelated list elsewhere
        # is reversed -- the reversal alone must still cause a failure;
        # the errno exception must never mask it.
        committed = self._committed_payload_with_three_unrelated_packages()
        fresh = copy.deepcopy(committed)
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        pkg_id = checker.KNOWN_ERRNO_HOST_AMBIGUOUS_PACKAGE_ID
        linked = fresh["membership_by_target"][triple]["linked_into_compiled_artifact"]
        fresh["membership_by_target"][triple]["linked_into_compiled_artifact"] = list(reversed(linked)) + [pkg_id]
        fresh["packages"][0]["membership"][triple] = ["linked_into_compiled_artifact"]
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_reversed_packages_array_order_fails(self) -> None:
        # `packages[]` itself is an array of dicts; swapping two entries'
        # positions with no other change must not be silently tolerated
        # even though every individual package object is byte-identical.
        committed = self._committed_payload_with_three_unrelated_packages()
        fresh = copy.deepcopy(committed)
        fresh["packages"] = list(reversed(fresh["packages"]))
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_inserted_unrelated_election_row_fails(self) -> None:
        committed = self._committed_payload_with_election_row()
        fresh = self._add_known_errno_diff_with_row(committed)
        fresh["license_elections"]["rows"].append(
            {
                "name": "brand-new-crate",
                "version": "9.9.9",
                "target_membership": {},
            }
        )
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_reordered_election_rows_array_fails(self) -> None:
        # license_elections.rows[] order is part of the canonical
        # serialization too -- reordering it with no errno involvement at
        # all must fail exactly like reordering packages[].
        committed = self._committed_payload_with_election_row()
        fresh = copy.deepcopy(committed)
        fresh["license_elections"]["rows"] = list(reversed(fresh["license_elections"]["rows"]))
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    # -- Gap 2 (2026-08-24 final round): the comparison must preserve
    # dictionary insertion order too (no `sort_keys`, no Python dict
    # `==`/`!=`), not just list order. Python dict equality ignores key
    # order entirely, so these prove the fix is a real byte/structure
    # comparison, not the previous `normalized(fresh) != normalized(committed)`
    # bare dict inequality. --------------------------------------------

    def _add_known_errno_diff_preserving_order(self, payload: dict) -> dict:
        """Like `_add_known_errno_diff`, but inserts errno's package id
        WITHOUT `sorted()` re-imposing alphabetical order on the rest of
        the list -- needed for fixtures (like
        `_committed_payload_with_three_unrelated_packages`) whose list is
        deliberately NOT already alphabetical, so this class's dict-order
        tests below exercise a genuine relative-order match, not an
        accidental artifact of `sorted()`.
        """
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        pkg_id = checker.KNOWN_ERRNO_HOST_AMBIGUOUS_PACKAGE_ID
        payload = copy.deepcopy(payload)
        linked = payload["membership_by_target"][triple]["linked_into_compiled_artifact"]
        if pkg_id not in linked:
            linked.insert(0, pkg_id)
        errno_pkg = next(p for p in payload["packages"] if p["name"] == "errno")
        errno_pkg["membership"][triple] = ["linked_into_compiled_artifact"]
        return payload

    def test_exact_canonical_order_on_both_sides_matches(self) -> None:
        # Sanity check: identical key/list order on both sides (mirroring
        # what check_evidence_is_freshly_regenerable now feeds this
        # function -- both reloaded through the SAME sort_keys=True
        # canonical dump) must still match when only the documented errno
        # diff differs.
        committed = self._committed_payload_with_three_unrelated_packages()
        fresh = self._add_known_errno_diff_preserving_order(committed)
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertTrue(matches, detail)

    def test_reversed_keys_in_an_unrelated_package_dict_fails(self) -> None:
        # Same keys, same values, reversed INSERTION order within one
        # unrelated package's own dict -- Python dict `==` would call
        # this identical; the fix must not.
        committed = self._committed_payload_with_three_unrelated_packages()
        fresh = self._add_known_errno_diff_preserving_order(committed)
        serde_pkg = next(p for p in fresh["packages"] if p["name"] == "zzz-crate")
        reversed_pkg = dict(reversed(list(serde_pkg.items())))
        self.assertEqual(reversed_pkg, serde_pkg)  # same by Python dict equality
        fresh["packages"][fresh["packages"].index(serde_pkg)] = reversed_pkg
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches, detail)

    def test_reversed_keys_in_an_unrelated_election_row_fails(self) -> None:
        committed = self._committed_payload_with_election_row()
        fresh = self._add_known_errno_diff_with_row(committed)
        serde_row = next(r for r in fresh["license_elections"]["rows"] if r["name"] == "serde")
        reversed_row = dict(reversed(list(serde_row.items())))
        self.assertEqual(reversed_row, serde_row)
        fresh["license_elections"]["rows"][fresh["license_elections"]["rows"].index(serde_row)] = reversed_row
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches, detail)

    def test_reversed_keys_in_a_nested_membership_by_target_dict_fails(self) -> None:
        # Reverses the key order of the nested per-target dict itself
        # (membership_by_target[other_triple]), two levels deep.
        committed = self._committed_payload_with_three_unrelated_packages()
        fresh = self._add_known_errno_diff(committed)
        other_triple = "aarch64-apple-darwin"
        nested = fresh["membership_by_target"][other_triple]
        reversed_nested = dict(reversed(list(nested.items())))
        self.assertEqual(reversed_nested, nested)
        fresh["membership_by_target"][other_triple] = reversed_nested
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches, detail)

    def test_reversed_top_level_keys_fails(self) -> None:
        # Reverses the top-level payload dict's own key order (with the
        # documented errno diff still present) -- a full-tree key reorder
        # that has zero effect under Python dict equality.
        committed = self._committed_payload_with_three_unrelated_packages()
        fresh = self._add_known_errno_diff(committed)
        fresh = dict(reversed(list(fresh.items())))
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches, detail)

    def test_reversed_keys_alongside_the_known_errno_diff_still_fails(self) -> None:
        # The known, tolerated errno diff is present AND an unrelated
        # dict's key order is separately reversed -- the reversal alone
        # must still cause a failure; the errno exception must never
        # mask it.
        committed = self._committed_payload_with_three_unrelated_packages()
        fresh = self._add_known_errno_diff(committed)
        aaa_pkg = next(p for p in fresh["packages"] if p["name"] == "aaa-crate")
        fresh["packages"][fresh["packages"].index(aaa_pkg)] = dict(reversed(list(aaa_pkg.items())))
        matches, _detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)

    def test_duplicate_errno_package_id_in_membership_by_target_fails(self) -> None:
        # A duplicated errno package id within the SAME
        # linked_into_compiled_artifact list is itself a real anomaly
        # (e.g. a corrupted index), not the documented single-entry
        # ambiguity -- must not be silently absorbed by the filter-based
        # removal.
        committed = self._committed_payload()
        fresh = self._add_known_errno_diff(committed)
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        pkg_id = checker.KNOWN_ERRNO_HOST_AMBIGUOUS_PACKAGE_ID
        fresh["membership_by_target"][triple]["linked_into_compiled_artifact"].append(pkg_id)
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)
        self.assertIn("more than once", detail)

    def test_duplicate_errno_package_id_on_committed_side_fails(self) -> None:
        committed = self._committed_payload()
        fresh = self._add_known_errno_diff(committed)
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        pkg_id = checker.KNOWN_ERRNO_HOST_AMBIGUOUS_PACKAGE_ID
        committed = copy.deepcopy(committed)
        committed["membership_by_target"][triple]["linked_into_compiled_artifact"] = [pkg_id, pkg_id]
        matches, detail = checker._cargo_inventory_diff_is_known_errno_host_ambiguity(fresh, committed)
        self.assertFalse(matches)
        self.assertIn("more than once", detail)

    def test_host_spoof_via_platform_module_is_ignored(self) -> None:
        # Even if platform.system()/machine() are spoofed to claim
        # Linux/x86_64, only the actual rustc host (mocked here) decides.
        with (
            mock.patch("platform.system", return_value="Linux"),
            mock.patch("platform.machine", return_value="x86_64"),
            mock.patch.object(checker, "_rustc_host_triple", return_value="aarch64-apple-darwin"),
        ):
            self.assertFalse(checker._host_is_linux_x86_64())

    def test_host_is_linux_x86_64_uses_rustc_host_triple(self) -> None:
        with mock.patch.object(checker, "_rustc_host_triple", return_value="x86_64-unknown-linux-gnu"):
            self.assertTrue(checker._host_is_linux_x86_64())
        with mock.patch.object(checker, "_rustc_host_triple", return_value="aarch64-apple-darwin"):
            self.assertFalse(checker._host_is_linux_x86_64())
        with mock.patch.object(checker, "_rustc_host_triple", return_value=None):
            self.assertFalse(checker._host_is_linux_x86_64())

    def _real_committed_payload(self) -> dict:
        text = (checker.EVIDENCE_DIR / "cargo_dependency_inventory.json").read_text(encoding="utf-8")
        return json.loads(text)

    def _toggle_known_errno_diff(self, payload: dict) -> dict:
        """Flip errno@0.3.14's x86_64-unknown-linux-gnu presence, whichever
        way it currently is, guaranteeing a genuine, exact-shape diff from
        `payload` regardless of which side of the real ambiguity the actual
        committed evidence file happens to be on when these three
        integration-style tests run (this repo's own committed file's
        exact errno membership on this one target is itself a live,
        environment-dependent fact this test class must not assume either
        way -- only the mechanics of the exception matter here).
        """
        triple = checker.LINUX_X86_64_TARGET_TRIPLE
        pkg_id = checker.KNOWN_ERRNO_HOST_AMBIGUOUS_PACKAGE_ID
        payload = copy.deepcopy(payload)
        linked = payload["membership_by_target"][triple]["linked_into_compiled_artifact"]
        errno_pkg = next(p for p in payload["packages"] if p["name"] == "errno")
        errno_row = next(
            (
                r
                for r in payload.get("license_elections", {}).get("rows", [])
                if r.get("name") == "errno" and r.get("version") == checker.KNOWN_ERRNO_VERSION
            ),
            None,
        )
        if pkg_id in linked:
            payload["membership_by_target"][triple]["linked_into_compiled_artifact"] = [
                x for x in linked if x != pkg_id
            ]
            errno_pkg["membership"].pop(triple, None)
            if errno_row is not None:
                errno_row.get("target_membership", {}).pop(triple, None)
        else:
            payload["membership_by_target"][triple]["linked_into_compiled_artifact"] = sorted(
                linked + [pkg_id]
            )
            errno_pkg["membership"][triple] = ["linked_into_compiled_artifact"]
            if errno_row is not None:
                errno_row["target_membership"][triple] = ["linked_into_compiled_artifact"]
        return payload

    def test_non_matching_rustc_host_skips_only_the_known_diff(self) -> None:
        committed = self._real_committed_payload()
        fresh = self._toggle_known_errno_diff(committed)
        with (
            mock.patch.object(evidence, "cargo_dependency_inventory_per_target", lambda: fresh),
            mock.patch.object(checker, "_rustc_host_triple", return_value="aarch64-apple-darwin"),
        ):
            errors = checker.check_evidence_is_freshly_regenerable()
        self.assertEqual(errors, [])

    def test_matching_rustc_host_does_not_skip_the_same_diff(self) -> None:
        committed = self._real_committed_payload()
        fresh = self._toggle_known_errno_diff(committed)
        with (
            mock.patch.object(evidence, "cargo_dependency_inventory_per_target", lambda: fresh),
            mock.patch.object(checker, "_rustc_host_triple", return_value="x86_64-unknown-linux-gnu"),
        ):
            errors = checker.check_evidence_is_freshly_regenerable()
        self.assertTrue(any("cargo_dependency_inventory.json is stale" in e for e in errors))

    def test_non_matching_host_still_fails_on_unrelated_divergence(self) -> None:
        committed = self._real_committed_payload()
        fresh = copy.deepcopy(committed)
        fresh["package_count"] = committed["package_count"] + 1
        with (
            mock.patch.object(evidence, "cargo_dependency_inventory_per_target", lambda: fresh),
            mock.patch.object(checker, "_rustc_host_triple", return_value="aarch64-apple-darwin"),
        ):
            errors = checker.check_evidence_is_freshly_regenerable()
        self.assertTrue(any("cargo_dependency_inventory.json is stale" in e for e in errors))

    def test_non_matching_host_fails_when_known_diff_plus_extra_diff_both_present(self) -> None:
        committed = self._real_committed_payload()
        fresh = self._toggle_known_errno_diff(committed)
        fresh["package_count"] = committed["package_count"] + 1
        with (
            mock.patch.object(evidence, "cargo_dependency_inventory_per_target", lambda: fresh),
            mock.patch.object(checker, "_rustc_host_triple", return_value="aarch64-apple-darwin"),
        ):
            errors = checker.check_evidence_is_freshly_regenerable()
        self.assertTrue(any("cargo_dependency_inventory.json is stale" in e for e in errors))


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

    def _write_tooling_files(self, *, suffix: str = "") -> None:
        """Stand-in tooling files at the exact relative paths
        `evidence.SEALED_TOOLING_FILES` names, inside the disposable temp
        repo -- `compute_tooling_hashes()` reads these via the mocked
        `REPO_ROOT`, so the seal/checker tooling-binding logic can be
        exercised without touching the real scripts/ tree.
        """
        for rel_path in evidence.SEALED_TOOLING_FILES:
            path = self.repo / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# stand-in for {rel_path}{suffix}\n", encoding="utf-8")

    def _seal(self) -> None:
        (self.repo / "SOURCE.txt").write_text("subject source\n", encoding="utf-8")
        self._write_tooling_files()
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
        # not even reachable from it, let alone its immediate parent.
        errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_extra_commit_on_top_of_seal_is_rejected(self) -> None:
        # A 2026-08-24 independent review found the prior "ancestor of
        # HEAD" wording let an unrelated later commit sit on top of an old
        # seal without invalidating it -- the seal commit must remain the
        # exact current tip for readiness.
        self._seal()
        (self.repo / "UNRELATED3.txt").write_text("x\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "unrelated later commit on top of the seal")
        errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    # -- GitHub `pull_request` merge-ref exception: event-bound hardening --
    #
    # A later independent review found the original tree-shape-only
    # acceptance (any two-parent commit whose tree matched a parent that
    # was the seal) could not distinguish a genuine GitHub merge-ref from
    # any other two-parent commit built to have the same shape -- octopus
    # merges, swapped/unrelated parents, and a fabricated same-tree merge
    # candidate all needed to be rejected. `_github_pull_request_merge_head()`
    # now validates the current GITHUB_EVENT_NAME/GITHUB_EVENT_PATH event
    # payload (repository identity, base/head ref+sha, exact GitHub parent
    # order) BEFORE any tree comparison, and denies the exception outright
    # on a stale/forged/mismatched/missing event or env var -- these tests
    # exercise both the positive shape and every named adversarial escape.

    _GITHUB_REPOSITORY = "sarmidev/KardanoSDK"

    def _write_github_event(
        self,
        *,
        base_sha: str,
        head_sha: str,
        repo_full_name: str | None = None,
        base_repo_full_name: str | None = None,
        head_repo_full_name: str | None = None,
        base_ref: str = "main",
        head_ref: str = "feature",
        merge_commit_sha: str | None = None,
        duplicate_key: bool = False,
    ) -> Path:
        # `merge_commit_sha` (when present at all) is the ACTUAL merge
        # commit GitHub creates for refs/pull/*/merge -- i.e. the commit
        # this checker is running against (GITHUB_SHA/`head`), never the
        # PR head branch commit itself. Tests that want the positive
        # "where provided" cross-check must pass the real merge commit
        # explicitly; omitting it (the default) exercises the "not
        # provided" branch, which every other positive test relies on.
        repo_full_name = repo_full_name if repo_full_name is not None else self._GITHUB_REPOSITORY
        base_repo_full_name = base_repo_full_name if base_repo_full_name is not None else repo_full_name
        head_repo_full_name = head_repo_full_name if head_repo_full_name is not None else repo_full_name
        pr: dict[str, object] = {
            "base": {
                "sha": base_sha,
                "ref": base_ref,
                "repo": {"full_name": base_repo_full_name},
            },
            "head": {
                "sha": head_sha,
                "ref": head_ref,
                "repo": {"full_name": head_repo_full_name},
            },
        }
        if merge_commit_sha is not None:
            pr["merge_commit_sha"] = merge_commit_sha
        event = {"repository": {"full_name": repo_full_name}, "pull_request": pr}
        event_path = self.repo / "event.json"
        if duplicate_key:
            event_path.write_text(
                '{"repository": {"full_name": "x"}, "repository": {"full_name": "x"}}\n',
                encoding="utf-8",
            )
        else:
            event_path.write_text(json.dumps(event), encoding="utf-8")
        return event_path

    def _github_pull_request_env(
        self,
        *,
        event_path: Path,
        head: str,
        event_name: str = "pull_request",
        repository: str | None = None,
        base_ref: str = "main",
        head_ref: str = "feature",
    ):
        env = {
            "GITHUB_EVENT_NAME": event_name,
            "GITHUB_EVENT_PATH": str(event_path),
            "GITHUB_SHA": head,
            "GITHUB_REPOSITORY": repository if repository is not None else self._GITHUB_REPOSITORY,
            "GITHUB_BASE_REF": base_ref,
            "GITHUB_HEAD_REF": head_ref,
        }
        return mock.patch.dict(os.environ, env, clear=False)

    def _merge_seal_into_base(self, seal: str, subject: str, *, message: str = "Merge seal into base") -> str:
        _git(self.repo, "checkout", "-q", "-B", "base", subject)
        _git(self.repo, "merge", "--no-ff", "-q", "-m", message, seal)
        return _git_output(self.repo, "rev-parse", "HEAD")

    def test_github_style_merge_ref_of_seal_tip_passes(self) -> None:
        # GitHub pull_request jobs check out refs/pull/*/merge: a two-parent
        # merge of the PR head into the base. When the PR head is the seal
        # commit, the event payload's base.sha/head.sha exactly match the
        # merge's actual parents in GitHub order, the repository/ref/SHA
        # all cross-check, and the merge tree equals that seal, this is the
        # same sealed tip, not a later commit on top of it.
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(base_sha=subject, head_sha=seal)
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            self.assertEqual(checker.check_scope_binding_seal(), [])

    def test_github_style_merge_ref_of_post_seal_commit_is_rejected(self) -> None:
        # The event binding is genuine and internally consistent, but the
        # PR head named by the event is a commit ON TOP OF the seal, not
        # the seal itself -- its own first parent is not evidence_commit,
        # so it still fails downstream exactly like the non-PR case does.
        self._seal()
        (self.repo / "UNRELATED4.txt").write_text("x\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "later commit on top of the seal")
        extra = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^^")
        merge_commit = self._merge_seal_into_base(extra, subject, message="Merge extra into base")
        event_path = self._write_github_event(base_sha=subject, head_sha=extra)
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_no_github_event_env_falls_back_to_strict_and_is_rejected(self) -> None:
        # No GITHUB_EVENT_NAME/GITHUB_EVENT_PATH at all: an otherwise
        # perfectly shaped merge-ref of the seal tip must NOT be granted
        # the exception -- the strict "HEAD's own first parent must be
        # evidence_commit" path applies, and a real merge commit's first
        # parent is the base branch, not the seal.
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        self._merge_seal_into_base(seal, subject)
        with mock.patch.dict(
            os.environ,
            {},
            clear=False,
        ):
            for name in checker._REQUIRED_PULL_REQUEST_ENV_VARS:
                os.environ.pop(name, None)
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_non_pull_request_event_name_is_rejected(self) -> None:
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(base_sha=subject, head_sha=seal)
        with self._github_pull_request_env(event_path=event_path, head=merge_commit, event_name="push"):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_octopus_merge_is_rejected(self) -> None:
        # A three-parent (octopus) merge is never eligible for the
        # exception, no matter what the event payload claims.
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        _git(self.repo, "checkout", "-q", "-B", "base", subject)
        _git(self.repo, "checkout", "-q", "-b", "third", subject)
        (self.repo / "THIRD.txt").write_text("third\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "third branch commit")
        third = _git_output(self.repo, "rev-parse", "HEAD")
        _git(self.repo, "checkout", "-q", "base")
        _git(self.repo, "merge", "--no-ff", "-q", "-m", "Octopus merge", seal, third)
        merge_commit = _git_output(self.repo, "rev-parse", "HEAD")
        event_path = self._write_github_event(base_sha=subject, head_sha=seal)
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_swapped_parents_is_rejected(self) -> None:
        # Merge order is [base, head] in real git parent order; if the
        # event's base.sha/head.sha are swapped relative to the actual
        # parents, the exact-order check must reject it.
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(base_sha=seal, head_sha=subject)
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_unrelated_parent_in_event_is_rejected(self) -> None:
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        _git(self.repo, "checkout", "-q", "--orphan", "unrelated5")
        (self.repo / "UNRELATED5.txt").write_text("x\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "unrelated root")
        unrelated = _git_output(self.repo, "rev-parse", "HEAD")
        _git(self.repo, "checkout", "-q", "base")
        event_path = self._write_github_event(base_sha=unrelated, head_sha=seal)
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_genuine_tree_mismatch_is_rejected(self) -> None:
        # A real conflict-resolution merge whose tree differs from the PR
        # head's own tree must not be silently accepted as "the same
        # sealed tip".
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        _git(self.repo, "checkout", "-q", "-B", "base", subject)
        (self.repo / "BASE_ONLY.txt").write_text("base-only change\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "base-only change before merging seal")
        _git(self.repo, "merge", "--no-ff", "-q", "-m", "Merge seal into base", seal)
        merge_commit = _git_output(self.repo, "rev-parse", "HEAD")
        event_path = self._write_github_event(base_sha=subject, head_sha=seal)
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_forged_same_tree_candidate_with_wrong_parent_order_is_rejected(self) -> None:
        # Build a commit with the SAME tree as a genuine merge but with
        # its two parents in the wrong (non-GitHub) order via
        # `git commit-tree` directly -- tree-shape equality alone must
        # not be sufficient; exact parent-order/event-SHA matching is
        # required first.
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        genuine_merge = self._merge_seal_into_base(seal, subject)
        tree = _git_output(self.repo, "rev-parse", f"{genuine_merge}^{{tree}}")
        forged = _git_output(
            self.repo,
            "commit-tree",
            tree,
            "-p",
            seal,
            "-p",
            subject,
            "-m",
            "forged same-tree candidate with swapped parents",
        )
        _git(self.repo, "checkout", "-q", "-B", "forged-branch", forged)
        event_path = self._write_github_event(base_sha=subject, head_sha=seal)
        with self._github_pull_request_env(event_path=event_path, head=forged):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_wrong_base_sha_in_event_is_rejected(self) -> None:
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(base_sha="a" * 40, head_sha=seal)
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_wrong_head_sha_in_event_is_rejected(self) -> None:
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(base_sha=subject, head_sha="b" * 40)
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_stale_event_wrong_github_sha_is_rejected(self) -> None:
        # GITHUB_SHA does not match the actual HEAD being checked -- the
        # event describes some other checkout, not this one.
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(base_sha=subject, head_sha=seal)
        with self._github_pull_request_env(event_path=event_path, head="c" * 40):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_wrong_repository_in_event_is_rejected(self) -> None:
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(
            base_sha=subject, head_sha=seal, repo_full_name="someone-else/OtherRepo"
        )
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_wrong_base_ref_in_event_is_rejected(self) -> None:
        # Base ref is not main -- this scope-binding exception only ever
        # applies to a pull_request targeting main.
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(base_sha=subject, head_sha=seal, base_ref="develop")
        with self._github_pull_request_env(
            event_path=event_path, head=merge_commit, base_ref="develop"
        ):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_head_ref_env_mismatch_is_rejected(self) -> None:
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(
            base_sha=subject, head_sha=seal, head_ref="feature-a"
        )
        with self._github_pull_request_env(
            event_path=event_path, head=merge_commit, head_ref="feature-b"
        ):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_fork_head_repository_is_rejected(self) -> None:
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(
            base_sha=subject,
            head_sha=seal,
            head_repo_full_name="someone-else/KardanoSDK",
        )
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_matching_merge_commit_sha_in_event_still_passes(self) -> None:
        # When `pull_request.merge_commit_sha` IS provided and correctly
        # names the actual merge commit (GITHUB_SHA/`head`), the exception
        # still applies -- the field is optional and not itself checked.
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(
            base_sha=subject, head_sha=seal, merge_commit_sha=merge_commit
        )
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            self.assertEqual(checker.check_scope_binding_seal(), [])

    def test_stale_merge_commit_sha_in_event_does_not_deny_the_exception(self) -> None:
        # `pull_request.merge_commit_sha` is a snapshot of GitHub's
        # ephemeral test-merge SHA taken at webhook-delivery time and is
        # well documented to legitimately lag the actual refs/pull/*/merge
        # commit `actions/checkout` fetches moments later for an ordinary
        # `synchronize` push (see actions/checkout#919 and Ken Muse's "The
        # Many SHAs of a GitHub Pull Request"). An earlier version of this
        # exception required this field to exactly equal `head` and was
        # empirically found to fail closed on a genuine, correctly-shaped
        # PR run for exactly that reason (Verify run 32855140709 on this
        # repository) -- this field is deliberately NOT cross-checked at
        # all now; only the parent-order/tree checks (which name real,
        # already-pushed branch tips, not an ephemeral merge SHA) bind the
        # exception.
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(
            base_sha=subject, head_sha=seal, merge_commit_sha="d" * 40
        )
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            self.assertEqual(checker.check_scope_binding_seal(), [])

    def test_duplicate_json_key_in_event_is_rejected(self) -> None:
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        event_path = self._write_github_event(
            base_sha=subject, head_sha=seal, duplicate_key=True
        )
        with self._github_pull_request_env(event_path=event_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
        )

    def test_missing_event_path_file_is_rejected(self) -> None:
        self._seal()
        seal = _git_output(self.repo, "rev-parse", "HEAD")
        subject = _git_output(self.repo, "rev-parse", "HEAD^^")
        merge_commit = self._merge_seal_into_base(seal, subject)
        missing_path = self.repo / "does-not-exist-event.json"
        with self._github_pull_request_env(event_path=missing_path, head=merge_commit):
            errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("is not current HEAD" in e and "immediate parent" in e for e in errors)
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

    # -- tooling_sha256 binding --------------------------------------------

    def test_old_schema_without_tooling_sha256_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        del binding["tooling_sha256"]
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("unexpected key set" in e for e in errors))

    def test_tooling_file_changed_after_seal_is_rejected(self) -> None:
        self._seal()
        any_rel_path = next(iter(evidence.SEALED_TOOLING_FILES))
        (self.repo / any_rel_path).write_text("# tampered tool content\n", encoding="utf-8")
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("tooling changed after the seal" in e for e in errors))

    def test_tooling_file_deleted_after_seal_is_rejected(self) -> None:
        self._seal()
        any_rel_path = next(iter(evidence.SEALED_TOOLING_FILES))
        (self.repo / any_rel_path).unlink()
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("is missing" in e and any_rel_path in e for e in errors))

    def test_tooling_file_replaced_with_symlink_is_rejected(self) -> None:
        self._seal()
        any_rel_path = next(iter(evidence.SEALED_TOOLING_FILES))
        target = self.repo / any_rel_path
        target.unlink()
        (self.repo / "SOURCE.txt").resolve()
        target.symlink_to(self.repo / "SOURCE.txt")
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("is a symlink" in e and any_rel_path in e for e in errors))

    def test_missing_tooling_entry_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        any_rel_path = next(iter(binding["tooling_sha256"]))
        del binding["tooling_sha256"][any_rel_path]
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("tooling_sha256 key set" in e for e in errors))

    def test_extra_tooling_entry_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        binding["tooling_sha256"]["scripts/not_a_real_tool.py"] = "0" * 64
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("tooling_sha256 key set" in e for e in errors))

    def test_wrong_tooling_hash_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        any_rel_path = next(iter(binding["tooling_sha256"]))
        binding["tooling_sha256"][any_rel_path] = "ab" * 32
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any("current bytes" in e and "do not match the sealed digest" in e for e in errors)
        )

    def test_malformed_tooling_hash_hex_is_rejected(self) -> None:
        self._seal()
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        any_rel_path = next(iter(binding["tooling_sha256"]))
        binding["tooling_sha256"][any_rel_path] = "not-a-hex-digest"
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(any("is not a 64-hex-char sha256" in e for e in errors))

    def test_tooling_hash_matching_worktree_but_not_subject_commit_is_rejected(self) -> None:
        # A fabricated seal: tooling_sha256 is hand-set to match the
        # CURRENT worktree bytes (so the worktree-vs-sealed-digest check
        # alone would pass), but those bytes were never actually what was
        # committed at subject_commit -- caught only by the independent
        # `git show <subject_commit>:<path>` cross-check.
        self._seal()
        any_rel_path = next(iter(evidence.SEALED_TOOLING_FILES))
        (self.repo / any_rel_path).write_text("# bytes never actually committed\n", encoding="utf-8")
        binding = json.loads((evidence.EVIDENCE_DIR / "scope_binding.json").read_text())
        binding["tooling_sha256"][any_rel_path] = evidence.sha256_file(self.repo / any_rel_path)
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        errors = checker.check_scope_binding_seal()
        self.assertTrue(
            any(
                "sha256 at subject_commit" in e and "does not match the sealed digest" in e
                for e in errors
            )
        )


class FullSourceScopeSealCheckTests(unittest.TestCase):
    """check_full_source_scope_seal() -- broad, import-graph-independent
    full source-scope diff (subject_commit vs current HEAD), replacing any
    reliance on ordinary-import AST closure for completeness.

    Builds the same disposable temp-git-repo, sealed three-commit history
    as ScopeBindingSealCheckTests, then proves every named escape (a
    dynamic-import helper, a relative/package-import helper, an arbitrary
    non-Python config file, a workflow/settings/lockfile/build file, a
    new/deleted/renamed tracked file, a symlink introduced at an otherwise
    -allowed path, and a dirty worktree) is caught even though none of
    them are `SEALED_TOOLING_FILES` entries or reached via any ordinary
    `import` statement -- and that the untouched, correctly-sealed history
    (and the exact reviewed allowed-path set itself) passes/matches.
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

    def _write_tooling_files(self) -> None:
        for rel_path in evidence.SEALED_TOOLING_FILES:
            path = self.repo / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# stand-in for {rel_path}\n", encoding="utf-8")

    def _seal(self, extra_subject_files: dict[str, str] | None = None) -> None:
        (self.repo / "SOURCE.txt").write_text("subject source\n", encoding="utf-8")
        self._write_tooling_files()
        for rel_path, content in (extra_subject_files or {}).items():
            path = self.repo / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "subject commit")

        self._write_outputs()
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "evidence commit")

        binding = evidence.seal_scope_binding()
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text(
            json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "seal commit")

    def _commit_all(self, message: str) -> None:
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", message)

    def test_only_exact_generated_output_changes_pass(self) -> None:
        self._seal()
        self.assertEqual(checker.check_full_source_scope_seal(), [])

    def test_dynamic_import_helper_changed_is_rejected(self) -> None:
        # Simulates a helper only ever reached via a dynamic
        # importlib.import_module() call -- invisible to
        # _discover_local_tooling_closure()'s ordinary-import AST walk,
        # but still caught here because it is not an allowed output path.
        self._seal(extra_subject_files={"scripts/dynamic_helper.py": "# original\n"})
        (self.repo / "scripts" / "dynamic_helper.py").write_text(
            "# changed after subject_commit, never reached by any ordinary "
            "import statement\n",
            encoding="utf-8",
        )
        self._commit_all("change a dynamically-loaded helper")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(
            any(
                "scripts/dynamic_helper.py" in e and "full source-scope seal violated" in e
                for e in errors
            )
        )

    def test_relative_or_package_import_helper_changed_is_rejected(self) -> None:
        self._seal(
            extra_subject_files={
                "scripts/pkg/__init__.py": "",
                "scripts/pkg/helper.py": "# original\n",
            }
        )
        (self.repo / "scripts" / "pkg" / "helper.py").write_text(
            "# changed -- reached only via `from . import helper`\n", encoding="utf-8"
        )
        self._commit_all("change a relative/package-import helper")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(
            any(
                "scripts/pkg/helper.py" in e and "full source-scope seal violated" in e
                for e in errors
            )
        )

    def test_arbitrary_config_file_changed_is_rejected(self) -> None:
        self._seal(extra_subject_files={"scripts/some_catalog.toml": "value = 1\n"})
        (self.repo / "scripts" / "some_catalog.toml").write_text("value = 2\n", encoding="utf-8")
        self._commit_all("change an arbitrary config file read without any import statement")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(
            any(
                "scripts/some_catalog.toml" in e and "full source-scope seal violated" in e
                for e in errors
            )
        )

    def test_workflow_file_changed_is_rejected(self) -> None:
        self._seal(extra_subject_files={".github/workflows/verify.yml": "name: Verify\n"})
        (self.repo / ".github" / "workflows" / "verify.yml").write_text(
            "name: Verify2\n", encoding="utf-8"
        )
        self._commit_all("change a workflow file")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(
            any(
                ".github/workflows/verify.yml" in e and "full source-scope seal violated" in e
                for e in errors
            )
        )

    def test_gradle_settings_file_changed_is_rejected(self) -> None:
        self._seal(extra_subject_files={"settings.gradle.kts": 'rootProject.name = "x"\n'})
        (self.repo / "settings.gradle.kts").write_text(
            'rootProject.name = "y"\n', encoding="utf-8"
        )
        self._commit_all("change settings.gradle.kts")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(
            any(
                "settings.gradle.kts" in e and "full source-scope seal violated" in e
                for e in errors
            )
        )

    def test_gradle_lockfile_changed_is_rejected(self) -> None:
        self._seal(extra_subject_files={"core/gradle.lockfile": "com.example:x:1.0=compile\n"})
        (self.repo / "core" / "gradle.lockfile").write_text(
            "com.example:x:2.0=compile\n", encoding="utf-8"
        )
        self._commit_all("change a gradle.lockfile")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(
            any(
                "core/gradle.lockfile" in e and "full source-scope seal violated" in e
                for e in errors
            )
        )

    def test_build_file_changed_is_rejected(self) -> None:
        self._seal(extra_subject_files={"core/build.gradle.kts": "// v1\n"})
        (self.repo / "core" / "build.gradle.kts").write_text("// v2\n", encoding="utf-8")
        self._commit_all("change a build.gradle.kts")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(
            any(
                "core/build.gradle.kts" in e and "full source-scope seal violated" in e
                for e in errors
            )
        )

    def test_new_tracked_file_outside_allowed_set_is_rejected(self) -> None:
        self._seal()
        (self.repo / "NEW_FILE.txt").write_text("new\n", encoding="utf-8")
        self._commit_all("add a new tracked file")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(
            any("NEW_FILE.txt" in e and "full source-scope seal violated" in e for e in errors)
        )

    def test_deleted_tracked_file_outside_allowed_set_is_rejected(self) -> None:
        self._seal(extra_subject_files={"TO_DELETE.txt": "gone soon\n"})
        (self.repo / "TO_DELETE.txt").unlink()
        self._commit_all("delete a tracked file")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(
            any("TO_DELETE.txt" in e and "full source-scope seal violated" in e for e in errors)
        )

    def test_renamed_tracked_file_outside_allowed_set_is_rejected(self) -> None:
        self._seal(extra_subject_files={"OLD_NAME.txt": "content\n"})
        (self.repo / "OLD_NAME.txt").rename(self.repo / "NEW_NAME.txt")
        self._commit_all("rename a tracked file")
        errors = checker.check_full_source_scope_seal()
        # --no-renames means this surfaces as delete-of-old plus add-of-new,
        # each independently outside the allowed set -- both are reported.
        self.assertTrue(any("OLD_NAME.txt" in e for e in errors))
        self.assertTrue(any("NEW_NAME.txt" in e for e in errors))

    def test_symlink_introduced_at_an_allowed_path_is_rejected(self) -> None:
        self._seal()
        any_name = next(iter(evidence.evidence_output_files()))
        target_path = evidence.EVIDENCE_DIR / any_name
        target_path.unlink()
        target_path.symlink_to(self.repo / "SOURCE.txt")
        self._commit_all("replace a generated evidence output with a symlink")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(any("is a symlink as of HEAD" in e for e in errors))

    def test_worktree_staged_changes_are_rejected(self) -> None:
        self._seal()
        (self.repo / "STAGED.txt").write_text("staged\n", encoding="utf-8")
        _git(self.repo, "add", "STAGED.txt")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(any("staged/unstaged changes" in e for e in errors))

    def test_worktree_unstaged_changes_are_rejected(self) -> None:
        self._seal()
        any_name = next(iter(evidence.evidence_output_files()))
        (evidence.EVIDENCE_DIR / any_name).write_text('{"tampered": true}\n', encoding="utf-8")
        errors = checker.check_full_source_scope_seal()
        self.assertTrue(any("staged/unstaged changes" in e for e in errors))

    def test_missing_scope_binding_is_a_silent_no_op(self) -> None:
        # Deferred to check_scope_binding_seal(), which already reports
        # "is missing" -- this function must not also raise/duplicate it.
        self._seal()
        (evidence.EVIDENCE_DIR / "scope_binding.json").unlink()
        self.assertEqual(checker.check_full_source_scope_seal(), [])

    def test_allowed_set_is_exactly_generated_outputs_plus_seal_and_digest(self) -> None:
        # Regression guard against silently widening the exclusion set --
        # it must be EXACTLY this formula, never a hand-added extra path.
        expected = {f"docs/evidence/{name}" for name in evidence.evidence_output_files()}
        expected.add("docs/evidence/scope_binding.json")
        expected.add("docs/evidence/LEGAL_EVIDENCE_DIGEST.txt")
        self.assertEqual(checker._allowed_post_subject_change_paths(), frozenset(expected))


def _git_output(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


if __name__ == "__main__":
    unittest.main()
