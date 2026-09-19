"""Existence and relative-link checks for Phase 1 readiness files."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_ROOT_FILES = (
    "SECURITY.md",
    "GOVERNANCE.md",
    "SUPPORT.md",
    "MAINTAINERS.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
)

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
DEPENDABOT = REPO_ROOT / ".github" / "dependabot.yml"


def _resolve_repo_link(source: Path, target: str) -> Path | None:
    if target.startswith(("http://", "https://", "mailto:")):
        return None
    path_part = target.split("#", 1)[0].split("?", 1)[0]
    if not path_part:
        return None
    return (source.parent / path_part).resolve()


class Phase1ReadinessDocsTests(unittest.TestCase):
    def test_required_root_files_exist(self) -> None:
        for name in REQUIRED_ROOT_FILES:
            path = REPO_ROOT / name
            self.assertTrue(path.is_file(), name)
            if path.suffix == ".md":
                self.assertGreater(path.stat().st_size, 0, name)

    def test_docs_security_is_a_pointer_to_root(self) -> None:
        pointer = REPO_ROOT / "docs" / "SECURITY.md"
        text = pointer.read_text(encoding="utf-8")
        self.assertIn("../SECURITY.md", text)
        self.assertIn("pointer", text.lower())
        self.assertNotIn("| Component | Current status |", text)

    def test_readme_points_at_canonical_policy_files(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for name in (
            "SECURITY.md",
            "GOVERNANCE.md",
            "SUPPORT.md",
            "MAINTAINERS.md",
            "CONTRIBUTING.md",
        ):
            self.assertIn(name, text)

    def test_code_of_conduct_and_contributing_reference_root_security(self) -> None:
        conduct = (REPO_ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
        contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("SECURITY.md", conduct)
        self.assertNotIn("docs/SECURITY.md", conduct)
        self.assertIn("GOVERNANCE.md", contributing)
        self.assertIn("SUPPORT.md", contributing)
        self.assertIn("SECURITY.md", contributing)

    def test_relative_links_in_new_policy_files_resolve(self) -> None:
        files = [
            REPO_ROOT / "SECURITY.md",
            REPO_ROOT / "GOVERNANCE.md",
            REPO_ROOT / "SUPPORT.md",
            REPO_ROOT / "MAINTAINERS.md",
            REPO_ROOT / "docs" / "SECURITY.md",
            REPO_ROOT / "docs" / "INTERSECT_PHASE1_APPLICATION.md",
        ]
        missing: list[str] = []
        for path in files:
            text = path.read_text(encoding="utf-8")
            for match in LINK_RE.finditer(text):
                resolved = _resolve_repo_link(path, match.group(1))
                if resolved is None:
                    continue
                try:
                    resolved.relative_to(REPO_ROOT.resolve())
                except ValueError:
                    continue
                if not resolved.exists():
                    missing.append(f"{path.relative_to(REPO_ROOT)} -> {match.group(1)}")
        self.assertEqual(missing, [])

    def test_dependabot_covers_supported_ecosystems_only(self) -> None:
        text = DEPENDABOT.read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: gradle", text)
        self.assertIn("package-ecosystem: cargo", text)
        self.assertIn("package-ecosystem: github-actions", text)
        self.assertIn("interval: weekly", text)
        self.assertNotRegex(text, r"(?m)^[^#]*auto-merge")
        self.assertNotIn("package-ecosystem: npm", text)
        self.assertNotIn("package-ecosystem: pip", text)

    def test_maintainers_does_not_invent_linkedin(self) -> None:
        text = (REPO_ROOT / "MAINTAINERS.md").read_text(encoding="utf-8")
        self.assertNotIn("linkedin.com", text.lower())
        self.assertIn("sarmidev@outlook.es", text)
        self.assertIn("bus factor", text.lower())

    def test_application_draft_keeps_phase_and_band_honesty(self) -> None:
        text = (REPO_ROOT / "docs" / "INTERSECT_PHASE1_APPLICATION.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Phase 1", text)
        self.assertIn("Phase 2", text)
        self.assertIn("Phase 3", text)
        self.assertIn("[OWNER TO ADD]", text)
        self.assertIn("No external adoption", text)
        self.assertIn("not an application claim", text.lower())
        self.assertIn("No pitch deck is added", text)
