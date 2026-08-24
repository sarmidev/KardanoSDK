#!/usr/bin/env python3
"""Compare two independent Linux x86-64 JVM staging trees.

Requires byte-identical SHA-256 and matching ELF/symbol/dependency
reports. After Phase C promotion, also requires that shared digest to
equal the committed Linux CHECKSUMS row and the committed ``.so``.
Does not write CHECKSUMS.sha256 or copy into src/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import linux_elf_verify as linux_elf  # noqa: E402
import native_artifacts as natives  # noqa: E402


def _so_path(root: Path) -> Path:
    spec = natives.LINUX_JVM_ARTIFACTS[0]
    direct = root / spec.relative_path
    if direct.is_file():
        return direct
    nested = root / "artifacts" / spec.relative_path
    if nested.is_file():
        return nested
    raise FileNotFoundError(f"Linux candidate missing under {root}")


def _report(path: Path) -> dict[str, object]:
    digest = natives.sha256_file(path)
    record = linux_elf.verify_linux_x86_64_cdylib(path, require_tools=True)
    return {
        "path": str(path),
        "sha256": digest,
        "size": path.stat().st_size,
        "soname": record.soname,
        "needed": record.needed,
        "rpath": record.rpath,
        "runpath": record.runpath,
        "symbols": record.symbols,
        "section_names": record.section_names,
        "has_build_id": record.has_build_id,
        "readelf_returncode": record.readelf_returncode,
        "nm_returncode": record.nm_returncode,
        "glibc_requirements": record.glibc_requirements,
        "gnu_versions": record.gnu_versions,
        "sign_exports": record.sign_exports,
        "documented_glibc_baseline": record.documented_glibc_baseline,
        "forbidden_paths": record.forbidden_paths,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--checksums",
        type=Path,
        help="Committed CHECKSUMS.sha256; require A/B SHA-256 to match the Linux row.",
    )
    parser.add_argument(
        "--committed-so",
        type=Path,
        help="Committed Linux .so path; require byte identity with A/B.",
    )
    args = parser.parse_args(argv)
    findings: list[str] = []
    try:
        left_so = _so_path(args.left.resolve())
        right_so = _so_path(args.right.resolve())
        left = _report(left_so)
        right = _report(right_so)
    except (OSError, linux_elf.ElfError) as error:
        findings.append(str(error))
        left = {}
        right = {}
    else:
        for key in (
            "sha256",
            "size",
            "soname",
            "needed",
            "rpath",
            "runpath",
            "glibc_requirements",
            "sign_exports",
        ):
            if left.get(key) != right.get(key):
                findings.append(f"{key} differs: {left.get(key)!r} vs {right.get(key)!r}")
        left_syms = [item for item in (left.get("symbols") or []) if item == natives.SIGN_SYMBOL]
        right_syms = [item for item in (right.get("symbols") or []) if item == natives.SIGN_SYMBOL]
        if len(left_syms) != 1 or len(right_syms) != 1:
            findings.append("sign symbol missing or ambiguous on one candidate")
        if left.get("forbidden_paths") or right.get("forbidden_paths"):
            findings.append("embedded host-absolute paths are present")
        linux_rel = natives.LINUX_JVM_ARTIFACTS[0].relative_path
        if args.checksums is not None:
            rows = natives.load_manifest(args.checksums.resolve())
            expected = rows.get(linux_rel)
            if expected is None:
                findings.append(f"committed CHECKSUMS is missing {linux_rel}")
            elif left.get("sha256") != expected or right.get("sha256") != expected:
                findings.append(
                    f"candidate SHA-256 {left.get('sha256')} != CHECKSUMS {expected}"
                )
        if args.committed_so is not None:
            committed = args.committed_so.resolve()
            if not committed.is_file():
                findings.append(f"committed Linux .so is missing: {committed}")
            else:
                committed_sha = natives.sha256_file(committed)
                if committed_sha != left.get("sha256") or committed_sha != right.get("sha256"):
                    findings.append(
                        f"candidate SHA-256 {left.get('sha256')} != committed .so {committed_sha}"
                    )
        baseline = linux_elf.DOCUMENTED_GLIBC_BASELINE_LABEL
        for side, report in (("left", left), ("right", right)):
            if report.get("documented_glibc_baseline") != baseline:
                findings.append(f"{side} glibc baseline is not {baseline}")
            too_new = [
                name
                for name in (report.get("glibc_requirements") or [])
                if not linux_elf.glibc_requirement_allowed(name)
            ]
            if too_new:
                findings.append(f"{side} GLIBC requirement {too_new} exceeds {baseline}")
    payload = {
        "left": left,
        "right": right,
        "findings": findings,
        "ok": not findings,
        "relative_path": natives.LINUX_JVM_ARTIFACTS[0].relative_path,
        "jna_prefix": linux_elf.JNA_RESOURCE_PREFIX,
        "documented_glibc_baseline": linux_elf.DOCUMENTED_GLIBC_BASELINE_LABEL,
        "linux_runs_on": "ubuntu-22.04",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if findings:
        print(f"linux candidate compare failed: {len(findings)} finding(s).", file=sys.stderr)
        return 1
    print("linux candidates are byte-identical and match ELF policy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
