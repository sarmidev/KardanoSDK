#!/usr/bin/env python3
"""Restricted-claim (banned-phrase) scanner.

Classifies each match on its own. A permitted occurrence on a line never
suppresses a second, prohibited occurrence on the same line.

Phrases are matched longest-first so "cryptographically safe" is one hit,
not a nested "safe". Output is path:line:column (1-based).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Longest phrase first. The list is the guardrails "No banned words" rule.
BANNED_PHRASES: tuple[str, ...] = (
    "cryptographically safe",
    "production-ready",
    "hardened",
    "guaranteed",
    "audited",
    "secure",
    "safe",
)

SCAN_SUFFIXES: tuple[str, ...] = (".md", ".mdc", ".html", ".kt", ".kts")

# Exact path exclusions — one file each, each with a stated rationale.
# Directory-wide exclusions are listed separately and kept to frozen records.
EXACT_PATH_EXCLUSIONS: dict[str, str] = {
    "docs/AI_WORKING_AGREEMENT.md": (
        "Defines the restricted-claim policy; scanning the definition for its "
        "own words is circular."
    ),
    "docs/PHASE_1_PLAN.md": (
        "Dated Phase 1 implementation log that is appended, not rewritten; "
        "historical session wording is not a living product claim."
    ),
    "crypto/src/commonMain/kotlin/org/sarmidev/kardano/crypto/mnemonic/"
    "Bip39EnglishWordlist.kt": (
        "Cited, verbatim official BIP-39 English wordlist; 'safe' is wordlist "
        "entry #1479 (data, not a claim)."
    ),
    "shared/src/commonTest/kotlin/org/sarmidev/kardano/playground/ui/"
    "DemoCopyTest.kt": (
        "Test fixture that stores this same phrase list as data to check "
        "Playground copy against it."
    ),
    "crypto/src/androidMain/kotlin/org/sarmidev/kardano/crypto/internal/"
    "pbkdf2/Pbkdf2HmacSha512.android.kt": (
        "One factual Android-platform-API availability note ('only guaranteed "
        "from Android API level 26'), not a product claim."
    ),
    "shared/src/commonTest/kotlin/org/sarmidev/kardano/playground/"
    "PlaygroundWalletPresenterTest.kt": (
        "One code comment ('safe to run under testAndroidHostTest'), not a "
        "product claim."
    ),
}

# Prefix exclusions — frozen historical records only, not living product docs.
PREFIX_EXCLUSIONS: dict[str, str] = {
    "docs/AUDIT/": (
        "Audit reports quote and discuss this exact policy; analyzing the "
        "rule is not itself a restricted claim."
    ),
    "docs/DECISIONS/": (
        "Frozen historical ADRs. This repo appends a dated result note rather "
        "than rewriting the original decision text."
    ),
    "docs/archive/": (
        "Verbatim historical HANDOFF/session snapshots. Prose is not edited."
    ),
    ".cursor/rules/": (
        "Cursor rules define the restricted-claim policy; scanning them is circular."
    ),
}

# "not" plus up to this many non-letters may precede a phrase (covers **not**).
NEGATION_GAP_MAX = 6


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    column: int
    phrase: str
    permitted: bool
    reason: str

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.column}: {self.phrase} ({self.reason})"


def posix_relpath(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_excluded(relative_path: str) -> bool:
    if relative_path in EXACT_PATH_EXCLUSIONS:
        return True
    return any(relative_path.startswith(prefix) for prefix in PREFIX_EXCLUSIONS)


def exclusion_rationale(relative_path: str) -> str | None:
    if relative_path in EXACT_PATH_EXCLUSIONS:
        return EXACT_PATH_EXCLUSIONS[relative_path]
    for prefix, rationale in PREFIX_EXCLUSIONS.items():
        if relative_path.startswith(prefix):
            return rationale
    return None


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _has_word_boundaries(text: str, start: int, end: int) -> bool:
    if start > 0 and _is_word_char(text[start - 1]):
        return False
    if end < len(text) and _is_word_char(text[end]):
        return False
    return True


def _preceded_by_hyphen_compound(text: str, start: int) -> bool:
    if start < 2:
        return False
    return text[start - 1] == "-" and text[start - 2].isalpha()


def _preceded_by_negation(text: str, start: int) -> bool:
    prefix = text[:start]
    # Allow up to NEGATION_GAP_MAX non-letters between "not" and the phrase.
    gap = 0
    i = len(prefix) - 1
    while i >= 0 and gap < NEGATION_GAP_MAX and not prefix[i].isalpha():
        i -= 1
        gap += 1
    if i < 2:
        return False
    # The three letters ending at i should be "not" as a whole word.
    candidate = prefix[i - 2 : i + 1]
    if candidate.lower() != "not":
        return False
    before = i - 3
    if before >= 0 and _is_word_char(prefix[before]):
        return False
    return True


def classify_match(text: str, start: int) -> tuple[bool, str]:
    if _preceded_by_hyphen_compound(text, start):
        return True, "hyphen-compound"
    if _preceded_by_negation(text, start):
        return True, "negation"
    return False, "restricted-claim"


def find_matches_in_text(text: str) -> list[tuple[int, int, str, bool, str]]:
    """Return (start, end, phrase, permitted, reason) for each match."""
    occupied = [False] * len(text)
    found: list[tuple[int, int, str, bool, str]] = []
    lower = text.lower()
    for phrase in BANNED_PHRASES:
        needle = phrase.lower()
        start = 0
        while True:
            index = lower.find(needle, start)
            if index < 0:
                break
            end = index + len(needle)
            start = index + 1
            if not _has_word_boundaries(text, index, end):
                continue
            if any(occupied[index:end]):
                continue
            for pos in range(index, end):
                occupied[pos] = True
            permitted, reason = classify_match(text, index)
            found.append((index, end, phrase, permitted, reason))
    found.sort(key=lambda item: item[0])
    return found


def scan_text(relative_path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    # splitlines() drops a trailing empty line; keep line numbers 1-based
    # against the original text including a final newline.
    lines = text.splitlines()
    offset = 0
    for line_no, line in enumerate(lines, start=1):
        for start, _end, phrase, permitted, reason in find_matches_in_text(line):
            findings.append(
                Finding(
                    path=relative_path,
                    line=line_no,
                    column=start + 1,
                    phrase=phrase,
                    permitted=permitted,
                    reason=reason,
                )
            )
        offset += len(line)
        if offset < len(text) and text[offset] == "\n":
            offset += 1
    return findings


def list_tracked_scan_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", *[f"*{suffix}" for suffix in SCAN_SUFFIXES]],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = [line for line in result.stdout.splitlines() if line]
    return [path for path in paths if not is_excluded(path)]


def scan_paths(root: Path, relative_paths: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for relative in relative_paths:
        if is_excluded(relative):
            continue
        path = root / relative
        text = path.read_text(encoding="utf-8")
        findings.extend(scan_text(relative, text))
    return findings


def prohibited_findings(findings: list[Finding]) -> list[Finding]:
    return [finding for finding in findings if not finding.permitted]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root (default: inferred from this script).",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional repo-relative paths. Default: git-tracked scan suffixes.",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    paths = args.paths if args.paths else list_tracked_scan_paths(root)
    prohibited = prohibited_findings(scan_paths(root, paths))
    if prohibited:
        for finding in prohibited:
            print(finding.format())
        print(
            f"restricted-claim scan failed: {len(prohibited)} prohibited "
            "occurrence(s).",
            file=sys.stderr,
        )
        return 1
    print(f"restricted-claim scan passed ({len(paths)} files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
