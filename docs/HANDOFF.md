# Kardano SDK - Handoff

## Purpose

This file exists so the project can be resumed by the owner, Cursor, ChatGPT or another AI assistant without relying on chat history.

Update it at the end of each work session.

## Current Project Context

Kardano SDK is an open-source Kotlin Multiplatform SDK for native Cardano mobile apps.

Current project identity:

- Name: Kardano SDK.
- Package/group: `org.sarmidev.kardano`.
- Main targets: Android, iOS, JVM/Desktop.
- Current status: **Phase 0 (Core Foundation) is complete** (Blocks 0.1 through 0.9).
  **Phase 1 Block 1.1 (Scope And Architecture Plan) is also complete** — a
  planning/documentation block with no wallet, crypto, provider, tx, or Android UI code, no
  Gradle or dependency changes. The next step is **Block 1.2 (Android SDK Playground)**, the
  first Phase 1 implementation block. Block-by-block detail follows. Blocks 0.1 (Project Governance And AI Rules),
  0.2 (SDK-Oriented Module Structure), and 0.3 (Testing Infrastructure) are complete: a
  UI-free `:core` module exists, `:shared` depends on it, and the testing foundation
  (test source-set strategy, fixture layout, test-vector policy in `docs/TESTING.md`) is
  in place. Block 0.4 (Core Primitives) is complete: `KardanoResult`, `Network`,
  `Lovelace`, and the byte-backed primitives (`TxHash`, `PolicyId`, `AssetName`, `UtxoRef`)
  and their tests have landed in `:core`. ADR-0001 (CBOR/parser policy) is now Accepted
  (constrained internal Bech32/Bech32m and CBOR subset; no external dependency). Block 0.5
  (Encoding Utilities) is complete: a generic, bounded `Hex` codec, a generic, bounded
  Bech32/Bech32m codec, and the Cardano HRP allowlist wrappers (`CardanoBech32` /
  `CardanoHrp` / `CardanoBech32Error`) have landed in `:core`. Block 0.6 (CBOR subset) is
  complete: the definite-length subset (`Cbor` / `CborValue` / `CborError`) covers the
  primitives plus definite-length arrays and maps, with named nesting/element limits and the
  Phase 0 deterministic map-ordering rule. Block 0.6.5 (Core Package Organization) then
  reorganized `:core` into `org.sarmidev.kardano.primitives` and
  `org.sarmidev.kardano.encoding.{hex,bech32,cbor}` packages (architecture-only; no behavior
  change, no new Gradle modules; `KardanoResult` and `Platform` stay at the root package).
  Block 0.7 (Address Parsing And Structural Validation) is complete: it covers structural
  CIP-19 parsing of the Shelley Bech32 address families — base (header types 0-3), pointer
  (4-5), enterprise (6-7), and reward/stake (14-15) — across mainnet and testnet, decode-only,
  via `Address.parse`. Step 1 added the `org.sarmidev.kardano.address` package (`Address`,
  `AddressType`, `AddressCredential` / `CredentialKind`, `AddressError`) for the
  single-credential types; Step 2 added the two-credential base types and the explicit nullable
  `paymentCredential` / `stakeCredential` properties; Step 3 added the pointer types
  (`AddressType.POINTER`): a payment credential plus a variable-length chain pointer
  (`AddressPointer` with `slot` / `transactionIndex` / `certificateIndex`, plus `PointerField`),
  exposed via a new nullable `Address.pointer` property and bounded variable-length-integer
  decoding. Byron/Base58 addresses and raw-byte/hex `Address` constructors are deferred beyond
  Block 0.7 (see `docs/ROADMAP.md`).

Business goal:

> Build the first credible mobile-first KMP SDK for Cardano apps, focused on shared Android/iOS Cardano logic.

Technical goal for Phase 0:

> Create a tested, documented foundation before implementing wallet creation, transaction signing or real network flows.

## Important Files

Read these first:

- `docs/PROJECT_BRIEF.md`
- `docs/ROADMAP.md`
- `docs/AI_WORKING_AGREEMENT.md`
- `docs/SECURITY.md`
- `docs/DECISIONS/0001-cbor-and-parser-policy.md` or equivalent ADR path
- Cursor rule files, usually under `.cursor/rules/`

If paths differ, locate files by name.

## Current Phase

Current phase:

- Phase 1 - MVP Transaction Flow (Blocks 1.1, 1.2, 1.3, 1.4, 1.5a, 1.5b-pre, 1.5b, and
  1.6a complete; **1.6b complete on JVM/Android with executed vectors; iOS compile targets
  pass, iOS runtime vector execution still future work**; **1.6c is now fully verified on
  every target: private derivation and public-key projection (`ExtendedPrivateKey`/
  `ExtendedPublicKey`/`KeyDerivation.derivePrivate`/`KeyDerivation.publicKey`) both work on
  JVM, real Android runtime, and iOS compile/link (resolved across the 1.6c-follow-up and
  1.6c-follow-up-2 sessions, ADR-0010, after 1.6c's own gate had found Android derivation
  blocked and no public-key primitive available at all)**; **1.6d (test-wallet fixture +
  Android Playground checkpoint) is now delivered** on top of that — `:shared` gained a
  `:crypto` dependency and a "Test Wallet (derivation)" Playground section showing only the
  CIP-1852 path and Blake2b-224 fingerprint of a restored test-only mnemonic — see below).
  Block 1.5b created
  the `:crypto` KMP module and wired Blake2b-224/256 behind the backend-neutral `Hashing`
  interface. It found that Apollo 1.8.8 ships no Blake2b (verified in `apollo-jvm-1.8.8.jar`
  and source tags `v1.7.2`–`v1.8.7`), so the hashing-only backend is KotlinCrypto
  `org.kotlincrypto.hash:blake2` `0.8.0`; Apollo and `bip32-ed25519` were not added this block
  and are reserved for 1.6 / 1.10 (ADR-0008 §8). The 1.5b-pre vector gate passed for both
  digest sizes: Blake2b-224 pinned to CIP-19 and Blake2b-256 pinned to the IntersectMBO Plutus
  `blake2b_256` conformance goldens (`IntersectMBO/plutus` @`5e18824e`, Apache-2.0; ADR-0008
  §7). Block 1.6 (mnemonic / seed / key derivation) is split into 1.6a–1.6d with blocking
  gates (ADR-0009). Block 1.6a (docs-only decision block) is complete: Icarus/CIP-3
  restoration path only (restore-only; generation/CSPRNG deferred; Byron/Ledger/Trezor
  deferred); the main Apollo artifact does not enter 1.6 (published-artifact inspection: its
  mnemonic API has no checksum validation and its PBKDF2 takes a String salt while Icarus
  needs entropy-bytes salt); 1.6c uses `dev.allain:bip32-ed25519:2.3.0`; the vector gate passed
  for all three families (Trezor `vectors.json`, CIP-3 `Icarus.md`,
  `IntersectMBO/cardano-addresses` goldens — all pinned by URL + commit + license in ADR-0009
  §4). **Block 1.6b implemented `Mnemonic.parse` and `IcarusMasterKey.fromMnemonic` in
  `:crypto`.** Closing its `To verify in 1.6b` gate found that cryptography-kotlin's PBKDF2
  fails on Android (JDK provider needs JCA `PBKDF2WithHmacSHA512`, API 26+, vs `minSdk = 24`;
  `testAndroidHostTest` can't catch this — it runs on the host JVM), so 1.6b adopted the
  ADR-0009 §3 platform-seam fallback instead: BouncyCastle on JVM/Android, Apple CommonCrypto
  on iOS; no hand-written PBKDF2. Tests pass the cited Trezor/CIP-3 vectors on
  `:crypto:jvmTest` and `:crypto:testAndroidHostTest`. **iOS compile targets pass**: an inline
  C interop shim in `pbkdf2raw.def` (`kardano_ccpbkdf2_hmac_sha512`) adapts
  `CCKeyDerivationPBKDF`'s password to a raw byte pointer and delegates the derivation to it
  verbatim; `:crypto:compileKotlinIosSimulatorArm64` and `:crypto:compileKotlinIosArm64` both
  succeed. **iOS runtime execution of the vectors is still future verification** — no
  iOS-simulator/device test run has exercised this binding (see ADR-0009's Block 1.6b gate
  result and `crypto/README.md` "iOS PBKDF2 cinterop"). A BIP-39 English wordlist transcription
  error was also
  found and fixed during review (regenerated against a fresh download of the pinned source
  commit; the difference from the erroneous file is not reproduced here — see the ADR/plan
  for the fix description). **Block 1.6c (Ed25519-BIP32 + CIP-1852 derivation)'s original gate
  narrowed it to private derivation only, with Android derivation blocked** (ADR-0009); **two
  follow-up gates (ADR-0010) then closed both that blocker and public-key projection on every
  target, including Android.** ADR-0010's method both times: an Android emulator/device was
  actually provisioned or connected (rather than accepting an artifact-only verdict), and each
  candidate backend was run against it before any production code changed. Results: (1)
  swapped the derivation backend's coordinate to
  `org.hyperledger.identus:bip32-ed25519:1.8.8` (identical wrapper API to the prior
  `dev.allain:bip32-ed25519:2.3.0`; this AAR ships the native `.so` the republish omitted) and
  **verified `KeyDerivation.derivePrivate` on real Android runtime**
  (`:crypto:connectedAndroidDeviceTest`); (2) added `ExtendedPublicKey`/
  `KeyDerivation.publicKey(key)`, backed by libsodium's
  `crypto_scalarmult_ed25519_base_noclamp`, verified byte-for-byte against the cited
  `addr_xvk` goldens on JVM — the first follow-up found this specific backend's published
  Android native build was missing the needed symbol (confirmed by static symbol inspection),
  so a second follow-up (1.6c-follow-up-2) swapped in `com.goterl:lazysodium-android:5.2.0`
  for the Android actual only (JVM/iOS keep the original backend) and **verified
  `KeyDerivation.publicKey` on real Android runtime across API 24, 35, and 36**
  (`:crypto:connectedAndroidDeviceTest`), reproducing the same `addr_xvk` goldens plus a
  cross-check against the CIP-19 payment credential pinned in 1.5b. `Cip1852Path`/
  `Cip1852Role`, `ExtendedPrivateKey`, `ExtendedPublicKey`, and both `KeyDerivation` methods
  are implemented and pass the cited `IntersectMBO/cardano-addresses` golden vectors on JVM
  and on real Android runtime, for both derivation and projection. iOS **compiles and links**
  for both; iOS runtime execution of the vectors remains future work (same posture as 1.6b).
  **1.6d (test-wallet fixture + Android Playground checkpoint) is delivered on top of this:**
  `:shared` gained a project dependency on `:crypto` and a "Test Wallet (derivation)"
  Playground section (`TestWalletFixture`, `PlaygroundPresenter.presentTestWallet()`,
  `WalletResultCard`) restoring the same cited test-only mnemonic, deriving
  `m/1852'/1815'/0'/0/0`, and showing only the path, the Blake2b-224 fingerprint, whether it
  matches the cited golden, and typed state — never the mnemonic, seed, or any raw key bytes.
  Phase 0 - Core Foundation closed below for reference.

Block status:

- Block 0.1 Project Governance And AI Rules: complete (all deliverables exist and are
  consistent — see `docs/ROADMAP.md`).
- Block 0.2 SDK-Oriented Module Structure: complete. UI-free `:core` module introduced;
  `Platform` moved into it; `:shared` depends on `:core` and remains the sample/UI host.
  The `:core` + `:shared` split is the settled Phase 0 module structure; further splits are
  deferred. See `docs/DECISIONS/0002-module-structure.md`.
- Block 0.3 Testing Infrastructure: complete. Added `docs/TESTING.md` (test source-set
  strategy, fixture layout, external test-vector policy), a `core/.../resources/fixtures/`
  folder structure with placeholder READMEs citing future sources, and a minimal `:core`
  `jvmTest` smoke test. See `docs/ROADMAP.md` Block 0.3 Outcome.
- Block 0.4 Core Primitives: complete. First step landed a shared `KardanoResult<T, E>`
  (`Ok` / `Err`) type, `Network` (`TESTNET` = 0, `MAINNET` = 1) with a typed `fromId`, and
  `Lovelace` (`@JvmInline value class` over `Long`, range `0..Long.MAX_VALUE`, negatives
  rejected, no arithmetic). Final step added byte-backed structural value types: `TxHash`
  (32 bytes), `PolicyId` (28 bytes), `AssetName` (0..32 bytes) sharing a `ByteSizeError`,
  and `UtxoRef` (`TxHash` + non-negative output index) with `UtxoRefError`. All have
  valid/invalid/edge tests in `core/src/commonTest`. `Address` was deferred to Block 0.7.
  See `docs/ROADMAP.md` Block 0.4 Outcome.
- Block 0.5 Encoding Utilities: complete. The Hex step landed a generic, bounded `Hex`
  codec in `:core` (`Hex.encode` / `Hex.decode`) with a typed `HexError`
  (`InputTooLong` / `OddLength` / `InvalidCharacter`), a named limit `Hex.MAX_INPUT_CHARS`,
  canonical lowercase encoding, mixed-case decoding, and validation before allocation. The
  Bech32 step landed a generic, bounded Bech32/Bech32m codec in `:core` (`Bech32.encode` /
  `Bech32.decode`, `Bech32Variant`, `Bech32Decoded`, `Bech32Error`) working at the 5-bit data
  layer: variant auto-detection on decode, mixed-case rejection, lowercase encoder output,
  HRP/separator/charset/checksum validation, and SDK-owned limits (`MAX_INPUT_CHARS`,
  `MAX_HRP_CHARS`, `MAX_DATA_VALUES`, plus `MAX_DATA_BYTES` for the internal `convertBits`)
  enforced with typed errors before allocation. Tests use the official BIP-173/BIP-350
  vectors verbatim plus edge/limit/round-trip cases. The final step added the Cardano HRP
  allowlist wrappers (`CardanoHrp`, `CardanoBech32`, `CardanoBech32Error`): `encode` takes a
  `CardanoHrp` and forces Bech32; `decode` delegates to the engine, then checks the HRP
  allowlist first and the variant second, rejecting Bech32m and non-allowlisted HRPs with a
  typed error while propagating generic failures via `Underlying`. HRP allowlist plus Bech32
  checksum/charset validation only — no address parsing, header inspection, or network-id
  reading. No dependencies or Gradle changes. See `docs/ROADMAP.md` Block 0.5 Outcome.
- Block 0.6 CBOR And Parser Strategy: complete. A bounded CBOR decoder/encoder in `:core`
  covers the definite-length subset (`Cbor`, sealed `CborValue` = `CborUnsigned` /
  `CborNegative` within signed `Long`, `CborByteString`, `CborTextString`, `CborArray`,
  `CborMap` as an ordered list of `CborEntry`; typed `CborError`). Canonical shortest-form
  encoding; named limits (`CBOR_MAX_INPUT_BYTES`, `CBOR_MAX_BYTESTRING_BYTES`,
  `CBOR_MAX_STRING_BYTES`, `CBOR_MAX_NESTING_DEPTH` = 64, `CBOR_MAX_COLLECTION_ELEMENTS` =
  65536) enforced before allocation / before reading collection elements; no allocation or
  list sizing from an untrusted declared length or count. Maps enforce the Phase 0
  deterministic rule (ADR-0001 / RFC 8949 §4.2.1: strictly ascending canonical key bytes, no
  duplicates) on both decode and encode; the encoder rejects rather than sorting. Tags/
  bignums/floats/indefinite/non-canonical/out-of-range/over-limit/  over-deep/trailing all
  rejected with typed errors. See `docs/ROADMAP.md` Block 0.6 Outcome.
- Block 0.6.5 Core Package Organization: complete. Reorganized the flat
  `org.sarmidev.kardano` package in `:core` into `primitives`, `encoding.hex`,
  `encoding.bech32`, and `encoding.cbor`; `KardanoResult` and `Platform` stay at the root.
  Architecture-only package move: type names unchanged, fully qualified names/imports
  changed (pre-alpha), no new modules, no dependencies. Gradle module splits deferred. See
  `docs/DECISIONS/0003-core-package-structure.md`.
- Block 0.8 Crypto Strategy Document: complete. ADR-0004 (`docs/DECISIONS/0004-crypto-strategy.md`,
  Accepted) records the cryptography strategy before any implementation lands. Policies recorded:
  no handwritten crypto; all future crypto delegated to externally maintained libraries or
  platform bindings selected through documented evaluation per algorithm; crypto isolated from
  `:core`; likely end state a separate module (`:crypto`, not final); seam pattern
  (expect/actual vs. common interface) chosen per algorithm; key-material lifecycle policy;
  typed-error / `KardanoResult` API policy; test-vector policy (official only, no vectors in
  this block). Algorithm scope, four candidate categories + evaluation template (all
  `Needs investigation` / `Unverified`), target matrix, platform-specific concerns, and seven
  open questions also documented. Fixed two existing governance docs that had named concrete
  libraries as if selected (`docs/SECURITY.md` principle 1 and `docs/AI_WORKING_AGREEMENT.md`
  crypto lines). No Kotlin, Gradle, dependency, or test changes.
- Block 0.7 Address Parsing And Structural Validation: complete (structural CIP-19 parsing of
  the Shelley Bech32 families — base 0-3, pointer 4-5, enterprise 6-7, reward/stake 14-15 —
  across mainnet/testnet, decode-only, via `Address.parse`). Step 1 added the
  `org.sarmidev.kardano.address` package with `Address` / `Address.parse`, `AddressType`,
  `AddressCredential` + `CredentialKind`, and `AddressError` for the single-credential
  Shelley types (enterprise `addr`/`addr_test` types 6/7, reward `stake`/`stake_test` types
  14/15). Step 2 added the two-credential **base** types (`addr`/`addr_test`, CIP-19 header
  types 0-3, fixed 57-byte payload) as `AddressType.BASE`, and replaced the ambiguous single
  `Address.credential` property with explicit nullable `paymentCredential` and
  `stakeCredential` (enterprise → payment only; reward → stake only; base → both). Step 3
  added the **pointer** types (`addr`/`addr_test`, CIP-19 header types 4-5) as
  `AddressType.POINTER`: a payment credential plus a variable-length chain pointer
  (`AddressPointer` = `slot`/`transactionIndex`/`certificateIndex` as non-negative `Long`,
  with a `PointerField` enum) exposed via a new nullable `Address.pointer`; pointer → payment
  + pointer (`stakeCredential` null). Parsing still decodes via `CardanoBech32`, does the
  5→8-bit conversion (`pad = false`), reads the header byte, resolves `Network.fromId`, and
  enforces HRP↔network + HRP↔family agreement (the `addr` family now accepts base, pointer,
  and enterprise); base/enterprise/reward use a per-type fixed length (57/29) while pointer
  uses a dedicated variable-length path. The pointer is three CIP-19 variable-length unsigned
  integers, decoded with bounded named limits (`MAX_POINTER_FIELD_BYTES` = 9,
  `MIN_POINTER_PAYLOAD_SIZE` = 32), an overflow check **before** each shift (no signed-`Long`
  wraparound), and typed rejection of truncated/non-canonical/over-range/trailing-byte
  encodings. Byron (8) and reserved types, bad lengths, checksums, and padding are rejected
  with typed errors. `AddressCredential` / `CredentialKind` are unchanged; all bytes
  defensively copied; structural-only KDoc. Tests use CIP-19 `type-00..07/14/15` vectors
  verbatim plus labeled derived rule tests. Rejecting non-canonical (over-long) pointer
  variable-length integers is an accepted Phase 0 parser decision (stricter than the lenient
  ledger decoder; consistent with the reject-never-normalize guardrail). Byron/Base58 and
  raw-byte/hex constructors are deferred beyond Block 0.7 (separate future work). No
  dependencies or Gradle changes. See `docs/ROADMAP.md` Block 0.7 Outcome and closure.
- Block 0.9 Phase 0 Closure Review: complete. Review/documentation/verification block only
  (no new features, no Kotlin behavior changes, no Gradle/dependency changes, no
  crypto/signing/key/mnemonic code, no validator relaxation). Verification passed
  (`:core:jvmTest`, `:core:testAndroidHostTest`, `:core:compileTestKotlinIosSimulatorArm64`;
  iOS simulator execution macOS/Xcode-gated, compile-only). Heuristic scans run and every hit
  classified as policy/ADR/disclaimer/structural-KDoc — no implementation crypto/signing, no
  real keys/mnemonics, no `ByteArray ==`, no Byron/Base58/raw `Address` constructor, no
  Gradle/dependency drift. `explicitApi()` holds; failable APIs return `KardanoResult`/sealed
  errors; parser limits + reject-never-normalize policy documented and implemented; tests cite
  official vectors verbatim. Docs reconciled (ROADMAP "Current Status" + this file set to
  "Phase 0 complete"; `docs/TESTING.md` gained the two omitted `:core` commands). No standalone
  closure document was created. See `docs/ROADMAP.md` Block 0.9 Outcome.
- Block 1.2 Android SDK Playground: complete. First Phase 1 implementation block. Added the
  `org.sarmidev.kardano.playground` package in `:shared` `commonMain` with `PlaygroundPresenter`
  (pure, UI-free; maps `:core` results to display models; `internal fun presentAddressError`
  directly unit-testable), `PlaygroundScreen` (Compose; address parser + typed error display +
  Hex + CBOR sections), and replaced `App.kt` to render the screen. Presenter tests in
  `:shared` `commonTest` exercise `AddressError` variants directly (no fragile input-dependent
  construction) plus 2 cited CIP-19 happy-path vectors (type-06/type-14 testnet), 1 invalid
  input test, and 1 Empty-state test. All
  build/test commands pass (BUILD SUCCESSFUL). `:core` untouched; no new Gradle modules or
  dependencies. Manual Android checkpoint documented in `docs/PHASE_1_PLAN.md` Block 1.2.
- Block 1.3a Provider Read-Only Boundary (interface + models + mock): complete. Added a new
  KMP Gradle module `:provider` (Android library + JVM + iosArm64 + iosSimulatorArm64,
  `explicitApi()`) depending only on `:core`; justified by ownership (provider logic must not
  live in dependency-free `:core` nor stay permanently in the `:shared` sample host).
  `:provider` `commonMain` adds no dependency; only `commonTest` uses `kotlinx-coroutines-test`
  (pinned in the catalog). Package `org.sarmidev.kardano.provider`: `ChainQueryProvider`
  (read-only; `val network: Network`; suspend `getUtxos` / `getProtocolParameters` / `getTip`;
  all return `KardanoResult`, never throw), provider-neutral ADA-only models (`Utxo`, `Value`,
  `ProtocolParameters`, `ChainTip`) and a sealed `ProviderError` (`Transport`,
  `RemoteStatus(code)` — transport-agnostic, not `HttpStatus` — `NotFound`, `Deserialization`,
  `RateLimited`, `NetworkMismatch`, `Unknown`), and `InMemoryChainQueryProvider` (a documented
  fake/test-only mock with two seed addresses: `SEED_ADDRESS_WITH_UTXOS`, `SEED_ADDRESS_EMPTY`,
  both public CIP-19 testnet vectors). Submit is deliberately not in the read-only interface:
  ADR-0006 refines ADR-0005 §5 by splitting query from a future `TxSubmitProvider` (Block
  1.11). The Playground gained a "Provider (mock)" section (`:shared` now depends on
  `:provider`), wired via `LaunchedEffect` (no new coroutine dep in `:shared`); pure mapping
  extracted to `internal` non-suspend functions for coroutine-free tests. Tests: `:provider`
  `commonTest` (`runTest`) + `:shared` presenter mapping tests. ADR-0006 added; ADR-0005 §5
  carries a one-line refinement cross-reference. All builds/tests pass. See
  `docs/DECISIONS/0006-provider-boundary-and-strategy.md` and `docs/PHASE_1_PLAN.md` Block 1.3.
- Block 1.1 Phase 1 Scope And Architecture Plan: complete (previous session).
  Recorded in `docs/PHASE_1_PLAN.md` ("Block 1.1 Decisions") and
  `docs/DECISIONS/0005-phase-1-architecture-and-scope.md` (ADR-0005, Accepted): the MVP
  preprod flow (create/restore test wallet, derive address, query UTxOs, build a minimal
  ADA-only tx, sign locally, submit to preprod, show result in Android); native assets placed
  out of the first MVP; Android set as the primary Phase 1 validation target, iOS/JVM-Desktop
  compile-only unless explicitly revisited; module/package strategy recorded as decision
  criteria only (packages first while dependency-free and ownership is exploratory; a
  crypto/provider/network dependency is the likely Gradle-module trigger; `:core` stays
  dependency-free; `:shared` stays the sample/UI host, not the SDK's long-term home — no
  module created and no home asserted for crypto/provider packages); provider strategy set
  to mock/stub first with Blockfrost as the first real preprod target and a minimal API
  (concrete selection deferred to Block 1.3); crypto decision path kept at Block 1.4/1.5
  against ADR-0004 (no library selected here); the address encoding/round-trip prerequisite
  (before Block 1.7) and the CBOR tx map-ordering prerequisite (before Block 1.9) recorded as
  deferred, each resolved in its own block. `docs/ROADMAP.md` Phase 1 acceptance criteria
  reconciled to Android-primary. Android baseline build verified
  (`./gradlew :androidApp:assembleDebug :core:jvmTest`); no app-launch claim made from that
  command alone. See `docs/ROADMAP.md` Phase 1 block sequence, Block 1.1 outcome.

**Block 1.3 is complete (1.3a + 1.3b-pre + 1.3b).** 1.3b-pre landed `Address.bech32` in
`:core` (the exact validated `Address.parse` input string, threaded through the fixed-size and
pointer paths, excluded from `equals`/`hashCode`/`toString`; it is the validated source
representation, not a `toBech32` re-encoder — encoding/round-trip stays deferred to Block 1.7).
1.3b then landed `:provider-blockfrost`: `BlockfrostChainQueryProvider` over Ktor (OkHttp/CIO/
Darwin engines) + kotlinx-serialization, with `internal @Serializable` DTOs mapped to the
neutral `:provider` models (UTxO pagination + ADA-only summation, protocol params, tip,
`404`-as-empty in `getUtxos`, and error mapping to `Transport`/`RateLimited`/`RemoteStatus`/
`NotFound`/`Deserialization`). `BlockfrostNetwork { PREPROD, PREVIEW, MAINNET }` maps to
`Network`. HTTP status codes are mapped to `RemoteStatus` only inside `:provider-blockfrost`;
`:core` and `:provider` stay HTTP-free. Tests use a Ktor `MockEngine` + sanitized fixtures; a
live preprod test is opt-in via `BLOCKFROST_PROJECT_ID` and skipped by default. The Playground
gained a "Use live Blockfrost (preprod)" toggle and a `project_id` field held in non-persistent
Compose state (`remember`, never stored/logged); Android got the `INTERNET` permission. No
secrets are committed. See `docs/DECISIONS/0007-http-client-and-blockfrost-provider.md`.

**Block 1.4 (Crypto Evaluation And Module Decision) is complete (docs-only).** ADR-0008
(`docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md`) is `Accepted` for
the module/seam/process decisions only and makes no final dependency-fitness claim while
compatibility is untested. Decided now: `:crypto` deferred to Block 1.5; the seam is a
`commonMain` common interface/adapter (`Hashing`, later `KeyDerivation`/`Signing`) returning
`KardanoResult` (no throwing across Swift/ObjC), with `expect`/`actual` as fallback; the first
algorithm boundary in Block 1.5 is Blake2b-224/256 behind `Hashing` with official cited vectors
(RFC 7693 / Cardano context), no invented vectors. Provisional: candidate selection is
provisional, with Hyperledger Identus Apollo + `bip32-ed25519` as the provisional lead (Kotlin
2.4.0 compatibility marked `To verify in 1.5a`); cryptography-kotlin (whyoleg) and ionspin
libsodium are the composition fallback; bloxbean cardano-client-lib is rejected as a shipped
dependency (JVM-only, no iOS) and retained only as a JVM vector oracle. The candidate matrix is
source-cited with unknowns marked `Unverified` / `To verify in 1.5a` and neutral review fields
(`External review`, `Public review notes`). ADR-0004 carries a one-line cross-reference to
ADR-0008. No Kotlin/Gradle/dependency/module changes.

**Block 1.5a (crypto compatibility spike) is complete (PASS).** On a throwaway branch
(`spike/1.5a-apollo-kotlin24`, since discarded) with a scratch `:crypto-spike` KMP module
depending only on the two candidate artifacts, the provisional candidate resolved and compiled on
all three required targets under this repo's Kotlin 2.4.0 / AGP 9.0.1 (new
`com.android.kotlin.multiplatform.library` plugin): `:crypto-spike:compileKotlinJvm`,
`:crypto-spike:compileKotlinIosSimulatorArm64`, and `:crypto-spike:testAndroidHostTest`
(`compileAndroidMain`). Resolved versions: `org.hyperledger.identus:apollo:1.8.8` +
`dev.allain:bip32-ed25519:2.3.0`. Correction to the prior plan: the
`org.hyperledger.identus:secp256k1-kmp:1.8.8` companion was **not** needed — Apollo pulls
`fr.acinq.secp256k1:secp256k1-kmp:0.16.0` transitively, and the candidates' declared stdlib
versions (1.9.25 / 1.9.22 / 2.2.0) coalesce to 2.4.0 without conflict. This proves resolution +
compilation/typecheck (including the iOS-simulator klib) only, not runtime cryptographic
correctness or native-binary linkage. No dependency was committed to the build; the scratch module
and its `settings.gradle.kts` entry were discarded. See ADR-0008 §6.

**Block 1.5b-pre (vector-source gate) is complete (docs-only); it passes for both digest
sizes.** Before creating `:crypto` or writing any hashing code, a blocking gate searched for
exact, official, citable Blake2b known-answer vectors (input bytes + exact digest + source
URL/commit). Result: Blake2b-224 PASS (CIP-19: verification key `addr_vk1w0l2sr…` + the 28-byte
payment credential from the full CIP-19 address `addr1qx2fxv2umyhttk…`, extractable via `:core`
`Address.parse`); Blake2b-256 PASS — IntersectMBO Plutus `blake2b_256` conformance goldens
(`IntersectMBO/plutus` @`5e18824e2e0e30656c81d182e0ca512b75e7e57c`, Apache-2.0, path prefix
`plutus-conformance/test-cases/uplc/evaluation/builtin/semantics/blake2b_256/`): input `#`
(empty) → `0e5751c026e543b2e8ab2eb06099daa1d1e5df47778f7787faab45cdf12fe3a8`, input
`2e7ea84da4bc4d7cfb463e3f2c8647057afff3fbececa1d200` (25 bytes) →
`91c60f99b33303c02b39ed93b713e3915a180c3747f3b31e05727618ee401624`. Each fixture is
`equalsByteString (blake2b_256 (con bytestring #INPUT)) (con bytestring #EXPECTED)` → `True`, so
the builtin hashes the raw UPLC bytestring literal only (no CBOR/UPLC envelope); the empty-input
digest previously seen only in a non-official third-party repo is now confirmed in this official
Intersect source. No module, dependency, API, or Kotlin/Gradle change landed. See ADR-0008 §7.

Block 1.5b is **complete**: the `:crypto` KMP module was created and Blake2b-224/256 wired
behind the backend-neutral `Hashing` interface. During wiring it was found that Apollo 1.8.8
ships no Blake2b, so the hashing-only backend is KotlinCrypto `org.kotlincrypto.hash:blake2`
`0.8.0` (pinned); Apollo and `bip32-ed25519` were not added and are reserved for 1.6 / 1.10.
See ADR-0008 §8, `docs/PHASE_1_PLAN.md` Block 1.5b, and `docs/ROADMAP.md`.

Next recommended task: **Block 1.6 (mnemonic / seed / key derivation)** — create/restore a test
wallet and derive keys per CIP-1852 / CIP-3 / BIP-39, citing vectors verbatim. Per ADR-0009, the
main Apollo artifact does not enter Block 1.6; Ed25519-BIP32 derivation (1.6c) uses the
standalone `dev.allain:bip32-ed25519` module instead.

Current modules:

- `:core` (UI-free SDK core seed)
- `:crypto` (Blake2b hashing boundary; added in Block 1.5b; depends only on `:core`; backed by
  KotlinCrypto `blake2`; no backend type in the public API)
- `:provider` (read-only chain query boundary + in-memory mock; added in Block 1.3a; depends
  only on `:core`, no third-party `commonMain` dependency)
- `:provider-blockfrost` (Blockfrost preprod provider: Ktor + kotlinx-serialization; added in
  Block 1.3b; depends on `:provider` + `:core`; the only module with an HTTP dependency)
- `:shared` (sample/UI host; builds the iOS `Shared` framework; depends on `:core`,
  `:provider`, and `:provider-blockfrost`)
- `:androidApp`, `:desktopApp`, and `iosApp` (Xcode entry point)

`:provider` was created in Block 1.3a, `:provider-blockfrost` in Block 1.3b, and `:crypto` in
Block 1.5b, each justified by the ownership/dependency boundary in
ADR-0005/ADR-0006/ADR-0007/ADR-0008. Further module splits (`:wallet`, `:tx`) remain deferred to
the block that introduces their dependency/ownership pressure.

Current priority:

- Keep scope tight.
- Avoid custom crypto.
- Do not implement transaction signing before crypto, provider, and transaction-builder
  scope are each implemented and reviewed at their respective blocks (per ADR-0005).
- Build tests and docs from the start.
- Phase 0 (Blocks 0.1–0.9) and Phase 1 Block 1.1 are complete; the next step is Phase 1
  *implementation* starting at Block 1.2 (`docs/PHASE_1_PLAN.md`, `docs/ROADMAP.md`) — Android
  SDK Playground, no wallet/crypto/provider/tx code yet.

## Decisions Already Made

- The project is mobile-first and KMP-first.
- Android and iOS are primary targets.
- JVM/Desktop is included for fast testing, demos and tooling.
- Web/Wasm is not a priority for Phase 0.
- Phase 0 must not implement transaction signing.
- Phase 0 must not implement custom cryptography.
- Public APIs must be documented.
- Unit tests are required for primitives, parsers, encoders and validators.
- CBOR must not be implemented before a documented technical decision.
- Parser limits and anti-DoS behavior must be explicit.
- Address validation must preserve and check network id.
- iOS/Swift error handling must be considered from the beginning.
- Phase 1 MVP is Android-primary; iOS and JVM/Desktop are compile-only in Phase 1 unless a
  future block explicitly revisits this (Block 1.1 / ADR-0005).
- Phase 1's first MVP transaction flow is ADA-only; native assets are deferred out of the
  first MVP (Block 1.1 / ADR-0005).
- Phase 1 provider strategy is mock/stub first, with Blockfrost as the first real preprod
  target and a minimal public API; concrete provider selection is deferred to Block 1.3
  (Block 1.1 / ADR-0005).
- Phase 1 module/package strategy is decision criteria, not a committed structure: packages
  first where the work is dependency-free and ownership is still exploratory; a
  crypto/provider/network dependency is the likely trigger for a real Gradle module; `:core`
  stays dependency-free; `:shared` stays the sample/UI host, not the long-term SDK home
  (Block 1.1 / ADR-0005).

## Open Decisions

These should be resolved before or during Phase 0/Phase 1 implementation:

1. Final module structure:
   - A UI-free `:core` module has been introduced (ADR-0002), and its internal package
     layout is settled (ADR-0003: `primitives`, `encoding.{hex,bech32,cbor}`, plus the
     `address` package added in Block 0.7). Block 1.1 (ADR-0005) recorded the *decision
     criteria* for when packages become Gradle modules (see "Decisions Already Made" above),
     but the final *module* structure is still open: whether/when to extract `:crypto`,
     `:wallet`, `:tx`, `:provider`, and whether `:shared` later becomes a dedicated
     `:sample:*` module. The likely trigger is Block 1.3 (provider, needs an HTTP client) or
     Block 1.4/1.5 (crypto, needs a crypto library/binding); no module is created until then.

2. CBOR strategy: **Resolved and implemented** (ADR-0001 Accepted) — constrained internal
   CBOR subset (definite-length only), no external dependency. The definite-length subset
   (`Cbor` / `CborValue` / `CborError`) has landed in `:core` covering primitives plus arrays
   and maps; Block 0.6 is complete. One open item is recorded for later: the Phase 0 map
   ordering rule uses RFC 8949 §4.2.1 (bytewise) per ADR-0001; whether Cardano transaction
   serialization will instead need RFC 7049 length-first ordering is left to the future
   tx-serialization work and is not asserted here.

3. Bech32 strategy: **Resolved and implemented** (ADR-0001 Accepted) — a constrained internal
   generic Bech32/Bech32m codec has landed in `:core` with verbatim BIP-173/BIP-350 vectors and
   no external dependency, plus the Cardano HRP allowlist wrappers (`CardanoBech32`). Block 0.5
   is complete.

4. Crypto strategy: **Strategy documented (ADR-0004) and Block 1.4 decision recorded
   (ADR-0008).** ADR-0004 (Accepted) holds the selection policy, key-material lifecycle, error
   policy, algorithm scope, and test-vector policy. Block 1.4 / ADR-0008 (Accepted for
   module/seam/process only) then decided: `:crypto` deferred to Block 1.5; the seam is a
   `commonMain` common interface/adapter (`Hashing` first) returning `KardanoResult`; the first
   algorithm boundary is Blake2b-224/256 with official cited vectors. **Still open:** the
   concrete dependency is provisional (Apollo + `bip32-ed25519` is the provisional lead) and is
   selected only after the Block 1.5a Kotlin-2.4.0 compatibility spike; per-algorithm library
   choices for derivation/signing follow in Blocks 1.6/1.10, each updating ADR-0004's matrix.
   **Block 1.6a (ADR-0009) fixed the derivation choices, and Block 1.6b closed the PBKDF2
   provider-coverage gate:** hashing = KotlinCrypto `blake2` (1.5b); mnemonic checksum =
   KotlinCrypto `sha2` (1.6b). Icarus PBKDF2 was originally a cryptography-kotlin lead, but
   1.6b's gate check found it fails on Android (JCA `PBKDF2WithHmacSHA512` is API 26+, below
   `minSdk = 24`), so 1.6b adopted the ADR-0009 §3 platform-seam fallback instead: BouncyCastle
   on JVM/Android, Apple CommonCrypto on iOS (iOS wiring blocked in this environment — see the
   Last Session Summary above). `cryptography-kotlin` is not added to this repository.
   Ed25519-BIP32 = `dev.allain:bip32-ed25519:2.3.0` (1.6c, not yet implemented). The main Apollo
   artifact enters neither 1.5 nor 1.6; its remaining candidacy is Block 1.10 (signing).
   See `docs/DECISIONS/0004-crypto-strategy.md` (open questions),
   `docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md`, and
   `docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md`.

5. Test vector sources:
   - The authoritative spec sources are now documented in `docs/TESTING.md` (Bech32/Bech32m
     → BIP-173/350; CBOR → RFC 8949 Appendix A; addresses → CIP-19). The specific
     tooling/reference repos used to copy vectors verbatim are still chosen per feature as
     it is implemented.

## What Not To Do Yet

Do not implement:

- Mnemonic generation.
- Private key handling.
- Transaction signing.
- Transaction submission.
- Real wallet flows.
- Plutus support.
- Staking or delegation.
- Hardware wallet behavior.
- Production security claims.

Do not use:

- Invented test vectors for protocol behavior.
- Handwritten cryptographic algorithms.
- Lenient parsers that accept malformed input to make tests pass.
- `ByteArray == ByteArray` for content equality.

## Session Update Template

At the end of each session, update this section.

### Last Session Summary

Date: 2026-07-12

Summary:

- **Block 1.6d (test-wallet fixture + Android Playground checkpoint) — delivered.** `:shared`
  gained a project dependency on `:crypto` (no new external dependency; verified first as its
  own gate: `:shared:compileKotlinIosSimulatorArm64`/`compileKotlinIosArm64`,
  `:androidApp:assembleDebug`, and `:desktopApp:compileKotlin` all still pass with the
  transitive native backends now bundled — no AGP duplicate-class or packaging regressions).
  New `playground/TestWalletFixture.kt` (`internal object`) holds the same cited test-only
  12-word mnemonic (`test walk nut …`) `:crypto`'s own `KeyDerivationVectorsTest`/
  `PublicKeyProjectionDeviceTest` already cite, and the fixed path `m/1852'/1815'/0'/0/0`
  (`Cip1852Path.of(0, EXTERNAL, 0)`) — never a real mnemonic, never real funds.
- **Presenter chain, all sample-only code in `:shared`, no `:crypto` API change.**
  `PlaygroundPresenter.presentTestWallet()` runs `Mnemonic.parse` ->
  `IcarusMasterKey.fromMnemonic` -> `KeyDerivation.derivePrivate` -> `KeyDerivation.publicKey`
  -> `Hashing.blake2b224`, returning a new `WalletPresentation` sealed type that carries only
  the CIP-1852 path string, the Blake2b-224 fingerprint hex, and whether it matches the cited
  golden — never the mnemonic, entropy, seed, root/private key bytes, or the raw 32-byte public
  key. In a `finally`, calls `.clear()` only on the handles that expose it (`Mnemonic`,
  `IcarusMasterKey`, `ExtendedPrivateKey`, `ExtendedPublicKey`); `HashDigest` has no `clear()`
  and is treated as a public digest, not key material. New exhaustive
  `presentMnemonicError`/`presentKeyDerivationError`/`presentCryptoError` mappers (same
  direct-construction-testable pattern as the existing `presentAddressError`). A
  `presentTestWalletWithWords(words)` seam lets invalid-input handling be exercised without
  touching `TestWalletFixture`.
- **UI:** one new synchronous "Test Wallet (derivation)" Playground section (button ->
  `presentTestWallet()`, same pattern as the Address/Hex/CBOR sections — no `LaunchedEffect`
  needed since the whole chain returns `KardanoResult` today) plus a `WalletResultCard`. No
  freeze observed manually on the same devices used for 1.6c-follow-up-2's checkpoints; if a
  future manual pass on an older/slower device disagrees, the plan called for switching to the
  existing request-token + `Loading` pattern instead.
- **Test split, enforced by construction, not just convention:**
  `shared/commonTest`'s new `PlaygroundWalletPresenterTest` (16 cases; runs under
  `:shared:testAndroidHostTest` too) covers only error-mapping variants (constructed directly),
  `TestWalletFixture.path`'s string form, and two invalid-mnemonic inputs that `Mnemonic.parse`
  rejects before any native call is reached — it never calls `presentTestWallet()`. The single
  end-to-end fingerprint golden check lives only in `shared/jvmTest`'s new
  `PlaygroundWalletDerivationDesktopTest`, asserting the path and the fingerprint hex
  `9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e` (= the CIP-19 payment credential
  already pinned in 1.5b and reproduced end to end by `:crypto`'s
  `PublicKeyProjectionDeviceTest`). Android-runtime coverage of the native path itself is not
  re-implemented in `:shared`; it stays `:crypto:connectedAndroidDeviceTest` plus the manual
  Android Playground checkpoint (below).
- Tests run this session: `:shared:jvmTest` (all pass, including the new golden test);
  `:shared:testAndroidHostTest` (all pass, 16/16 on the new native-free presenter test);
  `:shared:compileKotlinIosSimulatorArm64`/`compileKotlinIosArm64` (pass);
  `:desktopApp:compileKotlin` (pass); `:androidApp:assembleDebug` (pass; native `.so`s for
  `libsodium`/`libuniffi_ed25519_bip32_wrapper` package correctly, matching the 1.6c-follow-up-2
  finding); lints clean on every new/edited file.
- Files changed this session: `shared/build.gradle.kts` (added `implementation(projects.crypto)`
  to `commonMain`); `shared/src/commonMain/kotlin/org/sarmidev/kardano/playground/`:
  `TestWalletFixture.kt` (new), `PlaygroundPresenter.kt` (added `WalletPresentation` +
  `presentTestWallet`/`presentTestWalletWithWords` + three error mappers),
  `PlaygroundScreen.kt` (new section, `WalletResultCard`, reworded top KDoc to cover the
  `:crypto` checkpoint without implying SDK core logic lives in `:shared`);
  `shared/src/commonTest/kotlin/org/sarmidev/kardano/playground/PlaygroundWalletPresenterTest.kt`
  (new); `shared/src/jvmTest/kotlin/org/sarmidev/kardano/playground/PlaygroundWalletDerivationDesktopTest.kt`
  (new); `shared/README.md`, `docs/PHASE_1_PLAN.md`, `docs/ROADMAP.md`, this file. No ADR
  added or amended (no new dependency, no new decision beyond ADR-0010's already-recorded
  ones).

- **Android Playground checkpoint confirmed this session**, driven via `adb` (install, launch,
  scroll, `uiautomator dump` for exact button bounds, tap, screenshot) rather than left for a
  separate manual pass: on both the API 36 and API 24 emulators, tapping "Restore test wallet &
  derive" rendered `Path: m/1852'/1815'/0'/0/0`, `Fingerprint (Blake2b-224):
  9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e`, `Matches cited vector: yes`, with
  no crash/ANR (`logcat` checked) and no noticeable freeze on API 24 (result rendered within
  roughly 500–750 ms of the tap). The connected physical device (`SM-A356B`) was left untouched
  for this UI pass since it is PIN-locked; its native derivation/projection path is already
  covered by this session's `:crypto:connectedAndroidDeviceTest` run (12/12 passing across all
  three runtimes, physical device included).

Next recommended task:

- **Block 1.7 (address generation)** is the natural next step — not started, has not run its
  own dependency/target-verification gate.
- iOS runtime execution of vectors (derivation, projection, and now this checkpoint's chain)
  remains future work, same posture as every prior block.
- No commit was made this session unless the project owner explicitly requests one.

### Session Summary (1.6c-follow-up-2)

Date: 2026-07-12

Summary:

- **1.6c-follow-up-2 (closes the Android public-key-projection blocker the 1.6c-follow-up
  session below opened; full write-up:
  [ADR-0010 §2a](DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md).**
  Ran the gate this block's plan specified before any implementation: extracted
  `com.goterl:lazysodium-android:5.2.0`'s AAR and confirmed by `nm -D` (dynamic/exported symbol
  table) that `crypto_scalarmult_ed25519_base_noclamp` is exported as a global symbol on all
  four bundled ABIs — the symbol Ionspin's Android build (used for JVM/iOS) lacks entirely.
  Disassembled its `classes.jar` with `javap` across every class and confirmed its own
  `Sodium`/`SodiumAndroid` JNA interfaces do **not** declare that function anywhere, so the
  fix defines a minimal custom JNA `Library` interface for the one symbol needed, loaded via
  `Native.load("sodium", ...)` after `SodiumAndroid()` triggers the library's normal
  native-load path.
- **Runtime coverage for this gate: three real Android runtimes, not one.** In addition to the
  already-provisioned API 36 emulator, a physical device (`SM-A356B`, Android 15, API 35) was
  connected in the working environment, and a new **API 24** emulator
  (`system-images;android-24;google_apis;arm64-v8a`) was provisioned specifically to verify
  this project's actual `minSdk = 24` by execution rather than by inspection or extrapolation
  (Google publishes an `arm64-v8a` image for API 24, which runs natively on this Apple Silicon
  host). A throwaway on-device probe test (deleted after the gate) reproduced the cited
  `addr_xvk0` golden on all three runtimes before any production code changed.
- **Implementation.** `androidMain`'s `PublicKeyProjection.android.kt` actual now calls the
  real backend instead of immediately returning `PublicKeyProjectionUnavailable`: it wipes its
  output buffer on any failure path, maps native failures to the existing backend-neutral
  `KeyDerivationError.DerivationFailed`, and needs no intermediate scalar copy (unlike
  JVM/iOS's `UByteArray` conversion) since JNA's `byte[]` call signature matches `kL` directly.
  `com.goterl:lazysodium-android:5.2.0` and a pinned, `@aar`-typed
  `net.java.dev.jna:jna:5.17.0` were added to `androidMain` only (JVM/iOS keep the Ionspin
  backend, untouched). One packaging note: JNA publishes both a `.jar` and an `.aar` artifact
  for the same coordinate, and depending on it from two source sets that resolved different
  artifact types tripped AGP's duplicate-class check on the merged device-test APK — fixed by
  excluding JNA from the candidate's own dependency metadata, depending on it explicitly with
  a single pinned `@aar` coordinate, and adding a `packaging { resources.excludes += [...] }`
  block for a duplicated license-notice resource file. No effect on which native code
  loads/runs. `PublicKeyUnavailableDeviceTest` (whose contract — returning the unavailable
  error — no longer held) was replaced with `PublicKeyProjectionDeviceTest`, asserting both an
  `Ok` result matching `addr_xvk0` and that `Hashing.blake2b224` of the projected key matches
  the CIP-19 payment credential pinned in `HashingVectorsTest` (cross-linking two independently
  cited sources for the same key, per ADR-0009 §4). Updated KDoc across `KeyDerivation.kt`,
  `ExtendedPublicKey.kt`, `PublicKeyProjection.kt`, and `KeyDerivationError.kt` to state
  projection now works on every target; `KeyDerivationError.PublicKeyProjectionUnavailable`
  stays declared (removing a sealed-interface member is itself an API change) but no current
  target returns it.
- **Docs.** Added ADR-0010 §2a (the Android-projection resolution) and updated its header
  Status/Scope; reconciled `docs/PHASE_1_PLAN.md`, `docs/ROADMAP.md`, `crypto/README.md`, and
  this file to state public-key projection is verified on every target (JVM, real Android
  runtime, iOS compile/link) and that **1.6d's Android checkpoint is now fully unblocked**
  (both `derivePrivate` and `publicKey` verified on Android).
- Tests run this session: `:crypto:jvmTest` (pass, `addr_xvk` goldens unchanged);
  `:crypto:testAndroidHostTest` (pass); `:crypto:compileKotlinIosSimulatorArm64`/
  `compileKotlinIosArm64` (pass, no regression from the Android-only dependency addition);
  `:crypto:connectedAndroidDeviceTest` on all three real runtimes (API 24, 35, 36) — 4/4 tests
  pass on each device (`KeyDerivationDeviceTest`'s 2 unaffected derivation tests plus
  `PublicKeyProjectionDeviceTest`'s 2 new projection tests); lints clean; banned-word scan
  clean on every changed file.
- Files changed this session: `gradle/libs.versions.toml`, `crypto/build.gradle.kts`;
  `crypto/src/commonMain/kotlin/org/sarmidev/kardano/crypto/`: `KeyDerivation.kt`,
  `ExtendedPublicKey.kt`, `PublicKeyProjection.kt`, `KeyDerivationError.kt` (KDoc only, no
  signature changes); `crypto/src/androidMain/.../PublicKeyProjection.android.kt` (rewritten
  actual); `crypto/src/androidDeviceTest/kotlin/org/sarmidev/kardano/crypto/`:
  `PublicKeyUnavailableDeviceTest.kt` (deleted), `PublicKeyProjectionDeviceTest.kt` (new);
  `docs/DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md`,
  `docs/PHASE_1_PLAN.md`, `docs/ROADMAP.md`, `crypto/README.md`, this file.

Next recommended task:

- **Block 1.7 (address generation)** is the natural next step — it is not started and has not
  run its own dependency/target-verification gate, but no longer needs to account for any
  public-key-projection gap when scoping it, since projection is now verified on every target.
- iOS runtime execution of vectors (derivation and projection alike) remains future work,
  same posture as 1.6b/1.6c/1.6c-follow-up.
- No commit was made this session unless the project owner explicitly requests one; 1.6d/1.7
  were explicitly not started (per this block's own constraints).

### Session Summary (1.6c-follow-up)

Date: 2026-07-12

Summary:

- **1.6c-follow-up (closes both blockers ADR-0009's Block 1.6c gate result opened; full
  write-up: [ADR-0010](DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md)).**
  An Android runtime was not available in the initial verification environment, so — rather
  than accept a second artifact-only verdict — a local Android emulator (API 36, `arm64-v8a`)
  was provisioned in the working environment specifically to run real on-device verification.
  `adb devices` and `:crypto:connectedAndroidDeviceTest` below are against that emulator, not
  host JVM.
- **Derivation backend coordinate swap — resolves the Android-derivation blocker.** Swapped
  `gradle/libs.versions.toml`'s `bip32-ed25519` from `dev.allain:2.3.0` to
  `org.hyperledger.identus:1.8.8` — the upstream coordinate for the identical uniffi wrapper
  (same `deriveBytes`/`deriveBytesPub`/`fromNonextended` signatures; no adapter code changed).
  Its Android AAR ships the native `.so` the `dev.allain` republish omitted. Added a
  test-only `androidDeviceTest` source set to `:crypto` (`withDeviceTest {}` in
  `build.gradle.kts`, `KeyDerivationDeviceTest.kt`) exercising the same cited
  `IntersectMBO/cardano-addresses` golden vectors already pinned in ADR-0009 §4.
  `:crypto:connectedAndroidDeviceTest` **passed both tests on the real emulator** — actual
  on-device native-library loading and derivation, not host-JVM compile-only.
  `:crypto:jvmTest` and the iOS compile/link tasks were re-run with the swapped coordinate and
  are unaffected.
- **Public-key projection — implemented for JVM/iOS; Android is a new, separate, open
  blocker.** Added `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings:0.9.5` (+
  `kotlinx-coroutines-core`, needed to call its suspending initializer via `runBlocking`) to
  `jvmMain`/`iosArm64Main`/`iosSimulatorArm64Main` only, not `androidMain`. New
  `ExtendedPublicKey` (opaque, same key-material rules as `ExtendedPrivateKey`) and
  `KeyDerivation.publicKey(key)`, wired through an `internal expect fun projectPublicKey(kL)`
  seam (mirrors the existing PBKDF2 platform-seam pattern). The JVM/iOS actuals call
  libsodium's `crypto_scalarmult_ed25519_base_noclamp` over the extended private key's left
  32-byte scalar; verified byte-for-byte against the cited `addr_xvk` goldens
  (`m/1852'/1815'/0'/0/{0,1,1442}`) on `:crypto:jvmTest`'s new
  `publicKey_role0Index{0,1,1442}_matchesGoldenAddrXvk{0,1,1442}` tests. **On the same real
  emulator, this call throws a confirmed `UnsatisfiedLinkError: undefined symbol:
  crypto_scalarmult_ed25519_base_noclamp`.** Static inspection (`nm`/`strings`) confirmed the
  root cause: the published Android `.so` for this library exports only `crypto_sign_ed25519_*`
  symbols — no `crypto_core_ed25519_*`/`crypto_scalarmult_ed25519_*` at all — while the JVM
  artifact's bundled dylib exports the full set. This is a real gap in this specific published
  Android native build, not a math or wiring error. Per explicit owner approval, the
  `androidMain` actual does not attempt the native call: it returns
  `KeyDerivationError.PublicKeyProjectionUnavailable` immediately. Verified on the real
  emulator (`PublicKeyUnavailableDeviceTest`, part of `:crypto:connectedAndroidDeviceTest`)
  that this degrades gracefully rather than crashing.
- **Review-fix pass (same session, before commit):** (a) fixed a scalar-copy cleanup gap in
  the JVM/iOS `projectPublicKey` actuals — `kL.toUByteArray()` (a copy distinct from the
  caller's `kL`) and the native call's own `UByteArray` result were both left unwiped; both
  are now wiped in a `finally`/immediately-after-use block, matching the existing
  wipe-every-intermediate-copy discipline the rest of `:crypto` already follows; (b) added
  ADR-0010 (this section's write-up) and reconciled `docs/PHASE_1_PLAN.md`,
  `docs/ROADMAP.md`, `crypto/README.md`, and this file to state the Android split precisely:
  **derivation is verified on Android; public-key projection is not** — and to not describe
  1.6d's Android checkpoint or 1.7 as unblocked (only 1.6d's non-fingerprint,
  derivation-only portion is).
- Tests run this session: `:crypto:compileKotlinJvm`/`compileAndroidMain`/
  `compileKotlinIosSimulatorArm64`/`compileKotlinIosArm64` (all pass); `:crypto:jvmTest` (all
  suites pass, including 9/9 `KeyDerivationVectorsTest` cases with the 3 new `publicKey_*`
  tests); `:crypto:testAndroidHostTest` (pass); `:crypto:connectedAndroidDeviceTest` on the
  real emulator (3/3 pass: `fromMnemonic_rootMatchesGoldenRootXsk_onDeviceRuntime`,
  `derivePrivate_role0Index0_matchesGoldenAddrXsk0_onDeviceRuntime`,
  `publicKey_returnsUnavailableError_onDeviceRuntime`); lints clean; banned-word scan clean.
- Files changed this session: `gradle/libs.versions.toml`, `crypto/build.gradle.kts`;
  `crypto/src/commonMain/kotlin/org/sarmidev/kardano/crypto/`: `ExtendedPublicKey.kt` (new),
  `PublicKeyProjection.kt` (new expect seam), `KeyDerivationError.kt` (added
  `PublicKeyProjectionUnavailable`), `ExtendedPrivateKey.kt` (added internal
  `leftScalarAndChainCode()`), `KeyDerivation.kt` (added `publicKey(...)`),
  `Bip32Ed25519KeyDerivation.kt` (implemented `publicKey(...)`);
  `crypto/src/jvmMain/.../PublicKeyProjection.jvm.kt` (new),
  `crypto/src/iosArm64Main/.../PublicKeyProjection.ios.kt` (new),
  `crypto/src/iosSimulatorArm64Main/.../PublicKeyProjection.ios.kt` (new),
  `crypto/src/androidMain/.../PublicKeyProjection.android.kt` (new);
  `crypto/src/androidDeviceTest/kotlin/org/sarmidev/kardano/crypto/`:
  `KeyDerivationDeviceTest.kt`, `PublicKeyUnavailableDeviceTest.kt` (new source set + tests);
  `crypto/src/jvmTest/.../KeyDerivationVectorsTest.kt` (added `addr_xvk` vectors + tests);
  `docs/DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md` (new),
  `docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md` (forward-pointer amendment),
  `docs/PHASE_1_PLAN.md`, `docs/ROADMAP.md`, `crypto/README.md`, this file.

Next recommended task (as of this 2026-07-12 session; **closed the same day by
1.6c-follow-up-2 above — see that entry and ADR-0010 §2a for the current state**):

- Android public-key projection was an open blocker at this point. Candidate options
  considered for a future block: an alternative Android-capable Ed25519 "public key from a
  clamped scalar" library, a different libsodium Android distribution that does export the
  needed symbol, or an explicit re-scope decision. Whichever was chosen would need
  verification on real Android runtime.
- At this point, 1.6d could build its Android path-derivation/error-state work against a
  working `derivePrivate` on Android, but its fingerprint-display step and Android checkpoint
  as a whole were pending the item above.
- 1.7 (address generation) had not started and had not run its own dependency/target gate; it
  would need to account for the Android public-key-projection gap when scoping its own
  checkpoint, unless resolved first.
- No commit was made this session (explicitly deferred by the project owner); 1.6d/1.7 were
  explicitly not started.

### Session Summary (1.6c implementation)

Date: 2026-07-11

Summary:

- Block 1.6c (Ed25519-BIP32 + CIP-1852 derivation): implemented in `:crypto`, **narrowed to
  private derivation only**. Added `Cip1852Path`/`Cip1852Role` (SDK-owned CIP-1852 path type;
  `of(account: Long, role, index: Long)` validates range before storing as `Int`; uses this
  repo's "prime index"/`PRIME_INDEX_OFFSET` terminology per ADR-0009 §Terminology),
  `ExtendedPrivateKey` (opaque
  64-byte key + 32-byte chain code; private constructor, defensive copies, `clear()`, no
  public raw-private-key accessor), the `KeyDerivation` public interface
  (`derivePrivate(master, path)` only — see blocker below), and its
  `Bip32Ed25519KeyDerivation` adapter over `dev.allain:bip32-ed25519:2.3.0`'s
  `deriveBytes`, called directly from `commonMain` (Design A — the wrapper's API is
  callable from common code, no expect/actual seam needed for this dependency).
- **Pre-implementation blocking gate, run before writing adapter code:** inspected the
  published artifacts directly (`javap` on the JVM jar's constant pool, `unzip -l` on the
  Android AAR, the Gradle Module `.module` metadata) and ran throwaway probe tests, rather
  than trusting docs. Confirmed: the API resolves and is callable from `commonMain`; index
  parameters are Kotlin `UInt` (so prime indices are `0x8000_0000u + n`, no signed-`Int`
  overflow concern); `deriveBytes` returns a `Map` keyed `"secret_key"` (64 bytes) /
  `"chain_code"` (32 bytes); the scheme is V2 (Icarus) only, matching ADR-0009's restriction.
  This gate surfaced two blockers, resolved by explicit user decision rather than silently
  worked around:
  1. **No public-key-derivation primitive.** The pinned backend has private→private and
     public→public child derivation (`deriveBytes`/`deriveBytesPub`) but nothing that turns a
     private key into its public key. Decision: narrow 1.6c's public surface to
     `derivePrivate(...)` only; `ExtendedPublicKey`, `KeyDerivation.publicKey(...)`, and the
     `addr_xvk` vector checks are deferred to a separate follow-up block that makes its own
     dependency decision (Apollo's Ed25519 primitive is one candidate to evaluate there).
     This also blocks 1.6d's fingerprint-display checkpoint until that follow-up lands.
  2. **Android AAR ships no native library.** `unzip -l` on `bip32-ed25519-android` showed no
     `jni/<abi>/*.so` — only `classes.jar` and manifest/resources. Confirmed at runtime: an
     early `:crypto:testAndroidHostTest` run threw `UnsatisfiedLinkError` trying to load the
     backend — i.e. calling `deriveBytes` (what `derivePrivate` calls) reproducibly fails, not
     merely "has not been tried." No emulator was available in this environment for a
     fully device-confirmed verdict, but the AAR contains no native binary for any ABI, so a
     device run is expected to fail the same way. Decision: treat Android derivation as
     **blocked** for this dependency (stronger than "open risk" — a reproduced failure, not
     an absence of verification); JVM is the only verified target for 1.6c, and the 1.6d
     Android checkpoint is blocked, not merely at-risk, until this changes. Vector tests that
     call the backend were placed in `crypto/jvmTest` (not `commonTest`) specifically so
     `:crypto:testAndroidHostTest` keeps passing without silently masking the gap.
- **Review-fix pass (same session, before commit):** the initial framing above called 1.6c
  "complete" and Android an "open risk," which understated how strong the negative signal
  actually is. Reworded ADR-0009/`crypto/README.md`/`docs/PHASE_1_PLAN.md`/
  `docs/ROADMAP.md`/this file to say **JVM-verified + iOS compile/link verified; Android
  derivation blocked** wherever 1.6c's status is stated, and to make explicit that 1.6d's
  Android checkpoint is blocked (not just inheriting an "open risk") until Android has a
  working derivation path. Also: (a) fixed a byte-wipe gap in
  `Bip32Ed25519KeyDerivation.derivePrivate` — if `deriveBytes` ever returned one expected map
  key but not the other, the present array leaked unwiped before returning
  `InvalidKeyMaterial`; both are now wiped defensively in that branch; (b) removed the
  banned-word mention from `Cip1852Path.kt`'s KDoc (it had used a "never `X`" construction,
  which still writes the word) — reworded to name only "prime index"/`PRIME_INDEX_OFFSET`
  and point to ADR-0009 §Terminology, matching that section's own practice of never writing
  the banned word even to disclaim it.
- **iOS: both compile and link pass** for this dependency
  (`:crypto:compileKotlinIosSimulatorArm64`, `:crypto:compileKotlinIosArm64`) — an actual
  test-binary **link** against the Rust-backed static library, not just a compile, which is a
  stronger signal than 1.6b's iOS compile-only result.
- Tests: `Cip1852PathTest` and `ExtendedPrivateKeyTest` (structural: valid/invalid/edge
  construction, `toString()`, defensive copies, `clear()`) and
  `Bip32Ed25519KeyDerivationRuleTest` (unit-tests `mapThrowable` against synthetic
  `DerivationException` subtypes) live in `crypto/commonTest`. The backend-calling golden
  vector test, `KeyDerivationVectorsTest`, lives in `crypto/jvmTest` and checks
  `IcarusMasterKey.fromMnemonic` against the cited `root_xsk`, and
  `KeyDerivation.derivePrivate` against the cited `addr_xsk` for
  `m/1852'/1815'/0'/0/{0,1,1442}` — all from `IntersectMBO/cardano-addresses` Shelley
  goldens (already pinned by URL/commit/license in ADR-0009 §4; no new vectors invented). An
  internal `probeAccountPrefix` test helper (not public API) also checks the `acct_xsk`
  intermediate values for accounts 0 and 1, since the public API only derives a full
  `Cip1852Path`, not account-level prefixes. Bech32-decoding these CIP-5 keys in
  `crypto/jvmTest` uses a small test-only 5-bit→8-bit helper (cites BIP-173) instead of
  `:core`'s `Bech32.convertBits`, which is `internal` and not reachable from `:crypto`.
- Docs updated: ADR-0009 (new "Block 1.6c gate result" section, revised Blockers/Consequences/
  Follow-up work, public-API-shape narrowing note); `docs/PHASE_1_PLAN.md` (1.6c
  outcome, 1.6d note); `docs/ROADMAP.md` (Current Status + Block 1.6c/1.6d entries);
  `crypto/README.md` (1.6c role/scope/testing-placement); this file.

Files changed this step:

- `gradle/libs.versions.toml`, `crypto/build.gradle.kts` (`dev.allain:bip32-ed25519:2.3.0` in
  `commonMain`)
- `crypto/src/commonMain/kotlin/org/sarmidev/kardano/crypto/`: `Cip1852Path.kt`,
  `ExtendedPrivateKey.kt`, `KeyDerivation.kt`, `Bip32Ed25519KeyDerivation.kt` (new);
  `IcarusMasterKey.kt` (added internal `rootExtendedKeyBytes()`)
- `crypto/src/commonTest/kotlin/org/sarmidev/kardano/crypto/`: `Cip1852PathTest.kt`,
  `ExtendedPrivateKeyTest.kt`, `Bip32Ed25519KeyDerivationRuleTest.kt` (new)
- `crypto/src/jvmTest/kotlin/org/sarmidev/kardano/crypto/KeyDerivationVectorsTest.kt` (new)
- `docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md`, `docs/PHASE_1_PLAN.md`,
  `docs/ROADMAP.md`, `crypto/README.md`, `docs/HANDOFF.md`

Tests run:

- `./gradlew :crypto:jvmTest` — BUILD SUCCESSFUL (includes the 1.6c golden vectors).
- `./gradlew :crypto:testAndroidHostTest` — BUILD SUCCESSFUL (backend-calling tests excluded
  from this source set on purpose; see Summary).
- `./gradlew :crypto:compileKotlinIosSimulatorArm64 :crypto:compileKotlinIosArm64` — BUILD
  SUCCESSFUL (compile **and link**).

Next recommended task:

- **Public-key-derivation follow-up block (new, opened by 1.6c's gate):** pick a backend
  primitive for deriving a public key from a private/extended key (Apollo's Ed25519 support
  is one candidate), add `ExtendedPublicKey` and `KeyDerivation.publicKey(...)`, and verify
  the deferred `addr_xvk` vectors. 1.6d's fingerprint-display checkpoint is blocked on this.
- **Android derivation is blocked, not just unverified — needs its own resolution.**
  `KeyDerivation.derivePrivate` reproducibly throws `UnsatisfiedLinkError` under
  `:crypto:testAndroidHostTest`, and the published AAR contains no native binary for any ABI
  (so a real device/emulator run is expected, not merely likely, to fail the same way — none
  has actually been run). This blocks 1.6d's Android checkpoint specifically, not its
  non-Android work. Resolving it (an on-device run that disproves the failure, an
  Android-capable alternative dependency, or an explicit re-scope of the 1.6d checkpoint to
  JVM/iOS) is separate future work.
- 1.6d (test-wallet fixture + Android checkpoint) can proceed now on the private-derivation
  path for JVM/iOS and non-Android UI/error-state work; its fingerprint step and its Android
  checkpoint are both blocked pending the two items above, and should not be scheduled as if
  only "at risk."

### Session Summary (1.6b implementation)

Date: 2026-07-11

Summary:

- Block 1.6b (BIP-39 / CIP-3 mnemonic-to-master-key): implemented `Mnemonic.parse` and
  `IcarusMasterKey.fromMnemonic` in `:crypto` per ADR-0009 §5. **Complete on JVM and Android
  (executed CIP-3/BIP-39 vectors). On iOS, the compile targets now pass** via an interop shim
  (see below); **iOS runtime execution of the vectors is still future verification.**
- Closed the `To verify in 1.6b` gate — **cryptography-kotlin failed it.** Verified against
  the pinned `cryptography-kotlin` 0.6.0 source directly (not docs): its JDK-backed provider
  (used by both JVM and Android) calls JCA `SecretKeyFactory.getInstance
  ("PBKDF2WithHmacSHA512")`, guaranteed only from Android API 26, while this repo's
  `minSdk = 24`. `:crypto:testAndroidHostTest` cannot detect that gap (it runs on the host
  JVM, which does have the algorithm). Per ADR-0009 §3's documented fallback, adopted a
  platform seam instead: BouncyCastle `PKCS5S2ParametersGenerator` with `SHA512Digest`
  (`org.bouncycastle:bcprov-jdk18on`, pinned) on JVM and Android — it does not call
  `SecretKeyFactory`, so it is not subject to the API-26 restriction — and Apple CommonCrypto
  `CCKeyDerivationPBKDF` on iOS. No PBKDF2 is hand-written anywhere; full write-up in
  ADR-0009's new "Block 1.6b gate result" section.
- **iOS cinterop, resolved for the compile target:** the shipped Kotlin/Native
  `platform.CoreCrypto.CCKeyDerivationPBKDF` binding maps its `password` parameter to `String`,
  which cannot carry raw passphrase bytes. A first attempt added a custom cinterop definition
  (`crypto/src/nativeInterop/cinterop/pbkdf2raw.def`) using `noStringConversion` on
  `CCKeyDerivationPBKDF` itself (`modules = CommonCrypto`, mirroring JetBrains' own shipped
  `CommonCrypto.def`), but its generated klib came out with **zero declarations** in this
  build environment — confirmed by comparing `klib dump-metadata` output against the shipped
  `platform.CoreCrypto` klib, and reproduced even after removing `-fmodules` to match the
  shipped `.def` exactly.
  **Fix:** rewrote `pbkdf2raw.def` to add an inline C interop shim in the `.def`'s glue block —
  `kardano_ccpbkdf2_hmac_sha512(const uint8_t *password, size_t password_len, const uint8_t
  *salt, size_t salt_len, unsigned int rounds, uint8_t *derived_key, size_t derived_key_len)`
  (explicit `<stdint.h>`/`<stddef.h>`/`<CommonCrypto/CommonKeyDerivation.h>` includes) — that
  casts `password` to `const char *` only at the call boundary to `CCKeyDerivationPBKDF` and
  delegates every byte of the derivation to it; the shim implements no PBKDF2 itself. Verified
  bindable with `klib dump-metadata` before touching Kotlin: `kardano_ccpbkdf2_hmac_sha512`
  appears with `password` as `CValuesRef<UByteVarOf<UByte>>?` (raw bytes, not `String`) — the
  first rung of the planned fallback ladder (plain `static int`) worked, so no escalation to
  `static inline int` or an explicit header-shim file was needed. The `iosArm64Main` /
  `iosSimulatorArm64Main` actuals now call this shim with pinned raw pointers for both
  `password` and `salt` on every target (never decoded to/from `String`).
  **Verified: `:crypto:compileKotlinIosSimulatorArm64` and `:crypto:compileKotlinIosArm64` both
  pass.** **Not yet verified: iOS runtime execution** — no iOS-simulator/device test run has
  executed the CIP-3/BIP-39 vectors against this binding; only JVM and Android have executed
  vectors so far. Confirming iOS runtime behavior is deferred to when device/simulator test
  execution is wired up, and must not be read as proven by the compile-only result above.
- **Correctness fix found during review:** the BIP-39 English wordlist file initially checked
  in (`Bip39EnglishWordlist.kt`) had transcription errors relative to the canonical
  `bitcoin/bips` `bip-0039/english.txt` source at the pinned commit (a handful of
  wrong/duplicated words). Regenerated by diffing every one of the 2048 entries against a
  fresh download of the pinned commit; confirmed an exact match. Added
  `Bip39EnglishWordlistTest` (2048 unique entries, index-consistency check) as a guard against
  future silent drift.
- Tests added in `crypto/commonTest`, all passing on `:crypto:jvmTest` and
  `:crypto:testAndroidHostTest`: known-answer tests against the cited vectors verbatim
  (`trezor/python-mnemonic` `vectors.json` entropy↔mnemonic round-trips at 12/18/24 words;
  both CIP-3 `Icarus.md` master-key vectors, with and without the `"foo"` passphrase — the
  CIP-3 vectors were independently re-fetched from the pinned commit and matched byte-for-byte
  before use), derived rule tests for every `MnemonicError` variant (each built by mutating one
  property of a cited vector, per ADR-0009 §4's allowance), and structural tests (defensive
  copies, `clear()`, non-leaking `toString()`) for both `Mnemonic` and `IcarusMasterKey`.
- Docs updated: ADR-0009 (new "Block 1.6b gate result" section); `docs/PHASE_1_PLAN.md`
  (1.6b Outcome, "Next step"); `docs/ROADMAP.md` (Current Status + Block 1.6b entry);
  `crypto/README.md` (1.6b role/scope/boundaries + "iOS PBKDF2 cinterop"); this file. All
  updated again once the iOS cinterop shim closed the compile blocker (see above).

Files changed this step:

- `gradle/libs.versions.toml`, `crypto/build.gradle.kts` (KotlinCrypto `sha2`, BouncyCastle,
  iOS cinterop wiring)
- `crypto/src/commonMain/kotlin/org/sarmidev/kardano/crypto/`: `Bip39EnglishWordlist.kt`,
  `MnemonicError.kt`, `KeyDerivationError.kt`, `Mnemonic.kt`, `IcarusMasterKey.kt`,
  `Pbkdf2HmacSha512.kt` (new)
- `crypto/src/jvmMain/.../Pbkdf2HmacSha512.jvm.kt`,
  `crypto/src/androidMain/.../Pbkdf2HmacSha512.android.kt` (new)
- `crypto/src/nativeInterop/cinterop/pbkdf2raw.def` (inline C shim),
  `crypto/src/iosArm64Main/.../Pbkdf2HmacSha512.ios.kt`,
  `crypto/src/iosSimulatorArm64Main/.../Pbkdf2HmacSha512.ios.kt` (new; both iOS compile targets
  pass — see Summary)
- `crypto/src/commonTest/kotlin/org/sarmidev/kardano/crypto/`: `Bip39EnglishWordlistTest.kt`,
  `MnemonicVectorsTest.kt`, `MnemonicRuleTest.kt`, `IcarusMasterKeyVectorsTest.kt`,
  `IcarusMasterKeyTest.kt` (new)
- `docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md`, `docs/PHASE_1_PLAN.md`,
  `docs/ROADMAP.md`, `crypto/README.md`, `docs/HANDOFF.md`

Tests run:

- `./gradlew :crypto:jvmTest` — BUILD SUCCESSFUL (36 tests, including the BIP-39/CIP-3
  vectors).
- `./gradlew :crypto:testAndroidHostTest` — BUILD SUCCESSFUL.
- `./gradlew :crypto:compileKotlinIosSimulatorArm64` — **BUILD SUCCESSFUL** (via the
  `pbkdf2raw` interop shim; see Summary and `crypto/README.md`).
- `./gradlew :crypto:compileKotlinIosArm64` — **BUILD SUCCESSFUL** (same shim, device target).

Next recommended task:

- **iOS runtime verification (future work, not yet started):** no iOS-simulator/device test
  run has executed the CIP-3/BIP-39 vectors through the `pbkdf2raw` shim — only the compile
  targets have been verified. Wiring up iOS test execution (simulator or device) and running
  the existing `commonTest` vectors against it is the remaining iOS work item for 1.6b.
  Block 1.6c (Ed25519-BIP32 + CIP-1852 derivation) has not been started in this session; its
  timing relative to the iOS runtime item is a separate decision for the next session.

### Session Summary (1.6a decision record)

Date: 2026-07-11

Summary:

- Block 1.6a (mnemonic / seed / key derivation — API, dependency, and vector-source
  decision): docs-only. Added ADR-0009
  (`docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md`) splitting Block 1.6 into four
  gated subphases (1.6a decision / 1.6b mnemonic-to-master-key / 1.6c Ed25519-BIP32 +
  CIP-1852 / 1.6d test-wallet fixture + Android checkpoint), each its own diff.
- Scheme decision: Phase 1 targets the Icarus/CIP-3 restoration path for the MVP test
  wallet only; Byron, Ledger, Trezor variants deferred. Restore-only — mnemonic generation
  and the platform CSPRNG decision are deferred out of Block 1.6. English wordlist only;
  non-conforming input is rejected, not normalized (NFKD is the identity on that domain).
  The plain BIP-39 seed function is not exposed (Cardano's Icarus path does not use it).
- Dependency verification (published-artifact inspection, the 1.5b discipline): the main
  `org.hyperledger.identus:apollo` artifact does **not** enter Block 1.6 — `javap` on
  `apollo-jvm-1.8.8.jar` plus source reads showed its mnemonic API validates wordlist
  membership only (no checksum / word-count validation; `createSeed` is the Identus path
  with default passphrase "AtalaPrism", not BIP-39 or Icarus) and its `PBKDF2SHA512.derive`
  takes a `String` salt (Icarus needs entropy-bytes salt). `dev.allain:bip32-ed25519:2.3.0`
  verified to expose exactly the needed calls (`deriveBytes` / `deriveBytesPub` /
  `fromNonextended`; typed `DerivationException`); enters in 1.6c. 1.6b uses
  cryptography-kotlin 0.6.0 PBKDF2 (ByteArray salt) + `org.kotlincrypto.hash:sha2:0.8.0`
  (checksum), with per-target PBKDF2 provider coverage and the Android API-24/25 JCA
  question marked `To verify in 1.6b` (platform-seam fallback recorded). KotlinCrypto
  publishes no PBKDF2 (group listing verified). HMAC-SHA-512 needs no direct dependency.
- Vector gate: PASS for all three families, pinned by URL + commit + license in ADR-0009
  §4 — BIP-39 → `trezor/python-mnemonic` `vectors.json` (MIT, `b57a5ad7`); CIP-3/Icarus →
  `cardano-foundation/CIPs` `CIP-0003/Icarus.md` (CC-BY-4.0, `a36e1ebc`), both master-key
  vectors copied verbatim into the ADR; Ed25519-BIP32/CIP-1852 →
  `IntersectMBO/cardano-addresses` golden `addresses_5574d91d` (Apache-2.0, `46d01319`),
  mnemonic↔filename mapping confirmed by recomputing the spec's SHA3-256 `shortHex`. The
  golden's `addrXPub0` carries the same public-key bytes as the CIP-19 `addr_vk1w0l2sr…`
  pinned in 1.5b-pre, so the 1.6d fingerprint checkpoint is corroborated by two sources.
- Also recorded: public API sketch (opaque `Mnemonic` parse result, `IcarusMasterKey`,
  `KeyDerivation` seam, `Cip1852Path`; all failable APIs return `KardanoResult`), sealed
  `MnemonicError` / `KeyDerivationError` (payloads never carry words/entropy/key bytes),
  key-material rules (no private-key byte accessor in 1.6; the only raw accessor is the
  public key bytes needed by 1.7), and the 1.6d checkpoint scope (derived public metadata
  only: path + Blake2b-224 fingerprint + typed state; no raw/hex public key display).
- Docs updated: new ADR-0009; ADR-0008 follow-up cross-reference note (Apollo matrix
  correction for 1.6); `docs/PHASE_1_PLAN.md` (1.6 split into 1.6a–1.6d with gates,
  "Next step" → 1.6b); `docs/ROADMAP.md` (Current Status + Block 1.6 entry); this
  file. No Kotlin, Gradle, dependency, or module changes; no compile probe was needed (all
  checks ran against published artifacts and pinned source tags outside the repo).

Files changed this step:

- `docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md` (new)
- `docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md`
- `docs/PHASE_1_PLAN.md`, `docs/ROADMAP.md`, `docs/HANDOFF.md`

Tests run:

- None — docs-only block; no build was run and no source/build files changed.

Next recommended task:

- **Block 1.6b** (BIP-39 / CIP-3 mnemonic-to-master-key): implement `Mnemonic.parse` +
  `IcarusMasterKey.fromMnemonic` in `:crypto` per ADR-0009 §5, first closing the
  `To verify in 1.6b` gate item (PBKDF2-SHA-512 provider coverage on all four targets,
  including Android API 24/25); tests use the Trezor and CIP-3 vectors verbatim. No
  derivation paths, no addresses, no signing, no generation.

### Session Summary (1.5a spike record)

Date: 2026-07-11

Summary:

- Block 1.5a (crypto compatibility spike): executed the throwaway spike, then recorded the
  result as a docs-only update. The spike itself added a scratch `:crypto-spike` KMP module (on
  a disposable branch `spike/1.5a-apollo-kotlin24`) depending only on the two candidate
  artifacts, with versions pinned inline (no version-catalog change). It was discarded after the
  run; no dependency was committed to the build.
- Result: **PASS.** The provisional candidate resolved and compiled on all three required targets
  under this repo's Kotlin 2.4.0 / AGP 9.0.1 (new `com.android.kotlin.multiplatform.library`
  plugin): `:crypto-spike:compileKotlinJvm`, `:crypto-spike:compileKotlinIosSimulatorArm64`
  (commonMain metadata + iosSimulatorArm64 klib), and `:crypto-spike:testAndroidHostTest`
  (`compileAndroidMain`).
- Resolved versions: `org.hyperledger.identus:apollo:1.8.8` and `dev.allain:bip32-ed25519:2.3.0`.
  Correction to the earlier plan/matrix: the `org.hyperledger.identus:secp256k1-kmp:1.8.8`
  companion was **not** required; Apollo pulls `fr.acinq.secp256k1:secp256k1-kmp:0.16.0`
  transitively, and the candidates' declared Kotlin stdlib versions (Apollo 1.9.25, secp256k1-kmp
  1.9.22, bip32-ed25519 2.2.0) all upgrade to 2.4.0 without conflict.
- Honest scope: this proves dependency resolution + Kotlin compilation/typecheck (including the
  iOS-simulator klib) only — not runtime cryptographic correctness, iOS-simulator/device
  execution, or native-binary linkage. Those, plus the concrete adoption/wiring decision, land in
  1.5b via official cited vectors.
- Docs-only update this session: ADR-0008 (new §6 spike result; Candidate 3 matrix rows updated
  from `To verify in 1.5a`; §4 provisional text; follow-up work), `docs/PHASE_1_PLAN.md` (1.5a
  Outcome + "Next step" → 1.5b), `docs/ROADMAP.md` (Current Status + Block 1.5 entry), and
  this file. No Kotlin, Gradle, dependency, or module changes remain; only Markdown changed.

Files changed this step:

- `docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md`
- `docs/PHASE_1_PLAN.md`, `docs/ROADMAP.md`, `docs/HANDOFF.md`

Tests run:

- Spike verification (on the discarded branch): `:crypto-spike:compileKotlinJvm`,
  `:crypto-spike:compileKotlinIosSimulatorArm64`, `:crypto-spike:testAndroidHostTest` — all
  BUILD SUCCESSFUL. This docs-only update changed no code and ran no build.

Next recommended task:

- **Block 1.6** (mnemonic / seed / key derivation): create/restore a test wallet and derive keys
  per CIP-1852 / CIP-3 / BIP-39, citing vectors verbatim. Per ADR-0009, the main Apollo artifact
  does not enter Block 1.6; Ed25519-BIP32 derivation (1.6c) uses the standalone
  `dev.allain:bip32-ed25519` module instead, deferred out of the hashing-only 1.5b.

### Session Summary

Date: 2026-07-11

Summary:

- Block 1.5b (crypto module + Blake2b hashing boundary): created the `:crypto` KMP module
  (Android library + JVM + iosArm64 + iosSimulatorArm64, `explicitApi()`, depends only on
  `:core`; `:core` does not depend on `:crypto`). Public API in `org.sarmidev.kardano.crypto`:
  `Hashing` (`blake2b224`/`blake2b256` → `KardanoResult<HashDigest, CryptoError>`, never throw)
  with `Hashing.default()`; `HashDigest` (regular class, private constructor, internal
  size-validating factory, defensive copies, content equality, structural `toString`,
  `SIZE_224`/`SIZE_256`); sealed backend-neutral `CryptoError` (`HashingFailed`,
  `InvalidDigestLength`). Internal adapter `Blake2bHashing` maps backend failures to
  `CryptoError` and rethrows `CancellationException` first.
- Backend correction: **Apollo 1.8.8 ships no Blake2b** — verified in the published
  `apollo-jvm-1.8.8.jar` (its `hashing` package holds only `PBKDF2SHA512`) and across Apollo
  source tags `v1.7.2`–`v1.8.7`; transitive deps expose no Blake2b either. Since ADR-0004 forbids
  handwritten crypto, the hashing-only backend is **KotlinCrypto `org.kotlincrypto.hash:blake2`
  `0.8.0`** (Apache-2.0), pinned via the version catalog. Apollo and `bip32-ed25519` were **not**
  added this block; both are reserved for 1.6 / 1.10. The backend-neutral public API is
  unchanged by this substitution.
- Tests (`crypto/commonTest`): only the pinned cited vectors, verbatim, no generated digests —
  Blake2b-224 vs the CIP-19 payment credential (read structurally via `:core` `Address.parse`),
  Blake2b-256 vs the two IntersectMBO/plutus conformance goldens; plus `HashDigest` structural
  tests. Docs updated (ADR-0008 §8 + Candidate-3 correction, `docs/PHASE_1_PLAN.md`,
  `docs/ROADMAP.md`, this file); added `crypto/README.md`.
- Verification: `./gradlew :crypto:jvmTest :crypto:testAndroidHostTest
  :crypto:compileKotlinIosSimulatorArm64 :core:jvmTest` — all BUILD SUCCESSFUL.

### Previous Session Summary

Date: 2026-07-07

Summary:

- Block 1.4 (Crypto Evaluation And Module Decision): docs-only decision block. No Kotlin,
  Gradle, dependency, or module changes; only Markdown edited.
- Added `docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md` (ADR-0008),
  `Accepted` for the module/seam/process decisions only, with an explicit "Scope of this
  Accepted status" note that it makes no final dependency-fitness claim while compatibility is
  untested.
- Decided now (Accepted): (1) `:crypto` deferred to Block 1.5 (the block that adds the first
  crypto dependency), per ADR-0002/0005; (2) seam = a `commonMain` common interface/adapter
  (`Hashing`, later `KeyDerivation`/`Signing`) returning `KardanoResult`, no throwing across
  Swift/ObjC, with `expect`/`actual` as fallback; (3) first algorithm boundary in Block 1.5 =
  Blake2b-224/256 behind `Hashing`, using official cited vectors (RFC 7693 / Cardano context),
  no invented vectors.
- Provisional: candidate selection is provisional. Hyperledger Identus Apollo +
  `dev.allain:bip32-ed25519` is the provisional lead (only evaluated candidate covering all
  targets and the full set incl. Ed25519-BIP32), gated on a Block 1.5a Kotlin-2.4.0
  compatibility spike (recent Apollo releases target Kotlin 1.9.x). Fallbacks: a multi-library
  composition (cryptography-kotlin (whyoleg) for SHA-512/HMAC/PBKDF2/standard-Ed25519 + a
  Blake2b source such as ionspin libsodium + an Ed25519-BIP32 library), then the ADR-0004 A+B
  platform seam. bloxbean cardano-client-lib rejected as a shipped dependency (JVM-only, no
  iOS/KMP); retained only as a JVM vector oracle.
- Process: Block 1.5 split into 1.5a (throwaway compatibility spike; no committed dependency)
  and 1.5b (create `:crypto`, wire the chosen dependency behind `Hashing`, add Blake2b vectors).
- Matrix facts are source-cited; unknowns marked `Unverified` / `To verify in 1.5a`; third-party
  review status uses neutral fields (`External review`, `Public review notes`) with no fitness
  claim. No banned words in new text except when quoting the policy list.
- ADR-0004 got a one-line cross-reference to ADR-0008 (matrix advanced, not replaced).
  Updated `docs/PHASE_1_PLAN.md` (Block 1.4 complete + outcome; Block 1.5 split into 1.5a/1.5b;
  Next step -> 1.5a), `docs/ROADMAP.md` (Current Status; Block 1.4 complete; Block 1.5
  split), and this file (Block 1.4 status, Open Decisions #4, next task = 1.5a).

Files changed this step:

- `docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md` (new)
- `docs/DECISIONS/0004-crypto-strategy.md` (one-line cross-reference to ADR-0008)
- `docs/PHASE_1_PLAN.md`, `docs/ROADMAP.md`, `docs/HANDOFF.md`

Tests run:

- None required (docs-only). Optional sanity build (no code changed): see verification note.

Next recommended task:

- **Block 1.5a (crypto compatibility spike)**: add the provisional candidate (Apollo +
  `bip32-ed25519`, plus `secp256k1-kmp`) on a throwaway branch and confirm resolve/compile on
  Android + JVM + iosSimulatorArm64 under Kotlin 2.4.0. Fall back per ADR-0008 §4 if it fails.
  Only after it passes does 1.5b create `:crypto` and wire the dependency behind `Hashing`.

### Previous Session Summary

Date: 2026-07-05

Summary:

- Block 1.3a (Provider Read-Only Boundary — interface + models + mock): first Gradle module
  extraction of Phase 1. Created `:provider` (KMP: Android library + JVM + iosArm64 +
  iosSimulatorArm64, `explicitApi()`), depending only on `:core`. `commonMain` adds no
  dependency; `commonTest` adds `kotlinx-coroutines-test` (pinned in the version catalog).
- Package `org.sarmidev.kardano.provider`:
  - `ChainQueryProvider` — read-only interface: `val network: Network`; suspend `getUtxos`,
    `getProtocolParameters`, `getTip`; all return `KardanoResult` and never throw (compatible
    with Swift/ObjC interop). Submit is intentionally excluded (ADR-0006 refines ADR-0005 §5;
    a future `TxSubmitProvider` lands in Block 1.11).
  - Provider-neutral ADA-only models: `Utxo` (`UtxoRef` + `Value`), `Value` (wraps `Lovelace`;
    leaves room for future multiasset without promising compatibility), `ProtocolParameters`
    (fee/build `Long` fields), `ChainTip`. Sealed `ProviderError` with a transport-agnostic
    `RemoteStatus(code)` (not `HttpStatus`), plus `Transport`, `NotFound`, `Deserialization`,
    `RateLimited`, `NetworkMismatch`, `Unknown`. No Blockfrost-specific shapes.
  - `InMemoryChainQueryProvider` — a documented sample/test double with hardcoded fake,
    test-only data (no network, no funds, no secrets, not chain fixtures). Two documented seed
    addresses (public CIP-19 testnet vectors): `SEED_ADDRESS_WITH_UTXOS` (returns fake UTxOs)
    and `SEED_ADDRESS_EMPTY` (returns an empty list). Returns `NetworkMismatch` when the
    address network differs from the bound network (default `Network.TESTNET`).
- Playground: `:shared` now depends on `:provider`; added a "Provider (mock)" section
  (address field, seed-fill buttons, "Load UTxOs (mock)", "Load protocol params (mock)")
  labeled fake/test-only. Suspend calls run via `LaunchedEffect` keyed on a request token, so
  no coroutine dependency was added to `:shared`. Pure result mapping was extracted to
  `internal` non-suspend functions (`mapUtxosResult`, `mapParamsResult`, `presentProviderError`)
  so `:shared` tests stay coroutine-free.
- Tests: `:provider` `commonTest` (`runTest`) — seeded UTxOs, empty state, `NetworkMismatch`,
  protocol params, tip. `:shared` `commonTest` — presenter mapping (success/empty/failure/
  params + all seven `ProviderError` variants).
- Docs: added ADR-0006 (`docs/DECISIONS/0006-provider-boundary-and-strategy.md`, Accepted);
  added a one-line refinement cross-reference to ADR-0005 §5; expanded `docs/PHASE_1_PLAN.md`
  Block 1.3 into 1.3a (complete) / 1.3b (deferred); updated `docs/ROADMAP.md` (status + module
  list); added `provider/README.md`; updated `shared/README.md` (Provider mock section + seed
  addresses).

Files changed this step:

- `settings.gradle.kts` (include `:provider`)
- `gradle/libs.versions.toml` (`kotlinx-coroutinesTest` library)
- `provider/build.gradle.kts` (new)
- `provider/src/commonMain/kotlin/org/sarmidev/kardano/provider/` — `ChainQueryProvider.kt`,
  `Utxo.kt`, `Value.kt`, `ProtocolParameters.kt`, `ChainTip.kt`, `ProviderError.kt`,
  `InMemoryChainQueryProvider.kt` (all new)
- `provider/src/commonTest/kotlin/org/sarmidev/kardano/provider/InMemoryChainQueryProviderTest.kt` (new)
- `provider/README.md` (new)
- `shared/build.gradle.kts` (`implementation(projects.provider)`)
- `shared/src/commonMain/kotlin/org/sarmidev/kardano/playground/PlaygroundPresenter.kt`,
  `PlaygroundScreen.kt` (provider section)
- `shared/src/commonTest/kotlin/org/sarmidev/kardano/playground/PlaygroundProviderPresenterTest.kt` (new)
- `docs/DECISIONS/0006-provider-boundary-and-strategy.md` (new),
  `docs/DECISIONS/0005-phase-1-architecture-and-scope.md` (refinement cross-ref),
  `docs/PHASE_1_PLAN.md`, `docs/ROADMAP.md`, `docs/HANDOFF.md`, `shared/README.md`

Tests run:

- `./gradlew :provider:jvmTest` (pass)
- `./gradlew :shared:jvmTest :shared:testAndroidHostTest :shared:compileKotlinIosSimulatorArm64
  :provider:testAndroidHostTest :provider:compileKotlinIosSimulatorArm64` (pass / compile)
- `./gradlew :core:jvmTest :provider:jvmTest :androidApp:assembleDebug` (pass / APK built)

Manual Android checkpoint — to be run and recorded by the owner:

1. Open the app, scroll to "Provider (mock)".
2. Tap "Seed: has UTxOs", then "Load UTxOs (mock)" → a list of fake UTxO rows
   (`txHash#index → lovelace`).
3. Tap "Seed: empty", then "Load UTxOs (mock)" → "No UTxOs" state (not an error).
4. Enter an invalid address → typed error message, no crash.
5. Tap "Load protocol params (mock)" → protocol parameter rows.

Next recommended task:

- **Block 1.3b (Blockfrost preprod provider)**: `:provider-blockfrost` with an HTTP client,
  an API-key config strategy (no secrets committed), sanitized fixtures, and error-mapping
  tests. Alternatively advance the crypto track (Blocks 1.4/1.5) in parallel. See
  `docs/DECISIONS/0006-provider-boundary-and-strategy.md`.

### Previous Session Summary

Date: 2026-07-05

Summary:

- Block 1.2 (Android SDK Playground): first Phase 1 implementation block. Added the
  `org.sarmidev.kardano.playground` package in `:shared` `commonMain`:
  - `PlaygroundPresenter` (internal object, no Compose imports): maps `Address.parse` /
    `Hex` / `Cbor` results to display models (`AddressPresentation`, `HexPresentation`,
    `CborPresentation`). `internal fun presentAddressError(error: AddressError)` is
    directly unit-testable without needing a specific input string per variant. Credential
    hashes shown as a 6-byte short hex prefix with "structural only" caption; no full
    28-byte hash by default. No protocol logic reimplemented.
  - `PlaygroundScreen` (internal `@Composable`): address parser with typed `AddressError`
    display, Hex decoder, CBOR decoder. Local `remember { mutableStateOf }` state; no
    ViewModel or navigation framework.
  - `App.kt` replaced: now a thin `MaterialTheme { PlaygroundScreen() }` wrapper; `Greeting`
    and `GreetingUtil` are unchanged and `PlaygroundScreen` shows the platform name via
    `Greeting().greet()`.
- `:core` is not modified. No new Gradle modules. No new dependencies. `:androidApp` is
  not modified.
- Tests in `shared/src/commonTest/kotlin/org/sarmidev/kardano/playground/PlaygroundPresenterTest.kt`:
  11 `AddressError` variants constructed directly (not via parsed strings), 2 cited CIP-19
  happy-path vectors (type-06 enterprise testnet and type-14 reward testnet, cited to CIP-19),
  1 invalid input test, and 1 Empty-state test. The protocol test-vector suite is not replicated
  from `:core`.
- Fix applied mid-session: a compiler warning-as-error about always-false `is` checks on a
  sealed type in the test was resolved by replacing the test with a non-redundant check.

Files changed this step:

- `shared/src/commonMain/kotlin/org/sarmidev/kardano/App.kt` (replaced)
- `shared/src/commonMain/kotlin/org/sarmidev/kardano/playground/PlaygroundPresenter.kt` (new)
- `shared/src/commonMain/kotlin/org/sarmidev/kardano/playground/PlaygroundScreen.kt` (new)
- `shared/src/commonTest/kotlin/org/sarmidev/kardano/playground/PlaygroundPresenterTest.kt` (new)
- `docs/PHASE_1_PLAN.md` (Block 1.2 status/outcome; "Next step" → Block 1.3)
- `docs/ROADMAP.md` (Current Status; Block 1.2 outcome; Block 1.3 as next)
- `docs/HANDOFF.md` (Block 1.2 status entry; this session summary; next task updated)
- `shared/README.md` (Playground role; SDK logic stays in `:core`)

Tests run:

- `./gradlew :core:jvmTest` (pass — sanity, `:core` unchanged)
- `./gradlew :shared:jvmTest` (pass — presenter tests)
- `./gradlew :shared:testAndroidHostTest` (pass)
- `./gradlew :shared:compileKotlinIosSimulatorArm64` (pass — iOS compile guard)
- `./gradlew :androidApp:assembleDebug` (pass — Android APK build)

Manual Android checkpoint — verified by owner on 2026-07-05 (emulator/device):

1. Playground opens and renders correctly.
2. `addr_test1vz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerspjrlsz` (CIP-19 type-06
   enterprise testnet) → TESTNET / ENTERPRISE / addr_test / KEY / short hash prefix with
   "structural only" caption. ✓
3. `stake_test1uqehkck0lajq8gr28t9uxnuvgcqrc6070x3k9r8048z8y5gssrtvn` (CIP-19 type-14
   reward testnet) → TESTNET / REWARD / stake_test / KEY. ✓
4. Invalid address → typed `AddressError` message, no crash. ✓
5. Hex decoder with `010203` → correct result. ✓
6. CBOR decoder with `43010203` → `CborByteString` decoded, round-trip ok. ✓
   round-trip ok. ✓

Next recommended task:

- **Block 1.3 (Provider Read-Only Boundary)**: define a minimal read-only provider
  interface, a mock/stub implementation, and the first Blockfrost preprod wiring. This is
  the likely trigger for a new Gradle module (needs an HTTP client dependency) and for a
  provider-selection ADR (candidate ADR-0006). No wallet, crypto, or tx code yet. See
  `docs/PHASE_1_PLAN.md` Block 1.3.

### Previous Session Summary

Date: 2026-07-05

Summary:

- Block 1.1 (Phase 1 Scope And Architecture Plan): planning/documentation block only. No
  wallet, crypto, provider, tx, or Android UI code. No Kotlin, Gradle, or dependency changes.
  Declared Block 1.1 complete; implementation starts at Block 1.2.
- Recorded decisions (see `docs/PHASE_1_PLAN.md` "Block 1.1 Decisions" and
  `docs/DECISIONS/0005-phase-1-architecture-and-scope.md`, ADR-0005, Accepted):
  - MVP preprod flow: create/restore test wallet, derive one address, query UTxOs, build a
    minimal ADA-only tx, sign locally, submit to preprod, show the result in Android.
  - Native assets placed out of the first MVP.
  - Android set as the primary Phase 1 validation target; iOS and JVM/Desktop stay
    compile-only in Phase 1 unless a future block explicitly revisits this.
  - Module/package strategy recorded as decision criteria only, not a committed structure:
    packages first where dependency-free and ownership is exploratory; a crypto/provider/
    network dependency is the likely Gradle-module trigger; `:core` stays dependency-free;
    `:shared` stays the sample/UI host and is not the SDK's long-term home. No module was
    created, and no home is asserted for future crypto/provider packages.
  - Provider strategy: mock/stub first, Blockfrost as the first real preprod target, minimal
    public API; concrete selection deferred to Block 1.3. MVP data scope: UTxOs, protocol
    parameters, submit endpoint.
  - Crypto decision path: kept at Block 1.4 (evaluation) / 1.5 (primitives) against ADR-0004;
    no library selected and no crypto code in this block; read-only Blocks 1.2/1.3 proceed in
    parallel.
  - "Minimal ADA transaction" defined; two prerequisites recorded as deferred to their own
    blocks: an address encoding/round-trip ADR before Block 1.7, and a CBOR tx map-ordering
    decision (RFC 8949 §4.2.1 vs RFC 7049 length-first) before Block 1.9.
  - Scope/risk boundaries restated: no mainnet, no real keys/mnemonics/funds, no handwritten
    crypto, no signing before crypto+provider+tx scope is implemented and reviewed, no
    validator weakening, no new dependencies in this block.
- `docs/ROADMAP.md`: Block 1.1 marked `Status: complete` with an Outcome; Block 1.2 set as
  the next recommended block; Phase 1 acceptance criteria and expected capabilities
  reconciled to Android-primary / ADA-only-first (native assets and additional providers
  moved to an explicit "Deferred out of the first MVP" list); "Expected modules" reworded to
  "Expected packages/modules (candidate names, not committed)".
- Android baseline build verified: `./gradlew :androidApp:assembleDebug :core:jvmTest`. This
  confirms the sample Android app and `:core` still build with no code changes; it does not
  confirm the app launches — no app-launch claim is made from this command alone.
- No banned words (`secure`, `safe`, `hardened`, `audited`, `production-ready`, `guaranteed`)
  or misleading/readiness claims introduced; "Scope / risk boundaries" wording used instead
  of "safety" in the new plan/ADR text.

Files changed this step:

- `docs/PHASE_1_PLAN.md` (new "Block 1.1 Decisions" section; Block 1.1 marked
  complete with an outcome summary; "Next step" now points to Block 1.2)
- `docs/DECISIONS/0005-phase-1-architecture-and-scope.md` (new, ADR-0005, Accepted)
- `docs/ROADMAP.md` (Current Status header; Phase 1 section — Block 1.1 outcome, Block 1.2
  marked next, acceptance criteria and expected capabilities reconciled to Android-primary)
- `docs/HANDOFF.md` (Block 1.1 status entry; this session summary; Open Decisions and
  Decisions Already Made updated; next task = Block 1.2)

Tests run:

- `./gradlew :androidApp:assembleDebug :core:jvmTest` (build verification only; confirms the
  Android baseline and `:core` still build with no code changes — does not confirm app
  launch).

Next recommended task:

- **Block 1.2 (Android SDK Playground)**: add an Android-facing playground to parse
  `addr_test` / `stake_test` addresses and exercise existing SDK behavior (Hex, Bech32, CBOR
  checks), keeping `:core` UI-free. No wallet, crypto, provider, or tx code. See
  `docs/PHASE_1_PLAN.md` Block 1.2 and `docs/ROADMAP.md` Phase 1 block sequence.

### Previous Session Summary

Date: 2026-06-30

Summary:

- Block 0.9 (Phase 0 Closure Review): review/documentation/verification block only. No new
  SDK features, no Kotlin behavior changes, no Gradle/dependency changes, no
  crypto/signing/key/mnemonic code, no validator relaxation. Declared Phase 0 complete.
- Verification (all passed / compiled, BUILD SUCCESSFUL): `./gradlew :core:jvmTest`,
  `./gradlew :core:testAndroidHostTest`, `./gradlew :core:compileTestKotlinIosSimulatorArm64`.
  iOS simulator *execution* requires macOS/Xcode and was not run (compile-only). Working tree
  is clean — no Gradle / version-catalog drift; no dynamic (`+`) versions.
- Heuristic policy scans run, every hit manually classified (scans are heuristics, not gates):
  - `ByteArray ==` in `core/src`: no matches.
  - Banned words across READMEs/docs: all hits are the banned-word lists themselves, negated/
    factual disclaimers ("Not audited.", "Not for real funds.", "pre-alpha", "experimental"),
    or the "safe to test" round-trip guidance — no new or misleading positive claims; all
    disclaimers left intact. (Pre-existing general-engineering "safe foundation" wording in
    `docs/PROJECT_BRIEF.md` was left unchanged; out of scope for this block and not a security
    claim about funds/crypto.)
  - mnemonic/private-key patterns: only policy text, non-goals, ADR-0004, out-of-scope notes,
    and the fixtures policy README — no real secrets.
  - crypto/signing in `core/src`: only `blake2b-224` mentions in `AddressCredential` KDoc,
    which explicitly state the bytes are **not** verified as a digest — no implementation.
- Confirmed: `explicitApi()` holds; public failable APIs return `KardanoResult` / sealed
  errors (`Address.parse`, the `Cbor` / `Bech32` / `CardanoBech32` / `Hex` codecs, and the
  `TxHash` / `PolicyId` / `AssetName` / `Network` factories); named parser limits and the
  strict "reject, never normalize" policy are documented and implemented; tests cite
  BIP-173/350, RFC 8949 Appendix A, and CIP-19 vectors verbatim. `Address.parse` is the only
  address constructor — no Byron/Base58 or raw-byte/hex constructor exists.
- Deferred work / open decisions carried into Phase 1 planning: final module extraction
  (`:crypto` / `:wallet` / `:tx` / `:provider`; ADR-0002/0003); concrete crypto library/binding
  selection per algorithm (ADR-0004, all candidates `Needs investigation`); Byron/Base58
  addresses + an address encoding/round-trip ADR; CBOR map ordering for Cardano tx
  serialization (RFC 8949 §4.2.1 used now; possible RFC 7049 length-first deferred).

Files changed this step:

- `docs/ROADMAP.md` (Current Status header refreshed; Block 0.9 marked complete + Outcome;
  Phase 1 planning-first note)
- `docs/HANDOFF.md` (Phase 0 complete; Block 0.9 status entry; this session summary; next
  task = Phase 1 planning)
- `docs/TESTING.md` (added the two omitted `:core` verification commands)

Tests run:

- `./gradlew :core:jvmTest` (pass), `./gradlew :core:testAndroidHostTest` (pass),
  `./gradlew :core:compileTestKotlinIosSimulatorArm64` (iOS test sources compile). iOS
  simulator execution requires macOS/Xcode and was not run.

Next recommended task:

- **Phase 1 planning, not implementation.** Plan Phase 1 scope and resolve the open Phase 0
  decisions (per-algorithm crypto library selection per ADR-0004; module extraction per
  ADR-0002/0003) before writing any wallet/tx/provider code. No standalone closure document
  was created — `docs/ROADMAP.md` and this file are the closure record.

### Previous Session Summary

Date: 2026-06-30

Summary:

- Block 0.8 (Crypto Strategy Document): documentation/ADR-only block. Added
  `docs/DECISIONS/0004-crypto-strategy.md` (ADR-0004, Accepted), establishing the
  cryptography strategy before any implementation lands.
- ADR-0004 records: (1) no handwritten crypto (restates the hard rule); (2) all future
  crypto delegated to externally maintained libraries or platform bindings selected through
  documented evaluation per algorithm — no candidate is selected in this block; (3) crypto
  isolated from the dependency-free `:core`; likely end state a separate Gradle module
  (candidate name `:crypto`, not final), consistent with ADR-0002/ADR-0003; (4) seam
  pattern (platform `expect`/`actual` or common interface / strategy seam) chosen per
  algorithm during evaluation — neither mandated in advance; (5) key-material lifecycle
  policy (defensive copies, opaque handles, best-effort memory clearing — documented with
  no guarantee about compiler/runtime/GC behavior); (6) typed-error / `KardanoResult`
  policy for failable crypto APIs; (7) test-vector policy (official vectors only, cited
  verbatim, none added in this block). Future algorithm scope documented: Ed25519,
  Ed25519-BIP32, BIP-32 derivation, CIP-1852 paths, BIP-39 / CIP-3,
  PBKDF2-HMAC-SHA-512, HMAC-SHA-512, SHA-256, SHA-512, Blake2b-224, Blake2b-256,
  platform randomness (CSPRNG), key-material lifecycle. VRF / KES and Plutus hash
  builtins (keccak-256 / sha3-256) marked out of scope. Four candidate categories
  (JVM/Android JCA provider; C library via cinterop; pure-Kotlin / KMP-native; Cardano-
  specific binding) recorded with a reusable evaluation template; all fields `Unverified`;
  all `Decision status: Needs investigation`. Target support matrix and platform-specific
  concerns (randomness sourcing, JVM best-effort clearing, iOS/Swift interop, JCA
  provider variance for Blake2b) documented. Seven open questions listed.
- Fixed `docs/SECURITY.md` principle 1: previously named BouncyCastle on JVM/Android and
  libsodium on iOS as if already selected; reworded to point to ADR-0004 with no library
  named; crypto scope row now links to ADR-0004.
- Fixed `docs/AI_WORKING_AGREEMENT.md` crypto lines (~lines 83-87): previously named the
  same concrete libraries and mandated `expect`/`actual`; reworded to reference ADR-0004
  and allow either seam pattern (expect/actual or common interface) per algorithm.
- No Kotlin, Gradle, dependency, fixture, or test changes.

Files changed this step:

- `docs/DECISIONS/0004-crypto-strategy.md` (new)
- `docs/SECURITY.md` (principle 1 reworded; crypto scope row cross-linked to ADR-0004)
- `docs/AI_WORKING_AGREEMENT.md` (crypto lines reworded; reference to ADR-0004 added)
- `docs/ROADMAP.md` (Block 0.8 status: complete; Outcome added)
- `docs/HANDOFF.md`

Tests run:

- None — documentation-only block. No Kotlin or Gradle changes.

Next recommended task:

- Block 0.9 (Phase 0 Closure Review): verify all Phase 0 docs are consistent, tests pass
  on available targets, public APIs have KDoc, security docs are up to date,
  `docs/HANDOFF.md` reflects current state, open decisions are listed, and no signing or
  wallet flow exists. Byron/Base58 address support and an address encoding/round-trip ADR
  remain separate, independently-scheduled future work.

### Previous Session Summary

Date: 2026-06-30

Summary:

- Block 0.7 (Address Parsing And Structural Validation), Step 3: extended `Address.parse` to
  the Shelley **pointer** address types (CIP-19 header types 4-5, `addr` / `addr_test`),
  adding `AddressType.POINTER`. A pointer address is a 28-byte payment credential (key for
  type 4, script for type 5) plus a chain pointer instead of an inline delegation credential,
  so its payload is variable length and uses a dedicated parse path.
- New public API: `AddressPointer` (the three coordinates `slot` / `transactionIndex` /
  `certificateIndex` as non-negative `Long`, range `0..Long.MAX_VALUE`, built only via a
  range-validated internal `of(...)` factory), a `PointerField` enum (`SLOT` /
  `TRANSACTION_INDEX` / `CERTIFICATE_INDEX`) used by the typed errors, and a new nullable
  `Address.pointer` property. Presence contract: enterprise → payment only; reward → stake
  only; base → payment + stake; pointer → payment + pointer (`stakeCredential` null). `equals`
  / `hashCode` now include `pointer`.
- Pointer decoding: three CIP-19 variable-length unsigned integers (big-endian base-128 with
  continuation-bit framing). Named constants `MAX_POINTER_FIELD_BYTES` (9, = the 63-bit
  non-negative `Long` range) and `MIN_POINTER_PAYLOAD_SIZE` (32) bound the decode; iteration is
  over the already-bounded payload (no allocation from an untrusted length). The overflow guard
  is checked **before** each 7-bit shift, so signed-`Long` wraparound is never relied on.
  Rejected (never normalized) with typed errors: `TruncatedPointer` (field runs past the
  payload), `NonCanonicalPointer` (over-long leading-zero group — stricter than the lenient
  ledger decoder, per Phase 0 parser policy), `PointerValueOutOfRange(field)` (over-byte or
  over-`Long`), `TrailingPointerBytes(consumed, actual)` (bytes after the third coordinate).
  The `addr` / `addr_test` HRP family now accepts pointer in addition to base and enterprise.
- Tests: added the CIP-19 `type-04/05` mainnet and testnet pointer vectors verbatim (cited),
  asserting `AddressType.POINTER`, the payment credential kind, `stakeCredential == null`,
  `pointer != null`, and the spec-documented coordinates `(2498243, 27, 3)`; added a pointer
  presence test, pointer equality with equal `hashCode`, and a pointer `toString` no-bytes
  test. Added labeled derived rule tests (decode → mutate → re-encode) for pointer HRP network
  mismatch, pointer under a `stake` HRP, payload too short, truncated (continuation-at-end and
  dropped-byte variants), non-canonical slot, over-limit slot, and trailing bytes. Removed the
  now-invalid `rejectsUnsupportedPointerType` test (header type 4 is now valid); the Byron
  type-8 unsupported test stays. No AI-invented vectors.
- No dependencies, no Gradle changes, no crypto/signing/keys; structural-only KDoc throughout
  (no ownership/existence/controllability/spendability/balance claims; a pointer is not checked
  against any on-chain certificate).
- Block 0.7 closure (KDoc/docs-only follow-up, no behavior change): Block 0.7 is now complete,
  defined as structural CIP-19 parsing of the Shelley Bech32 address families (base 0-3,
  pointer 4-5, enterprise 6-7, reward/stake 14-15) across mainnet/testnet via `Address.parse`.
  Rejecting non-canonical (over-long) pointer variable-length integers is accepted as a Phase 0
  parser decision. Byron/Base58 addresses and raw-byte/hex `Address` constructors are deferred
  beyond Block 0.7 (Byron is a separate Base58 + Byron-CBOR block; raw/hex constructors await an
  address encoding/round-trip ADR). KDoc on `Address` / `AddressType` / `AddressPointer` /
  `AddressError` and `docs/ROADMAP.md`, `docs/HANDOFF.md`, `core/README.md`, and the address
  fixtures README were updated to state this; `Address.parse` remains the only constructor.

Files changed this step:

- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/Address.kt`
- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/AddressType.kt`
- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/AddressPointer.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/AddressError.kt`
- `core/src/commonTest/kotlin/org/sarmidev/kardano/address/AddressTest.kt`
- `core/README.md`, `core/src/commonTest/resources/fixtures/address/README.md`,
  `docs/ROADMAP.md`, `docs/HANDOFF.md`

Tests run:

- `./gradlew :core:jvmTest` (pass), `./gradlew :core:testAndroidHostTest` (pass),
  `./gradlew :core:compileTestKotlinIosSimulatorArm64` (iOS test sources compile). iOS
  simulator execution requires macOS/Xcode and was not run.

Next recommended task:

- Block 0.8 (Crypto Strategy Document) per `docs/ROADMAP.md` — a documentation/ADR-only block
  (candidate library/binding evaluation, target support matrix, required external vectors). No
  crypto, signing, keys, mnemonics, or dependencies. Byron/Base58 address support and an address
  encoding/round-trip ADR (for any future raw-byte/hex constructors) remain separate,
  independently-scheduled future work.

### Previous Session Summary

Date: 2026-06-30

Summary:

- Block 0.7 (Address Parsing And Structural Validation), Step 2: extended `Address.parse` to
  the two-credential Shelley **base** address types (CIP-19 header types 0-3, `addr` /
  `addr_test`, fixed 57-byte payload = 1 header + 28-byte payment credential + 28-byte
  delegation/stake credential), adding `AddressType.BASE`.
- Credential API evolution: replaced the ambiguous single `Address.credential` property with
  two explicit nullable properties, `paymentCredential: AddressCredential?` and
  `stakeCredential: AddressCredential?`. Presence follows the type — enterprise → payment
  only; reward/stake → stake only; base → both. This is a breaking source-level change to the
  Step 1 API, taken deliberately (rather than keeping an ambiguous "sometimes payment,
  sometimes stake" accessor); acceptable in this pre-alpha SDK with no external consumers per
  ADR-0003. `AddressCredential` and `CredentialKind` are unchanged.
- Parser changes: the four base header types are distinguished by the two low type-nibble
  bits (named `PAYMENT_SCRIPT_BIT = 0x1`, `DELEGATION_SCRIPT_BIT = 0x2`): bit 0 selects a
  script (vs key) payment part, bit 1 selects a script (vs key) delegation part. The type
  decode now resolves `(type, paymentKind, stakeKind)`; the `addr`/`addr_test` HRP family
  accepts both base and enterprise; the length check expects `BASE_PAYLOAD_SIZE` = 57 for
  base and 29 otherwise; payment is sliced from `[1,29)`, base stake from `[29,57)`, reward
  stake from `[1,29)`. Pointer (4-5), Byron (8), reserved types, wrong lengths, and bad
  checksums/padding stay rejected with typed errors; nothing is normalized.
- `equals`/`hashCode` now include both `paymentCredential` and `stakeCredential`; all bytes
  remain defensively copied (`contentEquals`/`contentHashCode`); `toString` still renders no
  bytes; structural-only KDoc updated on `Address`, `AddressType.BASE`, and
  `AddressError.UnsupportedAddressType` (no ownership/existence/spendability/balance claims).
- Tests: added the CIP-19 `type-00/01/02/03` mainnet and testnet base vectors verbatim
  (cited) covering all four payment/stake key/script combinations; added credential-presence
  tests (enterprise payment-only, reward stake-only, base both), base equality with equal
  `hashCode`, and a labeled derived rule object that shares the payment part but differs in
  the stake part to prove the stake credential participates in equality; added labeled
  derived rule tests for wrong base length (`InvalidPayloadLength(BASE, 57, 29)`), base under
  a `stake` HRP (`HrpFamilyMismatch`), and base HRP/network mismatch. Migrated all Step 1
  enterprise/reward assertions off the removed `credential` property to
  `paymentCredential`/`stakeCredential`; removed the now-invalid `rejectsUnsupportedBaseType`
  test (type 0 is now valid). No AI-invented vectors.
- No dependencies, no Gradle changes, no crypto/signing/keys.

Files changed this step:

- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/Address.kt`
- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/AddressType.kt`
- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/AddressError.kt`
- `core/src/commonTest/kotlin/org/sarmidev/kardano/address/AddressTest.kt`
- `core/README.md`, `core/src/commonTest/resources/fixtures/address/README.md`,
  `docs/ROADMAP.md`, `docs/HANDOFF.md`

Tests run:

- `./gradlew :core:jvmTest` (pass), `./gradlew :core:testAndroidHostTest` (pass),
  `./gradlew :core:compileTestKotlinIosSimulatorArm64` (iOS test sources compile). iOS
  simulator execution requires macOS/Xcode and was not run.

Next recommended task:

- Block 0.7 Step 3: pointer addresses (CIP-19 header types 4-5) — a payment credential plus
  a variable-length chain pointer (slot / tx-index / cert-index). Then, if/when justified,
  Byron/Base58 and hex/raw-byte address constructors. No crypto, no signing, no dependencies;
  cite CIP-19 vectors.

### Earlier Session Summary

Date: 2026-06-30

Summary:

- Block 0.7 (Address Parsing And Structural Validation), Step 1: added the
  `org.sarmidev.kardano.address` package implementing structural CIP-19 parsing for the
  single-credential Shelley address types only — enterprise (`addr` / `addr_test`, header
  types 6/7) and reward/stake (`stake` / `stake_test`, header types 14/15).
- New public API: `Address` with `Address.parse(bech32): KardanoResult<Address, AddressError>`
  (never throws), `AddressType` (`ENTERPRISE`, `REWARD` only; KDoc states it is the Step 1
  subset and more CIP-19 types may follow), `AddressCredential` + `CredentialKind`
  (`KEY` / `SCRIPT`), and a sealed `AddressError`.
- Parse pipeline: `CardanoBech32.decode` → internal `Bech32.convertBits(5, 8, pad = false)`
  (rejects non-zero padding) → header byte → type/credential-kind mapping → `Network.fromId`
  → HRP↔network agreement (`addr`/`stake` ⇒ mainnet, `addr_test`/`stake_test` ⇒ testnet) →
  HRP↔family agreement (`addr*` ⇒ enterprise, `stake*` ⇒ reward) → fixed 29-byte length
  check → `AddressCredential.of(28-byte slice)`. Unsupported types (base 0-3, pointer 4-5,
  Byron 8, reserved), wrong lengths, bad checksums/padding all return typed errors; nothing
  is normalized.
- `AddressCredential` cannot be built with arbitrary bytes: private constructor + `internal`
  length-validated `of(...)` returning `KardanoResult`, used only by `Address.parse`. All
  byte arrays are copied on construction and on every accessor, use `contentEquals` /
  `contentHashCode`, and `toString` renders no bytes. Structural-only KDoc on every public
  declaration (no ownership/existence/spendability/balance claim); the network id is
  preserved and exposed.
- Why packages, not widening: `Bech32.convertBits` and `CardanoHrp.fromValue` are `internal`
  and `:core` is one module, so the new `address` package uses them directly — no `internal`
  was widened to `public`; `explicitApi()` still holds. No dependencies, no Gradle changes,
  no crypto/signing/keys.
- Tests (`core/src/commonTest/.../address/AddressTest.kt`): the CIP-19 "Test vectors"
  `type-06/07/14/15` mainnet and testnet addresses are used verbatim (cited) for valid
  parses; invalid/edge cases are labeled hand-written rule tests derived from a cited vector
  (decode → mutate one field → re-encode) for bad checksum, Bech32m, non-allowlisted HRP,
  network mismatch, family mismatch, unsupported type (base/pointer/Byron), too-long /
  too-short payload, empty payload, defensive copies, and `toString`. No AI-invented vectors.
- Deferred to later Block 0.7 steps: base addresses (types 0-3), pointer addresses
  (types 4-5), Byron/Base58, and hex/raw-byte address constructors.

Files changed this step:

- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/Address.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/AddressType.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/AddressCredential.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/address/AddressError.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/address/AddressTest.kt` (new)
- `core/README.md`, `core/src/commonTest/resources/fixtures/address/README.md`,
  `docs/ROADMAP.md`, `docs/HANDOFF.md`

Tests run:

- `./gradlew :core:jvmTest` (pass), `./gradlew :core:testAndroidHostTest` (pass),
  `./gradlew :core:compileTestKotlinIosSimulatorArm64` (iOS test sources compile). iOS
  simulator execution requires macOS/Xcode and was not run.

Next recommended task:

- Block 0.7 Step 2: base addresses (CIP-19 header types 0-3) — the two-credential composite
  (payment + delegation, 57 bytes) on top of the Step 1 parser, adding `AddressType.BASE`
  and a second credential accessor. Then pointer addresses, and Byron/Base58 only if/when
  justified. No crypto, no signing, no dependencies; cite CIP-19 vectors.

### Older Session Summary

Date: 2026-06-30

Summary:

- Block 0.6.5 (Core Package Organization): reorganized the flat `org.sarmidev.kardano`
  package in `:core` into purpose-named packages, with no behavior change, no new Gradle
  modules, and no dependencies. This is an architecture-only package move done before
  Block 0.7 so the upcoming `Address` / CIP-19 code lands in the right place.
- New layout: `org.sarmidev.kardano.primitives` (`Network`, `Lovelace`, `TxHash`,
  `PolicyId`, `AssetName`, `UtxoRef`, `UtxoRefError`, `ByteSizeError`),
  `org.sarmidev.kardano.encoding.hex` (`Hex`, `HexError`),
  `org.sarmidev.kardano.encoding.bech32` (`Bech32`, `Bech32Variant`, `Bech32Decoded`,
  `Bech32Error`, `CardanoHrp`, `CardanoBech32`, `CardanoBech32Error`), and
  `org.sarmidev.kardano.encoding.cbor` (`Cbor`, `CborValue`, `CborError`). `KardanoResult`
  and `Platform` / `getPlatform` (+ actuals) stay at the root package, so `:shared` and the
  sample apps are untouched.
- Honest API note: class/type names are unchanged, but because public declarations moved
  into subpackages, their fully qualified names and imports changed. Acceptable in this
  pre-alpha SDK with no external consumers; recorded explicitly rather than called "no
  public API change". `org.sarmidev.kardano.address` was deliberately not created or stubbed
  yet — it arrives with real code in Block 0.7.
- Why packages and not modules: Kotlin `internal` is module-scoped, so the existing
  module-internal seams (`Bech32Variant.checksumConstant`, `Bech32.convertBits`,
  `Bech32Decoded`'s `internal` constructor, `CardanoHrp.fromValue`) keep working across
  subpackages without being widened to `public`. Gradle module splits are deferred until
  code and dependency pressure justify them. See `docs/DECISIONS/0003-core-package-structure.md`.
- Files moved (with updated `package` lines and added `import org.sarmidev.kardano.KardanoResult`
  / `...encoding.hex.Hex` where needed); `Cbor.kt`'s nested-type imports were repointed to
  `org.sarmidev.kardano.encoding.cbor`. Tests were moved to mirror the new packages.

Tests run:

- `./gradlew :core:jvmTest` (pass), `./gradlew :core:testAndroidHostTest` (pass),
  `./gradlew :core:compileTestKotlinIosSimulatorArm64` (iOS test sources compile),
  `./gradlew :shared:jvmTest :shared:compileKotlinIosSimulatorArm64` (pass; `:shared` and
  sample apps build with no source changes).

Docs updated:

- `docs/DECISIONS/0003-core-package-structure.md` (new), `core/README.md` (package layout),
  `docs/ROADMAP.md` (Block 0.6.5), `docs/HANDOFF.md`.

Next recommended task:

- Block 0.7 (Address Parsing And Structural Validation): introduce the deferred `Address`
  value type and the new `org.sarmidev.kardano.address` package with structural CIP-19
  validation on top of `CardanoBech32` / `Cbor`, preserving and checking the network id.
  No crypto, no signing, no dependencies; cite CIP-19 vectors.

### Oldest Session Summary

Date: 2026-06-29

Summary:

- Completed Block 0.6 by adding definite-length CBOR arrays (major type 4) and maps (major
  type 5) to the existing primitive subset, with no other CBOR types and no dependencies.
- `CborValue` gained `CborArray` (ordered `List<CborValue>`), `CborEntry` (key/value pair),
  and `CborMap` (an ordered `List<CborEntry>`, deliberately **not** a Kotlin `Map` so the
  canonical key order is an explicit, testable property). Both containers are regular classes
  with defensive list snapshots, content-based `equals`/`hashCode`, and structural `toString`.
- Added named limits `CBOR_MAX_NESTING_DEPTH` (64) and `CBOR_MAX_COLLECTION_ELEMENTS` (65536).
  The decoder threads a depth and validates a collection's declared count (canonical prefix,
  signed-`Long` range, then the element limit) **before** reading any element, and checks the
  depth limit when a collection head is reached — no list is sized from an untrusted count.
- Map ordering/duplicate policy: decoder records each key's canonical encoded bytes (the key
  was decoded under the same canonical rules, so its bytes are canonical) and requires the
  sequence to be strictly ascending bytewise — descending ⇒ `NonCanonicalMapKeyOrder`, equal ⇒
  `DuplicateMapKey`. Comparing adjacent keys suffices. Unsupported child/key types are rejected
  by the normal child decode. The encoder is recursive with the same limits, emits canonical
  definite-length collections, and **rejects rather than sorts** non-canonical/duplicate map
  keys (made explicit in KDoc and a dedicated "no silent sorting" test), consistent with the
  SDK-wide "reject, never normalize" rule. Tags/bignums/floats/simple/null/undefined/indefinite
  remain unrepresentable in `CborValue`, so the encoder `when` stays exhaustive.
- Map ordering rule is documented as the Phase 0 ADR-0001 / RFC 8949 §4.2.1 (bytewise)
  deterministic rule and is **not** asserted as final Cardano transaction-serialization
  compatibility (Cardano historically used RFC 7049 length-first ordering); that decision is
  left to the future tx-serialization work.
- New typed errors: `MaxNestingDepthExceeded`, `CollectionTooLarge`, `NonCanonicalMapKeyOrder`,
  `DuplicateMapKey`. Removed the now-dead `ArraysNotSupportedYet` / `MapsNotSupportedYet`
  variants and broadened the KDoc of `NonCanonicalLength` / `LengthOutOfRange` to cover
  collection count prefixes (major types 4/5).
- Tests: `CborDecodeTest` / `CborEncodeTest` use the RFC 8949 Appendix A array/map vectors
  verbatim (decode, canonical encode, round-trip) plus hand-written rule tests for the
  element-count and nesting-depth limits, indefinite collections, non-canonical map order,
  duplicate keys, nested unsupported values, trailing bytes, truncation, non-canonical count
  prefix, and container copy/equality/`toString`. No AI-invented protocol vectors; no
  dependencies or Gradle changes.
- Review microfix (same substep): `CborArray.items()` / `CborMap.entries()` now copy on every
  read (`items.toList()` / `entries.toList()`), not just on construction, so a caller cannot
  cast the returned `List` to `MutableList` and mutate internal state — matching the
  copy-on-read precedent of `CborByteString.toByteArray()`. Added accessor-copy tests
  mirroring the existing construction-copy tests. Block 0.6 is closed after this fix.

Files changed this step:

- `core/src/commonMain/kotlin/org/sarmidev/kardano/CborValue.kt` (added `CborArray`, `CborEntry`, `CborMap`)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/CborError.kt` (new collection errors; removed `…NotSupportedYet`; broadened KDoc)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/Cbor.kt` (limits, depth-threaded decode, `readArray`/`readMap`, recursive encode)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/CborDecodeTest.kt`, `CborEncodeTest.kt`
- `core/README.md`, `core/src/commonTest/resources/fixtures/cbor/README.md`,
  `docs/ROADMAP.md`, `docs/HANDOFF.md`

Tests run:

- `./gradlew :core:jvmTest` (pass), `./gradlew :core:testAndroidHostTest` (pass),
  `./gradlew :core:compileTestKotlinIosSimulatorArm64` (iOS test sources compile). iOS
  simulator execution requires macOS/Xcode and was not run.

Next recommended task:

- Block 0.7 (Address Parsing And Structural Validation): introduce the deferred `Address`
  value type with structural CIP-19 validation on top of `CardanoBech32` / `Cbor`, preserving
  and checking the network id. No crypto, no signing, no dependencies; cite CIP-19 vectors.

### Earliest Session Summary

Date: 2026-06-29

Summary:

- Implemented the first step of Block 0.6 (CBOR subset): a bounded decoder/encoder in `:core`
  for the definite-length **primitive** subset of RFC 8949 only. Added three new
  `commonMain` files: `CborValue.kt` (sealed `CborValue` with `CborUnsigned`, `CborNegative`,
  `CborByteString`, `CborTextString`), `CborError.kt` (sealed `CborError`), and `Cbor.kt`
  (`object Cbor` with `decode` / `encode`).
- Design decisions: `CborUnsigned`/`CborNegative` are data classes carrying documented range
  invariants (`0..Long.MAX_VALUE` and `Long.MIN_VALUE..-1`); the encoder enforces them with
  typed errors (`UnsignedValueNegative` / `NegativeValueNonNegative`) rather than throwing,
  and the decoder only constructs in-range instances. `CborByteString` is a regular class
  (defensive copy, `contentEquals` / `contentHashCode`, structural `toString`). For a `uint64`
  argument (additional info 27), the out-of-range check is unified across major types 0 and 1:
  reject iff bit 63 is set. String size limits were set below `CBOR_MAX_INPUT_BYTES`
  (`1 shl 16` vs `1 shl 20`) so they are independently meaningful and reachable. Strict UTF-8
  uses `decodeToString` / `encodeToByteArray(throwOnInvalidSequence = true)` wrapped in an
  internal `try/catch` mapping `CharacterCodingException` to `CborError.InvalidUtf8`.
- Anti-DoS ordering per ADR-0001: total input limit, then declared length vs remaining bytes,
  then declared length vs the named string limit, then copy. No buffer is allocated from an
  untrusted declared length.
- Tests: `CborDecodeTest` and `CborEncodeTest` in `core/src/commonTest`. Positive cases use
  RFC 8949 Appendix A vectors verbatim (cited inline); malformed/non-canonical/over-limit/
  unsupported/trailing-byte cases are hand-written and commented with the rule each exercises.
  Added explicit `Long.MAX_VALUE` / `Long.MIN_VALUE` boundary tests and `uint64`-overflow
  rejection tests (reusing the real Appendix A `0x1bff...` / `0x3bff...` vectors and asserting
  SDK rejection). Arrays, maps, tags, bignums, floats/simple/null/undefined, indefinite
  lengths, reserved additional info, and trailing bytes are all asserted rejected.
- No dependencies or Gradle changes. Arrays/maps are explicitly deferred to the next 0.6
  substep.
- Review follow-up (same substep, no scope change): added a distinct
  `CborError.LengthOutOfRange(majorType)` for byte/text string length prefixes whose `uint64`
  argument has bit 63 set, so an out-of-range length is rejected as `LengthOutOfRange` rather
  than folded into `DeclaredLengthExceedsInput` with a negative declared length; integer
  overflow for major types 0 and 1 (`IntegerOutOfRange`) is unchanged. Added decode tests for
  out-of-range byte/text string lengths (`5b…` / `7b…`, hand-written) and an explicit
  `CborByteString.toString()` structural test. The primitive substep review fix is complete.

Files changed this step:

- `core/src/commonMain/kotlin/org/sarmidev/kardano/CborValue.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/CborError.kt` (new; `LengthOutOfRange` added)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/Cbor.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/CborDecodeTest.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/CborEncodeTest.kt` (new)
- `core/README.md`, `core/src/commonTest/resources/fixtures/cbor/README.md`,
  `docs/ROADMAP.md`, `docs/HANDOFF.md`

Tests run:

- `./gradlew :core:jvmTest` (pass), `./gradlew :core:testAndroidHostTest` (pass),
  `./gradlew :core:compileTestKotlinIosSimulatorArm64` (iOS test sources compile). iOS
  simulator execution requires macOS/Xcode and was not run.

Next recommended task:

- The Block 0.6 arrays/maps substep (major types 4 and 5): add `CBOR_MAX_NESTING_DEPTH` and
  `CBOR_MAX_COLLECTION_ELEMENTS`, enforce canonical map key ordering, reject duplicate keys,
  with RFC 8949 Appendix A vectors. No dependencies; no crypto or signing.

### Initial Session Summary

Date: 2026-06-29

Summary:

- Implemented the Cardano HRP allowlist wrappers step of Block 0.5, completing the block.
  Added three new `:core` source files: `CardanoHrp` (allowlist enum `ADDR` / `ADDR_TEST` /
  `STAKE` / `STAKE_TEST` with a lowercase `value` and an `internal fromValue` lookup),
  `CardanoBech32` (`object` with `encode(hrp: CardanoHrp, data5Bit): KardanoResult<String,
  CardanoBech32Error>` forcing `Bech32Variant.BECH32`, and `decode(input): KardanoResult<
  Bech32Decoded, CardanoBech32Error>`), and `CardanoBech32Error` (`Underlying` /
  `UnsupportedHrp` / `UnsupportedVariant`).
- Design decisions: the wrappers expose no variant parameter (Cardano uses Bech32, not
  Bech32m); `decode` delegates to the generic engine, then checks the HRP allowlist **first**
  and the variant **second** — so a Bech32m string with an unsupported HRP returns
  `UnsupportedHrp` (the more domain-specific error) and a Bech32m string with an allowlisted
  HRP returns `UnsupportedVariant`. `Bech32Decoded` is reused; no new carrier type. KDoc on
  every public declaration states this is HRP allowlist + Bech32 checksum/charset validation
  only, not CIP-19 structural address validation, phrased defensively ("does not prove").
- Added `CardanoBech32Test` in `core/src/commonTest`: valid strings are generated with the
  generic engine (no real addresses, no funds, no CIP-19 vectors). Covers encode/decode/
  round-trip for the four HRPs, unsupported-HRP rejection, propagated generic checksum and
  charset errors via `Underlying`, Bech32m rejection, and the HRP-before-variant check order.
- The generic engine was not modified; no dependencies or Gradle changes.

Files changed this step:

- `core/src/commonMain/kotlin/org/sarmidev/kardano/CardanoHrp.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/CardanoBech32.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/CardanoBech32Error.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/CardanoBech32Test.kt` (new)
- `core/README.md`, `docs/ROADMAP.md`, `docs/HANDOFF.md`

### First Session Summary

Date: 2026-06-29

Summary:

- Implemented the Bech32/Bech32m step of Block 0.5 Encoding Utilities: a generic, bounded
  Bech32/Bech32m codec in `:core` per ADR-0001. Added `Bech32` (`object`) with
  `encode(hrp, data, variant): KardanoResult<String, Bech32Error>` and
  `decode(input): KardanoResult<Bech32Decoded, Bech32Error>` (neither throws), a
  `Bech32Variant` enum (`BECH32` / `BECH32M`, internal checksum constants), a `Bech32Decoded`
  carrier (regular class — not `data class` — with defensive copies, `contentEquals` /
  `contentHashCode`, and a `toData5BitArray()` accessor), and a typed `Bech32Error` sealed
  interface.
- Why: ADR-0001 sequences Block 0.5 as Hex first, then Bech32/Bech32m.
- Design: the public API works at the **5-bit data layer** (each data value `0..31`), which
  is exactly what the official BIP-173/350 generic vectors validate; the 5/8-bit `convertBits`
  helper is internal. `decode` auto-detects the variant from the checksum constant, rejects
  mixed case, and validates length / separator (last `1`) / HRP (chars `33..126`, length) /
  data charset / checksum, allocating the result only after all checks. `encode` rejects data
  values outside `0..31` (`DataValueOutOfRange`) and emits canonical lowercase.
- Limits (SDK-owned, revisable, enforced before allocation with typed errors):
  `MAX_INPUT_CHARS = 1023`, `MAX_HRP_CHARS = 83`, `MAX_DATA_VALUES = 1016` (5-bit layer), and
  `MAX_DATA_BYTES = 640` (8-bit `convertBits` output only). BIP-173's 90-char cap is
  intentionally not applied (CIP-19 addresses can exceed it).
- Added `Bech32Test` in `core/src/commonTest` using the official BIP-173 and BIP-350 valid and
  invalid vectors verbatim (cited inline), plus mixed-case, HRP, separator, charset, checksum,
  cross-variant, over-limit, padding, and round-trip cases. No AI-invented vectors.

Files changed:

- `core/src/commonMain/kotlin/org/sarmidev/kardano/Bech32.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/Bech32Variant.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/Bech32Decoded.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/Bech32Error.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/Bech32Test.kt` (new)
- `core/README.md`, `core/src/commonTest/resources/fixtures/README.md`,
  `core/src/commonTest/resources/fixtures/bech32/README.md`, `docs/ROADMAP.md`,
  `docs/HANDOFF.md`

Tests run:

- `./gradlew :core:jvmTest` (pass), `./gradlew :core:testAndroidHostTest` (pass),
  `./gradlew :core:compileTestKotlinIosSimulatorArm64` (iOS test sources compile).

Docs updated:

- `core/README.md`, both fixture `README.md` files, `docs/ROADMAP.md`, `docs/HANDOFF.md`.

Decisions made:

- Public Bech32 API operates at the 5-bit data layer; `convertBits` (5/8-bit) is internal.
  This lets the official generic vectors validate the HRP/charset/checksum layer directly,
  without forcing a 5→8 conversion that those vectors are not required to satisfy.
- `Bech32Decoded` is a regular class (not `data class`) so its `ByteArray` uses
  `contentEquals` / `contentHashCode` and defensive copies.
- Added `MAX_DATA_VALUES` as a new SDK-owned 5-bit-layer limit alongside the three limit
  names ADR-0001 lists (`MAX_INPUT_CHARS`, `MAX_HRP_CHARS`, `MAX_DATA_BYTES`); `MAX_DATA_BYTES`
  now bounds only the internal `convertBits` 8-bit output.
- The "overall max length exceeded" invalid vectors are rejected via the SDK HRP-length limit
  (their HRP is 84 chars, exceeding the 83-char `MAX_HRP_CHARS`), not via BIP-173's 90-char
  overall cap, consistent with ADR-0001.
- Block 0.5 stays **in progress** (not complete) until the Cardano HRP allowlist wrappers are
  added (deferred to a follow-up / Block 0.7).

Risks or concerns:

- The numeric limit values are SDK-owned starting points (documented as revisable). They are
  chosen to accept all official vectors and keep the limits mutually consistent backstops.
- iOS simulator tests were not executed (environment can fail); only the iOS test sources
  were compiled (`compileTestKotlinIosSimulatorArm64`).

Next recommended task:

- Either add the Cardano HRP allowlist wrappers (`addr`, `addr_test`, `stake`, `stake_test`)
  on top of the generic engine, or move to Block 0.6 (CBOR subset) per ADR-0001 (RFC 8949
  Appendix A vectors). Do not add dependencies; do not implement crypto or signing.

## Prompt For Cursor Business/Product Work

Use this prompt in Cursor Ask mode when working on business or product strategy:

```text
Act as a product and business strategy advisor for Kardano SDK.

Use these files as source of truth:
- docs/PROJECT_BRIEF.md
- docs/ROADMAP.md
- docs/HANDOFF.md
- docs/AI_WORKING_AGREEMENT.md
- docs/SECURITY.md
- ADR files under docs/DECISIONS/

Do not edit source code.

Focus only on:
- product positioning
- MVP scope
- roadmap
- adoption strategy
- Cardano ecosystem fit
- grants and funding
- documentation strategy
- developer experience

If you recommend changes, explain why and list the exact docs that should be updated.
```

## Prompt For Cursor Technical Planning

Use this prompt before implementation tasks:

```text
Act as a senior Kotlin Multiplatform engineer and security-conscious SDK maintainer.

Read:
- docs/PROJECT_BRIEF.md
- docs/ROADMAP.md
- docs/HANDOFF.md
- docs/AI_WORKING_AGREEMENT.md
- docs/SECURITY.md
- ADR files under docs/DECISIONS/

Do not edit files yet.

Plan the next small implementation task.

Return:
- objective
- files likely affected
- tests required
- docs required
- risks
- exact acceptance criteria
- whether this is appropriate for Agent mode
```

## Prompt For Updating This Handoff

Use this at the end of a Cursor session:

```text
Update docs/HANDOFF.md with the latest session state.

Include:
- what changed
- why it changed
- files touched
- tests run
- docs updated
- decisions made
- current risks
- next recommended task

Do not modify source code.
```

