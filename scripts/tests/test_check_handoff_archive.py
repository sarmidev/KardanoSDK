"""Coverage tests for the HANDOFF archive inventory check."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_handoff_archive as archive  # noqa: E402


class HandoffArchiveCheckTests(unittest.TestCase):
    def test_current_tree_restores_recorded_snapshot(self) -> None:
        errors = archive.verify_pre_curation_snapshot(REPO_ROOT)
        self.assertEqual(errors, [])

    def test_mutated_prose_fails_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / archive.ARCHIVE_RELATIVE
            dest.parent.mkdir(parents=True)
            original = (REPO_ROOT / archive.ARCHIVE_RELATIVE).read_text(encoding="utf-8")
            dest.write_text(original.replace("Kardano SDK", "Changed SDK", 1), encoding="utf-8")
            for relative in archive.DECISIONS_TARGETS:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("placeholder\n", encoding="utf-8")
            errors = archive.verify_pre_curation_snapshot(root)
            self.assertTrue(any("SHA-256" in error for error in errors))

    def test_missing_link_target_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / archive.ARCHIVE_RELATIVE
            dest.parent.mkdir(parents=True)
            dest.write_text(
                (REPO_ROOT / archive.ARCHIVE_RELATIVE).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            errors = archive.verify_pre_curation_snapshot(root)
            self.assertTrue(any("link target missing" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
