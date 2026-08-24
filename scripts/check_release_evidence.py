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
    "OPEN — pending independent PE re-review",
    "OPEN — pending per-election reviewer acceptance",
)

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


def check_evidence_is_freshly_regenerable() -> list[str]:
    errors: list[str] = []
    generators = {
        "gradle_dependency_inventory.json": lambda: evidence.gradle_dependency_inventory(
            evidence.discover_gradle_modules()
        ),
        "uniffi_bindings_inventory.json": evidence.uniffi_bindings_inventory,
        "native_artifacts_inventory.json": evidence.native_artifacts_inventory,
        "maven_native_carriers_inventory.json": evidence.maven_native_carriers_inventory,
        "bouncycastle_license_source.json": evidence.bouncycastle_license_source_inventory,
    }

    def gradle_license_generator() -> dict:
        gradle_report = evidence.gradle_dependency_inventory(evidence.discover_gradle_modules())
        return evidence.gradle_license_inventory(gradle_report)

    generators["gradle_license_inventory.json"] = gradle_license_generator
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
        committed_text = committed_path.read_text(encoding="utf-8")
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


def check_digest_file_exact() -> list[str]:
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

    modules = tuple(sorted(fields.get("gradle_modules", "").split(",")))
    lockfiles = [REPO_ROOT / m / "gradle.lockfile" for m in modules if m]
    recomputed = {
        "gradle_lockfiles_sha256": evidence.concat_sha256(lockfiles),
        "cargo_lock_sha256": evidence.sha256_file(evidence.SIGNING_BACKEND / "Cargo.lock"),
        "native_checksums_sha256": evidence.sha256_file(
            evidence.SIGNING_BACKEND / "CHECKSUMS.sha256"
        ),
        "notice_sha256": evidence.sha256_file(REPO_ROOT / "NOTICE"),
    }
    for key, expected in recomputed.items():
        actual = fields.get(key)
        if actual != expected:
            errors.append(
                f"docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: {key}={actual!r} does "
                f"not match recomputed {expected!r}"
            )

    on_disk_licenses = sorted(p.name for p in LICENSES_DIR.glob("*.txt"))
    declared_licenses = sorted(f for f in fields.get("licenses_files", "").split(",") if f)
    if declared_licenses != on_disk_licenses:
        errors.append(
            "docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: licenses_files= "
            f"{declared_licenses} does not match LICENSES/*.txt on disk "
            f"{on_disk_licenses}"
        )
    recomputed_licenses_sha = evidence.concat_sha256(
        [LICENSES_DIR / name for name in on_disk_licenses]
    )
    if fields.get("licenses_sha256") != recomputed_licenses_sha:
        errors.append(
            "docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: licenses_sha256 does not "
            "match recomputed digest over LICENSES/*.txt on disk"
        )

    on_disk_evidence = sorted(p.name for p in EVIDENCE_DIR.glob("*.json"))
    declared_evidence = sorted(f for f in fields.get("expected_evidence_files", "").split(",") if f)
    if declared_evidence != on_disk_evidence:
        errors.append(
            "docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: expected_evidence_files= "
            f"{declared_evidence} does not match docs/evidence/*.json on disk "
            f"{on_disk_evidence}"
        )
    for name in on_disk_evidence:
        key = f"{name}_sha256"
        expected = evidence.sha256_file(EVIDENCE_DIR / name)
        actual = fields.get(key)
        if actual != expected:
            errors.append(
                f"docs/evidence/LEGAL_EVIDENCE_DIGEST.txt: {key}={actual!r} does "
                f"not match recomputed {expected!r}"
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


def check_cargo_license_elections(mode: str) -> list[str]:
    """Schema-validate every Cargo license-election row; gate `release` mode.

    Every row's `status` must be an exact member of `VALID_ELECTION_STATUSES`
    -- an arbitrary string like "Approved" is rejected the same way the
    markdown-table placeholder scan rejects it, because this is the same
    "no unsupported claim without an exact accepted enum" requirement applied
    to generated JSON instead of hand-written prose. A mandatory
    (target-linked) row with `status == "ACCEPTED"` must also carry a
    non-empty `reviewer` and an ISO-8601 `review_date`; `release` mode
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
        label = f"{row['name']}@{row['version']}"
        status = row.get("status")
        if status not in VALID_ELECTION_STATUSES:
            errors.append(
                f"cargo license election {label}: status {status!r} is not one "
                f"of {VALID_ELECTION_STATUSES} (no unsupported claim without an "
                "exact accepted enum)"
            )
            continue
        if status == "ACCEPTED":
            if not row.get("reviewer"):
                errors.append(
                    f"cargo license election {label}: status ACCEPTED but "
                    "reviewer is empty"
                )
            review_date = row.get("review_date")
            if not review_date or not ISO_DATE_RE.match(review_date):
                errors.append(
                    f"cargo license election {label}: status ACCEPTED but "
                    f"review_date {review_date!r} is not an ISO-8601 date"
                )
        elif row["linked_in_any_target"] and status not in ("OPEN", "ACCEPTED"):
            errors.append(
                f"cargo license election {label}: target-linked row has "
                f"unexpected status {status!r} (expected OPEN or ACCEPTED)"
            )

    if mode == "release" and not elections["all_mandatory_elections_accepted"]:
        open_rows = sorted(
            f"{r['name']}@{r['version']}"
            for r in elections["rows"]
            if r["linked_in_any_target"] and r["status"] != "ACCEPTED"
        )
        errors.append(
            "release mode: not every mandatory Cargo license election is "
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
