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

    def test_trigger_is_workflow_dispatch_only(self) -> None:
        document = pins.parse_yaml_document(self.text, source_path=attest.WORKFLOW_PATH)
        keys = [str(key) for key in document["top_level_keys"]]
        self.assertIn("on", keys)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("pull_request:", self.text)
        self.assertNotRegex(self.text, r"(?m)^  push:")
        self.assertNotRegex(self.text, r"(?m)^on:\n  push:")
        # Psych maps the YAML key `on` to boolean true; JSON.generate then
        # stringifies that key as "true".
        on_block = (
            self.workflow.get("on")
            or self.workflow.get(True)
            or self.workflow.get("true")
        )
        self.assertIsInstance(on_block, dict)
        self.assertEqual(set(on_block.keys()), {"workflow_dispatch"})

    def test_permissions_are_exact_minimal_read_set(self) -> None:
        expected = {"contents": "read", "security-events": "read"}
        self.assertEqual(self.workflow["permissions"], expected)
        self.assertEqual(self.job["permissions"], expected)
        self.assertIsInstance(self.workflow["permissions"], dict)
        self.assertIsInstance(self.job["permissions"], dict)
        self.assertNotIn("read-all", self.text)
        self.assertNotIn("write-all", self.text)
        self.assertIn("security-events: read", self.text)
        self.assertIn("contents: read", self.text)

    def test_job_does_not_request_write_or_broad_scopes(self) -> None:
        forbidden_write = (
            "actions",
            "attestations",
            "checks",
            "contents",
            "deployments",
            "discussions",
            "id-token",
            "issues",
            "packages",
            "pages",
            "pull-requests",
            "security-events",
            "statuses",
        )
        for key in forbidden_write:
            self.assertNotEqual(self.workflow["permissions"].get(key), "write")
            self.assertNotEqual(self.job["permissions"].get(key), "write")
        self.assertNotIn("vulnerability-alerts", self.workflow["permissions"])
        self.assertNotIn("vulnerability-alerts", self.job["permissions"])
        extra_keys = set(self.workflow["permissions"]) - {
            "contents",
            "security-events",
        }
        self.assertEqual(extra_keys, set())
        job_extra = set(self.job["permissions"]) - {"contents", "security-events"}
        self.assertEqual(job_extra, set())
        self.assertNotIn("${{ secrets.", self.text)
        self.assertNotRegex(self.text, r"(?m)^  secrets:")

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

    def test_runner_is_pinned_ubuntu_24_04(self) -> None:
        self.assertEqual(self.job["runs-on"], "ubuntu-24.04")
        self.assertNotIn("ubuntu-latest", self.text)

    def test_official_script_runs_under_xvfb(self) -> None:
        self.assertIn("xvfb-run -a", self.text)
        self.assertIn("wkhtmltopdf", self.text)
        self.assertIn("apt-get install -y --no-install-recommends xvfb wkhtmltopdf", self.text)

    def test_days_input_is_env_passed_and_range_checked(self) -> None:
        self.assertIn("ATTESTATION_DAYS: ${{ github.event.inputs.days || '90' }}", self.text)
        self.assertNotIn("--days \"${{ github.event.inputs.days }}\"", self.text)
        self.assertNotIn("--days ${{ github.event.inputs.days }}", self.text)
        self.assertIn("--days \"${ATTESTATION_DAYS}\"", self.text)
        self.assertIn("[!0-9]*", self.text)
        self.assertIn("-lt 1", self.text)
        self.assertIn("-gt 365", self.text)
