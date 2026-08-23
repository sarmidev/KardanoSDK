#!/usr/bin/env python3
"""Require SHA-pinned GitHub Actions via a structural YAML walk.

Workflows and local action metadata are parsed with
`scripts/yaml_uses_extract.rb` (Ruby stdlib Psych → JSON). Line-oriented
regex is not used to discover `uses`. Every mapping/list `uses` value is
inspected, including flow mappings and `uses :` whitespace.

External actions and reusable workflows must be `owner/repo@` plus a
40-character lowercase SHA that matches `scripts/action_pin_inventory.py`
for that owner/repo. Local `./path` references are resolved from the
repository root, must stay inside the tree, and must have `action.yml`
and/or `action.yaml`. Nested local uses are followed; cycles, missing
metadata, path escape, and unreviewed external nested uses are findings.
Local metadata with `runs.using: docker` is rejected (any image) until
a digest/inventory policy exists. Direct `uses: docker://...` is also
rejected. YAML aliases/anchors and non-string `uses` / `runs` /
`runs.using` / `runs.image` values are extractor errors, never treated
as absent fields.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import action_pin_inventory as inventory  # noqa: E402

HELPER = REPO_ROOT / "scripts" / "yaml_uses_extract.rb"
RUBY = "ruby"

SHA_REF_RE = __import__("re").compile(
    r"^(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@(?P<sha>[0-9a-f]{40})$"
)
LOCAL_REF_RE = __import__("re").compile(r"^\./")
DOCKER_REF_RE = __import__("re").compile(r"^docker://")
ACTION_METADATA_NAMES = ("action.yml", "action.yaml")


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


def classify_use(path: str, line: int, raw: str | None) -> UseRef:
    if raw is None:
        return UseRef(path, line, "", None, None, "invalid")
    value = raw.strip()
    if not value:
        return UseRef(path, line, raw, None, None, "invalid")
    if LOCAL_REF_RE.match(value):
        return UseRef(path, line, value, None, None, "local")
    if DOCKER_REF_RE.match(value):
        return UseRef(path, line, value, None, None, "docker")
    sha_match = SHA_REF_RE.match(value)
    if sha_match is None:
        return UseRef(path, line, value, None, None, "unpinned")
    return UseRef(
        path,
        line,
        value,
        sha_match.group("action"),
        sha_match.group("sha"),
        "pinned",
    )


def parse_yaml_document(text: str, *, source_path: str = "") -> dict:
    if not HELPER.is_file():
        raise FileNotFoundError(f"missing YAML helper: {HELPER}")
    command = [RUBY, str(HELPER)]
    if Path(source_path).name in ACTION_METADATA_NAMES:
        command.append("--action-metadata")
    completed = subprocess.run(
        command,
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(completed.stderr.strip() or "YAML parse failed")
    payload = json.loads(completed.stdout or "{}")
    if not isinstance(payload, dict):
        raise ValueError("YAML helper returned a non-object")
    uses = payload.get("uses")
    if not isinstance(uses, list):
        raise ValueError("YAML helper returned no uses list")
    keys = payload.get("top_level_keys")
    if keys is not None and not isinstance(keys, list):
        raise ValueError("YAML helper returned invalid top_level_keys")
    runs = payload.get("runs")
    if runs is None:
        runs = {}
    if not isinstance(runs, dict):
        raise ValueError("YAML helper returned invalid runs")
    errors = payload.get("errors")
    if errors is None:
        errors = []
    if not isinstance(errors, list):
        raise ValueError("YAML helper returned invalid errors")
    return {
        "uses": uses,
        "top_level_keys": keys or [],
        "runs": runs,
        "errors": errors,
    }


def extract_uses_from_text(text: str, *, source_path: str = "") -> list[dict]:
    return parse_yaml_document(text, source_path=source_path)["uses"]


def parse_use_line(path: str, line_no: int, line: str) -> UseRef | None:
    """Classify one physical line by parsing it as YAML (not a regex hunt)."""
    try:
        entries = extract_uses_from_text(line)
    except ValueError:
        return None
    if not entries:
        return None
    first = entries[0]
    return classify_use(path, line_no, first.get("value"))


def list_workflow_paths(root: Path) -> list[Path]:
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return []
    return sorted(
        path
        for path in workflows.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    )


def list_action_metadata_paths(root: Path) -> list[Path]:
    found: list[Path] = []
    for name in ACTION_METADATA_NAMES:
        found.extend(root.rglob(name))
    return sorted(
        path
        for path in found
        if path.is_file() and ".git" not in path.parts
    )


def read_use_refs(root: Path, relative: str) -> tuple[list[UseRef], list[Finding]]:
    text = (root / relative).read_text(encoding="utf-8")
    findings: list[Finding] = []
    try:
        entries = extract_uses_from_text(text, source_path=relative)
    except ValueError as exc:
        return [], [Finding(relative, 1, f"YAML parse failed: {exc}")]
    refs: list[UseRef] = []
    for entry in entries:
        line = int(entry.get("line") or 1)
        if entry.get("error"):
            findings.append(Finding(relative, line, str(entry["error"])))
            continue
        value = entry.get("value")
        if not isinstance(value, str) or not value.strip():
            findings.append(
                Finding(relative, line, "uses value is empty or not a string")
            )
            continue
        refs.append(classify_use(relative, line, value))
    return refs, findings


def check_workflow_structure(root: Path, relative: str) -> list[Finding]:
    path = root / relative
    text = path.read_text(encoding="utf-8")
    findings: list[Finding] = []
    if "\t" in text:
        findings.append(Finding(relative, 1, "workflow uses tab indentation"))
    try:
        document = parse_yaml_document(text, source_path=relative)
    except ValueError as exc:
        return [Finding(relative, 1, f"workflow YAML is not parseable: {exc}")]
    keys = {str(key) for key in document["top_level_keys"]}
    if "on" not in keys:
        findings.append(Finding(relative, 1, "workflow is missing a top-level on: key"))
    if "jobs" not in keys:
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
                "docker:// uses are rejected until a digest/inventory "
                f"policy exists (found {ref.raw})",
            )
        ]
    if ref.kind == "invalid":
        return [Finding(ref.path, ref.line, "uses value is empty or not a string")]
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
        sha_owner = next(
            (pin.action for pin in inventory.ACTION_PINS if pin.sha == ref.sha),
            None,
        )
        if sha_owner is not None:
            return [
                Finding(
                    ref.path,
                    ref.line,
                    f"owner/repo mismatch: {ref.action} is not {sha_owner} "
                    f"for SHA {ref.sha}",
                )
            ]
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


def resolve_local_action(root: Path, raw: str, from_path: str, line: int) -> Path | Finding:
    if not raw.startswith("./"):
        return Finding(from_path, line, f"local uses: must start with ./ ({raw!r})")
    rel = Path(raw[2:])
    if rel.is_absolute() or ".." in rel.parts:
        return Finding(from_path, line, f"local uses: path escapes the repository ({raw})")
    dest = (root / rel).resolve()
    try:
        dest.relative_to(root.resolve())
    except ValueError:
        return Finding(from_path, line, f"local uses: path escapes the repository ({raw})")
    if not dest.is_dir():
        return Finding(from_path, line, f"local action path is missing ({raw})")
    metadata = [dest / name for name in ACTION_METADATA_NAMES if (dest / name).is_file()]
    if not metadata:
        return Finding(
            from_path,
            line,
            f"local action is missing action.yml or action.yaml ({raw})",
        )
    return dest


def _document_errors(relative: str, document: dict) -> list[Finding]:
    findings: list[Finding] = []
    for item in document.get("errors") or []:
        if not isinstance(item, dict) or not item.get("message"):
            findings.append(
                Finding(relative, 1, "YAML helper returned a non-scalar error marker")
            )
            continue
        findings.append(
            Finding(relative, int(item.get("line") or 1), str(item["message"]))
        )
    return findings


def check_local_action_runtime(relative: str, document: dict) -> list[Finding]:
    """Fail closed: this repo has no approved local Docker actions."""
    findings = _document_errors(relative, document)
    runs = document.get("runs")
    if not isinstance(runs, dict):
        findings.append(Finding(relative, 1, "runs is not a mapping"))
        return findings
    if runs.get("error"):
        findings.append(
            Finding(relative, int(runs.get("line") or 1), str(runs["error"]))
        )
        return findings
    using_entry = runs.get("using") if isinstance(runs.get("using"), dict) else None
    if using_entry is None:
        findings.append(Finding(relative, 1, "runs.using is missing or not a string"))
        return findings
    if using_entry.get("error"):
        findings.append(
            Finding(
                relative,
                int(using_entry.get("line") or 1),
                str(using_entry["error"]),
            )
        )
        return findings
    using = using_entry.get("value")
    if not isinstance(using, str) or not using.strip():
        findings.append(
            Finding(
                relative,
                int(using_entry.get("line") or 1),
                "runs.using is missing or not a string",
            )
        )
        return findings
    image_entry = runs.get("image") if isinstance(runs.get("image"), dict) else None
    if image_entry and image_entry.get("error"):
        findings.append(
            Finding(
                relative,
                int(image_entry.get("line") or 1),
                str(image_entry["error"]),
            )
        )
    if using.strip().lower() != "docker":
        return findings
    image = image_entry.get("value") if image_entry else None
    if not isinstance(image, str) or not image.strip():
        findings.append(
            Finding(
                relative,
                int((image_entry or {}).get("line") or using_entry.get("line") or 1),
                "runs.image is missing or not a string",
            )
        )
        image_text = "(no image)"
    else:
        image_text = image
    line = int(using_entry.get("line") or (image_entry or {}).get("line") or 1)
    findings.append(
        Finding(
            relative,
            line,
            f"local Docker action is not approved: {relative} "
            f"image={image_text!r}",
        )
    )
    return findings


def inspect_local_action(
    root: Path,
    dest: Path,
    stack: tuple[str, ...],
    seen: set[str],
) -> list[Finding]:
    dest = dest.resolve()
    relative_dir = dest.relative_to(root.resolve()).as_posix()
    if relative_dir in stack:
        cycle = " -> ".join((*stack, relative_dir))
        return [Finding(relative_dir, 1, f"local action cycle: {cycle}")]
    if relative_dir in seen:
        return []
    seen.add(relative_dir)
    findings: list[Finding] = []
    for name in ACTION_METADATA_NAMES:
        meta = dest / name
        if not meta.is_file():
            continue
        relative = meta.relative_to(root).as_posix()
        try:
            document = parse_yaml_document(
                meta.read_text(encoding="utf-8"),
                source_path=relative,
            )
        except ValueError as exc:
            findings.append(Finding(relative, 1, f"YAML parse failed: {exc}"))
            continue
        findings.extend(check_local_action_runtime(relative, document))
        refs, parse_findings = read_use_refs(root, relative)
        findings.extend(parse_findings)
        for ref in refs:
            findings.extend(check_use_ref(ref))
            if ref.kind == "local":
                resolved = resolve_local_action(root, ref.raw, ref.path, ref.line)
                if isinstance(resolved, Finding):
                    findings.append(resolved)
                else:
                    findings.extend(
                        inspect_local_action(
                            root,
                            resolved,
                            (*stack, relative_dir),
                            seen,
                        )
                    )
    return findings


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
    root = root.resolve()
    findings: list[Finding] = []
    findings.extend(check_inventory_transitives())
    findings.extend(check_review_doc(root))
    scanned: list[str] = []
    seen_local: set[str] = set()
    for path in list_workflow_paths(root):
        relative = path.relative_to(root).as_posix()
        scanned.append(relative)
        findings.extend(check_workflow_structure(root, relative))
        refs, parse_findings = read_use_refs(root, relative)
        findings.extend(parse_findings)
        for ref in refs:
            findings.extend(check_use_ref(ref))
            if ref.kind == "local":
                resolved = resolve_local_action(root, ref.raw, ref.path, ref.line)
                if isinstance(resolved, Finding):
                    findings.append(resolved)
                else:
                    findings.extend(inspect_local_action(root, resolved, (), seen_local))
    for path in list_action_metadata_paths(root):
        dest = path.parent
        findings.extend(inspect_local_action(root, dest.resolve(), (), seen_local))
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
