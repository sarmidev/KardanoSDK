# ADR-0008: Crypto Dependency Evaluation And Module Decision

| Field   | Value                                             |
|---------|---------------------------------------------------|
| Status  | **Accepted** (module / seam / process only — see "Scope of this Accepted status") |
| Scope   | Phase 1 Block 1.4 crypto evaluation and module decision |
| Phase   | Phase 1 (Block 1.4)                              |
| Updated | 2026-07-11                                        |

---

## Context

ADR-0004 (crypto strategy) established the hard rules — no handwritten cryptography, every
primitive delegated to an externally maintained library or platform binding, selected per
algorithm through documented evaluation — and left a candidate matrix in which every entry is
`Needs investigation` / `Unverified`. ADR-0005 §4 sequenced the crypto work as Block 1.4
(evaluation and module decision) and Block 1.5 (primitives needed for wallet), with priority
algorithms Ed25519-BIP32, BIP-32/CIP-1852, BIP-39/CIP-3, PBKDF2-HMAC-SHA-512, HMAC-SHA-512,
and Blake2b-224/256.

Block 1.4 is a docs-only decision block. It does not add any dependency, create any module, or
run any build. It fixes the decisions that are independent of which library wins (module timing,
seam shape, first algorithm boundary, and the Block 1.5 process) and records a source-cited
candidate matrix. It deliberately does not commit to a final dependency: no candidate has been
compiled against this repository yet.

### Scope of this Accepted status

This ADR is `Accepted` for the module, seam, and process decisions in the "Decided now" section.
It makes **no** claim of final dependency fitness. Candidate selection is provisional and is
resolved only after the Block 1.5a compatibility spike (below). Facts about third-party
libraries are recorded with their source; anything not confirmed from a source is marked
`Unverified` or `To verify in 1.5a`. This ADR uses neutral review fields (`External review`,
`Public review notes`) and makes no fitness or implementation-readiness claim about any
candidate.

### Algorithm needs for Phase 1 (mapped to blocks)

- BIP-39 / CIP-3 mnemonic to seed — Block 1.6. Needs PBKDF2-HMAC-SHA-512.
- Ed25519-BIP32 (Cardano extended-key scheme) + CIP-1852 path
  `m / 1852' / 1815' / account' / role / index`, Icarus / HD-Sequential — Block 1.6. Needs
  HMAC-SHA-512. (Source: CIP-1852, https://cips.cardano.org/cip/CIP-1852.)
- Blake2b-224 (credential hashes) / Blake2b-256 (transaction, datum, script hashes) — Blocks
  1.7 and 1.9.
- Ed25519 sign/verify — Block 1.10 (verify may land earlier to check vectors).
- Platform CSPRNG for entropy — Block 1.6; platform-provided only (ADR-0004 §Randomness).

---

## Decision

### Decided now (Accepted)

#### 1. The `:crypto` Gradle module is deferred to Block 1.5

No module is created in Block 1.4. `:crypto` is created in Block 1.5 — the block that first adds
a crypto dependency — consistent with ADR-0002/ADR-0005 ("extract a module when dependency or
ownership pressure justifies it"). The candidate name is `:crypto` (not final). It will be a
Kotlin Multiplatform module (Android library + JVM + iosArm64 + iosSimulatorArm64,
`explicitApi()`) depending only on `:core`, mirroring how `:provider` was shaped in Block 1.3a.
Crypto does not land in `:core` (dependency-free, structural) or `:shared` (sample/UI host).

#### 2. Seam shape: a common interface / adapter in `commonMain`

Per ADR-0004 §4, the seam is a `commonMain` common interface / adapter, not a call-site
`expect`/`actual`. Block 1.5 introduces small library-agnostic interfaces —
`Hashing` first, later `KeyDerivation` and `Signing` — whose failable operations return
`KardanoResult` with a typed sealed error and never throw across the Swift/ObjC boundary
(ADR-0004 §6). The concrete library is a swappable implementation behind these interfaces, so
the public API does not name or leak any library. `expect`/`actual` is the fallback pattern,
used only if the chosen stack lacks a single `commonMain` API covering all required targets
(for example a platform-seam composition). The interface shape does not depend on which
candidate wins Block 1.5a.

#### 3. First algorithm boundary: Blake2b-224 / Blake2b-256 behind `Hashing`

Block 1.5 lands hashing first: Blake2b-224 and Blake2b-256 behind the `Hashing` interface.
Rationale: it is keyless and deterministic (no key-material lifecycle surface yet), it is the
simplest boundary to test, and it unblocks Block 1.7 (credential hashing) and Block 1.9
(transaction/script hashes). Block 1.5 must use official, cited Blake2b test vectors (RFC 7693,
and the Cardano context where relevant) copied verbatim, and must not invent vectors
(ADR-0004 §7, `docs/TESTING.md`). Seed derivation, key derivation, and signing follow in Blocks
1.6 and 1.10.

### Provisional (no final fitness claim)

#### 4. Candidate selection is provisional

The Hyperledger Identus Apollo stack (`org.hyperledger.identus:apollo` plus its
`bip32-ed25519` module) is the current provisional lead because it is the only evaluated
candidate that covers all required targets and the full algorithm set including Ed25519-BIP32.
This is not yet a final adoption: the concrete decision to adopt and wire it lands in 1.5b. Its
compatibility with this repository's Kotlin version was untested when this ADR was first written;
the Block 1.5a spike has since confirmed it **resolves and compiles** under Kotlin 2.4.0 on
Android + JVM + iosSimulatorArm64 (see §6). Had it failed the Block 1.5a spike, the fallback order
would have been (a) a multi-library composition (cryptography-kotlin for SHA-512/HMAC/PBKDF2/
standard Ed25519 + a Blake2b source + a dedicated Ed25519-BIP32 library), then (b) the ADR-0004
A+B platform seam.

#### 5. Block 1.5 process: a compatibility spike (`1.5a`) gates any dependency commit

Block 1.5 begins with substep **1.5a**, a small throwaway compatibility spike, before any
dependency is committed:

- On a throwaway branch, add the provisional candidate (and its transitive companions, for
  example `secp256k1-kmp`) to a scratch module.
- Confirm it resolves and compiles on Android + JVM + iosSimulatorArm64 under this repository's
  Kotlin version (currently `2.4.0`, per `gradle/libs.versions.toml`).
- If it fails, discard the branch and repeat 1.5a with the next fallback candidate.
- Record the outcome (which candidate, which targets, versions) in this ADR's matrix or a
  short follow-up note.

Only after 1.5a passes does substep **1.5b** create `:crypto`, add the chosen dependency
(pinned, no dynamic versions), wire it behind the `Hashing` interface, and add the official
Blake2b vectors. No dependency is committed to the build before 1.5a passes.

#### 6. Block 1.5a spike result — PASS (compile compatibility)

The Block 1.5a throwaway spike ran on 2026-07-11 on a disposable branch
(`spike/1.5a-apollo-kotlin24`, since discarded) using a scratch `:crypto-spike` module that
depended only on the two candidate artifacts (versions pinned inline; no version-catalog change).
The candidate **resolved and compiled** on all three required targets under this repository's
Kotlin 2.4.0 / AGP 9.0.1 setup (the new `com.android.kotlin.multiplatform.library` plugin):

| Target | Gradle task | Result |
|--------|-------------|--------|
| JVM | `:crypto-spike:compileKotlinJvm` | compiled |
| iOS simulator (arm64) | `:crypto-spike:compileKotlinIosSimulatorArm64` | compiled (commonMain metadata + `iosSimulatorArm64` klib) |
| Android | `:crypto-spike:testAndroidHostTest` (runs `compileAndroidMain`) | compiled |

Exact resolved versions: `org.hyperledger.identus:apollo:1.8.8` and
`dev.allain:bip32-ed25519:2.3.0`. **Correction to §4 and the matrix:** the spike did **not** need
`org.hyperledger.identus:secp256k1-kmp:1.8.8`. Apollo pulls
`fr.acinq.secp256k1:secp256k1-kmp:0.16.0` transitively, and the Kotlin stdlib versions the
candidates declare (Apollo 1.9.25, secp256k1-kmp 1.9.22, bip32-ed25519 2.2.0) all upgrade to
2.4.0 without conflict.

Scope of this result: it establishes **dependency resolution and Kotlin compilation/typecheck**
(including the iOS-simulator klib) only. It does **not** establish runtime cryptographic
correctness, iOS-simulator/device execution, or native-binary linkage — those are validated in
1.5b via official cited vectors. The concrete decision to adopt and wire the dependency is made
in 1.5b, not here. No dependency was committed to the main build by the spike (the scratch module
and its `settings.gradle.kts` entry were discarded).

### Explicitly deferred

Transaction signing (Block 1.10), the wallet persistence model, the final per-platform
entropy/CSPRNG API, and any multi-library composition details are out of scope for Blocks 1.4
and 1.5b's first boundary.

---

## Candidate evaluation matrix

Facts are stated with their source. Anything not confirmed from a source is marked `Unverified`
or `To verify in 1.5a`. Review status uses neutral fields only and implies no fitness claim.
This advances ADR-0004's matrix from `Needs investigation`; it does not replace ADR-0004.

### Candidate 1 — cryptography-kotlin (whyoleg)

| Field | Value |
|-------|-------|
| Identifier | `dev.whyoleg.cryptography:cryptography-*`, v0.6.0 |
| Category (ADR-0004) | C (pure-Kotlin / KMP-native) |
| Source | github.com/whyoleg/cryptography-kotlin; release 0.6.0 notes, 2026-04-01 |
| Supported algorithms | SHA-256/384/512, SHA-1/SHA-3, HMAC, PBKDF2, HKDF, Ed25519 (EdDSA), X25519, RSA/ECDSA, AES (per supported-algorithms table) |
| Blake2b | Not listed (missing) |
| Ed25519-BIP32 | Not provided (standard Ed25519 only) |
| KMP targets | JDK, Apple/CryptoKit, OpenSSL (all K/N), WebCrypto; Android via JVM. Exact per-target provider coverage for our targets: To verify in 1.5a |
| commonMain API | Yes (unified multiplatform API) |
| Maintenance | Active; 0.6.0 released 2026-04 |
| License | Unverified (Apache-2.0 expected; confirm SPDX in 1.5a) |
| External review | unknown |
| Public review notes | none located |
| Test vectors | Standard-algorithm coverage; project test suites exist. Blake2b/Ed25519-BIP32 not applicable |
| KMP integration complexity | Low (single common dependency) |
| Risks / unknowns | No Blake2b; no Ed25519-BIP32 — insufficient alone for the Cardano derivation path |
| Recommendation | Strong for the seed/HMAC/PBKDF2/standard-Ed25519 slice; must be combined with a Blake2b source and an Ed25519-BIP32 library |

### Candidate 2 — ionspin kotlin-multiplatform-libsodium

| Field | Value |
|-------|-------|
| Identifier | `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings`, v0.9.5 |
| Category (ADR-0004) | B/C (libsodium wrapper across JVM/native/JS) |
| Source | github.com/ionspin/kotlin-multiplatform-libsodium; README + release 0.9.5, 2025-11-22 |
| Supported algorithms | libsodium surface: Blake2b (generichash), Ed25519 sign/verify, HMAC-SHA-256/512, Ristretto255, AEAD, etc. |
| Ed25519-BIP32 | Not provided (libsodium has no BIP32-Ed25519 derivation) |
| KMP targets | Android, JVM, iosArm64, iosSimulatorArm64, macOS, watchOS, tvOS, linux, mingw, JS (per README platform table) |
| commonMain API | Yes (bindings expose a common API; native libsodium built/bundled per target) |
| Maintenance | Active; 0.9.5 (2025-11) |
| License | Unverified (ISC/BSD-style expected via libsodium + wrapper; confirm SPDX in 1.5a) |
| External review | yes |
| Public review notes | Independent community review of v0.9.x by R. Vandervelde, source cited (reneevandervelde.com, "expect-fun" publications). Upstream README carries an author caution that the wrapper is a new surface and advises independent review before relying on it |
| Test vectors | libsodium-backed; Blake2b via RFC 7693 to be added by us in 1.5b |
| KMP integration complexity | Medium (native build weight / JNA on JVM; minSdk 26 per 0.9.5 notes) |
| Risks / unknowns | minSdk 26 vs project minSdk 24 — To verify in 1.5a; binary size; no Ed25519-BIP32 |
| Recommendation | Candidate for the Blake2b + Ed25519 leaf inside a composition; does not cover Ed25519-BIP32 |

### Candidate 3 — Hyperledger Identus Apollo + bip32-ed25519 (provisional lead)

| Field | Value |
|-------|-------|
| Identifier | `org.hyperledger.identus:apollo` v1.8.8 + `dev.allain:bip32-ed25519` v2.3.0; secp256k1 arrives transitively as `fr.acinq.secp256k1:secp256k1-kmp` v0.16.0 (confirmed in 1.5a — the `org.hyperledger.identus:secp256k1-kmp` companion was not required) |
| Category (ADR-0004) | D (Cardano-adjacent binding/port) + C |
| Source | github.com/hyperledger-identus/apollo (README); klibs.io/package/dev.allain/bip32-ed25519 (v2.3.0, listed 2025-07); Apollo PR #225 |
| Supported algorithms | Ed25519, X25519, Secp256k1, Blake2b, SHA family; **Ed25519-BIP32 HD derivation** via the `bip32-ed25519` module (Rust `ed25519-bip32` under the hood) |
| KMP targets | Android, JVM, iosArm64, iosSimulatorArm64, macOS, JS (per README / klibs listing). 1.5a confirmed **compile** on Android + JVM + iosSimulatorArm64 under Kotlin 2.4.0 |
| commonMain API | Yes |
| Maintenance | Active (IOG/Identus maintainers) |
| License | Unverified (Apache-2.0 expected; confirm SPDX in 1.5a) |
| External review | unknown |
| Public review notes | none located specific to crypto correctness |
| Test vectors | Cardano-context Ed25519-BIP32/CIP-1852 vectors available from IOG/Intersect references (ADR-0004 §7); we cite verbatim in the implementing block |
| KMP integration complexity | Medium/High (multiple artifacts; native `secp256k1-kmp` companion; Rust-derived native pieces) |
| Risks / unknowns | **Kotlin version resolved in 1.5a:** Apollo 1.8.8 declares Kotlin 1.9.25 and bip32-ed25519 2.3.0 declares Kotlin 2.2.0, yet both resolve and compile under this repo's Kotlin 2.4.0 (stdlib coalesces to 2.4.0). Companion artifact resolution also resolved in 1.5a (ACINQ `secp256k1-kmp` 0.16.0, transitive). Remaining: larger surface (Secp256k1/X25519) than the wallet MVP needs; runtime correctness and native-binary linkage are still to be validated in 1.5b via cited vectors |
| Recommendation | Provisional lead — closest single-stack fit for Cardano. **Block 1.5a compatibility spike passed** (resolve + compile on all three targets under Kotlin 2.4.0); adoption and wiring behind `Hashing` are decided in 1.5b |

### Candidate 4 — bloxbean cardano-client-lib (rejected as a shipped dependency)

| Field | Value |
|-------|-------|
| Identifier | `com.bloxbean.cardano:cardano-client-lib`, v0.7.1 |
| Category (ADR-0004) | D (Cardano-specific), JVM/Java |
| Source | cardano-client.dev/docs; developers.cardano.org (Java SDK), 2026 |
| Supported algorithms | Full Cardano crypto: BIP-39, CIP-1852 HD derivation, Ed25519 / Ed25519-BIP32 sign/verify, Blake2b helpers |
| KMP targets | JVM / Java only — **no iOS, not a KMP module** |
| commonMain API | No |
| Maintenance | Active; v0.7.1 |
| License | Unverified (MIT expected; not required since rejected as a shipped dependency) |
| External review | unknown |
| Public review notes | Widely used JVM Cardano library |
| Test vectors | Its own; usable as a cross-check oracle |
| Risks / unknowns | Fails the mandatory iOS target requirement (ADR-0004 target matrix) |
| Recommendation | **Rejected as a shipped SDK dependency** (no iOS/KMP). Retained only as an optional JVM-only test-vector oracle when generating/checking derivation vectors |

### Fallback — ADR-0004 A+B platform seam

| Field | Value |
|-------|-------|
| Composition | BouncyCastle (JVM/Android: Blake2b, HMAC, PBKDF2) + libsodium/Apple CryptoKit (iOS) + an Ed25519-BIP32 port, joined by `expect`/`actual` |
| Category (ADR-0004) | A + B |
| commonMain API | No — call-site `expect`/`actual` |
| KMP integration complexity | High (two+ libraries, per-platform actuals, Ed25519-BIP32 still needed on both sides) |
| Risks / unknowns | Most code and maintenance; Blake2b provider registration on Android (ADR-0004 §Android/JVM provider variance) |
| Recommendation | Documented fallback only, used if no single KMP stack passes the Block 1.5a spike |

### Rejected / out of scope

- Web/Wasm-only crypto libraries — Web/Wasm is not a Phase 1 target (ADR-0004 target matrix).
- VRF / KES and Plutus builtin hashes (keccak-256 / SHA3-256) — out of scope per ADR-0004.

---

## Relationship to ADR-0004

This ADR advances ADR-0004's candidate matrix for the evaluated candidates from
`Needs investigation` to "source-cited with open items", and records the module/seam/process
decisions ADR-0004 left to the implementing block. It does not replace ADR-0004: the hard
rules, key-material lifecycle policy, error policy, target matrix, and test-vector policy in
ADR-0004 remain in force. ADR-0004 carries a one-line cross-reference to this ADR.

---

## Consequences

- Block 1.5 has an actionable start: create `:crypto` (deferred here), introduce the `Hashing`
  interface, and land Blake2b-224/256 with official cited vectors — but only after the 1.5a
  compatibility spike selects a concrete dependency.
- No dependency, module, or build change lands in Block 1.4; the Android baseline stays green
  (Block 1.4 checkpoint: "keep the app compiling").
- The library-agnostic seam means a failed 1.5a spike changes the implementation behind
  `Hashing`, not the public API.

---

## Non-goals

- No crypto implementation, no handwritten algorithms, no signing.
- No dependency added, no module created, no Gradle/Kotlin change in Block 1.4.
- No real mnemonics, private keys, or funds; no embedded test vectors (only cited sources).
- No final dependency-fitness claim while compatibility is untested.
- No claim of external review coverage or implementation readiness for any candidate.

---

## Follow-up work

- Block 1.5a: **complete (PASS).** Compatibility spike for the provisional lead
  (Apollo 1.8.8 + bip32-ed25519 2.3.0) confirmed resolve + compile on Android + JVM +
  iosSimulatorArm64 under Kotlin 2.4.0 (see §6). Fallback per §4 was not needed.
- Block 1.5b (next): create `:crypto`, wire the selected dependency behind `Hashing`, add
  Blake2b-224/256 with RFC 7693 (and Cardano-context) vectors.
- Blocks 1.6 / 1.10: seed/key derivation and signing, each citing CIP-1852 / CIP-3 / BIP-39 /
  RFC 8032 vectors verbatim in the implementing block.
- ADR-0004 (`docs/DECISIONS/0004-crypto-strategy.md`) and ADR-0005
  (`docs/DECISIONS/0005-phase-1-architecture-and-scope.md`) remain the governing decisions this
  ADR aligns with; this ADR does not supersede them.
