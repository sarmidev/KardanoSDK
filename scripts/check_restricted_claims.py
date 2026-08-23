#!/usr/bin/env python3
"""Restricted-claim (banned-phrase) scanner.

Classifies each match on its own. A permitted occurrence on a line never
suppresses a second, prohibited occurrence on the same line.

Phrases are matched longest-first so "cryptographically safe" is one hit,
not a nested "safe". Markdown emphasis inside a phrase is ignored for
matching; reported columns refer to the original line.
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

SCAN_SUFFIXES: tuple[str, ...] = (
    ".md",
    ".mdc",
    ".html",
    ".kt",
    ".kts",
    ".swift",
    ".xml",
    ".properties",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
)

# Exact path exclusions — one file each, each with a stated rationale.
# No directory-wide exclusions. Active ADR result notes and the current
# final audit are scanned.
EXACT_PATH_EXCLUSIONS: dict[str, str] = {
    "docs/AI_WORKING_AGREEMENT.md": (
        "Defines the restricted-claim policy; scanning the definition for its "
        "own words is circular."
    ),
    "docs/PHASE_1_PLAN.md": (
        "Dated Phase 1 implementation log that is appended, not rewritten; "
        "historical session wording is not a living product claim."
    ),
    "docs/AUDIT/2026-08-22-pre-release-audit.md": (
        "Immutable prior-audit record. Quotes the restricted-claim list and "
        "historical module disclaimers; not a living product claim."
    ),
    "docs/DECISIONS/0001-cbor-and-parser-policy.md": (
        "Frozen evaluation question ('Is it audited…') from the original "
        "library-selection table. Historical ADR text is not rewritten."
    ),
    "docs/DECISIONS/0012-address-encoding-and-roundtrip.md": (
        "Frozen Block 1.7a wording ('safe direction') describing the "
        "decode(encode(x)) test-vector rule. Historical ADR text."
    ),
    "docs/DECISIONS/0018-signing-scope-enforcement-and-publication.md": (
        "Frozen ADR sentence forbidding release notes from using the "
        "restricted adjective. Historical decision text."
    ),
    "docs/archive/handoff/2026-08-23-pre-curation.md": (
        "Verbatim historical HANDOFF snapshot. Prose is not edited."
    ),
    ".cursor/rules/kardano-sdk-guardrails.mdc": (
        "Defines the restricted-claim policy list; scanning it is circular."
    ),
    ".cursor/rules/kotlin-tests-and-docs.mdc": (
        "Policy example ('decode(encode(x)) == x is safe to test'); scanning "
        "the rule text is circular."
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

# Explicit reviewed technical compounds only. Arbitrary hyphen prefixes
# (funds-safe, crypto-safe, type-safe) are prohibited.
PERMITTED_COMPOUNDS: dict[str, str] = {
    "display-safe": (
        "shared/README.md: Playground presentation types hold public metadata "
        "only. Technical compound, not a product-wide claim."
    ),
}

# "not" plus up to this many non-letters may precede a phrase, and only if
# the gap does not include sentence-ending punctuation.
NEGATION_GAP_MAX = 6
SENTENCE_ENDERS = frozenset(".!?;")
EMPHASIS_CHARS = frozenset("*_`")


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


def parse_ls_files_z(raw: bytes) -> list[str]:
    """Split `git ls-files -z` output. Filenames may contain spaces or newlines."""
    return [part.decode("utf-8") for part in raw.split(b"\0") if part]


def is_scan_path(relative_path: str) -> bool:
    return any(relative_path.endswith(suffix) for suffix in SCAN_SUFFIXES)


def is_excluded(relative_path: str) -> bool:
    return relative_path in EXACT_PATH_EXCLUSIONS


def exclusion_rationale(relative_path: str) -> str | None:
    return EXACT_PATH_EXCLUSIONS.get(relative_path)


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _normalize_emphasis(text: str) -> tuple[str, list[int]]:
    """Drop Markdown emphasis markers; map each kept char to its original index."""
    kept: list[str] = []
    mapping: list[int] = []
    for index, char in enumerate(text):
        if char in EMPHASIS_CHARS:
            continue
        kept.append(char)
        mapping.append(index)
    return "".join(kept), mapping


def _has_word_boundaries(text: str, start: int, end: int) -> bool:
    if start > 0 and _is_word_char(text[start - 1]):
        return False
    if end < len(text) and _is_word_char(text[end]):
        return False
    return True


def _preceded_by_permitted_compound(text: str, start: int, phrase: str) -> bool:
    if start < 2 or text[start - 1] != "-":
        return False
    left_end = start - 1
    left_start = left_end - 1
    if left_start < 0 or not text[left_start].isalpha():
        return False
    while left_start > 0 and text[left_start - 1].isalpha():
        left_start -= 1
    compound = f"{text[left_start:left_end]}-{phrase}"
    return compound.lower() in PERMITTED_COMPOUNDS


def _preceded_by_negation(text: str, start: int) -> bool:
    prefix = text[:start]
    gap = 0
    index = len(prefix) - 1
    while index >= 0 and gap < NEGATION_GAP_MAX and not prefix[index].isalpha():
        if prefix[index] in SENTENCE_ENDERS:
            return False
        index -= 1
        gap += 1
    if index < 2:
        return False
    candidate = prefix[index - 2 : index + 1]
    if candidate.lower() != "not":
        return False
    before = index - 3
    if before >= 0 and _is_word_char(prefix[before]):
        return False
    return True


def classify_match(text: str, start: int, phrase: str) -> tuple[bool, str]:
    if _preceded_by_permitted_compound(text, start, phrase):
        return True, "permitted-compound"
    if _preceded_by_negation(text, start):
        return True, "negation"
    return False, "restricted-claim"


def find_matches_in_text(text: str) -> list[tuple[int, int, str, bool, str]]:
    """Return (orig_start, orig_end, phrase, permitted, reason) for each match."""
    normalized, mapping = _normalize_emphasis(text)
    occupied = [False] * len(normalized)
    found: list[tuple[int, int, str, bool, str]] = []
    lower = normalized.lower()
    for phrase in BANNED_PHRASES:
        needle = phrase.lower()
        cursor = 0
        while True:
            index = lower.find(needle, cursor)
            if index < 0:
                break
            end = index + len(needle)
            cursor = index + 1
            if not _has_word_boundaries(normalized, index, end):
                continue
            if any(occupied[index:end]):
                continue
            for pos in range(index, end):
                occupied[pos] = True
            orig_start = mapping[index]
            orig_end = mapping[end - 1] + 1
            permitted, reason = classify_match(text, orig_start, phrase)
            found.append((orig_start, orig_end, phrase, permitted, reason))
    found.sort(key=lambda item: item[0])
    return found


def scan_text(relative_path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
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
    return findings


def list_tracked_scan_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    paths = parse_ls_files_z(result.stdout)
    return [path for path in paths if is_scan_path(path) and not is_excluded(path)]


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
