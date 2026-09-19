"""Structural checks for the pinned Intersect attestation workflow."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import action_pin_inventory as inventory  # noqa: E402
import check_action_pins as pins  # noqa: E402
import intersect_attestation_pin as attest  # noqa: E402

WORKFLOW = REPO_ROOT / attest.WORKFLOW_PATH
SECRETISH = (
    "ghp_",
    "github_pat_",
    "AKIA",
    "BEGIN PRIVATE KEY",
    "echo $GH_TOKEN",
    "echo ${GH_TOKEN",
    "echo \"$GH_TOKEN\"",
    "echo $GITHUB_TOKEN",
    "printenv GH_TOKEN",
    "printenv GITHUB_TOKEN",
)


def _load_workflow() -> dict:
    script = (
        "require 'psych'; require 'json'; "
        "doc = Psych.safe_load(File.read(ARGV[0])); "
        "puts JSON.generate(doc)"
    )
    result = subprocess.run(
        ["ruby", "-e", script, str(WORKFLOW)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


class IntersectAttestationPinTests(unittest.TestCase):
    def test_pin_is_lowercase_sha(self) -> None:
        self.assertTrue(inventory.is_lowercase_sha(attest.OFFICIAL_COMMIT_SHA))

    def test_workflow_file_exists(self) -> None:
        self.assertTrue(WORKFLOW.is_file())

    def test_workflow_records_the_inspected_upstream_commit(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(attest.OFFICIAL_COMMIT_SHA, text)
        self.assertIn(attest.OFFICIAL_OWNER_REPO, text)
        self.assertIn(attest.TARGET_OWNER_REPO, text)
        self.assertIn(attest.OFFICIAL_SCRIPT_PATH, text)


class IntersectAttestationWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _load_workflow()
        self.job = self.workflow["jobs"]["attest"]
        self.steps = self.job["steps"]
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_yaml_has_on_and_jobs(self) -> None:
        findings = pins.check_workflow_structure(REPO_ROOT, attest.WORKFLOW_PATH)
        self.assertEqual(findings, [])

    def test_trigger_is_manual_dispatch_only(self) -> None:
        document = pins.parse_yaml_document(self.text, source_path=attest.WORKFLOW_PATH)
        keys = [str(key) for key in document["top_level_keys"]]
        self.assertIn("on", keys)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotRegex(self.text, r"(?m)^  push:")
        self.assertNotRegex(self.text, r"(?m)^  pull_request:")
        self.assertNotRegex(self.text, r"(?m)^on:\n  push:")

    def test_permissions_are_contents_read_only(self) -> None:
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(self.job["permissions"], {"contents": "read"})

    def test_job_does_not_request_write_scopes(self) -> None:
        forbidden = {
            "contents": "write",
            "pull-requests": "write",
            "packages": "write",
            "security-events": "write",
        }
        for key, value in forbidden.items():
            self.assertNotEqual(self.workflow["permissions"].get(key), value)
            self.assertNotEqual(self.job["permissions"].get(key), value)

    def test_upload_artifact_uses_inventory_pin(self) -> None:
        upload = inventory.PIN_BY_ACTION["actions/upload-artifact"]
        upload_steps = [
            step
            for step in self.steps
            if str(step.get("uses", "")).startswith("actions/upload-artifact@")
        ]
        self.assertEqual(len(upload_steps), 1)
        self.assertEqual(
            upload_steps[0]["uses"],
            f"actions/upload-artifact@{upload.sha}",
        )

    def test_required_outputs_are_asserted(self) -> None:
        self.assertIn("kardano-sdk-self-attest.html", self.text)
        self.assertIn("kardano-sdk-self-attest.pdf", self.text)
        self.assertIn("kardano-sdk-self-attest.md", self.text)
        self.assertIn("attestation-environment.txt", self.text)
        self.assertIn("test -f kardano-sdk-self-attest.html", self.text)
        self.assertIn("test -f kardano-sdk-self-attest.pdf", self.text)

    def test_default_branch_limitation_is_documented(self) -> None:
        self.assertIn("default branch", self.text.lower())

    def test_workflow_does_not_embed_or_echo_secrets(self) -> None:
        for needle in SECRETISH:
            self.assertNotIn(needle, self.text)

    def test_token_presence_check_does_not_print_the_token(self) -> None:
        self.assertIn("token.encode()", self.text)
        self.assertNotIn("print(token)", self.text)
        self.assertNotIn("print(os.environ.get('GH_TOKEN')", self.text)
