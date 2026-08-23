#!/usr/bin/env python3
"""Compare staged signing-backend natives against a checksum manifest.

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
from native_toolchain import STABLE_INSTALL_NAME  # noqa: E402


def _record_dict(record: natives.ArtifactRecord) -> dict[str, object]:
    return {
        "id": record.spec.artifact_id,
        "relative_path": record.spec.relative_path,
        "exists": record.exists,
        "size": record.size,
        "sha256": record.sha256,
        "file": record.file_output,
        "file_returncode": record.file_returncode,
        "lipo": record.lipo_output,
        "lipo_returncode": record.lipo_returncode,
        "otool_returncode": record.otool_returncode,
        "install_name": record.install_name,
        "uuid": record.uuid,
        "linker_version": record.linker_version,
        "sdk_version": record.sdk_version,
        "nm_command": record.nm_command,
        "nm_returncode": record.nm_returncode,
        "sign_symbols": record.symbols,
        "symbol_ok": record.symbol_ok,
        "arch_ok": record.arch_ok,
        "install_name_ok": record.install_name_ok,
        "ar_tv_returncode": record.ar_tv_returncode,
        "member_hashes": record.member_hashes,
        "embedded_paths": record.embedded_paths,
        "inspection_errors": record.inspection_errors,
    }


def build_report(
    committed_root: Path,
    staged_root: Path,
    *,
    groups: tuple[str, ...] | None,
    ndk_home: Path | None,
    mode: str,
    manifest: Path,
    require_inspection: bool,
    expected_install_name: str,
    evidence_dir: Path | None,
    logs_dir: Path | None,
) -> dict[str, object]:
    checksums = natives.load_manifest(manifest)
    findings, committed, staged = natives.compare_trees(
        committed_root,
        staged_root,
        checksums=checksums,
        groups=groups,
        ndk_home=ndk_home,
        compare_committed=(mode == "committed"),
        require_inspection=require_inspection,
        expected_install_name=expected_install_name,
        evidence_dir=evidence_dir,
        logs_dir=logs_dir,
    )
    diffs: list[dict[str, object]] = []
    staged_by_id = {item.spec.artifact_id: item for item in staged}
    for spec in natives.artifacts_for_groups(groups):
        expected = checksums.get(spec.relative_path)
        staged_record = staged_by_id.get(spec.artifact_id)
        if staged_record is None or not staged_record.exists:
            continue
        if expected and staged_record.sha256 == expected:
            continue
        if mode == "committed":
            left = committed_root / spec.relative_path
            right = staged_root / spec.relative_path
            if not (left.is_file() and right.is_file()):
                continue
            if natives.sha256_file(left) == natives.sha256_file(right):
                continue
            first = natives.first_differing_byte(left, right)
            entry: dict[str, object] = {"id": spec.artifact_id, "path": spec.relative_path}
            if first is not None:
                entry.update(first)
            entry["clusters"] = natives.difference_clusters(left, right)
            diffs.append(entry)
            continue
        diffs.append(
            {
                "id": spec.artifact_id,
                "path": spec.relative_path,
                "kind": "candidate-mismatch",
                "staged_sha256": staged_record.sha256,
                "manifest_sha256": expected,
                "size": staged_record.size,
                "uuid": staged_record.uuid,
                "install_name": staged_record.install_name,
            }
        )
    return {
        "committed_root": str(committed_root),
        "staged_root": str(staged_root),
        "mode": mode,
        "manifest": str(manifest),
        "expected_install_name": expected_install_name,
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
        help="Comma-separated groups: macos-jvm,android,ios,linux-jvm (default: committed eight).",
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
    parser.add_argument(
        "--mode",
        choices=("committed", "candidate"),
        default="committed",
        help="committed compares src/ + CHECKSUMS; candidate compares the manifest only.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Checksum manifest path.",
    )
    parser.add_argument(
        "--require-inspection",
        dest="require_inspection",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--skip-inspection",
        dest="require_inspection",
        action="store_false",
        help="Hash-only compare (unit tests). Default is fail-closed inspection.",
    )
    parser.add_argument(
        "--expected-install-name",
        default=STABLE_INSTALL_NAME,
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Require inspect evidence files under this directory.",
    )
    parser.add_argument(
        "--logs",
        type=Path,
        help="Require retained command *.meta.json logs under this directory.",
    )
    args = parser.parse_args(argv)
    groups: tuple[str, ...] | None = None
    if args.groups.strip():
        groups = tuple(item.strip() for item in args.groups.split(",") if item.strip())
        unknown = sorted(set(groups) - set(natives.GROUPS))
        if unknown:
            print(f"unknown groups: {', '.join(unknown)}", file=sys.stderr)
            return 2
    module_root = args.module_root.resolve()
    manifest = args.manifest
    if manifest is None:
        if args.mode == "candidate":
            manifest = module_root / "rebuild-candidates" / natives.CANDIDATE_MANIFEST_NAME
        else:
            manifest = module_root / natives.CHECKSUMS_NAME
    report = build_report(
        module_root,
        args.staging.resolve(),
        groups=groups,
        ndk_home=args.ndk_home,
        mode=args.mode,
        manifest=manifest.resolve(),
        require_inspection=args.require_inspection,
        expected_install_name=args.expected_install_name,
        evidence_dir=args.evidence.resolve() if args.evidence else None,
        logs_dir=args.logs.resolve() if args.logs else None,
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
    if args.mode == "candidate":
        print("verify-artifacts passed: staged bytes match the candidate manifest.")
    else:
        print("verify-artifacts passed: staged bytes match committed natives and CHECKSUMS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
