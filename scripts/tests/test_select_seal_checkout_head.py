"""Coverage tests for scripts/select_seal_checkout_head.py."""

from __future__ import annotations

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

import select_seal_checkout_head as selector  # noqa: E402


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _git_output(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


BASE_ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_EVENT_NAME": "push",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_REPOSITORY": "sarmidev/KardanoSDK",
    "GITHUB_SERVER_URL": "https://github.com",
    "GITHUB_API_URL": "https://api.github.com",
}


class MainPushMergeSelectionTests(unittest.TestCase):
    """Build a disposable temp git repo shaped like a real GitHub `push`
    to `main` (a two-parent merge of a validated PR head into the
    previous main tip) and exercise every positive/adversarial case."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "test@example.invalid")
        _git(self.repo, "config", "user.name", "Test")
        self._patches = [mock.patch.object(selector, "REPO_ROOT", self.repo)]
        for patch in self._patches:
            patch.start()

    def tearDown(self) -> None:
        for patch in reversed(self._patches):
            patch.stop()
        self._tmp.cleanup()

    def _commit(self, name: str, content: str = "x\n") -> str:
        (self.repo / name).write_text(content, encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", f"add {name}")
        return _git_output(self.repo, "rev-parse", "HEAD")

    def _build_main_merge(self) -> tuple[str, str, str]:
        """Returns (previous_main_tip, pr_head, merge_commit)."""
        root = self._commit("ROOT.txt")
        _git(self.repo, "branch", "-M", "main")
        previous_main_tip = root
        _git(self.repo, "checkout", "-q", "-b", "feature")
        pr_head = self._commit("FEATURE.txt")
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "--no-ff", "-q", "-m", "Merge pull request", "feature")
        merge_commit = _git_output(self.repo, "rev-parse", "HEAD")
        return previous_main_tip, pr_head, merge_commit

    def _write_event(self, event: dict, *, name: str = "event.json") -> Path:
        path = self.repo / name
        path.write_text(json.dumps(event), encoding="utf-8")
        return path

    def _push_event(
        self,
        *,
        before: str,
        after: str,
        ref: str = "refs/heads/main",
        repo_full_name: str = "sarmidev/KardanoSDK",
        forced: bool = False,
        deleted: bool = False,
        created: bool = False,
    ) -> dict:
        return {
            "ref": ref,
            "before": before,
            "after": after,
            "repository": {"full_name": repo_full_name},
            "forced": forced,
            "deleted": deleted,
            "created": created,
        }

    def _env(self, *, event_path: Path, sha: str, **overrides: str) -> dict[str, str]:
        env = dict(BASE_ENV)
        env["GITHUB_EVENT_PATH"] = str(event_path)
        env["GITHUB_SHA"] = sha
        env.update(overrides)
        return env

    # -- positive path -----------------------------------------------------

    def test_valid_github_shaped_main_push_merge_selects_pr_head(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        self.assertEqual(selector.select_checkout_head(env), pr_head)

    def test_main_checkout_selects_and_detaches_to_pr_head_via_main(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with mock.patch.dict(os.environ, env, clear=True):
            exit_code = selector.main([])
        self.assertEqual(exit_code, 0)
        self.assertEqual(_git_output(self.repo, "rev-parse", "HEAD"), pr_head)

    def test_ordinary_fast_forward_push_to_main_returns_head_unchanged(self) -> None:
        # A non-merge push directly to main (HEAD has exactly one parent):
        # no merge validation applies at all; the strict checker handles
        # the ordinary case.
        self._commit("ROOT.txt")
        head = self._commit("SECOND.txt")
        env = dict(BASE_ENV)
        env["GITHUB_SHA"] = head
        # No GITHUB_EVENT_PATH needed: single-parent HEAD never reaches
        # the event-reading code path.
        self.assertEqual(selector.select_checkout_head(env), head)

    def test_root_commit_on_main_returns_head_unchanged(self) -> None:
        head = self._commit("ROOT.txt")
        env = dict(BASE_ENV)
        env["GITHUB_SHA"] = head
        self.assertEqual(selector.select_checkout_head(env), head)

    def test_ordinary_fix_branch_push_returns_head_unchanged(self) -> None:
        # Not a push to main at all -- e.g. a `fix/**` branch that itself
        # contains a "Merge branch 'main' into fix/**" two-parent commit.
        # Regardless of parent count, this selector must leave HEAD alone.
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        env = dict(BASE_ENV)
        env["GITHUB_REF"] = "refs/heads/fix/something"
        env["GITHUB_SHA"] = merge_commit
        self.assertEqual(selector.select_checkout_head(env), merge_commit)

    def test_pull_request_event_name_returns_head_unchanged(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        env = dict(BASE_ENV)
        env["GITHUB_EVENT_NAME"] = "pull_request"
        env["GITHUB_SHA"] = merge_commit
        self.assertEqual(selector.select_checkout_head(env), merge_commit)

    # -- adversarial / missing env / missing event --------------------------

    def test_missing_github_actions_env_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        env.pop("GITHUB_ACTIONS")
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_missing_event_path_env_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        env = self._env(event_path=Path("unused"), sha=merge_commit)
        env.pop("GITHUB_EVENT_PATH")
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_missing_event_file_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        env = self._env(
            event_path=self.repo / "does-not-exist.json", sha=merge_commit
        )
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_symlinked_event_path_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        real_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit),
            name="real-event.json",
        )
        link_path = self.repo / "event-symlink.json"
        link_path.symlink_to(real_path)
        env = self._env(event_path=link_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_oversized_event_file_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        big_path = self.repo / "big-event.json"
        big_path.write_bytes(b"{" + b" " * (selector.MAX_EVENT_BYTES + 1) + b"}")
        env = self._env(event_path=big_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_duplicate_json_key_in_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        dup_path = self.repo / "dup-event.json"
        dup_path.write_text(
            '{"ref": "refs/heads/main", "ref": "refs/heads/main"}\n',
            encoding="utf-8",
        )
        env = self._env(event_path=dup_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_malformed_json_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        bad_path = self.repo / "bad-event.json"
        bad_path.write_text("{not valid json", encoding="utf-8")
        env = self._env(event_path=bad_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_non_object_json_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        list_path = self.repo / "list-event.json"
        list_path.write_text("[1, 2, 3]\n", encoding="utf-8")
        env = self._env(event_path=list_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_wrong_repository_in_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(
                before=previous_main_tip,
                after=merge_commit,
                repo_full_name="someone-else/OtherRepo",
            )
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_wrong_event_ref_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(
                before=previous_main_tip, after=merge_commit, ref="refs/heads/develop"
            )
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_wrong_before_in_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before="a" * 40, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_malformed_before_in_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before="not-a-sha", after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_wrong_after_in_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after="b" * 40)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_github_sha_not_matching_head_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha="c" * 40)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_forced_push_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit, forced=True)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_deleted_push_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit, deleted=True)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_created_push_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit, created=True)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_octopus_merge_on_main_push_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        _git(self.repo, "checkout", "-q", "-b", "third", previous_main_tip)
        third = self._commit("THIRD.txt")
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "--no-ff", "-q", "-m", "Octopus merge", "feature", third)
        octopus = _git_output(self.repo, "rev-parse", "HEAD")
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=octopus)
        )
        env = self._env(event_path=event_path, sha=octopus)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_swapped_parent_order_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        # Event claims `before` is the PR head and `after` is the merge --
        # but the ACTUAL first parent of the merge is previous_main_tip,
        # not pr_head, so this must be rejected.
        event_path = self._write_event(
            self._push_event(before=pr_head, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_unrelated_before_in_event_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        _git(self.repo, "checkout", "-q", "--orphan", "unrelated")
        (self.repo / "UNRELATED.txt").write_text("x\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "unrelated root")
        unrelated = _git_output(self.repo, "rev-parse", "HEAD")
        _git(self.repo, "checkout", "-q", "main")
        event_path = self._write_event(
            self._push_event(before=unrelated, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_genuine_conflict_resolution_tree_mismatch_is_rejected(self) -> None:
        # A real merge that resolves a conflict (or otherwise edits
        # something during the merge) has a tree that differs from its
        # own second parent's tree -- must fail closed, not silently pass.
        previous_main_tip = self._commit("ROOT.txt")
        _git(self.repo, "branch", "-M", "main")
        _git(self.repo, "checkout", "-q", "-b", "feature")
        pr_head = self._commit("FEATURE.txt")
        _git(self.repo, "checkout", "-q", "main")
        (self.repo / "EXTRA_MAIN_ONLY.txt").write_text("extra\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "extra main-only change")
        new_main_tip = _git_output(self.repo, "rev-parse", "HEAD")
        _git(self.repo, "merge", "--no-ff", "-q", "-m", "Merge pull request", "feature")
        merge_commit = _git_output(self.repo, "rev-parse", "HEAD")
        event_path = self._write_event(
            self._push_event(before=new_main_tip, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_forged_same_tree_candidate_with_wrong_event_parent_is_rejected(self) -> None:
        # Build a commit with the SAME tree as a genuine merge, but claim
        # (via the event) a `before` that does not match its actual first
        # parent -- tree-shape equality alone must never be sufficient.
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        tree = _git_output(self.repo, "rev-parse", f"{merge_commit}^{{tree}}")
        forged = _git_output(
            self.repo,
            "commit-tree",
            tree,
            "-p",
            pr_head,
            "-p",
            previous_main_tip,
            "-m",
            "forged same-tree candidate with swapped parents",
        )
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=forged)
        )
        env = self._env(event_path=event_path, sha=forged)
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_wrong_server_url_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit)
        )
        env = self._env(
            event_path=event_path,
            sha=merge_commit,
            GITHUB_SERVER_URL="https://evil.example.invalid",
        )
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_wrong_api_url_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit)
        )
        env = self._env(
            event_path=event_path,
            sha=merge_commit,
            GITHUB_API_URL="https://evil.example.invalid",
        )
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_missing_repository_env_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        env.pop("GITHUB_REPOSITORY")
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_missing_github_sha_env_is_rejected(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        env.pop("GITHUB_SHA")
        with self.assertRaises(selector.SelectionError):
            selector.select_checkout_head(env)

    def test_checkout_failure_after_validation_returns_nonzero(self) -> None:
        previous_main_tip, pr_head, merge_commit = self._build_main_merge()
        event_path = self._write_event(
            self._push_event(before=previous_main_tip, after=merge_commit)
        )
        env = self._env(event_path=event_path, sha=merge_commit)
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            selector, "run_git_ok", return_value=False
        ):
            exit_code = selector.main([])
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
