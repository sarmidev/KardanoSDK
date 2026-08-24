#!/usr/bin/env python3
"""Release-evidence checker for the Prompt 7 legal-evidence packet.

Two modes (see `--mode`):

- `ci-structural` (default): the packet may still contain named, falsifiable
  open gates (one of `ALLOWED_OPEN_GATE_MARKERS`); every other mandatory
  field/table cell must be non-empty and free of generic or lowercase
  placeholders. This is what CI runs on every push; it can pass while the
  packet still has open counsel/upstream gates.
- `release`: additionally fails if ANY `ALLOWED_OPEN_GATE_MARKERS` string is
  still present anywhere in `docs/LEGAL_REVIEW.md`. By design, this mode
  fails today and will keep failing until an actual reviewer resolves every
  gate; it exists so a human can ask "is this packet release-clean" without
  reading the whole document, not to ever silently pass.

Fails closed (either mode) on any of:

1. NOTICE (and LICENSES/README.md) reference only license files that exist
   under LICENSES/, and every committed LICENSES/*.txt is cited by NOTICE.
2. The committed native-artifact evidence
   (docs/evidence/native_artifacts_inventory.json) matches
   crypto-signing-backend/CHECKSUMS.sha256 exactly (same paths, same count,
   same SHA-256 as the files on disk) -- no extra, missing, or stale row --
   and every native binary file tracked under crypto-signing-backend/src/ is
   one of those 9 rows (a newly added, uninventoried native binary fails).
3. Every generated evidence file under docs/evidence/, and the digest file,
   is byte-identical to what `scripts/generate_legal_evidence.py` produces
   right now from the current tracked tree (lock/graph state is
   deterministic and the committed copy is not stale). No committed
   docs/evidence/*.json file contains a duplicate JSON object key.
   One narrow, documented exception: on a host whose ACTUAL `rustc -vV` host
   triple (not the spoofable `platform` module) is not exactly
   `x86_64-unknown-linux-gnu`, a difference in `cargo_dependency_inventory.json`
   is tolerated ONLY if it is EXACTLY the single documented `errno@0.3.14`
   membership entry for that one target triple (see
   `LINUX_X86_64_TARGET_TRIPLE`/`_cargo_inventory_diff_is_known_errno_host_ambiguity`
   below for the exact package identity/paths/values this permits and
   nothing else -- an upstream Cargo/rustix build-script-cfg ambiguity, not a
   generator bug). On an actual linux/x86_64 host, and for every other byte
   of every evidence file on every host, comparison is always exact with no
   exception.
4. docs/evidence/LEGAL_EVIDENCE_DIGEST.txt's own named digests are
   byte-recomputed and compared, and its `licenses_files=`/
   `expected_evidence_files=` lines list exactly the files present on disk in
   LICENSES/ and docs/evidence/ -- no extra, no missing.
5. Every UniFFI-generated Kotlin binding file and every native binary file
   that `git ls-files` finds under `crypto-signing-backend/src/` is covered
   by the dynamic-discovery scan in `scripts/generate_legal_evidence.py`; a
   newly added file in an unexpected location fails rather than being
   silently invisible to the packet.
6. No symlink appears among the tracked files that back this packet
   (NOTICE, LICENSES/, docs/evidence/, native binaries, lockfiles,
   Cargo.lock, CHECKSUMS.sha256, the UniFFI binding files).
7. docs/LEGAL_REVIEW.md contains no unresolved generic placeholder token
   (TBD, TODO, FIXME, XXX, "PLACEHOLDER", "<insert", "[insert", case-
   insensitive), no blank required table cell, no table cell using a bare
   "open"/"pending" that is not one of `ALLOWED_OPEN_GATE_MARKERS` exactly,
   and no unsupported claim of "approved" outside a "not approved"/"not ...
   approval" disclaimer sentence.
8. docs/evidence/scope_binding.json's two-commit seal is independently
   verified against git history (not by regeneration): evidence_commit and
   subject_commit exist, subject_commit is evidence_commit's exact
   immediate parent, evidence_commit is an ancestor of current HEAD, and
   every sealed evidence file's current bytes match both the recorded
   digest and the actual bytes committed at evidence_commit's tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_legal_evidence as evidence  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
LICENSES_DIR = REPO_ROOT / "LICENSES"
NOTICE_PATH = REPO_ROOT / "NOTICE"
LEGAL_REVIEW_PATH = REPO_ROOT / "docs" / "LEGAL_REVIEW.md"
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence"

LICENSE_REFERENCE_RE = re.compile(r"LICENSES/([A-Za-z0-9._-]+\.txt)")

GENERIC_PLACEHOLDERS = (
    "tbd",
    "todo",
    "fixme",
    "xxx",
    "placeholder",
    "<insert",
    "[insert",
    "<counsel name>",
    "<reviewer name>",
    "lorem ipsum",
)

# The only strings LEGAL_REVIEW.md may use to mark a field as deliberately,
# currently unresolved and open (as opposed to "forgotten"). Every such gate
# must name the blocking external event so it is falsifiable. Matching is
# always exact-case: a lowercase "open" that is not one of these full strings
# is itself rejected as an unrecognized placeholder (see
# check_legal_review_placeholders).
ALLOWED_OPEN_GATE_MARKERS = (
    "OPEN — pending owner/counsel review",
    "OPEN — pending upstream hyperledger-identus/apollo issue #226",
    "OPEN — pending per-election reviewer acceptance",
)

# The independent PE (native-artifact structural) technical review of the
# Windows x86-64 signing-backend candidate DLL is COMPLETE as of commit
# c65a20a (see `git log --oneline c65a20a` / docs/HANDOFF.md Branch-Stack
# Status) -- it is intentionally NOT one of ALLOWED_OPEN_GATE_MARKERS above,
# so LEGAL_REVIEW.md may no longer describe it as an open gate. This is a
# narrow technical-review completion only: it is not a legal approval, does
# not promote the Windows candidate, and does not imply any DLL is
# distributed. The Windows candidate remains unpromoted/not-distributed
# solely because of the still-open upstream Identus issue #226 gate (and any
# separate manual/release decision), which IS still one of
# ALLOWED_OPEN_GATE_MARKERS above.
PE_TECHNICAL_REVIEW_COMPLETE_AT_COMMIT = "c65a20a"

NATIVE_BINARY_SUFFIXES = (".so", ".dylib", ".a", ".dll")


def run_git(*args: str) -> str:
    import subprocess

    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout


def run_git_ok(*args: str) -> bool:
    import subprocess

    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return result.returncode == 0


def run_git_bytes(*args: str) -> bytes:
    import subprocess

    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, check=True
    )
    return result.stdout


def git_tracked_files(*pathspecs: str) -> list[str]:
    out = run_git("ls-files", "-z", *pathspecs)
    return [p for p in out.split("\0") if p]


def git_symlinked_files(*pathspecs: str) -> list[str]:
    """Tracked files whose git file mode is 120000 (symlink), not disk state."""
    out = run_git("ls-files", "-s", "-z", *pathspecs)
    symlinks = []
    for entry in out.split("\0"):
        if not entry:
            continue
        mode_and_rest = entry.split(None, 1)
        if mode_and_rest and mode_and_rest[0] == "120000":
            # format: "<mode> <sha> <stage>\t<path>"
            path = entry.split("\t", 1)[-1]
            symlinks.append(path)
    return symlinks


def check_no_symlinks() -> list[str]:
    errors: list[str] = []
    watched = (
        "NOTICE",
        "LICENSES",
        "docs/evidence",
        "crypto-signing-backend/CHECKSUMS.sha256",
        "crypto-signing-backend/Cargo.lock",
        "crypto-signing-backend/src",
        "settings.gradle.kts",
    )
    for module_dir in sorted({REPO_ROOT / d for d in evidence.discover_gradle_modules()}):
        lockfile = module_dir / "gradle.lockfile"
        if lockfile.is_file():
            watched = watched + (str(lockfile.relative_to(REPO_ROOT)),)
    symlinks = git_symlinked_files(*watched)
    for path in sorted(symlinks):
        errors.append(f"tracked symlink is not allowed as an evidence input: {path}")
    return errors


def check_notice_license_references() -> list[str]:
    errors: list[str] = []
    if not NOTICE_PATH.is_file():
        return ["root NOTICE file is missing"]
    if not LICENSES_DIR.is_dir():
        return ["LICENSES/ directory is missing"]

    existing = {p.name for p in LICENSES_DIR.glob("*.txt")}
    if not existing:
        errors.append("LICENSES/ contains no *.txt license files")
    readme_path = LICENSES_DIR / "README.md"
    if not readme_path.is_file():
        errors.append("LICENSES/README.md is required and is missing")
    elif readme_path.is_symlink():
        errors.append("LICENSES/README.md must not be a symlink")

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

    # If any Gradle-runtime or Cargo target-linked package is MIT-only,
    # LICENSES/MIT.txt must exist and be referenced. This is the exact false
    # claim ("no MIT-only distributed component") the 2026-08-24 independent
    # review flagged; guard it structurally instead of trusting prose.
    try:
        gradle_report = evidence.gradle_dependency_inventory(evidence.discover_gradle_modules())
        gradle_license_report = evidence.gradle_license_inventory(gradle_report)
        cargo_report = evidence.cargo_dependency_inventory_per_target()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"could not evaluate MIT-only cross-check: {exc!r}")
        return errors
    any_mit_only = bool(gradle_license_report["mit_only_coordinates"]) or bool(
        cargo_report["mit_only_linked_packages"]
    )
    if any_mit_only and "MIT.txt" not in existing:
        errors.append(
            "at least one MIT-only Gradle-runtime or Cargo target-linked "
            "package exists but LICENSES/MIT.txt is missing"
        )
    return errors


LICENSES_README_TABLE_ROW_RE = re.compile(
    r"^\|\s*`([A-Za-z0-9._-]+\.txt)`\s*\|.*\|.*\|\s*`([0-9a-f]{64})`"
)


def check_licenses_readme_table_matches_files() -> list[str]:
    """`LICENSES/README.md`'s table is a checked summary, not free narration.

    A 2026-08-24 independent review found the table missing a row for
    `Unlicense.txt` (present on disk and cited by `NOTICE`, but silently
    absent from the README's own table) -- this asserts the table's file set
    and every declared SHA-256 are derived from, and stay in lockstep with,
    the actual committed LICENSES/*.txt bytes, so a future addition/removal/
    hash drift fails the checker instead of silently going stale.
    """
    errors: list[str] = []
    readme_path = LICENSES_DIR / "README.md"
    if not readme_path.is_file() or readme_path.is_symlink():
        return []  # reported by check_notice_license_references

    on_disk = sorted(p.name for p in LICENSES_DIR.glob("*.txt"))
    table_rows: dict[str, str] = {}
    for line in readme_path.read_text(encoding="utf-8").splitlines():
        match = LICENSES_README_TABLE_ROW_RE.match(line.strip())
        if match:
            name, declared_sha256 = match.groups()
            if name in table_rows:
                errors.append(f"LICENSES/README.md: duplicate table row for {name!r}")
            table_rows[name] = declared_sha256

    extra_in_table = sorted(set(table_rows) - set(on_disk))
    for name in extra_in_table:
        errors.append(
            f"LICENSES/README.md table cites {name!r}, which does not exist "
            "under LICENSES/*.txt"
        )
    missing_from_table = sorted(set(on_disk) - set(table_rows))
    for name in missing_from_table:
        errors.append(
            f"LICENSES/{name} exists but has no row in LICENSES/README.md's "
            "table (every committed license text must be listed there, not "
            "just cited by NOTICE)"
        )
    for name in sorted(set(table_rows) & set(on_disk)):
        actual = evidence.sha256_file(LICENSES_DIR / name)
        if table_rows[name] != actual:
            errors.append(
                f"LICENSES/README.md: table declares {name!r} sha256 "
                f"{table_rows[name]!r}, but the committed file's actual "
                f"sha256 is {actual!r}"
            )
    return errors


def check_native_inventory_matches_checksums() -> list[str]:
    errors: list[str] = []
    try:
        report = evidence.native_artifacts_inventory()
    except (FileNotFoundError, ValueError, evidence.EvidenceError) as exc:
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

    tracked_native_files = {
        p
        for p in git_tracked_files("crypto-signing-backend/src")
        if any(p.endswith(suffix) for suffix in NATIVE_BINARY_SUFFIXES)
    }
    inventoried_paths = {"crypto-signing-backend/" + row for row in checksum_rows}
    uninventoried = sorted(tracked_native_files - inventoried_paths)
    for path in uninventoried:
        errors.append(
            f"{path}: tracked native binary is not a row in "
            "crypto-signing-backend/CHECKSUMS.sha256 (new native binaries must "
            "be inventoried, not silently shipped)"
        )
    return errors


# scope_binding.json is deliberately NOT regenerated/compared here: its
# whole point is to bind an IMMUTABLE historical evidence_commit/
# subject_commit pair, which would be destroyed by silently rewriting it to
# whatever HEAD happens to be during a later check run. It is verified
# independently by check_scope_binding_seal() (git ancestry + byte-for-byte
# cross-check against `git show <evidence_commit>:<path>`), not by
# regeneration equality.
KNOWN_NON_REGENERABLE_EVIDENCE_FILES = {"scope_binding.json"}

# Empirically confirmed 2026-08-24 (Verify run 32744019867, job "Legal-evidence
# packet"): `cargo tree --locked --offline --target x86_64-unknown-linux-gnu
# -e normal` reports `errno@0.3.14` as reachable from this repository's
# aarch64-apple-darwin host (cross-evaluating that target's `[target.'cfg(...)']`
# sections), but NOT reachable when the identical command, same
# crypto-signing-backend/Cargo.lock, same pinned 1.97.0 toolchain, is run
# natively on an x86_64-unknown-linux-gnu host (ubuntu-latest CI). The
# difference traces to `rustix` v1.1.4's Cargo.toml gating its `errno`/
# `linux-raw-sys` dependency edges on a build-script-only custom cfg
# (`rustix_use_libc`) that Cargo's `--filter-platform`/`--target` graph
# resolution cannot evaluate without actually running that build script for
# the real target -- which only happens on a *native* (host == target) run.
#
# A 2026-08-24 independent review found the first fix for this (blanket-
# stripping EVERY dict key literally equal to this triple, anywhere in the
# payload) far too broad: it would have silently hidden a genuine, unrelated
# regression in this target's membership for any OTHER package, or a
# corrupted/dropped triple slice entirely. The rule below is narrowed to
# permit ONLY the exact, single, documented difference: `errno`'s own
# package entry (matched by name+version+source+cargo_lock_checksum, not by
# name alone) either has or lacks a `"x86_64-unknown-linux-gnu": '
# '["linked_into_compiled_artifact"]` key in its own `membership` dict, and
# `membership_by_target["x86_64-unknown-linux-gnu"]["linked_into_compiled_artifact"]`
# either does or does not contain errno's exact package id -- consistently
# with each other. ANY other difference anywhere in the payload (a different
# package, a different target triple, a different field, a wrong version/
# source/checksum for errno itself, or an inconsistent/partial version of
# just this one difference) is NOT the known ambiguity and fails closed like
# any other staleness. This is the same class of problem Gap 6 (native
# carrier evidence) already solves for compiled artifacts: a foreign/
# cross-compiled resolution of this one target is not authoritative, and
# only a run on an actual matching host is -- so a real
# x86_64-unknown-linux-gnu host (see `_host_is_linux_x86_64()`, itself based
# on the actual `rustc -vV` host, not the spoofable `platform` module) gets
# NO exception at all: every byte must match exactly there.
LINUX_X86_64_TARGET_TRIPLE = "x86_64-unknown-linux-gnu"
KNOWN_ERRNO_HOST_AMBIGUOUS_PACKAGE_ID = (
    "registry+https://github.com/rust-lang/crates.io-index#errno@0.3.14"
)
KNOWN_ERRNO_NAME = "errno"
KNOWN_ERRNO_VERSION = "0.3.14"
KNOWN_ERRNO_SOURCE = "registry+https://github.com/rust-lang/crates.io-index"
KNOWN_ERRNO_CHECKSUM = "39cab71617ae0d63f51a36d69f866391735b51691dbda63cf6f96d042b63efeb"


def _rustc_host_triple() -> str | None:
    """The actual Rust host triple, parsed from `rustc -vV`'s `host:` line.

    Deliberately NOT `platform.system()`/`platform.machine()`: those report
    the Python interpreter's OS/CPU, which is spoofable in-process (as this
    module's own tests must do to exercise both branches) and does not
    actually prove which triple `cargo metadata`/`cargo tree` resolved
    against -- `rustc -vV`'s own `host:` line is the same toolchain binary
    this packet's generator already shells out to via `cargo`, so it is the
    one source of truth that cannot disagree with the Cargo invocations
    whose ambiguity this function exists to gate.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["rustc", "-vV"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    for line in result.stdout.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    return None


def _host_is_linux_x86_64() -> bool:
    return _rustc_host_triple() == LINUX_X86_64_TARGET_TRIPLE


def _find_package(payload: dict, name: str) -> dict | None:
    matches = [p for p in payload.get("packages", []) if p.get("name") == name]
    if len(matches) != 1:
        return None
    return matches[0]


def _cargo_inventory_diff_is_known_errno_host_ambiguity(
    fresh: dict, committed: dict
) -> tuple[bool, str]:
    """True only if `fresh` and `committed` differ EXACTLY per the documented
    rustix/errno build-script-cfg host ambiguity above -- never more
    broadly. Returns `(matches, detail)` so a caller can log/report exactly
    why not, rather than a bare boolean.
    """
    triple = LINUX_X86_64_TARGET_TRIPLE
    pkg_id = KNOWN_ERRNO_HOST_AMBIGUOUS_PACKAGE_ID

    fresh_errno = _find_package(fresh, KNOWN_ERRNO_NAME)
    committed_errno = _find_package(committed, KNOWN_ERRNO_NAME)
    if fresh_errno is None or committed_errno is None:
        return False, "expected exactly one 'errno' package on each side"
    for side_label, pkg in (("fresh", fresh_errno), ("committed", committed_errno)):
        if (
            pkg.get("version") != KNOWN_ERRNO_VERSION
            or pkg.get("source") != KNOWN_ERRNO_SOURCE
            or pkg.get("cargo_lock_checksum") != KNOWN_ERRNO_CHECKSUM
        ):
            return False, (
                f"{side_label} errno package does not match the known pinned "
                f"version={KNOWN_ERRNO_VERSION!r}/source={KNOWN_ERRNO_SOURCE!r}/"
                f"checksum={KNOWN_ERRNO_CHECKSUM!r}"
            )

    fresh_mbt = fresh.get("membership_by_target", {}).get(triple, {})
    committed_mbt = committed.get("membership_by_target", {}).get(triple, {})
    fresh_linked = fresh_mbt.get("linked_into_compiled_artifact")
    committed_linked = committed_mbt.get("linked_into_compiled_artifact")
    if not isinstance(fresh_linked, list) or not isinstance(committed_linked, list):
        return False, f"membership_by_target[{triple!r}].linked_into_compiled_artifact is missing/malformed"

    fresh_pkg_has_slice = triple in fresh_errno.get("membership", {})
    committed_pkg_has_slice = triple in committed_errno.get("membership", {})
    fresh_mbt_has_errno = pkg_id in fresh_linked
    committed_mbt_has_errno = pkg_id in committed_linked

    if fresh_pkg_has_slice != fresh_mbt_has_errno:
        return False, "fresh payload's own errno membership and membership_by_target disagree with each other"
    if committed_pkg_has_slice != committed_mbt_has_errno:
        return False, "committed payload's own errno membership and membership_by_target disagree with each other"
    if fresh_pkg_has_slice == committed_pkg_has_slice:
        return False, "no actual x86_64-unknown-linux-gnu errno membership difference exists between fresh and committed"
    if fresh_pkg_has_slice and fresh_errno["membership"][triple] != ["linked_into_compiled_artifact"]:
        return False, "fresh errno's x86_64-unknown-linux-gnu membership value is not exactly ['linked_into_compiled_artifact']"
    if committed_pkg_has_slice and committed_errno["membership"][triple] != ["linked_into_compiled_artifact"]:
        return False, "committed errno's x86_64-unknown-linux-gnu membership value is not exactly ['linked_into_compiled_artifact']"

    # Every other byte of the payload -- every other package, every other
    # target triple, every other field on the errno package itself -- must
    # be identical. Build a normalized copy of each side with ONLY the two
    # known-mutable errno slices removed, then require full equality.
    def normalized(payload: dict) -> dict:
        payload = json.loads(json.dumps(payload))
        mbt = payload.get("membership_by_target", {}).get(triple, {})
        linked = mbt.get("linked_into_compiled_artifact")
        if isinstance(linked, list):
            mbt["linked_into_compiled_artifact"] = sorted(x for x in linked if x != pkg_id)
        errno_pkg = _find_package(payload, KNOWN_ERRNO_NAME)
        if errno_pkg is not None:
            errno_pkg.get("membership", {}).pop(triple, None)
        return payload

    if normalized(fresh) != normalized(committed):
        return False, "byte differences remain outside the known errno@0.3.14 host-ambiguous slice"

    return True, (
        "matches exactly the documented errno@0.3.14 rustix build-script-cfg "
        f"host ambiguity (package id {pkg_id!r} present/absent consistently "
        f"in both membership_by_target[{triple!r}] and the package's own "
        "membership dict, nothing else differs)"
    )


def check_evidence_is_freshly_regenerable() -> list[str]:
    errors: list[str] = []
    generators = {
        "gradle_dependency_inventory.json": lambda: evidence.gradle_dependency_inventory(
            evidence.discover_gradle_modules()
        ),
        "uniffi_bindings_inventory.json": evidence.uniffi_bindings_inventory,
        "native_artifacts_inventory.json": evidence.native_artifacts_inventory,
        "bouncycastle_license_source.json": evidence.bouncycastle_license_source_inventory,
    }

    def gradle_license_generator() -> dict:
        gradle_report = evidence.gradle_dependency_inventory(evidence.discover_gradle_modules())
        return evidence.gradle_license_inventory(gradle_report)

    def maven_native_carriers_generator() -> dict:
        # Pass gradle_report through so a warm local Gradle cache also
        # re-runs the live-cache cross-check on every freshness check, not
        # only when scripts/generate_legal_evidence.py itself runs.
        gradle_report = evidence.gradle_dependency_inventory(evidence.discover_gradle_modules())
        return evidence.maven_native_carriers_inventory(gradle_report)

    generators["gradle_license_inventory.json"] = gradle_license_generator
    generators["maven_native_carriers_inventory.json"] = maven_native_carriers_generator
    generators["cargo_dependency_inventory.json"] = evidence.cargo_dependency_inventory_per_target

    committed_files = {p.name for p in EVIDENCE_DIR.glob("*.json")}
    expected_files = set(generators) | KNOWN_NON_REGENERABLE_EVIDENCE_FILES
    for extra in sorted(committed_files - expected_files):
        errors.append(
            f"docs/evidence/{extra} exists but is not one of this checker's "
            "known generators; either the generator forgot to write it, or an "
            "uninventoried file was added by hand"
        )

    for filename in KNOWN_NON_REGENERABLE_EVIDENCE_FILES:
        committed_path = EVIDENCE_DIR / filename
        if not committed_path.is_file():
            continue
        try:
            json.loads(
                committed_path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
        except ValueError as exc:
            errors.append(f"docs/evidence/{filename}: {exc}")

    for filename, generator in sorted(generators.items()):
        committed_path = EVIDENCE_DIR / filename
        if not committed_path.is_file():
            errors.append(f"docs/evidence/{filename} is missing")
            continue
        if committed_path.is_symlink():
            errors.append(f"docs/evidence/{filename} is a symlink, not a regular file")
            continue
        committed_raw = committed_path.read_bytes()
        if b"\r" in committed_raw:
            errors.append(
                f"docs/evidence/{filename}: CRLF or stray CR byte present (reject -- "
                "no newline normalization is performed anywhere in this comparison)"
            )
            continue
        committed_text = committed_raw.decode("utf-8")
        try:
            json.loads(committed_text, object_pairs_hook=_reject_duplicate_keys)
        except ValueError as exc:
            errors.append(f"docs/evidence/{filename}: {exc}")
            continue
        try:
            fresh_payload = generator()
        except Exception as exc:  # noqa: BLE001 - report and continue
            errors.append(f"{filename}: regeneration raised {exc!r}")
            continue
        fresh_text = json.dumps(fresh_payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        if fresh_text == committed_text:
            continue
        if filename == "cargo_dependency_inventory.json" and not _host_is_linux_x86_64():
            committed_payload = json.loads(committed_text, object_pairs_hook=_reject_duplicate_keys)
            matches, detail = _cargo_inventory_diff_is_known_errno_host_ambiguity(
                fresh_payload, committed_payload
            )
            if matches:
                print(
                    f"[note] docs/evidence/{filename}: this host's actual rustc "
                    f"target ({_rustc_host_triple()!r}) is not "
                    f"{LINUX_X86_64_TARGET_TRIPLE!r}, and the only difference from "
                    f"the committed file {detail} (see the comment above "
                    "LINUX_X86_64_TARGET_TRIPLE in this file). Re-run this checker "
                    "on an actual linux/x86_64 host (e.g. the legal-evidence-scan "
                    "CI job) for a fully authoritative result.",
                    file=sys.stderr,
                )
                continue
            errors.append(
                f"docs/evidence/{filename} is stale: regenerating it from the "
                "current tracked tree produces different bytes, and the "
                f"difference is not the one narrow, documented errno@0.3.14 host "
                f"ambiguity ({detail}). Run python3 scripts/generate_legal_evidence.py "
                "and commit the result."
            )
            continue
        errors.append(
            f"docs/evidence/{filename} is stale: regenerating it from the "
            "current tracked tree produces different bytes. Run "
            "python3 scripts/generate_legal_evidence.py and commit the result."
        )

    digest_path = EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt"
    if not digest_path.is_file():
        errors.append("docs/evidence/LEGAL_EVIDENCE_DIGEST.txt is missing")
    return errors


def check_evidence_tree_exact() -> list[str]:
    """Recursively enumerate the entire tracked docs/evidence/ tree.

    A 2026-08-24 independent review found the freshness check only globbed
    `docs/evidence/*.json` (non-recursive) plus the digest file by name --
    a stray extra file anywhere under a nested directory (e.g.
    docs/evidence/license-sources/) would be silently invisible. This walks
    every file under EVIDENCE_DIR, rejects any symlink (file or directory)
    anywhere in the tree, and compares the discovered set exactly against
    the one hand-maintained list of expected non-JSON evidence files below
    (the JSON files themselves are already checked file-by-file elsewhere).
    """
    errors: list[str] = []
    if not EVIDENCE_DIR.is_dir():
        return ["docs/evidence/ directory is missing"]

    expected_extra_files = {
        "license-sources/bouncycastle-licence-2026-08-24.html",
    }

    discovered: set[str] = set()
    for root, dirnames, filenames in os.walk(EVIDENCE_DIR):
        root_path = Path(root)
        for dirname in dirnames:
            if (root_path / dirname).is_symlink():
                errors.append(
                    f"docs/evidence/{(root_path / dirname).relative_to(EVIDENCE_DIR)}: "
                    "symlinked directory is not allowed under docs/evidence/"
                )
        for filename in filenames:
            file_path = root_path / filename
            rel = str(file_path.relative_to(EVIDENCE_DIR)).replace("\\", "/")
            if file_path.is_symlink():
                errors.append(f"docs/evidence/{rel}: symlink is not allowed under docs/evidence/")
                continue
            discovered.add(rel)

    expected_top_level = {"LEGAL_EVIDENCE_DIGEST.txt"} | {
        p.name for p in EVIDENCE_DIR.glob("*.json")
    }
    expected = expected_top_level | expected_extra_files
    extras = sorted(discovered - expected)
    missing = sorted(expected_extra_files - discovered)
    for path in extras:
        errors.append(
            f"docs/evidence/{path}: untracked/unexpected file under docs/evidence/ "
            "(nested extras fail the same as top-level extras)"
        )
    for path in missing:
        errors.append(f"docs/evidence/{path}: expected evidence file is missing")
    return errors


GIT_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
SCOPE_BINDING_REQUIRED_KEYS = {
    "note",
    "evidence_commit",
    "evidence_tree",
    "subject_commit",
    "subject_tree",
    "sealed_evidence_digests",
}


def check_scope_binding_seal() -> list[str]:
    """Verify the two-commit seal independently of regeneration.

    Unlike every other evidence file, `scope_binding.json` is NOT
    byte-compared against a fresh regeneration (that would always trivially
    "pass" by rewriting the binding to whatever HEAD is right now, defeating
    the point of a seal). Instead this checks, purely from already-committed
    git history plus current worktree bytes:

    - `evidence_commit`/`subject_commit` are real, existing commit objects.
    - `evidence_tree`/`subject_tree` are exactly those commits' own trees.
    - `subject_commit` is EXACTLY `evidence_commit`'s immediate parent (not
      merely some ancestor -- the evidence-content commit must directly
      follow the subject-source commit it inventories, with no intervening
      commit that could have silently changed the inventoried state).
    - `evidence_commit` is an ancestor of (or equal to) current HEAD (the
      seal cannot point at a commit not yet reachable from here).
    - Every sealed evidence file's CURRENT on-disk bytes match both the
      recorded `sealed_evidence_digests` entry AND the actual bytes
      committed at `evidence_commit`'s tree (`git show
      <evidence_commit>:docs/evidence/<name>`) -- so a later commit that
      edited an already-sealed evidence file without a re-seal is caught
      even though regeneration-equality checks elsewhere only ever compare
      against the CURRENT tracked tree, not the sealed historical one.
    """
    errors: list[str] = []
    path = EVIDENCE_DIR / "scope_binding.json"
    if not path.is_file():
        return ["docs/evidence/scope_binding.json is missing"]
    if path.is_symlink():
        return ["docs/evidence/scope_binding.json is a symlink, not a regular file"]

    try:
        binding = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except ValueError as exc:
        return [f"docs/evidence/scope_binding.json: {exc}"]
    if not isinstance(binding, dict):
        return ["docs/evidence/scope_binding.json: top level is not a JSON object"]

    if set(binding) != SCOPE_BINDING_REQUIRED_KEYS:
        return [
            "docs/evidence/scope_binding.json: unexpected key set "
            f"{sorted(binding)} (expected exactly {sorted(SCOPE_BINDING_REQUIRED_KEYS)})"
        ]

    for field in ("evidence_commit", "evidence_tree", "subject_commit", "subject_tree"):
        value = binding[field]
        if not isinstance(value, str) or not GIT_SHA1_RE.match(value):
            errors.append(
                f"docs/evidence/scope_binding.json: {field!r} is not a "
                f"40-hex-char git object id: {value!r}"
            )
    if errors:
        return errors

    evidence_commit = binding["evidence_commit"]
    evidence_tree = binding["evidence_tree"]
    subject_commit = binding["subject_commit"]
    subject_tree = binding["subject_tree"]

    for label, oid in (("evidence_commit", evidence_commit), ("subject_commit", subject_commit)):
        if not run_git_ok("cat-file", "-e", f"{oid}^{{commit}}"):
            errors.append(
                f"docs/evidence/scope_binding.json: {label} {oid} does not "
                "exist as a commit object in this repository"
            )
    if errors:
        return errors

    actual_evidence_tree = run_git("rev-parse", f"{evidence_commit}^{{tree}}").strip()
    if actual_evidence_tree != evidence_tree:
        errors.append(
            "docs/evidence/scope_binding.json: evidence_tree "
            f"{evidence_tree!r} does not match evidence_commit {evidence_commit}'s "
            f"actual tree {actual_evidence_tree!r}"
        )
    actual_subject_tree = run_git("rev-parse", f"{subject_commit}^{{tree}}").strip()
    if actual_subject_tree != subject_tree:
        errors.append(
            "docs/evidence/scope_binding.json: subject_tree "
            f"{subject_tree!r} does not match subject_commit {subject_commit}'s "
            f"actual tree {actual_subject_tree!r}"
        )

    if run_git_ok("rev-parse", "--verify", f"{evidence_commit}^"):
        actual_parent = run_git("rev-parse", f"{evidence_commit}^").strip()
    else:
        actual_parent = None
    if actual_parent != subject_commit:
        errors.append(
            "docs/evidence/scope_binding.json: subject_commit "
            f"{subject_commit!r} is not evidence_commit {evidence_commit}'s "
            f"immediate parent (actual parent: {actual_parent!r}) -- the "
            "evidence-content commit must directly follow the exact "
            "subject-source commit it inventories"
        )

    head = run_git("rev-parse", "HEAD").strip()
    if not run_git_ok("merge-base", "--is-ancestor", evidence_commit, head):
        errors.append(
            f"docs/evidence/scope_binding.json: evidence_commit {evidence_commit} "
            f"is not an ancestor of (or equal to) current HEAD {head}"
        )

    digests = binding["sealed_evidence_digests"]
    if not isinstance(digests, dict):
        return errors + [
            "docs/evidence/scope_binding.json: sealed_evidence_digests is not an object"
        ]
    expected_names = set(evidence.evidence_output_files())
    actual_names = set(digests)
    if actual_names != expected_names:
        errors.append(
            "docs/evidence/scope_binding.json: sealed_evidence_digests key set "
            f"{sorted(actual_names)} != expected {sorted(expected_names)}"
        )

    for name in sorted(expected_names & actual_names):
        digest = digests[name]
        if not isinstance(digest, str) or not SHA256_HEX_RE.match(digest):
            errors.append(
                f"docs/evidence/scope_binding.json: sealed_evidence_digests"
                f"[{name!r}] is not a 64-hex-char sha256: {digest!r}"
            )
            continue
        current_path = EVIDENCE_DIR / name
        if not current_path.is_file():
            errors.append(f"docs/evidence/{name} is missing (required by the sealed binding)")
            continue
        current_digest = evidence.sha256_file(current_path)
        if current_digest != digest:
            errors.append(
                f"docs/evidence/{name}: current bytes (sha256 {current_digest}) "
                f"do not match the sealed digest {digest} in scope_binding.json "
                "-- evidence content drifted after the seal without a re-seal"
            )
        try:
            committed_bytes = run_git_bytes("show", f"{evidence_commit}:docs/evidence/{name}")
        except Exception:  # noqa: BLE001
            errors.append(
                f"docs/evidence/{name}: not found at evidence_commit "
                f"{evidence_commit}'s tree (git show failed)"
            )
            continue
        committed_digest = hashlib.sha256(committed_bytes).hexdigest()
        if committed_digest != digest:
            errors.append(
                f"docs/evidence/{name}: sha256 at evidence_commit "
                f"({committed_digest}) does not match the sealed digest "
                f"{digest} in scope_binding.json"
            )

    return errors


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    seen: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate JSON object key {key!r}")
        seen[key] = value
    return seen


DIGEST_LINE_RE = re.compile(r"^([a-zA-Z0-9_.]+)=(.*)$")
DIGEST_SHA256_VALUE_RE = re.compile(r"^[0-9a-f]{64}$")


def check_digest_file_exact() -> list[str]:
    """Byte-exact, schema-exact recomputation of `LEGAL_EVIDENCE_DIGEST.txt`.

    Reads the committed file as raw bytes (never through `Path.read_text()`,
    which silently applies universal-newline translation and would defeat
    the CRLF/stray-CR rejection below) and recomputes its entire expected
    content via `evidence.digest_file_lines()` -- the SAME pure builder
    `scripts/generate_legal_evidence.py` itself uses to write this file, so
    key SET, key ORDER, comment lines, and every value are all checked
    against one live source of truth rather than a second, independently
    maintained field-by-field recomputation that could drift from the
    generator. `gradle_modules=` is cross-checked against modules
    dynamically discovered from `settings.gradle.kts` (not merely
    self-consistent with its own declared hash).
    """
    digest_path = EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt"
    if not digest_path.is_file():
        return []  # already reported by check_evidence_is_freshly_regenerable
    if digest_path.is_symlink():
        return ["docs/evidence/LEGAL_EVIDENCE_DIGEST.txt is a symlink"]

    raw = digest_path.read_bytes()
    if b"\r" in raw:
        return ["docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: CRLF byte present (reject)"]

    fields: dict[str, str] = {}
    for lineno, line in enumerate(raw.decode("utf-8").split("\n"), start=1):
        if not line or line.startswith("#"):
            continue
        match = DIGEST_LINE_RE.match(line)
        if not match:
            return [f"docs/evidence/LEGAL_EVIDENCE_DIGEST.txt:{lineno}: malformed line: {line!r}"]
        key = match.group(1)
        if key in fields:
            return [f"docs/evidence/LEGAL_EVIDENCE_DIGEST.txt:{lineno}: duplicate key {key!r}"]
        fields[key] = match.group(2)

    errors: list[str] = []

    try:
        discovered_modules = evidence.discover_gradle_modules()
    except evidence.EvidenceError as exc:
        return [f"could not discover Gradle modules to recompute LEGAL_EVIDENCE_DIGEST.txt: {exc}"]

    declared_modules = [m for m in fields.get("gradle_modules", "").split(",") if m]
    if declared_modules != sorted(discovered_modules):
        errors.append(
            "docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: gradle_modules= "
            f"{declared_modules} does not match modules dynamically discovered "
            f"from settings.gradle.kts {sorted(discovered_modules)}"
        )

    for key, value in fields.items():
        if key.endswith("_sha256") and not DIGEST_SHA256_VALUE_RE.match(value):
            errors.append(
                f"docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: {key}={value!r} is not "
                "a 64-hex-char lowercase SHA-256 value"
            )

    on_disk_evidence = sorted(p.name for p in EVIDENCE_DIR.glob("*.json"))
    generated = {name: EVIDENCE_DIR / name for name in on_disk_evidence}
    try:
        expected_lines = evidence.digest_file_lines(discovered_modules, generated)
    except (evidence.EvidenceError, FileNotFoundError) as exc:
        errors.append(f"could not recompute LEGAL_EVIDENCE_DIGEST.txt: {exc}")
        return errors

    expected_fields: dict[str, str] = {}
    for eline in expected_lines:
        match = DIGEST_LINE_RE.match(eline)
        if match:
            expected_fields[match.group(1)] = match.group(2)

    extra_keys = sorted(set(fields) - set(expected_fields))
    missing_keys = sorted(set(expected_fields) - set(fields))
    for key in extra_keys:
        errors.append(
            f"docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: unexpected/extra key "
            f"{key!r} (not part of the exact schema derived from the current "
            "evidence scope -- no ad hoc keys are permitted)"
        )
    for key in missing_keys:
        errors.append(
            f"docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: missing expected key {key!r}"
        )
    for key in sorted(set(fields) & set(expected_fields)):
        if fields[key] != expected_fields[key]:
            errors.append(
                f"docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: {key}={fields[key]!r} "
                f"does not match recomputed {expected_fields[key]!r}"
            )

    if not errors:
        expected_bytes = ("\n".join(expected_lines) + "\n").encode("utf-8")
        if raw != expected_bytes:
            errors.append(
                "docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: every individual key/"
                "value matched, but the file's raw bytes do not exactly match "
                "deterministic recomputation (comment-line placement or key "
                "order differs -- no reordering or extra comments are "
                "permitted; run python3 scripts/generate_legal_evidence.py "
                "and commit the result)"
            )
    return errors


def check_uniffi_and_native_scope_has_no_orphans() -> list[str]:
    """Anything matching the shape of generated evidence must be discovered."""
    errors: list[str] = []
    signing_backend_files = git_tracked_files("crypto-signing-backend/src")
    binding_name_re = re.compile(r"kardano_ed25519_bip32_signing(\.\w+)?\.kt$")
    discovered = set(evidence.discover_uniffi_generated_files())
    for path in signing_backend_files:
        rel = path[len("crypto-signing-backend/") :]
        if binding_name_re.search(path) and rel not in discovered:
            errors.append(
                f"crypto-signing-backend/{rel}: looks like a generated UniFFI "
                "binding file but was not found by discover_uniffi_generated_files() "
                "-- add its source set to UNIFFI_SOURCE_SETS or move it"
            )

    declared_modules = set(evidence.discover_gradle_modules())
    for entry in sorted(REPO_ROOT.iterdir()):
        if not entry.is_dir():
            continue
        if (entry / "gradle.lockfile").is_file() and entry.name not in declared_modules:
            errors.append(
                f"{entry.name}/gradle.lockfile exists but '{entry.name}' is not "
                "included in settings.gradle.kts (or discovery missed it)"
            )
    return errors


ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_ELECTION_STATUSES = ("OPEN", "ACCEPTED", "NOT_APPLICABLE")


def _check_election_status_schema(
    label: str, status: object, reviewer: object, review_date: object
) -> list[str]:
    """Shared OPEN/ACCEPTED/NOT_APPLICABLE + reviewer/ISO-date schema check.

    Used for both a Cargo OR-election row and a Cargo AND-required
    component's own acceptance entry (and, symmetrically, a Gradle
    election row) -- the same "no unsupported claim without an exact
    accepted enum" requirement applies to all three shapes.
    """
    errors: list[str] = []
    if status not in VALID_ELECTION_STATUSES:
        errors.append(
            f"{label}: status {status!r} is not one of "
            f"{VALID_ELECTION_STATUSES} (no unsupported claim without an "
            "exact accepted enum)"
        )
        return errors
    if status == "ACCEPTED":
        if not reviewer:
            errors.append(f"{label}: status ACCEPTED but reviewer is empty")
        if not isinstance(review_date, str) or not ISO_DATE_RE.match(review_date):
            errors.append(
                f"{label}: status ACCEPTED but review_date {review_date!r} "
                "is not an ISO-8601 date"
            )
    return errors


def _check_proposed_election_is_a_real_option(
    label: str, status: object, proposed_election: object, or_election_options: list
) -> list[str]:
    """`release` mode: an ACCEPTED OR-election's chosen value must be exactly
    one of its own row's `or_election_options` -- no missing, no unknown
    value, and no accepting a package (e.g. `memchr`) that has deliberately
    proposed no election at all (`proposed_election: None`)."""
    if status != "ACCEPTED" or not or_election_options:
        return []
    if proposed_election not in or_election_options:
        return [
            f"{label}: status ACCEPTED but proposed_election "
            f"{proposed_election!r} is not exactly one of its own "
            f"or_election_options {or_election_options!r} (no missing/unknown "
            "election accepted)"
        ]
    return []


def check_cargo_license_elections(mode: str) -> list[str]:
    """Schema-validate every Cargo license-election row; gate `release` mode.

    Every row's `status` must be an exact member of `VALID_ELECTION_STATUSES`
    -- an arbitrary string like "Approved" is rejected the same way the
    markdown-table placeholder scan rejects it, because this is the same
    "no unsupported claim without an exact accepted enum" requirement applied
    to generated JSON instead of hand-written prose. A mandatory
    (target-linked) row with `status == "ACCEPTED"` must also carry a
    non-empty `reviewer`, an ISO-8601 `review_date`, and a `proposed_election`
    that is exactly one of its own `or_election_options` (see
    `_check_proposed_election_is_a_real_option`). Every one of the row's
    `and_component_acceptance` entries is validated the same way,
    independently of the row's own OR-election status -- accepting the OR
    side never implicitly accepts an AND-required component. `release` mode
    additionally fails while `all_mandatory_elections_accepted` is not
    exactly `True`.
    """
    errors: list[str] = []
    try:
        report = evidence.cargo_dependency_inventory_per_target()
    except Exception as exc:  # noqa: BLE001
        return [f"could not evaluate cargo license elections: {exc!r}"]

    elections = report.get("license_elections")
    if elections is None:
        return ["cargo_dependency_inventory.json has no 'license_elections' section"]

    for row in elections["rows"]:
        label = f"cargo license election {row['name']}@{row['version']}"
        status = row.get("status")
        errors.extend(
            _check_election_status_schema(label, status, row.get("reviewer"), row.get("review_date"))
        )
        if status in VALID_ELECTION_STATUSES:
            errors.extend(
                _check_proposed_election_is_a_real_option(
                    label, status, row.get("proposed_election"), row.get("or_election_options") or []
                )
            )
            if status not in ("OPEN", "ACCEPTED") and row["linked_in_any_target"]:
                errors.append(
                    f"{label}: target-linked row has unexpected status "
                    f"{status!r} (expected OPEN or ACCEPTED)"
                )
        for component_entry in row.get("and_component_acceptance", []):
            component_label = f"{label} AND-component {component_entry['component']!r}"
            errors.extend(
                _check_election_status_schema(
                    component_label,
                    component_entry.get("status"),
                    component_entry.get("reviewer"),
                    component_entry.get("review_date"),
                )
            )

    if mode == "release" and not elections["all_mandatory_elections_accepted"]:
        open_rows = sorted(
            f"{r['name']}@{r['version']}"
            for r in elections["rows"]
            if r["linked_in_any_target"] and r["status"] != "ACCEPTED"
        )
        open_and_components = sorted(
            f"{r['name']}@{r['version']}::{c['component']}"
            for r in elections["rows"]
            if r["linked_in_any_target"]
            for c in r.get("and_component_acceptance", [])
            if c["status"] != "ACCEPTED"
        )
        detail = []
        if open_rows:
            detail.append(f"OR elections not accepted: {open_rows}")
        if open_and_components:
            detail.append(f"AND components not accepted: {open_and_components}")
        errors.append(
            "release mode: not every mandatory Cargo license election is "
            f"ACCEPTED ({'; '.join(detail)})"
        )
    return errors


def check_gradle_license_elections(mode: str) -> list[str]:
    """Schema-validate every Gradle license-election row (e.g. JNA); gate
    `release` mode. Mirrors `check_cargo_license_elections` exactly: an
    exact `VALID_ELECTION_STATUSES` enum, ACCEPTED requires a non-empty
    reviewer and an ISO-8601 review_date, an ACCEPTED row's
    proposed_election must be exactly one of its own or_election_options,
    and `release` mode fails while `all_mandatory_elections_accepted` is
    not exactly `True`.
    """
    errors: list[str] = []
    try:
        gradle_report = evidence.gradle_dependency_inventory(evidence.discover_gradle_modules())
        report = evidence.gradle_license_inventory(gradle_report)
    except Exception as exc:  # noqa: BLE001
        return [f"could not evaluate gradle license elections: {exc!r}"]

    elections = report.get("license_elections")
    if elections is None:
        return ["gradle_license_inventory.json has no 'license_elections' section"]

    for row in elections["rows"]:
        label = f"gradle license election {row['coordinate']}"
        status = row.get("status")
        errors.extend(
            _check_election_status_schema(label, status, row.get("reviewer"), row.get("review_date"))
        )
        if status in VALID_ELECTION_STATUSES:
            errors.extend(
                _check_proposed_election_is_a_real_option(
                    label, status, row.get("proposed_election"), row.get("or_election_options") or []
                )
            )

    if mode == "release" and not elections["all_mandatory_elections_accepted"]:
        open_rows = sorted(
            r["coordinate"] for r in elections["rows"] if r["status"] != "ACCEPTED"
        )
        errors.append(
            "release mode: not every mandatory Gradle license election is "
            f"ACCEPTED: {open_rows}"
        )
    return errors


TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")


def check_legal_review_placeholders(mode: str) -> list[str]:
    errors: list[str] = []
    if not LEGAL_REVIEW_PATH.is_file():
        return ["docs/LEGAL_REVIEW.md is missing"]
    text = LEGAL_REVIEW_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()

    for lineno, line in enumerate(lines, start=1):
        lowered = line.lower()
        for token in GENERIC_PLACEHOLDERS:
            if token in lowered:
                errors.append(
                    f"docs/LEGAL_REVIEW.md:{lineno}: generic placeholder "
                    f"{token!r} is not allowed (case-insensitive match); use "
                    "one of ALLOWED_OPEN_GATE_MARKERS to mark a deliberately "
                    "open field, or fill in the real value"
                )

    approved_re = re.compile(r"approved", re.IGNORECASE)
    for lineno, line in enumerate(lines, start=1):
        for match in approved_re.finditer(line):
            preceding = line[max(0, match.start() - 4) : match.start()].lower()
            if "not " in preceding:
                continue
            errors.append(
                f"docs/LEGAL_REVIEW.md:{lineno}: unsupported claim containing "
                "'approved' (this packet never approves a release); rephrase "
                "as a disclaimer ('not ... approval') or remove"
            )

    for lineno, line in enumerate(lines, start=1):
        match = TABLE_ROW_RE.match(line)
        if not match:
            continue
        cells = [c.strip() for c in match.group(1).split("|")]
        if all(re.fullmatch(r"-+", c) for c in cells if c):
            continue  # header separator row
        if len(cells) < 2:
            continue  # not a data row (rare malformed table edge, ignored)
        for cell in cells:
            if re.fullmatch(r"-{2,}", cell):
                continue
            if cell == "":
                errors.append(
                    f"docs/LEGAL_REVIEW.md:{lineno}: blank required table cell "
                    "(use an em dash '—' for 'not applicable', or one of "
                    "ALLOWED_OPEN_GATE_MARKERS for a deliberately open field -- "
                    "never leave a cell truly empty)"
                )
                continue
            has_open_or_pending = re.search(r"\b(open|pending)\b", cell, re.IGNORECASE)
            if has_open_or_pending and cell not in ALLOWED_OPEN_GATE_MARKERS:
                errors.append(
                    f"docs/LEGAL_REVIEW.md:{lineno}: table cell {cell!r} uses "
                    "'open'/'pending' but is not exactly one of "
                    "ALLOWED_OPEN_GATE_MARKERS"
                )

    if mode == "release":
        present_markers = sorted(
            {marker for marker in ALLOWED_OPEN_GATE_MARKERS if marker in text}
        )
        if present_markers:
            errors.append(
                "release mode: docs/LEGAL_REVIEW.md still contains open gate(s), "
                f"cannot be release-clean: {present_markers}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("ci-structural", "release"),
        default="ci-structural",
        help=(
            "ci-structural (default): allow named OPEN gates. release: also "
            "fail if any OPEN gate is still present (expected to fail today)."
        ),
    )
    args = parser.parse_args()

    checks = (
        ("no tracked symlinks in evidence inputs", check_no_symlinks),
        ("NOTICE / LICENSES cross-reference", check_notice_license_references),
        ("LICENSES/README.md table matches committed files", check_licenses_readme_table_matches_files),
        ("native inventory vs CHECKSUMS.sha256", check_native_inventory_matches_checksums),
        ("evidence freshness (deterministic regeneration)", check_evidence_is_freshly_regenerable),
        ("docs/evidence/ recursive tree has no extra/missing/symlinked files", check_evidence_tree_exact),
        ("LEGAL_EVIDENCE_DIGEST.txt exact recomputation", check_digest_file_exact),
        ("scope_binding.json two-commit seal (ancestry + byte cross-check)", check_scope_binding_seal),
        ("no uninventoried UniFFI/module scope drift", check_uniffi_and_native_scope_has_no_orphans),
        (
            f"Cargo license elections ({args.mode} mode)",
            lambda: check_cargo_license_elections(args.mode),
        ),
        (
            f"Gradle license elections ({args.mode} mode)",
            lambda: check_gradle_license_elections(args.mode),
        ),
        (
            f"LEGAL_REVIEW.md placeholder scan ({args.mode} mode)",
            lambda: check_legal_review_placeholders(args.mode),
        ),
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
    print(f"\nrelease-evidence check passed ({args.mode} mode)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
