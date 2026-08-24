"""Compare two independent Windows x86-64 JVM staging trees.

Requires byte-identical SHA-256 and matching PE/export/import reports.
Does not write CHECKSUMS.sha256 or copy into src/. Windows is
candidate-only until an independent Phase C promotion review.
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
import windows_pe_verify as windows_pe  # noqa: E402


def _dll_path(root: Path) -> Path:
    spec = natives.WINDOWS_JVM_CANDIDATE_ARTIFACTS[0]
    direct = root / spec.relative_path
    if direct.is_file():
        return direct
    nested = root / "artifacts" / spec.relative_path
    if nested.is_file():
        return nested
    raise FileNotFoundError(f"Windows candidate missing under {root}")


def _report(path: Path) -> dict[str, object]:
    digest = natives.sha256_file(path)
    record = windows_pe.verify_windows_x86_64_dll(path, require_tools=True)
    return {
        "path": str(path),
        "sha256": digest,
        "size": path.stat().st_size,
        "machine": record.machine,
        "magic": record.magic,
        "subsystem": record.subsystem,
        "dll_characteristics": record.dll_characteristics,
        "timestamp": record.timestamp,
        "imports": [item.name for item in record.imports],
        "import_functions": {item.name: item.functions for item in record.imports},
        "sign_exports": [
            {"name": item.name, "ordinal": item.ordinal, "rva": item.rva}
            for item in record.sign_exports
        ],
        "dumpbin_returncode": record.dumpbin_returncode,
        "forbidden_paths": record.forbidden_paths,
        "jna_prefix": windows_pe.JNA_RESOURCE_PREFIX,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    findings: list[str] = []
    try:
        left_dll = _dll_path(args.left.resolve())
        right_dll = _dll_path(args.right.resolve())
        left = _report(left_dll)
        right = _report(right_dll)
    except (OSError, windows_pe.PeError) as error:
        findings.append(str(error))
        left = {}
        right = {}
    else:
        for key in (
            "sha256",
            "size",
            "machine",
            "magic",
            "subsystem",
            "dll_characteristics",
            "timestamp",
            "imports",
            "sign_exports",
        ):
            if left.get(key) != right.get(key):
                findings.append(f"{key} differs: {left.get(key)!r} vs {right.get(key)!r}")
        if left.get("forbidden_paths") or right.get("forbidden_paths"):
            findings.append("embedded host-absolute paths or PDB bytes are present")
    payload = {
        "left": left,
        "right": right,
        "findings": findings,
        "ok": not findings,
        "relative_path": natives.WINDOWS_JVM_CANDIDATE_ARTIFACTS[0].relative_path,
        "jna_prefix": windows_pe.JNA_RESOURCE_PREFIX,
        "windows_runs_on": "windows-2022",
        "candidate_only": True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if findings:
        print(f"windows candidate compare failed: {len(findings)} finding(s).", file=sys.stderr)
        return 1
    print("windows candidates are byte-identical and match PE policy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
