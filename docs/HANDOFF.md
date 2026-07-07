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

- Phase 1 - MVP Transaction Flow (Blocks 1.1, 1.2, 1.3, and 1.4 complete; Block 1.5a — a
  crypto compatibility spike — is next). Phase 0 - Core Foundation closed below for reference.

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
  Recorded in `docs/PHASE_1_PLAN.md` ("Decisiones del Bloque 1.1") and
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

Next recommended task: **Block 1.5a (crypto compatibility spike)** — on a throwaway branch, add
the provisional candidate (Apollo + `bip32-ed25519`, plus companions like `secp256k1-kmp`) and
confirm it resolves and compiles on Android + JVM + iosSimulatorArm64 under Kotlin 2.4.0. If it
fails, fall back per ADR-0008 §4 and re-run 1.5a. Only after 1.5a passes does Block 1.5b create
`:crypto`, wire the chosen dependency behind `Hashing`, and add official Blake2b vectors. No
dependency is committed to the build before 1.5a passes. See ADR-0008,
`docs/PHASE_1_PLAN.md` Block 1.5, and `docs/ROADMAP.md`.

Current modules:

- `:core` (UI-free SDK core seed)
- `:provider` (read-only chain query boundary + in-memory mock; added in Block 1.3a; depends
  only on `:core`, no third-party `commonMain` dependency)
- `:provider-blockfrost` (Blockfrost preprod provider: Ktor + kotlinx-serialization; added in
  Block 1.3b; depends on `:provider` + `:core`; the only module with an HTTP dependency)
- `:shared` (sample/UI host; builds the iOS `Shared` framework; depends on `:core`,
  `:provider`, and `:provider-blockfrost`)
- `:androidApp`, `:desktopApp`, and `iosApp` (Xcode entry point)

`:provider` was created in Block 1.3a and `:provider-blockfrost` in Block 1.3b, each justified
by the ownership/dependency boundary in ADR-0005/ADR-0006/ADR-0007. Further module splits
(`:crypto`, `:wallet`, `:tx`) remain deferred to the block that introduces their dependency/ownership
pressure.

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
   See `docs/DECISIONS/0004-crypto-strategy.md` (open questions) and
   `docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md`.

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
  Siguiente paso -> 1.5a), `docs/ROADMAP.md` (Current Status; Block 1.4 complete; Block 1.5
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
- `docs/PHASE_1_PLAN.md` (Block 1.2 status/outcome; "Siguiente paso" → Block 1.3)
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
- Recorded decisions (see `docs/PHASE_1_PLAN.md` "Decisiones del Bloque 1.1" and
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

- `docs/PHASE_1_PLAN.md` (new "Decisiones del Bloque 1.1" section; Block 1.1 marked
  complete with an outcome summary; "Siguiente paso" now points to Block 1.2)
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

