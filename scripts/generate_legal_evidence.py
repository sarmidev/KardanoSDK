#!/usr/bin/env python3
"""Generate deterministic distribution-evidence inventories for Prompt 7.

This script never asserts a legal conclusion. It reads already-locked build
state (Gradle `*/gradle.lockfile`, `crypto-signing-backend/Cargo.lock` via
`cargo metadata --locked --offline` / `cargo tree --locked --offline`, the
committed UniFFI-generated Kotlin bindings,
`crypto-signing-backend/CHECKSUMS.sha256`, and -- for the Gradle license and
native-carrier inventories -- the local Gradle module cache when present) and
writes plain, reviewable JSON and text reports under `docs/evidence/`.
`--offline` means the local Cargo registry cache must already contain every
locked crate before this script runs; CI bootstraps that cache once via an
explicit `cargo fetch --locked` network call before ever invoking this
script (see `.github/workflows/verify.yml`), so Cargo resolution itself
never touches the network from inside this script and a generation run
that unexpectedly needed to is a hard failure, not a silent re-fetch.

This script has exactly one OTHER, separately pinned network dependency:
`java_class_version_evidence()`'s live verification of the real
`org.bouncycastle:bcprov-jdk18on:1.85.2` artifact bytes
(`fetch_and_verify_bcprov_jar()`), used whenever no already-verified local
copy is supplied via `--bcprov-jar` or the `KARDANO_LEGAL_EVIDENCE_BCPROV_JAR`
environment variable. A 2026-08-25 independent review found the prior
design (a live re-scan against the local Gradle module cache only, treated
as pure defense-in-depth) returns success with nothing actually checked at
all on this repo's own legal-evidence-scan CI job, whose Gradle cache is
always cold -- silently defeating the point of "live" evidence in exactly
the environment it is supposed to be authoritative in. The fetch's request
and response URLs are both required to be byte-identical to the one pinned
`https://` Maven Central URL (exact host, default port only, exact path,
no query/fragment/userinfo -- see `_validate_pinned_artifact_url()`); it
refuses EVERY HTTP redirect outright, even to the same host (see
`_NoRedirectHandler`); it requires the downloaded bytes' whole-archive
SHA-256 and size to match the committed, reviewed evidence before any
member is scanned; and it writes the verified bytes to a fresh destination
path using an exclusive, symlink-refusing create (`_create_exclusive_file()`)
rather than a plain truncating write. A missing explicit path, a failed
fetch, a redirect, a URL that does not exactly match, or any mismatch is a
hard failure, never a silent skip.

Determinism rules (checked by `scripts/check_release_evidence.py` and
`scripts/tests/test_generate_legal_evidence.py`):

- No absolute filesystem paths, timestamps, hostnames, or environment values
  are written to any generated file.
- All lists are sorted; all JSON is written with sorted keys and a trailing
  newline.
- Running this script twice against the same tracked tree AND the same local
  Gradle module cache state byte-for-byte reproduces every generated file.
  The Gradle license/native-carrier inventories are the one part of this
  packet that is *not* reproducible from the tracked tree alone -- see
  "network and cache dependency" in `docs/LEGAL_REVIEW.md` \u00a78 and the
  `resolution_method` field on each of those reports.

Scope discovery is dynamic, not a hand-maintained list:

- Gradle modules come from parsing `settings.gradle.kts`'s `include(...)`
  calls, not a static tuple.
- UniFFI-generated binding files are discovered by globbing the documented
  package path, not a hand-maintained file list.
- The native-artifact catalog is still a maintained table (platform/arch/
  provenance is not derivable from the files themselves), but every row is
  required to match `CHECKSUMS.sha256` exactly, and every row's discovered
  path must also appear in `git ls-files` under `crypto-signing-backend/src/`
  (see `check_new_native_binaries_are_inventoried` in
  `scripts/check_release_evidence.py`), so a newly added, uninventoried
  native binary fails the checker rather than silently passing.

Gradle configuration classification is a transparent, documented heuristic
over the *configuration names* recorded by Gradle dependency locking -- it is
not a `./gradlew dependencies` run (avoids requiring a full build here) and
it is not a license or legal classification. See `CONFIG_RULES` below.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import tomllib
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cargo_election_catalog  # noqa: E402
import license_catalog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNING_BACKEND = REPO_ROOT / "crypto-signing-backend"
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence"
SETTINGS_GRADLE = REPO_ROOT / "settings.gradle.kts"

GRADLE_USER_HOME = Path(os.environ.get("GRADLE_USER_HOME", str(Path.home() / ".gradle")))
GRADLE_MODULES2 = GRADLE_USER_HOME / "caches" / "modules-2" / "files-2.1"

# Explicit, non-silent override for `live_verify_java_class_version_evidence()`
# -- an already-verified local bcprov-jdk18on .jar path, set by a human
# (`--bcprov-jar`) or by CI after its own one-time fetch+verify bootstrap
# step (see `.github/workflows/verify.yml` and `fetch_and_verify_bcprov_jar()`
# below), so repeated invocations within one job reuse that SAME verified
# copy instead of re-fetching from Maven Central every time. Never consulted
# silently in place of a failure: an explicit path that does not exist, or
# whose bytes do not match the pinned evidence, is still a hard error.
BCPROV_JAR_PATH_ENV_VAR = "KARDANO_LEGAL_EVIDENCE_BCPROV_JAR"

INCLUDE_RE = re.compile(r'include\(\s*"(:[^"]+)"\s*\)')
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(RuntimeError):
    """Raised for any fail-closed evidence-generation problem."""


def reject_symlink(path: Path) -> None:
    if path.is_symlink():
        raise EvidenceError(f"refusing to read symlink as an evidence input: {path}")


def read_bytes_no_symlink(path: Path) -> bytes:
    reject_symlink(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return path.read_bytes()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(read_bytes_no_symlink(path))


# ---------------------------------------------------------------------------
# Dynamic Gradle module discovery
# ---------------------------------------------------------------------------


def discover_gradle_modules() -> tuple[str, ...]:
    reject_symlink(SETTINGS_GRADLE)
    text = SETTINGS_GRADLE.read_text(encoding="utf-8")
    modules = sorted({m.lstrip(":") for m in INCLUDE_RE.findall(text)})
    if not modules:
        raise EvidenceError("discovered zero Gradle modules from settings.gradle.kts")
    for module in modules:
        lockfile = REPO_ROOT / module / "gradle.lockfile"
        if not lockfile.is_file():
            raise EvidenceError(
                f"module '{module}' from settings.gradle.kts has no gradle.lockfile "
                "(run the Gradle dependency-locking task for it, or it should not be "
                "included in settings.gradle.kts)"
            )
    return tuple(modules)


# ---------------------------------------------------------------------------
# Gradle lockfile parsing and configuration classification (strict)
# ---------------------------------------------------------------------------

CONFIG_RULES: tuple[tuple[str, str], ...] = (
    ("_internal-unified-test-platform", "build-tooling"),
    ("LintChecks", "build-tooling"),
    ("lintPublish", "build-tooling"),
    ("ResolvableDependenciesMetadata", "build-tooling"),
    ("CompilationDependenciesMetadata", "build-tooling"),
    ("CompileKlibraries", "build-tooling"),
    ("CInterop", "build-tooling"),
    ("kotlinCompilerPluginClasspath", "build-tooling"),
    ("kotlinCompiler", "build-tooling"),
    ("kotlinBuildToolsApiClasspath", "build-tooling"),
    ("kotlinKlibCommonizerClasspath", "build-tooling"),
    ("kotlinNativeBundleConfiguration", "build-tooling"),
    ("kotlinNativeCompilerPluginClasspath", "build-tooling"),
    ("kotlinAbiValidationCompatClasspath", "build-tooling"),
    ("KotlinScriptDefExtensions", "build-tooling"),
    ("swiftExportClasspathResolvable", "build-tooling"),
    ("swiftPMDependencies", "build-tooling"),
    ("androidJacocoAnt", "build-tooling"),
    ("androidJdkImage", "build-tooling"),
    ("androidApis", "build-tooling"),
    ("annotationProcessor", "build-tooling"),
    ("ReverseMetadataValues", "build-tooling"),
    ("kotlin-extension", "build-tooling"),
    ("composeMappingProducerClasspath", "build-tooling"),
    ("androidTestUtil", "build-tooling"),
    ("coreLibraryDesugaring", "build-tooling"),
    ("composeHotReload", "build-tooling"),
    ("resolvableIosArm64CompilationApi", "build-tooling"),
    ("resolvableIosSimulatorArm64CompilationApi", "build-tooling"),
    ("FrameworkExport", "runtime"),
    ("Test", "test"),
    ("RuntimeClasspath", "runtime"),
    ("CompileClasspath", "source"),
    ("MainImplementationDependenciesMetadata", "source"),
    ("MainResolvableDependenciesMetadata", "build-tooling"),
    ("compileClasspath", "source"),
    ("runtimeClasspath", "runtime"),
)

BUCKETS = ("runtime", "source", "test", "build-tooling", "other")

LOCKFILE_LINE_RE = re.compile(r"^([^=\s#][^=]*)=([^\s]+)$")


def classify_configuration(config: str) -> str:
    for substring, bucket in CONFIG_RULES:
        if substring in config:
            return bucket
    return "other"


def parse_lockfile(path: Path) -> list[tuple[str, list[str]]]:
    reject_symlink(path)
    raw = read_bytes_no_symlink(path)
    if b"\r" in raw:
        raise EvidenceError(f"{path}: CRLF or stray CR byte in a Gradle lockfile (reject)")
    entries: list[tuple[str, list[str]]] = []
    seen_gavs: set[str] = set()
    for lineno, raw_line in enumerate(raw.decode("utf-8").split("\n"), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = LOCKFILE_LINE_RE.match(line)
        if not match:
            raise EvidenceError(f"{path}:{lineno}: malformed lockfile line: {line!r}")
        gav, configs_raw = match.group(1), match.group(2)
        if gav == "empty":
            # Gradle's own lockfile marker for configurations that resolved
            # with zero dependencies. Not a dependency coordinate.
            continue
        if gav in seen_gavs:
            raise EvidenceError(f"{path}:{lineno}: duplicate coordinate {gav!r}")
        seen_gavs.add(gav)
        configs = configs_raw.split(",")
        if len(configs) != len(set(configs)):
            raise EvidenceError(f"{path}:{lineno}: duplicate configuration name for {gav!r}")
        entries.append((gav, sorted(configs)))
    return entries


def classify_gav(configs: list[str]) -> str:
    buckets = {classify_configuration(c) for c in configs}
    non_tooling = buckets - {"build-tooling"}
    if not non_tooling:
        return "build-tooling"
    if "runtime" in non_tooling:
        return "runtime"
    if "source" in non_tooling:
        return "source"
    if non_tooling == {"test"}:
        return "test"
    return "other"


def gradle_dependency_inventory(modules: tuple[str, ...]) -> dict[str, Any]:
    inventory: dict[str, Any] = {}
    for module in modules:
        lockfile = REPO_ROOT / module / "gradle.lockfile"
        by_bucket: dict[str, list[str]] = {b: [] for b in BUCKETS}
        for gav, configs in parse_lockfile(lockfile):
            bucket = classify_gav(configs)
            by_bucket[bucket].append(gav)
        for bucket in by_bucket:
            by_bucket[bucket] = sorted(set(by_bucket[bucket]))
        inventory[module] = {
            "counts": {b: len(by_bucket[b]) for b in BUCKETS},
            "coordinates": by_bucket,
        }
    return {
        "method": (
            "Parsed from */gradle.lockfile (Gradle dependency locking, "
            "LockMode.STRICT), for modules discovered from settings.gradle.kts. "
            "Classification is a documented substring heuristic over Gradle "
            "configuration names, not a './gradlew dependencies' run. 'runtime' = "
            "reachable from a non-test *RuntimeClasspath or an iOS FrameworkExport "
            "configuration (shipped). 'source' = compile-only or "
            "*MainImplementationDependenciesMetadata. 'test' = every configuration "
            "for that coordinate is test-scoped. 'build-tooling' = Gradle/Kotlin/"
            "AGP/lint/codegen machinery, never shipped. Lockfile parsing is strict: "
            "CRLF, duplicate coordinates, duplicate configuration names, and "
            "malformed lines all fail generation rather than being silently "
            "accepted."
        ),
        "modules": inventory,
    }


# ---------------------------------------------------------------------------
# Gradle per-package license resolution (curated catalog + local POM cache)
# ---------------------------------------------------------------------------


def parse_gav(gav: str) -> tuple[str, str, str]:
    parts = gav.split(":")
    if len(parts) != 3:
        raise EvidenceError(f"unexpected coordinate shape (want group:artifact:version): {gav!r}")
    return parts[0], parts[1], parts[2]


def find_local_pom(group: str, artifact: str, version: str) -> Path | None:
    base = GRADLE_MODULES2 / group / artifact / version
    if not base.is_dir():
        return None
    expected_name = f"{artifact}-{version}.pom"
    candidates = sorted(base.glob(f"*/{expected_name}"))
    for candidate in candidates:
        if not candidate.is_symlink():
            return candidate
    return None


POM_LICENSE_NAME_RE = re.compile(
    r"<license>\s*<name>(.*?)</name>", re.IGNORECASE | re.DOTALL
)


def parse_pom_licenses(pom_path: Path) -> list[str]:
    reject_symlink(pom_path)
    text = pom_path.read_text(encoding="utf-8", errors="strict")
    names = [n.strip() for n in POM_LICENSE_NAME_RE.findall(text)]
    return names


def gradle_license_inventory(gradle_report: dict[str, Any]) -> dict[str, Any]:
    all_runtime_gavs: set[str] = set()
    for module_data in gradle_report["modules"].values():
        all_runtime_gavs.update(module_data["coordinates"]["runtime"])

    resolved: dict[str, Any] = {}
    unresolved: list[str] = []
    mit_only: list[str] = []

    for gav in sorted(all_runtime_gavs):
        group, artifact, version = parse_gav(gav)
        catalog_entry = license_catalog.lookup(group, artifact, version)
        if catalog_entry is not None:
            licenses = list(catalog_entry["licenses"])
            resolved[gav] = {
                "licenses": licenses,
                "election": catalog_entry.get("election"),
                "source": catalog_entry.get("source"),
                "resolution_method": catalog_entry.get("resolution_method", "curated-catalog"),
                "election_status": catalog_entry.get("election_status"),
                "election_reviewer": catalog_entry.get("election_reviewer"),
                "election_review_date": catalog_entry.get("election_review_date"),
            }
        else:
            # Defense-in-depth only: a genuinely new coordinate that has not
            # yet been added to scripts/license_catalog.py or harvested into
            # scripts/license_catalog_harvested.py (see
            # scripts/harvest_gradle_pom_licenses.py) still resolves here IF
            # this machine happens to have it in its local Gradle cache, but
            # this path is never required for a clean/CI resolution -- the
            # two catalogs above are complete for every coordinate currently
            # in any */gradle.lockfile (see the cold-cache tests in
            # scripts/tests/test_generate_legal_evidence.py).
            pom_path = find_local_pom(group, artifact, version)
            if pom_path is None:
                unresolved.append(gav)
                continue
            licenses = parse_pom_licenses(pom_path)
            if not licenses:
                unresolved.append(gav)
                continue
            resolved[gav] = {
                "licenses": licenses,
                "election": licenses[0] if len(licenses) > 1 else None,
                "source": None,
                "resolution_method": "live-local-gradle-pom-cache",
            }
        if len(resolved[gav]["licenses"]) == 1 and resolved[gav]["licenses"][0] in (
            "MIT",
            "MIT License",
        ):
            mit_only.append(gav)

    if unresolved:
        raise EvidenceError(
            "gradle_license_inventory: "
            f"{len(unresolved)} runtime coordinate(s) have no resolvable "
            "license from scripts/license_catalog.py (curated or harvested) "
            "and no local Gradle POM cache entry either -- add them to "
            "scripts/license_catalog.py or re-run "
            "scripts/harvest_gradle_pom_licenses.py, then regenerate. This "
            f"generator never silently ships an unresolved coordinate: {sorted(unresolved)}"
        )

    return {
        "method": (
            "Every coordinate is looked up first in "
            "scripts/license_catalog.GRADLE_LICENSE_CATALOG (a curated, dated, "
            "hand-reviewed catalog -- the only place a multi-license/election "
            "entry may live), then in "
            "scripts/license_catalog_harvested.HARVESTED_POM_LICENSE_CATALOG (a "
            "mechanically harvested, always-single-license catalog committed "
            "by scripts/harvest_gradle_pom_licenses.py so this generator does "
            "not need a pre-populated local Gradle cache to reproduce this "
            "report -- see docs/LEGAL_REVIEW.md \u00a71 and "
            "scripts/tests/test_generate_legal_evidence.py's cold-cache tests). "
            "A coordinate in neither catalog falls back to a live read of the "
            "local Gradle module cache "
            "(GRADLE_USER_HOME/caches/modules-2/files-2.1) as defense in depth "
            "only; this generator FAILS CLOSED (raises, does not write any "
            "evidence file) if any runtime coordinate is unresolved by all "
            "three paths -- it never records a silent 'unresolved' entry."
        ),
        "runtime_coordinate_count": len(all_runtime_gavs),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "resolved": resolved,
        "unresolved": sorted(unresolved),
        "mit_only_coordinates": sorted(mit_only),
        "license_elections": gradle_license_elections(resolved),
    }


def gradle_license_elections(resolved: dict[str, Any]) -> dict[str, Any]:
    """Every Gradle-runtime coordinate with more than one resolved license
    (a real disjunctive OR choice, e.g. `net.java.dev.jna:jna`) gets an
    explicit, catalog-backed election row here -- generated dynamically
    from whatever `resolved` (already-runtime-scoped, already-license-
    resolved) contains, not a hand-maintained count. A single-license
    coordinate has no election to make and never appears here (mirrors
    `scripts/generate_legal_evidence.py`'s `cargo_license_elections()` on
    the Cargo side, and the same 2026-08-24 independent-review finding that
    JNA's own election had a proposed value but no status/reviewer/date
    schema at all).
    """
    rows: list[dict[str, Any]] = []
    mandatory_count = 0
    accepted_count = 0
    for gav in sorted(resolved):
        entry = resolved[gav]
        licenses = entry["licenses"]
        if len(licenses) <= 1:
            continue
        mandatory_count += 1
        status = entry.get("election_status")
        if status == "ACCEPTED":
            accepted_count += 1
        rows.append(
            {
                "coordinate": gav,
                "licenses": list(licenses),
                "or_election_options": list(licenses),
                "proposed_election": entry.get("election"),
                "status": status,
                "reviewer": entry.get("election_reviewer"),
                "review_date": entry.get("election_review_date"),
            }
        )
    return {
        "method": (
            "Every resolved Gradle-runtime coordinate whose own POM lists more "
            "than one <license> (a real disjunctive choice, not a compound AND "
            "expression -- Maven POMs do not express AND-required licenses the "
            "way Cargo.toml's SPDX `license` field can) gets one row here, "
            "sourced from scripts/license_catalog.GRADLE_LICENSE_CATALOG's "
            "election_status/election_reviewer/election_review_date fields. "
            "status only ever becomes ACCEPTED by a human editing that catalog; "
            "this generator never sets it itself, and "
            "scripts/check_release_evidence.py's release mode fails while any "
            "row here is not ACCEPTED with a non-empty reviewer, an ISO-8601 "
            "review_date, and a proposed_election that is exactly one of the "
            "row's own or_election_options."
        ),
        "mandatory_row_count": mandatory_count,
        "accepted_count": accepted_count,
        "all_mandatory_elections_accepted": accepted_count == mandatory_count and mandatory_count > 0,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Cargo per-target-triple inventory
# ---------------------------------------------------------------------------

# (rustc target triple, committed artifact path it produces) for all 9 rows
# in crypto-signing-backend/CHECKSUMS.sha256.
CARGO_TARGET_TRIPLES: tuple[tuple[str, str], ...] = (
    ("aarch64-apple-darwin", "src/jvmMain/resources/darwin-aarch64/libkardano_ed25519_bip32_signing.dylib"),
    ("x86_64-apple-darwin", "src/jvmMain/resources/darwin-x86-64/libkardano_ed25519_bip32_signing.dylib"),
    ("aarch64-linux-android", "src/androidMain/jniLibs/arm64-v8a/libkardano_ed25519_bip32_signing.so"),
    ("armv7-linux-androideabi", "src/androidMain/jniLibs/armeabi-v7a/libkardano_ed25519_bip32_signing.so"),
    ("i686-linux-android", "src/androidMain/jniLibs/x86/libkardano_ed25519_bip32_signing.so"),
    ("x86_64-linux-android", "src/androidMain/jniLibs/x86_64/libkardano_ed25519_bip32_signing.so"),
    ("aarch64-apple-ios", "src/nativeInterop/libs/iosArm64/libkardano_ed25519_bip32_signing.a"),
    ("aarch64-apple-ios-sim", "src/nativeInterop/libs/iosSimulatorArm64/libkardano_ed25519_bip32_signing.a"),
    ("x86_64-unknown-linux-gnu", "src/jvmMain/resources/linux-x86-64/libkardano_ed25519_bip32_signing.so"),
)


def cargo_lock_checksums() -> dict[tuple[str, str], str | None]:
    lock_path = SIGNING_BACKEND / "Cargo.lock"
    reject_symlink(lock_path)
    data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], str | None] = {}
    for pkg in data.get("package", []):
        out[(pkg["name"], pkg["version"])] = pkg.get("checksum")
    return out


def run_cargo_metadata_for_triple(triple: str) -> dict[str, Any]:
    """Run `cargo metadata` against the already-fetched, already-locked registry cache.

    `--locked` refuses to re-resolve if Cargo.lock and Cargo.toml disagree;
    `--offline` additionally refuses to touch the network at all, so this
    call can only succeed against packages already present in the local
    registry cache (populated once, deliberately, by an explicit
    `cargo fetch --locked` bootstrap step -- see `.github/workflows/verify.yml`
    and docs/LEGAL_REVIEW.md's network-requirement note). A generation run
    that unexpectedly needed network access fails loudly here instead of
    silently fetching new data mid-generation.
    """
    lock_path = SIGNING_BACKEND / "Cargo.lock"
    before = sha256_file(lock_path)
    result = subprocess.run(
        [
            "cargo",
            "metadata",
            "--locked",
            "--offline",
            "--format-version",
            "1",
            "--filter-platform",
            triple,
        ],
        cwd=SIGNING_BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    after = sha256_file(lock_path)
    if before != after:
        raise EvidenceError(
            "cargo metadata --locked --offline mutated Cargo.lock "
            f"(before={before} after={after}); refusing generated evidence"
        )
    return json.loads(result.stdout)


TREE_LINE_PREFIX_RE = re.compile(r"^[\s\u2502\u251c\u2514\u2500]*")
TREE_LINE_MARKER_RE = re.compile(r"\s*\((?:\*|proc-macro)\)$")


def run_cargo_tree_name_versions(triple: str, edges: str) -> set[tuple[str, str]]:
    """Real, feature-activation-correct package set for one edge-kind filter.

    `cargo metadata`'s `resolve.nodes[].deps` unconditionally lists every
    dependency edge declared in Cargo.toml, INCLUDING optional dependencies
    gated behind a Cargo feature that is not actually active for this build
    (verified 2026-08-24: `uniffi`'s optional `uniffi_bindgen`/`askama`/
    `goblin`/`nom`/`weedle2` "bindgen CLI" dependency chain appears as a
    `deps` edge even though the `bindgen`/`cli` feature that would enable it
    is not in this crate's active feature set). `cargo tree`, by contrast,
    performs real feature resolution and only shows edges that are actually
    active for the given `--target`/edge-kind filter, so it is used here as
    the ground truth for "is this package reachable at all", while
    `cargo metadata` supplies per-package facts (license/version/source).
    """
    lock_path = SIGNING_BACKEND / "Cargo.lock"
    before = sha256_file(lock_path)
    result = subprocess.run(
        [
            "cargo",
            "tree",
            "--locked",
            "--offline",
            "--target",
            triple,
            "-e",
            edges,
            "--prefix",
            "none",
        ],
        cwd=SIGNING_BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    after = sha256_file(lock_path)
    if before != after:
        raise EvidenceError(
            "cargo tree --locked --offline mutated Cargo.lock "
            f"(before={before} after={after}); refusing generated evidence"
        )
    out: set[tuple[str, str]] = set()
    for line in result.stdout.splitlines():
        line = TREE_LINE_PREFIX_RE.sub("", line)
        line = TREE_LINE_MARKER_RE.sub("", line)
        parts = line.split()
        if len(parts) >= 2 and parts[1].startswith("v"):
            out.add((parts[0], parts[1][1:]))
    return out


def name_version_index(metadata: dict[str, Any]) -> dict[tuple[str, str], list[str]]:
    index: dict[tuple[str, str], list[str]] = {}
    for pkg in metadata["packages"]:
        index.setdefault((pkg["name"], pkg["version"]), []).append(pkg["id"])
    return index


def require_unambiguous_name_versions(
    name_version_to_ids: dict[tuple[str, str], list[str]], context: str
) -> None:
    duplicates = {key: ids for key, ids in name_version_to_ids.items() if len(ids) > 1}
    if duplicates:
        raise EvidenceError(
            f"{context}: ambiguous name+version across sources, cannot map "
            f"`cargo tree` output back to a package id unambiguously: "
            f"{sorted(duplicates)}"
        )


def classify_cargo_packages(
    metadata: dict[str, Any],
    real_normal: set[str],
    real_normal_and_build: set[str],
    *,
    dev_only: set[str] | None = None,
) -> dict[str, Any]:
    """Pure classification: takes already-resolved ground-truth ID sets.

    `real_normal` and `real_normal_and_build` must already be package IDs
    (not name/version tuples) that are members of `metadata["packages"]`,
    matching what a real `cargo tree -e normal` / `-e normal,build` run would
    report for one target. Kept separate from the `cargo`-invoking wrapper
    below so this graph logic (proc-macro-boundary walk, build-only diff) is
    directly unit-testable against small synthetic metadata fixtures.
    """
    packages_by_id = {p["id"]: p for p in metadata["packages"]}
    nodes_by_id = {n["id"]: n for n in metadata["resolve"]["nodes"]}
    root_id = metadata["resolve"]["root"]

    host_build_only = real_normal_and_build - real_normal
    dev_only = set(dev_only or ())

    def is_proc_macro(pkg_id: str) -> bool:
        pkg = packages_by_id.get(pkg_id)
        if pkg is None:
            return False
        return any("proc-macro" in t.get("kind", []) for t in pkg.get("targets", []))

    # A proc-macro crate itself, and everything only reachable *through* a
    # proc-macro crate's own dependency edges, runs on the host compiler at
    # build time and is not embedded in the compiled cdylib/staticlib output.
    # Walk root's normal edges, restricted to the real (feature-activation
    # correct) `real_normal` set, stopping at (but including) proc-macro
    # crate nodes without descending into their own dependencies.
    reachable_excluding_proc_macro_deps: set[str] = set()

    def visit(pkg_id: str, seen: set[str]) -> None:
        if pkg_id in seen:
            return
        seen.add(pkg_id)
        if pkg_id != root_id and is_proc_macro(pkg_id):
            return
        reachable_excluding_proc_macro_deps.add(pkg_id)
        node = nodes_by_id.get(pkg_id)
        if node is None:
            return
        for dep in node.get("deps", []):
            dep_id = dep["pkg"]
            if dep_id not in real_normal:
                continue
            kinds = {k.get("kind") for k in (dep.get("dep_kinds") or [{"kind": None}])}
            if None in kinds:
                visit(dep_id, seen)

    visit(root_id, set())

    truly_linked = (real_normal & reachable_excluding_proc_macro_deps)
    truly_linked.discard(root_id)
    proc_macro_support_closure = real_normal - truly_linked
    # The root crate itself is never one of its own dependencies; excluding
    # it here matters in practice because this crate's own package id is a
    # `path+file://...` source (an absolute filesystem path), which must
    # never leak into committed evidence.
    proc_macro_support_closure.discard(root_id)
    host_build_only.discard(root_id)
    dev_only.discard(root_id)

    return {
        "linked_into_compiled_artifact": sorted(truly_linked),
        "proc_macro_and_support_closure": sorted(proc_macro_support_closure),
        "host_build_dependency_only": sorted(host_build_only),
        "dev_dependency_only": sorted(dev_only),
    }


def classify_cargo_packages_for_target(triple: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """I/O wrapper: resolves real edge sets for `triple` via `cargo tree`,
    then delegates to the pure `classify_cargo_packages`.

    This crate declares no [dev-dependencies], and Cargo never activates a
    dependency's own dev-dependencies when it is built as a library
    dependency of another crate, so there is no dev-only edge to discover
    for any real target here (`dev_only` is always empty in practice).
    """
    name_version_to_ids = name_version_index(metadata)
    require_unambiguous_name_versions(name_version_to_ids, triple)

    def resolve_ids(name_versions: set[tuple[str, str]]) -> set[str]:
        ids: set[str] = set()
        for key in name_versions:
            found = name_version_to_ids.get(key)
            if found:
                ids.add(found[0])
        return ids

    real_normal = resolve_ids(run_cargo_tree_name_versions(triple, "normal"))
    real_normal_and_build = resolve_ids(run_cargo_tree_name_versions(triple, "normal,build"))
    return classify_cargo_packages(metadata, real_normal, real_normal_and_build)


def cargo_dependency_inventory_per_target() -> dict[str, Any]:
    lock_checksums = cargo_lock_checksums()
    all_packages: dict[str, dict[str, Any]] = {}
    membership: dict[str, dict[str, list[str]]] = {}

    for triple, artifact_path in CARGO_TARGET_TRIPLES:
        metadata = run_cargo_metadata_for_triple(triple)
        root_id = metadata["resolve"]["root"]
        packages_by_id = {p["id"]: p for p in metadata["packages"]}
        classified = classify_cargo_packages_for_target(triple, metadata)
        for ids in classified.values():
            if root_id in ids:
                raise EvidenceError(
                    f"{triple}: the crate root's own package id leaked into a "
                    "classification bucket; refusing to write potentially "
                    "absolute-path evidence"
                )
        membership[triple] = {"artifact_path": artifact_path, **classified}

        for category, ids in classified.items():
            for pkg_id in ids:
                pkg = packages_by_id.get(pkg_id)
                if pkg is None:
                    continue
                if pkg_id not in all_packages:
                    checksum = lock_checksums.get((pkg["name"], pkg["version"]))
                    all_packages[pkg_id] = {
                        "name": pkg["name"],
                        "version": pkg["version"],
                        "license": pkg.get("license"),
                        "source": pkg.get("source"),
                        "cargo_lock_checksum": checksum,
                        "membership": {},
                    }
                all_packages[pkg_id]["membership"].setdefault(triple, set()).add(category)

    packages_report = []
    for pkg_id in sorted(all_packages):
        entry = dict(all_packages[pkg_id])
        entry["membership"] = {
            triple: sorted(cats) for triple, cats in sorted(entry["membership"].items())
        }
        entry["linked_in_any_target"] = any(
            "linked_into_compiled_artifact" in cats for cats in entry["membership"].values()
        )
        packages_report.append(entry)

    linked_in_any = [p for p in packages_report if p["linked_in_any_target"]]
    mit_only_linked = sorted(
        p["name"] + "@" + p["version"]
        for p in linked_in_any
        if p["license"] in ("MIT",)
    )
    elections = cargo_license_elections(packages_report)

    return {
        "method": (
            "Two tools per rustc target triple that produces one of the 9 "
            "committed native artifacts (a separate graph for each, not one "
            "merged closure): `cargo metadata --locked --offline --filter-platform "
            "<triple>` supplies per-package facts (license/version/source/targets), "
            "and `cargo tree --locked --offline --target <triple> -e <edges> "
            "--prefix none` supplies the ACTUAL feature-activation-correct reachable set for "
            "'normal' and 'normal,build' edges. `cargo metadata`'s own "
            "`resolve.nodes[].deps` is not used as the reachability source: it "
            "unconditionally lists every dependency edge declared in Cargo.toml, "
            "including optional dependencies gated behind an inactive feature "
            "(confirmed 2026-08-24 -- `uniffi`'s optional bindgen-CLI dependency "
            "chain, `uniffi_bindgen`/`askama`/`goblin`/`nom`/`weedle2`/`textwrap`/"
            "`smawk`/`clap`, appeared as metadata edges despite the feature that "
            "would enable them never being active for this crate's actual build; "
            "`cargo tree` correctly omits all of them). `--offline` means both "
            "commands only ever read the local registry cache that an explicit, "
            "separate `cargo fetch --locked` network bootstrap step already "
            "populated (see docs/LEGAL_REVIEW.md's network-requirement note); "
            "neither command run by this script ever touches the network itself. "
            "Cargo.lock's own SHA-256 "
            "is hashed before and after every `cargo metadata`/`cargo tree` "
            "invocation; a mismatch fails generation. Each package records its "
            "Cargo.lock checksum (the crates.io tarball digest Cargo itself "
            "pins), not a digest invented by this script. A package is "
            "'linked_into_compiled_artifact' for a target only if it is in the "
            "real normal-edge set AND reachable from the crate root without "
            "passing through a proc-macro crate's own dependency edges -- "
            "proc-macro crates and everything reachable only from them run on "
            "the host compiler and are not embedded in the cdylib/staticlib/so "
            "this crate produces. 'host_build_dependency_only' is the real "
            "normal+build set minus the real normal set (e.g. `autocfg`, used "
            "only by `fs-err`'s build.rs). 'dev_dependency_only' is always empty: "
            "this crate declares no [dev-dependencies], and Cargo never activates "
            "a dependency's own dev-dependencies when it is built as a library "
            "dependency of another crate."
        ),
        "target_triples": [t for t, _ in CARGO_TARGET_TRIPLES],
        "membership_by_target": membership,
        "package_count": len(packages_report),
        "linked_in_any_target_count": len(linked_in_any),
        "mit_only_linked_packages": mit_only_linked,
        "packages": packages_report,
        "license_elections": elections,
    }


# ---------------------------------------------------------------------------
# Cargo license-expression parsing and per-package election table
# ---------------------------------------------------------------------------


def parse_spdx_expression(expression: str) -> list[dict[str, Any]]:
    """Split a Cargo.toml `license` SPDX-ish expression into AND-components.

    Every AND-component is independently mandatory (an `AND`ed license, e.g.
    Unicode-3.0, is required regardless of any `OR` election made elsewhere
    in the expression). Within one AND-component, an `OR` makes it a real
    disjunctive election among its options; a lone value with no `OR` is a
    single mandatory license (no election to make). A `WITH <exception>`
    clause stays attached to its own option string (e.g. "Apache-2.0 WITH
    LLVM-exception") rather than being torn apart, because it names one
    specific licensing term, not a separate top-level requirement.

    Also accepts the legacy pre-SPDX Cargo `license = "MIT/Apache-2.0"` slash
    syntax (crates.io still permits it; `cryptoxide`, `fs-err`, `siphasher`,
    and `toml` in this graph all use it), treating `/` as equivalent to
    ` OR ` when no explicit `OR`/`AND`/`WITH` keyword is present -- a slash
    string is NOT single-license just because it lacks those keywords.

    This is a minimal parser for the actual expressions observed in this
    crate's dependency graph on 2026-08-24 (`OR`, `AND`, `WITH`, `/`, parens
    wrapping one AND-component) -- not a general SPDX-expression grammar. An
    expression this parser cannot make sense of raises rather than guessing.
    """
    if not expression or not expression.strip():
        raise EvidenceError(f"empty or missing SPDX license expression: {expression!r}")
    text = expression.strip()
    if "/" in text and " OR " not in text and " AND " not in text and " WITH " not in text:
        options = [o.strip() for o in text.split("/")]
        if any(not o for o in options):
            raise EvidenceError(
                f"empty slash-separated option in license expression: {expression!r}"
            )
        return [{"type": "or", "options": options}]
    and_parts = [p.strip() for p in text.split(" AND ")]
    components: list[dict[str, Any]] = []
    for part in and_parts:
        stripped = part
        if stripped.startswith("(") and stripped.endswith(")"):
            stripped = stripped[1:-1].strip()
        elif "(" in stripped or ")" in stripped:
            raise EvidenceError(f"unbalanced/unsupported parens in SPDX expression: {expression!r}")
        if " OR " in stripped:
            options = [o.strip() for o in stripped.split(" OR ")]
            if any(not o for o in options):
                raise EvidenceError(f"empty OR option in SPDX expression: {expression!r}")
            components.append({"type": "or", "options": options})
        else:
            if not stripped:
                raise EvidenceError(f"empty AND component in SPDX expression: {expression!r}")
            components.append({"type": "single", "value": stripped})
    return components


def is_single_license_expression(expression: str | None) -> bool:
    """True only for a bare single license with no OR/AND/WITH ambiguity."""
    if not expression:
        return False
    components = parse_spdx_expression(expression)
    return len(components) == 1 and components[0]["type"] == "single"


def cargo_license_elections(packages_report: list[dict[str, Any]]) -> dict[str, Any]:
    """Every non-single-license package gets an explicit, catalog-backed row.

    A 2026-08-24 independent review found this packet only recorded an
    election for 3 hand-picked dual-license crates (JNA is Gradle, not
    Cargo, but the same gap applied here) while leaving ~26 other
    OR/AND/WITH-expression target-linked crates with no election record at
    all -- silently treated as if some other election "covered" them. Every
    row here comes from `scripts/cargo_election_catalog.py`
    (`CARGO_ELECTION_CATALOG`), a hand-reviewed, per-package table; this
    function never invents a "blanket" default election for a package
    missing from that catalog -- a target-linked package with a non-single
    expression and no catalog row fails generation.

    A row's `status`/`reviewer`/`review_date` cover only its OR election
    (`or_election_options`); each of its `and_required_components` (always
    mandatory when the row is target-linked, regardless of the OR election)
    gets its OWN row in `and_component_acceptance`, sourced from the
    catalog entry's optional `and_component_acceptance` mapping
    (component name -> {status, reviewer, review_date}) or defaulted to
    `OPEN`/`NOT_APPLICABLE` the same way the row-level status defaults --
    accepting the OR side of an expression never implicitly accepts its
    AND-required component, so `scripts/check_release_evidence.py` checks
    both independently and `release` mode requires both to be `ACCEPTED`
    for every target-linked row.
    """
    rows: list[dict[str, Any]] = []
    missing_catalog_entries: list[str] = []
    accepted_count = 0
    mandatory_count = 0

    for pkg in packages_report:
        expression = pkg.get("license")
        if expression and is_single_license_expression(expression):
            continue
        key = f"{pkg['name']}@{pkg['version']}"
        components = parse_spdx_expression(expression) if expression else None
        catalog_entry = cargo_election_catalog.lookup(pkg["name"], pkg["version"])
        linked = bool(pkg["linked_in_any_target"])
        if linked:
            mandatory_count += 1
            if catalog_entry is None:
                missing_catalog_entries.append(key)
                continue
        elif catalog_entry is None:
            catalog_entry = {
                "proposed_election": None,
                "status": "NOT_APPLICABLE",
                "reviewer": None,
                "review_date": None,
                "note": (
                    "Not linked into any of the 9 committed native artifacts "
                    "(build-dependency-only or proc-macro-and-support-closure "
                    "only); no election is required for this release's "
                    "distributed binaries, but the expression is still "
                    "recorded for completeness."
                ),
            }
        and_required = [
            c["value"] for c in (components or []) if c["type"] == "single"
        ]
        or_groups = [c["options"] for c in (components or []) if c["type"] == "or"]
        catalog_and_acceptance = catalog_entry.get("and_component_acceptance") or {}
        and_component_acceptance = []
        for component in and_required:
            component_entry = catalog_and_acceptance.get(component)
            if component_entry is None:
                component_entry = {
                    "status": "OPEN" if linked else "NOT_APPLICABLE",
                    "reviewer": None,
                    "review_date": None,
                }
            and_component_acceptance.append({"component": component, **component_entry})
        row = {
            "name": pkg["name"],
            "version": pkg["version"],
            "expression": expression,
            "linked_in_any_target": linked,
            "target_membership": pkg["membership"],
            "and_required_components": and_required,
            "and_component_acceptance": and_component_acceptance,
            "or_election_options": or_groups[0] if or_groups else [],
            "proposed_election": catalog_entry.get("proposed_election"),
            "status": catalog_entry.get("status"),
            "reviewer": catalog_entry.get("reviewer"),
            "review_date": catalog_entry.get("review_date"),
            "note": catalog_entry.get("note"),
        }
        if row["status"] == "ACCEPTED":
            accepted_count += 1
        rows.append(row)

    if missing_catalog_entries:
        raise EvidenceError(
            "cargo_license_elections: target-linked package(s) with a "
            "non-single-license SPDX expression have no row in "
            "scripts/cargo_election_catalog.CARGO_ELECTION_CATALOG (no "
            f"blanket election is ever assumed): {sorted(missing_catalog_entries)}"
        )

    rows.sort(key=lambda r: (r["name"], r["version"]))
    mandatory_and_component_count = sum(
        1 for r in rows if r["linked_in_any_target"] for _ in r["and_component_acceptance"]
    )
    accepted_and_component_count = sum(
        1
        for r in rows
        if r["linked_in_any_target"]
        for c in r["and_component_acceptance"]
        if c["status"] == "ACCEPTED"
    )
    all_and_components_accepted = (
        accepted_and_component_count == mandatory_and_component_count
    )
    return {
        "method": (
            "Every package whose Cargo.toml `license` field is not a single "
            "unambiguous SPDX license (i.e. contains OR, AND, or WITH, or is "
            "missing) gets one row here. AND-components are always mandatory "
            "regardless of any OR election elsewhere in the same expression "
            "(unicode-ident's Unicode-3.0 AND-component, for example, is not "
            "satisfied by electing either side of its (MIT OR Apache-2.0) "
            "OR-component) and carry their OWN `and_component_acceptance` "
            "status/reviewer/review_date entry, separate from the row's OR "
            "election -- accepting the OR side never implicitly accepts an "
            "AND-required component, and vice versa. A target-linked package "
            "with no catalog row fails generation rather than being silently "
            "treated as covered by some other package's election."
        ),
        "mandatory_row_count": mandatory_count,
        "accepted_count": accepted_count,
        "mandatory_and_component_count": mandatory_and_component_count,
        "accepted_and_component_count": accepted_and_component_count,
        "all_mandatory_elections_accepted": (
            accepted_count == mandatory_count
            and mandatory_count > 0
            and all_and_components_accepted
        ),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# UniFFI generated-binding discovery (dynamic glob, not a hand-maintained list)
# ---------------------------------------------------------------------------

UNIFFI_PACKAGE_RELATIVE = (
    "org/sarmidev/kardano/crypto/signing/backend/internal/kardano_ed25519_bip32_signing"
)
UNIFFI_SOURCE_SETS = ("commonMain", "jvmMain", "androidMain", "nativeMain")
HAND_WRITTEN_CINTEROP_FILE = "src/nativeInterop/cinterop/kardano_ed25519_bip32_signing.def"
CINTEROP_HEADER_FILE = (
    "src/nativeInterop/cinterop/headers/kardano_ed25519_bip32_signing/"
    "kardano_ed25519_bip32_signing.h"
)


def discover_uniffi_generated_files() -> list[str]:
    found: list[str] = []
    for source_set in UNIFFI_SOURCE_SETS:
        pattern = f"src/{source_set}/kotlin/{UNIFFI_PACKAGE_RELATIVE}.*.kt"
        matches = sorted(SIGNING_BACKEND.glob(pattern))
        for match in matches:
            if match.is_symlink():
                raise EvidenceError(f"refusing symlinked UniFFI binding file: {match}")
            found.append(str(match.relative_to(SIGNING_BACKEND)).replace(os.sep, "/"))
    header = SIGNING_BACKEND / CINTEROP_HEADER_FILE
    if header.is_file():
        if header.is_symlink():
            raise EvidenceError(f"refusing symlinked UniFFI header: {header}")
        found.append(CINTEROP_HEADER_FILE)
    if not found:
        raise EvidenceError("dynamic UniFFI binding discovery found zero files")
    return sorted(found)


def uniffi_bindings_inventory() -> dict[str, Any]:
    generated_paths = discover_uniffi_generated_files()
    generated = [{"path": p, "sha256": sha256_file(SIGNING_BACKEND / p)} for p in generated_paths]

    hand_written_path = SIGNING_BACKEND / HAND_WRITTEN_CINTEROP_FILE
    if not hand_written_path.is_file():
        raise FileNotFoundError("missing hand-written cinterop def file")
    if hand_written_path.is_symlink():
        raise EvidenceError(f"refusing symlinked hand-written cinterop file: {hand_written_path}")

    return {
        "method": (
            "Generated binding files are discovered dynamically by globbing "
            "src/<sourceSet>/kotlin/.../kardano_ed25519_bip32_signing.*.kt for each "
            "documented source set, plus the generated C header at a fixed path, "
            "rather than reading a hand-maintained file list. A newly added or "
            "renamed generated file changes this report's file list and its "
            "sha256_of_file_list on the next regeneration; scripts/"
            "check_release_evidence.py separately cross-checks this discovered set "
            "against `git ls-files` so an untracked or unexpectedly-placed "
            "generated file is not silently invisible either way."
        ),
        "upstream_generator_reference": {
            "tool": "gobley-uniffi-bindgen",
            "tool_version": "0.3.7",
            "tool_license": "Apache-2.0 OR MIT",
            "target_crate": "uniffi",
            "target_crate_version": "=0.29.5",
            "target_crate_license": "MPL-2.0",
            "upstream_repository": "https://github.com/mozilla/uniffi-rs",
        },
        "mpl_obligation_status": (
            "OPEN counsel determination -- see docs/LEGAL_REVIEW.md \u00a76. This "
            "report does not conclude that generating/compiling against an "
            "MPL-2.0 crate is, or is not, itself Covered Software requiring "
            "separate notice beyond directing recipients to the upstream "
            "repository above."
        ),
        "generated_files": generated,
        "generated_file_count": len(generated),
        "hand_written_cinterop_def": {
            "path": HAND_WRITTEN_CINTEROP_FILE,
            "sha256": sha256_file(hand_written_path),
            "note": (
                "Not emitted by the bindgen CLI; hand-written and must keep "
                "package = kardano_ed25519_bip32_signing.cinterop "
                "(crypto-signing-backend/README.md)."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Native-artifact catalog (Kardano-committed) -- exact match to CHECKSUMS.sha256
# ---------------------------------------------------------------------------

NATIVE_ARTIFACT_CATALOG: dict[str, dict[str, str]] = {
    "src/jvmMain/resources/darwin-aarch64/libkardano_ed25519_bip32_signing.dylib": {
        "platform": "macOS (JVM/JNA)",
        "arch": "aarch64",
        "source_owner": "first-party (in-tree crypto-signing-backend crate)",
        "provenance": "Built and runtime-verified on the macOS arm64 host.",
        "rebuild_workflow": ".github/workflows/native-rebuild-evidence.yml (macos-jvm group)",
    },
    "src/jvmMain/resources/darwin-x86-64/libkardano_ed25519_bip32_signing.dylib": {
        "platform": "macOS (JVM/JNA)",
        "arch": "x86-64",
        "source_owner": "first-party (in-tree crypto-signing-backend crate)",
        "provenance": "Cross-built on macOS arm64; not runtime-verified on this host.",
        "rebuild_workflow": ".github/workflows/native-rebuild-evidence.yml (macos-jvm group)",
    },
    "src/androidMain/jniLibs/arm64-v8a/libkardano_ed25519_bip32_signing.so": {
        "platform": "Android (JNI)",
        "arch": "arm64-v8a",
        "source_owner": "first-party (in-tree crypto-signing-backend crate)",
        "provenance": "cargo-ndk cross-build.",
        "rebuild_workflow": ".github/workflows/native-rebuild-evidence.yml (android group)",
    },
    "src/androidMain/jniLibs/armeabi-v7a/libkardano_ed25519_bip32_signing.so": {
        "platform": "Android (JNI)",
        "arch": "armeabi-v7a",
        "source_owner": "first-party (in-tree crypto-signing-backend crate)",
        "provenance": "cargo-ndk cross-build.",
        "rebuild_workflow": ".github/workflows/native-rebuild-evidence.yml (android group)",
    },
    "src/androidMain/jniLibs/x86/libkardano_ed25519_bip32_signing.so": {
        "platform": "Android (JNI)",
        "arch": "x86",
        "source_owner": "first-party (in-tree crypto-signing-backend crate)",
        "provenance": "cargo-ndk cross-build.",
        "rebuild_workflow": ".github/workflows/native-rebuild-evidence.yml (android group)",
    },
    "src/androidMain/jniLibs/x86_64/libkardano_ed25519_bip32_signing.so": {
        "platform": "Android (JNI)",
        "arch": "x86_64",
        "source_owner": "first-party (in-tree crypto-signing-backend crate)",
        "provenance": "cargo-ndk cross-build.",
        "rebuild_workflow": ".github/workflows/native-rebuild-evidence.yml (android group)",
    },
    "src/nativeInterop/libs/iosArm64/libkardano_ed25519_bip32_signing.a": {
        "platform": "iOS device (Kotlin/Native)",
        "arch": "arm64",
        "source_owner": "first-party (in-tree crypto-signing-backend crate)",
        "provenance": "cargo build --target aarch64-apple-ios.",
        "rebuild_workflow": ".github/workflows/native-rebuild-evidence.yml (ios group)",
    },
    "src/nativeInterop/libs/iosSimulatorArm64/libkardano_ed25519_bip32_signing.a": {
        "platform": "iOS simulator (Kotlin/Native)",
        "arch": "arm64",
        "source_owner": "first-party (in-tree crypto-signing-backend crate)",
        "provenance": "cargo build --target aarch64-apple-ios-sim.",
        "rebuild_workflow": ".github/workflows/native-rebuild-evidence.yml (ios group)",
    },
    "src/jvmMain/resources/linux-x86-64/libkardano_ed25519_bip32_signing.so": {
        "platform": "Linux (JVM/JNA)",
        "arch": "x86-64",
        "source_owner": "first-party (in-tree crypto-signing-backend crate)",
        "provenance": (
            "Native ubuntu-22.04 rebuild; promoted from run 32678079715 "
            "(SHA-256 cb4390996d30cb9a6f64ad4cbc1bd301d4400dff0806a41829d574"
            "cd1f1b4ed5)."
        ),
        "rebuild_workflow": ".github/workflows/linux-jvm-rebuild-evidence.yml",
    },
}

WINDOWS_CANDIDATE_NOTE = (
    "win32-x86-64/kardano_ed25519_bip32_signing.dll has a technical GO on "
    "PE-structure evidence (windows-jvm-rebuild-evidence.yml). Its "
    "independent PE technical review is complete (commit c65a20a), which "
    "closes ONLY that technical-review gate -- it is not a legal approval "
    "and does not promote this candidate or mean any DLL is distributed. "
    "It remains unpromoted: not in crypto-signing-backend/CHECKSUMS.sha256, "
    "not in this catalog, and not distributed, solely because of the "
    "still-open upstream hyperledger-identus/apollo issue #226 (and any "
    "separate manual/release decision)."
)


def parse_checksums(path: Path) -> dict[str, str]:
    reject_symlink(path)
    raw = read_bytes_no_symlink(path)
    if b"\r" in raw:
        raise EvidenceError(f"{path}: CRLF or stray CR byte in CHECKSUMS.sha256 (reject)")
    rows: dict[str, str] = {}
    for lineno, raw_line in enumerate(raw.decode("utf-8").split("\n"), start=1):
        line = raw_line.strip()
        if not line:
            continue
        digest, _, rel_path = line.partition("  ")
        if not digest or not rel_path:
            raise EvidenceError(f"{path}:{lineno}: malformed CHECKSUMS.sha256 line: {line!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise EvidenceError(f"{path}:{lineno}: not a lowercase 64-hex SHA-256: {digest!r}")
        if rel_path in rows:
            raise EvidenceError(f"{path}:{lineno}: duplicate path {rel_path!r}")
        rows[rel_path] = digest
    return rows


def native_artifacts_inventory() -> dict[str, Any]:
    checksums_path = SIGNING_BACKEND / "CHECKSUMS.sha256"
    checksum_rows = parse_checksums(checksums_path)

    catalog_paths = set(NATIVE_ARTIFACT_CATALOG)
    checksum_paths = set(checksum_rows)
    if catalog_paths != checksum_paths:
        missing_from_checksums = sorted(catalog_paths - checksum_paths)
        missing_from_catalog = sorted(checksum_paths - catalog_paths)
        raise EvidenceError(
            "native artifact catalog does not match CHECKSUMS.sha256 exactly: "
            f"missing_from_checksums={missing_from_checksums} "
            f"missing_from_catalog={missing_from_catalog}"
        )

    entries = []
    for rel_path in sorted(checksum_rows):
        catalog = NATIVE_ARTIFACT_CATALOG[rel_path]
        on_disk = SIGNING_BACKEND / rel_path
        actual_sha256 = sha256_file(on_disk)
        if actual_sha256 != checksum_rows[rel_path]:
            raise EvidenceError(
                f"{rel_path}: on-disk SHA-256 {actual_sha256} != "
                f"CHECKSUMS.sha256 {checksum_rows[rel_path]}"
            )
        entries.append({"path": rel_path, "sha256": actual_sha256, **catalog})

    return {
        "method": (
            "Every row is required to appear in both "
            "crypto-signing-backend/CHECKSUMS.sha256 and this script's "
            "NATIVE_ARTIFACT_CATALOG; a mismatch in either direction, a "
            "duplicate path, a malformed line, a symlink, or a SHA-256 mismatch "
            "against the committed bytes all fail generation."
        ),
        "artifact_count": len(entries),
        "artifacts": entries,
        "windows_candidate_not_promoted": WINDOWS_CANDIDATE_NOTE,
    }


# ---------------------------------------------------------------------------
# Third-party Maven native carriers (point-in-time artifact inspection)
# ---------------------------------------------------------------------------

# Dated 2026-08-24 inspection of the actual resolved artifact bytes in the
# local Gradle module cache (Python zipfile, per-entry SHA-256 and size read
# directly from the archive, not narrated by hand) -- the same method
# THIRD_PARTY_NOTICES.md has used since 2026-08-23, now including every
# embedded native member's own SHA-256 and inferred platform/arch, not just
# path and size. This is a point-in-time fact about specific artifact bytes,
# not a live re-derivation: rerunning generate_legal_evidence.py on a machine
# without these exact artifacts resolved reproduces the *catalog* (this
# static table) but cannot independently re-confirm the embedded-file hashes
# without the artifact present. See docs/LEGAL_REVIEW.md \u00a78.
#
# `distribution_status` is one of:
#   - "redistributed_by_kardano": this carrier's own artifact bytes (and
#     therefore its embedded native members) end up inside a Kardano-built
#     APK/AAR/JAR that Kardano SDK distributes.
#   - "transitively_available": resolved in the dependency graph and
#     reachable, but not itself redistributed by Kardano in this release.
#   - "not_in_first_release_scope": resolved by Gradle (present in a
#     lockfile) but the distribution channel that would ship it (e.g. a
#     Desktop installer) is not built/distributed in this release -- see
#     docs/LEGAL_REVIEW.md \u00a71a.
#   - "resolved_runtime_dependency": a real runtime dependency of a
#     distributed module, used here only where neither of the above two
#     more specific labels applies.
# A 2026-08-24 independent review found JNA's own catalog entry claimed "25"
# embedded natives; the real count, enumerated here, is 27 (aix-ppc/
# aix-ppc64 were previously missed).
MAVEN_NATIVE_CARRIERS: tuple[dict[str, Any], ...] = (
    {
        "maven_coordinate": "org.hyperledger.identus:bip32-ed25519-android:1.8.8",
        "carrier_kind": "Android .aar",
        "license": "Apache-2.0 (wrapper POM); embedded native's own obligations OPEN",
        "distribution_status": "redistributed_by_kardano",
        "distributed_by_kardano": True,
        "windows_native_available_upstream": False,
        "inspected_2026_08_24": True,
        "artifact_sha256": "65f047d39bf88991892daf685f1bfeda644e2195d803857909cc7672c6aa09d8",
        "primary_artifact_kind": "aar",
        "embedded_natives": [
            {
                "path": "jni/arm64-v8a/libuniffi_ed25519_bip32_wrapper.so",
                "size_bytes": 696072,
                "sha256": "ca75e1042e62c61fd4382b0d8cbe5d86dd1d41e7d58f1f1a89b153ea0d1efc5a",
                "platform": "Android",
                "arch": "arm64-v8a",
            },
            {
                "path": "jni/armeabi-v7a/libuniffi_ed25519_bip32_wrapper.so",
                "size_bytes": 523692,
                "sha256": "ebb3f562f7c7ad0a2d6a320fec510f993c7526500d59db9b96bb95fa6109a922",
                "platform": "Android",
                "arch": "armeabi-v7a",
            },
            {
                "path": "jni/x86/libuniffi_ed25519_bip32_wrapper.so",
                "size_bytes": 708316,
                "sha256": "1d43aedf4eb0af8a75f192a6471f99ec2f388d204d03d1200d522cceed7bc2e2",
                "platform": "Android",
                "arch": "x86",
            },
            {
                "path": "jni/x86_64/libuniffi_ed25519_bip32_wrapper.so",
                "size_bytes": 668632,
                "sha256": "8850debc71aa6aa6313e4e0dc730d99a0d0993d714041b2360d277ac37e91e88",
                "platform": "Android",
                "arch": "x86_64",
            },
        ],
        "note": (
            "Upstream has not published a win32-x86-64 build "
            "(hyperledger-identus/apollo issue #226); Kardano SDK cannot "
            "distribute what upstream has not built. This repository has not "
            "independently reproduced this .so from source and does not claim an "
            "exact source-to-binary mapping; whether its own build embeds an "
            "MPL-2.0 UniFFI runtime (as this repo's own crypto-signing-backend "
            "does) is an OPEN counsel determination, not assumed either way."
        ),
    },
    {
        # Found by cross_check_maven_native_carriers_against_local_cache()'s
        # dynamic discovery (2026-08-24 independent review, Gap 7): a
        # separate JVM-classified artifact of the SAME upstream Identus
        # project, resolved by crypto/shared/wallet/desktopApp/androidApp's
        # JVM source sets, previously entirely absent from this catalog.
        "maven_coordinate": "org.hyperledger.identus:bip32-ed25519-jvm:1.8.8",
        "carrier_kind": "JVM .jar",
        "license": "Apache-2.0 (wrapper POM); embedded native's own obligations OPEN",
        # Kardano SDK does not publish Maven/JVM artifacts yet (see
        # docs/RELEASING.md), and no Desktop installer is built/distributed
        # in this release (docs/LEGAL_REVIEW.md \u00a71a) -- so this
        # coordinate's JVM jar is resolved and reachable (JVM tests across
        # crypto/shared/wallet/desktopApp/androidApp depend on it) but is not
        # itself redistributed by Kardano through any channel in this
        # release.
        "distribution_status": "transitively_available",
        "distributed_by_kardano": False,
        "windows_native_available_upstream": False,
        "inspected_2026_08_24": True,
        "artifact_sha256": "4db0135006f5ecbcc445f9ec8800101ab40438e5a9daa083c5ccab85cc661d3a",
        "primary_artifact_kind": "jar",
        "embedded_natives": [
            {
                "path": "darwin-aarch64/libuniffi_ed25519_bip32_wrapper.dylib",
                "size_bytes": 561744,
                "sha256": "35644b7fe8eac8347c9e51f50d64bcba79eb0a39240009bc5f68a057c4fbd309",
                "platform": "macOS",
                "arch": "arm64",
            },
            {
                "path": "darwin-aarch64/libuniffi_ed25519_bip32_wrapper.a",
                "size_bytes": 28805776,
                "sha256": "6aeb164932970ba0b57f9c6447b5c18c1a48e0cb4178e5c5ba90dc3d9f72937e",
                "platform": "macOS",
                "arch": "arm64",
            },
            {
                "path": "darwin-x86-64/libuniffi_ed25519_bip32_wrapper.dylib",
                "size_bytes": 551808,
                "sha256": "719b7ddbd23ace7da3744ccc21477d804d5f0372d9c4387bf589ba9c1b4023c3",
                "platform": "macOS",
                "arch": "x86-64",
            },
            {
                "path": "darwin-x86-64/libuniffi_ed25519_bip32_wrapper.a",
                "size_bytes": 28778240,
                "sha256": "fb7c79708a983112ed93fc3e2759dc7e862aac39131730025ca613d20acf1bfc",
                "platform": "macOS",
                "arch": "x86-64",
            },
            {
                "path": "linux-aarch64/libuniffi_ed25519_bip32_wrapper.so",
                "size_bytes": 659056,
                "sha256": "c977c2bdaeea541449b30e4e14b0aa405d005e78a7a8e6ae5efec812dd911690",
                "platform": "Linux",
                "arch": "aarch64",
            },
            {
                "path": "linux-aarch64/libuniffi_ed25519_bip32_wrapper.a",
                "size_bytes": 39509386,
                "sha256": "404b66ca22b2a2156c64c5ff48ebca68104441c48208081d81923b98d77778f8",
                "platform": "Linux",
                "arch": "aarch64",
            },
            {
                "path": "linux-x86-64/libuniffi_ed25519_bip32_wrapper.so",
                "size_bytes": 631304,
                "sha256": "81f41f32d0e678f30ae1329baeeaae061630eb0ce435ed84750fe18aade9eb1c",
                "platform": "Linux",
                "arch": "x86-64",
            },
            {
                "path": "linux-x86-64/libuniffi_ed25519_bip32_wrapper.a",
                "size_bytes": 38550120,
                "sha256": "c75e8f4b4b7ef07b35374373ccc69399895811d563dbd1b73cffeb6119824709",
                "platform": "Linux",
                "arch": "x86-64",
            },
        ],
        "note": (
            "No win32-x86-64 (or any Windows) build is published upstream for "
            "this JVM-classified artifact at all -- a strictly narrower gap "
            "than the Android variant's (hyperledger-identus/apollo issue "
            "#226), since Windows is not attempted here even conditionally. "
            "This repository has not independently reproduced these "
            "binaries from source and does not claim an exact "
            "source-to-binary mapping; whether this build embeds an "
            "MPL-2.0 UniFFI runtime (as this repo's own "
            "crypto-signing-backend does) is an OPEN counsel determination, "
            "the same unresolved question as the Android variant above -- "
            "not concluded 'satisfied' or 'no obligation' here."
        ),
    },
    {
        "maven_coordinate": "com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings-jvm:0.9.5",
        "carrier_kind": "JVM .jar",
        "license": "Apache-2.0 (wrapper) + ISC (bundled libsodium binaries)",
        "distribution_status": "redistributed_by_kardano",
        "distributed_by_kardano": True,
        "windows_native_available_upstream": True,
        "inspected_2026_08_24": True,
        "artifact_sha256": "63d7b2ea35c6fa57636931977f25929d4f2cac9513411f16337a244b7ddc239b",
        "primary_artifact_kind": "jar",
        "embedded_natives": [
            {
                "path": "libdynamic-linux-arm64-libsodium.so",
                "size_bytes": 358168,
                "sha256": "b35408a78e348bc173f3aac3c87c4a6beff9a9b6dfbb932ec7aa54485dc50569",
                "platform": "Linux",
                "arch": "arm64",
            },
            {
                "path": "libdynamic-linux-x86-64-libsodium.so",
                "size_bytes": 524432,
                "sha256": "0e8b1a9f0cad585f4bf87c6b40815eafb00b63f55dc93bf3bb033790c939f918",
                "platform": "Linux",
                "arch": "x86-64",
            },
            {
                "path": "libdynamic-macos.dylib",
                "size_bytes": 829200,
                "sha256": "ccbf9230dd12f84c5b1e1a6e5cb493210cee49c1026aafe1e7634e331bd1f60e",
                "platform": "macOS",
                "arch": "universal (arm64+x86-64 fat binary; not separately hashed per slice)",
            },
            {
                "path": "libdynamic-msvc-x86-64-libsodium.dll",
                "size_bytes": 346624,
                "sha256": "3ee699dcd60528a96d25a7a585a1388e127b01a2f45a51a134cb8ce667b2348e",
                "platform": "Windows",
                "arch": "x86-64",
            },
        ],
        "note": (
            "Windows libsodium .dll ships inside this jar; distinct from the "
            "Kardano Windows signing-backend candidate, which is not distributed."
        ),
    },
    {
        "maven_coordinate": "com.goterl:lazysodium-android:5.2.0",
        "carrier_kind": "Android .aar",
        "license": "MPL-2.0 (wrapper, file-level obligation OPEN) + ISC (bundled libsodium binaries)",
        "distribution_status": "redistributed_by_kardano",
        "distributed_by_kardano": True,
        "windows_native_available_upstream": False,
        "inspected_2026_08_24": True,
        "artifact_sha256": "b5378c1d9db2573d61b304e89cf83db187a05c3e4ff081d9b2ef3d0bb00ca314",
        "primary_artifact_kind": "aar",
        "embedded_natives": [
            {
                "path": "jni/arm64-v8a/libsodium.so",
                "size_bytes": 332824,
                "sha256": "4ecfcb35a3b9349914b877139e5ff483b27898b6ec276478d8cc76d28af581e7",
                "platform": "Android",
                "arch": "arm64-v8a",
            },
            {
                "path": "jni/armeabi-v7a/libsodium.so",
                "size_bytes": 341648,
                "sha256": "0a6f026dc74f7eb6355100ca280e647e250d449e4b4538aeb987728f272a7105",
                "platform": "Android",
                "arch": "armeabi-v7a",
            },
            {
                "path": "jni/x86/libsodium.so",
                "size_bytes": 467596,
                "sha256": "78cf8c1f9221732975b2d1adf895620a65a87492d62a20be365a467af777071c",
                "platform": "Android",
                "arch": "x86",
            },
            {
                "path": "jni/x86_64/libsodium.so",
                "size_bytes": 427312,
                "sha256": "fa59aee46baccf8b76ed4d9c92a45b9e50a5c45fe0da97ff12feb2be911241e9",
                "platform": "Android",
                "arch": "x86_64",
            },
        ],
        "note": "Android-only carrier; no Windows binary is bundled.",
    },
    {
        # Found by cross_check_maven_native_carriers_against_local_cache()'s
        # dynamic discovery (2026-08-24 independent review, Gap 7): a real
        # runtime dependency of `shared`/`androidApp` that was previously
        # entirely absent from this catalog despite bundling per-ABI native
        # code, an omission this generator now fails closed on rather than
        # silently missing again.
        "maven_coordinate": "androidx.graphics:graphics-path:1.0.1",
        "carrier_kind": "Android .aar",
        "license": "Apache-2.0",
        "distribution_status": "redistributed_by_kardano",
        "distributed_by_kardano": True,
        "windows_native_available_upstream": False,
        "inspected_2026_08_24": True,
        "artifact_sha256": "8ca4032b6d79b351f0b59ad4b580eddbb9423e1652f7c958830687f1eee2ec03",
        "primary_artifact_kind": "aar",
        "embedded_natives": [
            {
                "path": "jni/arm64-v8a/libandroidx.graphics.path.so",
                "size_bytes": 10096,
                "sha256": "41e9a793c43a0f4fddb19e33f346bace464f30f888ba7b9eaf96294ea115bfb6",
                "platform": "Android",
                "arch": "arm64-v8a",
            },
            {
                "path": "jni/armeabi-v7a/libandroidx.graphics.path.so",
                "size_bytes": 7252,
                "sha256": "41399eba6fc2a60f6f14642375c1824f3cf25eb8fec7397d753730a3ceda3e2b",
                "platform": "Android",
                "arch": "armeabi-v7a",
            },
            {
                "path": "jni/x86/libandroidx.graphics.path.so",
                "size_bytes": 9284,
                "sha256": "eb0570b41fd3bff25d8204a967c03bd7550719e768b791f680cc40cbe35f29af",
                "platform": "Android",
                "arch": "x86",
            },
            {
                "path": "jni/x86_64/libandroidx.graphics.path.so",
                "size_bytes": 10760,
                "sha256": "4e56c996f13670e70082658de7880c4020eabf4f25e43387f88ed78a713fc9f0",
                "platform": "Android",
                "arch": "x86_64",
            },
        ],
        "note": (
            "AndroidX Graphics Path (`shared`/`androidApp` runtime dependency, "
            "resolved via Compose UI graphics support). Android-only carrier; "
            "no Windows binary is bundled."
        ),
    },
    {
        "maven_coordinate": "org.jetbrains.skiko:skiko-awt-runtime-macos-arm64:0.144.6",
        "carrier_kind": "JVM .jar (Desktop app runtime classpath)",
        "license": "Apache-2.0",
        # Desktop MSI/DEB/DMG installers are not built or distributed in this
        # release (docs/LEGAL_REVIEW.md \u00a71a) even though desktopApp/
        # build.gradle.kts can configure them -- this coordinate is resolved
        # (real, locked) but not shipped to any end user in this release, so
        # it is NOT "redistributed_by_kardano" despite `distributed_by_kardano`
        # historically (incorrectly) implying that.
        "distribution_status": "not_in_first_release_scope",
        "distributed_by_kardano": False,
        "windows_native_available_upstream": False,
        "inspected_2026_08_24": True,
        "artifact_sha256": "aec37b44e8dabf4de620068146769655748be3971bf868614e5ec6b240b2ac35",
        "primary_artifact_kind": "jar",
        "embedded_natives": [
            {
                "path": "libskiko-macos-arm64.dylib",
                "size_bytes": 21455568,
                "sha256": "f7676395835316696f9b2a762705c307cbdd703545a02fc1b1154a13df96fb64",
                "platform": "macOS",
                "arch": "arm64",
            },
            {
                "path": "libskiko-macos-x64.dylib",
                "size_bytes": 22206704,
                "sha256": "27cce35c02a7465aca33e6fe2e63823fc49a5faf860304f5a1295d1187c9de6a",
                "platform": "macOS",
                "arch": "x86-64",
            },
        ],
        "note": (
            "Compose Multiplatform/Skia native renderer for the desktopApp "
            "sample only; not part of any SDK module, and no Desktop installer "
            "is built or distributed in this release. Only the macOS-arm64 "
            "runtime variant is currently resolved in this repository's "
            "desktopApp/gradle.lockfile; other Skiko OS/arch variants are not "
            "reviewed here."
        ),
    },
    {
        "maven_coordinate": "net.java.dev.jna:jna:5.19.1",
        "carrier_kind": "JVM/Android jar (also used directly by crypto-signing-backend)",
        "license": (
            "Apache-2.0 OR LGPL-2.1-or-later (Kardano SDK proposes electing "
            "Apache-2.0; not yet ACCEPTED -- OPEN row pending reviewer/date, "
            "see docs/LEGAL_REVIEW.md §5a)"
        ),
        "distribution_status": "redistributed_by_kardano",
        "distributed_by_kardano": True,
        "windows_native_available_upstream": True,
        "inspected_2026_08_24": True,
        "artifact_sha256": "4fb141dd8ef6b0585ffceea4bc49602fbc6312fa977e2c488794ea3e6aafecae",
        "primary_artifact_kind": "jar",
        # JNA 5.19.1 publishes Gradle Module Metadata with a SEPARATE Android
        # `.aar` variant (distinct file from the `.jar` above, same GAV) --
        # found by cross_check_maven_native_carriers_against_local_cache()'s
        # dynamic discovery (2026-08-24 independent review, Gap 7). Android
        # source sets (this repo's `androidApp`) resolve the `.aar`, whose
        # bundled natives are a DIFFERENT, smaller 7-file set (standard
        # Android ABI directory names, not JNA's own os-arch naming) than
        # the 27 in the `.jar` above -- both are recorded here since both
        # are real, resolved artifacts of this one coordinate.
        "additional_artifacts": [
            {
                "kind": "aar",
                "artifact_sha256": "b57125cb7d16253f0d65a80f7d3a4c3664effa711b8bdbb7f87fb572ce1624ed",
                "note": (
                    "Android Gradle Module Metadata variant of this same "
                    "coordinate; contains only the 7 embedded_natives rows "
                    "below whose path starts with 'jni/' (Android ABI "
                    "directory names), not the 27 'com/sun/jna/...' rows."
                ),
            }
        ],
        "embedded_native_count": 34,
        "embedded_natives": [
            {"path": "com/sun/jna/aix-ppc/libjnidispatch.a", "size_bytes": 613721, "sha256": "f33d3b4c2ca35fac8befc502b408e5b5851f8850c397d59f0094459fe455d0c1", "platform": "AIX", "arch": "ppc"},
            {"path": "com/sun/jna/aix-ppc64/libjnidispatch.a", "size_bytes": 657335, "sha256": "be8a1c6a282c637cf0ce217c331ee82a3643c59ef166fdbaabf1f27c3d7fd0dc", "platform": "AIX", "arch": "ppc64"},
            {"path": "com/sun/jna/darwin-aarch64/libjnidispatch.jnilib", "size_bytes": 159800, "sha256": "70c9af22ba3ce12128881b4654422ce69a6f96fc238333731cf718601b536245", "platform": "macOS", "arch": "aarch64"},
            {"path": "com/sun/jna/darwin-x86-64/libjnidispatch.jnilib", "size_bytes": 109824, "sha256": "69cca8bbe2f0ff3fc412481e73333d5b49fc3a1ba2ff564a0af9495d7e6b531d", "platform": "macOS", "arch": "x86-64"},
            {"path": "com/sun/jna/dragonflybsd-x86-64/libjnidispatch.so", "size_bytes": 116880, "sha256": "c0c6e64b476d726d86e996af1397491bbff9ccadcba1e0c4639a8f1ae5454062", "platform": "DragonFlyBSD", "arch": "x86-64"},
            {"path": "com/sun/jna/freebsd-aarch64/libjnidispatch.so", "size_bytes": 116008, "sha256": "bca4aece4b834fd04301d5896482f657d06d6860e2d03089c0cc78eea65dd492", "platform": "FreeBSD", "arch": "aarch64"},
            {"path": "com/sun/jna/freebsd-x86-64/libjnidispatch.so", "size_bytes": 121040, "sha256": "3c4d14c74bb6798c76b43cad4395b8bdaa9181a7991e160a376f87bb1ab13ced", "platform": "FreeBSD", "arch": "x86-64"},
            {"path": "com/sun/jna/freebsd-x86/libjnidispatch.so", "size_bytes": 105372, "sha256": "784b2a955b1504dec96fa8b87972bcb2815ecfa818fe5c2e57ed9073cab0592c", "platform": "FreeBSD", "arch": "x86"},
            {"path": "com/sun/jna/linux-aarch64/libjnidispatch.so", "size_bytes": 162288, "sha256": "f18fa2c973b2b9ea2dfa6d36d397e0bb743aa2aa09876e2a3b8c87a5e67bf8b6", "platform": "Linux", "arch": "aarch64"},
            {"path": "com/sun/jna/linux-arm/libjnidispatch.so", "size_bytes": 130788, "sha256": "b2a32135dea251fde4027f536345420001bc921e21baf82b2e01ce2753da2097", "platform": "Linux", "arch": "arm"},
            {"path": "com/sun/jna/linux-armel/libjnidispatch.so", "size_bytes": 139472, "sha256": "d9db010b0336cdbf643c38921c1c04519f811bee0f45824b6872661a25d64ed2", "platform": "Linux", "arch": "armel"},
            {"path": "com/sun/jna/linux-loongarch64/libjnidispatch.so", "size_bytes": 341968, "sha256": "6c55d9ec3efaaee1843795648246b3fe52de09d3990984c5b8a580cc803c6bc9", "platform": "Linux", "arch": "loongarch64"},
            {"path": "com/sun/jna/linux-mips64el/libjnidispatch.so", "size_bytes": 144056, "sha256": "0025cd4345faec5a7d9fc8c88f187016dbaf4a6ef411cd6c8907e199d952528d", "platform": "Linux", "arch": "mips64el"},
            {"path": "com/sun/jna/linux-ppc/libjnidispatch.so", "size_bytes": 127724, "sha256": "fbde8c5b108934e75c7008562e95b209535bf4996b3bc246ec5e425a0757a903", "platform": "Linux", "arch": "ppc"},
            {"path": "com/sun/jna/linux-ppc64le/libjnidispatch.so", "size_bytes": 145072, "sha256": "aaa31a2220e270f69259d930540c5682b1bd662a6d774918605e62cd562d5d11", "platform": "Linux", "arch": "ppc64le"},
            {"path": "com/sun/jna/linux-riscv64/libjnidispatch.so", "size_bytes": 100064, "sha256": "f817ac611184e31fd84ac2d223ff8f9312300fbc025adfb5cadbfefb8d1a2c13", "platform": "Linux", "arch": "riscv64"},
            {"path": "com/sun/jna/linux-s390x/libjnidispatch.so", "size_bytes": 136976, "sha256": "b31df7050aa22907e5caae2ef81db83e2900b7b6e683080f6f5681373a71e400", "platform": "Linux", "arch": "s390x"},
            {"path": "com/sun/jna/linux-x86-64/libjnidispatch.so", "size_bytes": 134447, "sha256": "ca07953d595210082339753d9e818a1fdb40509a17a41914d9a2cb0d2df6b6af", "platform": "Linux", "arch": "x86-64"},
            {"path": "com/sun/jna/linux-x86/libjnidispatch.so", "size_bytes": 123384, "sha256": "546ec7cc6548de411cc52a1069295301308437080be014cda2346ccd0f99bf55", "platform": "Linux", "arch": "x86"},
            {"path": "com/sun/jna/openbsd-x86-64/libjnidispatch.so", "size_bytes": 98728, "sha256": "ee3b7bfa0887b7388ad598dea98281ae40907bafa8cf56b406427aecd3d2ecdd", "platform": "OpenBSD", "arch": "x86-64"},
            {"path": "com/sun/jna/sunos-sparc/libjnidispatch.so", "size_bytes": 231108, "sha256": "5ae26c1d50dd6836d0bafb1af2a6c39eb4084be42f0a05da0645d31feed1efad", "platform": "Solaris", "arch": "sparc"},
            {"path": "com/sun/jna/sunos-sparcv9/libjnidispatch.so", "size_bytes": 166976, "sha256": "ccd720895968a885d423facf63615c7f16490f94d946ecb5fefdd4951c62297c", "platform": "Solaris", "arch": "sparcv9"},
            {"path": "com/sun/jna/sunos-x86-64/libjnidispatch.so", "size_bytes": 169992, "sha256": "4a0b0b11369d4f88437700e8ee3557cb518ec017bfe2df3bd49faf82e60e8f8e", "platform": "Solaris", "arch": "x86-64"},
            {"path": "com/sun/jna/sunos-x86/libjnidispatch.so", "size_bytes": 153152, "sha256": "fdba3f2f4220fb407c7841b2f49efd4fe1c06dca26c9768513e13461ed1520c5", "platform": "Solaris", "arch": "x86"},
            {"path": "com/sun/jna/win32-aarch64/jnidispatch.dll", "size_bytes": 274432, "sha256": "b8f98be314234cf12b5b46c29652f70c0f6abb93ae19b63d3fe2692062aa699d", "platform": "Windows", "arch": "aarch64"},
            {"path": "com/sun/jna/win32-x86-64/jnidispatch.dll", "size_bytes": 273408, "sha256": "5a7ff949f6d93d86491eb5b26b1cfc60051168a60622650224b89995ac420023", "platform": "Windows", "arch": "x86-64"},
            {"path": "com/sun/jna/win32-x86/jnidispatch.dll", "size_bytes": 226304, "sha256": "752d597cee7e95cb517327146bf42f124c0d6c0bc48b3ecc3b1b3b0531a52f44", "platform": "Windows", "arch": "x86"},
            {"path": "jni/arm64-v8a/libjnidispatch.so", "size_bytes": 176520, "sha256": "abc26e994517bcaa3309acdb0a27373864086c7569c89d3087b8626fada9ef06", "platform": "Android", "arch": "arm64-v8a"},
            {"path": "jni/armeabi-v7a/libjnidispatch.so", "size_bytes": 126496, "sha256": "9652282ef31834281229370a354d56c1522fe36e93625169df99b3e346f76092", "platform": "Android", "arch": "armeabi-v7a"},
            {"path": "jni/armeabi/libjnidispatch.so", "size_bytes": 126980, "sha256": "101daa2222382f3727800c0c49731346c5c4f81f1ecf1fde85ebcea64b151901", "platform": "Android", "arch": "armeabi"},
            {"path": "jni/mips/libjnidispatch.so", "size_bytes": 130556, "sha256": "eb549d34eb17b394f4ba74c21c51f41340d8b049aa90cc9feaef734695890402", "platform": "Android", "arch": "mips"},
            {"path": "jni/mips64/libjnidispatch.so", "size_bytes": 150256, "sha256": "93f5b0bec919b95160db0bf35c5ed6904d4d48f282501f0ff4a85f6511f3e44d", "platform": "Android", "arch": "mips64"},
            {"path": "jni/x86/libjnidispatch.so", "size_bytes": 124380, "sha256": "d10fcc75029621a88fa6020807e7ba82ff434a01ead396cf0e36c50e6c393118", "platform": "Android", "arch": "x86"},
            {"path": "jni/x86_64/libjnidispatch.so", "size_bytes": 126912, "sha256": "3809247e9b804a05ed8377b87d545cf5b5e97f960f75e725bc8497b40260e417", "platform": "Android", "arch": "x86_64"},
        ],
        "note": (
            "JNA is both a direct SDK dependency and its own native carrier. "
            "Only one of the 27 `.jar`-packaged platform-specific "
            "libjnidispatch binaries loads at runtime per host; a JVM-only "
            "consumer's jar as distributed contains all 27. Android "
            "consumers instead resolve the separate `.aar` variant (see "
            "additional_artifacts above), which bundles only the 7 "
            "Android-ABI-named binaries also listed here -- 34 total rows, "
            "not 27, once both real, resolved artifacts of this coordinate "
            "are counted. A prior version of this catalog said 25 -- aix-ppc "
            "and aix-ppc64 were missed; corrected here after a full zip-member "
            "enumeration. Do not classify JNA as a source-only dependency."
        ),
    },
)

VALID_CARRIER_DISTRIBUTION_STATUSES = (
    "resolved_runtime_dependency",
    "transitively_available",
    "redistributed_by_kardano",
    "not_in_first_release_scope",
)

# Archive member extensions treated as "native code" for discovery purposes.
# `.a` is included because JNA ships AIX static archives inside its jar
# (see the JNA carrier above); a bare static archive is still native object
# code subject to the same review requirement as a shared library.
NATIVE_MEMBER_EXTENSIONS = (".so", ".dll", ".dylib", ".jnilib", ".a")

# Magic-byte sniffing is applied to EVERY non-directory archive member,
# regardless of its filename extension -- a native payload packaged with a
# misleading extension (`payload.bin`, `.dat`, even a `.class`-suffixed
# file) or no extension at all must not be able to evade discovery merely
# by its name. Three magic families below (fat Mach-O, PE, XCOFF) are
# deliberately NOT in this flat list, because a bare 4-byte (or 2-byte)
# prefix match is not sufficient evidence for them: each needs its own
# bounded structural parse (`_validate_fat_macho_structure`,
# `_validate_pe_structure`, `_validate_xcoff_structure` below) before this
# generator will call it a genuine native member, and a member whose
# prefix matches one of those magics but fails that structural parse is a
# hard failure (`"malformed_native_magic"`), never silently `"not_native"`.
NATIVE_MAGIC_SIGNATURES: tuple[bytes, ...] = (
    b"\x7fELF",  # ELF (Linux/BSD/Solaris shared objects and executables)
    b"\xfe\xed\xfa\xce",  # Mach-O 32-bit (thin)
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit (thin)
    b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit (thin), reversed byte order
    b"\xce\xfa\xed\xfe",  # Mach-O 32-bit (thin), reversed byte order
    b"!<arch>\n",  # BSD/System-V ar archive (static library container, e.g. .a)
)
MAX_NATIVE_MAGIC_PREFIX_LEN = 8

# Mach-O "fat"/universal binary magic numbers (mach-o/fat.h), all four
# valid combinations of 32/64-bit and byte order. Apple's own convention
# writes the fat header big-endian on disk (`FAT_MAGIC`/`FAT_MAGIC_64`);
# `FAT_CIGAM`/`FAT_CIGAM_64` are the byte-swapped values a little-endian
# reader would see if the header were instead written in native/swapped
# order -- both this generator's own comparisons below and any other tool
# checking either byte pattern is intentional here, not a workaround for
# one specific ambiguous encoding.
#   FAT_MAGIC    = 0xcafebabe -> bytes CA FE BA BE (big-endian, 32-bit arch entries)
#   FAT_CIGAM    = 0xbebafeca -> bytes BE BA FE CA (little-endian, 32-bit arch entries)
#   FAT_MAGIC_64 = 0xcafebabf -> bytes CA FE BA BF (big-endian, 64-bit arch entries)
#   FAT_CIGAM_64 = 0xbfbafeca -> bytes BF BA FE CA (little-endian, 64-bit arch entries)
# Maps each magic to (bits, byte order of every subsequent header field).
FAT_MACHO_MAGIC_VARIANTS: dict[bytes, tuple[int, str]] = {
    b"\xca\xfe\xba\xbe": (32, "big"),
    b"\xbe\xba\xfe\xca": (32, "little"),
    b"\xca\xfe\xba\xbf": (64, "big"),
    b"\xbf\xba\xfe\xca": (64, "little"),
}
FAT_MACHO_HEADER_SIZE = 8  # magic (4) + nfat_arch (4)
FAT_MACHO_ARCH_ENTRY_SIZE_32 = 20  # cputype/cpusubtype/offset/size/align, all u32
FAT_MACHO_ARCH_ENTRY_SIZE_64 = 32  # + 64-bit offset/size + a reserved u32

# `CAFEBABE` (the 32-bit big-endian `FAT_MAGIC` variant above) is ALSO,
# by deliberate historical Sun/Apple naming coincidence and not a bug in
# either format, the exact same 4 bytes every Java `.class` file starts
# with. A jar's `.class` files vastly outnumber any real native member in
# this dependency graph, so this one specific magic (and only this one --
# the other three fat variants below have no such legitimate collision)
# gets a `"not_native"` fallback when it fails full structural validation,
# instead of the hard `"malformed_native_magic"` failure every other
# native-magic mismatch gets. The two formats diverge in their next 4
# bytes: a fat Mach-O's are `nfat_arch` (a big-endian count of the
# fat_arch structs that follow), while a class file's are
# `minor_version`(u2) then `major_version`(u2) -- and every real
# major_version Java has ever shipped (45 for JDK 1.1, increasing
# monotonically since) is far above any plausible architecture-slice
# count a real fat binary would use. Empirically confirmed 2026-08-24
# against real, currently-resolved artifacts in this repository's own
# dependency graph: the IonSpin libsodium JVM jar's
# `libdynamic-macos.dylib` (a genuine universal arm64+x86-64 fat Mach-O)
# has `nfat_arch == 2`, while `androidx.annotation:annotation-jvm`'s real
# `.class` files have `major_version == 52` (JDK 8).
JAVA_CLASS_COLLISION_FAT_MACHO_MAGIC = b"\xca\xfe\xba\xbe"

# Standard, exact-case `.class` suffix per the ZIP/JAR convention every
# real Java toolchain (javac, the JVM's own class loaders, jar/zip
# tooling) uses -- Java class-file member names are always emitted with
# a lowercase `.class` extension, never `.Class`/`.CLASS`/mixed case.
# This is a deliberate, explicit case policy: a member named with any
# other casing does NOT get the Java-class collision fallback below, no
# matter how well-formed its payload is, and instead fails closed as
# `"malformed_native_magic"` if it also fails the fat-Mach-O structural
# parse. This is intentionally the ONLY extension checked for the
# fallback -- unlike native extensions, there is no "renamed .class"
# concept to support here, since the whole point of the fallback is that
# `.class` is this collision's one common, legitimate, well-known name.
JAVA_CLASS_MEMBER_SUFFIX = ".class"

MAX_PLAUSIBLE_FAT_MACHO_ARCH_COUNT = 20

# Real Apple Mach-O `cputype` values this generator has ever actually
# needed to accept (mach/machine.h) -- deliberately an allowlist, not a
# "non-zero" heuristic, so a structurally-well-formed-looking but bogus
# cputype still fails closed as implausible rather than being guessed at.
# `CPU_ARCH_ABI64 = 0x01000000` / `CPU_ARCH_ABI64_32 = 0x02000000` are the
# 64-bit-variant mask bits Apple ORs into the matching 32-bit base type.
_MACHO_CPU_ARCH_ABI64 = 0x01000000
_MACHO_CPU_ARCH_ABI64_32 = 0x02000000
KNOWN_MACHO_CPU_TYPES = frozenset(
    {
        1,  # VAX
        6,  # MC680x0
        7,  # X86 / I386
        8,  # MIPS
        10,  # MC98000
        11,  # HPPA
        12,  # ARM
        13,  # MC88000
        14,  # SPARC
        15,  # I860
        18,  # POWERPC
        7 | _MACHO_CPU_ARCH_ABI64,  # X86_64
        12 | _MACHO_CPU_ARCH_ABI64,  # ARM64
        12 | _MACHO_CPU_ARCH_ABI64_32,  # ARM64_32
        18 | _MACHO_CPU_ARCH_ABI64,  # POWERPC64
    }
)
MAX_PLAUSIBLE_MACHO_ARCH_ALIGN_SHIFT = 31  # `align` is a power-of-two exponent


def _validate_fat_macho_structure(data: bytes) -> bool:
    """Structurally validate a Mach-O fat/universal binary header, not just
    its 4-byte magic.

    Parses a BOUNDED fat header (magic + `nfat_arch`) and every 32- or
    64-bit `fat_arch` entry the header claims, per this file's own
    matched-variant byte order (never assumed independently of which
    magic matched). Requires: `nfat_arch` in a plausible range (never a
    length taken on faith -- see `MAX_PLAUSIBLE_FAT_MACHO_ARCH_COUNT`);
    the full header AND arch table actually fit within `data` (no
    allocation or slice ever extends past what was actually read); at
    least one arch entry; every entry's `cputype` is one of
    `KNOWN_MACHO_CPU_TYPES` and `align` is a plausible shift amount; every
    entry's `[offset, offset + size)` byte range is entirely contained in
    `data`, starts at or after the end of the header/arch-table region
    (never overlapping it), has a strictly positive size, and does not
    overlap any other entry's range. Any violation returns `False` --
    callers decide the fail-closed consequence of that, this function
    never raises.
    """
    if len(data) < FAT_MACHO_HEADER_SIZE:
        return False
    variant = FAT_MACHO_MAGIC_VARIANTS.get(data[:4])
    if variant is None:
        return False
    bits, endian = variant
    nfat_arch = int.from_bytes(data[4:8], endian)
    if not (1 <= nfat_arch <= MAX_PLAUSIBLE_FAT_MACHO_ARCH_COUNT):
        return False
    entry_size = FAT_MACHO_ARCH_ENTRY_SIZE_32 if bits == 32 else FAT_MACHO_ARCH_ENTRY_SIZE_64
    header_end = FAT_MACHO_HEADER_SIZE + nfat_arch * entry_size
    total_size = len(data)
    if total_size < header_end:
        return False
    endian_prefix = ">" if endian == "big" else "<"
    fmt = f"{endian_prefix}iiIII" if bits == 32 else f"{endian_prefix}iiQQII"
    slices: list[tuple[int, int]] = []
    for index in range(nfat_arch):
        start = FAT_MACHO_HEADER_SIZE + index * entry_size
        entry = data[start : start + entry_size]
        fields = struct.unpack(fmt, entry)
        cputype, _cpusubtype, offset, size, align = fields[0], fields[1], fields[2], fields[3], fields[4]
        if cputype not in KNOWN_MACHO_CPU_TYPES:
            return False
        if not (0 <= align <= MAX_PLAUSIBLE_MACHO_ARCH_ALIGN_SHIFT):
            return False
        if size <= 0:
            return False
        if offset < header_end:
            return False
        if offset + size > total_size:
            return False
        slices.append((offset, offset + size))
    slices.sort()
    for (_start, end), (next_start, _next_end) in zip(slices, slices[1:]):
        if next_start < end:
            return False
    return True


# Windows PE/COFF (`MZ` DOS stub -> `e_lfanew` -> "PE\0\0" -> COFF file
# header -> optional header -> section table), all fields little-endian
# per the PE/COFF spec. Bounds below are deliberately generous (real
# toolchains rarely approach them) but still finite, so a claimed
# section/optional-header size can never justify an unbounded read.
PE_DOS_HEADER_SIZE = 64  # sizeof(IMAGE_DOS_HEADER); e_lfanew is the last field, at offset 0x3C
PE_E_LFANEW_OFFSET = 0x3C
PE_SIGNATURE = b"PE\x00\x00"
PE_COFF_HEADER_SIZE = 20  # sizeof(IMAGE_FILE_HEADER), immediately after the 4-byte "PE\0\0"
PE_SECTION_HEADER_SIZE = 40  # sizeof(IMAGE_SECTION_HEADER)
MAX_PLAUSIBLE_PE_SECTION_COUNT = 96
MAX_PLAUSIBLE_PE_OPTIONAL_HEADER_SIZE = 512
# IMAGE_FILE_HEADER.Machine values this generator has ever actually needed
# to accept -- an allowlist, same rationale as KNOWN_MACHO_CPU_TYPES.
KNOWN_PE_MACHINE_TYPES = frozenset(
    {
        0x014C,  # IMAGE_FILE_MACHINE_I386
        0x0200,  # IMAGE_FILE_MACHINE_IA64
        0x8664,  # IMAGE_FILE_MACHINE_AMD64
        0x01C0,  # IMAGE_FILE_MACHINE_ARM
        0x01C4,  # IMAGE_FILE_MACHINE_ARMNT (ARMv7 Thumb-2)
        0xAA64,  # IMAGE_FILE_MACHINE_ARM64
    }
)


def _validate_pe_structure(data: bytes) -> bool:
    """Structurally validate a Windows PE/COFF image, not just its `MZ`
    prefix.

    An ordinary text file (or any other non-PE data) that happens to
    start with `MZ` must fail this, not silently pass as native: requires
    the full minimum DOS header, a plausible `e_lfanew` pointing to an
    exact `"PE\\0\\0"` signature entirely within `data`, a plausible COFF
    file header (allowlisted `Machine`, in-range `NumberOfSections`,
    in-range `SizeOfOptionalHeader`), and a section table that -- given
    those two counts -- fits entirely within `data`. Every offset is
    checked against `len(data)` before it is ever used to slice, so a
    huge claimed `e_lfanew`/section count fails the bound check rather
    than allocating or reading anything untrusted. Never raises.
    """
    if len(data) < PE_DOS_HEADER_SIZE or data[:2] != b"MZ":
        return False
    e_lfanew = int.from_bytes(data[PE_E_LFANEW_OFFSET : PE_E_LFANEW_OFFSET + 4], "little")
    if e_lfanew < PE_DOS_HEADER_SIZE:
        return False
    pe_sig_end = e_lfanew + 4
    if pe_sig_end > len(data):
        return False
    if data[e_lfanew:pe_sig_end] != PE_SIGNATURE:
        return False
    coff_end = pe_sig_end + PE_COFF_HEADER_SIZE
    if coff_end > len(data):
        return False
    coff = data[pe_sig_end:coff_end]
    machine = int.from_bytes(coff[0:2], "little")
    num_sections = int.from_bytes(coff[2:4], "little")
    size_optional_header = int.from_bytes(coff[16:18], "little")
    if machine not in KNOWN_PE_MACHINE_TYPES:
        return False
    if not (1 <= num_sections <= MAX_PLAUSIBLE_PE_SECTION_COUNT):
        return False
    if not (0 <= size_optional_header <= MAX_PLAUSIBLE_PE_OPTIONAL_HEADER_SIZE):
        return False
    sections_end = coff_end + size_optional_header + num_sections * PE_SECTION_HEADER_SIZE
    return sections_end <= len(data)


# AIX XCOFF object/executable file headers. Both the 32- and 64-bit
# variants place `f_nscns` (section count) at the same byte offset (2)
# and `f_opthdr` (optional-header size) at the same byte offset (16),
# despite differing total header sizes, because the wider 64-bit
# `f_symptr` field absorbs exactly the size difference of the fields
# ahead of it -- this is a real, documented property of the two struct
# layouts (`struct external_filehdr` for 32-bit XCOFF is 20 bytes;
# for 64-bit XCOFF it is 24 bytes), not a simplification. XCOFF, unlike
# PE, has no little-endian on-disk variant on AIX; both magics are
# checked as fixed big-endian byte strings.
XCOFF32_MAGIC = b"\x01\xdf"
XCOFF64_MAGIC = b"\x01\xf7"
XCOFF32_FILEHDR_SIZE = 20
XCOFF64_FILEHDR_SIZE = 24
XCOFF32_SCNHDR_SIZE = 40
XCOFF64_SCNHDR_SIZE = 72
XCOFF_NSCNS_OFFSET = 2
XCOFF_OPTHDR_OFFSET = 16
MAX_PLAUSIBLE_XCOFF_SECTION_COUNT = 96
MAX_PLAUSIBLE_XCOFF_OPTIONAL_HEADER_SIZE = 4096


def _validate_xcoff_structure(data: bytes) -> bool:
    """Structurally validate an AIX XCOFF32/XCOFF64 object, not just its
    2-byte magic.

    Requires the recognized magic's own minimum file header to actually
    fit in `data`, a plausible section count and optional-header size
    (never a length taken on faith), and a section-header table that --
    given those two counts -- fits entirely within `data`. A short
    magic-prefixed member that cannot even hold the minimum file header
    fails immediately, before any field is read. Never raises.
    """
    if data[:2] == XCOFF32_MAGIC:
        filehdr_size, scnhdr_size = XCOFF32_FILEHDR_SIZE, XCOFF32_SCNHDR_SIZE
    elif data[:2] == XCOFF64_MAGIC:
        filehdr_size, scnhdr_size = XCOFF64_FILEHDR_SIZE, XCOFF64_SCNHDR_SIZE
    else:
        return False
    if len(data) < filehdr_size:
        return False
    nscns = int.from_bytes(data[XCOFF_NSCNS_OFFSET : XCOFF_NSCNS_OFFSET + 2], "big")
    opthdr = int.from_bytes(data[XCOFF_OPTHDR_OFFSET : XCOFF_OPTHDR_OFFSET + 2], "big")
    if not (1 <= nscns <= MAX_PLAUSIBLE_XCOFF_SECTION_COUNT):
        return False
    if not (0 <= opthdr <= MAX_PLAUSIBLE_XCOFF_OPTIONAL_HEADER_SIZE):
        return False
    table_end = filehdr_size + opthdr + nscns * scnhdr_size
    return table_end <= len(data)


def _member_has_native_extension(name: str) -> bool:
    basename = name.rsplit("/", 1)[-1]
    lower = basename.lower()
    return any(lower.endswith(ext) for ext in NATIVE_MEMBER_EXTENSIONS)


def _member_has_exact_java_class_suffix(name: str) -> bool:
    """Exact-case `.class` check -- see `JAVA_CLASS_MEMBER_SUFFIX` for the
    explicit case policy this deliberately enforces (never
    case-insensitive, unlike `_member_has_native_extension`).
    """
    basename = name.rsplit("/", 1)[-1]
    return basename.endswith(JAVA_CLASS_MEMBER_SUFFIX)


class _JavaClassParseError(Exception):
    """Internal-only control-flow signal for `_validate_java_class_structure`
    -- never escapes this module; every raise site here corresponds to one
    documented rejection reason (truncation, an unknown/malformed constant
    pool tag, an out-of-range count, an invalid index, or trailing bytes).
    """


class _BoundedJavaClassReader:
    """A strictly forward-only, bounds-checked cursor over one member's
    full byte content. Every read method raises `_JavaClassParseError`
    immediately if the requested field would extend past `data`'s actual
    length -- this is the parser's ENTIRE truncation/overflow defense:
    no length field is ever trusted to allocate or skip past what was
    actually read, and `constant_pool_count`/`interfaces_count`/
    `fields_count`/`methods_count`/`attributes_count`/`attribute_length`
    are all bounded by this, not by a separate fixed constant, per their
    own u2/u4 field width and the member's real remaining byte count.
    """

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def _remaining(self) -> int:
        return len(self.data) - self.pos

    def read_bytes(self, count: int) -> bytes:
        if count < 0 or self._remaining() < count:
            raise _JavaClassParseError("truncated")
        chunk = self.data[self.pos : self.pos + count]
        self.pos += count
        return chunk

    def read_u1(self) -> int:
        return self.read_bytes(1)[0]

    def read_u2(self) -> int:
        return int.from_bytes(self.read_bytes(2), "big")

    def read_u4(self) -> int:
        return int.from_bytes(self.read_bytes(4), "big")

    def skip(self, count: int) -> None:
        self.read_bytes(count)

    def at_exact_eof(self) -> bool:
        return self._remaining() == 0


# JVMS Table 4.4-A constant-pool tags this parser recognizes. Any tag
# byte not in this set is an unknown/unsupported tag and fails parsing
# immediately -- never guessed at or skipped with an assumed size.
JAVA_CP_TAG_UTF8 = 1
JAVA_CP_TAG_INTEGER = 3
JAVA_CP_TAG_FLOAT = 4
JAVA_CP_TAG_LONG = 5
JAVA_CP_TAG_DOUBLE = 6
JAVA_CP_TAG_CLASS = 7
JAVA_CP_TAG_STRING = 8
JAVA_CP_TAG_FIELDREF = 9
JAVA_CP_TAG_METHODREF = 10
JAVA_CP_TAG_INTERFACE_METHODREF = 11
JAVA_CP_TAG_NAME_AND_TYPE = 12
JAVA_CP_TAG_METHOD_HANDLE = 15
JAVA_CP_TAG_METHOD_TYPE = 16
JAVA_CP_TAG_DYNAMIC = 17
JAVA_CP_TAG_INVOKE_DYNAMIC = 18
JAVA_CP_TAG_MODULE = 19
JAVA_CP_TAG_PACKAGE = 20

# CONSTANT_Long/CONSTANT_Double each occupy TWO constant-pool indices
# (JVMS §4.4.5): "the constant_pool index n+1 must be considered
# invalid/unusable" for the entry directly after either -- this parser
# enforces that by advancing the running index by 2 (never recording a
# tag for the phantom second slot), so any later reference to that
# phantom index correctly fails the class/UTF8 index checks below.
JAVA_CP_DOUBLE_SLOT_TAGS = frozenset({JAVA_CP_TAG_LONG, JAVA_CP_TAG_DOUBLE})

# JVMS SE21 §4.1 Table 4.1-A lists major versions 45 (Java SE 1.0.2)
# through 65 (Java SE 21) explicitly by name; every constant-pool tag,
# MIN_MAJOR_VERSION floor, and attribute-layout rule this file
# implements is cited against that same JVMS edition, and none of them
# have changed for any major version above 56 -- JVMS §4.1's own
# "historical perspective" paragraph documents the minor_version rule
# (0 or 65535) as a STABLE, intentionally-extensible pattern that every
# subsequent JDK continues unchanged for its own new major version, not
# something that needs re-deriving release by release.
#
# This ceiling is fail-closed and evidence-pinned, NOT a speculative
# buffer: it is set to EXACTLY the highest major_version this SDK has
# actually evidenced in a real, currently-used dependency, and no
# higher. A 2026-08-24 direct inspection of the `.class` files inside
# the resolved `org.bouncycastle:bcprov-jdk18on` jar (this exact
# dependency's presence in this SDK's own resolved module graph is
# recorded in `docs/evidence/gradle_dependency_inventory.json` and
# `docs/evidence/gradle_license_inventory.json`) found it is a
# multi-release jar shipping classes under `META-INF/versions/25/` with
# major_version 69 (Java SE 25) -- and no evidenced dependency anywhere
# in that same resolved module graph exceeds major_version 69. Every
# constant-pool tag and attribute-layout rule this parser implements is
# independently
# unaffected by how high this ceiling is raised (an unknown
# constant-pool tag is rejected via the tag dispatch's own `else`
# branch, not gated by this ceiling), so this ceiling's ONLY job is
# refusing to silently vouch for a major_version this SDK has never
# actually needed to accept. Raising it past 69 requires a REVIEWED
# reason -- a newer real dependency (with its own major version bumping
# this constant AND this comment AND
# `MethodHandleTargetNameSemanticsTests`/`JavaClassStructuralValidationTests`
# tests to prove it) or a toolchain update, never a reflexive
# widen-to-be-safe buffer "just in case" a future dependency needs more
# room. Majors 70 and above fail closed today, even though many of them
# almost certainly follow the exact same stable minor_version pattern
# above -- this validator does not vouch for major versions it has
# never actually needed to parse.
MIN_SUPPORTED_JAVA_CLASS_MAJOR_VERSION = 45  # JVMS SE21 Table 4.1-A: Java SE 1.0.2
MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION = 69  # highest EVIDENCED major (bcprov-jdk18on, Java SE 25) -- see comment above


def _is_supported_java_class_version(major_version: int, minor_version: int) -> bool:
    """JVMS §4.1's own minor_version rule (as revised by JVMS SE21) is
    lenient: "between 45 and 55 inclusive, the minor_version may be any
    value" and "56 or above, the minor_version must be 0 or 65535". This
    validator deliberately narrows that for majors 45-55, matching what
    every real compiler has ever actually emitted per JVMS §4.1's own
    historical-perspective note: JDK 1.0.2 used minor versions 0-3 under
    major 45 (`45.0` through `45.3`), and every JDK from 1.2 onward that
    introduced a new major version (46 through 55) used ONLY minor 0
    under it. A minor_version outside those observed-in-the-wild values
    is non-canonical for a major in that range and is rejected here,
    same fail-closed posture as every other "reject non-canonical input,
    never normalize it" rule in this file -- even though the bare JVMS
    text would technically tolerate it. Majors 56 and above keep the
    spec's own 0-or-65535 (preview) rule exactly, up to this file's own
    `MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION` ceiling; nothing above that
    ceiling is accepted regardless of its minor_version.
    """
    if major_version == 45:
        return minor_version in (0, 1, 2, 3)
    if 46 <= major_version <= 55:
        return minor_version == 0
    if 56 <= major_version <= MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION:
        return minor_version in (0, 65535)
    return False

# JVMS Table 4.4-B: the class-file-format version each tag was first
# defined in. A tag not listed here (the 45.3-original ten: Utf8,
# Integer, Float, Long, Double, Class, String, Fieldref, Methodref,
# InterfaceMethodref, NameAndType) has no additional version floor
# beyond this file's own MIN_SUPPORTED_JAVA_CLASS_MAJOR_VERSION. A class
# file whose own major_version predates a tag it uses could never have
# been produced by any real, spec-conforming compiler for that version.
JAVA_CP_TAG_MIN_MAJOR_VERSION: dict[int, int] = {
    JAVA_CP_TAG_METHOD_HANDLE: 51,
    JAVA_CP_TAG_METHOD_TYPE: 51,
    JAVA_CP_TAG_INVOKE_DYNAMIC: 51,
    JAVA_CP_TAG_MODULE: 53,
    JAVA_CP_TAG_PACKAGE: 53,
    JAVA_CP_TAG_DYNAMIC: 55,
}


def _is_valid_modified_utf8(data: bytes) -> bool:
    """Validate `data` as Modified UTF-8 per JVMS §4.4.7 -- deliberately
    NOT ordinary UTF-8/CESU-8: this enforces every difference the spec
    calls out explicitly (raw NUL forbidden -- code point 0 may ONLY
    appear as the exact 2-byte overlong form `C0 80`; no byte may be in
    `0xF0`-`0xFF` at all, i.e. the standard 4-byte lead-byte form is
    never recognized -- supplementary characters instead use the
    6-byte/two-surrogate form below), plus rejects every other overlong
    encoding (a 2- or 3-byte sequence whose decoded value could have
    used a shorter form is illegal, `C0 80` being the sole documented
    exception), truncated sequences, and stray/malformed continuation
    bytes. A 3-byte sequence decoding to a UTF-16 high surrogate
    (U+D800-U+DBFF) must be immediately followed by another 3-byte
    sequence decoding to a matching low surrogate (U+DC00-U+DFFF) --
    exactly the "separately encoding the two surrogate code units"
    6-byte supplementary-character form the spec describes; an unpaired
    high or low surrogate is rejected as malformed rather than passed
    through, since this generator treats any such ambiguity as
    non-canonical input to reject, not normalize. Never raises; bounded
    entirely by `len(data)` (no allocation from any decoded value).
    """
    i = 0
    n = len(data)
    while i < n:
        b0 = data[i]
        if b0 == 0x00:
            return False  # raw NUL forbidden -- must be encoded as C0 80
        if b0 <= 0x7F:
            i += 1
            continue
        if 0x80 <= b0 <= 0xBF:
            return False  # stray continuation byte used as a lead byte
        if 0xC0 <= b0 <= 0xDF:
            if i + 1 >= n:
                return False  # truncated 2-byte sequence
            b1 = data[i + 1]
            if not (0x80 <= b1 <= 0xBF):
                return False  # malformed continuation byte
            value = ((b0 & 0x1F) << 6) | (b1 & 0x3F)
            if 1 <= value <= 0x7F:
                return False  # illegal overlong encoding of an ASCII code point
            # value == 0 is reachable ONLY via the exact bytes C0 80
            # (b0 & 0x1F == 0 forces b0 == 0xC0; b1 & 0x3F == 0 forces
            # b1 == 0x80 given b1 is already constrained to 0x80-0xBF) --
            # the documented NUL exception falls out of the arithmetic
            # itself, needing no separate special case.
            i += 2
            continue
        if 0xE0 <= b0 <= 0xEF:
            if i + 2 >= n:
                return False  # truncated 3-byte sequence
            b1, b2 = data[i + 1], data[i + 2]
            if not (0x80 <= b1 <= 0xBF and 0x80 <= b2 <= 0xBF):
                return False  # malformed continuation byte(s)
            value = ((b0 & 0x0F) << 12) | ((b1 & 0x3F) << 6) | (b2 & 0x3F)
            if value < 0x800:
                return False  # illegal overlong encoding
            if 0xD800 <= value <= 0xDBFF:
                # High surrogate: must be immediately followed by a
                # matching low-surrogate 3-byte sequence (the spec's
                # 6-byte supplementary-character form) -- an unpaired
                # high surrogate is rejected, never passed through.
                if i + 5 >= n:
                    return False  # truncated surrogate pair
                b3, b4, b5 = data[i + 3], data[i + 4], data[i + 5]
                if not (0xE0 <= b3 <= 0xEF and 0x80 <= b4 <= 0xBF and 0x80 <= b5 <= 0xBF):
                    return False
                low = ((b3 & 0x0F) << 12) | ((b4 & 0x3F) << 6) | (b5 & 0x3F)
                if not (0xDC00 <= low <= 0xDFFF):
                    return False  # not a valid low surrogate -- unpaired high surrogate
                i += 6
                continue
            if 0xDC00 <= value <= 0xDFFF:
                return False  # unpaired low surrogate (no preceding matched high surrogate)
            i += 3
            continue
        return False  # 0xF0-0xFF: never a valid lead byte in modified UTF-8
    return True


def _parse_java_class_constant_pool(
    reader: _BoundedJavaClassReader, constant_pool_count: int, major_version: int
) -> tuple[dict[int, int], dict[int, tuple[int, ...]], dict[int, bytes]]:
    """Parse every constant-pool entry.

    Returns `(tags, refs, utf8_values)`: `tags` maps every OCCUPIED index
    (1-based; index 0 is always unused, and a Long/Double's phantom
    second slot is deliberately never a key) to its tag byte. `refs`
    maps every index whose entry carries one or more
    constant-pool-index-valued fields to the raw (unvalidated) tuple of
    those field values, in declaration order -- see
    `_validate_java_cp_references` for what each tag's tuple means and
    how it is cross-checked, which happens only AFTER every entry has
    been parsed here (constant-pool references may legally point
    forward to an entry not yet seen). `utf8_values` maps every Utf8
    entry's index to its already Modified-UTF8-validated raw byte
    content, used later to resolve a MethodHandle's semantic target
    method NAME (e.g. `<init>`/`<clinit>`) -- see
    `_resolve_java_method_handle_target_name`. Comparisons against those
    exact ASCII literals are always done on these raw bytes, never on a
    decoded `str`: both names are pure ASCII, and Modified UTF-8 encodes
    every ASCII byte as itself, so no decoding step can change whether a
    byte-for-byte match holds.

    Raises `_JavaClassParseError` on an unknown tag, a tag whose
    class-file-format version (JVMS Table 4.4-B, `JAVA_CP_TAG_MIN_MAJOR_VERSION`)
    exceeds this class file's own `major_version`, invalid Modified
    UTF-8 content in a Utf8 entry, a Long/Double whose reserved
    successor slot is not itself in range, or truncation -- never
    guesses a body size for a tag it does not recognize.
    """
    tags: dict[int, int] = {}
    refs: dict[int, tuple[int, ...]] = {}
    utf8_values: dict[int, bytes] = {}
    index = 1
    while index < constant_pool_count:
        tag = reader.read_u1()
        min_version = JAVA_CP_TAG_MIN_MAJOR_VERSION.get(tag)
        if min_version is not None and major_version < min_version:
            raise _JavaClassParseError(
                f"constant pool tag {tag} requires class file major_version >= "
                f"{min_version}, but this class file declares {major_version}"
            )
        if tag == JAVA_CP_TAG_UTF8:
            length = reader.read_u2()
            utf8_bytes = reader.read_bytes(length)
            if not _is_valid_modified_utf8(utf8_bytes):
                raise _JavaClassParseError(f"Utf8 entry {index} is not valid Modified UTF-8")
            tags[index] = tag
            utf8_values[index] = utf8_bytes
            index += 1
        elif tag in (JAVA_CP_TAG_INTEGER, JAVA_CP_TAG_FLOAT):
            reader.skip(4)
            tags[index] = tag
            index += 1
        elif tag in JAVA_CP_DOUBLE_SLOT_TAGS:
            # JVMS §4.4.5: a Long/Double occupies two consecutive
            # constant_pool entries; the second (index+1) "must be valid
            # but is considered unusable". "Valid" here is the same
            # general constant_pool-index rule as everywhere else in
            # JVMS §4.1 (greater than zero, less than
            # constant_pool_count) -- so a Long/Double may NOT be placed
            # such that its reserved successor slot would fall at or
            # beyond constant_pool_count. This is stricter than merely
            # "the phantom slot is never dereferenced": no real,
            # spec-conforming compiler could ever emit a Long/Double
            # whose reserved slot has no legal index at all.
            if index + 1 >= constant_pool_count:
                raise _JavaClassParseError(
                    f"Long/Double entry {index} leaves no in-range reserved "
                    f"successor slot (index+1={index + 1} >= "
                    f"constant_pool_count={constant_pool_count})"
                )
            reader.skip(8)
            tags[index] = tag
            index += 2
        elif tag == JAVA_CP_TAG_CLASS:
            refs[index] = (reader.read_u2(),)  # name_index
            tags[index] = tag
            index += 1
        elif tag == JAVA_CP_TAG_STRING:
            refs[index] = (reader.read_u2(),)  # string_index
            tags[index] = tag
            index += 1
        elif tag in (JAVA_CP_TAG_FIELDREF, JAVA_CP_TAG_METHODREF, JAVA_CP_TAG_INTERFACE_METHODREF):
            refs[index] = (reader.read_u2(), reader.read_u2())  # class_index, name_and_type_index
            tags[index] = tag
            index += 1
        elif tag == JAVA_CP_TAG_NAME_AND_TYPE:
            refs[index] = (reader.read_u2(), reader.read_u2())  # name_index, descriptor_index
            tags[index] = tag
            index += 1
        elif tag == JAVA_CP_TAG_METHOD_HANDLE:
            refs[index] = (reader.read_u1(), reader.read_u2())  # reference_kind, reference_index
            tags[index] = tag
            index += 1
        elif tag == JAVA_CP_TAG_METHOD_TYPE:
            refs[index] = (reader.read_u2(),)  # descriptor_index
            tags[index] = tag
            index += 1
        elif tag in (JAVA_CP_TAG_DYNAMIC, JAVA_CP_TAG_INVOKE_DYNAMIC):
            refs[index] = (reader.read_u2(), reader.read_u2())  # bootstrap_method_attr_index, name_and_type_index
            tags[index] = tag
            index += 1
        elif tag in (JAVA_CP_TAG_MODULE, JAVA_CP_TAG_PACKAGE):
            refs[index] = (reader.read_u2(),)  # name_index
            tags[index] = tag
            index += 1
        else:
            raise _JavaClassParseError(f"unknown constant pool tag {tag}")
    return tags, refs, utf8_values


def _java_cp_index_has_tag(tags: dict[int, int], index: int, expected_tag: int) -> bool:
    return index != 0 and tags.get(index) == expected_tag


# JVMS §4.4.8: reference_kind values 1-4 (REF_getField/getStatic/
# putField/putStatic) target a Fieldref; 5 (REF_invokeVirtual) and 8
# (REF_newInvokeSpecial) target a Methodref; 9 (REF_invokeInterface)
# targets an InterfaceMethodref. Kinds 6/7 (REF_invokeStatic/
# REF_invokeSpecial) are handled separately below since their allowed
# target tag(s) depend on this class file's own major_version.
_JAVA_METHOD_HANDLE_FIXED_KIND_TARGET_TAGS: dict[int, tuple[int, ...]] = {
    1: (JAVA_CP_TAG_FIELDREF,),
    2: (JAVA_CP_TAG_FIELDREF,),
    3: (JAVA_CP_TAG_FIELDREF,),
    4: (JAVA_CP_TAG_FIELDREF,),
    5: (JAVA_CP_TAG_METHODREF,),
    8: (JAVA_CP_TAG_METHODREF,),
    9: (JAVA_CP_TAG_INTERFACE_METHODREF,),
}
_JAVA_METHOD_HANDLE_VERSION_DEPENDENT_KINDS = frozenset({6, 7})
_JAVA_METHOD_HANDLE_VERSION_DEPENDENT_MIN_MAJOR_VERSION_FOR_INTERFACE_TARGET = 52

# JVMS §4.4.8, the paragraph on reference_kind: reference_kind 8
# (REF_newInvokeSpecial) requires the target Methodref's method name to
# be exactly `<init>`; reference_kinds 5 (REF_invokeVirtual), 6
# (REF_invokeStatic), 7 (REF_invokeSpecial), and 9 (REF_invokeInterface)
# require it NOT be `<init>` or `<clinit>`. Kinds 1-4 (field
# get/put-Field/Static) carry no such name restriction -- field names
# have no `<init>`/`<clinit>` special meaning.
_JAVA_METHOD_HANDLE_KINDS_REQUIRING_INIT_NAME = frozenset({8})
_JAVA_METHOD_HANDLE_KINDS_FORBIDDING_INIT_OR_CLINIT_NAME = frozenset({5, 6, 7, 9})
_JAVA_INIT_METHOD_NAME = b"<init>"
_JAVA_CLINIT_METHOD_NAME = b"<clinit>"


def _resolve_java_method_handle_target_name(
    tags: dict[int, int],
    refs: dict[int, tuple[int, ...]],
    utf8_values: dict[int, bytes],
    reference_index: int,
) -> bytes | None:
    """Resolve a MethodHandle's `reference_index` -> (Methodref or
    InterfaceMethodref) -> `name_and_type_index` -> NameAndType ->
    `name_index` -> Utf8 chain down to the target method's raw name
    bytes, for the `<init>`/`<clinit>` semantic checks below.

    Returns `None` -- deliberately WITHOUT raising -- if `reference_index`
    does not resolve to a Methodref/InterfaceMethodref, or if any link
    further down the chain (`name_and_type_index` or `name_index`) does
    not itself carry the expected tag. Every one of those links is
    ALSO independently validated by its own owning entry's branch in
    `_validate_java_cp_references` (Methodref/InterfaceMethodref's own
    `name_and_type_index`, NameAndType's own `name_index`) as that same
    overall pass walks every index in `tags`, in whatever order that
    happens to be relative to this MethodHandle entry -- so a broken
    link here is always independently caught by, and reported from,
    that other branch; this function only needs to skip the semantic
    name check rather than duplicate that error.
    """
    if not (
        _java_cp_index_has_tag(tags, reference_index, JAVA_CP_TAG_METHODREF)
        or _java_cp_index_has_tag(tags, reference_index, JAVA_CP_TAG_INTERFACE_METHODREF)
    ):
        return None
    _class_index, name_and_type_index = refs[reference_index]
    if not _java_cp_index_has_tag(tags, name_and_type_index, JAVA_CP_TAG_NAME_AND_TYPE):
        return None
    name_index, _descriptor_index = refs[name_and_type_index]
    if not _java_cp_index_has_tag(tags, name_index, JAVA_CP_TAG_UTF8):
        return None
    return utf8_values.get(name_index)


def _validate_java_method_handle_reference(
    tags: dict[int, int],
    refs: dict[int, tuple[int, ...]],
    utf8_values: dict[int, bytes],
    reference_kind: int,
    reference_index: int,
    major_version: int,
) -> None:
    if not (1 <= reference_kind <= 9):
        raise _JavaClassParseError(f"MethodHandle reference_kind {reference_kind} outside valid range 1..9")
    if reference_kind in _JAVA_METHOD_HANDLE_VERSION_DEPENDENT_KINDS:
        allowed_tags = (
            (JAVA_CP_TAG_METHODREF,)
            if major_version < _JAVA_METHOD_HANDLE_VERSION_DEPENDENT_MIN_MAJOR_VERSION_FOR_INTERFACE_TARGET
            else (JAVA_CP_TAG_METHODREF, JAVA_CP_TAG_INTERFACE_METHODREF)
        )
    else:
        allowed_tags = _JAVA_METHOD_HANDLE_FIXED_KIND_TARGET_TAGS[reference_kind]
    if not any(_java_cp_index_has_tag(tags, reference_index, tag) for tag in allowed_tags):
        raise _JavaClassParseError(
            f"MethodHandle reference_index does not reference an entry with an "
            f"allowed tag {allowed_tags} for reference_kind {reference_kind}"
        )
    if (
        reference_kind in _JAVA_METHOD_HANDLE_KINDS_REQUIRING_INIT_NAME
        or reference_kind in _JAVA_METHOD_HANDLE_KINDS_FORBIDDING_INIT_OR_CLINIT_NAME
    ):
        name = _resolve_java_method_handle_target_name(tags, refs, utf8_values, reference_index)
        if name is not None:
            if reference_kind in _JAVA_METHOD_HANDLE_KINDS_REQUIRING_INIT_NAME and name != _JAVA_INIT_METHOD_NAME:
                raise _JavaClassParseError(
                    f"MethodHandle reference_kind 8 (REF_newInvokeSpecial) must target a "
                    f"method named exactly {_JAVA_INIT_METHOD_NAME!r}, found {name!r}"
                )
            if reference_kind in _JAVA_METHOD_HANDLE_KINDS_FORBIDDING_INIT_OR_CLINIT_NAME and name in (
                _JAVA_INIT_METHOD_NAME,
                _JAVA_CLINIT_METHOD_NAME,
            ):
                raise _JavaClassParseError(
                    f"MethodHandle reference_kind {reference_kind} must not target "
                    f"{name!r}"
                )


def _validate_java_cp_references(
    tags: dict[int, int], refs: dict[int, tuple[int, ...]], utf8_values: dict[int, bytes], major_version: int
) -> None:
    """Cross-check every constant-pool entry's own internal index
    field(s) against the now-COMPLETE `tags` map (built by
    `_parse_java_class_constant_pool`, which must run to completion
    first since references may point forward). Every reference must be
    nonzero, in range, and land on an entry with the exact tag JVMS §4.4
    requires for that field -- `_java_cp_index_has_tag` already rejects
    index 0, any out-of-range index, and any Long/Double's reserved
    phantom slot (which is never a key in `tags`), so no separate bounds
    check is needed here. For MethodHandle entries specifically, also
    resolves and checks the target method's semantic name (see
    `_resolve_java_method_handle_target_name`). Raises
    `_JavaClassParseError` on the first violation found; never raises
    for any tag that has no `refs` entry (Utf8/Integer/Float/Long/
    Double, which carry no cross-references).
    """
    for index, tag in tags.items():
        if tag == JAVA_CP_TAG_CLASS:
            (name_index,) = refs[index]
            if not _java_cp_index_has_tag(tags, name_index, JAVA_CP_TAG_UTF8):
                raise _JavaClassParseError(f"Class entry {index} name_index does not reference a Utf8 entry")
        elif tag == JAVA_CP_TAG_STRING:
            (string_index,) = refs[index]
            if not _java_cp_index_has_tag(tags, string_index, JAVA_CP_TAG_UTF8):
                raise _JavaClassParseError(f"String entry {index} string_index does not reference a Utf8 entry")
        elif tag in (JAVA_CP_TAG_FIELDREF, JAVA_CP_TAG_METHODREF, JAVA_CP_TAG_INTERFACE_METHODREF):
            class_index, name_and_type_index = refs[index]
            if not _java_cp_index_has_tag(tags, class_index, JAVA_CP_TAG_CLASS):
                raise _JavaClassParseError(f"ref entry {index} class_index does not reference a Class entry")
            if not _java_cp_index_has_tag(tags, name_and_type_index, JAVA_CP_TAG_NAME_AND_TYPE):
                raise _JavaClassParseError(
                    f"ref entry {index} name_and_type_index does not reference a NameAndType entry"
                )
        elif tag == JAVA_CP_TAG_NAME_AND_TYPE:
            name_index, descriptor_index = refs[index]
            if not _java_cp_index_has_tag(tags, name_index, JAVA_CP_TAG_UTF8):
                raise _JavaClassParseError(f"NameAndType entry {index} name_index does not reference a Utf8 entry")
            if not _java_cp_index_has_tag(tags, descriptor_index, JAVA_CP_TAG_UTF8):
                raise _JavaClassParseError(
                    f"NameAndType entry {index} descriptor_index does not reference a Utf8 entry"
                )
        elif tag == JAVA_CP_TAG_METHOD_HANDLE:
            reference_kind, reference_index = refs[index]
            _validate_java_method_handle_reference(
                tags, refs, utf8_values, reference_kind, reference_index, major_version
            )
        elif tag == JAVA_CP_TAG_METHOD_TYPE:
            (descriptor_index,) = refs[index]
            if not _java_cp_index_has_tag(tags, descriptor_index, JAVA_CP_TAG_UTF8):
                raise _JavaClassParseError(f"MethodType entry {index} descriptor_index does not reference a Utf8 entry")
        elif tag in (JAVA_CP_TAG_DYNAMIC, JAVA_CP_TAG_INVOKE_DYNAMIC):
            # bootstrap_method_attr_index indexes the BootstrapMethods
            # attribute's own table, not the constant pool -- this
            # parser does not parse that attribute (see
            # `_parse_java_class_attribute_list`), so only the
            # constant-pool-indexed field is cross-checked here.
            _bootstrap_method_attr_index, name_and_type_index = refs[index]
            if not _java_cp_index_has_tag(tags, name_and_type_index, JAVA_CP_TAG_NAME_AND_TYPE):
                raise _JavaClassParseError(
                    f"Dynamic/InvokeDynamic entry {index} name_and_type_index does not reference a NameAndType entry"
                )
        elif tag in (JAVA_CP_TAG_MODULE, JAVA_CP_TAG_PACKAGE):
            (name_index,) = refs[index]
            if not _java_cp_index_has_tag(tags, name_index, JAVA_CP_TAG_UTF8):
                raise _JavaClassParseError(f"Module/Package entry {index} name_index does not reference a Utf8 entry")


def _parse_java_class_member_list(reader: _BoundedJavaClassReader, tags: dict[int, int]) -> None:
    """Parse one `fields[]` or `methods[]` table (JVMS §4.5/§4.6 --
    identical shape: access_flags, name_index, descriptor_index,
    attributes_count, attributes[]). `name_index`/`descriptor_index`
    must each reference a CONSTANT_Utf8 entry. Raises
    `_JavaClassParseError` on any violation.
    """
    count = reader.read_u2()
    for _ in range(count):
        reader.read_u2()  # access_flags -- accepted as-is, not further validated
        name_index = reader.read_u2()
        if not _java_cp_index_has_tag(tags, name_index, JAVA_CP_TAG_UTF8):
            raise _JavaClassParseError("field/method name_index does not reference a Utf8 entry")
        descriptor_index = reader.read_u2()
        if not _java_cp_index_has_tag(tags, descriptor_index, JAVA_CP_TAG_UTF8):
            raise _JavaClassParseError("field/method descriptor_index does not reference a Utf8 entry")
        _parse_java_class_attribute_list(reader, tags)


def _parse_java_class_attribute_list(reader: _BoundedJavaClassReader, tags: dict[int, int]) -> None:
    """Parse one `attributes[]` table (JVMS §4.7): each entry is
    `{u2 attribute_name_index; u4 attribute_length; u1 info[attribute_length]}`.
    This parser does not interpret any attribute's own contents (Code,
    ConstantValue, etc.) -- it bounds-checks and skips `attribute_length`
    bytes, which is the exact same fail-closed contract as every other
    unbounded-length field here: `attribute_length` is a u4 (up to ~4GB)
    with NO fixed cap of its own, so the ONLY thing preventing an
    over-read is `_BoundedJavaClassReader.skip()` checking it against
    this member's actual remaining bytes.
    """
    count = reader.read_u2()
    for _ in range(count):
        attribute_name_index = reader.read_u2()
        if not _java_cp_index_has_tag(tags, attribute_name_index, JAVA_CP_TAG_UTF8):
            raise _JavaClassParseError("attribute_name_index does not reference a Utf8 entry")
        attribute_length = reader.read_u4()
        reader.skip(attribute_length)


def _parse_java_class_structure(data: bytes) -> bool:
    reader = _BoundedJavaClassReader(data)
    if reader.read_bytes(4) != JAVA_CLASS_COLLISION_FAT_MACHO_MAGIC:
        return False
    minor_version = reader.read_u2()
    major_version = reader.read_u2()
    if not _is_supported_java_class_version(major_version, minor_version):
        raise _JavaClassParseError(
            f"unsupported class file version {major_version}.{minor_version} "
            f"(JVMS §4.1: major 45 permits minor 0-3, major 46-55 requires minor 0, "
            f"major 56-{MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION} permits minor 0 or 65535 (preview))"
        )
    constant_pool_count = reader.read_u2()
    if constant_pool_count < 1:
        raise _JavaClassParseError("constant_pool_count must be at least 1")
    tags, refs, utf8_values = _parse_java_class_constant_pool(reader, constant_pool_count, major_version)
    _validate_java_cp_references(tags, refs, utf8_values, major_version)
    reader.read_u2()  # access_flags -- accepted as-is, not further validated
    this_class = reader.read_u2()
    if not _java_cp_index_has_tag(tags, this_class, JAVA_CP_TAG_CLASS):
        raise _JavaClassParseError("this_class does not reference a Class entry")
    super_class = reader.read_u2()
    if super_class != 0 and not _java_cp_index_has_tag(tags, super_class, JAVA_CP_TAG_CLASS):
        raise _JavaClassParseError("super_class is neither 0 nor a Class entry")
    interfaces_count = reader.read_u2()
    for _ in range(interfaces_count):
        interface_index = reader.read_u2()
        if not _java_cp_index_has_tag(tags, interface_index, JAVA_CP_TAG_CLASS):
            raise _JavaClassParseError("an interfaces[] entry does not reference a Class entry")
    _parse_java_class_member_list(reader, tags)  # fields[]
    _parse_java_class_member_list(reader, tags)  # methods[]
    _parse_java_class_attribute_list(reader, tags)  # top-level attributes[]
    return reader.at_exact_eof()


def _validate_java_class_structure(data: bytes) -> bool:
    """Structurally validate a Java `.class` file (JVMS §4), not just its
    4-byte magic -- the ONLY thing that may exempt a member whose content
    starts with the exact CAFEBABE fat-Mach-O magic
    (`JAVA_CLASS_COLLISION_FAT_MACHO_MAGIC`) from a hard
    `"malformed_native_magic"` failure once it has already failed the fat
    Mach-O structural parse (see `_classify_by_magic`).

    Parses, in order, with every count/length bounds-checked against this
    member's own actual remaining bytes (never a separately-trusted
    length): magic, minor/major version (JVMS §4.1 major/minor
    combination rules, see `_is_supported_java_class_version`, within
    this file's own explicit `MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION`
    ceiling), `constant_pool_count` and every constant-pool entry (known
    tag approved for this class file's own major_version, correct fixed
    body size or bounds-checked+Modified-UTF8-validated Utf8 length,
    Long/Double double-slot indexing with its reserved successor slot
    required to remain in range), every entry's OWN internal
    constant-pool reference field(s) cross-checked against the now-
    complete tag map for the exact target tag JVMS §4.4 requires
    (Class/String->Utf8; Field/Method/InterfaceMethodref->Class+
    NameAndType; NameAndType->Utf8+Utf8; MethodHandle->reference_kind in
    1..9 with a version-dependent allowed target tag AND, for reference
    kinds 5/6/7/8/9, the resolved method name's `<init>`/`<clinit>`
    semantics (see `_resolve_java_method_handle_target_name`);
    MethodType->Utf8; Dynamic/InvokeDynamic->NameAndType;
    Module/Package->Utf8 -- every such reference must be nonzero, in
    range, and never land on a Long/Double's reserved phantom slot),
    access_flags, `this_class`/
    `super_class` (must reference a Class entry, or 0 for super_class),
    `interfaces[]` (each must reference a Class entry), `fields[]`/
    `methods[]` (each member's name/descriptor index must reference a
    Utf8 entry, each attribute bounds-checked and skipped), top-level
    `attributes[]`, and finally requires EXACT end-of-member with zero
    trailing bytes. Any violation (unknown tag, a tag used before its
    own class-file-format version, invalid Modified UTF-8, truncation,
    an attribute/UTF8 length that overflows past the member's actual
    size, any invalid cross-reference described above, or trailing bytes
    after the last attribute) returns `False`. Never raises, and never
    invokes any external/unpinned class-file parser -- this bounded,
    dependency-free walk is the entire implementation.
    """
    try:
        return _parse_java_class_structure(data)
    except _JavaClassParseError:
        return False


def _classify_by_magic(name: str, data: bytes) -> str:
    """Classify one archive member's content (using its name ONLY for the
    narrow Java-`.class` collision fallback below, never for any other
    magic family).

    Returns exactly one of:
    - `"native"`: a supported native-code format, positively confirmed --
      either a simple prefix match (ELF/thin Mach-O/ar) or, for fat
      Mach-O/PE/XCOFF, a full bounded structural parse that passed.
    - `"malformed_native_magic"`: the leading bytes matched a recognized
      native-format magic, but the structural parse for that format
      failed. This is a hard failure the caller must never silently
      absorb as `"not_native"` -- with exactly one documented, narrow
      exception (see `JAVA_CLASS_COLLISION_FAT_MACHO_MAGIC`): a member
      whose content starts with the exact CAFEBABE fat-Mach-O magic,
      fails that structural parse, has an EXACT-CASE `.class` member
      name (`JAVA_CLASS_MEMBER_SUFFIX`), AND whose full payload
      independently passes `_validate_java_class_structure` falls back
      to `"not_native"` instead. A 2026-08-24 review found the PRIOR
      version of this fallback fired for ANY CAFEBABE-prefixed payload
      under ANY filename purely because it failed the fat-Mach-O parse --
      that let a renamed, malformed fat-Mach-O collision payload evade
      review entirely. Fail-closed now requires BOTH the exact-case name
      AND independent structural proof of a genuine Java class file
      before granting the same exemption; anything else (wrong
      extension, or a `.class`-named member whose payload does not
      actually parse as a valid class file) is `"malformed_native_magic"`
      like every other native-magic mismatch.
    - `"not_native"`: no recognized native-format magic matched at all.
    """
    prefix = data[:MAX_NATIVE_MAGIC_PREFIX_LEN]
    if data[:4] in FAT_MACHO_MAGIC_VARIANTS:
        if _validate_fat_macho_structure(data):
            return "native"
        if (
            data[:4] == JAVA_CLASS_COLLISION_FAT_MACHO_MAGIC
            and _member_has_exact_java_class_suffix(name)
            and _validate_java_class_structure(data)
        ):
            return "not_native"
        return "malformed_native_magic"
    if data[:2] == b"MZ":
        return "native" if _validate_pe_structure(data) else "malformed_native_magic"
    if data[:2] in (XCOFF32_MAGIC, XCOFF64_MAGIC):
        return "native" if _validate_xcoff_structure(data) else "malformed_native_magic"
    if any(prefix.startswith(sig) for sig in NATIVE_MAGIC_SIGNATURES):
        return "native"
    return "not_native"


def classify_native_member_signal(name: str, data: bytes) -> str:
    """Classify one archive member for native-code discovery purposes.

    Returns exactly one of:
    - `"native"`: treat as a native carrier member requiring review --
      either a known native extension (`NATIVE_MEMBER_EXTENSIONS`) whose
      content positively confirms a supported native format, or an
      unknown/absent extension whose content does anyway (a
      renamed/extensionless payload -- `payload.bin`, `.dat`, even a
      misleading `.class` name, all still count if the magic AND
      structure are real).
    - `"malformed_native_magic"`: the member's leading bytes matched a
      recognized native-format magic (fat Mach-O/PE/XCOFF), but a full
      structural parse of that claimed format failed -- regardless of
      the member's extension -- and (for the CAFEBABE/Java-`.class`
      collision magic specifically) the member also failed to
      independently qualify for the narrow Java-class fallback in
      `_classify_by_magic` (wrong/non-exact extension, or a `.class`-
      named member whose payload does not actually parse as a valid
      Java class file). Never silently accepted OR silently ignored;
      the caller must fail closed and a human reviewer must inspect
      this member.
    - `"extension_magic_mismatch"`: the member's extension IS one of
      `NATIVE_MEMBER_EXTENSIONS`, but its content does not match any
      supported native magic signature at all (not even one that then
      failed structural validation -- that case is
      `"malformed_native_magic"` above). Never silently accepted OR
      silently ignored.
    - `"not_native"`: none of the above; ordinary member (a genuinely
      structurally-valid `.class` file, a resource, a POM, etc.).
    """
    magic_signal = _classify_by_magic(name, data)
    if magic_signal in ("native", "malformed_native_magic"):
        return magic_signal
    if _member_has_native_extension(name):
        return "extension_magic_mismatch"
    return "not_native"


MAX_ZIP_MEMBERS_SCANNED = 20_000
MAX_ZIP_MEMBER_BYTES_READ = 512 * 1024 * 1024


def find_local_maven_artifacts(group: str, artifact: str, version: str) -> list[Path]:
    """Locate every resolved .jar/.aar for one coordinate in the local
    Gradle module cache -- there can legitimately be BOTH for one GAV (e.g.
    `net.java.dev.jna:jna:5.19.1` publishes Gradle Module Metadata with a
    separate Android `.aar` variant, distinct from its main `.jar`, and
    different consuming source sets/modules resolve different files for
    the exact same coordinate). Returns an empty list (never raises) when
    the cache is cold/absent for this coordinate, so callers can treat this
    purely as defense-in-depth, same as the POM live-fallback in
    `gradle_license_inventory()` -- this generator's core determinism never
    depends on this function finding anything.
    """
    base = GRADLE_MODULES2 / group / artifact / version
    if not base.is_dir():
        return []
    found: list[Path] = []
    for ext in (".aar", ".jar"):
        for candidate in sorted(base.glob(f"*/{artifact}-{version}{ext}")):
            if not candidate.is_symlink():
                found.append(candidate)
    return found


# Individually human-reviewed archive members that legitimately match a
# recognized native-code magic (or a native extension) but were each
# confirmed, on inspection, to be genuine non-native content -- pinned by
# the EXACT (maven_coordinate, member path, whole-member SHA-256) triple
# so this is a narrow, auditable, single-file exception, never a general
# "trust this filename/shape" bypass: any other member -- including this
# exact coordinate+path with even one different content byte -- still
# raises `EvidenceError` in `_scan_zip_for_native_members` below and
# requires a fresh review. `classify_native_member_signal()` itself is
# never modified by this list; the exception is applied only at the
# point this scanner would otherwise raise.
REVIEWED_NON_NATIVE_MEMBERS: tuple[dict[str, str], ...] = (
    {
        # kotlinx-coroutines-core-jvm ships its coroutine debug-probes
        # bytecode as a resource literally named `DebugProbesKt.bin`
        # (never `DebugProbesKt.class`) specifically so ordinary
        # classloaders never load it automatically -- only the
        # coroutines debug agent loads it explicitly, by resource name,
        # when debug-probes mode is turned on. Confirmed 2026-08-24 by
        # extracting this exact member and running it through
        # `_validate_java_class_structure()`: genuine CAFEBABE magic,
        # major_version 52 (JDK 8), a real (if small) constant pool/
        # this_class/methods/attributes structure that fully validates
        # -- an ordinary compiled Java class body, not a native payload
        # evading detection under a misleading extension.
        "maven_coordinate": "org.jetbrains.kotlinx:kotlinx-coroutines-core-jvm:1.11.0",
        "path": "DebugProbesKt.bin",
        "sha256": "065bd792b8527764f33147188302af5bf9e2a8da40fde0830dc111ad26dae40e",
    },
    {
        # Same upstream mechanism as above, resolved for a different
        # coroutines version by a different module/source-set's own
        # transitive dependency graph. Confirmed 2026-08-24 the same way.
        "maven_coordinate": "org.jetbrains.kotlinx:kotlinx-coroutines-core-jvm:1.6.4",
        "path": "DebugProbesKt.bin",
        "sha256": "158a19eb94aa2f3e2f459db69ee10276c73b945dd6c5f8fc223cf2d85e2b5e33",
    },
)


_ZIP_DRIVE_LETTER_PATH_RE = re.compile(r"^[A-Za-z]:")


def _canonical_zip_member_path_or_none(raw_name: str) -> str | None:
    r"""Canonicalize one archive member's raw central-directory name for
    duplicate/collision detection AND `REVIEWED_NON_NATIVE_MEMBERS`
    exception matching (never for classification or extraction, which
    both still use the member's own raw, unmodified name):

    1. Backslashes are folded to forward slashes (some non-canonical
       zip writers emit `\\`-separated paths, and this is also how a
       Windows drive-letter or UNC-style name is normalized into a
       plain, checkable slash form below).
    2. The result is Unicode-normalized to NFC. Two members whose names
       are visually/semantically identical but differ in Unicode
       composition (e.g. a precomposed "e" + combining acute accent
       U+0301 vs the single precomposed codepoint U+00E9) must be
       treated as the same path -- NFC is the same normalization form
       Java string/identifier comparisons and most filesystems'
       Unicode-aware collation converge on, and is applied here purely
       for collision detection, never to silently rewrite what gets
       extracted.
    3. Repeated separators are collapsed (`foo//bar` -> `foo/bar`) and
       ALL trailing separators are stripped (`foo/bar///` -> `foo/bar`),
       so a directory entry and a same-named file entry, or two members
       differing only by redundant slashes, normalize to the same path.

    Returns `None` (never raises -- see `_canonical_zip_member_path_or_raise`
    for the archive-scanning caller that turns this into a hard failure)
    if `raw_name` is unsafe or malformed in any of these ways:

    - contains an unpaired UTF-16 surrogate code point (malformed
      Unicode -- cannot correspond to any real decoded zip member name
      that this generator should trust);
    - normalizes to an empty path (e.g. a bare `/` or `\\` root marker);
    - normalizes to an ABSOLUTE path (leading `/` -- this also catches
      every UNC form, e.g. `\\server\share\x`, which folds to
      `//server/share/x` and then collapses to `/server/share/x`);
    - normalizes to a Windows drive-letter path (`C:...`, `C:/...`);
    - normalizes to a path with a `.` or `..` component (current-dir or
      parent traversal), at any position.
    """
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in raw_name):
        return None
    normalized = unicodedata.normalize("NFC", raw_name.replace("\\", "/"))
    normalized = re.sub(r"/+", "/", normalized)
    canonical = normalized.rstrip("/")
    if canonical == "":
        return None
    if canonical.startswith("/"):
        return None
    if _ZIP_DRIVE_LETTER_PATH_RE.match(canonical):
        return None
    if any(component in (".", "..") for component in canonical.split("/")):
        return None
    return canonical


def _validate_reviewed_non_native_members_catalog(entries: tuple[dict[str, str], ...]) -> None:
    """Fail closed on a malformed `REVIEWED_NON_NATIVE_MEMBERS` catalog
    itself, before it is ever consulted: every entry's
    `(maven_coordinate, path)` pair must be UNIQUE across the whole
    catalog. Two entries sharing a coordinate+path -- whether they agree
    on `sha256` (a pointless exact duplicate) or disagree (a genuinely
    conflicting exception for the same member) -- both indicate a
    catalog authoring error, not a real narrow single-file exception,
    and both are rejected the same way. Also requires every entry's
    `path` to ALREADY be in canonical form (see
    `_canonical_zip_member_path_or_none`) -- `_is_reviewed_non_native_member`
    compares a scanned archive member's canonical path directly against
    this catalog's `path` field, so a catalog entry that were itself
    non-canonical (a redundant slash, an `NFD` accent, etc.) could never
    match anything and would silently be dead code. Called once at
    module import ("startup") against the real catalog below, and
    independently callable/tested with any other tuple.
    """
    seen: dict[tuple[str, str], str] = {}
    for entry in entries:
        canonical = _canonical_zip_member_path_or_none(entry["path"])
        if canonical != entry["path"]:
            raise EvidenceError(
                "REVIEWED_NON_NATIVE_MEMBERS catalog entry for "
                f"maven_coordinate={entry['maven_coordinate']!r} has a "
                f"non-canonical path {entry['path']!r} (canonical form: "
                f"{canonical!r}) -- catalog paths must already be canonical; "
                "refusing to start"
            )
        key = (entry["maven_coordinate"], entry["path"])
        if key in seen:
            raise EvidenceError(
                "REVIEWED_NON_NATIVE_MEMBERS catalog has more than one entry for "
                f"maven_coordinate={key[0]!r} path={key[1]!r} (sha256 "
                f"{seen[key]!r} vs {entry['sha256']!r}) -- each reviewed member "
                "exception must be unique by coordinate+path; refusing to start"
            )
        seen[key] = entry["sha256"]


_validate_reviewed_non_native_members_catalog(REVIEWED_NON_NATIVE_MEMBERS)


def _is_reviewed_non_native_member(gav: str, canonical_path: str, data: bytes) -> bool:
    """`canonical_path` must already be the archive member's canonical
    path from `_canonical_zip_member_path_or_raise` -- the catalog's own
    `path` values are enforced (by `_validate_reviewed_non_native_members_catalog`)
    to already be in that exact canonical form, so both sides of this
    comparison are guaranteed to use the same normalization.
    """
    digest = hashlib.sha256(data).hexdigest()
    return any(
        entry["maven_coordinate"] == gav and entry["path"] == canonical_path and entry["sha256"] == digest
        for entry in REVIEWED_NON_NATIVE_MEMBERS
    )


def _canonical_zip_member_path_or_raise(archive_path: Path, raw_name: str) -> str:
    canonical = _canonical_zip_member_path_or_none(raw_name)
    if canonical is None:
        raise EvidenceError(
            f"{archive_path}: member name {raw_name!r} is unsafe or malformed "
            "(absolute path, drive-letter/UNC form, '.'/'..' traversal "
            "component, malformed Unicode surrogate, or normalizes to an "
            "empty path) -- malformed/adversarial zip, refusing to scan"
        )
    return canonical


def _reject_duplicate_zip_members(archive_path: Path, infos: list[zipfile.ZipInfo]) -> dict[str, str]:
    """Enumerate every raw archive member (including directory entries),
    reject any member whose name is unsafe/malformed per
    `_canonical_zip_member_path_or_none`, and fail closed on any two
    whose canonical paths collide -- exact duplicate names,
    slash-vs-backslash variants, repeated/trailing-separator variants,
    NFC-vs-NFD Unicode variants, and directory/file collisions are all
    the same failure here. This runs BEFORE any per-member classification
    or `REVIEWED_NON_NATIVE_MEMBERS` lookup in `_scan_zip_for_native_members`,
    and does not consult that exception catalog at all: a hash-pinned
    reviewed exception for one member's CONTENT can never excuse the
    archive itself from carrying two members that collide by name, since
    that ambiguity affects every consumer of the archive (build tool,
    classloader, extractor), not just this generator's own scan.

    Returns a `{raw_name: canonical_path}` mapping for every member, so
    the caller can reuse the SAME canonical path for
    `REVIEWED_NON_NATIVE_MEMBERS` matching without recomputing it (and
    without risking the two call sites silently drifting apart).
    """
    canonical_by_raw: dict[str, str] = {}
    seen: dict[str, str] = {}
    for info in infos:
        canonical = _canonical_zip_member_path_or_raise(archive_path, info.filename)
        canonical_by_raw[info.filename] = canonical
        if canonical in seen:
            raise EvidenceError(
                f"{archive_path}: members {seen[canonical]!r} and {info.filename!r} "
                f"both normalize to the same canonical path {canonical!r} (exact "
                "duplicate, backslash/forward-slash variant, repeated/trailing "
                "separator variant, NFC/NFD Unicode variant, or directory/file "
                "collision) -- malformed/adversarial zip, refusing to scan"
            )
        seen[canonical] = info.filename
    return canonical_by_raw


def _scan_zip_for_native_members(archive_path: Path, gav: str) -> list[dict[str, Any]]:
    reject_symlink(archive_path)
    members: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_MEMBERS_SCANNED:
            raise EvidenceError(
                f"{archive_path}: {len(infos)} zip members exceeds "
                f"MAX_ZIP_MEMBERS_SCANNED={MAX_ZIP_MEMBERS_SCANNED} (refusing to scan)"
            )
        canonical_by_raw = _reject_duplicate_zip_members(archive_path, infos)
        for info in infos:
            if info.is_dir():
                continue
            if info.file_size > MAX_ZIP_MEMBER_BYTES_READ:
                raise EvidenceError(
                    f"{archive_path}: member {info.filename!r} declares "
                    f"{info.file_size} bytes, exceeding "
                    f"MAX_ZIP_MEMBER_BYTES_READ={MAX_ZIP_MEMBER_BYTES_READ}"
                )
            with zf.open(info) as fh:
                data = fh.read()
            signal = classify_native_member_signal(info.filename, data)
            if signal in ("malformed_native_magic", "extension_magic_mismatch") and _is_reviewed_non_native_member(
                gav, canonical_by_raw[info.filename], data
            ):
                continue
            if signal == "malformed_native_magic":
                raise EvidenceError(
                    f"{archive_path}: member {info.filename!r} has leading "
                    "bytes matching a recognized native-code magic "
                    "(fat Mach-O/PE/XCOFF) but failed this generator's "
                    "bounded structural validation for that format -- "
                    "refusing to classify automatically; a human reviewer "
                    "must inspect this member"
                )
            if signal == "extension_magic_mismatch":
                raise EvidenceError(
                    f"{archive_path}: member {info.filename!r} has a "
                    "recognized native-code extension "
                    f"{NATIVE_MEMBER_EXTENSIONS} but its leading bytes do "
                    "not match any supported native magic signature "
                    "(ELF/Mach-O/PE/ar/XCOFF) -- extension/content "
                    "mismatch, refusing to classify automatically; a "
                    "human reviewer must inspect this member"
                )
            if signal == "not_native":
                continue
            members.append(
                {
                    "path": info.filename,
                    "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
    return members


SUPPORTED_MAVEN_ARTIFACT_EXTENSIONS = ("jar", "aar")


def _expected_artifact_hashes_by_extension(
    gav: str, catalog_entry: dict[str, Any]
) -> dict[str, str]:
    """Map each supported archive extension ("jar"/"aar") to the single
    whole-archive SHA-256 this catalog entry declares for it: its
    required `primary_artifact_kind` maps to the top-level
    `artifact_sha256`, and each `additional_artifacts[].kind` maps to
    that entry's own `artifact_sha256`. `maven_native_carriers_inventory()`
    already validates that `primary_artifact_kind` is one of
    `SUPPORTED_MAVEN_ARTIFACT_EXTENSIONS` and is not also claimed by any
    `additional_artifacts` entry, so this function only builds the map.
    """
    mapping = {catalog_entry["primary_artifact_kind"]: catalog_entry["artifact_sha256"]}
    for extra in catalog_entry.get("additional_artifacts", []):
        mapping[extra["kind"]] = extra["artifact_sha256"]
    return mapping


def _verify_resolved_artifact_hashes(
    gav: str, catalog_entry: dict[str, Any], artifact_paths: list[Path]
) -> None:
    """Compute the whole-archive SHA-256 of every resolved .jar/.aar for
    `gav` and require exact equality with the catalog's declared
    primary/additional artifact hash for that extension, BEFORE any
    member inside the archive is inspected.

    A member-hash-only check cannot catch a substituted/wrong archive
    whose one catalogued native member happens to still be byte-identical
    while everything else (classes, metadata, other resources) differs --
    this closes that gap. Also rejects: multiple resolved archives of the
    same extension with different content (ambiguous -- which one was
    actually used to build?), and a resolved extension this catalog entry
    has no corresponding declared hash for at all (missing mapping).
    """
    expected_by_ext = _expected_artifact_hashes_by_extension(gav, catalog_entry)
    by_ext: dict[str, dict[str, Path]] = {}
    for path in artifact_paths:
        ext = path.suffix.lower().lstrip(".")
        digest = sha256_file(path)
        by_ext.setdefault(ext, {})[digest] = path

    for ext, digest_to_path in by_ext.items():
        if len(digest_to_path) > 1:
            raise EvidenceError(
                f"{gav}: {len(digest_to_path)} different resolved .{ext} "
                f"archives found in the local Gradle cache with different "
                f"whole-archive SHA-256 values {sorted(digest_to_path)} -- "
                "ambiguous which is the real resolved artifact, refusing "
                "to inspect its members"
            )
        (actual_digest,) = digest_to_path
        expected_digest = expected_by_ext.get(ext)
        if expected_digest is None:
            (only_path,) = digest_to_path.values()
            raise EvidenceError(
                f"{gav}: resolved .{ext} artifact {only_path} has no "
                f"corresponding artifact_sha256/additional_artifacts entry "
                f"in MAVEN_NATIVE_CARRIERS[{gav!r}] for extension {ext!r} "
                f"(catalogued extensions: {sorted(expected_by_ext)}) -- "
                "missing/ambiguous archive mapping, refusing to inspect "
                "its members"
            )
        if actual_digest != expected_digest:
            (only_path,) = digest_to_path.values()
            raise EvidenceError(
                f"{gav}: resolved .{ext} artifact {only_path} whole-archive "
                f"SHA-256 {actual_digest} does not match catalogued "
                f"{expected_digest} -- wrong/substituted artifact, "
                "refusing to inspect its members"
            )


def cross_check_maven_native_carriers_against_local_cache(
    gradle_report: dict[str, Any],
) -> None:
    """Defense-in-depth: on a warm Gradle cache, verify every resolved
    runtime coordinate's actual .jar/.aar whole-archive bytes against
    `MAVEN_NATIVE_CARRIERS` above, THEN scan for native-looking members and
    require that result to exactly match the same catalog entry too.

    Like `find_local_pom()`'s live-cache fallback, this needs no
    pre-populated cache to pass (a cold cache simply finds nothing to check,
    since `find_local_maven_artifacts()` returns an empty list for every
    coordinate and this function never raises for a coordinate whose
    artifacts it could not locate) -- but when the cache IS warm, this
    generator FAILS CLOSED rather than silently omitting a native member or
    trusting a substituted archive: a whole-archive hash that does not
    match the catalog's primary/additional artifact_sha256 (checked BEFORE
    any member is inspected -- see `_verify_resolved_artifact_hashes()`), a
    native-carrying coordinate absent from the static catalog, an
    unreviewed extra member on a known carrier, or a hash/size mismatch on
    an already-catalogued member all raise `EvidenceError` and abort
    generation.
    """
    catalog_by_coordinate = {c["maven_coordinate"]: c for c in MAVEN_NATIVE_CARRIERS}

    all_runtime_gavs: set[str] = set()
    for module_data in gradle_report["modules"].values():
        all_runtime_gavs.update(module_data["coordinates"]["runtime"])

    for gav in sorted(all_runtime_gavs):
        group, artifact, version = parse_gav(gav)
        artifact_paths = find_local_maven_artifacts(group, artifact, version)
        if not artifact_paths:
            continue  # cold cache for this coordinate -- nothing to cross-check

        catalog_entry_for_hash_check = catalog_by_coordinate.get(gav)
        if catalog_entry_for_hash_check is not None:
            _verify_resolved_artifact_hashes(gav, catalog_entry_for_hash_check, artifact_paths)

        discovered_by_path: dict[str, dict[str, Any]] = {}
        for artifact_path in artifact_paths:
            discovered = _scan_zip_for_native_members(artifact_path, gav)

            # Duplicate-member-path detection within a single archive:
            # zipfile's infolist() can legitimately contain duplicate names
            # for a malformed/adversarial zip, and each would silently
            # overwrite the last-scanned entry in a naive dict build below
            # -- guard explicitly, before merging across artifacts.
            discovered_paths_seen: list[str] = [m["path"] for m in discovered]
            if len(discovered_paths_seen) != len(set(discovered_paths_seen)):
                dupes = sorted(
                    {p for p in discovered_paths_seen if discovered_paths_seen.count(p) > 1}
                )
                raise EvidenceError(
                    f"{gav}: archive {artifact_path} contains duplicate native "
                    f"member path(s) {dupes} -- malformed/adversarial zip, refusing"
                )
            for member in discovered:
                existing_member = discovered_by_path.get(member["path"])
                if existing_member is not None and existing_member["sha256"] != member["sha256"]:
                    raise EvidenceError(
                        f"{gav}: member path {member['path']!r} appears with "
                        "two different SHA-256 values across this "
                        "coordinate's own resolved artifacts (e.g. its .jar "
                        "vs its .aar) -- ambiguous, refusing"
                    )
                discovered_by_path[member["path"]] = member

        if not discovered_by_path:
            continue

        catalog_entry = catalog_by_coordinate.get(gav)
        if catalog_entry is None:
            raise EvidenceError(
                f"{gav}: local Gradle cache artifact(s) "
                f"{[str(p) for p in artifact_paths]} carry "
                f"{len(discovered_by_path)} native-looking member(s) "
                f"{sorted(discovered_by_path)} not present in "
                "MAVEN_NATIVE_CARRIERS -- a new native-carrying coordinate "
                "must be added to that catalog (with reviewed "
                "distribution_status) before this generator will proceed; "
                "it is never silently omitted"
            )

        catalog_by_path = {m["path"]: m for m in catalog_entry["embedded_natives"]}
        extra = sorted(set(discovered_by_path) - set(catalog_by_path))
        if extra:
            raise EvidenceError(
                f"{gav}: local cache artifact(s) {[str(p) for p in artifact_paths]} "
                f"carry unreviewed native member path(s) {extra} not present "
                f"in MAVEN_NATIVE_CARRIERS[{gav!r}]['embedded_natives'] -- "
                "archive drift since the catalog was last reviewed"
            )
        missing = sorted(set(catalog_by_path) - set(discovered_by_path))
        if missing:
            raise EvidenceError(
                f"{gav}: MAVEN_NATIVE_CARRIERS[{gav!r}] declares native "
                f"member path(s) {missing} that local cache artifact(s) "
                f"{[str(p) for p in artifact_paths]} no longer contain -- "
                "archive drift, review and update the catalog"
            )
        for path, discovered_member in discovered_by_path.items():
            catalog_member = catalog_by_path[path]
            if discovered_member["sha256"] != catalog_member["sha256"]:
                raise EvidenceError(
                    f"{gav}: member {path!r} sha256 "
                    f"{discovered_member['sha256']} does not match catalogued "
                    f"{catalog_member['sha256']} -- archive/hash drift"
                )
            if discovered_member["size_bytes"] != catalog_member["size_bytes"]:
                raise EvidenceError(
                    f"{gav}: member {path!r} size {discovered_member['size_bytes']} "
                    f"does not match catalogued {catalog_member['size_bytes']}"
                )


def maven_native_carriers_inventory(gradle_report: dict[str, Any] | None = None) -> dict[str, Any]:
    seen_coordinates: set[str] = set()
    for carrier in MAVEN_NATIVE_CARRIERS:
        coordinate = carrier["maven_coordinate"]
        if coordinate in seen_coordinates:
            raise EvidenceError(f"duplicate maven_coordinate in MAVEN_NATIVE_CARRIERS: {coordinate}")
        seen_coordinates.add(coordinate)
        status = carrier.get("distribution_status")
        if status not in VALID_CARRIER_DISTRIBUTION_STATUSES:
            raise EvidenceError(
                f"{carrier['maven_coordinate']}: distribution_status {status!r} "
                f"is not one of {VALID_CARRIER_DISTRIBUTION_STATUSES}"
            )
        if not SHA256_HEX_RE.match(carrier.get("artifact_sha256", "")):
            raise EvidenceError(
                f"{carrier['maven_coordinate']}: artifact_sha256 "
                f"{carrier.get('artifact_sha256')!r} is not a 64-hex-char sha256"
            )
        primary_kind = carrier.get("primary_artifact_kind")
        if primary_kind not in SUPPORTED_MAVEN_ARTIFACT_EXTENSIONS:
            raise EvidenceError(
                f"{carrier['maven_coordinate']}: primary_artifact_kind "
                f"{primary_kind!r} is not one of {SUPPORTED_MAVEN_ARTIFACT_EXTENSIONS}"
            )
        additional_kinds_seen: set[str] = set()
        for extra_artifact in carrier.get("additional_artifacts", []):
            extra_kind = extra_artifact.get("kind")
            if extra_kind not in SUPPORTED_MAVEN_ARTIFACT_EXTENSIONS:
                raise EvidenceError(
                    f"{carrier['maven_coordinate']}: additional_artifacts kind "
                    f"{extra_kind!r} is not one of {SUPPORTED_MAVEN_ARTIFACT_EXTENSIONS}"
                )
            if extra_kind == primary_kind:
                raise EvidenceError(
                    f"{carrier['maven_coordinate']}: additional_artifacts kind "
                    f"{extra_kind!r} duplicates primary_artifact_kind"
                )
            if extra_kind in additional_kinds_seen:
                raise EvidenceError(
                    f"{carrier['maven_coordinate']}: additional_artifacts declares "
                    f"kind {extra_kind!r} more than once"
                )
            additional_kinds_seen.add(extra_kind)
            if not SHA256_HEX_RE.match(extra_artifact.get("artifact_sha256", "")):
                raise EvidenceError(
                    f"{carrier['maven_coordinate']}: additional_artifacts entry "
                    f"{extra_artifact.get('kind')!r} artifact_sha256 "
                    f"{extra_artifact.get('artifact_sha256')!r} is not a "
                    "64-hex-char sha256"
                )
        seen_member_paths: set[str] = set()
        for member in carrier["embedded_natives"]:
            for field in ("path", "size_bytes", "sha256", "platform", "arch"):
                if field not in member:
                    raise EvidenceError(
                        f"{carrier['maven_coordinate']}: embedded native "
                        f"{member.get('path')!r} is missing required field {field!r}"
                    )
            if member["path"] in seen_member_paths:
                raise EvidenceError(
                    f"{carrier['maven_coordinate']}: duplicate embedded native "
                    f"member path {member['path']!r}"
                )
            seen_member_paths.add(member["path"])
            if not SHA256_HEX_RE.match(member["sha256"]):
                raise EvidenceError(
                    f"{carrier['maven_coordinate']}: embedded native "
                    f"{member['path']!r} sha256 {member['sha256']!r} is not a "
                    "64-hex-char sha256"
                )
            if not isinstance(member["size_bytes"], int) or member["size_bytes"] <= 0:
                raise EvidenceError(
                    f"{carrier['maven_coordinate']}: embedded native "
                    f"{member['path']!r} size_bytes {member['size_bytes']!r} "
                    "is not a positive integer"
                )
        count = carrier.get("embedded_native_count")
        if count is not None and count != len(carrier["embedded_natives"]):
            raise EvidenceError(
                f"{carrier['maven_coordinate']}: embedded_native_count {count} != "
                f"len(embedded_natives) {len(carrier['embedded_natives'])}"
            )

    if gradle_report is not None:
        cross_check_maven_native_carriers_against_local_cache(gradle_report)

    return {
        "method": (
            "Point-in-time inspection (2026-08-24) of the actual resolved "
            "artifact bytes in the local Gradle module cache: Python `zipfile` "
            "for the embedded native member list, with size and SHA-256 read "
            "directly from each archive member's own extracted bytes (not "
            "estimated, not copied from any upstream release notes). This "
            "table is static; it is not re-derived from a live artifact fetch "
            "on every run (see docs/LEGAL_REVIEW.md \u00a78 for why, and the "
            "re-verification command). Distinct from "
            "crypto-signing-backend/CHECKSUMS.sha256, which lists only "
            "first-party binaries built from this repository's own Rust crate. "
            "`distribution_status` is one of "
            f"{VALID_CARRIER_DISTRIBUTION_STATUSES}. Defense-in-depth: when "
            "generation runs with a warm local Gradle module cache, every "
            "resolved runtime coordinate's actual .jar/.aar has its own "
            "whole-archive SHA-256 verified against this table's "
            "artifact_sha256/additional_artifacts BEFORE any member inside "
            "it is inspected (rejecting a wrong/substituted/ambiguous "
            "archive up front), then every non-directory member's leading "
            "bytes are inspected for ELF/Mach-O (thin and fat/universal)/ "
            "PE/ar/XCOFF magic regardless of filename extension -- a "
            f"known native extension ({NATIVE_MEMBER_EXTENSIONS}) whose "
            "content does not match any supported native magic fails "
            "generation outright, and an unknown/absent extension whose "
            "content DOES match becomes a reviewable carrier member the "
            "same as an extension match would -- via "
            "cross_check_maven_native_carriers_against_local_cache(), which "
            "fails generation on any undeclared native-carrying coordinate, "
            "unreviewed extra/missing member, or member hash/size drift "
            "against this table; a cold cache (as in CI) skips this specific "
            "cross-check without weakening any other check in this file."
        ),
        "carriers": list(MAVEN_NATIVE_CARRIERS),
    }


# ---------------------------------------------------------------------------
# Bouncy Castle license: source-HTML snapshot hash vs manual-transcription hash
# ---------------------------------------------------------------------------

BOUNCYCASTLE_SOURCE_HTML = (
    EVIDENCE_DIR / "license-sources" / "bouncycastle-licence-2026-08-24.html"
)


def bouncycastle_license_source_inventory() -> dict[str, Any]:
    bc_txt = REPO_ROOT / "LICENSES" / "BouncyCastle.txt"
    return {
        "method": (
            "LICENSES/BouncyCastle.txt is a manual, human transcription of the "
            "licence paragraphs rendered by https://www.bouncycastle.org/licence.html "
            "-- it is NOT byte-fetched/verbatim HTML, and its SHA-256 cannot be "
            "reproduced by re-fetching that URL. To let a reviewer independently "
            "check the transcription, this repository separately commits the "
            "raw HTML snapshot fetched from that URL on 2026-08-24 at "
            "docs/evidence/license-sources/bouncycastle-licence-2026-08-24.html, "
            "hashed below as source_html_sha256. transcription_sha256 is the "
            "SHA-256 of LICENSES/BouncyCastle.txt itself. Whether the "
            "transcription is a faithful, complete rendering of the source HTML "
            "is an OPEN counsel determination, not asserted by this script."
        ),
        "source_url": "https://www.bouncycastle.org/licence.html",
        "fetched_date": "2026-08-24",
        "source_html_snapshot": str(
            BOUNCYCASTLE_SOURCE_HTML.relative_to(REPO_ROOT)
        ),
        "source_html_sha256": sha256_file(BOUNCYCASTLE_SOURCE_HTML),
        "transcription_file": "LICENSES/BouncyCastle.txt",
        "transcription_sha256": sha256_file(bc_txt),
        "transcription_faithfulness_review": "OPEN — pending owner/counsel review",
    }


# ---------------------------------------------------------------------------
# Java class-version evidence: real resolved-artifact bytes, not just a
# ceiling comment's prose claim
# ---------------------------------------------------------------------------
#
# MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION's own comment (above) cites the
# resolved `org.bouncycastle:bcprov-jdk18on` jar's real major_version 69
# classes as this ceiling's evidence -- but a comment is prose, not
# evidence a reviewer or a machine can independently verify. This section
# instead commits the actual scan result: `JAVA_CLASS_VERSION_EVIDENCE` is
# a reviewed, static, committed snapshot (so the evidence FILE's content is
# byte-identical run to run, independent of network/cache timing), and
# `live_verify_java_class_version_evidence()` is a MANDATORY re-verification
# against the REAL resolved jar's actual bytes, run every time
# `java_class_version_evidence()` is called (from `run_generate()`, from
# `check_evidence_is_freshly_regenerable()`, or directly) -- with NO skip
# branch at all.
#
# A 2026-08-25 independent review found the prior design -- re-scan the
# local Gradle module cache and treat "nothing found" as a safe no-op, the
# same tradeoff `find_local_maven_artifacts()` documents for
# `MAVEN_NATIVE_CARRIERS` -- silently returns success with NOTHING checked
# on this repo's own legal-evidence-scan CI job, whose Gradle cache is
# always cold (that job runs no `./gradlew` task at all): exactly the
# environment this "live" evidence is supposed to be authoritative in
# never actually ran the check. `MAVEN_NATIVE_CARRIERS`' local-cache cross
# check is deliberately left as pure defense-in-depth (its committed
# snapshot is dated and re-verified by a documented manual `unzip`/hash
# procedure instead -- see `docs/LEGAL_REVIEW.md` §13); this evidence gets
# a different, stricter treatment because it is the sole basis for
# `MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION`, a live-enforced parser ceiling.
#
# The fix: `live_verify_java_class_version_evidence()` always resolves an
# ACTUAL jar to scan -- an explicit path (`--bcprov-jar`, or the
# `BCPROV_JAR_PATH_ENV_VAR` environment variable CI sets once after its own
# fetch+verify bootstrap step) if given, else `fetch_and_verify_bcprov_jar()`
# downloads the exact pinned artifact from Maven Central into a fresh temp
# directory. Either way, a missing/wrong-hash file is a hard `EvidenceError`
# -- there is no longer a third "quietly skip" path.


def _read_java_class_header_version(data: bytes) -> tuple[int, int] | None:
    """Bounded read of ONLY a `.class` file's leading magic + minor/major
    version fields (JVMS §4.1's first 8 bytes) -- deliberately not the
    full structural walk `_validate_java_class_structure()` performs.
    This helper's one job is extracting the raw `(major, minor)` pair for
    `_scan_and_verify_bcprov_jar_bytes()`'s max-observed-major scan across
    every member of a real resolved jar;
    `_validate_java_class_structure()` is still run separately (and
    required to pass) against the SAME bytes, so the evidence this
    produces is backed by full validator agreement, not just a
    plausible-looking header. Returns `None` (never raises) if there are
    fewer than 8 bytes or the first 4 do not match the Java class-file
    magic.
    """
    if len(data) < 8 or data[:4] != JAVA_CLASS_COLLISION_FAT_MACHO_MAGIC:
        return None
    minor_version, major_version = struct.unpack(">HH", data[4:8])
    return major_version, minor_version


# Maven Central's own canonical host -- `fetch_and_verify_bcprov_jar()`
# refuses EVERY HTTP redirect, to any host including this one (see
# `_NoRedirectHandler` below), and this evidence's own
# `artifact_maven_central_url` field is required to already be an
# `https://` URL on exactly this host (`_validate_sealed_java_class_version_evidence()`).
BCPROV_MAVEN_CENTRAL_HOST = "repo1.maven.org"

# Generous ceiling on the download -- the real artifact is ~9.8 MiB
# (`artifact_size_bytes` below is the exact, pinned figure this bounds
# a sanity check against); this constant only guards against an
# unbounded read of a misbehaving/hostile response, never a legitimate
# size check on its own.
MAX_BCPROV_DOWNLOAD_BYTES = 64 * 1024 * 1024

BCPROV_FETCH_TIMEOUT_SECONDS = 60.0

# Reviewed 2026-08-24 against the actual resolved
# `org.bouncycastle:bcprov-jdk18on:1.85.2` jar in the local Gradle module
# cache: every one of its 7163 non-directory `*.class` members (including
# every `META-INF/versions/N/` multi-release variant) was read via Python
# `zipfile`, its leading 8 bytes parsed for the JVMS §4.1 magic/minor/major
# fields, and its full bytes independently run through this file's own
# `_validate_java_class_structure()` -- all 7163 passed. The observed
# maximum `major_version` is 69 (Java SE 25), reached by exactly the 24
# members below, every one of them a real `META-INF/versions/25/...class`
# member of the real resolved artifact (never synthetic). This ceiling
# (`MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION`) and this snapshot are REQUIRED
# to move together -- `_validate_sealed_java_class_version_evidence()`
# below fails closed at import time if they ever disagree, and
# `live_verify_java_class_version_evidence()` (this section's module
# comment above) fails generation/checking outright -- with NO skip branch
# -- if a fresh scan of the real artifact (an explicit `--bcprov-jar` path,
# an already-verified path from `BCPROV_JAR_PATH_ENV_VAR`, or a fresh
# Maven-Central fetch+verify) ever produces a different whole-archive hash,
# member count, observed maximum, or member set at that maximum.
# `artifact_size_bytes`/`artifact_maven_central_url` were independently
# confirmed 2026-08-25 against Maven Central's own directory listing and
# its published `.jar.sha256` sidecar (`docs/DEPENDENCY_PROVENANCE.md`
# already recorded this exact coordinate/URL/hash before this section
# existed) -- both are asserted, not merely recorded, by
# `fetch_and_verify_bcprov_jar()`.
JAVA_CLASS_VERSION_EVIDENCE: dict[str, Any] = {
    "method": (
        "Point-in-time inspection (2026-08-24, re-verified 2026-08-25 via a "
        "live Maven Central fetch) of the actual resolved "
        "org.bouncycastle:bcprov-jdk18on:1.85.2 .jar: Python `zipfile` for "
        "member discovery, this file's own bounded 8-byte header read for "
        "each member's raw major/minor version fields, and this file's own "
        "_validate_java_class_structure() (full JVMS §4 structural walk, "
        "not just the magic bytes) required to pass for every one of the "
        "7163 scanned members. This table is static; the evidence FILE's "
        "content is not re-derived from a live fetch on every run (a fixed, "
        "reviewed snapshot, not a moving target), but "
        "live_verify_java_class_version_evidence() unconditionally "
        "re-verifies it byte-for-byte against a real resolved jar -- an "
        "explicit --bcprov-jar path, an already-verified path from the "
        "KARDANO_LEGAL_EVIDENCE_BCPROV_JAR environment variable, or (the "
        "default) a fresh pinned-host, SHA-256-and-size-verified download "
        "from Maven Central -- every single time this function runs, with "
        "no cold-cache/no-op skip branch. It fails generation/checking "
        "outright on any drift: wrong whole-archive SHA-256, wrong member "
        "count, wrong observed maximum major_version, or a different "
        "member set at that maximum. max_major_version is exactly "
        "MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION -- the ceiling and this "
        "evidence are reviewed and moved together, never independently."
    ),
    "coordinate": "org.bouncycastle:bcprov-jdk18on:1.85.2",
    "artifact_maven_central_url": (
        "https://repo1.maven.org/maven2/org/bouncycastle/bcprov-jdk18on/"
        "1.85.2/bcprov-jdk18on-1.85.2.jar"
    ),
    "artifact_sha256": "986b0fb92ec10e0c66b43e036ce0077e6150cfaecd1db9fb92b56672e157afe5",
    "artifact_size_bytes": 10280518,
    "total_class_members_scanned": 7163,
    "max_major_version": 69,
    "members_at_max_major_version": (
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/hkdf/HKDFSpi$HKDFwithSHA256.class",
            "sha256": "684b2b75d3e1edf14b61cb80dd96569a350b3aaeb87260253bdd084ad78327a0",
            "size_bytes": 576,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/hkdf/HKDFSpi$HKDFwithSHA384.class",
            "sha256": "cc9bd91cae86950551f2f8fa6213c04fd151a4df557a6560c3b603c20bdc7db7",
            "size_bytes": 576,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/hkdf/HKDFSpi$HKDFwithSHA512.class",
            "sha256": "e62269c9686688d2952cad6ea6ecbf8c8e4a449d25b01223835455f5c825284b",
            "size_bytes": 576,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/hkdf/HKDFSpi.class",
            "sha256": "f85c537c7c6f61761216ea31ddfa8ba6f68ba9be55d19c5b16f1f5e930875bbc",
            "size_bytes": 3947,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2with8BIT.class",
            "sha256": "e06c05b971bb2e6fe9e8dbc9c862e01d014da96ac4d51826ab88255d187d9c4c",
            "size_bytes": 739,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withGOST3411.class",
            "sha256": "7ef4714d612cf474b206fa94c339a4c748d738e4c9268b7f9ec91515dec0b265",
            "size_bytes": 594,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSHA224.class",
            "sha256": "315c1073d3b4b5c5e35e6a1fc799c48bddcc1b5e4c0947dcfd93bb5565d64beb",
            "size_bytes": 588,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSHA256.class",
            "sha256": "a1dd374e1e91a0384eb30e4a588e043a23f4bd2fb728a9a77e38686917a2ad6f",
            "size_bytes": 588,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSHA384.class",
            "sha256": "4bc3257c6f93d06db155285ad762166e6777ec15e01cae2c8530d5244241237a",
            "size_bytes": 588,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSHA3_224.class",
            "sha256": "521b1da50a3eba6260c78df4eccc44d3fd1a74285bcddfc2fdce2cf9ac49a4b3",
            "size_bytes": 600,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSHA3_256.class",
            "sha256": "a1d54f34294da8a22e6724d1781e003563d5486d961d865f75e928f80f208483",
            "size_bytes": 600,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSHA3_384.class",
            "sha256": "b0d57673adf31a1926864d57dd49743a7ac1630e9b7c21976686f53f73f63504",
            "size_bytes": 600,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSHA3_512.class",
            "sha256": "ca04a30ba4b4abf8cc7192f69c4715c6fdbd0d57df51e320f239511ab90f69fb",
            "size_bytes": 600,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSHA512.class",
            "sha256": "d7804e2f671b2422c90d5b67b633918bb2967c52193ea56eeb9721c18045b132",
            "size_bytes": 588,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSHA512_224.class",
            "sha256": "1590d5acaa83d81fe2ad24c87725efa92b764abe4b32ff99c27474b47fa4f62c",
            "size_bytes": 607,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSHA512_256.class",
            "sha256": "6052992aa05284b15b0c3b86ccc15ba69d246f02470e13b5ba745b316e0c0e2e",
            "size_bytes": 607,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withSM3.class",
            "sha256": "dba4695b7e5c2783d2eff4ced412adc125e470d53adb192db6cbcec002264e57",
            "size_bytes": 579,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi$PBKDF2withUTF8.class",
            "sha256": "7302e64cf2daaf7330468759be8a5db58ed8204da731b607f6e6023b7079b155",
            "size_bytes": 582,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/pbkdf2/PBKDF2Spi.class",
            "sha256": "c4e1257aa1abbff1fde8cd0ace5a8805c066b9e88e60396a6aab9c73d425a74a",
            "size_bytes": 3992,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/scrypt/ScryptSpi$ScryptWithUTF8.class",
            "sha256": "f29201b0a6b4a72b327be8ff72794e8de2f0ed7aa7839d6e36583ca5be9f4e77",
            "size_bytes": 446,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/provider/kdf/scrypt/ScryptSpi.class",
            "sha256": "90d6cc65d5e56684b8c78dd18f59bbc1272a818955d23ff8b0eec92eb19bb142",
            "size_bytes": 2497,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/spec/PBKDF2ParameterSpec.class",
            "sha256": "ae49383adeac2ac730ca41577ff6939c118e4190ff8d7bf3b5c0ab173cd3fbb0",
            "size_bytes": 340,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/spec/ScryptParameterSpec.class",
            "sha256": "9cb161188533fdc08a937ef3ecbe810e1761957e1b24cbad719983260f658339",
            "size_bytes": 255,
            "major_version": 69,
            "minor_version": 0,
        },
        {
            "path": "META-INF/versions/25/org/bouncycastle/jcajce/util/SpiUtil.class",
            "sha256": "8357487278ffb208c738ce9f96e76d3e6f959d50a0fcc0d344ca6b39bbf6a72d",
            "size_bytes": 231,
            "major_version": 69,
            "minor_version": 0,
        },
    ),
}


def _validate_sealed_java_class_version_evidence(entry: dict[str, Any]) -> None:
    """Fail closed at import time if `JAVA_CLASS_VERSION_EVIDENCE` (hand-
    reviewed) is internally malformed OR disagrees with the live
    `MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION` ceiling -- these two are
    required to move together (see this section's own module comment)."""
    if not SHA256_HEX_RE.match(entry["artifact_sha256"]):
        raise EvidenceError(
            f"JAVA_CLASS_VERSION_EVIDENCE artifact_sha256 {entry['artifact_sha256']!r} "
            "is not a 64-hex-char sha256"
        )
    if not isinstance(entry["artifact_size_bytes"], int) or entry["artifact_size_bytes"] <= 0:
        raise EvidenceError(
            f"JAVA_CLASS_VERSION_EVIDENCE artifact_size_bytes "
            f"{entry['artifact_size_bytes']!r} is not a positive int"
        )
    parsed_url = urllib.parse.urlsplit(entry["artifact_maven_central_url"])
    if parsed_url.scheme != "https" or parsed_url.hostname != BCPROV_MAVEN_CENTRAL_HOST:
        raise EvidenceError(
            f"JAVA_CLASS_VERSION_EVIDENCE artifact_maven_central_url "
            f"{entry['artifact_maven_central_url']!r} is not an https:// URL on the "
            f"pinned host {BCPROV_MAVEN_CENTRAL_HOST!r}"
        )
    if entry["max_major_version"] != MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION:
        raise EvidenceError(
            "JAVA_CLASS_VERSION_EVIDENCE max_major_version "
            f"{entry['max_major_version']} != live "
            f"MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION "
            f"{MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION} -- the ceiling and this "
            "evidence snapshot must be reviewed and updated together"
        )
    members = entry["members_at_max_major_version"]
    if not members:
        raise EvidenceError("JAVA_CLASS_VERSION_EVIDENCE members_at_max_major_version is empty")
    seen_paths: set[str] = set()
    for member in members:
        if member["path"] in seen_paths:
            raise EvidenceError(
                f"JAVA_CLASS_VERSION_EVIDENCE has a duplicate member path {member['path']!r}"
            )
        seen_paths.add(member["path"])
        if not SHA256_HEX_RE.match(member["sha256"]):
            raise EvidenceError(
                f"JAVA_CLASS_VERSION_EVIDENCE member {member['path']!r} sha256 "
                f"{member['sha256']!r} is not a 64-hex-char sha256"
            )
        if member["major_version"] != entry["max_major_version"]:
            raise EvidenceError(
                f"JAVA_CLASS_VERSION_EVIDENCE member {member['path']!r} "
                f"major_version {member['major_version']} != max_major_version "
                f"{entry['max_major_version']}"
            )
        if not _is_supported_java_class_version(member["major_version"], member["minor_version"]):
            raise EvidenceError(
                f"JAVA_CLASS_VERSION_EVIDENCE member {member['path']!r} version "
                f"{member['major_version']}.{member['minor_version']} fails this "
                "file's own JVMS major/minor combination rules"
            )


_validate_sealed_java_class_version_evidence(JAVA_CLASS_VERSION_EVIDENCE)

# Convenience alias for the pinned coordinate's own reviewed URL -- the
# `.sha256` sidecar this evidence's live verification best-effort-checks
# lives at exactly this URL with a `.sha256` suffix (see Maven Central's
# own directory-listing convention, independently confirmed 2026-08-25).
BCPROV_MAVEN_CENTRAL_URL = JAVA_CLASS_VERSION_EVIDENCE["artifact_maven_central_url"]

# The pinned URL's own path component, split out once so
# `_validate_pinned_artifact_url()` can require an EXACT match rather than
# re-deriving it ad hoc at each call site.
BCPROV_MAVEN_CENTRAL_PATH = urllib.parse.urlsplit(BCPROV_MAVEN_CENTRAL_URL).path


def _validate_pinned_artifact_url(url: str, *, expected_path: str) -> None:
    """Structural provenance check on `url`, independent of and prior to
    any network I/O: exactly scheme `https`, exactly host
    `BCPROV_MAVEN_CENTRAL_HOST`, no explicit port other than the HTTPS
    default (443), exactly `expected_path`, and no query string,
    fragment, or userinfo. A 2026-08-25 independent review found this
    fetch previously validated only the *hostname* of the initial and
    final URLs -- a URL like
    ``https://user:pass@repo1.maven.org:8443/../evil/path?x#y`` has the
    pinned hostname yet is not remotely the one pinned artifact URL.
    Called on the URL about to be requested AND (see `_fetch_url_bytes`)
    the actual final response URL, so neither a corrupted constant nor a
    same-host response whose URL otherwise drifted can silently pass.
    Raises `EvidenceError` on any deviation; never touches the network.
    """
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        raise EvidenceError(f"{url!r}: scheme must be exactly 'https', got {parsed.scheme!r}")
    if parsed.username is not None or parsed.password is not None:
        raise EvidenceError(f"{url!r}: userinfo (user:pass@) is not allowed in a pinned artifact URL")
    if parsed.hostname != BCPROV_MAVEN_CENTRAL_HOST:
        raise EvidenceError(
            f"{url!r}: host must be exactly {BCPROV_MAVEN_CENTRAL_HOST!r}, "
            f"got {parsed.hostname!r}"
        )
    if parsed.port is not None and parsed.port != 443:
        raise EvidenceError(
            f"{url!r}: only the default HTTPS port is allowed, got explicit port {parsed.port!r}"
        )
    if parsed.query:
        raise EvidenceError(f"{url!r}: a query string is not allowed in a pinned artifact URL")
    if parsed.fragment:
        raise EvidenceError(f"{url!r}: a fragment is not allowed in a pinned artifact URL")
    if parsed.path != expected_path:
        raise EvidenceError(
            f"{url!r}: path must be exactly {expected_path!r}, got {parsed.path!r}"
        )


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuses EVERY HTTP 3xx redirect, unconditionally -- including one
    that would land on the exact same scheme/host/port/path this fetch
    already pinned. A 2026-08-25 independent review found the prior
    design's "same host is fine" exception meant a captive portal, an
    on-path proxy, or a compromised intermediate hop could redirect an
    already-in-flight request through an arbitrary detour (still
    reporting the same final host) before it ever reached Maven Central,
    without this ever being flagged; a same-host redirect through a
    *different path/port/query* was also never checked at all. There is
    no legitimate reason this fetch's one pinned URL should ever redirect,
    so the simplest and strictest fix is to reject every redirect, full
    stop, before a single byte of the redirected response is read --
    `redirect_request()` raises directly instead of calling
    `super().redirect_request()`, so urllib never opens the new request.
    This also makes a redirect loop moot: the very first hop already
    fails closed, with no chance to loop.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise EvidenceError(
            f"refusing HTTP {code} redirect from {req.full_url!r} to {newurl!r} -- "
            "this fetch never follows a redirect, even to the same host/scheme/path"
        )


def _fetch_url_bytes(url: str, *, expected_path: str, max_bytes: int, timeout: float) -> tuple[bytes, str | None]:
    """The one function in this file that makes a real HTTP request --
    kept this small and separate specifically so tests can monkeypatch
    exactly this seam instead of exercising real network I/O.

    `url` is validated against the pinned scheme/host/port/path/no-query/
    no-fragment/no-userinfo rule (`_validate_pinned_artifact_url()`)
    BEFORE any request is made. The opener never follows a redirect
    (`_NoRedirectHandler`): any 3xx response raises immediately, before
    a single byte of the redirected response is read. After a successful
    (non-redirected) response, the actual `response.url` is required to
    be byte-for-byte IDENTICAL to the requested `url` -- not just same-
    host -- and is independently re-validated through the same pinned-URL
    check, so a same-host response that otherwise did not go through our
    redirect handler (in principle impossible via `urllib`, but never
    assumed) still cannot silently substitute a different path/port/
    query for the one pinned artifact. Returns
    `(body_bytes, declared_content_length_header_or_None)`; never reads
    more than `max_bytes + 1` bytes, so an oversized response is
    reported, not silently truncated into looking valid.
    """
    _validate_pinned_artifact_url(url, expected_path=expected_path)
    opener = urllib.request.build_opener(_NoRedirectHandler())
    request = urllib.request.Request(
        url, headers={"User-Agent": "KardanoSDK-legal-evidence-fetch/1.0"}
    )
    with opener.open(request, timeout=timeout) as response:
        final_url = response.url
        if final_url != url:
            raise EvidenceError(
                f"{url}: final response URL {final_url!r} is not byte-identical to the "
                "requested URL -- refusing to trust a request that changed in flight"
            )
        _validate_pinned_artifact_url(final_url, expected_path=expected_path)
        declared_length = response.headers.get("Content-Length")
        data = response.read(max_bytes + 1)
    return data, declared_length


def _write_all_to_fd(fd: int, data: bytes) -> None:
    """Write every byte of `data` to raw file descriptor `fd`, looping on
    both a partial write (a `write()` that returns fewer bytes than
    given -- always legal per POSIX, common on a full pipe/slow disk) and
    `InterruptedError` (EINTR) rather than trusting a single `os.write()`
    call to consume the whole buffer. Raises `EvidenceError` if a
    `write()` call ever returns 0 with bytes still remaining (would
    otherwise loop forever).
    """
    view = memoryview(data)
    total = len(view)
    written = 0
    while written < total:
        try:
            n = os.write(fd, view[written:])
        except InterruptedError:
            continue
        if n == 0:
            raise EvidenceError(
                f"os.write() returned 0 bytes with {total - written} of {total} bytes "
                "still unwritten"
            )
        written += n


def _create_exclusive_file(path: Path, data: bytes) -> None:
    """Create `path` and write `data` to it, refusing to write through OR
    over anything already at that exact path -- a regular file, a
    symlink (to anywhere), or a directory. A 2026-08-25 independent
    review found the prior code (`Path.write_bytes()`, i.e. `open(path,
    "wb")`) opens with `O_CREAT | O_TRUNC` and no `O_EXCL`: if `path`
    already existed as a symlink, it would silently write through that
    symlink to whatever it pointed at, and a prior `dest_path.is_symlink()`
    check-then-write is itself a check-then-act TOCTOU race, not a fix.

    This uses `os.open()` with `O_CREAT | O_EXCL | O_WRONLY` (plus
    `O_NOFOLLOW` where the platform defines it, e.g. not on Windows) in
    ONE atomic syscall: `O_EXCL` makes creation fail with `EEXIST` if
    `path` already exists at all -- file, symlink, or directory, with no
    separate stat-then-open window for a race to land in -- and
    `O_NOFOLLOW` is a second, independent guard against ever traversing a
    symlink at the final path component even in the hypothetical case an
    OS's `O_EXCL` semantics ever diverged from POSIX. On ANY failure
    (creation failure, or a write failure partway through -- e.g. disk
    full, `OSError` mid-write) this removes whatever partial file it
    created rather than leaving a half-written file that a later, unaware
    read could mistake for complete; a failure to create in the first
    place obviously leaves nothing to clean up.
    """
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(path), flags, 0o644)
    except FileExistsError as exc:
        raise EvidenceError(
            f"{path}: refusing to write -- a file, symlink, or directory already exists "
            "at this exact path"
        ) from exc
    except OSError as exc:
        raise EvidenceError(f"{path}: failed to create destination file: {exc}") from exc
    try:
        _write_all_to_fd(fd, data)
    except BaseException:
        os.close(fd)
        try:
            path.unlink()
        except OSError:
            pass
        raise
    else:
        os.close(fd)


def _best_effort_verify_bcprov_sha256_sidecar(actual_sha256: str) -> None:
    """Maven Central publishes a `.jar.sha256` sidecar alongside the real
    artifact -- fetched here as an OPTIONAL, best-effort SECOND signal,
    never the mandatory check (`JAVA_CLASS_VERSION_EVIDENCE['artifact_sha256']`,
    already verified by the caller before this runs, is that). A sidecar
    fetch that fails outright (network hiccup, sidecar temporarily
    unavailable) is silently ignored -- it is not required to be present.
    A sidecar that WAS fetched successfully but disagrees with the
    already-verified download IS treated as an error: a positively
    disagreeing signal is never worth ignoring just because it was
    optional to obtain.
    """
    try:
        sidecar_bytes, _ = _fetch_url_bytes(
            BCPROV_MAVEN_CENTRAL_URL + ".sha256",
            expected_path=BCPROV_MAVEN_CENTRAL_PATH + ".sha256",
            max_bytes=4096,
            timeout=BCPROV_FETCH_TIMEOUT_SECONDS,
        )
    except Exception:  # noqa: BLE001 -- best-effort only, never fails generation on its own
        return
    try:
        sidecar_hex = sidecar_bytes.decode("ascii").strip().split()[0].lower()
    except (UnicodeDecodeError, IndexError):
        return  # unexpected sidecar format -- not worth failing generation over
    if not SHA256_HEX_RE.match(sidecar_hex):
        return
    if sidecar_hex != actual_sha256:
        raise EvidenceError(
            f"{BCPROV_MAVEN_CENTRAL_URL}.sha256: publisher-provided sha256 "
            f"{sidecar_hex} disagrees with the verified download's {actual_sha256}"
        )


def fetch_and_verify_bcprov_jar(dest_dir: Path) -> Path:
    """Download the exact pinned `org.bouncycastle:bcprov-jdk18on:1.85.2`
    `.jar` from Maven Central into `dest_dir` (caller-provided; expected to
    be a fresh, disposable temporary directory -- see
    `live_verify_java_class_version_evidence()`) and verify its whole-
    archive SHA-256 AND size EXACTLY match `JAVA_CLASS_VERSION_EVIDENCE`
    before returning its path. Independent of any local Gradle module
    cache -- this is the fix for a 2026-08-25 independent review finding
    that the prior Gradle-cache-only design silently no-ops (returns
    success, checks nothing) on this repo's own always-cold-cache CI job.

    Fails closed (`EvidenceError`) on: a symlinked or non-directory
    `dest_dir`; any HTTP error; a request/response URL that is not
    byte-identical to the one pinned Maven Central URL (scheme, host,
    port, path, no query/fragment/userinfo -- see
    `_validate_pinned_artifact_url()`); any HTTP redirect at all (see
    `_NoRedirectHandler`); a byte count that disagrees with either the
    response's own declared `Content-Length` or the pinned
    `artifact_size_bytes` (covers both a truncated download and one with
    unexpected extra bytes); a whole-archive SHA-256 mismatch; or a
    destination path that already exists in any form, file, symlink, or
    directory (see `_create_exclusive_file()`). Also best-effort verifies
    Maven Central's own published `.sha256` sidecar (never mandatory on
    its own; see `_best_effort_verify_bcprov_sha256_sidecar()`).
    """
    if dest_dir.is_symlink():
        raise EvidenceError(f"{dest_dir}: refusing a symlinked download destination directory")
    if not dest_dir.is_dir():
        raise EvidenceError(f"{dest_dir}: download destination directory does not exist")
    try:
        data, declared_length = _fetch_url_bytes(
            BCPROV_MAVEN_CENTRAL_URL,
            expected_path=BCPROV_MAVEN_CENTRAL_PATH,
            max_bytes=MAX_BCPROV_DOWNLOAD_BYTES,
            timeout=BCPROV_FETCH_TIMEOUT_SECONDS,
        )
    except EvidenceError:
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise EvidenceError(f"failed to fetch {BCPROV_MAVEN_CENTRAL_URL}: {exc}") from exc

    if len(data) > MAX_BCPROV_DOWNLOAD_BYTES:
        raise EvidenceError(
            f"{BCPROV_MAVEN_CENTRAL_URL}: downloaded {len(data)} bytes exceeds "
            f"MAX_BCPROV_DOWNLOAD_BYTES={MAX_BCPROV_DOWNLOAD_BYTES}"
        )
    expected_size = JAVA_CLASS_VERSION_EVIDENCE["artifact_size_bytes"]
    if declared_length is not None and int(declared_length) != expected_size:
        raise EvidenceError(
            f"{BCPROV_MAVEN_CENTRAL_URL}: server declared Content-Length "
            f"{declared_length} != pinned artifact_size_bytes {expected_size}"
        )
    if len(data) != expected_size:
        raise EvidenceError(
            f"{BCPROV_MAVEN_CENTRAL_URL}: downloaded {len(data)} bytes != pinned "
            f"artifact_size_bytes {expected_size} (truncated or padded download)"
        )
    actual_sha256 = hashlib.sha256(data).hexdigest()
    expected_sha256 = JAVA_CLASS_VERSION_EVIDENCE["artifact_sha256"]
    if actual_sha256 != expected_sha256:
        raise EvidenceError(
            f"{BCPROV_MAVEN_CENTRAL_URL}: downloaded sha256 {actual_sha256} != "
            f"pinned {expected_sha256} -- refusing to trust this download"
        )

    dest_path = dest_dir / "bcprov-jdk18on-1.85.2.jar"
    _create_exclusive_file(dest_path, data)

    _best_effort_verify_bcprov_sha256_sidecar(actual_sha256)
    return dest_path


def _scan_and_verify_bcprov_jar_bytes(jar_path: Path) -> None:
    """Shared scan core for `live_verify_java_class_version_evidence()`:
    whole-archive SHA-256 (checked BEFORE any member is inspected, same
    ordering as `_verify_resolved_artifact_hashes()`), every real `.class`
    member's own JVMS structural validity (`_validate_java_class_structure()`
    must pass for every one, not just the ones recorded in
    `JAVA_CLASS_VERSION_EVIDENCE`), the true observed maximum
    `major_version`, and the exact member set recorded at that maximum
    (path, SHA-256, size, minor_version). Raises `EvidenceError` on any
    disagreement; `jar_path` must already exist (callers are responsible
    for that -- see `live_verify_java_class_version_evidence()`).
    """
    coordinate = JAVA_CLASS_VERSION_EVIDENCE["coordinate"]
    reject_symlink(jar_path)
    actual_artifact_sha256 = sha256_file(jar_path)
    expected_artifact_sha256 = JAVA_CLASS_VERSION_EVIDENCE["artifact_sha256"]
    if actual_artifact_sha256 != expected_artifact_sha256:
        raise EvidenceError(
            f"{coordinate}: {jar_path} whole-archive SHA-256 "
            f"{actual_artifact_sha256} does not match the pinned "
            f"{expected_artifact_sha256} in JAVA_CLASS_VERSION_EVIDENCE -- "
            "wrong/substituted artifact, refusing to inspect its members"
        )

    max_major = -1
    members_at_max: list[dict[str, Any]] = []
    total_class_members = 0
    with zipfile.ZipFile(jar_path) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_MEMBERS_SCANNED:
            raise EvidenceError(
                f"{jar_path}: {len(infos)} zip members exceeds "
                f"MAX_ZIP_MEMBERS_SCANNED={MAX_ZIP_MEMBERS_SCANNED} (refusing to scan)"
            )
        _reject_duplicate_zip_members(jar_path, infos)
        for info in infos:
            if info.is_dir() or not info.filename.endswith(".class"):
                continue
            if info.file_size > MAX_ZIP_MEMBER_BYTES_READ:
                raise EvidenceError(
                    f"{jar_path}: member {info.filename!r} declares "
                    f"{info.file_size} bytes, exceeding "
                    f"MAX_ZIP_MEMBER_BYTES_READ={MAX_ZIP_MEMBER_BYTES_READ}"
                )
            with zf.open(info) as fh:
                data = fh.read()
            total_class_members += 1
            header = _read_java_class_header_version(data)
            if header is None:
                raise EvidenceError(
                    f"{jar_path}: member {info.filename!r} is named *.class but "
                    "does not start with the Java class-file magic"
                )
            major_version, minor_version = header
            if not _validate_java_class_structure(data):
                raise EvidenceError(
                    f"{jar_path}: member {info.filename!r} (version "
                    f"{major_version}.{minor_version}) failed full JVMS "
                    "structural validation"
                )
            if major_version > max_major:
                max_major = major_version
                members_at_max = []
            if major_version == max_major:
                members_at_max.append(
                    {
                        "path": info.filename,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "size_bytes": len(data),
                        "major_version": major_version,
                        "minor_version": minor_version,
                    }
                )

    expected_total = JAVA_CLASS_VERSION_EVIDENCE["total_class_members_scanned"]
    if total_class_members != expected_total:
        raise EvidenceError(
            f"{coordinate}: resolved .jar {jar_path} has {total_class_members} "
            f"*.class members, but JAVA_CLASS_VERSION_EVIDENCE pins "
            f"{expected_total} -- the committed snapshot must be reviewed and "
            "regenerated for this artifact"
        )
    expected_max_major = JAVA_CLASS_VERSION_EVIDENCE["max_major_version"]
    if max_major != expected_max_major:
        raise EvidenceError(
            f"{coordinate}: resolved .jar {jar_path} actual observed maximum "
            f"major_version is {max_major}, but JAVA_CLASS_VERSION_EVIDENCE "
            f"pins {expected_max_major} -- the ceiling and this evidence "
            "must be reviewed and updated together before this can pass"
        )
    if max_major != MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION:
        raise EvidenceError(
            f"{coordinate}: resolved .jar {jar_path} actual observed maximum "
            f"major_version {max_major} != live "
            f"MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION "
            f"{MAX_SUPPORTED_JAVA_CLASS_MAJOR_VERSION}"
        )
    actual_sorted = sorted(members_at_max, key=lambda m: m["path"])
    expected_sorted = sorted(
        JAVA_CLASS_VERSION_EVIDENCE["members_at_max_major_version"], key=lambda m: m["path"]
    )
    if actual_sorted != expected_sorted:
        raise EvidenceError(
            f"{coordinate}: resolved .jar {jar_path}'s actual members at "
            f"major_version {max_major} do not exactly match "
            "JAVA_CLASS_VERSION_EVIDENCE's members_at_max_major_version -- "
            f"actual={actual_sorted!r} expected={expected_sorted!r}"
        )


def live_verify_java_class_version_evidence(explicit_jar_path: Path | None = None) -> None:
    """Fail-closed, MANDATORY live verification of
    `JAVA_CLASS_VERSION_EVIDENCE` against real resolved
    `bcprov-jdk18on:1.85.2` bytes -- there is no skip branch:

    - If `explicit_jar_path` is given (from `--bcprov-jar`), it MUST
      already exist as a real, non-symlinked file -- a missing path is an
      `EvidenceError`, never treated as "nothing to check".
    - Else, if `BCPROV_JAR_PATH_ENV_VAR` is set in the environment (CI sets
      this once, after its own fetch+verify bootstrap step -- see
      `.github/workflows/verify.yml`), that path is used the same way.
    - Else, `fetch_and_verify_bcprov_jar()` downloads the exact pinned
      artifact from Maven Central into a fresh temporary directory.

    Either way, `_scan_and_verify_bcprov_jar_bytes()` then requires an
    exact match against the committed `JAVA_CLASS_VERSION_EVIDENCE`
    snapshot: whole-archive SHA-256, every member's own JVMS structural
    validity, the true observed maximum `major_version`, and the exact
    member set at that maximum. This replaces the prior
    `cross_check_java_class_version_evidence_against_local_cache()`, whose
    "cold local Gradle cache is a safe no-op" tradeoff a 2026-08-25
    independent review found meant this evidence was never actually
    live-checked at all on this repo's own (always-cold-cache)
    legal-evidence-scan CI job.
    """
    if explicit_jar_path is None:
        env_value = os.environ.get(BCPROV_JAR_PATH_ENV_VAR)
        if env_value:
            explicit_jar_path = Path(env_value)

    if explicit_jar_path is not None:
        if not explicit_jar_path.is_file():
            raise EvidenceError(
                f"explicit bcprov jar path {explicit_jar_path} does not exist -- "
                "an explicit path must be a real, already-verified artifact, "
                "never treated as a cue to skip live verification"
            )
        _scan_and_verify_bcprov_jar_bytes(explicit_jar_path)
        return

    with tempfile.TemporaryDirectory(prefix="kardano-bcprov-fetch-") as tmp_dir:
        jar_path = fetch_and_verify_bcprov_jar(Path(tmp_dir))
        _scan_and_verify_bcprov_jar_bytes(jar_path)


def java_class_version_evidence(bcprov_jar_path: Path | None = None) -> dict[str, Any]:
    """Committed Java class-file major-version evidence, derived from real
    resolved artifact bytes -- see this section's own module comment for
    why the returned FILE content is a static, reviewed snapshot rather
    than a live scan result (byte-identical run to run, independent of
    network/cache timing), and `live_verify_java_class_version_evidence()`
    for the MANDATORY live re-verification this function always runs
    first -- with no skip branch. `bcprov_jar_path`, if given, is forwarded
    as that call's `explicit_jar_path` (see `--bcprov-jar`); otherwise the
    `BCPROV_JAR_PATH_ENV_VAR` environment variable, then a live Maven
    Central fetch, are tried in that order.
    """
    live_verify_java_class_version_evidence(bcprov_jar_path)
    return {
        "method": JAVA_CLASS_VERSION_EVIDENCE["method"],
        "coordinate": JAVA_CLASS_VERSION_EVIDENCE["coordinate"],
        "artifact_maven_central_url": JAVA_CLASS_VERSION_EVIDENCE["artifact_maven_central_url"],
        "artifact_sha256": JAVA_CLASS_VERSION_EVIDENCE["artifact_sha256"],
        "artifact_size_bytes": JAVA_CLASS_VERSION_EVIDENCE["artifact_size_bytes"],
        "total_class_members_scanned": JAVA_CLASS_VERSION_EVIDENCE["total_class_members_scanned"],
        "max_major_version": JAVA_CLASS_VERSION_EVIDENCE["max_major_version"],
        "members_at_max_major_version": list(JAVA_CLASS_VERSION_EVIDENCE["members_at_max_major_version"]),
    }


# ---------------------------------------------------------------------------
# Scope binding: two-commit seal (evidence-content commit -> seal commit)
# ---------------------------------------------------------------------------
#
# A single self-generated `scope_binding.json` written in the SAME commit as
# the evidence it describes cannot prove anything: it would just be this
# script's own unverified claim about "whatever HEAD happens to be right
# now", re-derived fresh on every run, with no independent way to detect
# later drift (e.g. a later commit quietly editing an already-sealed
# evidence file). A 2026-08-24 independent review named this gap explicitly.
#
# The two-commit pattern this module implements instead:
#
# 1. Evidence-content commit ("commit A"): `python3 generate_legal_evidence.py`
#    (no flag) writes every file in `evidence_output_files()` -- NOT
#    including `scope_binding.json` -- against the CURRENT worktree/lock
#    state, and computes `LEGAL_EVIDENCE_DIGEST.txt` over exactly those
#    files. This is committed as a normal commit; its parent is the
#    immutable "subject-source commit" (the actual code/lock state that was
#    inventoried -- crypto-signing-backend/Cargo.lock, every
#    */gradle.lockfile, CHECKSUMS.sha256, NOTICE, LICENSES/*.txt).
# 2. Seal commit ("commit B"): `python3 generate_legal_evidence.py --seal`,
#    run with a clean worktree at commit A, reads back commit A's own hash
#    (`git rev-parse HEAD`) and commit A's parent (the subject-source
#    commit), records a SHA-256 of every evidence-content file's bytes
#    (`sealed_evidence_digests`), and writes `scope_binding.json`. It then
#    rewrites `LEGAL_EVIDENCE_DIGEST.txt` to add a `scope_binding.json_sha256=`
#    line -- the manifest now covers the seal file's own bytes, but (per the
#    same self-reference argument above) does not attempt to hash itself.
#
# `scripts/check_release_evidence.py`'s `check_scope_binding_seal()` verifies
# this binding independently of regeneration: it confirms `evidence_commit`
# and `subject_commit` exist as real git objects, that `subject_commit` is
# EXACTLY `evidence_commit`'s immediate parent, that `evidence_commit` is
# EXACTLY the effective seal tip's immediate parent (HEAD itself, or --
# ONLY when `_github_pull_request_merge_head()` validates HEAD as a
# genuine, fully event-bound GitHub `pull_request` merge-ref of exactly
# the sealed branch: exact `GITHUB_EVENT_NAME`/`GITHUB_EVENT_PATH` event
# payload, same repository, `main` base ref, matching head ref, exact
# GitHub parent order matched against the event's own `base.sha`/
# `head.sha`, and a byte-identical merge tree -- never by tree shape
# alone -- the validated PR-head parent, i.e. that parent *is* the seal
# commit. A 2026-08-24 independent review found the prior "ancestor of
# HEAD" wording let an unrelated later commit sit on top of an old seal
# without invalidating it; any commit added after the seal commit still
# requires a fresh subject/evidence/seal sequence before this check
# passes again. A later, independent review found the tree-shape-only
# merge-ref acceptance (no event binding at all) could not distinguish a
# genuine GitHub merge-ref from any other two-parent commit with a
# matching tree shape -- octopus merges, swapped/unrelated parents, and a
# fabricated same-tree merge candidate are all rejected now because
# `_github_pull_request_merge_head()` validates parent order and identity
# against the actual GitHub event payload FIRST, before any tree
# comparison, and denies the exception outright on a stale, forged,
# mismatched, or missing event/env -- falling back to the strict
# HEAD-must-be-the-exact-tip path, which a genuine merge commit does not
# satisfy), and that every evidence file's CURRENT bytes match both
# the digest recorded here AND the actual bytes committed at
# `evidence_commit`'s tree (`git show <evidence_commit>:<path>`) -- so an
# evidence file edited by some later commit without a re-seal is caught
# even though `check_evidence_is_freshly_regenerable()` would not itself
# notice (regeneration only compares against the CURRENT tracked tree,
# which is exactly the self-reference this two-commit design avoids
# relying on for the seal itself).
#
# Full source-scope binding: the seal above proves the EVIDENCE bytes are
# pinned to an exact subject-source commit, but says nothing about whether
# the SCRIPT that produced (and the script that checks) those bytes, or any
# OTHER tracked file the generator might read (a config file, a workflow, a
# lockfile, a dynamically-`importlib`-loaded or relative-imported helper an
# import-graph closure could miss), could itself change later without a
# re-seal -- a 2026-08-24 independent review named this gap explicitly, and
# a follow-up review found that binding only an explicit, AST-import-
# discovered TOOL-FILE set (the first attempt at closing this gap, kept
# below as `SEALED_TOOLING_FILES`/`tooling_sha256`) is still an INCOMPLETE
# closure claim: ordinary-import discovery cannot see a dynamic/relative/
# package import, and says nothing at all about a non-script input (an
# arbitrary config/catalog/workflow/lockfile/build file) the generator
# might read without ever `import`-ing it.
#
# `check_scope_binding_seal()` therefore no longer relies on ANY import-
# graph argument for completeness. Instead it diffs EVERY tracked file
# between `subject_commit` and current HEAD (`git diff --raw --no-renames`,
# so even a renamed file surfaces as an ordinary delete-of-old-path plus
# add-of-new-path, each checked independently) and requires that the ONLY
# paths allowed to differ are the exact, small, reviewed set of generated
# outputs the evidence-content and seal commits are themselves allowed to
# write: every name in `evidence_output_files()` under `docs/evidence/`,
# plus `docs/evidence/scope_binding.json` and
# `docs/evidence/LEGAL_EVIDENCE_DIGEST.txt` (see
# `_allowed_post_subject_change_paths()` in
# `scripts/check_release_evidence.py`). ANY other tracked file added,
# deleted, renamed, mode-changed (a symlink introduced anywhere, even at an
# otherwise-allowed path), or content-changed between those two commits
# fails this check -- a script, a catalog module, a workflow file, a
# lockfile, a build file, or a doc, whether reached by an ordinary import,
# a dynamic import, a relative/package import, or no import at all (a
# plain file read). This makes the import-graph question moot: it does not
# matter HOW a file could influence generated evidence, only THAT it did
# not change. `check_release_evidence.py`'s worktree-cleanliness check
# (`git status --porcelain`) is required to be empty for this same reason
# -- an uncommitted staged/unstaged change is exactly as much an
# unaccounted-for scope change as a committed one, just not yet visible to
# the commit-to-commit diff above.
#
# `SEALED_TOOLING_FILES`/`tooling_sha256` (below) are KEPT as additional,
# narrower audit detail -- a reviewer can see at a glance exactly which
# files this module considers "the tooling" and their exact pinned hashes,
# without diffing two full trees by hand -- but they are no longer the
# mechanism this module relies on to CLAIM completeness; the full
# source-scope diff above is.


# Explicit, reviewed set of every LOCAL PYTHON MODULE reachable from either
# legal-evidence entry-point script's ordinary import graph -- this is what
# `seal_scope_binding()`'s `tooling_sha256` field seals, kept as narrower
# audit detail alongside the authoritative full source-scope diff (see the
# "Full source-scope binding" module docstring above, which is what
# `check_scope_binding_seal()` actually relies on for completeness -- this
# list, by construction, can never see a dynamic/relative import or a
# non-Python input file, which is exactly why it is not that proof).
# Repo-relative, POSIX-separated paths. Reviewed 2026-08-24; kept honest
# against silent drift by `_discover_local_tooling_closure()` below, which
# this module refuses to import against if the two disagree.
SEALED_TOOLING_FILES: tuple[str, ...] = (
    "scripts/generate_legal_evidence.py",
    "scripts/check_release_evidence.py",
    "scripts/cargo_election_catalog.py",
    "scripts/license_catalog.py",
    "scripts/license_catalog_harvested.py",
)

# The two scripts that actually generate or check legal evidence; every
# local module reachable from either one's import graph must appear in
# SEALED_TOOLING_FILES above (nothing more, nothing less).
_TOOLING_ENTRY_POINT_SCRIPTS: tuple[str, ...] = (
    "generate_legal_evidence.py",
    "check_release_evidence.py",
)

_SCRIPTS_DIR = Path(__file__).resolve().parent


def _discover_local_tooling_closure() -> frozenset[str]:
    """Statically re-derive the transitive closure of same-directory
    (`scripts/`) module imports reachable from every legal-evidence
    entry-point script, via `ast` parsing only -- never by importing or
    executing anything, so this catalog's completeness can be verified
    even though `check_release_evidence.py` imports `generate_legal_evidence`
    and not the other way around (a live-import approach from inside this
    module would never see `check_release_evidence.py` itself).

    Returns repo-relative POSIX paths (e.g. `"scripts/foo.py"`).
    """
    seen: set[str] = set()
    pending: list[str] = list(_TOOLING_ENTRY_POINT_SCRIPTS)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        path = _SCRIPTS_DIR / name
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        for node in ast.walk(tree):
            module_names: list[str] = []
            if isinstance(node, ast.Import):
                module_names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
                module_names = [node.module]
            for module_name in module_names:
                candidate = module_name.split(".")[0] + ".py"
                if (_SCRIPTS_DIR / candidate).is_file():
                    pending.append(candidate)
    return frozenset(f"scripts/{name}" for name in seen)


def _validate_sealed_tooling_files_catalog() -> None:
    """Fail closed at import time if `SEALED_TOOLING_FILES` (hand-reviewed)
    and `_discover_local_tooling_closure()` (statically re-derived) ever
    disagree -- see `SEALED_TOOLING_FILES`'s own docstring comment above."""
    explicit = frozenset(SEALED_TOOLING_FILES)
    if len(explicit) != len(SEALED_TOOLING_FILES):
        raise EvidenceError(
            f"SEALED_TOOLING_FILES contains a duplicate entry: {SEALED_TOOLING_FILES!r}"
        )
    discovered = _discover_local_tooling_closure()
    missing = discovered - explicit
    extra = explicit - discovered
    if missing or extra:
        raise EvidenceError(
            "SEALED_TOOLING_FILES has drifted from the actual import graph of "
            f"{_TOOLING_ENTRY_POINT_SCRIPTS}: missing={sorted(missing)!r} "
            f"extra={sorted(extra)!r} -- add/remove entries in "
            "SEALED_TOOLING_FILES (scripts/generate_legal_evidence.py) to match."
        )


_validate_sealed_tooling_files_catalog()


def compute_tooling_hashes() -> dict[str, str]:
    """SHA-256 of every `SEALED_TOOLING_FILES` entry's CURRENT bytes on
    disk, keyed by its repo-relative path.

    Used by both `seal_scope_binding()` (to record `tooling_sha256` at seal
    time) and `check_release_evidence.py`'s `check_scope_binding_seal()` (to
    independently recompute and compare against what was sealed). Raises
    `EvidenceError` if any listed file is missing, is a symlink (never trust
    an indirection for something this security-sensitive), or is not a
    regular file.
    """
    hashes: dict[str, str] = {}
    for rel_path in SEALED_TOOLING_FILES:
        path = REPO_ROOT / rel_path
        if path.is_symlink():
            raise EvidenceError(
                f"sealed tooling file {rel_path!r} is a symlink -- refusing to hash it"
            )
        if not path.is_file():
            raise EvidenceError(f"sealed tooling file {rel_path!r} is missing")
        hashes[rel_path] = sha256_file(path)
    return hashes


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def evidence_output_files() -> dict[str, Path]:
    """The evidence-content files sealed by `scope_binding.json`.

    Deliberately excludes `scope_binding.json` itself (written only by
    `--seal`, in a later commit) and `LEGAL_EVIDENCE_DIGEST.txt` (rewritten
    by `--seal` to add the seal file's own digest line, so its bytes
    legitimately differ between the evidence-content commit and every
    commit from the seal commit onward). A plain (non---seal) run against an
    ALREADY-sealed worktree does not lose that digest line, though: see
    `run_generate()`'s opportunistic re-inclusion below, which is what lets
    verify.yml's "regenerate twice"/"cold cache" steps run the plain
    generator on top of an already-sealed tree and still get back the exact
    committed `LEGAL_EVIDENCE_DIGEST.txt` bytes, without that being a second,
    competing way to create or verify the seal itself.
    """
    return {
        "gradle_dependency_inventory.json": EVIDENCE_DIR / "gradle_dependency_inventory.json",
        "gradle_license_inventory.json": EVIDENCE_DIR / "gradle_license_inventory.json",
        "cargo_dependency_inventory.json": EVIDENCE_DIR / "cargo_dependency_inventory.json",
        "uniffi_bindings_inventory.json": EVIDENCE_DIR / "uniffi_bindings_inventory.json",
        "native_artifacts_inventory.json": EVIDENCE_DIR / "native_artifacts_inventory.json",
        "maven_native_carriers_inventory.json": EVIDENCE_DIR / "maven_native_carriers_inventory.json",
        "bouncycastle_license_source.json": EVIDENCE_DIR / "bouncycastle_license_source.json",
        "java_class_version_evidence.json": EVIDENCE_DIR / "java_class_version_evidence.json",
    }


def outputs_including_existing_scope_binding(outputs: dict[str, Path]) -> dict[str, Path]:
    """`outputs` unchanged, or `outputs` plus `scope_binding.json` if that
    file already exists on disk right now.

    Pure/testable half of `run_generate()`'s opportunistic re-inclusion (see
    `evidence_output_files()`'s docstring): does not create, delete, or read
    `scope_binding.json`'s content, only decides whether `write_digest_file()`
    should be asked to re-hash its current bytes.
    """
    scope_binding_path = EVIDENCE_DIR / "scope_binding.json"
    if not scope_binding_path.is_file():
        return outputs
    merged = dict(outputs)
    merged["scope_binding.json"] = scope_binding_path
    return merged


def seal_scope_binding() -> dict[str, Any]:
    """Build `scope_binding.json`'s content. Caller (`main --seal`) must run
    this with a clean worktree at the evidence-content commit; see the
    module docstring above for the two-commit design this implements."""
    status = git("status", "--porcelain")
    if status:
        raise EvidenceError(
            "--seal requires a clean worktree at the already-committed "
            "evidence-content commit (git status --porcelain is non-empty):\n"
            f"{status}"
        )
    scope_binding_path = EVIDENCE_DIR / "scope_binding.json"
    if scope_binding_path.exists():
        raise EvidenceError(
            "docs/evidence/scope_binding.json already exists -- HEAD is "
            "already sealed. Delete it (and reseal after committing new "
            "evidence content) if this is meant to re-seal, rather than "
            "sealing a second time in place."
        )
    outputs = evidence_output_files()
    missing = [name for name, path in sorted(outputs.items()) if not path.is_file()]
    if missing:
        raise EvidenceError(
            f"--seal: expected evidence file(s) missing, run generate_legal_evidence.py "
            f"(without --seal) first: {missing}"
        )

    evidence_commit = git("rev-parse", "HEAD")
    evidence_tree = git("rev-parse", "HEAD^{tree}")
    try:
        subject_commit = git("rev-parse", "HEAD^")
        subject_tree = git("rev-parse", "HEAD^^{tree}")
    except subprocess.CalledProcessError as exc:
        raise EvidenceError(
            "--seal: HEAD has no parent commit to bind as the subject-source "
            "commit (is this the repository's very first commit?)"
        ) from exc

    return {
        "note": (
            "Two-commit seal (see scripts/generate_legal_evidence.py's module "
            "docstring 'Scope binding'). evidence_commit/evidence_tree are "
            "the commit/tree that carried the evidence-content files listed "
            "in sealed_evidence_digests (this commit's own hash, read back "
            "via `git rev-parse HEAD` while sealing). subject_commit/"
            "subject_tree are that commit's immediate parent -- the "
            "immutable subject-source commit actually inventoried "
            "(crypto-signing-backend/Cargo.lock, every */gradle.lockfile, "
            "CHECKSUMS.sha256, NOTICE, LICENSES/*.txt as they existed there, "
            "PLUS every file listed as a key of tooling_sha256 as it existed "
            "there -- the subject commit is where the sealed tool version is "
            "pinned). sealed_evidence_digests is the SHA-256 of each "
            "evidence file's bytes as committed at evidence_commit. "
            "tooling_sha256 is the SHA-256 of every "
            "scripts/generate_legal_evidence.py SEALED_TOOLING_FILES entry's "
            "bytes as of this same evidence-content commit's worktree -- "
            "kept as additional, narrower audit detail alongside the "
            "authoritative check, not the completeness proof itself (see "
            "the 'Full source-scope binding' module docstring). "
            "scripts/check_release_evidence.py's check_scope_binding_seal() "
            "independently recomputes sealed_evidence_digests and "
            "tooling_sha256 from both the current worktree and "
            "`git show <evidence_commit>:<path>` / "
            "`git show <subject_commit>:<path>`, requires evidence_commit to "
            "be the effective seal tip's immediate parent (HEAD itself, or "
            "-- only when the current GITHUB_EVENT_NAME/GITHUB_EVENT_PATH "
            "event payload validates HEAD as a genuine, same-repository "
            "GitHub pull_request merge-ref of exactly the sealed branch, "
            "checked via exact GitHub parent order against the event's "
            "own base.sha/head.sha plus a byte-identical merge tree, never "
            "by tree shape alone; see _github_pull_request_merge_head() -- "
            "the validated PR-head parent that is the seal commit). The "
            "seal must remain the exact effective tip; any later commit "
            "requires a fresh subject/evidence/seal sequence), and "
            "separately diffs EVERY "
            "tracked file between subject_commit and HEAD, failing on any "
            "change outside the exact reviewed set of generated evidence/ "
            "seal outputs -- see check_full_source_scope_seal()."
        ),
        "evidence_commit": evidence_commit,
        "evidence_tree": evidence_tree,
        "subject_commit": subject_commit,
        "subject_tree": subject_tree,
        "sealed_evidence_digests": {
            name: sha256_file(path) for name, path in sorted(outputs.items())
        },
        "tooling_sha256": compute_tooling_hashes(),
    }


# ---------------------------------------------------------------------------
# Output plumbing
# ---------------------------------------------------------------------------


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")


def concat_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.as_posix()):
        digest.update(read_bytes_no_symlink(path))
    return digest.hexdigest()


# The exact, fixed comment/header lines `digest_file_lines()` always emits
# before any `key=value` line -- part of this file's "exact schema" contract
# with `scripts/check_release_evidence.py`'s `check_digest_file_exact()`,
# which rejects any OTHER comment line, in any position, as an unrecognized
# addition (no ad hoc notes/comments are permitted in a committed digest
# file, even though this parser could technically tolerate them).
DIGEST_FILE_HEADER_LINES: tuple[str, ...] = (
    "# Legal Evidence Digest",
    "#",
    "# Deterministic SHA-256 digests over locked/committed inputs and the",
    "# evidence files this script generates. Regenerate with",
    "# `python3 scripts/generate_legal_evidence.py` and diff against this",
    "# file; a clean regeneration must produce byte-identical output for the",
    "# tracked-tree-derived fields. See docs/LEGAL_REVIEW.md \u00a78 for the",
    "# Gradle-license/native-carrier fields, which depend on the local",
    "# Gradle module cache and are not tracked-tree-derived.",
    "",
)


def digest_file_lines(modules: tuple[str, ...], generated: dict[str, Path]) -> list[str]:
    """Pure builder for `LEGAL_EVIDENCE_DIGEST.txt`'s exact line sequence.

    Used by both `write_digest_file()` (this module) and
    `scripts/check_release_evidence.py`'s `check_digest_file_exact()`, so
    the committed file's exact key SET, key ORDER, and every value are all
    recomputed from a single source of truth instead of two independently
    hand-maintained implementations that could silently drift apart from
    each other.
    """
    lockfiles = [REPO_ROOT / m / "gradle.lockfile" for m in modules]
    licenses = sorted((REPO_ROOT / "LICENSES").glob("*.txt"))
    lines = list(DIGEST_FILE_HEADER_LINES)
    lines += [
        f"gradle_modules={','.join(sorted(modules))}",
        f"gradle_lockfiles_sha256={concat_sha256(lockfiles)}",
        f"cargo_lock_sha256={sha256_file(SIGNING_BACKEND / 'Cargo.lock')}",
        f"native_checksums_sha256={sha256_file(SIGNING_BACKEND / 'CHECKSUMS.sha256')}",
        f"notice_sha256={sha256_file(REPO_ROOT / 'NOTICE')}",
        f"licenses_sha256={concat_sha256(licenses)}",
        f"licenses_files={','.join(sorted(p.name for p in licenses))}",
    ]
    for name, path in sorted(generated.items()):
        lines.append(f"{name}_sha256={sha256_file(path)}")
    lines.append(f"expected_evidence_files={','.join(sorted(generated.keys()))}")
    return lines


def write_digest_file(modules: tuple[str, ...], generated: dict[str, Path]) -> None:
    lines = digest_file_lines(modules, generated)
    (EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def run_generate(bcprov_jar_path: Path | None = None) -> int:
    outputs = evidence_output_files()
    try:
        modules = discover_gradle_modules()
        gradle_report = gradle_dependency_inventory(modules)
        write_json(outputs["gradle_dependency_inventory.json"], gradle_report)
        write_json(
            outputs["gradle_license_inventory.json"], gradle_license_inventory(gradle_report)
        )
        write_json(outputs["cargo_dependency_inventory.json"], cargo_dependency_inventory_per_target())
        write_json(outputs["uniffi_bindings_inventory.json"], uniffi_bindings_inventory())
        write_json(outputs["native_artifacts_inventory.json"], native_artifacts_inventory())
        write_json(
            outputs["maven_native_carriers_inventory.json"],
            maven_native_carriers_inventory(gradle_report),
        )
        write_json(
            outputs["bouncycastle_license_source.json"], bouncycastle_license_source_inventory()
        )
        write_json(
            outputs["java_class_version_evidence.json"],
            java_class_version_evidence(bcprov_jar_path),
        )
        write_digest_file(modules, outputs)
        # This run does not create, verify, or touch the seal itself (that is
        # exclusively `--seal`'s job) -- it only avoids clobbering an
        # ALREADY-sealed tree's LEGAL_EVIDENCE_DIGEST.txt shape with the
        # unsealed one above, purely by re-hashing scope_binding.json's
        # existing, untouched bytes if that file happens to already be on
        # disk (e.g. a plain re-run against an already-sealed worktree).
        sealed_outputs = outputs_including_existing_scope_binding(outputs)
        if sealed_outputs is not outputs:
            write_digest_file(modules, sealed_outputs)
    except (EvidenceError, FileNotFoundError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"legal evidence generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"legal evidence written to {EVIDENCE_DIR.relative_to(REPO_ROOT)}/")
    print(
        "NOTE: docs/evidence/scope_binding.json is not written by this "
        "command. Commit the files above first, then run "
        "'python3 scripts/generate_legal_evidence.py --seal' against that "
        "clean commit -- see the 'Scope binding' module docstring above."
    )
    return 0


def run_seal() -> int:
    outputs = evidence_output_files()
    scope_binding_path = EVIDENCE_DIR / "scope_binding.json"
    try:
        binding = seal_scope_binding()
        write_json(scope_binding_path, binding)
        sealed_outputs = dict(outputs)
        sealed_outputs["scope_binding.json"] = scope_binding_path
        write_digest_file(discover_gradle_modules(), sealed_outputs)
    except (EvidenceError, FileNotFoundError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"legal evidence seal failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"docs/evidence/scope_binding.json sealed: evidence_commit="
        f"{binding['evidence_commit']} subject_commit={binding['subject_commit']}"
    )
    print(
        "Commit docs/evidence/scope_binding.json and the updated "
        "LEGAL_EVIDENCE_DIGEST.txt as the seal commit."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seal",
        action="store_true",
        help=(
            "Write docs/evidence/scope_binding.json binding the current, "
            "already-committed, clean HEAD (as 'evidence_commit') to its "
            "immediate parent commit (as 'subject_commit'). Run this AFTER "
            "committing the output of a normal (non---seal) run. See the "
            "'Scope binding' module docstring above."
        ),
    )
    parser.add_argument(
        "--bcprov-jar",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "An already-resolved, verified org.bouncycastle:bcprov-jdk18on:"
            "1.85.2 .jar to live-scan for java_class_version_evidence.json "
            "instead of fetching one from Maven Central (e.g. a local "
            "Gradle-cache copy, for offline iteration). Must exist; a "
            "missing path is an error, never a silent skip. Same effect as "
            f"setting the {BCPROV_JAR_PATH_ENV_VAR} environment variable "
            "(this flag takes precedence if both are set). Ignored by "
            "--seal."
        ),
    )
    args = parser.parse_args()
    if args.seal:
        return run_seal()
    return run_generate(args.bcprov_jar)


if __name__ == "__main__":
    raise SystemExit(main())
