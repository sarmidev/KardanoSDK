"""Workflow expression/config test: the `legal-evidence-scan` job in
`.github/workflows/verify.yml` must check out the exact `pull_request`
head SHA (never the default `refs/pull/*/merge` ref) and must run
`scripts/select_seal_checkout_head.py` before any evidence/seal check --
see ADR-level discussion in `docs/RELEASING.md`/`docs/LEGAL_REVIEW.md`.

Parses the real workflow YAML with Ruby's stdlib Psych (already a build
dependency of `scripts/check_action_pins.py`; no PyYAML dependency is
added), so this test fails if the workflow file is ever edited back to
the default merge-ref checkout or loses the selector step, rather than
relying on a human to notice.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

VERIFY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "verify.yml"

EXPECTED_PR_HEAD_REF_EXPRESSION = (
    "${{ github.event_name == 'pull_request' "
    "&& github.event.pull_request.head.sha || github.sha }}"
)


def _load_workflow_as_json() -> dict:
    """Parse the real workflow file with Ruby stdlib Psych, converted to
    plain JSON -- a full structural parse, not a line-oriented regex
    hunt, so this test actually inspects `with:`/`steps:` nesting."""
    script = (
        "require 'psych'; require 'json'; "
        "doc = Psych.safe_load(File.read(ARGV[0])); "
        "puts JSON.generate(doc)"
    )
    result = subprocess.run(
        ["ruby", "-e", script, str(VERIFY_WORKFLOW)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


class LegalEvidenceScanCheckoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _load_workflow_as_json()
        self.job = self.workflow["jobs"]["legal-evidence-scan"]
        self.steps = self.job["steps"]

    def test_first_step_is_a_checkout_pinned_to_exact_pr_head_sha(self) -> None:
        first_step = self.steps[0]
        self.assertTrue(str(first_step.get("uses", "")).startswith("actions/checkout@"))
        with_block = first_step.get("with") or {}
        self.assertEqual(with_block.get("ref"), EXPECTED_PR_HEAD_REF_EXPRESSION)
        self.assertEqual(with_block.get("fetch-depth"), 0)

    def test_checkout_does_not_use_default_merge_ref(self) -> None:
        first_step = self.steps[0]
        with_block = first_step.get("with") or {}
        ref_expression = str(with_block.get("ref", ""))
        self.assertNotIn("refs/pull", ref_expression)
        self.assertNotIn("merge", ref_expression)

    def test_second_step_runs_the_seal_checkout_selector_before_any_other_step(self) -> None:
        second_step = self.steps[1]
        self.assertEqual(
            second_step.get("run", "").strip(),
            "python3 scripts/select_seal_checkout_head.py",
        )
        step_names = [step.get("name", "") for step in self.steps]
        selector_index = next(
            i for i, step in enumerate(self.steps)
            if "select_seal_checkout_head.py" in str(step.get("run", ""))
        )
        checker_index = next(
            i for i, step in enumerate(self.steps)
            if "check_release_evidence.py" in str(step.get("run", ""))
        )
        self.assertLess(
            selector_index,
            checker_index,
            f"select_seal_checkout_head.py must run before check_release_evidence.py "
            f"(steps: {step_names})",
        )

    def test_regression_test_module_is_wired_into_ci(self) -> None:
        regression_step = next(
            step for step in self.steps
            if "Run legal-evidence regression tests" == step.get("name")
        )
        self.assertIn(
            "scripts.tests.test_select_seal_checkout_head",
            regression_step.get("run", ""),
        )

    def test_other_jobs_may_keep_the_default_merge_ref_checkout(self) -> None:
        # Only legal-evidence-scan is required to pin an exact ref; other
        # jobs' plain `actions/checkout` steps (no `with.ref` override at
        # all) keep GitHub's default merge-ref behavior for `pull_request`,
        # which is fine for ordinary test/build jobs.
        for job_name, job in self.workflow["jobs"].items():
            if job_name == "legal-evidence-scan":
                continue
            first_step = job["steps"][0]
            if str(first_step.get("uses", "")).startswith("actions/checkout@"):
                with_block = first_step.get("with") or {}
                self.assertNotIn(
                    "ref",
                    with_block,
                    f"job {job_name!r} unexpectedly pins an explicit checkout ref",
                )


if __name__ == "__main__":
    unittest.main()
