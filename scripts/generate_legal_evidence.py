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
script (see `.github/workflows/verify.yml`), so this script itself never
touches the network and a generation run that unexpectedly needed to is a
hard failure, not a silent re-fetch.

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
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tomllib
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


def _classify_by_magic(data: bytes) -> str:
    """Classify one archive member's content, independent of its filename.

    Returns exactly one of:
    - `"native"`: a supported native-code format, positively confirmed --
      either a simple prefix match (ELF/thin Mach-O/ar) or, for fat
      Mach-O/PE/XCOFF, a full bounded structural parse that passed.
    - `"malformed_native_magic"`: the leading bytes matched a recognized
      native-format magic, but the structural parse for that format
      failed. This is a hard failure the caller must never silently
      absorb as `"not_native"` -- with exactly one documented exception
      (see `JAVA_CLASS_COLLISION_FAT_MACHO_MAGIC`): the one fat-Mach-O
      magic that is byte-identical to every Java `.class` file's own
      magic falls back to `"not_native"` instead, since that specific
      4-byte collision has an extremely common, completely legitimate
      innocent explanation this generator already scans past constantly.
    - `"not_native"`: no recognized native-format magic matched at all.
    """
    prefix = data[:MAX_NATIVE_MAGIC_PREFIX_LEN]
    if data[:4] in FAT_MACHO_MAGIC_VARIANTS:
        if _validate_fat_macho_structure(data):
            return "native"
        if data[:4] == JAVA_CLASS_COLLISION_FAT_MACHO_MAGIC:
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
      the member's extension. Never silently accepted OR silently
      ignored; the caller must fail closed and a human reviewer must
      inspect this member.
    - `"extension_magic_mismatch"`: the member's extension IS one of
      `NATIVE_MEMBER_EXTENSIONS`, but its content does not match any
      supported native magic signature at all (not even one that then
      failed structural validation -- that case is
      `"malformed_native_magic"` above). Never silently accepted OR
      silently ignored.
    - `"not_native"`: none of the above; ordinary member (a `.class`
      file, a resource, a POM, etc.).
    """
    magic_signal = _classify_by_magic(data)
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


def _scan_zip_for_native_members(archive_path: Path) -> list[dict[str, Any]]:
    reject_symlink(archive_path)
    members: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_MEMBERS_SCANNED:
            raise EvidenceError(
                f"{archive_path}: {len(infos)} zip members exceeds "
                f"MAX_ZIP_MEMBERS_SCANNED={MAX_ZIP_MEMBERS_SCANNED} (refusing to scan)"
            )
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
            discovered = _scan_zip_for_native_members(artifact_path)

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
# EXACTLY `evidence_commit`'s immediate parent, that `evidence_commit` is an
# ancestor of (or equal to) current HEAD, and that every evidence file's
# CURRENT bytes match both the digest recorded here AND the actual bytes
# committed at `evidence_commit`'s tree (`git show <evidence_commit>:<path>`)
# -- so an evidence file edited by some later commit without a re-seal is
# caught even though `check_evidence_is_freshly_regenerable()` would not
# itself notice (regeneration only compares against the CURRENT tracked
# tree, which is exactly the self-reference this two-commit design avoids
# relying on for the seal itself).


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
            "CHECKSUMS.sha256, NOTICE, LICENSES/*.txt as they existed there). "
            "sealed_evidence_digests is the SHA-256 of each evidence file's "
            "bytes as committed at evidence_commit; "
            "scripts/check_release_evidence.py's check_scope_binding_seal() "
            "independently recomputes these from both the current worktree "
            "and `git show <evidence_commit>:<path>` and fails on any "
            "mismatch, ancestry violation, or non-immediate-parent binding."
        ),
        "evidence_commit": evidence_commit,
        "evidence_tree": evidence_tree,
        "subject_commit": subject_commit,
        "subject_tree": subject_tree,
        "sealed_evidence_digests": {
            name: sha256_file(path) for name, path in sorted(outputs.items())
        },
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


def run_generate() -> int:
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
    args = parser.parse_args()
    if args.seal:
        return run_seal()
    return run_generate()


if __name__ == "__main__":
    raise SystemExit(main())
