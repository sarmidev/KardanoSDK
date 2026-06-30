# ADR-0004: Cryptography Strategy

| Field   | Value                               |
|---------|-------------------------------------|
| Status  | **Accepted**                        |
| Scope   | Future cryptography strategy        |
| Phase   | Phase 0 (Block 0.8)                 |
| Updated | 2026-06-30                          |

---

## Context

Phase 0 closes with structural encoding and address parsing only. No cryptographic
primitives are implemented: no signing, no key derivation, no hashing beyond the BCH
polymod inside the Bech32 codec (which is checksum arithmetic, not a cryptographic
primitive).

A future Cardano SDK will require several cryptographic algorithm areas before wallet
creation, address generation, or transaction signing can be supported. Documenting the
strategy — library selection policy, module boundaries, seam design, key-material
lifecycle, error policy, and test-vector sourcing — now means that when the first
crypto-capable block opens, the framework for making and recording those decisions already
exists.

This ADR follows the same pre-implementation pattern as ADR-0001, which fixed the CBOR
and Bech32 policies before Blocks 0.5 and 0.6.

### Hard constraint

The project rule is absolute: **no handwritten cryptographic algorithms**. All
cryptographic primitives are delegated to externally maintained libraries or platform
bindings. The selection of a specific library or binding for a specific algorithm happens
in the implementation block that introduces that algorithm, gates on a documented
evaluation, and updates the candidate matrix in this ADR from `Needs investigation` to
`Accepted` or `Rejected`.

---

## Decision

The following policies are **Accepted** now, before any crypto code lands.

### 1. No handwritten cryptographic algorithms

No implementation of cryptographic primitives in Kotlin source. No direct translation of
RFC pseudocode into production code. Every algorithm must be delegated to an externally
maintained library or platform binding selected through documented evaluation.

### 2. Library/binding selection policy

Selection happens per algorithm, per implementation block:

- A future block that needs algorithm X opens its own evaluation — updating the candidate
  matrix below with verified facts.
- The evaluation results in an explicit `Accepted` or `Rejected` decision recorded in
  this ADR (or a follow-up ADR).
- No library or binding is considered selected until a matrix entry records `Accepted`.

Until then every candidate in this ADR's matrix is `Needs investigation`.

Do not describe candidates as having been "reviewed", "vetted", or "peer-reviewed" unless
that status is established by the evaluation of that future block.

### 3. Module boundary

Crypto must not land inside the dependency-free structural `:core` module. The settled
package seams (`primitives`, `encoding.*`, `address`) introduced in ADR-0003 are intended
to stay free of crypto dependencies.

The **likely** end state is a dedicated Gradle module (candidate name `:crypto`, not
final), consistent with the deferred module candidates listed in ADR-0002. However,
this module boundary is not fixed today. A crypto algorithm may first land as an isolated
package inside an existing module and be extracted into a separate module when code and
dependency pressure justify the split — consistent with ADR-0002's "extract only when
justified" rule.

### 4. Seam design

Two patterns are acceptable; the choice is made per algorithm during evaluation:

- **Platform seam (`expect`/`actual`):** a `commonMain` `expect` declaration with
  platform-specific `actual` bodies wrapping distinct per-platform libraries (for
  example, a JVM/Android actual and an iOS/native actual). Use this when no single
  library supports all required KMP targets.
- **Common interface / strategy seam:** a `commonMain` interface or object backed by
  a KMP-capable library whose own `commonMain` API covers all required targets. Use this
  when a single library covers all targets without requiring per-platform `actual` bodies.

Neither pattern is mandated in advance. The evaluation for each algorithm determines
which fits.

### 5. Key-material lifecycle

- Never expose a mutable internal `ByteArray` for key data.
- Defensive copy on every input and every output accessor.
- Prefer opaque key handles over exposing raw key bytes at public API boundaries.
- Prefer `ByteArray` over `String` for any secret material that must be held in memory.
- Provide explicit clearing (`clear()`/`close()`) where possible. This must be documented
  as **best-effort memory clearing, with no guarantee about compiler, runtime, or GC
  behavior** — particularly on the JVM, where GC copying, memory relocation, and `String`
  immutability mean a zeroed backing array may not be the only copy in memory. On native
  targets, overwriting a backing buffer is more direct, but no guarantee is asserted.
  No claim is made about complete memory erasure or runtime-level secrecy.

### 6. Error policy

All failable crypto APIs must return `KardanoResult<T, E>` with a typed sealed error.
No throwing across the Swift/ObjC boundary: that crashes the iOS app. Any exception that
cannot be avoided (for example, a wrapped platform API that is declared as throwing) must
be caught internally and mapped to a typed error; if it must propagate, it requires
`@Throws` and KDoc explaining why.

### 7. Test-vector policy

- Official, externally sourced vectors only, copied verbatim with the source cited.
- No AI-generated vectors for any cryptographic algorithm.
- No vectors are added in this block (strategy only). Vectors land with the implementation.
- Authoritative sources by algorithm area:

| Algorithm area                  | Source                                            |
|---------------------------------|---------------------------------------------------|
| Ed25519 signing                 | RFC 8032 test vectors                             |
| Ed25519-BIP32 (Cardano)         | CIP-1852 / IOHK reference implementation vectors |
| BIP-32 hierarchical derivation  | BIP-32 test vectors                               |
| BIP-39 mnemonics                | BIP-39 wordlist and test vectors                  |
| CIP-3 / Icarus entropy          | CIP-3 reference test vectors                      |
| PBKDF2-HMAC-SHA-512 (seeding)   | RFC 8018 / BIP-39 seed test vectors               |
| HMAC-SHA-512 (derivation)       | RFC 2104 + BIP-32 derivation vectors              |
| SHA-256 / SHA-512               | FIPS 180-4 test vectors                           |
| Blake2b-224 / Blake2b-256       | RFC 7693 test vectors                             |
| Randomness                      | No external vectors — platform CSPRNG; tested by  |
|                                 | statistical properties and platform documentation |

Reuse the fixture layout and citation discipline from `docs/TESTING.md`.

### 8. No transaction signing in Phase 0

No transaction signing, no wallet creation, no real private key or mnemonic handling.
These are Phase 1+ capabilities. This block establishes strategy only.

---

## Future algorithm scope

The following algorithm areas are **in scope for future implementation blocks**, not for
this block. They are listed so future blocks have a common checklist.

### In scope (future)

| Algorithm area              | Cardano relevance                                             |
|-----------------------------|---------------------------------------------------------------|
| Ed25519                     | Standard signature scheme (RFC 8032)                         |
| Ed25519-BIP32               | Cardano's extended-key variant (64-byte private key + chain  |
|                             | code); distinct from standard Ed25519                        |
| BIP32-style derivation      | Hierarchical key derivation from a root key                  |
| CIP-1852 paths              | Cardano account/role/index derivation paths                  |
| BIP-39 / CIP-3              | Mnemonic generation and entropy / Icarus seed handling       |
| PBKDF2-HMAC-SHA-512         | Seed derivation from mnemonic (BIP-39)                       |
| HMAC-SHA-512                | Child key derivation step (BIP-32)                           |
| SHA-256 / SHA-512           | General hashing (FIPS 180-4)                                 |
| Blake2b-224                 | 28-byte key and credential hashes (RFC 7693)                 |
| Blake2b-256                 | 32-byte transaction, datum, and script hashes (RFC 7693)     |
| Platform randomness (CSPRNG)| Entropy for key generation; platform-provided only           |
| Key-material lifecycle      | Handles, copies, best-effort clearing                        |

### Explicitly out of scope (not wallet-SDK work)

| Algorithm area             | Reason                                               |
|----------------------------|------------------------------------------------------|
| VRF / KES                  | Node / consensus layer; not wallet or SDK work       |
| Keccak-256 / SHA3-256      | Plutus builtin hashes; a future Plutus phase, not    |
|                            | the wallet/tx SDK scope                              |

---

## Target support matrix

All crypto implementations must support:

| Target                   | Required | Notes                                  |
|--------------------------|----------|----------------------------------------|
| Android (arm64, x86_64)  | Yes      | Primary mobile target                  |
| iOS (iosArm64)           | Yes      | Primary mobile target                  |
| iOS simulator            | Yes      | Required for CI test compilation       |
| JVM / Desktop            | Yes      | Fast testing, tooling, demos           |
| Web / Wasm               | No       | Not a Phase 0 priority                 |

A candidate library or binding must cover all required targets, or a target-combination
approach must be documented and evaluated (e.g. a platform seam with JVM and iOS actuals).

---

## Platform-specific concerns

### Randomness / entropy

Each platform supplies its own cryptographic random number generator. The SDK must use
the platform-provided system CSPRNG — the JVM/Android system random provider and Apple's
platform RNG API on iOS. The SDK must not implement its own RNG. The exact API name used
per platform is recorded in the implementation block that introduces key generation.

### Memory clearing limitations

On JVM/Android: `String` objects are immutable; GC copying, relocation, and JIT
compilation mean that zeroing one `ByteArray` does not guarantee that no other copy of
the key bytes exists in memory. Best-effort clearing is documented as such. No
"memory-clearing guarantee" is claimed.

On iOS/native: overwriting a backing buffer is more direct, but still not a formal
guarantee. Document as best-effort.

### iOS / Swift interop

No throwing across the Swift/ObjC boundary. All failable crypto APIs use `KardanoResult`.
Prefer opaque handles over raw `ByteArray` at the public API boundary. Be mindful that
`ByteArray` passed across the KMP boundary is copied by the framework.

### Android / JVM provider variance

The JVM's JCA algorithm availability varies by provider and by API level. Notably,
Blake2b is not part of the standard JCA algorithm suite; its availability depends on the
provider explicitly added. The implementation block that introduces Blake2b must document
and pin the provider used.

---

## Candidate evaluation matrix

Each entry represents a candidate library or binding category. All fields are
`Unverified` until explicitly checked during the relevant implementation block. Every
`Decision status` is `Needs investigation` until an implementation block records a
verified conclusion.

The matrix is structured by **candidate category**. Concrete library names within each
category are examples only — not selections.

---

### Category A: JVM / Android JCA-style provider

**Description:** A library that integrates with or wraps the JVM's JCA (Java Cryptography
Architecture), usable on Android and JVM targets. Not available natively on iOS — a
platform seam would be required.

| Field                      | Value              |
|----------------------------|--------------------|
| Example names              | BouncyCastle, Tink (partial JCA), platform JCA builtins |
| Supported algorithms       | Unverified per example |
| KMP target: Android        | Likely (JVM-based) |
| KMP target: JVM            | Likely             |
| KMP target: iosArm64       | No — JCA not available on iOS |
| KMP target: commonMain API | No — requires platform seam |
| Maintenance status         | Unverified per example |
| License compatibility      | Unverified per example |
| iOS / native story         | Not applicable — JVM/Android only; requires iOS actual |
| Test-vector availability   | Unverified per example |
| Risks / unknowns           | Android API level restrictions for some algorithms; Blake2b absence from standard JCA; BouncyCastle on Android requires explicit provider registration |
| Decision status            | **Needs investigation** |

---

### Category B: C library via Kotlin/Native cinterop (iOS / native)

**Description:** A C library (for example a libsodium-family library or similar) accessed
on iOS via Kotlin/Native cinterop. Not available on JVM/Android without a separate JNI
layer — a platform seam would be required.

| Field                      | Value              |
|----------------------------|--------------------|
| Example names              | libsodium family, other ANSI C crypto libraries |
| Supported algorithms       | Unverified per example |
| KMP target: Android        | Not via cinterop — requires JNI binding separately |
| KMP target: JVM            | Not via cinterop — requires JNI binding separately |
| KMP target: iosArm64       | Likely (Kotlin/Native cinterop) |
| KMP target: commonMain API | No — cinterop is per-target; requires platform seam |
| Maintenance status         | Unverified per example |
| License compatibility      | Unverified per example |
| iOS / native story         | Direct cinterop; binary distribution requires framework packaging |
| Test-vector availability   | Unverified per example |
| Risks / unknowns           | Build complexity for iOS framework; cinterop header generation; binary size; linking strategy for simulator vs. device |
| Decision status            | **Needs investigation** |

---

### Category C: Pure-Kotlin / KMP-native crypto provider

**Description:** A library written in Kotlin Multiplatform that exposes a `commonMain`
API covering all required targets without requiring per-target `actual` bodies at the
call site. Would be the simplest seam if a suitable one covering the required algorithm
set exists.

| Field                      | Value              |
|----------------------------|--------------------|
| Example names              | cryptography-kotlin, kotlinx-crypto (if exists), other pure-KMP crypto libraries |
| Supported algorithms       | Unverified per example |
| KMP target: Android        | Unverified per example |
| KMP target: JVM            | Unverified per example |
| KMP target: iosArm64       | Unverified per example |
| KMP target: commonMain API | Unverified per example |
| Maintenance status         | Unverified per example |
| License compatibility      | Unverified per example |
| iOS / native story         | Unverified — may use cinterop internally |
| Test-vector availability   | Unverified per example |
| Risks / unknowns           | Pure-Kotlin crypto implementations require independent review; performance on constrained targets is unverified; algorithm coverage may not include Ed25519-BIP32 or Blake2b |
| Decision status            | **Needs investigation** |

---

### Category D: Cardano-specific binding or port

**Description:** A library or binding that specifically targets Cardano cryptography
(Ed25519-BIP32, CIP-1852 derivation, Blake2b in the Cardano context), possibly a Kotlin
port of the Cardano Haskell library or a binding to a Rust crate.

| Field                      | Value              |
|----------------------------|--------------------|
| Example names              | cardano-crypto (Haskell-derived ports), cardano-multiplatform-lib bindings, Rust crate bindings |
| Supported algorithms       | Unverified per example |
| KMP target: Android        | Unverified per example |
| KMP target: JVM            | Unverified per example |
| KMP target: iosArm64       | Unverified per example |
| KMP target: commonMain API | Unverified per example |
| Maintenance status         | Unverified per example |
| License compatibility      | Unverified per example |
| iOS / native story         | Unverified — may require xcframework packaging |
| Test-vector availability   | Cardano-specific vectors may be available from IOHK / Intersect repositories |
| Risks / unknowns           | Maintenance alignment with Cardano protocol upgrades; binary distribution; FFI boundary risk |
| Decision status            | **Needs investigation** |

---

### Evaluation template (for future blocks)

When a future implementation block evaluates a specific candidate, copy this template
and fill in verified values:

```
Candidate name:
Category:

| Field                      | Value |
|----------------------------|-------|
| Supported algorithms       |       |
| KMP target: Android        |       |
| KMP target: JVM            |       |
| KMP target: iosArm64       |       |
| KMP target: iosSimulatorArm64 |    |
| KMP target: commonMain API |       |
| Maintenance status         | (last release, issue tracker health) |
| License compatibility      | (SPDX identifier, compatibility with SDK license) |
| iOS / native story         |       |
| Test-vector availability   |       |
| Risks / unknowns           |       |
| Seam pattern               | (expect/actual | common interface | other) |
| Decision status            | Accepted / Rejected / Needs investigation |
| Rationale                  |       |
```

---

## Non-goals

- No cryptographic implementation of any kind in this block.
- No Gradle dependency additions.
- No key generation, mnemonic generation, or seed derivation.
- No transaction signing.
- No wallet behavior.
- No real private keys, mnemonics, or addresses holding real funds — anywhere.
- No claim of readiness, external review, or audit status.

---

## Open questions

The following items are unresolved and must be answered in the relevant future
implementation blocks:

1. Which library or binding for Ed25519-BIP32 key derivation on each target (Android,
   iOS, JVM)? Pure-Kotlin, cinterop, or JCA-backed?
2. Which library or binding for Blake2b-224 and Blake2b-256 on each target? Blake2b is
   absent from standard JCA; what provider approach is used on Android vs. JVM?
3. Which specific iOS platform API is used for randomness, and what is the fallback
   strategy for testing on iOS simulator without a device CSPRNG?
4. What is the `:crypto` module timing? Does crypto first land as a package inside an
   existing module or directly in a new module?
5. Does any single KMP-capable library cover all required algorithm areas (Ed25519-BIP32,
   Blake2b, BIP-39, PBKDF2) with sufficient target coverage, or must the implementation
   use multiple libraries and a platform seam?
6. What is the correct BIP-32 / CIP-1852 derivation path root for Cardano (account role,
   coin type), and which reference test vectors confirm it?
7. How is the test for Ed25519-BIP32 structured when the algorithm diverges from standard
   Ed25519? Which reference implementation provides the canonical test vectors?

---

## Consequences

- This ADR's candidate matrix is the tracking artifact for future library selection.
  Each future crypto block updates the matrix from `Needs investigation` to `Accepted` or
  `Rejected` for the specific algorithm and candidate.
- No crypto implementation lands before a candidate evaluation updates this matrix with
  verified facts and records a decision.
- This ADR is part of the project's decision record and is referenced from
  `docs/AI_WORKING_AGREEMENT.md` and `docs/SECURITY.md`. Do not delete it.

---

## Follow-up work

- Future crypto implementation blocks (Phase 1+):
  - Ed25519-BIP32 / CIP-1852 key derivation block.
  - BIP-39 / CIP-3 mnemonic block.
  - Blake2b-224 / Blake2b-256 hashing block.
  - Platform randomness / entropy block.
- Each block opens its own documented evaluation using the template above.
- ADR-0001 (`docs/DECISIONS/0001-cbor-and-parser-policy.md`) established the parser
  decision pattern; this ADR follows it for cryptography.
