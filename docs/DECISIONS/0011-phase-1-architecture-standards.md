# ADR-0011: Phase 1 Architecture Standards And Pre-1.7 Package Cleanup

| Field    | Value                                                          |
|----------|----------------------------------------------------------------|
| Status   | **Accepted**                                                    |
| Scope    | Pre-1.7 microblock — `:crypto` package layout, Cursor-rules refresh, Block 1.7 module/ownership decision, cross-module standards for Phase 1 onward |
| Phase    | Phase 1 (between Block 1.6 and Block 1.7)                       |
| Updated  | 2026-07-12                                                      |

---

## Context

Block 1.6 (ADR-0009/ADR-0010) landed BIP-39 mnemonic restoration, Icarus/CIP-3 master-key
derivation, and Ed25519-BIP32/CIP-1852 private and public key derivation, all inside
`:crypto`. By the end of 1.6, `:crypto` had 17 production files sitting flat in a single
package, `org.sarmidev.kardano.crypto`, mixing hashing, mnemonic/BIP-39, key derivation, and
two `internal expect`/`actual` platform seams as siblings. This is the same "hard to
navigate flat root" situation [ADR-0003](0003-core-package-structure.md) fixed for `:core`
before Block 0.7 added address parsing.

Block 1.7 (Address Generation) is next. It needs both `:core`'s address/Bech32 types and
`:crypto`'s derived public keys, so before writing 1.7 code this ADR fixes: where 1.7's
code should live, whether a new Gradle module (`:wallet` or otherwise) is justified now, and
what package-organization state `:crypto` should be in first. This ADR is a reorganization
and documentation change only — no behavior change, no new dependency, no Gradle module
added.

## Decision

### 1. `:crypto` package layout

Split the flat `org.sarmidev.kardano.crypto` package into three public thematic
sub-packages plus two `internal.*` sub-packages for the platform seams, all staying inside
the single `:crypto` Gradle module (Android namespace `org.sarmidev.kardano.crypto` is
unchanged):

- `org.sarmidev.kardano.crypto.hashing` — `Hashing`, `Blake2bHashing`, `HashDigest`,
  `CryptoError`.
- `org.sarmidev.kardano.crypto.mnemonic` — `Mnemonic`, `MnemonicError`,
  `Bip39EnglishWordlist`.
- `org.sarmidev.kardano.crypto.derivation` — `KeyDerivation`, `KeyDerivationError`,
  `Bip32Ed25519KeyDerivation`, `Cip1852Path`, `IcarusMasterKey`, `ExtendedPrivateKey`,
  `ExtendedPublicKey`.
- `org.sarmidev.kardano.crypto.internal.pbkdf2` — the `pbkdf2HmacSha512` seam (`expect` +
  JVM/Android/iOS `actual`s).
- `org.sarmidev.kardano.crypto.internal.projection` — the `projectPublicKey` seam (`expect`
  + JVM/Android/iOS `actual`s).

The two seams are deliberately not placed inside the public-facing `derivation` package:
`pbkdf2HmacSha512` and `projectPublicKey` are `internal expect` implementation details, not
part of the derivation API surface. An `internal.*` segment signals "not API" to anyone
browsing the module and keeps `derivation` reading as public API only. All five
sub-packages stay in one Gradle module, so `internal`-visible members (`HashDigest.of()`,
both seam functions, every opaque type's `internal` constructor/accessor) remain callable
across sub-packages without being widened to `public` — a module split would force that
widening, the same reasoning ADR-0003 §Rationale recorded for `:core`.

Out of scope for this cleanup: the verbatim iOS per-target file duplication
(`iosArm64Main`/`iosSimulatorArm64Main`) and the identical JVM/Android BouncyCastle PBKDF2
files. These are pre-existing KMP source-set duplication, not a navigability problem this
ADR addresses; deduping them (for example via `kotlin.mpp.enableCInteropCommonization`) is
separate, higher-risk follow-up work.

### 2. Block 1.7 (Address Generation): no new module; ownership split by dependency direction

Block 1.7 builds payment/stake credentials from a derived key, generates a testnet base
address, encodes it to Bech32, and round-trips through `Address.parse`. This ADR fixes the
ownership split before any 1.7 code is written:

- **`:core` owns address assembly and encoding.** Given already-computed 28-byte credential
  hashes and a `Network`, `:core` assembles the `Address` and encodes it to Bech32. This is
  the bulk of 1.7 and where the still-needed address-encoding/roundtrip ADR (recorded as a
  1.7 prerequisite in ADR-0005 §6) applies. It lands in `org.sarmidev.kardano.address` and
  keeps that package dependency-free.
  - **The current `Address`/`AddressCredential` types must not be assumed reusable as-is
    for generation.** They were built for parsing (`Address.parse`); their constructors and
    factories are parse-oriented and may be `internal`. Block 1.7 must design the minimal
    public factory/encoding API `:core` needs — for example a public credential factory
    from raw key/script hash bytes, a base-address builder from
    `(Network, paymentCredential, stakeCredential)`, and `Address.toBech32()` — rather than
    assuming an existing entry point is already suitable.
- **`:crypto` may own a tiny public-key-to-credential-hash helper, only if needed.** The one
  crypto-dependent step is `ExtendedPublicKey.publicKeyBytes()` piped through
  `Hashing.blake2b224` to a 28-byte credential hash. If an ergonomic single call is useful,
  it can live in `:crypto` (which already depends on `:core`); otherwise the 1.7 caller
  composes the two existing calls directly. Scoped narrowly to hashing-to-a-credential-hash
  only — address assembly itself stays in `:core`.
- **`:shared` owns no SDK logic for 1.7.** The playground may call the new `:core`/`:crypto`
  APIs to display a generated `addr_test`, matching the Block 1.7 Android checkpoint, but
  must not host address-generation logic itself.
- **No `:wallet` module at 1.7.** ADR-0009 §1 recorded the extraction trigger precisely:
  "the first block that composes derivation with non-crypto concerns — account/address
  orchestration, wallet state, or persistence." Address generation, as scoped above, is a
  pure function over already-derived key material — not orchestration or state. The trigger
  fires at **Block 1.8 (Wallet State Read-Only)**, which is the first block that holds
  wallet state and composes it with a provider query; `:wallet` extraction is re-evaluated
  there, not before.

### 3. `:shared` fixture rule

- **General rule.** Reusable protocol/crypto test fixtures and vectors do not belong in
  `:shared`'s production `commonMain`; they belong in the owning SDK module's test source
  sets.
- **Exception.** A sample-only UI checkpoint fixture may live in `:shared commonMain` when
  the UI must render it at runtime, provided it is `internal`, carries a source citation, is
  clearly labeled test-only, and never exposes real funds, mnemonics, or private keys — only
  public, cited vectors and public derived metadata.
- `TestWalletFixture` (the 1.6d Playground checkpoint fixture) fits the exception: the
  Playground UI renders it directly, it is cited (`IntersectMBO/cardano-addresses` golden),
  and it carries no real key material. It is **not** relocated by this ADR — no concrete
  better home exists that the UI could still render from directly. If a future block
  introduces a shared test-fixtures source set the UI can consume across modules, revisit
  then.
- `PlaygroundPresenter` continues to format and orchestrate SDK calls for display without
  reimplementing protocol logic; this ADR records that as the standing rule for `:shared`
  presenters generally, not just for the current file.

### 4. Cross-module standards for Phase 1 onward

- **Packages before modules.** Extract a Gradle module only under real dependency-direction
  or ownership/visibility pressure (ADR-0002/0003/0005). Sub-packages preserve `internal`
  seams across a module's own boundaries; a module split does not.
- **Internal platform seams live under an `internal.*` sub-package**, not inside a
  public-facing API package (§1 above sets the precedent for future seams).
- Root group stays `org.sarmidev.kardano`; SDK modules stay UI-free with `explicitApi()`.
- Preserve typed errors / `KardanoResult` (no throwing across the Swift/ObjC boundary),
  defensive `ByteArray` rules (`contentEquals`/`contentHashCode`, copy on construction and on
  every accessor), and test-vector integrity (vectors copied verbatim from cited specs,
  never generated).
- No Clean Architecture boilerplate (`Repository`, `UseCase`, `Flow`) unless it removes real
  complexity — this SDK's modules are small enough that an interface plus a default adapter
  (the existing `Hashing`/`KeyDerivation`/`ChainQueryProvider` pattern) is the standing
  convention, not a layered architecture.
- No compatibility typealiases when a type moves between packages. This SDK is pre-alpha
  with no external consumers; record the import change in the change's own docs instead of
  papering over it (same posture ADR-0003 §Consequences recorded).
- A reorganization block changes packages/imports only, never behavior; any `expect`/
  `actual` seam moves with every one of its source sets in the same diff.

### 5. Cursor-rules refresh

`.cursor/rules/kardano-sdk-guardrails.mdc` and `.cursor/rules/kotlin-tests-and-docs.mdc` are
updated in this same change (rules-only, no behavior change):

- `kardano-sdk-guardrails.mdc`'s "Phase 0 scope" section said "Crypto is `expect`/strategy docs
  only," which Block 1.6 made false. It is reworded to describe Phase 0 (complete) and
  Phase 1 (in progress: `:crypto` and the `:provider`/`:provider-blockfrost` read path are
  real, backend-delegated code), and gains the packages-before-modules and `internal.*` seam
  conventions from §4 plus a pointer to this ADR.
- `kotlin-tests-and-docs.mdc`'s test-vector list gains the three crypto vector families now
  in use (BIP-39, CIP-3/Icarus, Ed25519-BIP32/CIP-1852 goldens) and a new section on
  Android/iOS runtime testing for native-backed crypto (what `jvmTest`, `androidHostTest`,
  `androidDeviceTest`, and iOS compile/link each actually prove).

## Rationale

- The `:crypto` split follows the exact precedent ADR-0003 already set and validated for
  `:core`: reorganize packages before the next block adds more code, so the new code lands
  in the right place instead of a flat root that later needs untangling.
- Deciding the 1.7 ownership split now, before any 1.7 implementation, avoids the mistake of
  assuming `:core`'s parse-oriented `Address`/`AddressCredential` API is generation-ready
  and prevents `:crypto` from silently growing address-shaped responsibilities.
- Declaring the `:wallet` non-decision explicitly (again) keeps the ADR-0009 §1 trigger
  intact and stops 1.7 from re-litigating a question ADR-0009 already answered.
- The Cursor rules are part of what every future change reads first; leaving a stale
  "crypto is docs-only" line in an `alwaysApply: true` rule after Block 1.6 shipped real
  crypto code is a standing correctness bug in the rule itself.

## Rejected alternatives

- **Create `:wallet` now, at 1.7.** Rejected: address generation is a pure function over
  already-derived key material, not the orchestration/state ADR-0009 §1 named as the
  trigger; creating the module now would produce a near-empty module the way ADR-0003
  rejected for `:core` splits during Phase 0.
- **Put the public-key-to-credential-hash helper's logic in `:core`.** Rejected: `:core` is
  dependency-free by design (ADR-0003/ADR-0005); adding a `:crypto`-shaped hashing helper
  there would introduce a dependency `:core` does not need. The helper, if built at all,
  belongs in `:crypto`, which already depends on `:core`.
- **Relocate `TestWalletFixture` out of `:shared` in this change.** Rejected: no concrete
  better home exists yet that the Playground UI could still render from directly; moving it
  without a real destination would be motion without improvement. The general/exception
  fixture rule (§3) is recorded instead, and relocation is revisited if a shared
  test-fixtures source set is introduced later.
- **Defer the Cursor-rules refresh to a separate microblock.** Rejected: the user requested
  it be included now, and the stale "crypto is docs-only" line is a correctness bug in an
  always-applied rule that should not persist through another block.

## Consequences

- `:crypto` compiles, tests, and links exactly as before on every target
  (`:crypto:compileKotlinJvm`, `:crypto:jvmTest`, `:crypto:testAndroidHostTest`,
  `:crypto:compileKotlinIosSimulatorArm64`, `:crypto:linkDebugTestIosSimulatorArm64`); only
  packages and imports changed. Fully qualified names change for every moved type (for
  example `org.sarmidev.kardano.crypto.Mnemonic` becomes
  `org.sarmidev.kardano.crypto.mnemonic.Mnemonic`); this is a public package-move / import
  change, acceptable and recorded explicitly because this SDK is pre-alpha with no external
  consumers (same posture as ADR-0003 §Consequences).
  `:shared`'s `PlaygroundPresenter`, `TestWalletFixture`, and playground tests update their
  imports in the same change.
- Block 1.7 has a written ownership split to implement against: `:core` for address
  assembly/encoding (including designing the minimal public factory/encoding API), an
  optional narrow `:crypto` helper for the credential-hash step, no `:wallet` module, and no
  SDK logic in `:shared`.
- The two Cursor rules no longer describe crypto as docs-only or Phase-0-scoped, and gain
  the crypto vector-source and Android/iOS runtime-testing guidance Block 1.6 already
  established in practice but had not recorded as a rule.

## Follow-up work

- Block 1.7 implements the address-generation split recorded in §2, starting with the
  address-encoding/roundtrip ADR that ADR-0005 §6 already flags as a prerequisite.
- Block 1.8 re-evaluates `:wallet` extraction against the ADR-0009 §1 trigger, now that
  wallet state/orchestration is in scope.
- The iOS per-target file duplication and JVM/Android PBKDF2 file duplication noted in §1
  remain candidates for a future, separate dedup pass (for example evaluating
  `kotlin.mpp.enableCInteropCommonization`); not addressed here.
- If a shared test-fixtures source set is introduced for `:shared` and its sample apps,
  revisit whether `TestWalletFixture` should move into it (§3).
