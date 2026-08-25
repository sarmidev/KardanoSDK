#!/usr/bin/env python3
"""Fail-closed selector: which commit should the legal-evidence checks run
against, for a `push` to `refs/heads/main` whose HEAD is a merge commit.

This script is the ONLY place a merge commit is ever validated against a
GitHub event payload for the legal-evidence packet. `scripts/
check_release_evidence.py` itself contains no such exception: its
`check_scope_binding_seal()` always requires literal HEAD's own immediate
parent to be `evidence_commit` (see that module's docstring). This script
runs BEFORE the checker, and -- only in the one narrow case described
below -- performs a `git checkout --detach` so the checker then sees a
literal, already-selected HEAD to check strictly.

Design (see docs/RELEASING.md and docs/LEGAL_REVIEW.md for the reviewer-
facing summary):

- Any HEAD with a number of parents other than exactly two is left
  unchanged: an ordinary branch push (0 or 1 parents) or a merge commit
  that is not a `push`-to-`main` event (e.g. `Merge branch 'main' into
  fix/**` on a feature branch) is not this script's concern -- the
  strict checker applies to literal HEAD either way, and will correctly
  fail a merge commit that is not a validated main-push seal candidate.
- A HEAD with exactly two parents, on a `push` to `refs/heads/main`, is
  validated against the *trusted GitHub push event* named by
  `GITHUB_EVENT_PATH` (see `_read_trusted_push_event()` for the exact
  file-handling hardening, and `_validate_main_push_merge()` for the
  exact field-by-field cross-checks). Every one of the following must
  hold, or this script exits non-zero and performs NO checkout at all:

  - `GITHUB_ACTIONS == "true"`, and (defense-in-depth only) `GITHUB_
    SERVER_URL`/`GITHUB_API_URL` match the expected github.com hosts.
    This is NOT a claim that a local/forged environment cannot set these
    same variables -- it cannot distinguish a genuine GitHub-hosted
    runner from a process that fakes the same env vars and event file.
    The actual trust boundary is that this script only ever runs as a
    step inside a GitHub-hosted Actions job (see `.github/workflows/
    verify.yml`'s `legal-evidence-scan` job); nothing in this script
    "cryptographically" proves the event is genuine.
  - `GITHUB_EVENT_NAME == "push"`, `GITHUB_REF == "refs/heads/main"`,
    `GITHUB_REPOSITORY` and `GITHUB_SHA` are both set and non-empty.
  - `GITHUB_EVENT_PATH` names a regular, non-symlink file no larger than
    `MAX_EVENT_BYTES`, containing valid UTF-8 JSON with no duplicate
    object key, whose top level is an object.
  - `event["repository"]["full_name"] == GITHUB_REPOSITORY`.
  - `event["ref"] == GITHUB_REF == "refs/heads/main"`.
  - `event["forced"] is False`, `event["deleted"] is False`, and
    `event["created"] is False` -- a force-push, branch deletion, or
    branch-creation push event is never a plain fast-forward merge of an
    already-validated PR and is rejected outright ("non-fast event
    state").
  - `event["before"]` and `event["after"]` are each present and exactly
    40 lowercase hex characters.
  - `event["after"] == GITHUB_SHA == git rev-parse HEAD` -- the event
    describes exactly this checkout, not some other one.
  - HEAD has EXACTLY two parents (already required to reach this branch)
    and, in exact order, `parents[0] == event["before"]` -- the merge's
    first parent is the previous main tip the event itself names; a
    swapped, wrong-order, or unrelated first parent is rejected.
  - HEAD's own tree is byte-identical to `parents[1]`'s tree -- the
    merge introduced no conflict-resolution edit or other change beyond
    what the incoming (PR head) commit already had. A tree mismatch
    (including a forged same-tree-as-something-else candidate whose
    actual parent[1] tree differs) is rejected.

  On success, `parents[1]` -- the sealed PR-head candidate -- is printed
  and checked out via `git checkout --detach`; the caller then runs the
  strict legal-evidence checks against THAT commit. If a genuine main
  merge's tree does not match its own second parent's tree (a real
  conflict-resolution edit), this script -- and therefore the main-push
  legal job -- intentionally fails and requires a fresh seal, exactly as
  documented above.

Any missing/malformed field, wrong type, wrong value, an octopus merge
(more than two parents) on a `push` to `main`, or any of the above
mismatches is a hard failure (nonzero exit, no checkout performed) --
never a silent pass and never a silent fall-back to "keep HEAD" once this
script has determined it is looking at a `push`-to-`main` merge commit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MAX_EVENT_BYTES = 1 * 1024 * 1024  # 1 MiB
GIT_SHA1_RE = __import__("re").compile(r"^[0-9a-f]{40}$")
EXPECTED_SERVER_URL = "https://github.com"
EXPECTED_API_URL = "https://api.github.com"
MAIN_REF = "refs/heads/main"


class SelectionError(Exception):
    """Raised for any reason the main-push merge selection must fail
    closed. The caller treats this as a hard failure, never a fallback."""


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout


def run_git_ok(*args: str) -> bool:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return result.returncode == 0


def _commit_parents(oid: str) -> list[str]:
    output = run_git("rev-parse", f"{oid}^@").strip()
    return output.splitlines() if output else []


def _commit_tree(oid: str) -> str:
    return run_git("rev-parse", f"{oid}^{{tree}}").strip()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    seen: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate JSON object key {key!r}")
        seen[key] = value
    return seen


def _read_trusted_push_event(event_path_str: str) -> dict:
    """Strictly parse the file named by `GITHUB_EVENT_PATH`.

    Trusted-runner boundary: this function hardens the FILE HANDLING
    (no symlink, no non-regular file, size-capped, well-formed JSON, no
    duplicate keys, object top level) -- it does not and cannot prove the
    file's CONTENT is a genuine GitHub event; that trust comes only from
    this script running inside a GitHub-hosted Actions job, never from
    anything checkable in-process. See the module docstring.
    """
    if not event_path_str:
        raise SelectionError("GITHUB_EVENT_PATH is not set")
    path = Path(event_path_str)
    try:
        lstat = path.lstat()
    except OSError as exc:
        raise SelectionError(f"GITHUB_EVENT_PATH is not accessible: {exc}") from exc
    if path.is_symlink():
        raise SelectionError("GITHUB_EVENT_PATH must not be a symlink")
    import stat as stat_module

    if not stat_module.S_ISREG(lstat.st_mode):
        raise SelectionError("GITHUB_EVENT_PATH must be a regular file")
    if lstat.st_size > MAX_EVENT_BYTES:
        raise SelectionError(
            f"GITHUB_EVENT_PATH is {lstat.st_size} bytes, exceeding the "
            f"{MAX_EVENT_BYTES}-byte cap"
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SelectionError(f"could not read GITHUB_EVENT_PATH: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SelectionError(f"GITHUB_EVENT_PATH is not valid UTF-8: {exc}") from exc
    try:
        event = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as exc:
        raise SelectionError(f"GITHUB_EVENT_PATH is not valid JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise SelectionError("GITHUB_EVENT_PATH's top level is not a JSON object")
    return event


def _require_env(env: dict[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise SelectionError(f"{name} is not set")
    return value


def _validate_main_push_merge(
    head: str, parents: list[str], env: dict[str, str]
) -> str:
    """Return the validated sealed-PR-head candidate (`parents[1]`), or
    raise `SelectionError`. `parents` must already have exactly two
    entries (checked by the caller)."""
    if env.get("GITHUB_ACTIONS") != "true":
        raise SelectionError(
            "GITHUB_ACTIONS != 'true' -- this selector only runs inside a "
            "GitHub Actions job (defense-in-depth; see module docstring: "
            "this check cannot itself prove genuineness)"
        )
    server_url = env.get("GITHUB_SERVER_URL")
    api_url = env.get("GITHUB_API_URL")
    if server_url is not None and server_url != EXPECTED_SERVER_URL:
        raise SelectionError(
            f"GITHUB_SERVER_URL {server_url!r} != expected {EXPECTED_SERVER_URL!r}"
        )
    if api_url is not None and api_url != EXPECTED_API_URL:
        raise SelectionError(
            f"GITHUB_API_URL {api_url!r} != expected {EXPECTED_API_URL!r}"
        )

    repository = _require_env(env, "GITHUB_REPOSITORY")
    github_sha = _require_env(env, "GITHUB_SHA")
    if github_sha != head:
        raise SelectionError(
            f"GITHUB_SHA {github_sha!r} != current HEAD {head!r}"
        )

    event = _read_trusted_push_event(env.get("GITHUB_EVENT_PATH", ""))

    top_repo = event.get("repository")
    if not isinstance(top_repo, dict) or top_repo.get("full_name") != repository:
        raise SelectionError(
            "event.repository.full_name does not match GITHUB_REPOSITORY"
        )

    event_ref = event.get("ref")
    if event_ref != MAIN_REF or event_ref != env.get("GITHUB_REF"):
        raise SelectionError(
            f"event.ref {event_ref!r} is not exactly {MAIN_REF!r} matching GITHUB_REF"
        )

    for flag_name in ("forced", "deleted", "created"):
        flag_value = event.get(flag_name)
        if flag_value is not False:
            raise SelectionError(
                f"event.{flag_name} is {flag_value!r}, not exactly False -- "
                "non-fast-forward/deleted/created push event state is rejected"
            )

    before = event.get("before")
    after = event.get("after")
    if not isinstance(before, str) or not GIT_SHA1_RE.match(before):
        raise SelectionError(f"event.before is not a 40-hex-char git object id: {before!r}")
    if not isinstance(after, str) or not GIT_SHA1_RE.match(after):
        raise SelectionError(f"event.after is not a 40-hex-char git object id: {after!r}")
    if after != github_sha:
        raise SelectionError(
            f"event.after {after!r} != GITHUB_SHA {github_sha!r}"
        )

    if len(parents) != 2:
        raise SelectionError(
            f"HEAD {head} has {len(parents)} parent(s), not exactly two "
            "(octopus merge or non-merge commit is never eligible)"
        )
    if parents[0] != before:
        raise SelectionError(
            f"HEAD's first parent {parents[0]!r} != event.before {before!r} "
            "(wrong parent order, wrong parents, or a merge not built on "
            "top of the branch tip the event names)"
        )

    head_tree = _commit_tree(head)
    parent2_tree = _commit_tree(parents[1])
    if head_tree != parent2_tree:
        raise SelectionError(
            f"HEAD's tree {head_tree} != its second parent {parents[1]}'s "
            f"tree {parent2_tree} -- this merge changed something beyond "
            "what the incoming commit already had (a real conflict-"
            "resolution edit); this fails closed and requires a fresh seal, "
            "by design"
        )

    return parents[1]


def select_checkout_head(env: dict[str, str]) -> str:
    """The commit the legal-evidence checks must run against.

    Returns literal HEAD unchanged unless this is a `push` to
    `refs/heads/main` whose HEAD has exactly two parents, in which case
    it returns the validated sealed-PR-head parent (raising
    `SelectionError` if validation fails for any reason -- there is no
    silent fallback to HEAD once a `push`-to-`main` merge commit has been
    identified).
    """
    head = run_git("rev-parse", "HEAD").strip()
    parents = _commit_parents(head)
    if env.get("GITHUB_EVENT_NAME") != "push" or env.get("GITHUB_REF") != MAIN_REF:
        return head
    if len(parents) <= 1:
        return head  # ordinary fast-forward/non-merge push directly to main
    return _validate_main_push_merge(head, parents, env)


def main(argv: list[str] | None = None) -> int:
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    head_before = run_git("rev-parse", "HEAD").strip()
    try:
        target = select_checkout_head(dict(os.environ))
    except SelectionError as exc:
        print(f"[FAIL] select_seal_checkout_head: {exc}", file=sys.stderr)
        return 1

    if target == head_before:
        print(
            f"[ok] select_seal_checkout_head: no main-push merge validation "
            f"needed; keeping {head_before} checked out for legal-evidence checks"
        )
        return 0

    if not run_git_ok("checkout", "--detach", target):
        print(
            f"[FAIL] select_seal_checkout_head: validated sealed PR-head "
            f"{target}, but `git checkout --detach {target}` failed",
            file=sys.stderr,
        )
        return 1
    print(
        f"[ok] select_seal_checkout_head: validated main-push merge commit "
        f"{head_before} (a genuine, byte-identical-tree merge of PR head "
        f"{target} into the previous main tip); checked out {target} "
        "detached for the strict legal-evidence checks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
