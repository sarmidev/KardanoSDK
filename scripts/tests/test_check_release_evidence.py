"""Coverage tests for scripts/check_release_evidence.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_release_evidence as checker  # noqa: E402


class RealTreeChecksTests(unittest.TestCase):
    """The current tracked tree must pass every check with zero errors."""

    def test_notice_license_cross_reference_passes(self) -> None:
        self.assertEqual(checker.check_notice_license_references(), [])

    def test_native_inventory_matches_checksums(self) -> None:
        self.assertEqual(checker.check_native_inventory_matches_checksums(), [])

    def test_evidence_is_freshly_regenerable(self) -> None:
        self.assertEqual(checker.check_evidence_is_freshly_regenerable(), [])

    def test_legal_review_has_no_placeholders(self) -> None:
        self.assertEqual(checker.check_legal_review_placeholders(), [])

    def test_main_passes_on_real_tree(self) -> None:
        self.assertEqual(checker.main(), 0)


class PlaceholderDetectionTests(unittest.TestCase):
    def test_detects_generic_placeholder_token(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown("Reviewer: TBD\n"),
        ):
            errors = checker.check_legal_review_placeholders()
        self.assertTrue(any("TBD" in e for e in errors))

    def test_allowed_open_gate_marker_is_accepted(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown(
                "- Status: OPEN — pending owner/counsel review\n"
            ),
        ):
            errors = checker.check_legal_review_placeholders()
        self.assertEqual(errors, [])

    def test_unrecognized_status_value_is_rejected(self) -> None:
        with mock.patch.object(
            checker,
            "LEGAL_REVIEW_PATH",
            _write_temp_markdown("- Status: open, will fill in later\n"),
        ):
            errors = checker.check_legal_review_placeholders()
        self.assertTrue(any("unrecognized Status" in e for e in errors))


def _write_temp_markdown(text: str) -> Path:
    import tempfile

    fd = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    fd.write(text)
    fd.close()
    return Path(fd.name)


if __name__ == "__main__":
    unittest.main()
