#!/usr/bin/env python3
"""Restricted-claim (banned-phrase) scanner.

Classifies each match on its own. A permitted occurrence on a line never
suppresses a second, prohibited occurrence on the same line.

Phrases are matched longest-first so "cryptographically safe" is one hit,
not a nested "safe". Markdown emphasis inside a phrase is ignored for
matching; reported columns refer to the original line.

Hyphen compounds are not exempt. Historical wording that cannot be
rewritten is allowlisted per occurrence: repository-relative path +
1-based physical line number + SHA-256 of the exact line bytes +
restricted phrase + 1-based occurrence of that phrase on the line.
Editing the line, duplicating it elsewhere, appending a new claim, or
adding a second match of the same phrase on an allowlisted line is a
finding. Inserting a line before an allowlisted occurrence shifts the
physical line number and is fail-closed until the allowlist is
re-reviewed.
"""

from __future__ import annotations

import argparse
import hashlib
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

# Whole-file exclusions — immutable archived snapshots or circular
# policy/test data only. Evolving ADRs, append-only logs, and ordinary
# source comments are scanned; historical hits use ALLOWED_OCCURRENCES.
EXACT_PATH_EXCLUSIONS: dict[str, str] = {
    "docs/AI_WORKING_AGREEMENT.md": (
        "Defines the restricted-claim policy; scanning the definition for its "
        "own words is circular."
    ),
    "docs/AUDIT/2026-08-22-pre-release-audit.md": (
        "Immutable dated prior-audit record. Later audits are new dated files; "
        "this file is not appended. It quotes the restricted-claim inventory "
        "throughout, so scanning it is circular."
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
}

# "not" plus up to this many non-letters may precede a phrase, and only if
# the gap does not include sentence-ending punctuation.
NEGATION_GAP_MAX = 6
SENTENCE_ENDERS = frozenset(".!?;")
EMPHASIS_CHARS = frozenset("*_`")


@dataclass(frozen=True)
class AllowedOccurrence:
    path: str
    line: int
    line_sha256: str
    phrase: str
    occurrence: int
    rationale: str


# Key: path + 1-based physical line + SHA-256 of the exact line text
# (UTF-8, no terminator) + phrase + 1-based phrase occurrence on that line.
# Line numbers were verified against the current tree on 2026-08-23.
ALLOWED_OCCURRENCES: tuple[AllowedOccurrence, ...] = (
    AllowedOccurrence(
        path="docs/DECISIONS/0001-cbor-and-parser-policy.md",
        line=43,
        line_sha256="7d60535476c7e82bff82d51140769a7586bea13f709814112ce5e62001d13c3d",
        phrase="audited",
        occurrence=1,
        rationale="Frozen library-selection question; later addenda must still scan.",
    ),
    AllowedOccurrence(
        path="docs/DECISIONS/0012-address-encoding-and-roundtrip.md",
        line=95,
        line_sha256="54e0a7d8d2fd9c6174e3b405e3c3fbb57962e81bed5ffca90052962ed06c28ed",
        phrase="safe",
        occurrence=1,
        rationale="Frozen Block 1.7a test-vector direction wording.",
    ),
    AllowedOccurrence(
        path="docs/DECISIONS/0018-signing-scope-enforcement-and-publication.md",
        line=162,
        line_sha256="c616f1a4dd13029603647ba8b6f6aebecaea8e81835e1511bd1855abf38c5464",
        phrase="safe",
        occurrence=1,
        rationale="Frozen sentence forbidding release notes from using the adjective.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=499,
        line_sha256="ffddc90a8034d71a5b1ac686fdd9bca0d2aae31e0237bc4aaaf98a00a301e1d6",
        phrase="guaranteed",
        occurrence=1,
        rationale="Dated 1.6b PBKDF2 platform-API note in the append-only log.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=594,
        line_sha256="06013b5013fa51aac397e1e0faf2f16c868d84f95cd5bb2d316589c6e029860c",
        phrase="safe",
        occurrence=1,
        rationale="Dated host-test scope note in the append-only log.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1382,
        line_sha256="a4678abbffdeaff5767b39f6b696e91c545f0ae6446b86e413330943dc3c67d4",
        phrase="secure",
        occurrence=1,
        rationale="Dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1382,
        line_sha256="a4678abbffdeaff5767b39f6b696e91c545f0ae6446b86e413330943dc3c67d4",
        phrase="safe",
        occurrence=1,
        rationale="Dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1382,
        line_sha256="a4678abbffdeaff5767b39f6b696e91c545f0ae6446b86e413330943dc3c67d4",
        phrase="hardened",
        occurrence=1,
        rationale="Dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1382,
        line_sha256="a4678abbffdeaff5767b39f6b696e91c545f0ae6446b86e413330943dc3c67d4",
        phrase="audited",
        occurrence=1,
        rationale="Dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1383,
        line_sha256="eb5439e8b8fe6825133fc6da007ece68026aa0244dc8ea2d8f7d349b2fb991d1",
        phrase="production-ready",
        occurrence=1,
        rationale="Dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1383,
        line_sha256="eb5439e8b8fe6825133fc6da007ece68026aa0244dc8ea2d8f7d349b2fb991d1",
        phrase="guaranteed",
        occurrence=1,
        rationale="Dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1383,
        line_sha256="eb5439e8b8fe6825133fc6da007ece68026aa0244dc8ea2d8f7d349b2fb991d1",
        phrase="cryptographically safe",
        occurrence=1,
        rationale="Dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1430,
        line_sha256="a4678abbffdeaff5767b39f6b696e91c545f0ae6446b86e413330943dc3c67d4",
        phrase="secure",
        occurrence=1,
        rationale="Second dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1430,
        line_sha256="a4678abbffdeaff5767b39f6b696e91c545f0ae6446b86e413330943dc3c67d4",
        phrase="safe",
        occurrence=1,
        rationale="Second dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1430,
        line_sha256="a4678abbffdeaff5767b39f6b696e91c545f0ae6446b86e413330943dc3c67d4",
        phrase="hardened",
        occurrence=1,
        rationale="Second dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1430,
        line_sha256="a4678abbffdeaff5767b39f6b696e91c545f0ae6446b86e413330943dc3c67d4",
        phrase="audited",
        occurrence=1,
        rationale="Second dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1431,
        line_sha256="f9dc97bc50bbf7996c20954c1865562c6ad6c5aa465ae88f4163d37663687b37",
        phrase="production-ready",
        occurrence=1,
        rationale="Second dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1431,
        line_sha256="f9dc97bc50bbf7996c20954c1865562c6ad6c5aa465ae88f4163d37663687b37",
        phrase="guaranteed",
        occurrence=1,
        rationale="Second dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1431,
        line_sha256="f9dc97bc50bbf7996c20954c1865562c6ad6c5aa465ae88f4163d37663687b37",
        phrase="cryptographically safe",
        occurrence=1,
        rationale="Second dated copy-review note quoting the restricted-claim list.",
    ),
    AllowedOccurrence(
        path="docs/PHASE_1_PLAN.md",
        line=1520,
        line_sha256="3734e748dfca2cead1ee717b4e3696a5d3abb9dc1c1c6bebced6c52b89d4ab15",
        phrase="safe",
        occurrence=1,
        rationale="Dated adaptive-icon layout note ('safe zone') in the append-only log.",
    ),
    AllowedOccurrence(
        path=(
            "crypto/src/androidMain/kotlin/org/sarmidev/kardano/crypto/internal/"
            "pbkdf2/Pbkdf2HmacSha512.android.kt"
        ),
        line=12,
        line_sha256="3a3933323de4a6e8783b5d2ec76b09203c903432ecb373ef71170814b6e83195",
        phrase="guaranteed",
        occurrence=1,
        rationale="Factual Android-platform-API availability note, not a product claim.",
    ),
    AllowedOccurrence(
        path=(
            "shared/src/commonTest/kotlin/org/sarmidev/kardano/playground/"
            "PlaygroundWalletPresenterTest.kt"
        ),
        line=138,
        line_sha256="d247a6158c9e5e4220d7d8f79cd2927053f8fd2c0f6964b1f5d7d418c27e21ae",
        phrase="safe",
        occurrence=1,
        rationale="Host-test scope comment, not a product claim.",
    ),
)

# (path, line, line_sha256, phrase, occurrence)
ALLOWED_OCCURRENCE_KEYS: frozenset[tuple[str, int, str, str, int]] = frozenset(
    (item.path, item.line, item.line_sha256, item.phrase, item.occurrence)
    for item in ALLOWED_OCCURRENCES
)


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


def line_content_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def parse_ls_files_z(raw: bytes) -> list[str]:
    """Split `git ls-files -z` output. Filenames may contain spaces or newlines."""
    return [part.decode("utf-8") for part in raw.split(b"\0") if part]


def is_scan_path(relative_path: str) -> bool:
    lowered = relative_path.lower()
    return any(lowered.endswith(suffix) for suffix in SCAN_SUFFIXES)


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


def apply_occurrence_allowlist(
    relative_path: str,
    line_no: int,
    line: str,
    phrase: str,
    occurrence: int,
    permitted: bool,
    reason: str,
    allowed_keys: frozenset[tuple[str, int, str, str, int]],
) -> tuple[bool, str]:
    if permitted:
        return permitted, reason
    key = (relative_path, line_no, line_content_hash(line), phrase, occurrence)
    if key in allowed_keys:
        return True, "allowed-occurrence"
    return False, reason


def scan_text(
    relative_path: str,
    text: str,
    allowed_keys: frozenset[tuple[str, int, str, str, int]] | None = None,
) -> list[Finding]:
    keys = ALLOWED_OCCURRENCE_KEYS if allowed_keys is None else allowed_keys
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        phrase_counts: dict[str, int] = {}
        for start, _end, phrase, permitted, reason in find_matches_in_text(line):
            if not permitted:
                phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
                occurrence = phrase_counts[phrase]
                permitted, reason = apply_occurrence_allowlist(
                    relative_path,
                    line_no,
                    line,
                    phrase,
                    occurrence,
                    permitted,
                    reason,
                    keys,
                )
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


def scan_paths(
    root: Path,
    relative_paths: list[str],
    allowed_keys: frozenset[tuple[str, int, str, str, int]] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    for relative in relative_paths:
        if is_excluded(relative):
            continue
        path = root / relative
        text = path.read_text(encoding="utf-8")
        findings.extend(scan_text(relative, text, allowed_keys=allowed_keys))
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
