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

    def test_markdown_emphasis_negation_then_second_hit(self) -> None:
        line = "**not** safe, but later guaranteed."
        hits = _hits(line)
        self.assertEqual(hits[0].phrase, "safe")
        self.assertTrue(hits[0].permitted)
        self.assertEqual(hits[0].reason, "negation")
        self.assertEqual(hits[1].phrase, "guaranteed")
        self.assertFalse(hits[1].permitted)


class QualifierAndBoundaryTests(unittest.TestCase):
    def test_hyphen_compound_is_permitted(self) -> None:
        hits = _hits("Use a type-safe wrapper.")
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0].permitted)
        self.assertEqual(hits[0].reason, "hyphen-compound")

    def test_plain_safe_is_prohibited(self) -> None:
        hits = _prohibited("This is safe.")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].column, 9)

    def test_case_insensitive(self) -> None:
        hits = _prohibited("SAFE and Secure.")
        self.assertEqual([h.phrase for h in hits], ["safe", "secure"])

    def test_markdown_wrapped_phrase_is_still_found(self) -> None:
        hits = _prohibited("This is **safe** and `secure`.")
        self.assertEqual([h.phrase for h in hits], ["safe", "secure"])

    def test_longest_phrase_first_does_not_also_report_safe(self) -> None:
        hits = _prohibited("It is cryptographically safe.")
        self.assertEqual([h.phrase for h in hits], ["cryptographically safe"])
        self.assertEqual(hits[0].column, 7)

    def test_second_safe_after_long_phrase_is_separate(self) -> None:
        hits = _prohibited("cryptographically safe and later safe")
        self.assertEqual(
            [h.phrase for h in hits],
            ["cryptographically safe", "safe"],
        )


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

    def test_same_filename_outside_excluded_path_still_fails(self) -> None:
        excluded = "shared/src/commonTest/kotlin/org/sarmidev/kardano/playground/ui/DemoCopyTest.kt"
        other = "other/DemoCopyTest.kt"
        self.assertTrue(scanner.is_excluded(excluded))
        self.assertFalse(scanner.is_excluded(other))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (excluded, other):
                path = root / relative
                path.parent.mkdir(parents=True)
                path.write_text("This is safe.\n", encoding="utf-8")
            findings = scanner.prohibited_findings(scanner.scan_paths(root, [excluded, other]))
            self.assertEqual([f.path for f in findings], [other])

    def test_prefix_exclusion_does_not_cover_sibling_directory(self) -> None:
        inside = "docs/AUDIT/note.md"
        sibling = "docs/AUDIT-EXTRA/note.md"
        self.assertTrue(scanner.is_excluded(inside))
        self.assertFalse(scanner.is_excluded(sibling))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (inside, sibling):
                path = root / relative
                path.parent.mkdir(parents=True)
                path.write_text("This is safe.\n", encoding="utf-8")
            findings = scanner.prohibited_findings(
                scanner.scan_paths(root, [inside, sibling])
            )
            self.assertEqual([f.path for f in findings], [sibling])


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
