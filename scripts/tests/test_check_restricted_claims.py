"""Unit tests for match-by-match restricted-claim classification."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_restricted_claims as scanner  # noqa: E402


def _hits(text: str, path: str = "sample.md") -> list[scanner.Finding]:
    return scanner.scan_text(path, text)


def _prohibited(text: str, path: str = "sample.md") -> list[scanner.Finding]:
    return [finding for finding in _hits(text, path) if not finding.permitted]


class SameLineClassificationTests(unittest.TestCase):
    def test_permitted_and_prohibited_share_one_line(self) -> None:
        line = "Not audited. This is safe."
        hits = _hits(line)
        self.assertEqual(
            [(h.phrase, h.column, h.permitted, h.reason) for h in hits],
            [
                ("audited", 5, True, "negation"),
                ("safe", 22, False, "restricted-claim"),
            ],
        )
        self.assertEqual([h.phrase for h in _prohibited(line)], ["safe"])

    def test_hyphen_compound_then_plain_safe_on_one_line(self) -> None:
        line = "display-safe metadata, later safe"
        hits = _hits(line)
        self.assertEqual(
            [(h.phrase, h.permitted, h.reason) for h in hits],
            [
                ("safe", False, "restricted-claim"),
                ("safe", False, "restricted-claim"),
            ],
        )


class QualifierAndBoundaryTests(unittest.TestCase):
    def test_display_safe_compound_is_prohibited(self) -> None:
        hits = _prohibited("already carry only public, display-safe metadata")
        self.assertEqual([h.phrase for h in hits], ["safe"])

    def test_funds_safe_is_prohibited(self) -> None:
        hits = _prohibited("Not a funds-safe issue.")
        self.assertEqual([h.phrase for h in hits], ["safe"])

    def test_crypto_safe_is_prohibited(self) -> None:
        hits = _prohibited("Use the crypto-safe backend.")
        self.assertEqual([h.phrase for h in hits], ["safe"])

    def test_type_safe_is_not_a_reviewed_compound(self) -> None:
        hits = _prohibited("Use a type-safe wrapper.")
        self.assertEqual([h.phrase for h in hits], ["safe"])

    def test_sentence_boundary_negation_does_not_qualify(self) -> None:
        hits = _prohibited("This does not. This is safe.")
        self.assertEqual([h.phrase for h in hits], ["safe"])
        self.assertEqual(hits[0].column, 24)

    def test_negation_does_not_cross_period_on_same_line(self) -> None:
        hits = _prohibited("This does not. safe")
        self.assertEqual([h.phrase for h in hits], ["safe"])

    def test_markdown_emphasis_negation_still_qualifies(self) -> None:
        hits = _hits("**not** safe, but later guaranteed.")
        self.assertTrue(hits[0].permitted)
        self.assertEqual(hits[0].reason, "negation")
        self.assertFalse(hits[1].permitted)
        self.assertEqual(hits[1].phrase, "guaranteed")

    def test_markdown_split_safe_is_detected(self) -> None:
        hits = _prohibited("This is s**afe**.")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].phrase, "safe")
        self.assertEqual(hits[0].column, 9)

    def test_markdown_split_long_phrase_is_one_hit(self) -> None:
        hits = _prohibited("It is crypto**graphically** safe.")
        self.assertEqual([h.phrase for h in hits], ["cryptographically safe"])
        self.assertEqual(hits[0].column, 7)

    def test_plain_safe_is_prohibited(self) -> None:
        hits = _prohibited("This is safe.")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].column, 9)

    def test_case_and_punctuation(self) -> None:
        hits = _prohibited("SAFE! Secure.")
        self.assertEqual([h.phrase for h in hits], ["safe", "secure"])

    def test_markdown_wrapped_phrase_is_still_found(self) -> None:
        hits = _prohibited("This is **safe** and `secure`.")
        self.assertEqual([h.phrase for h in hits], ["safe", "secure"])

    def test_longest_phrase_first_does_not_also_report_safe(self) -> None:
        hits = _prohibited("It is cryptographically safe.")
        self.assertEqual([h.phrase for h in hits], ["cryptographically safe"])
        self.assertEqual(hits[0].column, 7)


class NearMissTests(unittest.TestCase):
    def test_near_miss_words_are_not_matches(self) -> None:
        text = "\n".join(
            [
                "safely stored",
                "safety note",
                "safest path",
                "unsafe input",
                "secured by the caller",
                "securely wiped",
                "audit trail",
                "guarantee of nothing",
                "guarantees nothing",
                "hardening discussion",
            ]
        )
        self.assertEqual(_hits(text), [])


class ExclusionBoundaryTests(unittest.TestCase):
    def test_exact_excluded_path_is_skipped(self) -> None:
        excluded = next(iter(scanner.EXACT_PATH_EXCLUSIONS))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / excluded
            path.parent.mkdir(parents=True)
            path.write_text("This is safe.\n", encoding="utf-8")
            findings = scanner.scan_paths(root, [excluded])
            self.assertEqual(findings, [])

    def test_new_adr_with_positive_claim_is_detected(self) -> None:
        relative = "docs/DECISIONS/9999-new-decision.md"
        self.assertFalse(scanner.is_excluded(relative))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_text("This module is safe.\n", encoding="utf-8")
            findings = scanner.prohibited_findings(scanner.scan_paths(root, [relative]))
            self.assertEqual([f.path for f in findings], [relative])

    def test_new_audit_with_positive_claim_is_detected(self) -> None:
        relative = "docs/AUDIT/2099-future-audit.md"
        self.assertFalse(scanner.is_excluded(relative))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_text("The SDK is production-ready.\n", encoding="utf-8")
            findings = scanner.prohibited_findings(scanner.scan_paths(root, [relative]))
            self.assertEqual([f.phrase for f in findings], ["production-ready"])

    def test_directory_name_is_not_an_exclusion(self) -> None:
        self.assertFalse(scanner.is_excluded("docs/DECISIONS/"))
        self.assertFalse(scanner.is_excluded("docs/AUDIT/"))

    def test_evolving_adrs_are_not_whole_file_excluded(self) -> None:
        for relative in (
            "docs/DECISIONS/0001-cbor-and-parser-policy.md",
            "docs/DECISIONS/0012-address-encoding-and-roundtrip.md",
            "docs/DECISIONS/0018-signing-scope-enforcement-and-publication.md",
            "docs/PHASE_1_PLAN.md",
        ):
            self.assertFalse(scanner.is_excluded(relative), relative)


class FilenameAndExtensionTests(unittest.TestCase):
    def test_nul_separated_listing_keeps_newline_filename(self) -> None:
        raw = b"README.md\0docs/weird\nname.md\0"
        self.assertEqual(
            scanner.parse_ls_files_z(raw),
            ["README.md", "docs/weird\nname.md"],
        )

    def test_newly_included_swift_extension_is_scanned(self) -> None:
        self.assertTrue(scanner.is_scan_path("iosApp/iosApp/ContentView.swift"))
        hits = _prohibited("This is safe.", path="iosApp/iosApp/ContentView.swift")
        self.assertEqual(hits[0].path, "iosApp/iosApp/ContentView.swift")

    def test_newly_included_yaml_and_json_extensions_are_scanned(self) -> None:
        self.assertTrue(scanner.is_scan_path(".github/workflows/verify.yml"))
        self.assertTrue(scanner.is_scan_path("package.json"))
        self.assertTrue(scanner.is_scan_path("gradle.properties"))

    def test_mixed_case_extensions_are_scanned_with_original_paths(self) -> None:
        for relative in ("NOTES.MD", "Config.Xml", "App.SWIFT", "mixed.YmL"):
            self.assertTrue(scanner.is_scan_path(relative), relative)
            hits = _prohibited("This is safe.", path=relative)
            self.assertEqual(hits[0].path, relative)
            self.assertEqual(hits[0].phrase, "safe")


class OccurrenceAllowlistTests(unittest.TestCase):
    ADR = "docs/DECISIONS/0018-signing-scope-enforcement-and-publication.md"

    def test_exact_allowed_line_at_exact_line_number_passes(self) -> None:
        text = (REPO_ROOT / self.ADR).read_text(encoding="utf-8")
        findings = scanner.scan_text(self.ADR, text)
        prohibited = scanner.prohibited_findings(findings)
        self.assertEqual(prohibited, [], "\n".join(f.format() for f in prohibited))
        allowed = [f for f in findings if f.reason == "allowed-occurrence"]
        self.assertEqual([f.phrase for f in allowed], ["safe"])
        self.assertEqual(allowed[0].line, 162)

    def test_duplicate_identical_line_elsewhere_fails(self) -> None:
        original = (REPO_ROOT / self.ADR).read_text(encoding="utf-8")
        allowed_line = original.splitlines()[161]
        duplicated = original + "\n" + allowed_line + "\n"
        findings = scanner.scan_text(self.ADR, duplicated)
        allowed = [f for f in findings if f.reason == "allowed-occurrence"]
        prohibited = scanner.prohibited_findings(findings)
        self.assertEqual([f.line for f in allowed], [162])
        self.assertEqual([f.phrase for f in prohibited], ["safe"])
        self.assertGreater(prohibited[0].line, 162)

    def test_shifted_line_number_fails(self) -> None:
        original = (REPO_ROOT / self.ADR).read_text(encoding="utf-8")
        shifted = "Inserted line for fail-closed numbering.\n" + original
        prohibited = scanner.prohibited_findings(scanner.scan_text(self.ADR, shifted))
        self.assertTrue(any(f.phrase == "safe" and f.line == 163 for f in prohibited))

    def test_edited_historical_line_fails(self) -> None:
        original = (REPO_ROOT / self.ADR).read_text(encoding="utf-8")
        edited = original.replace(
            'as "safe" or "restricted"',
            'as "safe" and still safe',
            1,
        )
        self.assertNotEqual(edited, original)
        prohibited = scanner.prohibited_findings(scanner.scan_text(self.ADR, edited))
        self.assertTrue(any(f.phrase == "safe" and not f.permitted for f in prohibited))

    def test_appended_positive_claim_in_same_adr_fails(self) -> None:
        original = (REPO_ROOT / self.ADR).read_text(encoding="utf-8")
        appended = original + "\nThis signing path is safe.\n"
        prohibited = scanner.prohibited_findings(scanner.scan_text(self.ADR, appended))
        self.assertEqual([f.phrase for f in prohibited], ["safe"])
        self.assertEqual(prohibited[0].line, original.count("\n") + 2)

    def test_second_occurrence_on_allowed_line_fails(self) -> None:
        same_hash_line = "safe token then another safe token"
        allowed_one = frozenset(
            {
                (
                    self.ADR,
                    1,
                    scanner.line_content_hash(same_hash_line),
                    "safe",
                    1,
                )
            }
        )
        hits = scanner.scan_text(
            self.ADR, same_hash_line + "\n", allowed_keys=allowed_one
        )
        self.assertEqual(
            [(h.phrase, h.permitted, h.reason) for h in hits],
            [
                ("safe", True, "allowed-occurrence"),
                ("safe", False, "restricted-claim"),
            ],
        )


class CurrentTreeTests(unittest.TestCase):
    def test_current_tracked_tree_has_no_prohibited_hits(self) -> None:
        paths = scanner.list_tracked_scan_paths(REPO_ROOT)
        prohibited = scanner.prohibited_findings(scanner.scan_paths(REPO_ROOT, paths))
        self.assertEqual(
            prohibited,
            [],
            "\n".join(finding.format() for finding in prohibited),
        )


if __name__ == "__main__":
    unittest.main()
