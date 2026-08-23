"""Unit tests for SHA-pinned GitHub Action checking."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import action_pin_inventory as inventory  # noqa: E402
import check_action_pins as pins  # noqa: E402

CHECKOUT = inventory.PIN_BY_ACTION["actions/checkout"]
WORKFLOW = """name: Sample
on:
  push:
    branches:
      - main
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{sha} # {release}
"""


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _review_text() -> str:
    return (REPO_ROOT / inventory.REVIEW_DOC).read_text(encoding="utf-8")


class ParseUseLineTests(unittest.TestCase):
    def test_sha_pin_is_accepted(self) -> None:
        ref = pins.parse_use_line(
            "w.yml",
            1,
            f"        uses: actions/checkout@{CHECKOUT.sha} # {CHECKOUT.release}",
        )
        assert ref is not None
        self.assertEqual(ref.kind, "pinned")
        self.assertEqual(ref.action, "actions/checkout")
        self.assertEqual(ref.sha, CHECKOUT.sha)

    def test_quoted_sha_pin_is_accepted(self) -> None:
        ref = pins.parse_use_line(
            "w.yml",
            1,
            f'        uses: "actions/checkout@{CHECKOUT.sha}"',
        )
        assert ref is not None
        self.assertEqual(ref.kind, "pinned")

    def test_tag_only_is_unpinned(self) -> None:
        ref = pins.parse_use_line("w.yml", 1, "        uses: actions/checkout@v7")
        assert ref is not None
        self.assertEqual(ref.kind, "unpinned")

    def test_v4_major_tag_is_unpinned(self) -> None:
        ref = pins.parse_use_line("w.yml", 1, "        uses: actions/checkout@v4")
        assert ref is not None
        self.assertEqual(ref.kind, "unpinned")

    def test_v4_3_1_tag_is_unpinned(self) -> None:
        ref = pins.parse_use_line("w.yml", 1, "        uses: actions/checkout@v4.3.1")
        assert ref is not None
        self.assertEqual(ref.kind, "unpinned")

    def test_uppercase_sha_is_unpinned(self) -> None:
        upper = CHECKOUT.sha.upper()
        ref = pins.parse_use_line("w.yml", 1, f"        uses: actions/checkout@{upper}")
        assert ref is not None
        self.assertEqual(ref.kind, "unpinned")

    def test_short_sha_is_unpinned(self) -> None:
        ref = pins.parse_use_line(
            "w.yml", 1, f"        uses: actions/checkout@{CHECKOUT.sha[:12]}"
        )
        assert ref is not None
        self.assertEqual(ref.kind, "unpinned")

    def test_local_composite_is_local(self) -> None:
        ref = pins.parse_use_line(
            "w.yml", 1, "        uses: ./.github/actions/upload-pages"
        )
        assert ref is not None
        self.assertEqual(ref.kind, "local")

    def test_setup_gradle_path_is_parsed(self) -> None:
        gradle = inventory.PIN_BY_ACTION["gradle/actions/setup-gradle"]
        ref = pins.parse_use_line(
            "w.yml",
            1,
            f"        uses: gradle/actions/setup-gradle@{gradle.sha}",
        )
        assert ref is not None
        self.assertEqual(ref.action, "gradle/actions/setup-gradle")
        self.assertEqual(ref.sha, gradle.sha)


class InventoryTests(unittest.TestCase):
    def test_every_recorded_sha_is_lowercase_hex(self) -> None:
        for pin in inventory.ACTION_PINS:
            self.assertTrue(inventory.is_lowercase_sha(pin.sha), pin.action)
            for child in pin.transitive:
                self.assertTrue(
                    inventory.is_lowercase_sha(child.sha),
                    f"{pin.action} -> {child.action}",
                )

    def test_composite_pins_record_transitive_shas(self) -> None:
        composites = [pin for pin in inventory.ACTION_PINS if pin.kind == "composite"]
        self.assertEqual(
            [pin.action for pin in composites],
            ["actions/upload-pages-artifact"],
        )
        child = composites[0].transitive[0]
        self.assertEqual(child.action, "actions/upload-artifact")
        self.assertEqual(child.sha, "bbbca2ddaa5d8feaa63e36b76fdaad77386f024f")

    def test_javascript_actions_have_no_transitive_uses(self) -> None:
        for pin in inventory.ACTION_PINS:
            if pin.kind == "javascript":
                self.assertEqual(pin.transitive, (), pin.action)


class CheckUseRefTests(unittest.TestCase):
    def test_unknown_action_is_a_finding(self) -> None:
        other_sha = "0" * 40
        ref = pins.UseRef(
            "w.yml",
            3,
            f"octo/example@{other_sha}",
            "octo/example",
            other_sha,
            "pinned",
        )
        findings = pins.check_use_ref(ref)
        self.assertEqual(len(findings), 1)
        self.assertIn("not recorded", findings[0].message)

    def test_sha_mismatch_is_a_finding(self) -> None:
        other = "0" * 40
        ref = pins.UseRef(
            "w.yml",
            3,
            f"actions/checkout@{other}",
            "actions/checkout",
            other,
            "pinned",
        )
        findings = pins.check_use_ref(ref)
        self.assertEqual(len(findings), 1)
        self.assertIn("does not match inventory", findings[0].message)


class FakeTreeTests(unittest.TestCase):
    def test_tag_only_workflow_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                ".github/workflows/verify.yml",
                WORKFLOW.format(sha="v4", release="v4"),
            )
            _write(root, inventory.REVIEW_DOC, _review_text())
            findings = pins.collect_findings(root)
            self.assertTrue(
                any("40-char lowercase SHA" in item.message for item in findings)
            )

    def test_missing_on_key_fails_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                ".github/workflows/verify.yml",
                "name: Broken\njobs:\n  x:\n    runs-on: ubuntu-latest\n",
            )
            _write(root, inventory.REVIEW_DOC, _review_text())
            findings = pins.collect_findings(root)
            self.assertTrue(any("on:" in item.message for item in findings))

    def test_local_composite_with_floating_child_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                ".github/workflows/verify.yml",
                WORKFLOW.format(sha=CHECKOUT.sha, release=CHECKOUT.release),
            )
            _write(
                root,
                ".github/actions/sample/action.yml",
                "name: sample\nruns:\n  using: composite\n  steps:\n"
                "    - uses: actions/upload-artifact@v4\n",
            )
            _write(root, inventory.REVIEW_DOC, _review_text())
            findings = pins.collect_findings(root)
            self.assertTrue(
                any("40-char lowercase SHA" in item.message for item in findings)
            )


class StructuralYamlTests(unittest.TestCase):
    def test_flow_mapping_uses_is_found(self) -> None:
        text = (
            "name: Flow\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
            f"    steps:\n      - {{uses: actions/checkout@{CHECKOUT.sha}}}\n"
        )
        entries = pins.extract_uses_from_text(text)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["value"], f"actions/checkout@{CHECKOUT.sha}")

    def test_uses_with_space_before_colon_is_found(self) -> None:
        text = f"uses : actions/checkout@{CHECKOUT.sha}\n"
        entries = pins.extract_uses_from_text(text)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["value"], f"actions/checkout@{CHECKOUT.sha}")

    def test_flow_mapping_unpinned_workflow_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                ".github/workflows/verify.yml",
                "name: Flow\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - {uses: actions/checkout@v7}\n",
            )
            _write(root, inventory.REVIEW_DOC, _review_text())
            findings = pins.collect_findings(root)
            self.assertTrue(
                any("40-char lowercase SHA" in item.message for item in findings)
            )

    def test_local_action_outside_github_actions_is_inspected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                ".github/workflows/verify.yml",
                "name: Sample\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - uses: ./tools/sample-action\n",
            )
            _write(
                root,
                "tools/sample-action/action.yml",
                "name: sample\nruns:\n  using: composite\n  steps:\n"
                "    - uses: actions/upload-artifact@v4\n",
            )
            _write(root, inventory.REVIEW_DOC, _review_text())
            findings = pins.collect_findings(root)
            self.assertTrue(
                any("40-char lowercase SHA" in item.message for item in findings)
            )

    def test_action_yaml_filename_is_inspected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                ".github/workflows/verify.yml",
                "name: Sample\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - uses: ./tools/yaml-action\n",
            )
            _write(
                root,
                "tools/yaml-action/action.yaml",
                "name: sample\nruns:\n  using: composite\n  steps:\n"
                "    - uses: actions/upload-artifact@v4\n",
            )
            _write(root, inventory.REVIEW_DOC, _review_text())
            findings = pins.collect_findings(root)
            self.assertTrue(
                any("40-char lowercase SHA" in item.message for item in findings)
            )

    def test_reusable_workflow_must_be_recorded(self) -> None:
        sha = "a" * 40
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                ".github/workflows/verify.yml",
                "name: Sample\non:\n  push:\njobs:\n  x:\n"
                f"    uses: octo/tools/.github/workflows/ci.yml@{sha}\n",
            )
            _write(root, inventory.REVIEW_DOC, _review_text())
            findings = pins.collect_findings(root)
            self.assertTrue(
                any("not recorded" in item.message for item in findings)
            )

    def test_local_action_cycle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                ".github/workflows/verify.yml",
                "name: Sample\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - uses: ./tools/a\n",
            )
            _write(
                root,
                "tools/a/action.yml",
                "name: a\nruns:\n  using: composite\n  steps:\n    - uses: ./tools/b\n",
            )
            _write(
                root,
                "tools/b/action.yml",
                "name: b\nruns:\n  using: composite\n  steps:\n    - uses: ./tools/a\n",
            )
            _write(root, inventory.REVIEW_DOC, _review_text())
            findings = pins.collect_findings(root)
            self.assertTrue(any("cycle" in item.message for item in findings))

    def test_missing_local_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                ".github/workflows/verify.yml",
                "name: Sample\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - uses: ./tools/missing\n",
            )
            _write(root, inventory.REVIEW_DOC, _review_text())
            findings = pins.collect_findings(root)
            self.assertTrue(
                any("missing" in item.message for item in findings)
            )

    def test_owner_repo_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                ".github/workflows/verify.yml",
                "name: Sample\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
                f"    steps:\n      - uses: octocat/checkout@{CHECKOUT.sha}\n",
            )
            _write(root, inventory.REVIEW_DOC, _review_text())
            findings = pins.collect_findings(root)
            self.assertTrue(
                any("owner/repo mismatch" in item.message for item in findings)
            )


class LocalDockerActionTests(unittest.TestCase):
    def _tree(
        self,
        action_path: str,
        action_text: str,
        workflow_extra_step: str = "",
    ) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        _write(
            root,
            ".github/workflows/verify.yml",
            "name: Sample\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
            "    steps:\n"
            f"      - uses: actions/checkout@{CHECKOUT.sha}\n"
            f"{workflow_extra_step}",
        )
        _write(root, action_path, action_text)
        _write(root, inventory.REVIEW_DOC, _review_text())
        return root

    def test_local_docker_floating_image_is_rejected(self) -> None:
        root = self._tree(
            "tools/docker-float/action.yml",
            "name: float\nruns:\n  using: docker\n  image: docker://alpine:latest\n",
        )
        findings = pins.collect_findings(root)
        self.assertTrue(
            any(
                "local Docker action is not approved" in item.message
                and "tools/docker-float/action.yml" in item.message
                and "docker://alpine:latest" in item.message
                for item in findings
            ),
            "\n".join(item.format() for item in findings),
        )

    def test_local_docker_digest_image_is_rejected(self) -> None:
        digest = "0" * 64
        image = f"docker://alpine@sha256:{digest}"
        root = self._tree(
            "tools/docker-digest/action.yml",
            f"name: digest\nruns:\n  using: docker\n  image: {image}\n",
        )
        findings = pins.collect_findings(root)
        self.assertTrue(
            any(
                "local Docker action is not approved" in item.message
                and image in item.message
                for item in findings
            ),
            "\n".join(item.format() for item in findings),
        )

    def test_local_docker_dockerfile_image_is_rejected(self) -> None:
        root = self._tree(
            "tools/docker-file/action.yml",
            "name: file\nruns:\n  using: docker\n  image: Dockerfile\n",
        )
        findings = pins.collect_findings(root)
        self.assertTrue(
            any(
                "local Docker action is not approved" in item.message
                and "Dockerfile" in item.message
                for item in findings
            ),
            "\n".join(item.format() for item in findings),
        )

    def test_local_docker_action_yaml_is_rejected(self) -> None:
        root = self._tree(
            "tools/docker-yaml/action.yaml",
            "name: yaml\nruns:\n  using: docker\n  image: docker://alpine:3\n",
        )
        findings = pins.collect_findings(root)
        self.assertTrue(
            any(
                "local Docker action is not approved" in item.message
                and "tools/docker-yaml/action.yaml" in item.message
                and "docker://alpine:3" in item.message
                for item in findings
            ),
            "\n".join(item.format() for item in findings),
        )

    def test_direct_docker_workflow_use_is_rejected(self) -> None:
        root = self._tree(
            "tools/js/action.yml",
            "name: js\nruns:\n  using: node20\n  main: index.js\n",
            workflow_extra_step="      - uses: docker://alpine:latest\n",
        )
        findings = pins.collect_findings(root)
        self.assertTrue(
            any(
                "docker://" in item.message and "alpine:latest" in item.message
                for item in findings
            ),
            "\n".join(item.format() for item in findings),
        )

    def test_local_javascript_and_composite_actions_still_pass(self) -> None:
        root = self._tree(
            "tools/js/action.yml",
            "name: js\nruns:\n  using: node20\n  main: index.js\n",
        )
        _write(
            root,
            "tools/composite/action.yml",
            "name: composite\nruns:\n  using: composite\n  steps:\n"
            "    - run: echo ok\n      shell: bash\n",
        )
        findings = pins.collect_findings(root)
        self.assertEqual(
            findings,
            [],
            "\n".join(item.format() for item in findings),
        )


class CurrentTreeTests(unittest.TestCase):
    def test_current_tree_passes(self) -> None:
        findings = pins.collect_findings(REPO_ROOT)
        self.assertEqual(
            findings,
            [],
            "\n".join(item.format() for item in findings),
        )

    def test_checker_main_exits_zero(self) -> None:
        self.assertEqual(pins.main(["--root", str(REPO_ROOT)]), 0)


if __name__ == "__main__":
    unittest.main()
