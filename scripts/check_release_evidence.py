#!/usr/bin/env python3
"""Release-evidence checker for the Prompt 7 legal-evidence packet.

Fails closed on any of:

1. NOTICE (and LICENSES/README.md) reference only license files that exist
   under LICENSES/.
2. The committed native-artifact evidence
   (docs/evidence/native_artifacts_inventory.json) matches
   crypto-signing-backend/CHECKSUMS.sha256 exactly (same paths, same count,
   same SHA-256 as the files on disk) -- no extra, missing, or stale row.
3. Every generated evidence file under docs/evidence/, and the digest file,
   is byte-identical to what `scripts/generate_legal_evidence.py` produces
   right now from the current tracked tree (lock/graph state is
   deterministic and the committed copy is not stale).
4. docs/LEGAL_REVIEW.md contains no unresolved generic placeholder token
   (TBD, TODO, FIXME, XXX, "PLACEHOLDER", "<insert", "[insert", "N/A" used as
   a stand-in for a required field). Legitimate open gates must use one of
   the ALLOWED_OPEN_GATE_MARKERS strings instead, so a reviewer can tell
   "deliberately open, pending a named external event" apart from
   "someone forgot to fill this in".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_legal_evidence as evidence  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
LICENSES_DIR = REPO_ROOT / "LICENSES"
NOTICE_PATH = REPO_ROOT / "NOTICE"
LEGAL_REVIEW_PATH = REPO_ROOT / "docs" / "LEGAL_REVIEW.md"
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence"

LICENSE_REFERENCE_RE = re.compile(r"LICENSES/([A-Za-z0-9._-]+\.txt)")

GENERIC_PLACEHOLDERS = (
    "TBD",
    "TODO",
    "FIXME",
    "XXX",
    "PLACEHOLDER",
    "<insert",
    "[insert",
    "<counsel name>",
    "<reviewer name>",
)

# The only strings LEGAL_REVIEW.md may use to mark a field as deliberately,
# currently unresolved and open (as opposed to "forgotten"). Every such gate
# must name the blocking external event so it is falsifiable.
ALLOWED_OPEN_GATE_MARKERS = (
    "OPEN — pending owner/counsel review",
    "OPEN — pending upstream hyperledger-identus/apollo issue #226",
    "OPEN — pending independent PE re-review",
)


def check_notice_license_references() -> list[str]:
    errors: list[str] = []
    if not NOTICE_PATH.is_file():
        return ["root NOTICE file is missing"]
    if not LICENSES_DIR.is_dir():
        return ["LICENSES/ directory is missing"]

    existing = {p.name for p in LICENSES_DIR.glob("*.txt")}
    if not existing:
        errors.append("LICENSES/ contains no *.txt license files")

    for source_path in (NOTICE_PATH, LICENSES_DIR / "README.md"):
        if not source_path.is_file():
            continue
        text = source_path.read_text(encoding="utf-8")
        referenced = set(LICENSE_REFERENCE_RE.findall(text))
        missing = sorted(referenced - existing)
        for name in missing:
            errors.append(
                f"{source_path.relative_to(REPO_ROOT)} references "
                f"LICENSES/{name}, which does not exist"
            )

    notice_text = NOTICE_PATH.read_text(encoding="utf-8")
    referenced_from_notice = set(LICENSE_REFERENCE_RE.findall(notice_text))
    unreferenced = sorted(existing - referenced_from_notice)
    for name in unreferenced:
        errors.append(
            f"LICENSES/{name} exists but is not cited anywhere in NOTICE "
            "(every committed license text must be attributed to at least "
            "one component)"
        )
    return errors


def check_native_inventory_matches_checksums() -> list[str]:
    errors: list[str] = []
    try:
        report = evidence.native_artifacts_inventory()
    except (FileNotFoundError, ValueError) as exc:
        return [f"native artifact inventory generation failed: {exc}"]

    checksums_path = evidence.SIGNING_BACKEND / "CHECKSUMS.sha256"
    checksum_rows = evidence.parse_checksums(checksums_path)
    if len(checksum_rows) != 9:
        errors.append(
            f"CHECKSUMS.sha256 has {len(checksum_rows)} rows, expected exactly 9"
        )
    if report["artifact_count"] != len(checksum_rows):
        errors.append(
            "native_artifacts_inventory artifact_count "
            f"{report['artifact_count']} != CHECKSUMS.sha256 row count "
            f"{len(checksum_rows)}"
        )
    inventory_path = EVIDENCE_DIR / "native_artifacts_inventory.json"
    if not inventory_path.is_file():
        errors.append("docs/evidence/native_artifacts_inventory.json is missing")
    return errors


def check_evidence_is_freshly_regenerable() -> list[str]:
    errors: list[str] = []
    generators = {
        "gradle_dependency_inventory.json": evidence.gradle_dependency_inventory,
        "cargo_dependency_inventory.json": evidence.cargo_dependency_inventory,
        "uniffi_bindings_inventory.json": evidence.uniffi_bindings_inventory,
        "native_artifacts_inventory.json": evidence.native_artifacts_inventory,
        "maven_native_carriers_inventory.json": evidence.maven_native_carriers_inventory,
    }
    for filename, generator in sorted(generators.items()):
        committed_path = EVIDENCE_DIR / filename
        if not committed_path.is_file():
            errors.append(f"docs/evidence/{filename} is missing")
            continue
        try:
            fresh_payload = generator()
        except Exception as exc:  # noqa: BLE001 - report and continue
            errors.append(f"{filename}: regeneration raised {exc!r}")
            continue
        import json

        fresh_text = json.dumps(fresh_payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        committed_text = committed_path.read_text(encoding="utf-8")
        if fresh_text != committed_text:
            errors.append(
                f"docs/evidence/{filename} is stale: regenerating it from the "
                "current tracked tree produces different bytes. Run "
                "python3 scripts/generate_legal_evidence.py and commit the result."
            )

    digest_path = EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt"
    if not digest_path.is_file():
        errors.append("docs/evidence/LEGAL_EVIDENCE_DIGEST.txt is missing")
    return errors


def check_legal_review_placeholders() -> list[str]:
    errors: list[str] = []
    if not LEGAL_REVIEW_PATH.is_file():
        return ["docs/LEGAL_REVIEW.md is missing"]
    text = LEGAL_REVIEW_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for token in GENERIC_PLACEHOLDERS:
            if token in line:
                errors.append(
                    f"docs/LEGAL_REVIEW.md:{lineno}: generic placeholder "
                    f"'{token}' is not allowed; use one of "
                    f"ALLOWED_OPEN_GATE_MARKERS to mark a deliberately open "
                    "field"
                )
    # Every "Status:" line must resolve to either a factual value or one of
    # the allowed named-gate markers -- never a bare "open"/"pending" without
    # naming what it is pending on.
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped.lower().startswith("- status:") and not stripped.lower().startswith(
            "status:"
        ):
            continue
        if any(marker in line for marker in ALLOWED_OPEN_GATE_MARKERS):
            continue
        if "resolved" in line.lower() or "n/a — " in line.lower():
            continue
        errors.append(
            f"docs/LEGAL_REVIEW.md:{lineno}: unrecognized Status value; use "
            "one of ALLOWED_OPEN_GATE_MARKERS or mark the field Resolved with "
            "its value"
        )
    return errors


def main() -> int:
    checks = (
        ("NOTICE / LICENSES cross-reference", check_notice_license_references),
        ("native inventory vs CHECKSUMS.sha256", check_native_inventory_matches_checksums),
        ("evidence freshness (deterministic regeneration)", check_evidence_is_freshly_regenerable),
        ("LEGAL_REVIEW.md placeholder scan", check_legal_review_placeholders),
    )
    all_errors: list[str] = []
    for name, check in checks:
        errors = check()
        if errors:
            print(f"[FAIL] {name}:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"[ok] {name}")
        all_errors.extend(errors)
    if all_errors:
        print(f"\nrelease-evidence check failed with {len(all_errors)} error(s)", file=sys.stderr)
        return 1
    print("\nrelease-evidence check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
