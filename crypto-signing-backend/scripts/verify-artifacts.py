#!/usr/bin/env python3
"""Compare staged signing-backend natives against committed bytes and CHECKSUMS.

Never writes into src/. A mismatch is a finding; this tool does not rewrite
CHECKSUMS.sha256 to accept unexplained output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import native_artifacts as natives  # noqa: E402


def _record_dict(record: natives.ArtifactRecord) -> dict[str, object]:
    return {
        "id": record.spec.artifact_id,
        "relative_path": record.spec.relative_path,
        "exists": record.exists,
        "size": record.size,
        "sha256": record.sha256,
        "file": record.file_output,
        "lipo": record.lipo_output,
        "install_name": record.install_name,
        "uuid": record.uuid,
        "sign_symbols": record.symbols,
        "symbol_ok": record.symbol_ok,
        "arch_ok": record.arch_ok,
    }


def build_report(
    committed_root: Path,
    staged_root: Path,
    *,
    groups: tuple[str, ...] | None,
    ndk_home: Path | None,
) -> dict[str, object]:
    checksums = natives.load_checksums(committed_root)
    findings, committed, staged = natives.compare_trees(
        committed_root,
        staged_root,
        checksums=checksums,
        groups=groups,
        ndk_home=ndk_home,
    )
    diffs: list[dict[str, object]] = []
    for spec in natives.EXISTING_ARTIFACTS:
        if groups is not None and spec.group not in groups:
            continue
        left = committed_root / spec.relative_path
        right = staged_root / spec.relative_path
        if left.is_file() and right.is_file() and natives.sha256_file(left) != natives.sha256_file(right):
            first = natives.first_differing_byte(left, right)
            if first is not None:
                diffs.append({"id": spec.artifact_id, **first})
    return {
        "committed_root": str(committed_root),
        "staged_root": str(staged_root),
        "groups": list(groups) if groups else list(natives.GROUPS),
        "checksum_rows": checksums,
        "committed": [_record_dict(item) for item in committed],
        "staged": [_record_dict(item) for item in staged],
        "first_differences": diffs,
        "findings": [
            {
                "kind": item.kind,
                "id": item.artifact_id,
                "path": item.path,
                "message": item.message,
            }
            for item in findings
        ],
        "ok": not findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module-root",
        type=Path,
        default=natives.MODULE_ROOT,
        help="crypto-signing-backend module root (committed artifacts live here).",
    )
    parser.add_argument(
        "--staging",
        type=Path,
        required=True,
        help="Staging directory that holds rebuilt copies at the same relative paths.",
    )
    parser.add_argument(
        "--groups",
        default="",
        help="Comma-separated groups: macos-jvm,android,ios (default: all).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Write the JSON comparison report here.",
    )
    parser.add_argument(
        "--ndk-home",
        type=Path,
        help="Optional Android NDK root for llvm-nm.",
    )
    args = parser.parse_args(argv)
    groups: tuple[str, ...] | None = None
    if args.groups.strip():
        groups = tuple(item.strip() for item in args.groups.split(",") if item.strip())
        unknown = sorted(set(groups) - set(natives.GROUPS))
        if unknown:
            print(f"unknown groups: {', '.join(unknown)}", file=sys.stderr)
            return 2
    report = build_report(
        args.module_root.resolve(),
        args.staging.resolve(),
        groups=groups,
        ndk_home=args.ndk_home,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    findings = report["findings"]
    if findings:
        print(f"verify-artifacts failed: {len(findings)} finding(s).", file=sys.stderr)
        return 1
    print("verify-artifacts passed: staged bytes match committed natives and CHECKSUMS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
