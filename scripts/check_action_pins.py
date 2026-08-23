#!/usr/bin/env python3
"""Require SHA-pinned GitHub Actions and reviewed composite transitives.

Every external `uses:` in `.github/workflows/*` and local composite
`action.yml` files must contain exactly one 40-character lowercase SHA.
Pinned composite metadata lives in scripts/action_pin_inventory.py and
must be copied into docs/DEPENDENCY_REVIEW.md. A recorded floating
transitive `uses:` is a finding.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import action_pin_inventory as inventory  # noqa: E402

WORKFLOW_GLOB = ".github/workflows/*.{yml,yaml}"
LOCAL_ACTION_GLOB = ".github/actions/**/action.yml"

USES_RE = re.compile(
    r"^(?P<indent>\s*)(?:-\s*)?uses:\s*(?P<quote>['\"]?)(?P<ref>.+?)(?P=quote)\s*(?:#.*)?$"
)
SHA_REF_RE = re.compile(
    r"^(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@(?P<sha>[0-9a-f]{40})$"
)
LOCAL_REF_RE = re.compile(r"^\./")
DOCKER_REF_RE = re.compile(r"^docker://")


@dataclass(frozen=True)
class UseRef:
    path: str
    line: int
    raw: str
    action: str | None
    sha: str | None
    kind: str


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def parse_use_line(path: str, line_no: int, line: str) -> UseRef | None:
    match = USES_RE.match(line.rstrip("\n"))
    if match is None:
        return None
    raw = match.group("ref").strip()
    if LOCAL_REF_RE.match(raw):
        return UseRef(path, line_no, raw, None, None, "local")
    if DOCKER_REF_RE.match(raw):
        return UseRef(path, line_no, raw, None, None, "docker")
    sha_match = SHA_REF_RE.match(raw)
    if sha_match is None:
        return UseRef(path, line_no, raw, None, None, "unpinned")
    return UseRef(
        path,
        line_no,
        raw,
        sha_match.group("action"),
        sha_match.group("sha"),
        "pinned",
    )


def list_workflow_paths(root: Path) -> list[Path]:
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return []
    return sorted(
        path
        for path in workflows.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    )


def list_local_action_paths(root: Path) -> list[Path]:
    actions = root / ".github" / "actions"
    if not actions.is_dir():
        return []
    return sorted(actions.glob("**/action.yml"))


def read_use_refs(root: Path, relative: str) -> list[UseRef]:
    text = (root / relative).read_text(encoding="utf-8")
    refs: list[UseRef] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        parsed = parse_use_line(relative, line_no, line)
        if parsed is not None:
            refs.append(parsed)
    return refs


def check_workflow_syntax(root: Path, relative: str) -> list[Finding]:
    """Stdlib-only workflow structure checks. Not a full YAML parser."""
    findings: list[Finding] = []
    path = root / relative
    text = path.read_text(encoding="utf-8")
    if "\t" in text:
        findings.append(Finding(relative, 1, "workflow uses tab indentation"))
    if not re.search(r"(?m)^on:\s", text) and not re.search(r"(?m)^on:\s*$", text):
        findings.append(Finding(relative, 1, "workflow is missing a top-level on: key"))
    if not re.search(r"(?m)^jobs:\s*$", text):
        findings.append(Finding(relative, 1, "workflow is missing a top-level jobs: key"))
    return findings


def check_use_ref(ref: UseRef) -> list[Finding]:
    if ref.kind == "local":
        return []
    if ref.kind == "docker":
        return [
            Finding(
                ref.path,
                ref.line,
                f"docker uses: is not in the reviewed Action inventory ({ref.raw})",
            )
        ]
    if ref.kind != "pinned" or ref.action is None or ref.sha is None:
        return [
            Finding(
                ref.path,
                ref.line,
                "external uses: must be owner/name@<40-char lowercase SHA> "
                f"(found {ref.raw!r})",
            )
        ]
    if not inventory.is_lowercase_sha(ref.sha):
        return [
            Finding(
                ref.path,
                ref.line,
                f"Action SHA must be 40 lowercase hex characters (found {ref.sha})",
            )
        ]
    recorded = inventory.PIN_BY_ACTION.get(ref.action)
    if recorded is None:
        return [
            Finding(
                ref.path,
                ref.line,
                f"{ref.action} is not recorded in scripts/action_pin_inventory.py",
            )
        ]
    if recorded.sha != ref.sha:
        return [
            Finding(
                ref.path,
                ref.line,
                f"{ref.action} SHA {ref.sha} does not match inventory "
                f"{recorded.sha} ({recorded.release})",
            )
        ]
    return []


def check_inventory_transitives() -> list[Finding]:
    findings: list[Finding] = []
    for pin in inventory.ACTION_PINS:
        if pin.kind == "composite" and not pin.transitive:
            findings.append(
                Finding(
                    "scripts/action_pin_inventory.py",
                    1,
                    f"{pin.action} is composite but records no transitive uses:",
                )
            )
        for child in pin.transitive:
            if not inventory.is_lowercase_sha(child.sha):
                findings.append(
                    Finding(
                        "scripts/action_pin_inventory.py",
                        1,
                        f"{pin.action} records floating/invalid transitive "
                        f"{child.action}@{child.sha}",
                    )
                )
    return findings


def check_review_doc(root: Path) -> list[Finding]:
    review = root / inventory.REVIEW_DOC
    if not review.is_file():
        return [Finding(inventory.REVIEW_DOC, 1, "dependency review file is missing")]
    text = review.read_text(encoding="utf-8")
    findings: list[Finding] = []
    for sha in sorted(inventory.all_recorded_shas()):
        if sha not in text:
            findings.append(
                Finding(
                    inventory.REVIEW_DOC,
                    1,
                    f"recorded SHA {sha} is missing from the dependency review",
                )
            )
    return findings


def collect_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(check_inventory_transitives())
    findings.extend(check_review_doc(root))
    scanned: list[str] = []
    for path in list_workflow_paths(root):
        relative = path.relative_to(root).as_posix()
        scanned.append(relative)
        findings.extend(check_workflow_syntax(root, relative))
        for ref in read_use_refs(root, relative):
            findings.extend(check_use_ref(ref))
    for path in list_local_action_paths(root):
        relative = path.relative_to(root).as_posix()
        scanned.append(relative)
        for ref in read_use_refs(root, relative):
            findings.extend(check_use_ref(ref))
    if not scanned:
        findings.append(Finding(".github/workflows", 1, "no workflow files found"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root (default: inferred from this script).",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    findings = collect_findings(root)
    if findings:
        for finding in findings:
            print(finding.format())
        print(f"action-pin check failed: {len(findings)} finding(s).", file=sys.stderr)
        return 1
    workflow_count = len(list_workflow_paths(root))
    print(
        f"action-pin check passed "
        f"({workflow_count} workflow files, {len(inventory.ACTION_PINS)} recorded pins)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
