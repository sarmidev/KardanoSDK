#!/usr/bin/env python3
"""Generate deterministic distribution-evidence inventories for Prompt 7.

This script never asserts a legal conclusion. It reads already-locked build
state (Gradle `*/gradle.lockfile`, `crypto-signing-backend/Cargo.lock` via
`cargo metadata --locked`, the committed UniFFI-generated Kotlin bindings, and
`crypto-signing-backend/CHECKSUMS.sha256`) and writes plain, reviewable JSON
and text reports under `docs/evidence/`.

Determinism rules (checked by `scripts/check_release_evidence.py` and
`scripts/tests/test_generate_legal_evidence.py`):

- No absolute filesystem paths, timestamps, hostnames, or environment values
  are written to any generated file.
- All lists are sorted; all JSON is written with sorted keys and a trailing
  newline.
- Running this script twice against the same tracked tree byte-for-byte
  reproduces every generated file.

Gradle configuration classification is a transparent, documented heuristic
over the *configuration names* recorded by Gradle dependency locking — it is
not a `./gradlew dependencies` run (avoids requiring a full build here) and it
is not a license or legal classification. See `CONFIG_RULES` below for the
exact substrings.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNING_BACKEND = REPO_ROOT / "crypto-signing-backend"
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence"

GRADLE_MODULES = (
    "androidApp",
    "core",
    "crypto",
    "crypto-signing-backend",
    "desktopApp",
    "provider",
    "provider-blockfrost",
    "shared",
    "tx",
    "wallet",
)

# Ordered, first-match-wins substring rules mapping a Gradle configuration
# name to a coarse evidence bucket. Kept as an ordered tuple (not a dict) so
# earlier, more specific rules win over later, broader ones.
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
    entries: list[tuple[str, list[str]]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = LOCKFILE_LINE_RE.match(line)
        if not match:
            continue
        gav, configs_raw = match.group(1), match.group(2)
        if gav == "empty":
            # Gradle's own lockfile marker for configurations that resolved
            # with zero dependencies. Not a dependency coordinate.
            continue
        configs = sorted(configs_raw.split(","))
        entries.append((gav, configs))
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


def gradle_dependency_inventory() -> dict[str, Any]:
    modules: dict[str, Any] = {}
    for module in GRADLE_MODULES:
        lockfile = REPO_ROOT / module / "gradle.lockfile"
        if not lockfile.is_file():
            raise FileNotFoundError(f"missing lockfile for module {module}")
        by_bucket: dict[str, list[str]] = {b: [] for b in BUCKETS}
        for gav, configs in parse_lockfile(lockfile):
            bucket = classify_gav(configs)
            by_bucket[bucket].append(gav)
        for bucket in by_bucket:
            by_bucket[bucket] = sorted(set(by_bucket[bucket]))
        modules[module] = {
            "counts": {b: len(by_bucket[b]) for b in BUCKETS},
            "coordinates": by_bucket,
        }
    return {
        "method": (
            "Parsed from */gradle.lockfile (Gradle dependency locking, "
            "LockMode.STRICT). Classification is a documented substring "
            "heuristic over Gradle configuration names, not a "
            "'./gradlew dependencies' run. 'runtime' = reachable from a "
            "non-test *RuntimeClasspath or an iOS FrameworkExport "
            "configuration (shipped). 'source' = compile-only or "
            "*MainImplementationDependenciesMetadata (compiled against, "
            "runtime shipping reviewed per-component in "
            "docs/THIRD_PARTY_NOTICES.md). 'test' = every configuration for "
            "that coordinate is test-scoped. 'build-tooling' = Gradle/Kotlin/"
            "AGP/lint/codegen machinery, never shipped."
        ),
        "modules": modules,
    }


def run_cargo_metadata() -> dict[str, Any]:
    result = subprocess.run(
        ["cargo", "metadata", "--locked", "--format-version", "1"],
        cwd=SIGNING_BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def strip_local_paths(value: str) -> str:
    """Remove this machine's absolute repo path from a cargo metadata string."""
    repo_uri_prefix = f"path+file://{SIGNING_BACKEND.as_posix()}"
    value = value.replace(repo_uri_prefix, "path+file://<crypto-signing-backend>")
    value = value.replace(str(SIGNING_BACKEND), "<crypto-signing-backend>")
    return value


def cargo_dependency_inventory() -> dict[str, Any]:
    metadata = run_cargo_metadata()
    packages_by_id = {p["id"]: p for p in metadata["packages"]}
    root_id = metadata["resolve"]["root"]

    nodes_by_id = {n["id"]: n for n in metadata["resolve"]["nodes"]}

    reachable_normal_build: set[str] = set()
    reachable_dev_only: set[str] = set()

    def visit(pkg_id: str, via_dev_only: bool, seen: set[str]) -> None:
        if pkg_id in seen:
            return
        seen.add(pkg_id)
        node = nodes_by_id.get(pkg_id)
        if node is None:
            return
        for dep in node.get("deps", []):
            dep_id = dep["pkg"]
            dep_kinds = dep.get("dep_kinds", [])
            kinds = {k.get("kind") for k in dep_kinds} if dep_kinds else {None}
            is_normal_or_build = bool(kinds & {None, "build"})
            is_dev = "dev" in kinds
            if is_normal_or_build and not via_dev_only:
                reachable_normal_build.add(dep_id)
                visit(dep_id, via_dev_only=False, seen=seen)
            elif is_dev or (is_normal_or_build and via_dev_only):
                reachable_dev_only.add(dep_id)
                visit(dep_id, via_dev_only=True, seen=set())

    visit(root_id, via_dev_only=False, seen=set())
    reachable_dev_only -= reachable_normal_build

    packages_report = []
    for pkg_id in sorted(reachable_normal_build | reachable_dev_only):
        pkg = packages_by_id[pkg_id]
        is_proc_macro = any(
            "proc-macro" in t.get("kind", []) for t in pkg.get("targets", [])
        )
        linked_into_native_artifacts = (
            pkg_id in reachable_normal_build and not is_proc_macro
        )
        packages_report.append(
            {
                "name": pkg["name"],
                "version": pkg["version"],
                "license": pkg.get("license"),
                "source": pkg.get("source"),
                "reachable_via": (
                    "normal-or-build" if pkg_id in reachable_normal_build else "dev-only"
                ),
                "is_proc_macro": is_proc_macro,
                "linked_into_native_artifacts": linked_into_native_artifacts,
            }
        )

    root_pkg = packages_by_id[root_id]
    return {
        "method": (
            "cargo metadata --locked --format-version 1, resolved from "
            "crypto-signing-backend/Cargo.lock against Cargo.toml. Packages "
            "reachable only through a dev-dependency edge are 'dev-only' "
            "(test/build harness, never linked into the committed native "
            "artifacts). Packages reachable via a normal or build edge and "
            "not a proc-macro crate are 'linked_into_native_artifacts': true "
            "-- their license terms travel with the compiled .so/.dylib/.a "
            "files in crypto-signing-backend/CHECKSUMS.sha256. Proc-macro "
            "crates run only at compile time and are not present as code in "
            "the compiled output."
        ),
        "root_package": {"name": root_pkg["name"], "version": root_pkg["version"]},
        "package_count": len(packages_report),
        "linked_into_native_artifacts_count": sum(
            1 for p in packages_report if p["linked_into_native_artifacts"]
        ),
        "dev_only_count": sum(
            1 for p in packages_report if p["reachable_via"] == "dev-only"
        ),
        "packages": packages_report,
    }


UNIFFI_BINDING_FILES = (
    "src/commonMain/kotlin/org/sarmidev/kardano/crypto/signing/backend/internal/"
    "kardano_ed25519_bip32_signing.common.kt",
    "src/jvmMain/kotlin/org/sarmidev/kardano/crypto/signing/backend/internal/"
    "kardano_ed25519_bip32_signing.jvm.kt",
    "src/androidMain/kotlin/org/sarmidev/kardano/crypto/signing/backend/internal/"
    "kardano_ed25519_bip32_signing.android.kt",
    "src/nativeMain/kotlin/org/sarmidev/kardano/crypto/signing/backend/internal/"
    "kardano_ed25519_bip32_signing.native.kt",
    "src/nativeInterop/cinterop/headers/kardano_ed25519_bip32_signing/"
    "kardano_ed25519_bip32_signing.h",
)

# src/nativeInterop/cinterop/kardano_ed25519_bip32_signing.def is hand-written
# (see crypto-signing-backend/README.md "Regenerating the committed
# artifacts"), not emitted by the bindgen CLI, so it is listed separately.
HAND_WRITTEN_CINTEROP_FILE = "src/nativeInterop/cinterop/kardano_ed25519_bip32_signing.def"


def sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def uniffi_bindings_inventory() -> dict[str, Any]:
    generated = []
    for relative in sorted(UNIFFI_BINDING_FILES):
        full = SIGNING_BACKEND / relative
        if not full.is_file():
            raise FileNotFoundError(f"missing generated UniFFI binding: {relative}")
        generated.append({"path": relative, "sha256": sha256_file(full)})

    hand_written_path = SIGNING_BACKEND / HAND_WRITTEN_CINTEROP_FILE
    if not hand_written_path.is_file():
        raise FileNotFoundError("missing hand-written cinterop def file")

    return {
        "method": (
            "Static, reviewed list of the files crypto-signing-backend/README.md "
            "documents as generated by the offline gobley-uniffi-bindgen CLI "
            "(0.3.7) against the in-tree uniffi Rust crate (=0.29.5, MPL-2.0). "
            "SHA-256 is of the committed file bytes; it changes only when the "
            "bindings are regenerated in the same commit as a native rebuild "
            "(see crypto-signing-backend/README.md 'Regeneration rule')."
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
        "generated_files": generated,
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


# platform/arch/owner/provenance/rebuild-workflow catalog for every row that
# is allowed to appear in crypto-signing-backend/CHECKSUMS.sha256. Any row in
# that file not present here, or any key here missing from that file, is a
# failure in scripts/check_release_evidence.py.
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

# The Windows candidate is explicitly NOT promoted and MUST NOT be in
# CHECKSUMS.sha256 or NATIVE_ARTIFACT_CATALOG above. Recorded here only so the
# evidence packet states the gate by name.
WINDOWS_CANDIDATE_NOTE = (
    "win32-x86-64/kardano_ed25519_bip32_signing.dll has a technical GO on "
    "PE-structure evidence (windows-jvm-rebuild-evidence.yml) but remains "
    "unpromoted: not in crypto-signing-backend/CHECKSUMS.sha256, not in this "
    "catalog, and not distributed, pending independent PE re-review and "
    "upstream hyperledger-identus/apollo issue #226."
)


def parse_checksums(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, rel_path = line.partition("  ")
        if not digest or not rel_path:
            raise ValueError(f"malformed CHECKSUMS.sha256 line: {line!r}")
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
        raise ValueError(
            "native artifact catalog does not match CHECKSUMS.sha256 exactly: "
            f"missing_from_checksums={missing_from_checksums} "
            f"missing_from_catalog={missing_from_catalog}"
        )

    entries = []
    for rel_path in sorted(checksum_rows):
        catalog = NATIVE_ARTIFACT_CATALOG[rel_path]
        on_disk = SIGNING_BACKEND / rel_path
        if not on_disk.is_file():
            raise FileNotFoundError(f"CHECKSUMS.sha256 references missing file: {rel_path}")
        actual_sha256 = sha256_file(on_disk)
        if actual_sha256 != checksum_rows[rel_path]:
            raise ValueError(
                f"{rel_path}: on-disk SHA-256 {actual_sha256} != "
                f"CHECKSUMS.sha256 {checksum_rows[rel_path]}"
            )
        entries.append(
            {
                "path": rel_path,
                "sha256": actual_sha256,
                **catalog,
            }
        )

    return {
        "method": (
            "Every row is required to appear in both "
            "crypto-signing-backend/CHECKSUMS.sha256 and this script's "
            "NATIVE_ARTIFACT_CATALOG; a mismatch in either direction, or a "
            "SHA-256 mismatch against the committed bytes, fails generation."
        ),
        "artifact_count": len(entries),
        "artifacts": entries,
        "windows_candidate_not_promoted": WINDOWS_CANDIDATE_NOTE,
    }


# Third-party Maven artifacts that bundle their own compiled native binaries,
# distinct from the Kardano-committed artifacts above. This table mirrors the
# artifact-inspection evidence already recorded in
# docs/THIRD_PARTY_NOTICES.md (dated 2026-08-23: unzip -l / find / strings on
# the actual resolved .aar/.jar files). It is not re-derived from a live
# Gradle-cache inspection here, to avoid depending on machine-specific cache
# paths or downloading large binaries into evidence output.
MAVEN_NATIVE_CARRIERS: tuple[dict[str, Any], ...] = (
    {
        "maven_coordinate": "org.hyperledger.identus:bip32-ed25519:1.8.8",
        "carrier_kind": "Android .aar",
        "bundled_native": "libuniffi_ed25519_bip32_wrapper.so (per ABI)",
        "distributed_by_kardano": True,
        "license": "Apache-2.0",
        "windows_native_available_upstream": False,
        "note": (
            "Upstream has not published a win32-x86-64 build "
            "(hyperledger-identus/apollo issue #226); Kardano SDK cannot "
            "distribute what upstream has not built."
        ),
    },
    {
        "maven_coordinate": "com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings:0.9.5",
        "carrier_kind": "JVM .jar",
        "bundled_native": (
            "libdynamic-macos.dylib, libdynamic-linux-{arm64,x86-64}-libsodium.so, "
            "libdynamic-msvc-x86-64-libsodium.dll"
        ),
        "distributed_by_kardano": True,
        "license": "Apache-2.0 (wrapper) + ISC (bundled libsodium binary)",
        "windows_native_available_upstream": True,
        "note": "Windows libsodium .dll ships inside this jar; distinct from the Kardano Windows signing-backend candidate, which is not distributed.",
    },
    {
        "maven_coordinate": "com.goterl:lazysodium-android:5.2.0",
        "carrier_kind": "Android .aar",
        "bundled_native": "libsodium.so (per ABI)",
        "distributed_by_kardano": True,
        "license": "MPL-2.0 (wrapper) + ISC (bundled libsodium binary)",
        "windows_native_available_upstream": False,
        "note": "Android-only carrier; no Windows binary is bundled.",
    },
)


def maven_native_carriers_inventory() -> dict[str, Any]:
    return {
        "method": (
            "Static table mirroring the artifact-inspection evidence dated "
            "2026-08-23 in docs/THIRD_PARTY_NOTICES.md. Distinct from "
            "crypto-signing-backend/CHECKSUMS.sha256, which lists only "
            "first-party binaries built from this repository's own Rust crate."
        ),
        "carriers": list(MAVEN_NATIVE_CARRIERS),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")


def concat_sha256(paths: list[Path]) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.as_posix()):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def write_digest_file(generated: dict[str, Path]) -> None:
    lockfiles = [REPO_ROOT / m / "gradle.lockfile" for m in GRADLE_MODULES]
    licenses = sorted((REPO_ROOT / "LICENSES").glob("*.txt"))
    lines = [
        "# Legal Evidence Digest",
        "#",
        "# Deterministic SHA-256 digests over locked/committed inputs and the",
        "# evidence files this script generates. Regenerate with",
        "# `python3 scripts/generate_legal_evidence.py` and diff against this",
        "# file; a clean regeneration must produce byte-identical output.",
        "",
        f"gradle_lockfiles_sha256={concat_sha256(lockfiles)}",
        f"cargo_lock_sha256={sha256_file(SIGNING_BACKEND / 'Cargo.lock')}",
        f"native_checksums_sha256={sha256_file(SIGNING_BACKEND / 'CHECKSUMS.sha256')}",
        f"notice_sha256={sha256_file(REPO_ROOT / 'NOTICE')}",
        f"licenses_sha256={concat_sha256(licenses)}",
    ]
    for name, path in sorted(generated.items()):
        lines.append(f"{name}_sha256={sha256_file(path)}")
    (EVIDENCE_DIR / "LEGAL_EVIDENCE_DIGEST.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    outputs = {
        "gradle_dependency_inventory": EVIDENCE_DIR / "gradle_dependency_inventory.json",
        "cargo_dependency_inventory": EVIDENCE_DIR / "cargo_dependency_inventory.json",
        "uniffi_bindings_inventory": EVIDENCE_DIR / "uniffi_bindings_inventory.json",
        "native_artifacts_inventory": EVIDENCE_DIR / "native_artifacts_inventory.json",
        "maven_native_carriers_inventory": EVIDENCE_DIR / "maven_native_carriers_inventory.json",
    }
    try:
        write_json(outputs["gradle_dependency_inventory"], gradle_dependency_inventory())
        write_json(outputs["cargo_dependency_inventory"], cargo_dependency_inventory())
        write_json(outputs["uniffi_bindings_inventory"], uniffi_bindings_inventory())
        write_json(outputs["native_artifacts_inventory"], native_artifacts_inventory())
        write_json(
            outputs["maven_native_carriers_inventory"], maven_native_carriers_inventory()
        )
        write_digest_file(outputs)
    except (FileNotFoundError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"legal evidence generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"legal evidence written to {EVIDENCE_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
