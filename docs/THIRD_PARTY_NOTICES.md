# Third-Party Components And Notices

Kardano SDK source files are licensed under Apache-2.0. Dependencies, generated bindings, and
prebuilt native artifacts remain subject to their own licences. This page is an initial inventory,
not a replacement for a release-time dependency and notice review.

**2026-08-24 reconciliation (Prompt 7 legal-evidence packet).** This page is
now cross-referenced against generated, deterministic inventories rather than
narrative-only claims:

- Root [`NOTICE`](../NOTICE) and [`LICENSES/`](../LICENSES/README.md) hold the
  verbatim license texts and per-component attribution for every license
  actually used below.
- [`docs/LEGAL_REVIEW.md`](LEGAL_REVIEW.md) is the owner/counsel evidence
  checklist (not legal advice, not approval).
- [`docs/evidence/`](evidence/) holds the generated Gradle/Cargo/UniFFI/
  native-artifact/Maven-native-carrier inventories
  (`scripts/generate_legal_evidence.py`), checked for internal consistency by
  `scripts/check_release_evidence.py`.
- JNA 5.19.1 (`Apache-2.0 OR LGPL-2.1`) and the `ed25519-bip32`/`cryptoxide`
  Rust crates (`MIT OR Apache-2.0`, compiled into all 9 committed
  `crypto-signing-backend` native artifacts) are **dual-licensed**; Kardano
  SDK elects **Apache-2.0** for this distribution for all three (see
  `docs/LEGAL_REVIEW.md` §5).
- The `uniffi` Rust crate (`=0.29.5`, single-license MPL-2.0, not dual) is
  also compiled into all 9 committed native artifacts, alongside the
  first-party `ed25519-bip32` wrapper code. Its MPL-2.0 file-level obligation
  is reviewed in `docs/LEGAL_REVIEW.md` §6, same as `lazysodium-android`.
- **Not distributed, stated explicitly:** the Windows x86-64 JVM
  signing-backend candidate DLL and the Identus `apollo` derivation-backend
  Windows native library are both **not** part of any Kardano SDK release
  artifact. See "Windows candidate and Identus derivation DLL are not
  distributed" below.

## Directly documented components

Each row's "Kind" marks whether the component is a **source** dependency (compiled from/against
its own source into our modules), a **test-only** dependency (never in a shipped artifact), or a
component that **redistributes a native binary** (a compiled shared library bundled inside the
Gradle artifact itself, not built by this project). A component can be both a source dependency
and a redistributed-native-binary carrier at the same time (see `bip32-ed25519` and the two
libsodium rows below); that is noted per row rather than forcing one label.

| Component | Kind | Use in Kardano SDK | Documented licence |
|---|---|---|---|
| Kotlin and Kotlin Multiplatform | Source | Language, build plugins, standard libraries | Apache-2.0 |
| Ktor | Source | Blockfrost HTTP client | Apache-2.0 |
| kotlinx.serialization / coroutines / atomicfu | Source | Serialization, concurrency, generated binding support | Apache-2.0 |
| Compose Multiplatform and AndroidX | Source | Sample Playground UI | Apache-2.0 |
| Bouncy Castle (`bcprov-jdk18on` 1.85.2) | Source | JVM/Android PBKDF2 platform seam | MIT-style Bouncy Castle licence |
| `org.kotlincrypto.hash:blake2` | Source | Blake2b-224/256 hashing backend (`:crypto`) | Apache-2.0 |
| `org.kotlincrypto.hash:sha2` | Source | SHA-256 hashing backend (`:crypto`) | Apache-2.0 |
| `org.hyperledger.identus:bip32-ed25519` (`dev.allain`/`bip32-ed25519`, part of the `hyperledger-identus/apollo` monorepo) | Source + redistributed native binary | Android/iOS/JVM key derivation backend | **Apache-2.0** (confirmed 2026-08-23 by fetching the published `LICENSE` at `github.com/hyperledger-identus/apollo`, copyright 2024 Input Output Global — matches the artifact's own declared licence). Its Android `.aar` bundles a compiled Rust native library per ABI (`libuniffi_ed25519_bip32_wrapper.so`, confirmed by inspecting the actual distributed artifact — see below). This repository has **not** obtained that native library's own source or build-time dependency graph and does **not** claim an exact source-to-binary mapping for it; given the library name (`libuniffi_...`) it plausibly links a UniFFI runtime the same way this repo's own `crypto-signing-backend` does, which would carry the same MPL-2.0 file-level question reviewed below for `uniffi`/`lazysodium-android` — but this is a plausible, unverified structural similarity, not a fact. Whether the wrapper's declared Apache-2.0 covers the whole distributed `.so`, and whether an embedded MPL-2.0 (or other) component changes that, is an **OPEN counsel determination** (see `docs/LEGAL_REVIEW.md` §6b), tracked separately from upstream `hyperledger-identus/apollo` issue #226 (a distribution-availability gap, not this license question). |
| IonSpin libsodium bindings (`com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings`) | Source + redistributed native binary | JVM/iOS public-key projection | **Apache-2.0** (confirmed 2026-08-23 by fetching the published `LICENSE` at `github.com/ionspin/kotlin-multiplatform-libsodium`, copyright 2019 Ugljesa Jovanovic). Its JVM artifact bundles compiled `libsodium` (the upstream C library) binaries directly for macOS/Linux/Windows (confirmed by inspecting the actual `.jar`: `libdynamic-macos.dylib`, `libdynamic-linux-{arm64,x86-64}-libsodium.so`, `libdynamic-msvc-x86-64-libsodium.dll`) — see the separate `libsodium` row below for that binary's own licence. |
| LazySodium Android (`com.goterl:lazysodium-android`) | Source + redistributed native binary | Android public-key projection | **Mozilla Public License 2.0 (MPL-2.0)** (confirmed 2026-08-23 via the GitHub API's `license` metadata and the published `LICENSE.md` at `github.com/terl/lazysodium-android`, matching the artifact's own Maven Central POM `<licenses>` block). MPL-2.0 is **file-level, not whole-program, copyleft**: §3.2 requires that the covered *source form* remain available under MPL-2.0 terms and that recipients be told how to obtain it. Kardano SDK does not modify `lazysodium-android`'s own source, and recipients can obtain that source form from the upstream repository above — but **whether that fully discharges every MPL-2.0 obligation for a dependency compiled/linked into a distributed binary (as opposed to merely redistributed unmodified) is an OPEN counsel determination**, not asserted satisfied here (see `docs/LEGAL_REVIEW.md` §6). Its Android `.aar` also bundles a compiled `libsodium.so` per ABI (confirmed by inspecting the actual artifact) — see the `libsodium` row below. |
| `libsodium` (C library; not a direct Gradle dependency) | Redistributed native binary only | Bundled, compiled, inside both the IonSpin JVM artifact and the LazySodium Android artifact above (confirmed by inspecting both artifacts' contents: symbol names and embedded strings match the upstream `jedisct1/libsodium` project) | **ISC License** (confirmed 2026-08-23 by fetching the published `LICENSE` at `github.com/jedisct1/libsodium`, copyright 2013-2026 Frank Denis) — a short, permissive, MIT-equivalent licence. |
| JNA 5.19.1 | Source + redistributed native binary | JVM/native signing backend loading | Apache-2.0 OR LGPL-2.1 (Kardano SDK elects **Apache-2.0**; see `docs/LEGAL_REVIEW.md` §5). The single `jna-5.19.1.jar` bundles 27 platform-specific `libjnidispatch` native binaries (`com/sun/jna/<platform>/libjnidispatch.*`, confirmed by a full zip-member enumeration in `docs/evidence/maven_native_carriers_inventory.json` — a prior version of this evidence said 25; two AIX variants were previously missed). Do not classify JNA as source-only. |
| `ed25519-bip32` Rust crate (0.4.2) and its transitive `cryptoxide` dependency (0.5.3) | Source + compiled into all 9 committed native artifacts | Project-owned signing wrapper's cryptographic primitive | MIT OR Apache-2.0 (Kardano SDK elects **Apache-2.0** for this distribution) |
| `uniffi` Rust crate (`=0.29.5`) | Source + compiled into all 9 committed native artifacts | Generated signing backend bindings; single-license (no OR clause) | **MPL-2.0** (file-level copyleft; see `docs/LEGAL_REVIEW.md` §6 — same obligation review as `lazysodium-android` above) |
| Gobley UniFFI bindgen | Source (build-time only) | Offline generation tool only | Apache-2.0 OR MIT |
| JUnit | Test-only | JVM test framework | Eclipse Public License 2.0 |
| Gitleaks CLI `v8.30.1` | CI-only (not redistributed) | Full-history credential scan. Installed by `scripts/install_gitleaks.py` after verifying the official release checksums file. Not a GitHub Action wrapper. | MIT |
| GitHub Actions used by `verify.yml` / `deploy-site.yml` | CI-only (not redistributed) | SHA-pinned javascript/composite Actions. Versions and peeled commit SHAs, plus the Pages upload composite's transitive `actions/upload-artifact` pin, are recorded in [DEPENDENCY_REVIEW.md](DEPENDENCY_REVIEW.md). | Each Action's own upstream licence (typically MIT) |
| Gradle lockfiles and `gradle/verification-metadata.xml` | Build-input metadata (not redistributed) | Per-project locked coordinates and SHA-256 artifact checksums generated by Gradle 9.5.0, plus independently compared publisher checksums in [DEPENDENCY_PROVENANCE.md](DEPENDENCY_PROVENANCE.md). Review notes are in [DEPENDENCY_REVIEW.md](DEPENDENCY_REVIEW.md). | Not a third-party library; checksums describe Maven/Google artifacts already listed above |
| Rust `rust-toolchain.toml` (`1.97.0`) | Offline native rebuild only | rustup pin for regenerating committed signing-backend binaries. Not a Gradle dependency. | MIT OR Apache-2.0 (Rust) |
| `androidx.test:runner` | Test-only | Android instrumented test runner | Apache-2.0 |

The signing-backend module records its pinned versions and a more detailed inventory in
[crypto-signing-backend/README.md](../crypto-signing-backend/README.md).

**Evidence method (2026-08-23, W5-1/W5-3):** the three previously-unresolved rows above were
resolved by downloading and inspecting the actual distributed artifacts from the local Gradle
cache (the `.aar`/`.jar` files themselves — `unzip -l`, `find` for `META-INF`/`LICENSE`/`NOTICE`
entries, and `strings` on the bundled native libraries), then cross-checking against each
upstream project's own published `LICENSE` file (not just the Maven Central listing page). None
of the three artifacts embeds a `LICENSE`/`NOTICE` file inside the `.aar`/`.jar` itself — that
absence is itself a confirmed fact, not an unresolved question — so the licence text above is
sourced from each project's canonical GitHub repository instead. This is not a substitute for
legal counsel review (see the disclaimer below); it is the best evidence obtainable through direct
artifact/repository inspection.

## First-party assets

| Asset | Source | Note |
|---|---|---|
| Kardano SDK icon mark (light/dark variants, low/medium/high resolution PNGs) | Sarmidev (project owner) | First-party artwork, not a third-party component. Derived files — the Android adaptive-icon/legacy launcher PNGs (including the monochrome adaptive layer traced from the adaptive foreground alpha), the iOS `AppIcon` PNGs, the Desktop `.icns`/`.ico`/`.png` icons, the Compose header mark (`kardano_mark_light.png`/`kardano_mark_dark.png`), and the `site/assets/brand/` web derivatives (`kardano-mark-light.png`/`kardano-mark-dark.png` copies, plus `favicon-32.png`/`favicon-64.png`/`apple-touch-icon.png`/`og-image.png` resize/pad-only derivatives, added for the public landing page) — are resized/padded/composited copies of these two source PNGs, added in Block 1.12-pre-d and extended for the landing page. It is not the Kotlin or Cardano logo. |
| Linux x86-64 signing cdylib (`linux-x86-64/libkardano_ed25519_bip32_signing.so`) | First-party (in-tree `crypto-signing-backend` crate) | Committed JNA resource promoted from `ubuntu-22.04` run `32678079715` (SHA-256 `cb4390996d30cb9a6f64ad4cbc1bd301d4400dff0806a41829d574cd1f1b4ed5`). Not a third-party redistributed binary. Scope is Linux x86-64 / glibc >= 2.35. |

## Windows candidate and Identus derivation DLL are not distributed

Two Windows-related native artifacts are explicitly **not** part of any
Kardano SDK release artifact, and neither is in
`crypto-signing-backend/CHECKSUMS.sha256`:

1. **Kardano's own Windows x86-64 JVM signing-backend candidate**
   (`win32-x86-64/kardano_ed25519_bip32_signing.dll`). It has a technical GO
   on native-artifact (PE-structure) evidence in
   `.github/workflows/windows-jvm-rebuild-evidence.yml`, but promotion is
   withheld pending independent PE re-review and upstream issue #226 below.
   See `crypto-signing-backend/README.md` "Windows x86-64 — candidate-only".
2. **The Identus `apollo` derivation-backend native library's Windows
   build.** `org.hyperledger.identus:bip32-ed25519` 1.8.8 ships Android `.so`
   natives per ABI but has not published a `win32-x86-64` build upstream
   (tracked as `hyperledger-identus/apollo` issue #226). Kardano SDK cannot
   distribute what upstream has not built; `:crypto`/`:wallet` JVM tests that
   would exercise this backend on Windows remain blocked by that upstream gap,
   not by a Kardano SDK decision.

Both gates are cross-referenced, not restated with different wording, in
`docs/LEGAL_REVIEW.md` §9/§11 and `docs/HANDOFF.md`.

## Release-time checklist

Before publishing a binary, Maven artifact, app bundle, or other distribution:

1. Generate or obtain a dependency licence report for all Gradle runtime artifacts — see
   `docs/evidence/gradle_dependency_inventory.json` for the deterministic, locked-graph
   starting point (source/runtime/test-only per module).
2. Review the `Cargo.lock` dependency graph for the Rust signing backend — see
   `docs/evidence/cargo_dependency_inventory.json` (`cargo metadata --locked`).
3. Preserve notices required by redistributed native artifacts and generated bindings — see
   root `NOTICE`, `LICENSES/`, and `docs/evidence/uniffi_bindings_inventory.json`.
4. Verify that every copied test vector, code fragment, image, or documentation extract has an
   attribution and licence compatible with its use.
5. Add required attribution text to the release package or a `NOTICE` file — already present at
   the repository root; re-run `python3 scripts/generate_legal_evidence.py` and
   `python3 scripts/check_release_evidence.py` if the dependency graph changed.
6. Record the review date, release tag, and reviewer in the release notes and in
   `docs/LEGAL_REVIEW.md`.
7. Re-run `python3 scripts/check_gitleaks.py` on the tagged commit (full history,
   redacted output) and keep allowlists match-level only.

Do not treat this initial inventory, `NOTICE`, `LICENSES/`, `docs/LEGAL_REVIEW.md`, or
`docs/evidence/` as legal advice or as counsel approval. Consult qualified counsel when
distributing a commercial product or when licence obligations are unclear.
