# Third-Party Components And Notices

Kardano SDK source files are licensed under Apache-2.0. Dependencies, generated bindings, and
prebuilt native artifacts remain subject to their own licences. This page is an initial inventory,
not a replacement for a release-time dependency and notice review.

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
| `org.hyperledger.identus:bip32-ed25519` (`dev.allain`/`bip32-ed25519`, part of the `hyperledger-identus/apollo` monorepo) | Source + redistributed native binary | Android/iOS/JVM key derivation backend | **Apache-2.0** (confirmed 2026-08-23 by fetching the published `LICENSE` at `github.com/hyperledger-identus/apollo`, copyright 2024 Input Output Global — matches the artifact's own declared licence). Its Android `.aar` bundles a compiled Rust native library per ABI (`libuniffi_ed25519_bip32_wrapper.so`, confirmed by inspecting the actual distributed artifact — see below); that native library's own transitive Rust dependencies (`cryptoxide`, `anyhow`, `bytes`, `uniffi_core`) are MIT/Apache-2.0/MPL-2.0-licensed *dependencies of that upstream project*, not of Kardano SDK — Kardano SDK consumes only the compiled binary and does not fork or modify its source, so no separate source-form obligation attaches to Kardano SDK itself. |
| IonSpin libsodium bindings (`com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings`) | Source + redistributed native binary | JVM/iOS public-key projection | **Apache-2.0** (confirmed 2026-08-23 by fetching the published `LICENSE` at `github.com/ionspin/kotlin-multiplatform-libsodium`, copyright 2019 Ugljesa Jovanovic). Its JVM artifact bundles compiled `libsodium` (the upstream C library) binaries directly for macOS/Linux/Windows (confirmed by inspecting the actual `.jar`: `libdynamic-macos.dylib`, `libdynamic-linux-{arm64,x86-64}-libsodium.so`, `libdynamic-msvc-x86-64-libsodium.dll`) — see the separate `libsodium` row below for that binary's own licence. |
| LazySodium Android (`com.goterl:lazysodium-android`) | Source + redistributed native binary | Android public-key projection | **Mozilla Public License 2.0 (MPL-2.0)** (confirmed 2026-08-23 via the GitHub API's `license` metadata and the published `LICENSE.md` at `github.com/terl/lazysodium-android`, matching the artifact's own Maven Central POM `<licenses>` block). MPL-2.0 is **file-level, not whole-program, copyleft**: §3.2 requires that the covered *source form* remain available under MPL-2.0 terms and that recipients be told how to obtain it — since Kardano SDK does not modify `lazysodium-android`'s own source, this is satisfied by directing recipients to the upstream repository above; it does **not** require Kardano SDK's own source to be released under MPL-2.0. Its Android `.aar` also bundles a compiled `libsodium.so` per ABI (confirmed by inspecting the actual artifact) — see the `libsodium` row below. |
| `libsodium` (C library; not a direct Gradle dependency) | Redistributed native binary only | Bundled, compiled, inside both the IonSpin JVM artifact and the LazySodium Android artifact above (confirmed by inspecting both artifacts' contents: symbol names and embedded strings match the upstream `jedisct1/libsodium` project) | **ISC License** (confirmed 2026-08-23 by fetching the published `LICENSE` at `github.com/jedisct1/libsodium`, copyright 2013-2026 Frank Denis) — a short, permissive, MIT-equivalent licence. |
| JNA 5.19.1 | Source | JVM/native signing backend loading | Apache-2.0 OR LGPL-2.1 |
| `ed25519-bip32` Rust crate | Source | Project-owned signing wrapper | MIT OR Apache-2.0 |
| UniFFI Rust crate | Source | Generated signing backend bindings | MPL-2.0 |
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

## Release-time checklist

Before publishing a binary, Maven artifact, app bundle, or other distribution:

1. Generate or obtain a dependency licence report for all Gradle runtime artifacts.
2. Review the `Cargo.lock` dependency graph for the Rust signing backend.
3. Preserve notices required by redistributed native artifacts and generated bindings.
4. Verify that every copied test vector, code fragment, image, or documentation extract has an
   attribution and licence compatible with its use.
5. Add required attribution text to the release package or a `NOTICE` file.
6. Record the review date, release tag, and reviewer in the release notes.
7. Re-run `python3 scripts/check_gitleaks.py` on the tagged commit (full history,
   redacted output) and keep allowlists match-level only.

Do not treat this initial inventory as legal advice. Consult qualified counsel when distributing a
commercial product or when licence obligations are unclear.
