#!/usr/bin/env python3
"""Compare two independent Linux x86-64 JVM staging trees.

Requires byte-identical SHA-256 and matching ELF/symbol/dependency
reports. Does not write CHECKSUMS.sha256 or copy into src/.
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
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
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
        for key in ("sha256", "size", "soname", "needed", "rpath", "runpath"):
            if left.get(key) != right.get(key):
                findings.append(f"{key} differs: {left.get(key)!r} vs {right.get(key)!r}")
        left_syms = set(left.get("symbols") or [])
        right_syms = set(right.get("symbols") or [])
        if natives.SIGN_SYMBOL not in left_syms or natives.SIGN_SYMBOL not in right_syms:
            findings.append("sign symbol missing from one candidate")
    payload = {
        "left": left,
        "right": right,
        "findings": findings,
        "ok": not findings,
        "relative_path": natives.LINUX_JVM_ARTIFACTS[0].relative_path,
        "jna_prefix": linux_elf.JNA_RESOURCE_PREFIX,
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
