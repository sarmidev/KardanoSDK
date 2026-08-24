#!/usr/bin/env python3
"""Generate deterministic distribution-evidence inventories for Prompt 7.

This script never asserts a legal conclusion. It reads already-locked build
state (Gradle `*/gradle.lockfile`, `crypto-signing-backend/Cargo.lock` via
`cargo metadata --locked`, the committed UniFFI-generated Kotlin bindings,
`crypto-signing-backend/CHECKSUMS.sha256`, and -- for the Gradle license and
native-carrier inventories -- the local Gradle module cache when present) and
writes plain, reviewable JSON and text reports under `docs/evidence/`.

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

import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import license_catalog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNING_BACKEND = REPO_ROOT / "crypto-signing-backend"
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence"
SETTINGS_GRADLE = REPO_ROOT / "settings.gradle.kts"

GRADLE_USER_HOME = Path(os.environ.get("GRADLE_USER_HOME", str(Path.home() / ".gradle")))
GRADLE_MODULES2 = GRADLE_USER_HOME / "caches" / "modules-2" / "files-2.1"

INCLUDE_RE = re.compile(r'include\(\s*"(:[^"]+)"\s*\)')


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
                "resolution_method": "curated-catalog",
            }
        else:
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
                "resolution_method": "local-gradle-pom-cache",
            }
        if len(resolved[gav]["licenses"]) == 1 and resolved[gav]["licenses"][0] in (
            "MIT",
            "MIT License",
        ):
            mit_only.append(gav)

    return {
        "method": (
            "Every coordinate is looked up first in scripts/license_catalog.py "
            "(a curated, dated review of the coordinate's own POM), then in the "
            "local Gradle module cache's copy of that coordinate's POM "
            "(GRADLE_USER_HOME/caches/modules-2/files-2.1), parsing every "
            "<license><name> entry (an OR list when more than one is present). "
            "This is NOT reproducible on a machine whose Gradle cache does not "
            "already have that POM resolved -- see docs/LEGAL_REVIEW.md \u00a78. "
            "Unresolved coordinates are listed explicitly with an exact count, "
            "never silently dropped or assumed permissive."
        ),
        "runtime_coordinate_count": len(all_runtime_gavs),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "resolved": resolved,
        "unresolved": sorted(unresolved),
        "mit_only_coordinates": sorted(mit_only),
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
    lock_path = SIGNING_BACKEND / "Cargo.lock"
    before = sha256_file(lock_path)
    result = subprocess.run(
        ["cargo", "metadata", "--locked", "--format-version", "1", "--filter-platform", triple],
        cwd=SIGNING_BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    after = sha256_file(lock_path)
    if before != after:
        raise EvidenceError(
            "cargo metadata --locked mutated Cargo.lock "
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
        ["cargo", "tree", "--locked", "--target", triple, "-e", edges, "--prefix", "none"],
        cwd=SIGNING_BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    after = sha256_file(lock_path)
    if before != after:
        raise EvidenceError(
            "cargo tree --locked mutated Cargo.lock "
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

    return {
        "method": (
            "Two tools per rustc target triple that produces one of the 9 "
            "committed native artifacts (a separate graph for each, not one "
            "merged closure): `cargo metadata --locked --filter-platform <triple>` "
            "supplies per-package facts (license/version/source/targets), and "
            "`cargo tree --locked --target <triple> -e <edges> --prefix none` "
            "supplies the ACTUAL feature-activation-correct reachable set for "
            "'normal' and 'normal,build' edges. `cargo metadata`'s own "
            "`resolve.nodes[].deps` is not used as the reachability source: it "
            "unconditionally lists every dependency edge declared in Cargo.toml, "
            "including optional dependencies gated behind an inactive feature "
            "(confirmed 2026-08-24 -- `uniffi`'s optional bindgen-CLI dependency "
            "chain, `uniffi_bindgen`/`askama`/`goblin`/`nom`/`weedle2`/`textwrap`/"
            "`smawk`/`clap`, appeared as metadata edges despite the feature that "
            "would enable them never being active for this crate's actual build; "
            "`cargo tree` correctly omits all of them). Cargo.lock's own SHA-256 "
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
    "PE-structure evidence (windows-jvm-rebuild-evidence.yml) but remains "
    "unpromoted: not in crypto-signing-backend/CHECKSUMS.sha256, not in this "
    "catalog, and not distributed, pending independent PE re-review and "
    "upstream hyperledger-identus/apollo issue #226."
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
# local Gradle module cache (unzip -l + per-entry SHA-256), the same method
# THIRD_PARTY_NOTICES.md has used since 2026-08-23. This is a point-in-time
# fact about specific artifact bytes, not a live re-derivation: rerunning
# generate_legal_evidence.py on a machine without these exact artifacts
# resolved reproduces the *catalog* (this static table) but cannot
# independently re-confirm the embedded-file hashes without the artifact
# present. See docs/LEGAL_REVIEW.md \u00a78.
MAVEN_NATIVE_CARRIERS: tuple[dict[str, Any], ...] = (
    {
        "maven_coordinate": "org.hyperledger.identus:bip32-ed25519-android:1.8.8",
        "carrier_kind": "Android .aar",
        "license": "Apache-2.0 (wrapper POM); embedded native's own obligations OPEN",
        "distributed_by_kardano": True,
        "windows_native_available_upstream": False,
        "inspected_2026_08_24": True,
        "embedded_natives": [
            {"path": "jni/arm64-v8a/libuniffi_ed25519_bip32_wrapper.so", "size_bytes": 696072},
            {"path": "jni/armeabi-v7a/libuniffi_ed25519_bip32_wrapper.so", "size_bytes": 523692},
            {"path": "jni/x86/libuniffi_ed25519_bip32_wrapper.so", "size_bytes": 708316},
            {"path": "jni/x86_64/libuniffi_ed25519_bip32_wrapper.so", "size_bytes": 668632},
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
        "maven_coordinate": "com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings-jvm:0.9.5",
        "carrier_kind": "JVM .jar",
        "license": "Apache-2.0 (wrapper) + ISC (bundled libsodium binaries)",
        "distributed_by_kardano": True,
        "windows_native_available_upstream": True,
        "inspected_2026_08_24": True,
        "embedded_natives": [
            {"path": "libdynamic-linux-arm64-libsodium.so", "size_bytes": 358168},
            {"path": "libdynamic-linux-x86-64-libsodium.so", "size_bytes": 524432},
            {"path": "libdynamic-macos.dylib", "size_bytes": 829200},
            {"path": "libdynamic-msvc-x86-64-libsodium.dll", "size_bytes": 346624},
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
        "distributed_by_kardano": True,
        "windows_native_available_upstream": False,
        "inspected_2026_08_24": True,
        "embedded_natives": [
            {"path": "jni/arm64-v8a/libsodium.so", "size_bytes": 332824},
            {"path": "jni/armeabi-v7a/libsodium.so", "size_bytes": 341648},
            {"path": "jni/x86/libsodium.so", "size_bytes": 467596},
            {"path": "jni/x86_64/libsodium.so", "size_bytes": 427312},
        ],
        "note": "Android-only carrier; no Windows binary is bundled.",
    },
    {
        "maven_coordinate": "org.jetbrains.skiko:skiko-awt-runtime-macos-arm64:0.144.6",
        "carrier_kind": "JVM .jar (Desktop app runtime classpath)",
        "license": "Apache-2.0",
        "distributed_by_kardano": True,
        "windows_native_available_upstream": False,
        "inspected_2026_08_24": True,
        "embedded_natives": [
            {"path": "libskiko-macos-arm64.dylib", "size_bytes": 21455568},
            {"path": "libskiko-macos-x64.dylib", "size_bytes": 22206704},
        ],
        "note": (
            "Compose Multiplatform/Skia native renderer for the desktopApp "
            "sample only; not part of any SDK module. Only the macOS-arm64 "
            "runtime variant is currently resolved in this repository's "
            "desktopApp/gradle.lockfile; other Skiko OS/arch variants are not "
            "reviewed here."
        ),
    },
    {
        "maven_coordinate": "net.java.dev.jna:jna:5.19.1",
        "carrier_kind": "JVM/Android jar (also used directly by crypto-signing-backend)",
        "license": "Apache-2.0 OR LGPL-2.1-or-later (Kardano SDK elects Apache-2.0)",
        "distributed_by_kardano": True,
        "windows_native_available_upstream": True,
        "inspected_2026_08_24": True,
        "embedded_native_count": 25,
        "embedded_natives_note": (
            "25 platform-specific libjnidispatch native binaries bundled inside "
            "the single jna-5.19.1.jar (com/sun/jna/<platform>/libjnidispatch.*); "
            "see docs/DECISIONS or re-run `unzip -l jna-5.19.1.jar` to enumerate "
            "them all. Only one loads at runtime per host; the jar as distributed "
            "contains all 25. Do not classify JNA as a source-only dependency."
        ),
        "note": "JNA is both a direct SDK dependency and its own native carrier.",
    },
)


def maven_native_carriers_inventory() -> dict[str, Any]:
    return {
        "method": (
            "Point-in-time inspection (2026-08-24) of the actual resolved "
            "artifact bytes in the local Gradle module cache: unzip -l for the "
            "embedded native member list, sizes read directly from the archive "
            "directory. This table is static; it is not re-derived from a live "
            "artifact fetch on every run (see docs/LEGAL_REVIEW.md \u00a78 for why, "
            "and the re-verification command). Distinct from "
            "crypto-signing-backend/CHECKSUMS.sha256, which lists only "
            "first-party binaries built from this repository's own Rust crate."
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
# Scope binding (subject tree vs evidence-packet tree)
# ---------------------------------------------------------------------------


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def scope_binding() -> dict[str, Any]:
    # This is the commit/tree the generator ran against -- necessarily the
    # PARENT of whatever commit later carries these generated files, since a
    # commit cannot record its own resulting tree hash. See "binding design"
    # in docs/LEGAL_REVIEW.md \u00a76 for why this is not, and cannot be, made
    # self-referential.
    return {
        "note": (
            "subject_commit/subject_tree are the repository HEAD at generation "
            "time (the parent of whatever commit carries this evidence). They "
            "are NOT the hash of the commit that will contain this file -- a "
            "commit cannot know its own resulting tree hash in advance. Compare "
            "against `git log -1 --format=%H` / `%T` on the commit BEFORE the "
            "one that added/updated docs/evidence/ to confirm this binding."
        ),
        "subject_commit": git("rev-parse", "HEAD"),
        "subject_tree": git("rev-parse", "HEAD^{tree}"),
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


def write_digest_file(modules: tuple[str, ...], generated: dict[str, Path]) -> None:
    lockfiles = [REPO_ROOT / m / "gradle.lockfile" for m in modules]
    licenses = sorted((REPO_ROOT / "LICENSES").glob("*.txt"))
    lines = [
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
        f"gradle_modules={','.join(modules)}",
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
    (EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    outputs = {
        "gradle_dependency_inventory.json": EVIDENCE_DIR / "gradle_dependency_inventory.json",
        "gradle_license_inventory.json": EVIDENCE_DIR / "gradle_license_inventory.json",
        "cargo_dependency_inventory.json": EVIDENCE_DIR / "cargo_dependency_inventory.json",
        "uniffi_bindings_inventory.json": EVIDENCE_DIR / "uniffi_bindings_inventory.json",
        "native_artifacts_inventory.json": EVIDENCE_DIR / "native_artifacts_inventory.json",
        "maven_native_carriers_inventory.json": EVIDENCE_DIR / "maven_native_carriers_inventory.json",
        "bouncycastle_license_source.json": EVIDENCE_DIR / "bouncycastle_license_source.json",
        "scope_binding.json": EVIDENCE_DIR / "scope_binding.json",
    }
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
            outputs["maven_native_carriers_inventory.json"], maven_native_carriers_inventory()
        )
        write_json(
            outputs["bouncycastle_license_source.json"], bouncycastle_license_source_inventory()
        )
        write_json(outputs["scope_binding.json"], scope_binding())
        write_digest_file(modules, outputs)
    except (EvidenceError, FileNotFoundError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"legal evidence generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"legal evidence written to {EVIDENCE_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
