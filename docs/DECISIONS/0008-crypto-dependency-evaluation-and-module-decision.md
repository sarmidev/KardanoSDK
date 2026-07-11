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
| Supported algorithms | Ed25519, X25519, Secp256k1, PBKDF2-HMAC-SHA-512, SHA family (transitive KotlinCrypto `sha2`/`hmac-sha2`); **Ed25519-BIP32 HD derivation** via the `bip32-ed25519` module (Rust `ed25519-bip32` under the hood). **Correction (Block 1.5b):** Apollo does **not** ship a Blake2b implementation — verified in the published `apollo-jvm-1.8.8.jar` (its `hashing` package contains only `PBKDF2SHA512`) and across Apollo source tags `v1.7.2`–`v1.8.7`; its transitive deps expose no Blake2b either. The earlier "Blake2b" entry here was unverified and is retracted. Apollo remains the lead for Ed25519-BIP32 (Blocks 1.6 / 1.10), not for hashing |
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
- Block 1.5b split into **1.5b-pre** (vector-source gate, docs-only) and **1.5b** (wire +
  test), because the first-boundary test-vector policy (ADR-0004 §7) requires exact, cited
  vectors before any hashing code lands, and one of the two required vectors was not cleanly
  available. See §7 below.
- Block 1.5b: **complete.** `:crypto` created and Blake2b-224/256 wired behind `Hashing`
  with the pinned cited vectors. See §8. During wiring it was found that Apollo 1.8.8 ships
  **no Blake2b** (Candidate-3 correction above), so the hashing backend is KotlinCrypto
  `org.kotlincrypto.hash:blake2` rather than Apollo. `bip32-ed25519` was not added and Apollo
  was not added this block; both are reserved for the later key-derivation blocks (1.6 / 1.10).

#### 7. Block 1.5b-pre vector-source gate result — 224 PASS, 256 PASS

Before creating `:crypto` or writing any hashing code, a blocking gate searched for exact,
official, citable known-answer vectors (concrete input bytes + exact digest + source
URL/commit) for both digest sizes. Outcome on 2026-07-11 (Blake2b-256 pinned in a follow-up
search the same day; see below the table):

| Size | Result | Source |
|------|--------|--------|
| Blake2b-224 | **PASS** | CIP-19 test vectors (CC-BY-4.0). Input: verification key `addr_vk1w0l2sr2zgfm26ztc6nl9xy8ghsk5sh6ldwemlpmp9xylzy4dtf7st80zhd` (bech32-decodable to a 32-byte Ed25519 key). Expected: the 28-byte payment credential extractable from the full CIP-19 address `addr1qx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgse35a3x` (type-00) via `:core` `Address.parse`. Source: https://cips.cardano.org/cip/CIP-19 |
| Blake2b-256 | **PASS** | IntersectMBO Plutus conformance goldens for the unkeyed `blake2b_256` builtin (Apache-2.0), repo `IntersectMBO/plutus`, commit `5e18824e2e0e30656c81d182e0ca512b75e7e57c`, path prefix `plutus-conformance/test-cases/uplc/evaluation/builtin/semantics/blake2b_256/`. Vector 1 (`blake2b_256-empty`): input `#` (0 bytes) → `0e5751c026e543b2e8ab2eb06099daa1d1e5df47778f7787faab45cdf12fe3a8`. Vector 2 (`blake2b_256-length-200`): input `2e7ea84da4bc4d7cfb463e3f2c8647057afff3fbececa1d200` (25 bytes) → `91c60f99b33303c02b39ed93b713e3915a180c3747f3b31e05727618ee401624`. |

Blake2b-256 source validation (why these goldens satisfy the gate): each fixture is a UPLC program
`equalsByteString (blake2b_256 (con bytestring #INPUT)) (con bytestring #EXPECTED)` whose
`.uplc.expected` is `(con bool True)`. The builtin `blake2b_256` is applied to the raw UPLC
bytestring constant `#INPUT` only — no CBOR/UPLC envelope bytes enter the hash input — where `#`
is the empty byte string and `#2e7e…1d200` is exactly the 25-byte input. The Plutus `blake2b_256`
builtin is the same unkeyed Blake2b with a 32-byte digest that Cardano uses for its 32-byte hashes;
Blake2b is deterministic (empty key/salt/personalization), so these digests are
implementation-independent and apply to the selected dependency. This is the
"Cardano spec / official test/golden file" acceptable-source category. Notably, the empty-input
digest `0e5751c0…` — previously rejected because it was found only in a third-party Rust repo — is
now confirmed verbatim in an official Intersect source, which resolves the earlier gap.

Sources originally searched for Blake2b-256 (recorded for history), and how the gap was closed:

- RFC 7693 Appendix A — only BLAKE2b-512 ("abc") and BLAKE2s-256; no unkeyed BLAKE2b-256.
- Official BLAKE2 KAT `github.com/BLAKE2/BLAKE2/testvectors/blake2b-kat.txt` — keyed and
  full 64-byte output only; no unkeyed truncated 256 vector.
- `IntersectMBO/cardano-base`, `cardano-crypto-class/testlib/Test/Crypto/Hash.hs` — hash tests
  are property-based (roundtrip, MemPack, `hashFromStringAsHex`/`fromString`, `expected =
  digest p bs`); no fixed known-answer vector with a concrete input and expected digest.
- `input-output-hk/cardano-crypto` — no golden/KAT located.
- `cardano-ledger` goldens — only complex constitution-hash CBOR, not a clean small
  Blake2b-256 input/digest pair.
- The frequently quoted value `0e5751c0…` (empty) was initially located only in a third-party
  Rust repo (`DaJo-Code/cardano-crypto`), which is not an official IOG/Intersect source; on its
  own it failed the gate. It is now confirmed verbatim in the official `IntersectMBO/plutus`
  conformance golden above, which is what closes the gap. Generating an "official" digest with
  another library (Apollo, Python, BouncyCastle, libsodium) is prohibited by ADR-0004 §7;
  cross-checks are secondary only.
- Gap closed by the `IntersectMBO/plutus` conformance goldens for the unkeyed `blake2b_256`
  builtin (see the table row and the validation paragraph above): official Intersect repo,
  concrete input bytes, exact 32-byte digests, pinned commit, Apache-2.0.

Consequence: with both digest sizes pinned, the 1.5b-pre gate passes and 1.5b is unblocked.
1.5b-pre itself commits no module, dependency, API, or Kotlin/Gradle change.
- Blocks 1.6 / 1.10: seed/key derivation and signing, each citing CIP-1852 / CIP-3 / BIP-39 /
  RFC 8032 vectors verbatim in the implementing block.
- ADR-0004 (`docs/DECISIONS/0004-crypto-strategy.md`) and ADR-0005
  (`docs/DECISIONS/0005-phase-1-architecture-and-scope.md`) remain the governing decisions this
  ADR aligns with; this ADR does not supersede them.

#### 8. Block 1.5b result — `:crypto` created; hashing backed by KotlinCrypto `blake2`

Block 1.5b created the `:crypto` Kotlin Multiplatform module (Android library + JVM +
iosArm64 + iosSimulatorArm64, `explicitApi()`), depending only on `:core`, and wired
Blake2b-224/256 behind a backend-neutral `Hashing` interface.

**Backend correction.** The seam design in §2 anticipated Apollo as the concrete
implementation, but wiring this block established that **Apollo 1.8.8 provides no Blake2b**
(verified in the published `apollo-jvm-1.8.8.jar`, whose `hashing` package contains only
`PBKDF2SHA512`, and across Apollo source tags `v1.7.2`–`v1.8.7`; its transitive dependencies
expose no Blake2b either). The 1.5a spike only established dependency resolution and Kotlin
compilation, and 1.5b-pre only pinned test vectors — neither had verified that Apollo exposes
a Blake2b API. Because ADR-0004 forbids handwritten cryptography, this hashing-only block is
backed by **KotlinCrypto `org.kotlincrypto.hash:blake2` `0.8.0`** (Apache-2.0; from the same
KotlinCrypto project whose `sha2`/`hmac-sha2` Apollo already depends on). Apollo is **not**
added in this block, and `bip32-ed25519` is **not** added; Apollo's Ed25519-BIP32 value is
reserved for Blocks 1.6 / 1.10. The seam held: the public API (`Hashing`, `HashDigest`,
`CryptoError`) names no backend, so a later block can still adopt Apollo for derivation
without touching this surface.

**Wiring.**

- Public API in `org.sarmidev.kardano.crypto`: `Hashing` (`blake2b224`/`blake2b256`, both
  returning `KardanoResult<HashDigest, CryptoError>`, never throwing) with `Hashing.default()`;
  `HashDigest` (regular class, private constructor, internal size-validating factory,
  defensive copies, content-based equality, structural `toString`, `SIZE_224`/`SIZE_256`
  constants); and the sealed, backend-neutral `CryptoError` (`HashingFailed`,
  `InvalidDigestLength`). The internal adapter `Blake2bHashing` maps backend failures to
  `CryptoError` and rethrows `CancellationException` before mapping other throwables.
- Dependency pinned via the version catalog (`kotlincrypto-blake2 = "0.8.0"`); no dynamic
  versions.
- Availability note: `blake2` publishes `jvm` and iOS artifacts plus artifacts expected to be
  usable by this repo's Android target; `:crypto:testAndroidHostTest` verifies Android target
  resolution/compile (no unverified "Android-native" claim is made).

**Tests.** `commonTest` uses only the pinned cited vectors from §7, copied verbatim with
source comments, and generates no expected digest: Blake2b-224 against the CIP-19 payment
credential (read structurally from the cited address via `:core` `Address.parse`), and
Blake2b-256 against the two IntersectMBO/plutus conformance goldens. `HashDigest` structural
tests (defensive copy on construction and on read, structural `toString`, content equality,
`InvalidDigestLength`) exercise the module-internal factory directly.

**Verification.** `./gradlew :crypto:jvmTest :crypto:testAndroidHostTest
:crypto:compileKotlinIosSimulatorArm64 :core:jvmTest` — all BUILD SUCCESSFUL.
