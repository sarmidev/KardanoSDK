#!/usr/bin/env python3
"""Verify archived HANDOFF snapshots preserve the original bytes.

The 2026-08-23 snapshot is a verbatim copy of docs/HANDOFF.md at
fix/provider-boundaries-and-timeouts (3936047), except the six
`](DECISIONS/` Markdown links are rewritten to `](../../DECISIONS/` so they
resolve from docs/archive/handoff/. Reversing that rewrite must restore the
recorded SHA-256.

This script is a coverage check, not a claim about completeness of later
edits to the living docs/HANDOFF.md.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Recorded from docs/HANDOFF.md immediately before the 2026-08-23 curation
# (UTF-8 SHA-256 of the living file at 3936047).
PRE_CURATION_SHA256 = "39998bd77ee96a55c3e2473e4aee73f7a9cc2a65f91136fc340a1af849cf21c4"
PRE_CURATION_BYTES = 358808
PRE_CURATION_LINES = 4875
ARCHIVE_RELATIVE = Path("docs/archive/handoff/2026-08-23-pre-curation.md")
LINK_ARCHIVE_PREFIX = "](../../DECISIONS/"
LINK_ORIGINAL_PREFIX = "](DECISIONS/"
EXPECTED_LINK_REWRITES = 6
DECISIONS_TARGETS = (
    "docs/DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md",
    "docs/DECISIONS/0011-phase-1-architecture-standards.md",
    "docs/DECISIONS/0012-address-encoding-and-roundtrip.md",
    "docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md",
    "docs/DECISIONS/0014-minimal-ada-transaction-builder.md",
)


def sha256_utf8(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def restore_original_links(archive_text: str) -> str:
    return archive_text.replace(LINK_ARCHIVE_PREFIX, LINK_ORIGINAL_PREFIX)


def verify_pre_curation_snapshot(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    archive_path = repo_root / ARCHIVE_RELATIVE
    if not archive_path.is_file():
        return [f"missing archive snapshot: {ARCHIVE_RELATIVE.as_posix()}"]

    archive_text = archive_path.read_text(encoding="utf-8")
    rewrite_count = archive_text.count(LINK_ARCHIVE_PREFIX)
    if rewrite_count != EXPECTED_LINK_REWRITES:
        errors.append(
            f"expected {EXPECTED_LINK_REWRITES} rewritten DECISIONS links, "
            f"found {rewrite_count}"
        )
    if LINK_ORIGINAL_PREFIX in archive_text:
        errors.append("archive still contains unresolved ](DECISIONS/ links")

    restored = restore_original_links(archive_text)
    restored_bytes = len(restored.encode("utf-8"))
    restored_lines = restored.count("\n") + (0 if restored.endswith("\n") else 1)
    restored_sha = sha256_utf8(restored)
    if restored_sha != PRE_CURATION_SHA256:
        errors.append(
            f"restored snapshot SHA-256 {restored_sha} != recorded "
            f"{PRE_CURATION_SHA256}"
        )
    if restored_bytes != PRE_CURATION_BYTES:
        errors.append(
            f"restored snapshot is {restored_bytes} bytes, expected {PRE_CURATION_BYTES}"
        )
    if restored_lines != PRE_CURATION_LINES:
        errors.append(
            f"restored snapshot is {restored_lines} lines, expected {PRE_CURATION_LINES}"
        )

    for relative in DECISIONS_TARGETS:
        if not (repo_root / relative).is_file():
            errors.append(f"rewritten link target missing: {relative}")
    return errors


def main() -> int:
    errors = verify_pre_curation_snapshot()
    if errors:
        print("HANDOFF archive check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(
        "HANDOFF archive check passed: "
        f"{ARCHIVE_RELATIVE.as_posix()} restores to {PRE_CURATION_SHA256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
