# Kardano SDK - Phase 1 Plan

## Objective

Phase 1 turns the Phase 0 foundation into a first verifiable MVP flow in an
Android app. The priority is not to build everything at once, but to progress in small
blocks with checkpoints where the app can be opened to confirm that the integrated
functionality actually responds.

The final objective of Phase 1 is a preprod/testnet flow:

1. Create or restore a test wallet.
2. Derive an address.
3. Query UTxOs.
4. Build a simple ADA transaction.
5. Sign it locally.
6. Submit it to preprod.
7. See the result from the Android app.

No mainnet or real funds are used in this phase.

## Working principle

Each block must have a clear boundary:

- What is implemented.
- What is not implemented.
- What can be tested on Android.
- What tests/docs remain updated.
- What decisions remain open for the next block.

Android checkpoints are part of the plan, not an extra at the end. If a feature
cannot yet be seen on Android, it must be clear why and what it unblocks.

## Block 1.1 Decisions

Block 1.1 (planning/documentation, no code) records the following
decisions before touching wallet, crypto, provider, tx, or Android UI. See also
`docs/DECISIONS/0005-phase-1-architecture-and-scope.md` (ADR-0005).

Decisions made now:

- **MVP flow (preprod, verified on Android):** create/restore test wallet ->
  derive an address -> query UTxOs -> build a minimal ADA-only tx -> sign
  locally -> submit to preprod -> show the result. Corresponds to blocks 1.6-1.11.
- **Native assets: out of scope for the first MVP.** ADA only (payment + change). Reconsidered after
  Phase 1 closes or in Phase 2.
- **Android is the primary target of Phase 1.** iOS/Desktop are kept only in
  compile mode during Phase 1 (unless explicitly decided otherwise); their
  functional checkpoints are deferred to the close of Phase 1 (1.12) or Phase 2. This reduces the
  scope relative to the Phase 1 acceptance criteria in `docs/ROADMAP.md`, which currently ask for
  iOS and JVM/Desktop demos; that document is updated together with this block.
- **Module/package strategy: decision criteria only, no module is created in
  this block.**
  - Packages first, only where the work is dependency-free and the ownership
    boundaries are still under exploration.
  - Any implementation that introduces crypto, provider, or network dependencies is a
    likely trigger for creating a real Gradle module.
  - `:core` remains dependency-free and structural.
  - `:shared` remains the sample/UI host and must not become the definitive
    home of the SDK's crypto/wallet/tx/provider logic.
  - The actual creation of modules is deferred to the first implementation block that
    needs dependency/ownership separation (per ADR-0002/ADR-0003).
  - It is **not** claimed that the crypto/provider packages will live in `:core` or in
    `:shared`; their home is decided when the block that triggers that separation runs.
- **Provider: mock/stub first, Blockfrost as the first real preprod provider.** A
  provider interface is defined in Block 1.3 together with a mock implementation, so
  that wallet/tx work can proceed without depending on a real network; Blockfrost is
  connected afterward on preprod. Koios, Maestro, Ogmios, and Kupo are deferred (Phase 2). The provider's
  public API stays minimal to avoid blocking future design.
- **Provider data scope for the MVP:** UTxOs by address, protocol
  parameters, submit endpoint. Any other data (tx history, metadata) is
  deferred.
- **Crypto decision path:** the library/binding evaluation from ADR-0004 remains
  the real blocker for the wallet; it stays as Block 1.4 (evaluation) and 1.5
  (primitives), but the read-only blocks 1.2 and 1.3 can proceed in parallel because they do
  not require crypto. Algorithms to resolve first: Ed25519-BIP32, BIP-32/CIP-1852
  derivation, BIP-39/CIP-3, PBKDF2-HMAC-SHA-512, HMAC-SHA-512, Blake2b-224/256. The candidate matrix from
  ADR-0004 is updated in 1.4/1.5, not in this block; no library is selected here.
- **Definition of a "minimal ADA transaction":** one or more inputs selected from the
  wallet's UTxOs, one payment output to a destination `addr_test` address, one change
  output, a computed fee, and a validity interval only if it turns out to be necessary. No native assets,
  metadata, certificates, or scripts.
- **CBOR/serialization prerequisites before building transactions:** it remains
  pending to decide whether Cardano tx serialization needs the RFC 7049 map
  ordering "length-first" instead of the bytewise rule from RFC 8949 §4.2.1 used in Phase 0 (open
  item from ADR-0001); and an address encoding/roundtrip policy remains
  pending (`Address.parse` today is decode-only; generating addresses in 1.7 needs `toBech32`
  or equivalent, which requires its own ADR). Both are resolved in their own blocks
  (CBOR in 1.9, addresses before/in 1.7), not here.
- **Fee/change scope:** a direct fee calculation from the protocol
  parameters plus a simple change strategy in Block 1.9; no advanced coin
  selection.

Decisions explicitly deferred (not resolved in 1.1):

- Concrete crypto library/binding per algorithm -> Block 1.4/1.5 (updates the
  ADR-0004 matrix).
- Final Gradle module boundaries and their exact timing -> when dependency
  pressure appears (probably in 1.3/1.4).
- Address encoding/roundtrip ADR (needed for generation in 1.7) -> its own ADR
  before/in 1.7.
- CBOR map ordering for tx serialization -> tx serialization work (1.9).
- Wallet persistence model -> not improvised alongside signing; a separate decision.
- Native assets, Byron/Base58, functional iOS/Desktop flows, additional providers ->
  Phase 1 stretch or Phase 2.

Scope/risk boundaries (repeated in ADR-0005):

No mainnet; no private keys, mnemonics, or real funds anywhere; no handwritten
crypto; no transaction signing before approving the crypto + provider +
tx scope; validators are not weakened; no new dependencies are added in this block
(dependencies are only justified in a later implementation block); `:core`
remains free of UI and dependencies; `:shared` remains the sample/UI host and is not
the definitive home of the SDK's crypto/wallet/tx/provider logic.

## Proposed blocks

### 1.1 Phase 1 Scope And Architecture Plan

Status: complete.

Planning block. Does not implement crypto, wallet, provider, or transactions.

Objective:

- Define the exact MVP scope for Phase 1.
- Decide which modules are created now and which are deferred.
- Define the initial boundaries between `:core`, possible `:crypto`, `:wallet`, `:tx`,
  `:provider`, and sample apps.
- Choose the first target provider for preprod, or leave a concrete decision pending.
- Define the minimal Android screens to validate each block.
- Define which data is test-only.

Outcome:

- See the "Block 1.1 Decisions" section above and
  `docs/DECISIONS/0005-phase-1-architecture-and-scope.md` (ADR-0005, Accepted) for the
  full detail. Summary: the ADA-only MVP flow is defined (1.6-1.11); native assets are out of the
  first MVP; Android is the primary target, iOS/Desktop are compile-only in Phase 1; the
  module/package strategy stays as decision criteria (no modules created now,
  no assumption that crypto/provider live in `:core` or `:shared`); provider mock/stub first
  with Blockfrost as the first real preprod candidate; the crypto decision path delegated to
  ADR-0004 in Blocks 1.4/1.5; and the address prerequisites (encoding/roundtrip
  ADR) and CBOR (map ordering for tx) are explicitly deferred to
  their own blocks. No Kotlin, Gradle, or dependency changes in this block.

Android checkpoint:

- Verified by compilation baseline: `./gradlew :androidApp:assembleDebug :core:jvmTest`
  compiles the sample Android app and `:core` with no code changes. This confirms that the APK
  assembles, not that it was opened manually; a manual open verification is optional and,
  if performed, is recorded separately by the owner.

### 1.2 Android SDK Playground

Status: complete.

Objective:

- Have a visible place to try out the SDK throughout Phase 1.
- Parse `addr_test` / `stake_test` addresses.
- Show `network`, `AddressType`, credentials, and pointer when applicable.
- Exercise typed address errors in a comprehensible way.
- Optionally expose simple Hex, Bech32, and CBOR checks.

Outcome:

- New package `org.sarmidev.kardano.playground` in `:shared` `commonMain`:
  - `PlaygroundPresenter`: a pure object with no Compose imports that maps
    `KardanoResult<Address, AddressError>` to labeled rows (network, type, hrp,
    credential kind, a short 6-byte hash with caption "structural only") or to a
    readable error message per variant. Includes `internal fun presentAddressError(error)` so
    that tests can build `AddressError` variants directly without depending
    on concrete inputs. Also exposes `presentHexDecode` and `presentCbor` (hex -> CBOR
    decode + re-encode round-trip).
  - `PlaygroundScreen`: `@Composable internal` with local state (`remember mutableStateOf`),
    no ViewModel or navigation framework. Sections: address parser with
    typed-error display, Hex decoder, CBOR decoder.
  - `App.kt` replaced to render `PlaygroundScreen()` inside `MaterialTheme`.
    `:core` is not modified; `:androidApp` is not modified; no new dependencies or Gradle
    modules; `:shared` does not replicate `:core`'s protocol vector suite; it only uses
    a minimal number of cited CIP-19 vectors to verify the presenter's wiring.
- Tests in `shared/src/commonTest`: `PlaygroundPresenterTest` covers 11
  `AddressError` variants constructed directly, 2 cited CIP-19 happy paths (`type-06`
  enterprise testnet and `type-14` reward testnet), 1 simple invalid input, and 1 test of the
  Empty state. `:core`'s protocol vector suite is not replicated.
- Verification: `./gradlew :core:jvmTest`, `:shared:jvmTest`, `:shared:testAndroidHostTest`,
  `:shared:compileKotlinIosSimulatorArm64`, `:androidApp:assembleDebug` — all BUILD
  SUCCESSFUL.
- UI tests / Compose UI / Espresso are deferred; the manual checkpoint is the block's
  verification.

Android checkpoint (verified by the owner on 2026-07-05):

1. `./gradlew :androidApp:assembleDebug` — APK installed and app opened.
2. The Playground screen renders (title, input field, result area).
3. Pasted `addr_test1vz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerspjrlsz` -> saw
   `Network: TESTNET`, `Type: ENTERPRISE`, `HRP: addr_test`, credential kind, and short hash
   prefix with caption "structural only". ✓
4. Pasted `stake_test1uqehkck0lajq8gr28t9uxnuvgcqrc6070x3k9r8048z8y5gssrtvn` -> saw
   `Type: REWARD`, `Network: TESTNET`, stake credential kind. ✓
5. Invalid input -> readable `AddressError` message, no crash. ✓
6. Hex decoder with `010203` -> correct result. ✓
   CBOR decoder with `43010203` -> `CborByteString` decoded and round-trip ok. ✓

Only public CIP-19 vectors are used — no real funds or private data.

### 1.3 Provider Read-Only Boundary

Define and test the network query layer before creating wallets. The block is split into
1.3a (interface + models + mock, no network or secrets) and 1.3b (real Blockfrost preprod,
deferred). See `docs/DECISIONS/0006-provider-boundary-and-strategy.md` (ADR-0006, Accepted).

Objective:

- Define a provider interface for read-only queries, neutral with respect to the backend.
- Query UTxOs for an address.
- Query protocol parameters needed for future fee/build.
- Model errors with clear, neutral types (without leaking Blockfrost shapes).
- Start with a mock/stub implementation; the real Blockfrost provider is left for 1.3b.

#### 1.3a Interface + models + mock (this block)

Status: complete.

Outcome:

- New Gradle KMP module `:provider` (Android library + JVM + iosArm64 + iosSimulatorArm64,
  `explicitApi()`), which depends only on `:core`. Justified by *ownership* (the provider cannot
  live in `:core`, which is dependency-free, nor stay in `:shared`, the sample/UI
  host). `:provider` `commonMain` adds no dependencies; only `commonTest` uses
  `kotlinx-coroutines-test` (pinned in the catalog).
- Package `org.sarmidev.kardano.provider`:
  - `ChainQueryProvider`: read-only interface with `val network: Network` and `suspend` functions
    `getUtxos(Address)`, `getProtocolParameters()`, `getTip()`, all returning
    `KardanoResult` (never throwing). Submit is **not** here: ADR-0006 refines ADR-0005 §5
    by separating the read-only query from a future `TxSubmitProvider` (Block 1.11).
  - ADA-only, neutral models: `Utxo` (`:core`'s `UtxoRef` + `Value`), `Value` (wraps
    `Lovelace`, leaves room for a future multiasset without promising compatibility), `ProtocolParameters`
    (fee/build fields as `Long`), `ChainTip`. Sealed `ProviderError` (`Transport`,
    `RemoteStatus(code)` transport-agnostic — not `HttpStatus` —, `NotFound`, `Deserialization`,
    `RateLimited`, `NetworkMismatch`, `Unknown`).
  - `InMemoryChainQueryProvider`: a sample/test double with **fake / test-only** data
    (no network, no funds, no secrets, not chain fixtures). Recognizes two documented seed
    addresses (public testnet CIP-19 vectors): one with UTxOs
    (`SEED_ADDRESS_WITH_UTXOS`) and one empty (`SEED_ADDRESS_EMPTY`). Returns `NetworkMismatch`
    if the address's network does not match the provider's (`Network.TESTNET` by default;
    `TESTNET` alone does not identify preprod versus preview).
- Playground (`:shared` depends on `:provider`): new "Provider (mock)" section with an address
  field, buttons to fill in the seed addresses, "Load UTxOs (mock)" and "Load protocol
  params (mock)"; shows UTxO rows, the "no UTxOs" state, parameters, and typed errors,
  all labeled as fake/test-only. The `suspend` calls are triggered via `LaunchedEffect`
  (no new coroutines dependencies in `:shared`). The pure mapping was extracted into
  non-suspend `internal` functions (`mapUtxosResult`, `mapParamsResult`, `presentProviderError`) so
  they can be tested without coroutines.
- Tests: `:provider` `commonTest` (with `runTest`) covers the seed UTxOs, the empty state,
  `NetworkMismatch`, parameters, and tip. `:shared` `commonTest` covers the presenter mapping
  (success/empty/failure/params and the seven `ProviderError` variants).
- Verification: `./gradlew :core:jvmTest :provider:jvmTest :provider:testAndroidHostTest
  :provider:compileKotlinIosSimulatorArm64 :shared:jvmTest :shared:testAndroidHostTest
  :shared:compileKotlinIosSimulatorArm64 :androidApp:assembleDebug` — all BUILD SUCCESSFUL.

#### 1.3b-pre Address source-string microchange (completed)

- Minimal additive change in `:core`: `Address` exposes `public val bech32`, the exact validated
  string passed to `Address.parse`, threaded through the fixed-size and pointer paths and excluded from
  `equals`/`hashCode`/`toString`. It is the validated source representation, not a `toBech32`
  (encoding/roundtrip remains deferred to 1.7). Unblocks the Blockfrost endpoints
  indexed by address without adding an encoder. Landed separately because it touches the public API.

#### 1.3b Real Blockfrost preprod (completed)

- Module `:provider-blockfrost` (depends on `:provider` + `:core`) with `BlockfrostChainQueryProvider`,
  an HTTP Ktor client (OkHttp/CIO/Darwin engines), and kotlinx-serialization, all isolated in the
  module (`:core` and `:provider` remain HTTP-free). Internal `@Serializable` DTOs; mapping to the
  neutral models (UTxOs with pagination and ADA-only sum, parameters, tip, `404`-as-empty in
  `getUtxos`, error mapping to `Transport`/`RateLimited`/`RemoteStatus`/`NotFound`/`Deserialization`).
  `BlockfrostNetwork { PREPROD, PREVIEW, MAINNET }` maps to `Network`. API key at runtime/env/
  `local.properties` (no secrets in the repo). Tests with `MockEngine` + sanitized fixtures;
  an opt-in real integration test gated on `BLOCKFROST_PROJECT_ID` (skipped by default).
  Consumes the already-landed `Address.bech32` (1.3b-pre); does not introduce it. Submit remains in 1.11
  (ADR-0006). See ADR-0007.

Android checkpoint (1.3a, mock):

- Open the app, go to "Provider"; with the seed address that has UTxOs -> a list of UTxOs
  (`txHash#index -> lovelace`); with the empty seed address -> "no UTxOs" state; invalid
  address -> typed error without crash; "Load protocol params" -> parameter rows.
  All labeled fake/test-only, no network or secrets.

Android checkpoint (1.3b, live) — to be run by the owner with their own key:

- Enable "Use live Blockfrost (preprod)", paste a preprod `project_id` and a real
  `addr_test1...` -> real UTxOs/parameters; invalid key -> typed `RemoteStatus`/`Transport` without crash;
  unused address -> empty state. The key is not persisted.

### 1.4 Crypto Evaluation And Module Decision

Status: complete. Decision/evaluation block (docs only), based on ADR-0004. See
`docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md` (ADR-0008).

Objective:

- Evaluate concrete libraries/bindings for the algorithms Phase 1 needs.
- Decide whether to create `:crypto` now or start with an isolated package.
- Record decisions in ADR-0004 or a new ADR if needed.
- Do not implement the full wallet in this block.

Outcome:

- Added ADR-0008 (`Accepted` only for the module/seam/process decisions; without claiming
  final fitness for any dependency while compatibility remains untested). No Kotlin,
  Gradle, dependency, or module changes in this block; docs only.
- **Decided now:** (1) `:crypto` is deferred to Block 1.5 (the block that adds the first
  crypto dependency), consistent with ADR-0002/0005; (2) the seam is a common
  interface/adapter in `commonMain` (`Hashing`, later `KeyDerivation` / `Signing`) that returns
  `KardanoResult` and does not throw across Swift/ObjC, with `expect`/`actual` only as a fallback;
  (3) the first algorithmic boundary in 1.5 is Blake2b-224/256 behind `Hashing`, with cited
  official vectors (RFC 7693 / Cardano context) — no invented vectors.
- **Provisional:** the dependency selection is provisional. Hyperledger Identus Apollo +
  `bip32-ed25519` is the provisional lead (the only evaluated candidate that covers all targets
  and the full set including Ed25519-BIP32), but its compatibility with Kotlin 2.4.0 is
  untested. A candidate matrix with facts cited by source and unknowns marked
  `Unverified` / `To verify in 1.5a`; third-party review status uses neutral fields
  (`External review`, `Public review notes`), with no fitness claim.
- **Rejected as a shipped dependency:** bloxbean cardano-client-lib (JVM/Java, no iOS/KMP);
  retained only as a JVM vector oracle.

Android checkpoint:

- Keep the app compiling. This block unblocks the following ones, even without a
  new functional screen.

### 1.5 Crypto Primitives Needed For Wallet

Implement only the primitives needed for the wallet MVP, following ADR-0004 and the
decisions in ADR-0008. It is split so as not to commit to a dependency without testing it first.

#### 1.5a Compatibility spike (before committing to any dependency)

- On a disposable branch, add the provisional candidate (Apollo + `bip32-ed25519`, and its
  transitive companions, e.g. `secp256k1-kmp`) to a scratch module.
- Confirm it resolves and compiles on Android + JVM + iosSimulatorArm64 under the repo's
  Kotlin version (currently `2.4.0`).
- If it fails, discard the branch and repeat 1.5a with the next fallback (multi-library
  composition: cryptography-kotlin + a Blake2b source + an Ed25519-BIP32 library; then the
  platform seam A+B from ADR-0004).
- Record the result (candidate, targets, versions) in ADR-0008 or a short follow-up
  note. No dependency is committed to the build before 1.5a passes.

Outcome (2026-07-11): **PASS.** On a disposable branch (`spike/1.5a-apollo-kotlin24`, already
discarded) with a scratch module `:crypto-spike` that depended only on the two candidate
artifacts, the candidate **resolved and compiled** on all three targets under Kotlin 2.4.0 / AGP 9.0.1:
`:crypto-spike:compileKotlinJvm`, `:crypto-spike:compileKotlinIosSimulatorArm64`, and
`:crypto-spike:testAndroidHostTest` (`compileAndroidMain`). Resolved versions:
`org.hyperledger.identus:apollo:1.8.8` and `dev.allain:bip32-ed25519:2.3.0`. Correction: there was no
need for `org.hyperledger.identus:secp256k1-kmp:1.8.8`; Apollo transitively pulls in
`fr.acinq.secp256k1:secp256k1-kmp:0.16.0`. This proves resolution +
compilation/typecheck (including the iOS sim klib), not cryptographic correctness or runtime
execution. The concrete adoption/wiring is decided in 1.5b. Detail in ADR-0008 §6.

#### 1.5b-pre Vector gate (docs-only, before creating `:crypto`)

Before creating `:crypto` or writing the hashing API, a blocking gate looks for
official, cited, exact vectors (input bytes + exact digest + URL/commit) for both
sizes. Outcome (2026-07-11): both sizes **PASS**.

- Blake2b-224: **PASS.** Official CIP-19 pair (CC-BY-4.0): verification key
  `addr_vk1w0l2sr2zgfm26ztc6nl9xy8ghsk5sh6ldwemlpmp9xylzy4dtf7st80zhd` (bech32-decodable
  to 32 bytes) + the 28 bytes of payment credential extractable from the full CIP-19
  address `addr1qx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgse35a3x`
  via `:core`'s `Address.parse`.
- Blake2b-256: **PASS.** Plutus conformance goldens for the unkeyed builtin
  `blake2b_256` (Apache-2.0), repo `IntersectMBO/plutus`, commit
  `5e18824e2e0e30656c81d182e0ca512b75e7e57c`, path prefix
  `plutus-conformance/test-cases/uplc/evaluation/builtin/semantics/blake2b_256/`.
  Vector 1 (`blake2b_256-empty`): input `#` (0 bytes) -> `0e5751c026e543b2e8ab2eb06099daa1d1e5df47778f7787faab45cdf12fe3a8`.
  Vector 2 (`blake2b_256-length-200`): input `2e7ea84da4bc4d7cfb463e3f2c8647057afff3fbececa1d200`
  (25 bytes) -> `91c60f99b33303c02b39ed93b713e3915a180c3747f3b31e05727618ee401624`.
  Validation: each fixture is `equalsByteString (blake2b_256 (con bytestring #INPUT)) (con bytestring #EXPECTED)`
  with `.uplc.expected` = `(con bool True)`; the builtin is applied only to the raw bytes of the
  UPLC literal (no CBOR/UPLC envelope), `#` = empty and `#2e7e…1d200` = exactly 25 bytes. The
  empty-input digest `0e5751c0…`, previously rejected for appearing only in a third-party Rust
  repo, is now confirmed verbatim in this official Intersect source.

Consequence: with both sizes fixed, the `1.5b-pre` gate passes and `1.5b` is unblocked.
`1.5b-pre` creates no module, dependency, or Kotlin/Gradle change; docs only. Detail in
ADR-0008 §7.

#### 1.5b Wire + test (unblocked; vectors already fixed in 1.5b-pre)

Status: complete.

Objective:

- Create `:crypto` and add the chosen dependency (pinned, no dynamic versions).
- Wire the first algorithmic boundary: Blake2b-224/256 behind the `Hashing` interface.
- Implement wrappers/bindings for the chosen algorithms.
- Cover them with cited official vectors (Blake2b-224 CIP-19, Blake2b-256 IntersectMBO/plutus);
  no invented vectors.
- Keep errors typed (`KardanoResult`, no throwing across Swift/ObjC).
- Avoid exposing mutable internal bytes.
- Do not sign transactions yet, if it can be kept separate.

Outcome:

- New KMP module `:crypto` (Android library + JVM + iosArm64 + iosSimulatorArm64,
  `explicitApi()`) that depends only on `:core`. `:core` does not depend on `:crypto`.
- Package `org.sarmidev.kardano.crypto`: `Hashing` (`blake2b224`/`blake2b256`, both return
  `KardanoResult<HashDigest, CryptoError>`, never throwing) with `Hashing.default()`; `HashDigest`
  (a regular class, private constructor, internal factory that validates size, defensive copies,
  content-based equality, structural `toString`, `SIZE_224`/`SIZE_256` constants); a sealed,
  backend-neutral `CryptoError` (`HashingFailed`, `InvalidDigestLength`). Internal adapter
  `Blake2bHashing`; no backend type appears in the public API.
- **Dependency correction:** while wiring it up, it was confirmed that **Apollo 1.8.8 does not include Blake2b**
  (verified in the published `apollo-jvm-1.8.8.jar` — its `hashing` package contains only
  `PBKDF2SHA512` — and in source tags `v1.7.2`–`v1.8.7`). Since ADR-0004 prohibits handwritten
  crypto, the backend for this hashing-only block is **KotlinCrypto `org.kotlincrypto.hash:blake2`
  `0.8.0`** (Apache-2.0), pinned in the catalog. Apollo is **not** added in this block, and
  neither is `bip32-ed25519`; Apollo's value (Ed25519-BIP32) is reserved for 1.6 / 1.10. The
  public API is backend-neutral, so a later block can adopt Apollo without touching this
  surface. Detail in ADR-0008 §8.
- Tests in `crypto/commonTest` using only the vectors cited in 1.5b-pre, copied verbatim without
  generating digests: Blake2b-224 against the CIP-19 payment credential (read structurally from
  the cited address via `:core`'s `Address.parse`) and Blake2b-256 against the two
  IntersectMBO/plutus conformance goldens. Structural `HashDigest` tests (defensive copy on
  construction and on read, structural `toString`, content-based equality, `InvalidDigestLength`).
- Verification: `./gradlew :crypto:jvmTest :crypto:testAndroidHostTest
  :crypto:compileKotlinIosSimulatorArm64 :core:jvmTest` — all BUILD SUCCESSFUL.

Android checkpoint:

- A diagnostics screen that runs checks against known vectors and shows the result
  without using real keys.

### 1.6 Mnemonic / Seed / Key Derivation

Implement restoration of a test wallet and key derivation. The block is
split into four sub-phases with blocking gates, each its own diff. See
`docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md` (ADR-0009). Phase 1 covers only the
Icarus/CIP-3 restoration path for the MVP test wallet; the Byron,
Ledger, and Trezor variants are deferred. Block 1.6 is restoration-only: mnemonic generation
(and the per-platform CSPRNG decision) is out of scope for this block.

#### 1.6a API, dependencies, and vector-source decision (docs only)

Status: complete.

Outcome:

- Added ADR-0009 with eight decision areas: (1) all of 1.6 lives in `:crypto` (no
  `:wallet` module; an extraction trigger is recorded for 1.7/1.8); (2) the scheme is fixed to
  Icarus/CIP-3 (PBKDF2-HMAC-SHA-512 over the **entropy**, 4096 iterations, 96 bytes, CIP-3
  bit tweaks; the plain BIP-39 seed is not exposed; English wordlist only, accepting
  lowercase ASCII input from the English wordlist; non-conforming input (non-ASCII / uppercase
  / out of the wordlist) is rejected, not normalized); (3) a dependency-per-algorithm table verified
  against published artifacts (`javap` method + source tags, as in 1.5b); (4) a vector
  gate with PASS across all three families; (5) a public API sketch (signatures only);
  (6) an error model (`MnemonicError`, `KeyDerivationError`, sealed and neutral);
  (7) key-material rules (opaque handles, no private-byte accessor, input-only mnemonics
  never echoed, best-effort `clear()`); (8) generation deferred.
- **1.5b-style correction:** Apollo's main artifact is **not used in 1.6** — its mnemonic
  API only validates wordlist membership (no checksum or word count) and its
  `PBKDF2SHA512.derive` takes a `String` salt (Icarus's salt is entropy bytes). The
  Ed25519-BIP32 value comes via the independent module `dev.allain:bip32-ed25519:2.3.0`
  (verified: `deriveBytes` / `deriveBytesPub` / `fromNonextended`). Apollo's candidacy is
  reduced to Block 1.10 (signing).
- Dependencies per sub-phase: 1.6b = `org.kotlincrypto.hash:sha2:0.8.0` (SHA-256 checksum) +
  cryptography-kotlin 0.6.0 (PBKDF2 with `ByteArray` salt; per-target coverage and the
  JCA API 26+ vs minSdk 24 topic marked `To verify in 1.6b`, with a documented platform-seam
  fallback); 1.6c = `dev.allain:bip32-ed25519:2.3.0`; 1.6d = none (only
  `:shared` -> `:crypto` wiring). HMAC-SHA-512 needs no direct dependency in 1.6.
- Vector gate (all PASS, with URL + commit + license in ADR-0009 §4): BIP-39 ->
  `trezor/python-mnemonic` `vectors.json` (MIT, commit `b57a5ad7`); CIP-3/Icarus ->
  `cardano-foundation/CIPs` `CIP-0003/Icarus.md` (CC-BY-4.0, commit `a36e1ebc`);
  Ed25519-BIP32/CIP-1852 -> Shelley goldens from `IntersectMBO/cardano-addresses`
  (`test/golden/addresses_5574d91d/golden`, Apache-2.0, commit `46d01319`; name<->mnemonic
  mapping confirmed by recomputing the spec's SHA3-256 `shortHex`). Cross-link: the golden's
  `addrXPub0` carries the same 32 public-key bytes as CIP-19's
  `addr_vk1w0l2sr…`, already fixed in 1.5b-pre.
- No Kotlin, Gradle, dependency, or module changes; docs only. No compile probe was needed
  (all checks ran against artifacts published outside the repo).

#### 1.6b BIP-39 / CIP-3 mnemonic-to-master-key

Status: implementation complete on JVM and Android with executed CIP-3/BIP-39 vectors; iOS
compile targets pass (see below), with iOS runtime vector execution still future work.

Outcome:

- Scope delivered exactly as planned: `Mnemonic.parse` (word count, English wordlist
  membership, checksum, entropy extraction) and `IcarusMasterKey.fromMnemonic` (PBKDF2-HMAC-
  SHA-512 over the entropy, 4096 iterations, 96 bytes, CIP-3 bit tweaks). No derivation paths,
  no addresses, no signing, no generation — all deferred as planned.
- **Closed the `To verify in 1.6b` PBKDF2 gate — cryptography-kotlin failed it.** Verified
  against the pinned `cryptography-kotlin` 0.6.0 source directly (not docs): its JDK-backed
  provider (used by both JVM and Android) calls JCA
  `SecretKeyFactory.getInstance("PBKDF2WithHmacSHA512")`, guaranteed only from Android API 26,
  while this repo's `minSdk = 24`. `:crypto:testAndroidHostTest` cannot detect that gap (it
  runs on the host JVM, which does have the algorithm). Per ADR-0009 §3's documented fallback,
  1.6b adopted a platform seam instead: BouncyCastle `PKCS5S2ParametersGenerator` (JVM +
  Android, does not touch `SecretKeyFactory`) and Apple CommonCrypto `CCKeyDerivationPBKDF`
  (iOS). No PBKDF2 is hand-written anywhere. Full write-up: ADR-0009 "Block 1.6b gate result".
- **iOS cinterop, resolved for the compile target:** the shipped Kotlin/Native
  `platform.CoreCrypto.CCKeyDerivationPBKDF` binding maps its `password` parameter to `String`,
  which cannot carry raw passphrase bytes. A first attempt used `noStringConversion` directly
  on `CCKeyDerivationPBKDF` (mirroring JetBrains' own shipped `CommonCrypto.def`), but its
  generated cinterop klib came out with zero declarations in this environment (confirmed with
  `klib dump-metadata`, reproduced after removing `-fmodules` to match the shipped `.def`
  exactly). **Fix:** an inline C interop shim added to `pbkdf2raw.def`'s glue block —
  `kardano_ccpbkdf2_hmac_sha512` (explicit `<stdint.h>`/`<stddef.h>`/
  `<CommonCrypto/CommonKeyDerivation.h>` includes) — that declares `password` as
  `const uint8_t *` and casts it to `const char *` only at the call boundary to
  `CCKeyDerivationPBKDF`, delegating the entire derivation to it; no PBKDF2 logic is
  implemented in the shim. Verified bindable with `klib dump-metadata` (`password` shows as a
  raw byte pointer, not `String`) before the `iosArm64Main`/`iosSimulatorArm64Main` actuals
  were updated to call it with pinned pointers. **Verified:
  `:crypto:compileKotlinIosSimulatorArm64` and `:crypto:compileKotlinIosArm64` both pass.**
  **Not yet verified: iOS runtime execution of the CIP-3/BIP-39 vectors** — no
  iOS-simulator/device test run has exercised this binding. That remains future work and does
  not, by itself, prove iOS runtime correctness.
- Tests in `crypto/commonTest`: known-answer tests against the cited vectors verbatim
  (`trezor/python-mnemonic` `vectors.json` for BIP-39 entropy round-trips across 12/18/24-word
  counts; CIP-3 `Icarus.md` vectors 1 and 2 for the master key, with and without a passphrase),
  derived rule tests for each `MnemonicError` variant (built by mutating a cited vector, one
  property at a time), and structural tests for both key-material types (defensive copies,
  `clear()`, non-leaking `toString()`).
- **Correctness fix found during review:** the BIP-39 English wordlist file initially checked
  in had several transcription errors (a few wrong/duplicated words) relative to the canonical
  `bitcoin/bips` source. It was regenerated by diffing every entry against a fresh download of
  the pinned commit; a structural test (`Bip39EnglishWordlistTest`) now asserts exactly 2048
  unique entries and index consistency as a guard against silent drift.

#### 1.6c Ed25519-BIP32 + CIP-1852 — private derivation and public-key projection both verified on JVM, real Android runtime, and iOS compile/link (1.6c-follow-up + 1.6c-follow-up-2, ADR-0010)

Status: **both private derivation and public-key projection are verified on JVM, real Android
runtime, and iOS compile/link.** `KeyDerivation.publicKey(...)`/`ExtendedPublicKey` are
golden-vector-verified on JVM and on real Android runtime (a physical device plus API 24/36
emulators), and compile/link verified on iOS (iOS runtime vector execution still future work,
as in 1.6b). Full write-up: ADR-0009 "Block 1.6c gate result" (original scope) and
[ADR-0010](DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md) (the two
follow-ups that closed the Android-derivation blocker, added public-key projection for
JVM/iOS, then closed the Android-projection sub-blocker that opened in between).

Outcome:

- Delivered (1.6c): a `KeyDerivation` seam with `derivePrivate(master, path)`, over
  `bip32-ed25519`'s `deriveBytes` (called directly from `commonMain`, no platform seam needed
  for this dependency); SDK-owned `Cip1852Path`/`Cip1852Role` value types (`account'`/`role`/
  `index`, `Long`-validated); the opaque `ExtendedPrivateKey` type. No signing; no address
  generation (that is 1.7, which also requires the encoding ADR).
- Delivered (1.6c-follow-up, ADR-0010): **swapped the derivation backend's coordinate** to
  `org.hyperledger.identus:bip32-ed25519:1.8.8` (identical wrapper API; this AAR ships the
  native `.so` the prior `dev.allain` republish omitted) and **verified private derivation on
  real Android runtime** (`:crypto:connectedAndroidDeviceTest`, not host JVM) — this resolves
  1.6c's original Android-derivation blocker. Also delivered
  `ExtendedPublicKey`/`KeyDerivation.publicKey(key)` for JVM/iOS, backed by libsodium's
  `crypto_scalarmult_ed25519_base_noclamp` over the extended private key's left 32-byte
  scalar, verified byte-for-byte against the cited `addr_xvk` goldens on JVM.
- Delivered (1.6c-follow-up-2, ADR-0010): **closed the Android public-key-projection gap**
  ADR-0010's first follow-up opened. `KeyDerivation.publicKey` now delegates on Android to
  `com.goterl:lazysodium-android:5.2.0`, whose AAR bundles a fuller libsodium `.so` exporting
  `crypto_scalarmult_ed25519_base_noclamp` on all four ABIs (Ionspin's Android build, used on
  JVM/iOS, does not export it). Verified on real Android runtime — a physical device (API 35)
  plus API 24 and 36 emulators — reproducing the cited `addr_xvk` golden and cross-checked
  against the CIP-19 payment credential (1.5b). `KeyDerivationError.
  PublicKeyProjectionUnavailable` remains declared (an API-shape guarantee, not a live path)
  but no current target returns it.
- Tests against the cardano-addresses goldens' private- and public-key values (`root_xsk`,
  `acct_xsk`, `addr_xsk`, `addr_xvk`), decoded with `:core`'s generic `Bech32.decode` plus a
  test-only 5-bit-to-8-bit helper local to `crypto/jvmTest`/`crypto/androidDeviceTest` (the
  CIP-5 HRPs are intentionally outside `CardanoBech32`'s allowlist; `:core`'s `convertBits`
  stays `internal`, not widened for this).

#### 1.6d Test-wallet fixture / Android checkpoint — delivered

- A fixture (`TestWalletFixture`, `:shared` `playground` package) built exclusively from the
  cited public vector (`test walk nut …`), labeled test-only. No real funds, no real
  mnemonics.
- Playground: `:shared` gained a project dependency on `:crypto` (no new external
  dependency). The new "Test Wallet (derivation)" section shows **only publicly derived
  metadata**: the CIP-1852 path used (`m/1852'/1815'/0'/0/0`), the Blake2b-224 fingerprint of
  the derived public key (via the existing `Hashing`, matching the CIP-19 payment credential
  fixed in 1.5b), whether it matches the cited golden vector, and the typed success/error
  state. **No** raw public key or hex is shown; nothing about private bytes, seed, or words.
  Addresses remain part of the 1.7 checkpoint.
- **1.6d's Android checkpoint is fully unblocked and delivered.** 1.6c-follow-up (ADR-0010)
  verified `KeyDerivation.derivePrivate` on real Android runtime; 1.6c-follow-up-2 (ADR-0010)
  then verified `KeyDerivation.publicKey` there too, so the fingerprint-display step needed no
  Android scope-out. 1.7 is still not started or unblocked by this: address generation has not
  run its own target-verification gate.
- Test split: `shared/commonTest`'s `PlaygroundWalletPresenterTest` covers error mapping, path
  formatting, and mnemonic-parsing failures that stop before any native call (safe under
  `:shared:testAndroidHostTest`, where `:crypto`'s native backend cannot load); the end-to-end
  fingerprint golden check lives only in `shared/jvmTest`'s
  `PlaygroundWalletDerivationDesktopTest`. Android runtime coverage for the native path stays
  `:crypto:connectedAndroidDeviceTest` (already exercises the same path/fingerprint) plus the
  manual Android Playground checkpoint below.

Android checkpoint (1.6d) — confirmed on real Android runtime (API 36 and API 24 emulators,
via `adb`-driven UI interaction: install, launch, scroll to the section, tap, screenshot):

- Tapping "Restore test wallet & derive" renders `Path: m/1852'/1815'/0'/0/0`,
  `Fingerprint (Blake2b-224): 9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e`,
  `Matches cited vector: yes` — on both runtimes. No crash, no ANR (checked via `logcat`), and
  no noticeable freeze on API 24 (the oldest supported runtime): the result rendered within
  roughly 500–750 ms of the tap.
- Invalid-mnemonic input has no dedicated UI trigger in this block (per plan: the primary flow
  has no mnemonic text field); that path is covered by `presentTestWalletWithWords` in
  `PlaygroundWalletPresenterTest` instead.

### Pre-1.7 Architecture Cleanup

Docs-and-package-only microblock, no behavior change, done before starting 1.7 code.
Recorded in [ADR-0011](DECISIONS/0011-phase-1-architecture-standards.md):

- Reorganized `:crypto`'s flat `org.sarmidev.kardano.crypto` package into
  `hashing`/`mnemonic`/`derivation` (public) plus `internal.pbkdf2`/`internal.projection`
  (the two platform seams), mirroring what ADR-0003 did for `:core` before Block 0.7.
  `:shared`'s imports (`PlaygroundPresenter`, `TestWalletFixture`, playground tests) updated
  in the same change. Verified: `:crypto:compileKotlinJvm`, `:crypto:jvmTest`,
  `:crypto:testAndroidHostTest`, `:shared:jvmTest`,
  `:crypto:compileKotlinIosSimulatorArm64` + `:crypto:linkDebugTestIosSimulatorArm64` all
  pass unchanged.
- Fixed Block 1.7's ownership split ahead of any 1.7 code: `:core` owns address
  assembly/encoding (and must design a minimal public factory/encoding API — the current
  `Address`/`AddressCredential` types are parse-oriented, not assumed generation-ready);
  `:crypto` may own a narrow public-key-to-credential-hash helper only if useful; `:shared`
  owns no SDK logic. No `:wallet` module at 1.7 — see the note below.
- Refreshed `.cursor/rules/kardano-sdk-guardrails.mdc` and
  `.cursor/rules/kotlin-tests-and-docs.mdc` (rules-only): the Phase 0 rule no longer claims
  crypto is docs-only, and the testing rule
  now lists the BIP-39/CIP-3/CIP-1852 vector sources and Android/iOS runtime-testing
  guidance Block 1.6 already established in practice.

**`:wallet` extraction trigger, cross-linked:** ADR-0009 §1 records the trigger as "the
first block that composes derivation with non-crypto concerns — account/address
orchestration, wallet state, or persistence." ADR-0011 §2 confirms Block 1.7 (a pure
function over already-derived keys) does not fire that trigger; it fires at **Block 1.8**
below, which is the first block holding wallet state composed with a provider query.
Re-evaluate `:wallet` there, not before.

### 1.7 Address Generation

Generate Shelley addresses from derived keys. Split into 1.7a (`:core` ADR + generation
capability) and 1.7b (`:shared` Android checkpoint), gated on the address encoding/roundtrip
ADR ADR-0005 §6 flagged as a Block 1.7 prerequisite.

Objective:

- Create the payment credential and stake credential from keys.
- Generate a testnet base address.
- Produce Bech32.
- Verify roundtrip with `Address.parse`.
- Define the address encoding/roundtrip policy if it does not already exist.

Android checkpoint:

- Generate an `addr_test` address in the app and parse it immediately, showing its
  structure.

#### 1.7a ADR-0012 + `:core` generation capability

Status: complete.

Outcome:

- Added [ADR-0012](DECISIONS/0012-address-encoding-and-roundtrip.md), resolving the ADR-0005
  §6 prerequisite: the exact `:core` public API shape, the `bech32` (untouched parse-time
  source string) vs `toBech32()` (canonical, always-derived) distinction, the plain-Bech32
  canonical encoding/round-trip contract, base-only builder scope, no new `:crypto` API, and
  the structural-only disclaimer.
- `AddressCredential`'s companion is now public; `HASH_SIZE` and the parser-only `of(...)`
  stay `internal`. Added public `keyHash(hash)` / `scriptHash(hash)` factories that
  length-check 28 bytes (`AddressError.InvalidCredentialLength`), defensive-copy, and
  delegate to `of(...)`.
- `Address.baseAddress(network, paymentCredential, stakeCredential)` builds a CIP-19 base
  address (header types 0-3) and encodes it; `Address.toBech32()` returns the canonical
  lowercase Bech32 encoding from a new private `canonicalBech32` field computed at
  construction for both the parse and generate paths. `bech32` is unchanged (still the exact
  parse-time source string; for a generated address it equals `toBech32()`, since generation
  has no separate source).
- `AddressError`'s type-level KDoc updated to state it covers parse, construction, and
  encoding failures — all structural, none an ownership/funds/ledger claim. No new variant.
- `:crypto` untouched, as ADR-0011 §2/ADR-0012 anticipated: no new API added.
- Tests: new `AddressGenerationTest.kt` (22 tests) — rebuilds every cited CIP-19 base vector
  (mainnet + testnet, types 00-03) from its own decoded credential bytes through
  `keyHash`/`scriptHash` + `baseAddress` and asserts `toBech32()` matches the cited string,
  plus a parse→generate→parse structural roundtrip, credential-length rejection, defensive
  copies, HRP/network derivation, and equals/hashCode/toString coverage. `AddressTest.kt`
  gained 20 `toBech32()` canonicalization tests (`parse(vector).toBech32() == vector`) across
  every currently parsed type (base/enterprise/reward/pointer, mainnet + testnet); all
  existing non-canonical rejection tests are unchanged. `AddressTest` total: 58 → 78 tests;
  new `AddressGenerationTest`: 22 tests.
- Verified: `:core:jvmTest`, `:core:testAndroidHostTest`,
  `:core:compileKotlinIosSimulatorArm64` all pass; `:core` stays dependency-free.

#### 1.7b `:shared` Android checkpoint

Status: complete.

Outcome:

- Extended the existing Test Wallet section in `:shared` (Block 1.6d) into a combined
  derivation + structural address-generation checkpoint, per ADR-0011 §2: `:shared` calls
  `:core`/`:crypto` APIs and displays results; it owns no protocol logic. `:crypto` was not
  touched.
- `TestWalletFixture`: replaced the single `path` with explicit `paymentPath`
  (`m/1852'/1815'/0'/0/0`, role `EXTERNAL`) and `stakePath` (`m/1852'/1815'/0'/2/0`, role
  `STAKING`). The cited golden payment fingerprint is unchanged; no golden was invented for
  the stake credential or a full generated address — those are computed at runtime and
  labelled as fixture/checkpoint output, not an external vector.
- `PlaygroundPresenter.presentTestWalletWithWords` now derives both the payment and stake
  keys from one restored master key, hashes each derived public key with
  `Hashing.default().blake2b224(...)`, builds `AddressCredential.keyHash(...)` for each, and
  calls `Address.baseAddress(Network.TESTNET, paymentCredential, stakeCredential)`. The
  generated address is immediately re-parsed with `Address.parse(address.toBech32())` for a
  structural round-trip check. Both private keys, both public keys, the master key, and the
  mnemonic are cleared in `finally`. Mnemonic words, entropy, seed, private/root key bytes,
  and raw public key bytes are never surfaced — only path strings, full credential-hash hex
  (a public CIP-19 credential, not secret key material), the generated `addr_test1...`
  string, and an "ok"/"mismatch" round-trip row.
- `PlaygroundScreen`'s section copy was renamed from "Test Wallet (derivation)" to "Test
  Wallet & Address Generation" and reworded to describe the structural address-generation
  checkpoint; the warning text stays factual (test-only fixture, no real funds, no signing,
  structural generation only).
- Tests: `PlaygroundWalletPresenterTest` (runs on every target, including
  `testAndroidHostTest`, where `:crypto`'s native backend cannot load) updated for
  `paymentPath`/`stakePath` formatting, unchanged for error-mapping and pre-native-call
  mnemonic-rejection cases. `PlaygroundWalletDerivationDesktopTest` (JVM-only, reaches native
  derivation) now asserts both path strings, the cited golden payment-credential hex, an
  `addr_test1`-prefixed generated address, that it parses back as `Network.TESTNET` /
  `AddressType.BASE`, and a positive round-trip row — never pinning the generated address
  string itself as a golden.
- Verified: `:shared:jvmTest`, `:shared:testAndroidHostTest`,
  `:shared:compileKotlinIosSimulatorArm64`, `:core:jvmTest` all pass; lints clean on every
  touched file; no banned words or mnemonic/seed/private/raw-key exposure found.

### 1.8 Wallet State Read-Only

Connect wallet + provider without building transactions yet.

Objective:

- Show the generated address.
- Query UTxOs for that address.
- Show the test ADA balance.
- Allow a manual refresh.

Android checkpoint:

- Receive ADA from a preprod faucet at the generated address and see balance/UTxOs in the app.

#### 1.8a `:wallet` module + read-only API

Status: complete.

Outcome:

- Added [ADR-0013](DECISIONS/0013-wallet-boundary-and-read-only-state.md), resolving the
  `:wallet` module/ownership/API-shape decision ADR-0011 §2 deferred to this block: creating a
  new Gradle module (not a package) because holding wallet state and composing it with a
  provider query is the exact ADR-0009 §1 extraction trigger firing for the first time.
- New module `:wallet` (`org.sarmidev.kardano.wallet`), targets mirroring `:provider`
  (`iosArm64`, `iosSimulatorArm64`, `jvm`, `androidLibrary { withHostTest }`,
  `explicitApi()`). Depends on `:core`, `:crypto`, and `:provider` only — never
  `:provider-blockfrost`; no new external `commonMain` dependency.
- `ReadOnlyWallet`: `companion.restore(words, network)` restores a mnemonic, derives the
  account-0 payment (`m/1852'/1815'/0'/0/0`) and stake (`m/1852'/1815'/0'/2/0`) keys, hashes
  each with `Hashing.default().blake2b224(...)`, and builds a base address via
  `AddressCredential.keyHash(...)` + `Address.baseAddress(...)`. `balance(provider)` queries a
  caller-supplied `ChainQueryProvider` and sums lovelace into a `WalletBalance`, rejecting
  `Long` overflow (`WalletError.BalanceOverflow`) rather than truncating. An `internal
  of(...)` test-only factory assembles a wallet around an already-built address, so
  `balance`'s tests avoid native crypto. The mnemonic, master key, and both derived
  private/public key handles are cleared in `finally`; the returned handle retains only
  `network`, `address`, `paymentPath`, and `stakePath` — no secret material.
- `WalletBalance` (`coin: Lovelace`, `utxoCount: Int`) and `WalletError` (a sealed interface
  wrapping `MnemonicError`, `KeyDerivationError`, `CryptoError`, `AddressError`, or
  `ProviderError`, plus the wallet-owned `BalanceOverflow`) are the only other new public
  types. No `WalletState`, `WalletAddress`, or `TestWallet` type was added (ADR-0013 §3).
- Confirmed and documented (ADR-0013 §7): a restored wallet's generated address is not seeded
  by `InMemoryChainQueryProvider`'s default data, so it reads as zero-balance under the
  default mock; this is correct and `defaultSeed()` was not changed to fake a funded wallet.
- Tests (15 total, all native-crypto-free except one): `ReadOnlyWalletBalanceTest` (5 —
  seeded-with-UTxOs summation, seeded-empty, unseeded, provider `NetworkMismatch` wrapping,
  overflow rejection), `WalletErrorTest` (7 — direct construction/equality for every variant),
  `ReadOnlyWalletRestoreMnemonicTest` (2 — invalid word count / word not in wordlist rejected
  before any native call). `ReadOnlyWalletRestoreDesktopTest` (1, JVM-only) restores the same
  cited `IntersectMBO/cardano-addresses` mnemonic already pinned in `:crypto`'s
  `HashingVectorsTest`/`KeyDerivationVectorsTest`, asserts both path strings, the cited golden
  payment-credential hex, an `addr_test1`-prefixed address, and a structural
  parse-back-equal round trip — no generated address string is pinned as a golden.
- Verified: `:wallet:jvmTest`, `:wallet:testAndroidHostTest`,
  `:wallet:compileKotlinIosSimulatorArm64`, `:wallet:compileKotlinIosArm64`, and `:core:jvmTest`
  (regression) all pass; `:core`/`:crypto`/`:provider` sources unchanged; lints clean on every
  touched file; no banned words or mnemonic/seed/private/raw-key exposure found.

#### 1.8b `:shared` Android checkpoint

Status: complete.

Outcome:

- Added `:wallet` as a `:shared` `commonMain` dependency (no `:provider-blockfrost` dependency
  added to `:wallet` itself). No other Gradle module changed.
- New "Wallet Balance (read-only)" section in the Playground, wired through a new
  `PlaygroundPresenter.presentWalletBalance(provider)`: restores `TestWalletFixture`'s cited
  mnemonic via `:wallet`'s `ReadOnlyWallet.restore(TestWalletFixture.words, Network.TESTNET)`
  (always testnet — the Phase 1 no-mainnet boundary is enforced by this call site, not by
  `ReadOnlyWallet.restore` itself, ADR-0013 §3), then queries whichever `ChainQueryProvider` is
  currently active (mock or live) via `wallet.balance(provider)`. `:shared` reimplements none
  of mnemonic parsing, derivation, hashing, address generation, or balance summation — all of
  it is `:wallet`'s.
- New `WalletBalancePresentation` (`Empty`/`Loading`/`Success(rows)`/`Failure(message)`,
  mirroring `ProviderUtxosPresentation`'s shape) and `PlaygroundPresenter.presentWalletError`
  map every `WalletError` variant, delegating to the existing `presentMnemonicError`/
  `presentKeyDerivationError`/`presentCryptoError`/`presentAddressError`/`presentProviderError`
  for the five wrapped variants and adding one message for `WalletError.BalanceOverflow`. A
  non-suspend, `internal` `mapWalletBalanceResult(address, result)` keeps the formatting logic
  unit-testable without native crypto, same pattern as `mapUtxosResult`/`mapParamsResult`.
- The screen shows only the generated `addr_test1...` address, UTxO count, and balance in
  lovelace (no existing lovelace→ADA formatting pattern existed anywhere in `:shared`, so none
  was invented — kept lovelace-only per the plan's fallback). A zero balance/UTxO count under
  the default mock is rendered as a normal `Success`, not a `Failure`, with explanatory copy
  that the mock has no fake UTxOs seeded for this address and that live preprod needs the
  address funded from a faucet first. Uses the same request-token + `LaunchedEffect` pattern as
  the existing Provider section's "Load UTxOs"/"Load protocol params" buttons.
- Tests: `PlaygroundWalletBalancePresenterTest` (commonTest, native-free — feeds constructed
  `WalletBalance`/`WalletError` values plus a `Address.parse`-derived address, covering the
  zero-balance-is-success case and every `WalletError` variant's message delegation).
  `PlaygroundWalletBalanceDesktopTest` (jvmTest, JVM-only — the only place
  `presentWalletBalance` and `ReadOnlyWallet.restore` are exercised end to end together, since
  `restore` reaches `:crypto`'s native backend) asserts the default in-memory mock's honest
  zero balance and that the checkpoint's own `restore` call uses `Network.TESTNET`.
- Verified: `:shared:jvmTest`, `:shared:testAndroidHostTest`,
  `:shared:compileKotlinIosSimulatorArm64`, `:wallet:jvmTest`, `:wallet:testAndroidHostTest`,
  `:androidApp:assembleDebug` all pass; lints clean on every touched file; no banned words or
  mnemonic/seed/private/raw-key exposure found; `:wallet` still depends on `:core`/`:crypto`/
  `:provider` only.

### 1.9 Transaction Builder Minimal

Build a simple unsigned ADA transaction draft. Split into 1.9a/1.9b-1/1.9b-2/1.9c
(see [ADR-0014](DECISIONS/0014-minimal-ada-transaction-builder.md)).

Objective:

- Select inputs.
- Create the destination output.
- Compute change.
- Compute the fee.
- Include minimal validity parameters if applicable.
- Generate the transaction body / CBOR needed for future signing.

Android checkpoint:

- Enter a destination address + amount, build a draft transaction, and see a
  summary before signing. (As implemented in `1.9c`: the destination and amount are a fixed,
  cited test vector rather than a free-text form, to keep this a diagnostic checkpoint; see
  `1.9c` below for what actually shipped.)

- `1.9a` ADR / decision record — **Status: complete (docs-only).** Outcome:
  [ADR-0014](DECISIONS/0014-minimal-ada-transaction-builder.md) resolves every blocking
  decision for the builder and, in particular, the CBOR map-ordering item ADR-0005 §6 deferred
  to this block. Decisions:
  - **Module (§1):** Block 1.9b creates a new Gradle module `:tx` (`org.sarmidev.kardano.tx`,
    targets mirroring `:provider`/`:wallet`), depending on **`:core` and `:provider` only** —
    not `:wallet`, `:shared`, `:provider-blockfrost`, nor `:crypto` (the builder is a pure,
    signing-free, I/O-free function). Transaction-building logic cannot live in `:core`
    (dependency-free, cannot see `:provider`), `:provider` (query boundary, not construction),
    `:wallet` (would drag `:crypto`, conflates state with construction), or `:shared`
    (barred from SDK protocol logic, ADR-0011 §3).
  - **Scope (§2):** build the **unsigned `transaction_body`** only (fields `0` inputs, `1`
    outputs, `2` fee, optional `3` ttl); emit its canonical CBOR bytes in 1.9b; **no** witness
    set, full `transaction` array, signing, or submit. The transaction id (`Blake2b-256(body)`)
    is **not computed by `:tx`, nor by anything in Block 1.9**, including the 1.9c Playground
    checkpoint (as originally sketched here) — a meaningful id requires the finalized,
    correctly-fee'd body that only exists once signing/finalization lands, so displaying one is
    deferred to Block 1.10 or whichever block introduces that first (see `1.9c` below for what
    the checkpoint actually shows). No native assets, metadata, certificates, withdrawals,
    scripts, collateral, datums, reference inputs, or minting.
  - **CBOR map ordering (§3):** Cardano uses **RFC 7049 §3.9** canonical ordering (length-first,
    then bytewise), per CIP-21, RFC 7049 §3.9, the ledger CDDL comments, and `cardano-api`'s
    canonicaliser. `:core`'s CBOR subset is **reused unchanged** for the MVP because the body
    keys `0/1/2/3` are single-byte integers, for which RFC 7049 length-first and `:core`'s
    RFC 8949 bytewise ordering are byte-identical. Recorded limitation: features with
    heterogeneous/multi-byte map keys (multiasset, withdrawals) must revisit this before
    implementation, without weakening `:core`'s Phase 0 parser policy.
  - **Input ordering (§4):** sort inputs by the ledger `(transaction_id, index)` order
    (transaction-id bytes ascending, then numeric index), reject duplicates, and encode field 0
    as a plain untagged definite-length array (no Conway tag `258`).
  - **Output form (§5):** encode outputs in the legacy/Alonzo array form `[address, coin]`
    (value = coin = uint for ADA-only), per the Conway CDDL (`transaction_output =
    legacy_transaction_output / post_alonzo_transaction_output`, interchangeable); the legacy
    array stays within `:core`'s subset and needs no inner map.
  - **Fee/size (§6):** `fee = minFeeCoefficient * txSize + minFeeConstant`, where `txSize` is
    the estimated size of the **whole** `[body, witness_set, bool, aux]` transaction (not the
    body alone) — one vkey witness per selected input (documented conservative assumption). The
    fee is an **estimate** until Block 1.10 signs and finalizes it; a bounded fixed-point loop
    resolves the fee/change/size circularity.
  - **Min-ADA/change (§7):** enforce the sourced Babbage/Conway rule
    `minADA = (160 + serializedOutputBytes) * coinsPerUtxoByte` (ledger `babbageMinUTxOValue`);
    omit zero change; reject dust change below min-UTxO (`ChangeBelowMinimum`); never fold dust
    into the fee.
  - **Errors (§8):** a `:tx`-owned sealed `TxBuildError` (`NoInputs`, `InsufficientFunds`,
    `InvalidOutputAmount`, `ChangeBelowMinimum`, `ExceedsMaxTxSize`, `FeeCalculationOverflow`,
    `Serialization`, `NetworkMismatch`, `UnsupportedFeature`); provider errors are **not** in
    it (`:tx` queries no provider).
  - **Tests (§9):** no citable minimal ADA-only body golden was found, so use structural,
    CDDL-derived, and decode/inspect tests (body key order, input-set order, output form,
    fee/change edge cases, insufficient funds, overflow, max tx size); no invented goldens; no
    signing tests.
  - No Kotlin, Gradle, dependency, or module changes in this block.
- `1.9b-1` `:tx` module + `transaction_body` serialization — **Status: complete.** Created
  the `:tx` Gradle module (`org.sarmidev.kardano.tx`, depending on `:core` and `:provider`
  only, targets mirroring `:provider`/`:wallet`) and implemented
  `TransactionBodySerializer.serialize`: an already fully specified `TransactionBodyRequest`
  (explicit inputs/outputs/fee/ttl) is ordered, validated, and encoded into the canonical
  Conway `transaction_body` via `:core`'s unchanged CBOR subset (ADR-0014 §3-5). Inputs sort
  by the ledger `(transaction_id, index)` order and reject duplicates
  (`TxBuildError.DuplicateInput`, an addition to ADR-0014 §8's illustrative sketch); outputs
  use the legacy `[address, coin]` array form; output addresses are checked against the
  request's declared network (`TxBuildError.NetworkMismatch`). Rejects an empty inputs list
  (`TxBuildError.NoInputs`, reachable here directly, not only from the future coin-selection
  builder) and an empty outputs list (`TxBuildError.NoOutputs`, a second
  implementation-discovered addition to ADR-0014 §8, per the review microfix). `TxBuildError`
  already exposes the full ADR-0014 §8 error surface plus these additions (KDoc marks which
  variants are not yet reachable). Does **not** implement largest-first coin selection or the
  fee/change fixed-point loop (ADR-0014 §6-7) — deferred to `1.9b-2` to keep this diff focused,
  per the task's explicit permission. Tests are structural/CDDL-derived (decode-and-inspect
  via `:core`'s `Cbor.decode`; no invented `transaction_body` goldens; addresses reuse
  `:core`'s cited CIP-19 vectors).
- `1.9b-2` fee/change coin-selection builder — **Status: complete.** Added
  `TransactionBuildRequest` (network, candidate `Utxo`s, payment, change address,
  `ProtocolParameters`, optional ttl) and `TransactionBuilder.build`, which delegates the
  actual body encoding to `TransactionBodySerializer.serialize` (no duplicated CBOR logic).
  Coin selection is largest-first by `Utxo.value.coin.value`, tied-broken by the same ledger
  `(transaction_id, index)` order the serializer uses (`LedgerInputOrder`, extracted so both
  agree). Fee follows ADR-0014 §6: `minFeeCoefficient * txSize + minFeeConstant`, where
  `txSize` is the wrapper header + the real encoded body size + a sized-but-unbuilt witness set
  (one vkey witness per selected input) + the validity-flag and auxiliary-data-null bytes, all
  via generic, checked-arithmetic CBOR head-size accounting (no `N < 24` shortcut). The bounded
  fixed-point loop (`MAX_FEE_ITERATIONS = 8`) can oscillate between a with-change and a
  without-change body shape as the fee estimate converges from below; on non-convergence it
  takes `maxOf` the last two fee estimates and rebuilds exactly once more with that
  conservative value, per ADR-0014 §6. Min-ADA/change follows ADR-0014 §7
  (`minADA = (160 + serializedOutputSizeInBytes) * coinsPerUtxoByte`, using the same
  `TxCborSupport.encodeOutput` the serializer encodes with): payment below min-ADA is rejected
  (`InvalidOutputAmount`), zero change is omitted, change at/above min-ADA is emitted, and dust
  change is rejected (`ChangeBelowMinimum`) rather than folded into the fee — this dust check
  is applied once to the final accepted result, not to every intermediate fee-loop attempt,
  since an intermediate attempt's change is not final. All existing `TxBuildError` variants
  sufficed (`InsufficientFunds`, `InvalidOutputAmount`, `ChangeBelowMinimum`,
  `ExceedsMaxTxSize`, `FeeCalculationOverflow`, plus pass-through `NetworkMismatch`,
  `NoInputs`, `Serialization`, `DuplicateInput`); no new variant was needed. Tests use a
  `ProtocolParameters` with `minFeeCoefficient = 0` for two scenarios that need an exact change
  amount (zero change, dust change), isolating that check from the size-dependent fee formula
  without duplicating `:core`'s CBOR byte-size accounting by hand; other tests use the real
  formula with generous headroom. No `:core`, `:provider`, Gradle, or dependency changes.
- `1.9c` `:shared` Android Playground checkpoint — **Status: complete.** Added a "Transaction
  Draft (unsigned)" section to `PlaygroundScreen`/`PlaygroundPresenter`. It restores the same
  `TestWalletFixture` mnemonic as the Wallet Balance section (`ReadOnlyWallet.restore`, always
  `Network.TESTNET`), queries whichever `ChainQueryProvider` is currently active (mock or live)
  for that wallet's candidate UTxOs and current `ProtocolParameters`, and calls `:tx`'s
  `TransactionBuilder.build` for a fixed 2 ADA payment to a reused cited CIP-19 testnet vector
  (`InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY` — not invented, not a user-editable field, to
  keep this a diagnostic checkpoint rather than a general-purpose send form) with change returned
  to the restored wallet's own address; `:shared` adds no new coin-selection, fee, or CBOR logic
  of its own. On success the screen shows selected input/output counts, the fee and any change
  in lovelace, the encoded body size, and a truncated body-CBOR hex preview, always labeled an
  unsigned draft. On failure the screen shows a message distinguishing the cause, mapped from
  `:tx`'s `TxBuildError`. **No transaction id / body hash is computed or shown** — that requires
  `:crypto` hashing over the final signed structure and is out of scope until signing lands
  (Block 1.10); the originally sketched "body hash / transaction id" display was dropped for
  that reason. Under the default `InMemoryChainQueryProvider`, the restored wallet's address has
  no fake UTxOs seeded for it, so this normally reports "no UTxOs" — the same honest-empty
  pattern as the Wallet Balance section (ADR-0013 §7), not a failure to fix. `:shared` gained an
  explicit `:tx` dependency; no `:core`, `:crypto`, `:tx`, `:wallet`, `:provider`, Android app
  wiring, or iOS project file changes were needed beyond that.

### 1.10 Transaction Signing

Sign a testnet/preprod transaction locally. Split into `1.10a` / `1.10b-pre` / `1.10b` /
`1.10c` (ADR-0015, `docs/DECISIONS/0015-transaction-signing.md`).

Objective:

- Use only test keys (the existing test-fixture / restored-wallet path).
- Sign the transaction body **hash** (`Blake2b-256(TransactionDraft.bodyCbor())`), not the raw
  body bytes.
- Produce a full signed `transaction` (witness set + full CBOR) plus the transaction id.
- Keep tests backed by official/citable extended Ed25519-BIP32 vectors when available; never
  invent signing vectors.

Scope (ADR-0015 §2): testnet/preprod only (enforced `Network.TESTNET`), the existing test
fixture/restored wallet only, ADA-only single-payment `TransactionBuilder` drafts only. No
mainnet, non-fixture wallet, native assets, scripts, metadata, or multisig. **This is not a
`:wallet`-internal API constraint — `:wallet` cannot depend on `:shared` and so cannot itself
recognize the fixture.** Block 1.10 must not introduce a general-purpose wallet signing API;
`:wallet`'s entry point takes the same explicit `(words, network)` shape `ReadOnlyWallet.restore`
already takes, plus a draft, and the fixture-only scope is enforced by the Phase 1 call
sites/checkpoint/tests passing the cited fixture words/path and `Network.TESTNET` explicitly, not
by `:wallet` verifying anything (ADR-0015 §2a). Docs/KDoc must never describe this as arbitrary or
general wallet signing.

Sub-blocks:

- `1.10a` Transaction Signing ADR — **Status: complete (docs-only).** ADR-0015 resolves the
  signing ownership/boundary (no new module: `:crypto` owns the signing primitive, `:tx` owns
  crypto-free witness/full-`transaction` assembly, `:wallet` owns orchestration through an
  explicitly-scoped, non-general-purpose entry point and gains a `:wallet → :tx` dependency,
  `:shared` displays only), the exact scope (§2) and its fixture-only enforcement boundary (§2a:
  a Phase 1 call-site/checkpoint/test policy, since `:wallet` cannot depend on `:shared`), the
  signing message (§3: sign the 32-byte `bodyHash`; the fee is signed as-is — the Block 1.9
  one-witness-per-input estimate can over-estimate for the single-key wallet, and exact
  witness-aware fee minimization is deferred), the artifact (full signed `transaction` + witness
  count + tx id; the tx id is now displayable, closing the item ADR-0014 §2 deferred here), the
  blocking backend gate (§4), the error model (§5), the test/vector policy (§6), the Playground
  checkpoint (§7), and the guardrail reconciliation (§8). No Kotlin/Gradle/dependency/source
  changes.
- `1.10b-pre` Signing backend + vector-source gate — **Status: complete. Gate result: backend
  ADOPTED and VERIFIED; Block 1.10b unblocked** (ADR-0016 §9i,
  `docs/DECISIONS/0016-transaction-signing-backend-gate.md`). Symbol-level
  inspection of the resolved artifacts confirmed **none can sign an extended key**: the pinned
  `org.hyperledger.identus:bip32-ed25519:1.8.8` native library exports only
  `derive_bytes`/`derive_bytes_pub`/`from_nonextended` (no `sign` symbol at all — the gap is in the
  shipped Rust cdylib, not just the Kotlin binding); Apollo's `KMMEdPrivateKey.sign` delegates to
  BouncyCastle standard **seed-based** RFC-8032 Ed25519; and the ionspin/lazysodium libsodium
  signing API is seed-based (`ed25519SkToSeed` confirms the `seed‖pk` layout), with no way to sign
  a pre-expanded 64-byte scalar. **The extended-key KAT is PINNED** (ADR-0016 §3): the reference
  `ed25519-bip32` crate `0.4.2` (MIT OR Apache-2.0) `xprv_sign` test vector — a 64-byte extended
  scalar signing `"Hello World"` to a fixed 64-byte signature via `XPrv::sign`/`signature_extended`
  (unambiguously extended; a plain seed-based Ed25519 vector does **not** pass), with the CIP-0100
  32-byte-body-hash vector recorded as a secondary reproduce-to-confirm example. **Provisioning
  spike (and its Android-packaging follow-up) both run — all four §7d verification legs now
  individually PASS (ADR-0016 §8):** the recommended path (a disposable `scratch-signing-backend`
  module, Gobley 0.3.7, for JVM/iOS) plus a second disposable sibling
  `scratch-signing-backend:android` module (no Gobley Gradle plugin; `cargo ndk` + the
  `gobley-uniffi-bindgen` CLI invoked directly + this SDK's `androidLibrary {}` KMP DSL, for
  Android) was built and exposes the reference crate's `XPrv::sign`/`XPub::verify` via uniffi.
  **JVM: PASS** (real Gobley/JNA bindings, KAT reproduced, symbol proof). **iOS: PASS**
  (compile/link, symbol proof on both static libs). **Android: PASS** — a real
  `connectedAndroidDeviceTest` reproduces the KAT *through the packaged Kotlin/JNA bindings* on
  both a physical device and an emulator; Gobley's own Android Gradle integration remains
  incompatible with this repo's pinned AGP 9.0.1 (upstream-confirmed, `gobley/gobley#153`) and was
  not used, but the same `gobley-uniffi-bindgen` CLI, invoked by hand instead, was. **The backend
  has now been ADOPTED (ADR-0016 §9i):** the spike is the permanent, project-owned module
  **`:crypto-signing-backend`** (crate `kardano-ed25519-bip32-signing`, `publish = false`,
  `ed25519-bip32 = "0.4.2"` pinned + `Cargo.lock`), landed as Option R1 (no Rust/Cargo/Gobley Gradle
  plugin; 8 committed native artifacts + pre-generated UniFFI bindings). Every §7d leg was **re-run
  and passes against the real module**: `jvmTest` 4/4 (macOS arm64); `connectedAndroidDeviceTest`
  4/4 on a physical device (Android 15) + 4/4 on an API-24 emulator, through the packaged bindings;
  `compileKotlinIosArm64` + `linkDebugTestIosSimulatorArm64` green; `nm`/`llvm-nm` symbol proof on
  all 8 artifacts. The disposable `scratch-signing-backend` modules are deleted. JVM native coverage
  is macOS-only by design (no CI in-repo; Linux/Windows = future work, ADR-0016 §9 R3). **Block
  1.10b (the signing API) is unblocked**, but the adoption block itself added **no** signing code,
  **no** `:crypto`→backend dependency, and no change to any other SDK module.
- `1.10b` `:crypto` `Signing` + `:tx` assembly + `:wallet` orchestration — **Status: complete.**
  Added `:crypto`'s backend-neutral `Signing`/`SigningError`/`Ed25519Bip32Signing` (sign the
  32-byte `bodyHash` with an `ExtendedPrivateKey`, delegating to the adopted
  `:crypto-signing-backend`; added the module-internal
  `extendedPrivateKeyBytesForSigning()` accessor, no public private-key byte accessor); `:tx`'s
  `VerificationKeyWitness`/`TransactionWitnessSet`/`SignedTransaction`/`TransactionAssembler`
  (witness-set/full-`transaction` CBOR assembly from supplied `(vkey, signature)` pairs, three
  new `TxBuildError` variants, still crypto-free — `:core`'s CBOR subset gained narrow
  `true`/`false`/`null` support to encode the wrapper, addendum to ADR-0001); `:wallet`'s
  `ReadOnlyWallet.signTransaction(words, network, draft)` orchestration (derive → hash → sign →
  assemble, returning `WalletSignedTransaction`; new `WalletError.Signing`/`.TransactionAssembly`;
  key material cleared in `finally`); and the split tests (backend KAT + structural CBOR +
  labeled sign/verify self-consistency; Android runtime test required). See ADR-0015 §9 result
  note for the full verification matrix (all JVM/Android-host/Android-device/iOS
  compile-and-link commands pass).
- `1.10c` `:shared` Android "Signed Transaction (not submitted)" checkpoint — **Status:
  complete, including manual Android runtime checkpoint.** Built the same unsigned draft as
  1.9c (extracted into a shared `buildTransactionDraft` helper reused by both checkpoints), signs
  it by calling `:wallet`'s `ReadOnlyWallet.signTransaction` with the cited `TestWalletFixture`
  words/path and `Network.TESTNET` explicitly (ADR-0015 §2a — `:wallet` is not fixture-aware;
  `:shared` supplies it), and displays the transaction id, witness count, a truncated
  signed-transaction CBOR preview, and an explicit "signed, not submitted — testnet-only, test
  fixture, no real funds" label. No submission (that is Block 1.11). While implementing this, a
  pre-existing compile gap surfaced: `PlaygroundPresenter.presentWalletError`/`presentTxBuildError`
  had not been updated for the `WalletError.Signing`/`WalletError.TransactionAssembly` and
  `TxBuildError.InvalidVerificationKeyLength`/`InvalidSignatureLength`/`EmptyWitnessSet` variants
  Block 1.10b added to `:wallet`/`:tx` — `:shared` did not compile without those branches; adding
  them (plus a new `presentSigningError` for `SigningError`) was the tiny compile-forced fix this
  block's guardrail allows, not a behavior change to any SDK module. All verification commands
  pass: `:shared:jvmTest`, `:shared:testAndroidHostTest`, `:shared:compileKotlinIosArm64`,
  `:shared:compileKotlinIosSimulatorArm64`. Android runtime verification was then completed
  manually by the project owner using live Blockfrost preprod: after correcting the preprod
  `project_id`, tapping "Sign transaction" showed a transaction id, witness count `1`, a
  truncated signed-CBOR preview (`288B total`), and the "signed, not submitted — testnet-only,
  test fixture, no real funds" label. No submit action was present or invoked.

Android checkpoint (manual PASS, 2026-07-13):

- Build and sign a transaction, showing the tx id and signed CBOR without submitting it yet.

### 1.11 Submit Transaction

Submit the signed transaction to preprod.

Objective:

- Implement submit via the provider.
- Handle submit errors.
- Show the tx id or a comprehensible error.
- Optionally allow simple polling or an external link.

Split into `1.11a` / `1.11b` / `1.11c` / `1.11d` / `1.11d-2` (ADR-0017,
`docs/DECISIONS/0017-transaction-submission-boundary.md`, plus the ADR-0006/0007/0014
2026-07-13 addenda for `1.11d`, and a second ADR-0006/0014 2026-07-13 addendum for `1.11d-2`):

- `1.11a` `:provider` submission boundary — **Status: complete.** Added `TxSubmitProvider`
  (`network`, `suspend fun submit(transactionCbor: ByteArray): KardanoResult<TxHash,
  SubmitError>`) as a new interface separate from `ChainQueryProvider` (submission is a single
  mutating, non-idempotent action with its own failure taxonomy, not a read); the sealed
  `SubmitError` (`SubmissionNotSupported`, `EmptyTransaction`, `Rejected`, `Transport`,
  `RemoteStatus`, `RateLimited`, `Deserialization`, `Unknown`); and `InMemoryTxSubmitProvider`,
  which never submits — every call, including with empty bytes, returns
  `SubmitError.SubmissionNotSupported`, and it performs no validation of its input since it
  never uses it. `submit` takes raw signed transaction CBOR bytes rather than a `:tx`/`:wallet`
  type because `:provider` must not depend on `:tx` (which already depends on `:provider`).
  No Blockfrost implementation and no `:shared` change in this sub-block.
- `1.11b` `:provider-blockfrost` Blockfrost submit implementation — **Status: complete.** Added
  `BlockfrostTxSubmitProvider` implementing `TxSubmitProvider`: `POST
  {config.network.baseUrl}/tx/submit`, `Content-Type: application/cbor`, `project_id` from the
  existing `configureBlockfrost` default request, and the raw (defensively copied)
  `transactionCbor` as the body. Empty input is rejected with `SubmitError.EmptyTransaction`
  before any HTTP call. A successful (`200`) response is Blockfrost's JSON string containing a
  64-hex-character transaction id; the surrounding quotes are stripped from the raw response
  text deliberately (not via JSON content negotiation) before hex-decoding into a `TxHash`, and
  a malformed/wrong-length result becomes `SubmitError.Deserialization`. Non-2xx statuses map
  to `SubmitError.Rejected` (`400`), `SubmitError.RateLimited` (`429`), or
  `SubmitError.RemoteStatus` (any other non-2xx, for example `403`/`404`/`418`/`425`/`500`),
  with `detail` parsed from Blockfrost's JSON error envelope (`message`/`error`) falling back
  to the raw body; transport exceptions map to `SubmitError.Transport`, and
  `CancellationException` is rethrown, not swallowed. No automated live-network submit test:
  submitting is a mutating, non-idempotent action that consumes real preprod test UTxOs, unlike
  the read-only provider's opt-in live test. No `:shared` change in this sub-block.
- `1.11c` `:shared` Android "Submit Transaction" Playground checkpoint — **Status:
  implementation complete; manual Android checkpoint complete after `1.11d`/`1.11d-2` follow-ups.** Added a "Submit Transaction
  (preprod)" Playground section below "Signed Transaction (not submitted)": it builds and
  signs the same fixture draft as Block 1.10c through `PlaygroundPresenter.presentSubmitTransaction`,
  then calls `TxSubmitProvider.submit(signed.signedTransaction.cbor())` directly — no new
  `:wallet` orchestration method was added (ADR-0017 "Non-goals"). Wired a new
  `activeSubmitProvider: TxSubmitProvider` alongside the existing `activeProvider:
  ChainQueryProvider`, defaulting to `InMemoryTxSubmitProvider()` and switching to
  `BlockfrostTxSubmitProvider.create(BlockfrostConfig(projectId = key))` under the same live
  toggle and `project_id` field the read-only Provider section already uses (no second key
  field). On success the screen shows the accepted transaction id, the locally-signed
  transaction id, whether they match (with a readable mismatch note if not), and an explicit
  `submitted to preprod — testnet-only, test fixture, no real funds` label. On failure every
  `SubmitError` variant (including `SubmissionNotSupported`'s explicit "this provider does not
  support submission (mock)" message) and every upstream draft-building/signing error the
  existing checkpoints can already produce is mapped to a readable message. **No polling**: the
  accepted id is shown once for manual explorer lookup (justified in
  `PlaygroundPresenter.presentSubmitTransaction`'s KDoc — a single-shot submit-and-display
  checkpoint has no justification yet for the added complexity). Tests:
  `PlaygroundSubmitTransactionPresenterTest` (`commonTest`, native-free — every `SubmitError`
  variant plus the accepted/local-id match and mismatch cases, since `TxHash` needs no native
  call) and `PlaygroundSubmitTransactionDesktopTest` (`jvmTest`-only — end to end with
  `InMemoryChainQueryProvider` + `InMemoryTxSubmitProvider`, asserting the mock's honest
  not-supported failure even once signing succeeds; no live network submit in tests).
- `1.11d` ADA-only enforcement for the submit flow — **Status: implementation complete;
  superseded by `1.11d-2`; final manual Android re-validation PASS.** The `1.11c` manual checkpoint found a real bug: a
  preprod address funded with mixed (ADA + native-asset) UTxOs let a draft build and sign, then
  the node rejected the submitted transaction with `ValueNotConservedUTxO` — the build silently
  dropped the native assets those inputs carried, which the ledger does not allow. Phase 1 stays
  ADA-only (ADR-0005); this block adds early, honest rejection instead of a false success:
  - `:provider`'s `Value` gains `hasNativeAssets: Boolean = false` — presence only, no
    quantities/policy ids/asset names, default preserves every existing ADA-only call site
    (ADR-0006 addendum).
  - `:provider-blockfrost`'s `mapUtxo` sets it to `true` whenever a Blockfrost `amount` entry's
    `unit != "lovelace"`, instead of silently dropping that entry (ADR-0007 addendum).
  - `:tx`'s `TransactionBuilder.build` rejected the **entire** candidate list with
    `TxBuildError.UnsupportedFeature` — right after the existing `NoInputs` check, before any
    coin selection — if **any** candidate input has `hasNativeAssets` set (ADR-0014 addendum).
    **Superseded by `1.11d-2` below** — this whole-list-reject behavior turned out to be too
    broad for a real wallet with a mix of ADA-only and native-asset UTxOs; see that entry.
  - `:shared`'s `presentTxBuildError` gives `UnsupportedFeature` a dedicated message (wording
    also updated by `1.11d-2` below).
  - Tests: `:provider`'s new `ValueTest` (default/explicit ADA-only, native-asset presence
    representable); `:provider-blockfrost`'s `BlockfrostChainQueryProviderTest` gained
    lovelace-only/lovelace+token flag assertions plus two new dedicated fixtures/tests (both
    still current, unaffected by `1.11d-2`). The `:tx`/`:shared` reject-whole-list tests this
    block originally added were replaced by `1.11d-2`'s filtering tests — see that entry.
- `1.11d-2` ADA-only UTxO filtering, not whole-wallet rejection — **Status: implementation
  complete; manual Android re-validation PASS; Block 1.11 complete.** Manual
  preprod testing under `1.11d` showed a real wallet/address can have many UTxOs, some with
  native assets and some ADA-only — rejecting the *whole* candidate list because of one
  native-asset UTxO meant a wallet with plenty of spendable ADA could not build a transaction at
  all. This block narrows `1.11d` to filter, not reject-if-any:
  - `:tx`'s `TransactionBuilder.build` now drops every `TransactionBuildRequest.candidateInputs`
    entry with `Value.hasNativeAssets` set **before** coin selection, then proceeds normally
    from the remaining ADA-only candidates. `TxBuildError.UnsupportedFeature` is returned only
    if that filtering leaves **no** candidates at all (detail names how many were dropped); if
    the ADA-only candidates are non-empty but still cannot cover `payment + fee`, the usual
    `TxBuildError.InsufficientFunds` fires — its `available` total reflects only the ADA-only
    candidates, since a native-asset UTxO's lovelace is never counted (ADR-0014 second
    2026-07-13 addendum). `TransactionDraft.selectedInputs` can never contain a native-asset
    UTxO, in either the old or new behavior.
  - `:shared`'s `presentTxBuildError`'s `UnsupportedFeature` message is reworded to: "This
    wallet has no ADA-only UTxOs to spend — only UTxOs containing native assets/tokens. Phase 1
    only builds ADA-only transactions." (with `detail` appended), reflecting that the failure
    now only means *no* ADA-only UTxO existed, not that *some* UTxO carried a native asset.
  - Tests: `:tx`'s `TransactionBuilderTest` gained an only-native-asset-candidates test (single
    and multi-UTxO), a mixed-candidates-with-sufficient-ADA-only-funds success test (asserting
    `selectedInputs` contains only the ADA-only ref), a mixed-candidates-with-insufficient-
    ADA-only-funds test (asserting `InsufficientFunds.available` excludes the native-asset
    UTxO's lovelace), and the existing ADA-only regression test carries over unchanged;
    `:shared`'s `PlaygroundTransactionDraftPresenterTest` gained a mixed-candidates success test
    alongside the updated sole-native-asset-candidate rejection test, and
    `PlaygroundTransactionDraftDesktopTest` gained an end-to-end mixed-UTxO success test
    alongside the updated end-to-end rejection test. No multi-asset CBOR output, no token
    sending, no token-preserving change, and no ledger-rule engine were added anywhere in this
    stack — coin selection's existing `InsufficientFunds` path does all the "is this enough"
    work it already did before.

Android checkpoint:

- Submit a preprod transaction from the app and see either an accepted result or an
  explainable error. **Status: attempted; found a real bug, now closed by `1.11d`/`1.11d-2`;
  re-validation PASS.** A preprod submit reached Blockfrost and was rejected with
  `ValueNotConservedUTxO` because the funded address's UTxOs carried native assets alongside
  ADA — see `1.11d`/`1.11d-2` above and `docs/HANDOFF.md` for the full write-up. After `1.11d-2`,
  the mixed ADA-only + native-asset case was owner-run on Android and passed: build/sign/submit
  succeeded using only ADA-only UTxOs, and the accepted transaction id matched the locally signed
  id (`331a79ece991fc9bfd98e9da2a5514f38f7ffeb3a08f1bd7e5a1f75af0e42416`). The owner then
  reported both remaining cases OK: (1) an address whose UTxOs are *all* native-asset showed the
  readable ADA-only rejection before submit; (2) an address funded with ADA-only UTxOs only
  showed the expected build/sign/submit outcome. No additional accepted transaction ids were
  provided.

### 1.12-pre-a Playground MVI Architecture

Refactor the `:shared` Playground from a long tool-like Compose screen into a maintainable
guided-flow architecture, ahead of Phase 1 closure. **Architecture-only**: no SDK behavior
change, and no visual redesign yet (that is `1.12-pre-b`).

Objective:

- Introduce a lightweight MVI (Model-View-Intent) split under
  `shared/src/commonMain/kotlin/org/sarmidev/kardano/playground/`: `mvi/PlaygroundState.kt`,
  `mvi/PlaygroundIntent.kt`, `mvi/PlaygroundReducer.kt`, `mvi/PlaygroundViewModel.kt`,
  `domain/PlaygroundUseCases.kt` (`RestoreWalletUseCase`, `QueryWalletFundsUseCase`,
  `BuildTransactionDraftUseCase`, `SignTransactionUseCase`, `SubmitTransactionUseCase`, each a
  thin wrapper over the existing `PlaygroundPresenter`), and `data/PlaygroundProviderFactory.kt`
  (the mock-vs-live-Blockfrost provider selection, moved out of the Compose layer).
- Model the guided flow explicitly — Wallet → Funds → Build → Sign → Submit — as a
  `PlaygroundStep` enum and matching `PlaygroundState` fields, reusing the existing
  `PlaygroundPresenter` `*Presentation` sealed types rather than a parallel display model.
- Refactor `PlaygroundScreen` into a renderer: it reads `PlaygroundState` and dispatches
  `PlaygroundIntent`s to `PlaygroundViewModel`; it computes nothing itself. The standalone
  Address Parser/Hex Decoder/CBOR Decoder/generic Provider-explorer tools are folded into the
  same state/intent model and rendered in a "Diagnostics" area below the guided flow, rather than
  kept as separate ad hoc Compose state.
- Preserve every existing behavior: the same test-only fixture wallet, the same mock/live
  provider selection and Blockfrost preprod-only boundary, the same ADA-only filtering from
  `1.11d`/`1.11d-2`, the same readable errors, the same submit id comparison, no mainnet, no real
  mnemonic/private-key display, no full CBOR display, no multi-asset support, no polling, no
  arbitrary-mnemonic import.
- No new architecture library and no Gradle/dependency change: `androidx.lifecycle`
  (`ViewModel`/`viewModelScope`, `collectAsStateWithLifecycle`) was already a `commonMain`
  dependency (Block 1.2), and `kotlinx.coroutines` was already resolvable transitively.
- Tests: `PlaygroundReducerTest` (`commonTest`, pure/non-suspend/native-free) covers the default
  mock initial state, provider-selection and technical-details transitions, `ResetFlow`'s
  keep-vs-clear behavior, and every `applyXResult` helper. `PlaygroundViewModelTest`
  (`jvmTest`-only, since `viewModelScope` needs a `Dispatchers.Main` that
  `kotlinx-coroutines-test` supplies) covers each guided-flow step's success/failure with faked
  use cases, the submit step's id match/mismatch, the funds step's in-flight loading flag, and
  that `PlaygroundProviderFactory` selects the correct provider instance. Every existing
  `PlaygroundPresenter` test is kept unchanged — the presenter itself was not moved or modified.
- Docs: `shared/README.md` gained a "Playground architecture (Block 1.12-pre-a)" section; this
  entry and the matching `docs/ROADMAP.md`/`docs/HANDOFF.md` entries record the block.

**Status: complete.** Compiles on common/JVM/Android/iOS-simulator (iOS simulator run itself is
environment-gated on this machine — no installed simulator SDK — but
`compileTestKotlinIosSimulatorArm64`/`linkDebugTestIosSimulatorArm64` both succeed, the existing
compile-and-link-only iOS bar per `docs/TESTING.md`). `:shared:jvmTest` and
`:shared:testAndroidHostTest` pass, including the new `PlaygroundReducerTest` (19 tests) and
`PlaygroundViewModelTest` (12 tests). **Next: `1.12-pre-b`** (visual refresh of the guided flow
built on this architecture), then Block 1.12 (Phase 1 Closure / MVP Review).

### 1.12-pre-b Playground Visual/UX Refresh

Refresh the `:shared` Playground UI so it presents the Kardano SDK MVP as a clear, modern guided
flow — **Wallet → Funds → Build → Sign → Submit** — rather than a list of text fields and
buttons. **Visual/UX only**: the Block 1.12-pre-a MVI architecture remains the state-management
foundation, and no SDK behavior, SDK public API, dependency, or non-`:shared` module changes.

Objective:

- Add a `playground/ui/` package of presentation-shell composables (none reach an SDK API):
  `PlaygroundTheme.kt` (a Kotlin/KMP-inspired Material 3 color scheme — purple lead, blue
  secondary, orange tertiary, at restrained contrast, following the system light/dark setting),
  `PlaygroundHeader.kt` (a hero header with the "Kardano SDK" title, the "Kotlin Multiplatform
  Cardano transaction flow" subtitle, always-on `TESTNET`/`ADA-only`/provider-mode badges, and a
  `FlowStepper` highlighting completed steps), `StatusBadge.kt` (the `MOCK` / `LIVE PREPROD` /
  `TESTNET` / `ADA-only` / `SIGNED` / `SUBMITTED` badges and per-step status chips),
  `FlowStepCard.kt` (a numbered step card with title, one-line explanation, status chip, one
  primary action with an in-button spinner, key output, and a "Technical details" toggle, plus
  shared `ResultRow`/`LabeledRows`/`ErrorInline`/`LoadingInline` primitives), and
  `DiagnosticsSection.kt` (the Address Parser, Hex Decoder, CBOR Decoder, and Provider explorer,
  visually secondary and collapsed by default).
- Keep the hero mark **Compose-drawn** (a rounded-square gradient with two white forward
  chevrons) — intentionally not the Kotlin or Cardano logo, and **no external image asset is
  bundled**, so there is no third-party artwork license to document.
- Rewrite `PlaygroundScreen.kt` to compose the header, `FlowStepper`, a shared provider-config
  card, the five step cards, a reset action, and the diagnostics area. Each step shows its title,
  short microcopy, current status, one main action, and its key output, with the full
  `PlaygroundPresenter` row list kept behind the per-step "Technical details" toggle. Loading is
  shown per step; errors render inline under the step that produced them, reusing the exact
  `PlaygroundPresenter` messages. `App.kt` wraps the screen in `KardanoPlaygroundTheme`.
- Preserve every existing behavior: same fixture wallet, mock/live provider selection, Blockfrost
  preprod-only submit boundary, ADA-only filtering, no mainnet, no real mnemonic/private-key
  display, no arbitrary-mnemonic input, no full CBOR display, no polling, no multi-asset support.
- Tests: the existing `PlaygroundReducerTest`/`PlaygroundViewModelTest` and every
  `PlaygroundPresenter` test are kept unchanged — none assert UI wording/layout, so the visual
  refresh required no test edits and deleted no behavioral coverage.
- Docs: `shared/README.md` gained a "Playground visual flow (Block 1.12-pre-b)" section; this
  entry and the matching `docs/ROADMAP.md`/`docs/HANDOFF.md` entries record the block.

**Status: complete.** `:shared:jvmTest` and `:shared:testAndroidHostTest` pass (existing
`PlaygroundReducerTest`/`PlaygroundViewModelTest` unchanged); `:shared:compileKotlinJvm` and
`:shared:compileKotlinIosArm64` succeed. `git diff --check` clean; no banned words on touched
files. **Next: Block 1.12 (Phase 1 Closure / MVP Review).**

**Follow-up polish (same block): background and system insets.** A manual Android screenshot
review found two cohesion issues the first pass missed: the root container had no background of
its own (so it fell back to the platform's default white window background, clashing with the
darker hero/cards), and — despite `:androidApp` already calling `enableEdgeToEdge()` (Block
1.2) — the screen applied no inset padding, so the hero could start under the status bar and the
bottom reset/diagnostics controls could sit behind the navigation bar. Fixed in
`PlaygroundScreen.kt` only: the root `Column` now paints a theme-derived vertical gradient
(`MaterialTheme.colorScheme.surface` → `background`, continuing the tone `PlaygroundHeader`'s own
gradient ends on — no new colors introduced) and applies `Modifier.safeDrawingPadding()` (a
Compose-Multiplatform-common `expect`/`actual` API in `androidx.compose.foundation.layout`, not an
Android-specific inset call) so inset-aware content padding keeps the scrollable flow clear of
the system bars.
No MVI, SDK, provider, wallet, tx, or transaction-flow change; no new dependency. Verified:
`:shared:jvmTest`, `:shared:testAndroidHostTest`, `:shared:compileAndroidMain` (exercises the real
Android `actual safeDrawingPadding`), `:shared:compileKotlinIosArm64`, `:desktopApp:compileKotlin`;
`git diff --check` clean; no banned words on touched files.

### 1.12-pre-c Playground Landing Section And Developer-Friendly Copy

Extend the `:shared` Playground so it opens like a small developer-facing landing/demo page — what
the SDK is, what it does today, and where it is going — before the existing guided **Wallet → Funds
→ Build → Sign → Submit** flow. **UX/content structure only**: the Block 1.12-pre-a MVI architecture
and all SDK behavior are preserved. No SDK public API, no provider/wallet/tx behavior change, no new
dependency, and no non-`:shared` module touched.

Objective:

- Add a landing/overview area above the interactive flow, built from Compose-drawn visuals and
  cards (no external image/logo asset is bundled — those are deferred until added with an explicit
  source/license):
  - **Hero** (`PlaygroundHeader.kt`): the "Kardano SDK" title, "Kotlin Multiplatform Cardano SDK"
    subtitle, the value statement "Build Cardano wallet and transaction flows from shared Kotlin
    code.", the platform/scope badge row (`KMP`/`Android`/`iOS`/`JVM`/`Preprod`/`ADA-only MVP`), the
    test-only framing line, and a CTA button ("Try the transaction flow below ↓") that scrolls to
    the flow. Its former `useLiveBlockfrost` param was dropped (provider mode is shown by the flow's
    provider card and per-step badges).
  - **`LandingSection.kt`** (`PlaygroundLanding`): *What the SDK does today* (five capability
    cards), *The transaction flow* preview (five developer-friendly step labels), *Code examples*
    (three collapsible monospace snippet cards, each tagged `simplified` — illustrative
    pseudo-snippets, never a real mnemonic/private key/full signed CBOR), and *Roadmap and scope*
    (Phase 0 / Phase 1 / Next cards plus an honest "Current limitations" list: testnet/preprod-focused
    demo, ADA-only MVP, no multi-asset, no mainnet flow, no real wallet import in the Playground).
- Add one presentation-only MVI flag for the landing "Code examples" toggle:
  `PlaygroundState.codeExamplesExpanded` (default `false`), `PlaygroundIntent.ToggleCodeExamples`,
  and a `PlaygroundReducer.reduce` branch (routed by the ViewModel's existing `else -> reduce`; no
  ViewModel change). It gates only static snippet visibility and carries no SDK semantics; `ResetFlow`
  does not touch it.
- Improve the guided steps' microcopy to developer-friendly titles ("Create a test wallet", "Check
  available test ADA", "Prepare a transaction", "Sign it locally", "Send it to preprod") with a
  one-line explanation each; exact hex/fees/witnesses/ids stay behind the existing per-step
  "Technical details" toggle. The step actions/outputs dispatch the same intents as before.
- Keep Diagnostics visually secondary and collapsed by default.
- Copy avoids hype/readiness claims and the banned words (`secure`, `safe`, `hardened`, `audited`,
  `production-ready`, `guaranteed`, `cryptographically safe`), suggests no mainnet use, and keeps the
  "test-only fixture", "preprod", and "ADA-only MVP" framing clear.
- Tests: `PlaygroundReducerTest` gained `toggleCodeExamples_flipsFlagAndTouchesNothingElse` and an
  `initial().codeExamplesExpanded == false` assertion; no existing behavioral coverage was removed.
- Docs: `shared/README.md`, this entry, and the matching `docs/ROADMAP.md`/`docs/HANDOFF.md`
  entries; each notes this is a sample-app UX/content change (not SDK public API) and that external
  image/logo assets are deferred unless added with an explicit source/license.

**Status: complete.** `:shared:jvmTest` and `:shared:testAndroidHostTest` pass;
`:shared:compileKotlinIosArm64` (and `:shared:compileAndroidMain`/`compileKotlinJvm`) succeed.
`git diff --check` clean; no banned words on touched files. **Next: Block 1.12 (Phase 1 Closure /
MVP Review).**

### 1.12-pre-c-2 Roadmap Screen And Friendlier Wallet Copy

Add a dedicated, tappable Roadmap screen to the `:shared` Playground and split the sample app into
navigable Overview / Try SDK / Roadmap sections, and soften the Wallet step's main-UX language.
**Sample-app UX/content only** — the 1.12-pre-a MVI architecture and all SDK behavior are preserved.
No SDK public API, no provider/wallet/tx behavior change, no new dependency, and no non-`:shared`
module touched. The Roadmap screen is presentation, **not a committed public API or delivery
schedule**.

Objective:

- Add presentation-only navigation to the MVI state: `PlaygroundState.section`
  (`PlaygroundSection.OVERVIEW`/`TRY_SDK`/`ROADMAP`, default `OVERVIEW`) and
  `PlaygroundState.selectedRoadmapPhase` (`RoadmapPhase?`, default `PHASE_1`), with
  `PlaygroundIntent.NavigateToOverview`/`NavigateToTrySdk`/`NavigateToRoadmap` and
  `SelectRoadmapPhase(phase)` handled in `PlaygroundReducer.reduce` (routed by the ViewModel's
  existing `else -> reduce`; no ViewModel change). `SelectRoadmapPhase` toggles — tapping the
  already-selected phase collapses its detail to `null`. `ResetFlow` does not touch either field.
- Restructure `PlaygroundScreen.kt` around a top `SectionNav` (Overview / Try SDK / Roadmap;
  selected = filled button): *Overview* renders the hero + `PlaygroundLanding` (whose CTA and a new
  `RoadmapTeaser` navigate to Try SDK / Roadmap); *Try SDK* renders the unchanged
  `FlowStepper`/provider card/five steps/reset + collapsed Diagnostics; *Roadmap* renders the new
  `RoadmapScreen`. The 1.12-pre-c hero-CTA scroll-anchor code was removed (sections replace in-page
  scrolling).
- Add `RoadmapScreen.kt`: one clickable card per phase with a title, a status badge (Done /
  Current / Planned / Future), a tagline, and — when selected — a highlights list and a scope note.
  Phase 0/1 describe shipped work; **Phase 2 (wallet/provider expansion) and Phase 3 (advanced
  transaction/ecosystem features) are aspirational candidate direction, explicitly not a commitment
  and with no dates**. All Compose-drawn; no external image/logo asset bundled.
- Refine the Wallet step to read "Create test wallet" (title + action; status "Creating…") with a
  softer explanation, while its Technical-details block keeps the precise wording that the demo
  calls `ReadOnlyWallet.restore(...)` with a cited public test-only mnemonic fixture. No
  arbitrary-mnemonic input and no real wallet import were added; the `RestoreWallet` intent and all
  SDK calls are unchanged.
- Copy avoids hype/readiness claims and the banned words (`secure`, `safe`, `hardened`, `audited`,
  `production-ready`, `guaranteed`, `cryptographically safe`), suggests no mainnet use, and keeps
  the "test-only fixture", "preprod", and "ADA-only MVP" framing clear.
- Tests: `PlaygroundReducerTest` gained navigation and roadmap-selection tests plus `initial()`
  section/phase assertions; no existing behavioral coverage was removed (no test asserted the old
  wallet wording).
- Docs: `shared/README.md`, this entry, and the matching `docs/ROADMAP.md`/`docs/HANDOFF.md`
  entries; each notes this is a sample-app UX/content change (not SDK public API) and that the
  Roadmap screen is direction, not a commitment.

**Status: complete.** `:shared:jvmTest` and `:shared:testAndroidHostTest` pass;
`:shared:compileKotlinIosArm64` (and `:shared:compileAndroidMain`/`compileKotlinJvm`) succeed.
`git diff --check` clean; no banned words on touched files. **Next: Block 1.12-pre-c-3 (Seed mock
Playground UTxOs for the guided flow).**

### 1.12-pre-c-3 Seed Mock Playground UTxOs For The Guided Transaction Flow

Let the *default mock mode* of the `:shared` Playground run the whole Wallet → Funds → Build → Sign
flow offline, instead of stopping at "no UTxOs". **Playground/sample mock data only** — no SDK
public API, no `:provider`/`:wallet`/`:tx` behavior change, no live Blockfrost change, and no faked
network submission. This is not chain data.

Context:

- The guided flow restores `TestWalletFixture` and queries the active provider for *that wallet's
  own* self-generated testnet address. `:provider`'s default seed has no UTxOs for that address —
  so under the bare in-memory mock, Build/Sign/Submit failed early with "no UTxOs".

Objective:

- Add `playground/data/PlaygroundMockSampleData.kt` (a `:shared` sample object) that builds the
  Playground's default mock `ChainQueryProvider` from `InMemoryChainQueryProvider.defaultSeed()`
  (keeping `SEED_ADDRESS_WITH_UTXOS` funded and `SEED_ADDRESS_EMPTY` empty for the explorer) and
  **adds two deterministic, fake, ADA-only UTxOs for the demo wallet's own restored address**
  (5 ADA + 8 ADA = 13 ADA — enough for the fixed 2 ADA demo payment plus fee and change;
  `hasNativeAssets = false`, fixed sentinel tx hashes). It restores `TestWalletFixture` only to
  obtain that address (degrades to the bare default on failure). `PlaygroundProviderFactory` now
  builds its mock query provider from this object, lazily; the mock submit provider is unchanged.
- Keep submission honest: `InMemoryTxSubmitProvider` still always returns
  `SubmitError.SubmissionNotSupported`. In mock mode the Submit step now *reaches* it (Build/Sign
  succeed) and shows the readable "does not support submission (mock)" message.
- No seed-address collision and no diagnostics change: the demo wallet address is distinct from
  both `SEED_ADDRESS_WITH_UTXOS` and `SEED_ADDRESS_EMPTY`, so the Provider explorer's "has UTxOs"
  and "empty" examples are untouched.
- Copy: the provider card states mock mode uses "fake local UTxOs, test-only, no network. Submit is
  not supported here."; live mode keeps "real network calls, test funds only." No hype/readiness
  claims and no banned words.
- Tests: new `PlaygroundMockFlowDesktopTest` (`jvmTest`) asserts the default mock provider seeds
  exactly the restored fixture address (two ADA-only UTxOs), reports a non-zero balance (13 ADA,
  2 UTxOs), builds and signs past the old "no UTxOs" failure, and reaches the honest not-supported
  submit message. Existing presenter/desktop tests (which use the bare `:provider` default) are
  unchanged.
- Docs: `shared/README.md`, this entry, and the matching `docs/ROADMAP.md`/`docs/HANDOFF.md`
  entries; each notes this is Playground/sample mock data only, not chain data and not SDK public
  API.

**Status: complete.** `:shared:jvmTest` and `:shared:testAndroidHostTest` pass;
`:shared:compileKotlinIosArm64` succeeds. `git diff --check` clean; no banned words on touched
files. **Next: Block 1.12-pre-d (Brand Assets And Theme Refresh).**

### 1.12-pre-d Brand Assets And Theme Refresh

Replace every placeholder/template icon and the Kotlin/KMP-inspired sample palette with the
project's own, first-party icon mark and a matching Material 3 theme, ahead of building the public
landing page. **Visual/branding only** — no SDK public API, no `:core`/`:crypto`/`:wallet`/`:tx`/
`:provider`/`:provider-blockfrost` change, no MVI/flow change, no new runtime dependency.

Context:

- The owner produced the project's first definitive icon mark — a violet-to-blue "K" beside a
  cyan-tinted, Cardano-style dot cluster — in a light variant (saturated, for light surfaces) and a
  dark variant (white/lilac, for dark surfaces), each at low/medium/high resolution with verified
  transparent backgrounds. Every prior icon (the Android robot template, a Compose-drawn
  placeholder header mark) and the Kotlin/KMP-inspired palette were sample/template artifacts, not
  the project's own identity.

Objective:

- Confirm both source PNGs have a fully transparent background and centered content (done via a
  Pillow-based bounding-box check before generating any derived asset).
- Centralize theme tokens in `PlaygroundTheme.kt`: a violet/blue/cyan Material 3 light/dark
  `ColorScheme` matched to the mark, plus a new `KardanoBrandColors`/`LocalKardanoBrand`
  composition local carrying the five decorative accent hues and the chip background/foreground
  pairs `StatusBadge.kt`/`LandingSection.kt` previously hardcoded — each pair gets a distinct,
  non-recycled dark-mode value.
- Replace the Compose-drawn `KmpMark()` in `PlaygroundHeader.kt` with a `BrandMark()` `Image` that
  picks the light/dark PNG (`shared/src/commonMain/composeResources/drawable/
  kardano_mark_{light,dark}.png`) via `isSystemInDarkTheme()`, and delete the unused JetBrains
  template drawable (`compose-multiplatform.xml`).
- Rebuild the Android launcher as an adaptive icon (solid-color background XML plus a
  density-specific foreground PNG of the mark, padded to the adaptive-icon safe zone) with a
  `-night` pair for dark mode, regenerate the legacy pre-API-26 `mipmap-*dpi` PNGs (square +
  circle-masked) as light/dark opaque tiles, and rename the visible app label to `Kardano SDK`.
- Add an iOS dark-appearance `AppIcon` PNG and wire it into the existing `Contents.json` slot
  (leaving `tinted` unpublished), set `AccentColor` to the theme's light/dark primary, and set the
  visible display name to `Kardano SDK` without touching the bundle identifier.
- Wire Desktop distribution icons (`.icns`/`.ico`/`.png`) into `nativeDistributions` and a runtime
  window/dock icon into `Window(...)`, and rename the window title to `Kardano SDK`.
- Record the source PNGs as first-party Sarmidev assets in `docs/THIRD_PARTY_NOTICES.md` (not a
  tracked third-party component).

Non-goals:

- No redesign of the guided Wallet → Funds → Build → Sign → Submit flow, its MVI state/intents/
  reducer, or any provider/wallet/tx call.
- No new runtime dependency, no Gradle plugin change beyond the existing Compose-desktop
  `nativeDistributions` DSL already in `desktopApp/build.gradle.kts`.
- No Kotlin/Cardano third-party logo; the mark is Sarmidev's own artwork.

**Status: complete.** `./gradlew :shared:jvmTest :shared:testAndroidHostTest
:shared:compileKotlinIosArm64 :desktopApp:compileKotlin :androidApp:assembleDebug` pass; `git diff
--check` clean; no banned words on touched files. Manual light/dark review covered the Android
launcher (adaptive + legacy, day/night), the iOS AppIcon default/dark slots, the Desktop window/
dock icon, and the in-app header/badges/buttons in both themes. **Next: Block 1.12-pre-e (Guided
Playground Demo Redesign).**

### 1.12-pre-e Guided Playground Demo Redesign

Redesign the Playground into a linear, self-explaining five-step demo (Welcome → Demo → Summary)
for a short public video: one screen at a time, one plain-language explanation and one obvious
button per step, and every technical detail (hashes, fees, CBOR, UTxOs, witnesses) collapsed
behind an optional "Technical details" toggle. **Presentation only** — no SDK public API, no
`:core`/`:crypto`/`:wallet`/`:tx`/`:provider`/`:provider-blockfrost` change, no new dependency; the
1.12-pre-a MVI split and every existing `RestoreWallet`/`QueryFunds`/`BuildDraft`/
`SignTransaction`/`SubmitTransaction` call are unchanged.

Context:

- The Block 1.12-pre-c-2 tab row (Overview / Try SDK / Roadmap) put a developer-facing prose page
  in front of the working flow — the opposite of what a short, guided video needs. Reviewers with
  no Cardano background also found the flow's own language (UTxO, CBOR, witnesses, fee/change in
  raw lovelace) hard to follow without narration.

Objective:

- Replace the tab row with a linear journey: **Welcome** (what the demo does, a five-step
  preview, one *Start the demo* button) → **Demo** (one `FlowStepCard` at a time, driven by a new
  `PlaygroundState.demoStep` cursor, with `Step N of 5`, a recap strip of finished steps, and
  *Back*/*Continue*/*Start over* controls) → **Summary** (a plain-language recap plus an honest
  "what this demo is not" scope list, and *Run the demo again*). **About** (the former Overview
  content, re-copied) and **Roadmap** become secondary screens off Welcome/Summary, each with a
  "Back to the demo" control.
- Add `PlaygroundDemoFlow.kt`, a pure `commonTest`-covered object owning step outcome
  classification (`StepOutcome`: `NOT_STARTED`/`WORKING`/`DONE`/`INFO`/`ERROR`), continue-gating,
  friendly-reason mapping for a documented subset of existing error messages, and
  address/id truncation — so no composable computes this logic itself.
- Classify the mock Submit step's unchanged, honest `SubmitError.SubmissionNotSupported` failure
  as a new, neutral `StepOutcome.INFO` ("stopped on purpose") rather than a red `ERROR`, keyed off
  a byte-identical constant extracted from `PlaygroundPresenter.presentSubmitError` — the
  underlying `Failure` state and the mock provider's behavior do not change.
- Add `DemoCopy.kt`, a single reviewable, data-driven table holding every Welcome/Demo/Summary
  string, asserted jargon- and banned-word-free outside two documented, narrower exceptions (the
  collapsed "Advanced" disclosure and the Summary's scope-boundary list).
- Add four purely additive, ADA-formatted `LabeledRow`s to `PlaygroundPresenter.kt` (`Test ADA`,
  `Payment`, `Network cost`, `Change back`) via a new `LovelaceDisplay.ada(lovelace)` helper, so
  the main narrative reads in ADA while every existing raw-lovelace row stays available under
  Technical details.
- Relocate `DiagnosticsSection` (content unchanged) under the About screen's "Developer tools"
  heading, since it is unrelated to the guided demo's fixture wallet.
- Mask the Blockfrost preprod project-id field (`PasswordVisualTransformation`) and distinguish
  switch intent from effective provider state: a blank id keeps Mock active and displays a
  configuration-required message; live-request copy appears only once the id is non-blank.

Non-goals:

- No wallet import, no user-supplied mnemonic, no mainnet, no native assets, no scripts, no
  metadata, no multisig, no polling.
- No change to which use case runs, which provider it receives, or in what order; no change to
  `TestWalletFixture`, `PlaygroundMockSampleData`'s seeded UTxOs, or `PlaygroundProviderFactory`.
- No new Compose UI-test dependency; navigation/gating/copy are covered at the reducer/derived-
  state level (`commonTest`) plus `@Preview`s for visual review, the same testing shape the rest
  of `:shared` uses.

**Status: complete.** `./gradlew :shared:jvmTest :shared:testAndroidHostTest
:shared:compileKotlinIosArm64 :desktopApp:compileKotlin :androidApp:assembleDebug` pass; `git diff
--check` clean; no banned words on touched files; the pre-existing, unrelated working-tree edit in
`core/src/commonMain/kotlin/org/sarmidev/kardano/encoding/cbor/CborValue.kt` was left untouched.
**Next: Block 1.12 (Phase 1 Closure / MVP Review).**

### 1.12 Phase 1 Closure / MVP Review

Close Phase 1 with a review of the full flow.

Status: in progress. The implementation and manual preprod checkpoint are complete; the remaining
closure work reconciles public documentation, release readiness, target limitations, and the
Phase 2 handoff.

Objective:

- Verify that the full Android flow works on preprod.
- Confirm tests and docs are updated.
- Confirm that no UI has been mixed into `:core`.
- Document known limitations.
- Define the next scope.

Android checkpoint:

- Full demo: create/restore a test wallet, see the address, receive test ADA,
  query UTxOs, build, sign, and submit a transaction.

## Mandatory Android checkpoints

Open the Android app and verify functionality after:

- `1.2`: playground parsing addresses.
- `1.3`: read-only UTxO query.
- `1.6`: test wallet generates derived material.
- `1.7`: testnet address generated and parsed.
- `1.8`: balance/UTxOs visible.
- `1.9`: transaction draft visible.
- `1.10`: signed transaction visible.
- `1.11`: transaction submitted to preprod. **Status: complete** — implementation (`1.11a`/
  `1.11b`/`1.11c`/`1.11d`/`1.11d-2`) is complete, and one owner-run attempt already surfaced a
  real ADA-only gap (`ValueNotConservedUTxO` from a mixed-UTxO address, now closed by
  `1.11d`/`1.11d-2`). The mixed ADA-only + native-asset re-validation then passed on Android:
  build/sign/submit succeeded using only ADA-only UTxOs and returned accepted transaction id
  `331a79ece991fc9bfd98e9da2a5514f38f7ffeb3a08f1bd7e5a1f75af0e42416`; the owner also reported
  the all-native-asset rejection and ADA-only-only build/sign/submit checks OK (see
  `docs/HANDOFF.md`).

## Deferred or conditional work

- Byron/Base58 address support remains separate from Phase 1 unless explicitly decided otherwise.
- Address raw/hex constructors require an encoding/roundtrip policy.
- Native assets may stay out of the first MVP if the scope is tightened.
- Wallet persistence can start simple or be left for another block, but must not
  be improvised alongside signing.
- Additional providers (Koios, Maestro, Ogmios, Kupo) come after the first provider.

## Next step

`1.1`, `1.2`, `1.3a` (interface + models + mock + Playground in `:provider`), `1.3b-pre`
(`Address.bech32` in `:core`), `1.3b` (`:provider-blockfrost`: `BlockfrostChainQueryProvider`
with Ktor + kotlinx-serialization, mapping to neutral models, a live toggle in the Playground, and
ADR-0007), `1.4` (Crypto Evaluation And Module Decision, docs only; ADR-0008), and `1.5a` (compatibility
spike, **PASS**) are complete. `1.5a` confirmed that the provisional candidate
(Apollo 1.8.8 + `bip32-ed25519` 2.3.0) resolves and compiles on Android + JVM + iosSimulatorArm64
under Kotlin 2.4.0 (ADR-0008 §6); no dependency was committed to the build (the scratch module
was discarded). `1.5b-pre` (vector gate, docs only) is done and **passes for both sizes**:
Blake2b-224 fixed with CIP-19 and Blake2b-256 fixed with the Plutus conformance goldens
(`IntersectMBO/plutus` @`5e18824e`, Apache-2.0; ADR-0008 §7). `1.5b` is **complete**: `:crypto`
was created and Blake2b-224/256 were wired behind `Hashing`. While wiring it, it was confirmed that Apollo
1.8.8 does not include Blake2b, so the hashing-only backend is KotlinCrypto
`org.kotlincrypto.hash:blake2` `0.8.0` (Apollo and `bip32-ed25519` are not added in this block; they are
reserved for 1.6 / 1.10; ADR-0008 §8). `1.6a` (API, dependency, and vector decision for
mnemonic/seed/derivation, docs only) is **complete**: ADR-0009 fixes the Icarus/CIP-3 scheme
(restoration only, English wordlist), the dependency-per-algorithm table verified against
published artifacts (Apollo is not used in 1.6; `bip32-ed25519` for 1.6c;
cryptography-kotlin PBKDF2 + KotlinCrypto `sha2` for 1.6b), the vector gate (PASS across all
three families: Trezor `vectors.json`, CIP-3 `Icarus.md`, `IntersectMBO/cardano-addresses`
goldens), the API sketch, the error model, and the key-material rules. `1.6b`
(mnemonic-to-master-key) closed its `To verify in 1.6b` PBKDF2 gate (cryptography-kotlin failed
it on Android; adopted the ADR-0009 §3 platform-seam fallback — BouncyCastle on JVM/Android,
Apple CommonCrypto on iOS) and is **complete on JVM and Android**, with cited BIP-39/CIP-3
vectors passing on both. On iOS, an inline C interop shim (`kardano_ccpbkdf2_hmac_sha512` in
`pbkdf2raw.def`) adapts `CCKeyDerivationPBKDF`'s password to a raw byte pointer, and **both iOS
compile targets pass** (`:crypto:compileKotlinIosSimulatorArm64` and
`:crypto:compileKotlinIosArm64`); **iOS runtime execution of the vectors is still future
verification** — no iOS-simulator/device test run has exercised this binding. `1.6c`
(Ed25519-BIP32 + CIP-1852 private derivation) closed its original gate narrowed to private
derivation only (ADR-0009), then a follow-up (ADR-0010) swapped the backend coordinate to
`org.hyperledger.identus:bip32-ed25519:1.8.8` and **verified private derivation on real
Android runtime** (`:crypto:connectedAndroidDeviceTest`), resolving the earlier Android
blocker, and added `ExtendedPublicKey`/`KeyDerivation.publicKey(...)` for JVM/iOS (backed by
libsodium's `crypto_scalarmult_ed25519_base_noclamp`), verified against the cited `addr_xvk`
goldens on JVM with iOS compile/link passing. A second follow-up then **closed the Android
public-key-projection gap that opened**: `KeyDerivation.publicKey` now delegates on Android to
`com.goterl:lazysodium-android:5.2.0` (a fuller libsodium build than the JVM/iOS backend's
Android native library, which lacks the needed symbol), verified on real Android runtime — a
physical device plus API 24/36 emulators — reproducing the cited `addr_xvk` golden and the
CIP-19 payment credential. Full write-up: ADR-0009 "Block 1.6c gate result" and ADR-0010.
`1.6d` (test-wallet fixture + Android checkpoint) is delivered on top of that: `:shared` gained
a `:crypto` dependency and a Playground section restoring the cited test-only mnemonic,
deriving `m/1852'/1815'/0'/0/0`, and displaying only its CIP-1852 path and Blake2b-224
fingerprint.

`1.7` (address generation, ADR-0012), `1.8` (read-only `:wallet`, ADR-0013), and `1.9`
(minimal unsigned ADA transaction builder in `:tx`, ADR-0014) are **complete**, including their
Android checkpoints. `1.10a` (Transaction Signing ADR, ADR-0015) is **complete (docs-only)**: it
records the signing ownership/boundary, the exact scope and its fixture-only enforcement boundary
(§2a — a Phase 1 call-site/checkpoint/test policy, not a `:wallet`-internal check, since `:wallet`
cannot depend on `:shared`'s `TestWalletFixture`; Block 1.10 introduces no general-purpose wallet
signing API), the signing message, artifact, error model, test policy, and the blocking backend
gate, but authorizes no signing code. `1.10b-pre` (Signing backend + vector-source gate, ADR-0016)
is also **complete**: its provisioning spike (ADR-0016 §8) has now been **ADOPTED and VERIFIED**
(ADR-0016 §9i) into the permanent, project-owned module **`:crypto-signing-backend`** (crate
`kardano-ed25519-bip32-signing`, `publish = false`, `ed25519-bip32 = "0.4.2"` pinned + `Cargo.lock`),
landed as Option R1 — no Rust/Cargo/Gobley Gradle plugin; 8 committed native artifacts + pre-generated
UniFFI bindings, all offline-regenerable. Every §7d leg was **re-run and passes against that real
module**: `jvmTest` 4/4 (macOS arm64); `connectedAndroidDeviceTest` 4/4 on a physical device (Android
15) + 4/4 on an API-24 emulator, through the packaged Kotlin/JNA bindings; `compileKotlinIosArm64` +
`linkDebugTestIosSimulatorArm64` green (cinterop over the committed static libs); and `nm`/`llvm-nm`
symbol proof on all 8 artifacts. The disposable `scratch-signing-backend` /
`scratch-signing-backend:android` modules are deleted. JVM native coverage is macOS-only by design
(no CI in-repo; Linux/Windows JVM hosts are future work, ADR-0016 §9 Option R3).

`1.10b` (the signing implementation) is **complete** (ADR-0015 §9 result note): `:crypto` gained
the `Signing`/`SigningError` API delegating to `:crypto-signing-backend`
(`extendedPrivateKeyBytesForSigning()` module-internal accessor, no public private-key byte
exposure); `:tx` gained witness-set/full-`transaction` CBOR assembly
(`VerificationKeyWitness`/`TransactionWitnessSet`/`SignedTransaction`/`TransactionAssembler`,
still crypto-free — `:core`'s CBOR subset gained the narrow `true`/`false`/`null` simple values
this required, per the ADR-0001 addendum); `:wallet` gained the `:wallet → :tx` dependency and
`ReadOnlyWallet.signTransaction(words, network, draft)` orchestration returning
`WalletSignedTransaction`. Every verification command in ADR-0015 §6/§9 passes: `jvmTest` for
`:crypto`/`:tx`/`:wallet`/`:crypto-signing-backend`; `testAndroidHostTest` for
`:crypto`/`:tx`/`:wallet`; `:crypto-signing-backend:connectedAndroidDeviceTest` on a physical
device and an emulator; `compileKotlinIosArm64` for
`:crypto`/`:tx`/`:wallet`/`:crypto-signing-backend`; and
`:crypto-signing-backend:linkDebugTestIosSimulatorArm64`.

`1.10c` (the `:shared` Android "Signed Transaction (not submitted)" checkpoint, ADR-0015 §7) is
**complete**: see its own entry above for what was added and verified, including the manual
Android runtime checkpoint.

`1.11a` (`:provider` submission boundary), `1.11b` (`:provider-blockfrost` Blockfrost submit
implementation), `1.11c` (the `:shared` Android "Submit Transaction (preprod)" checkpoint,
ADR-0017), `1.11d` (ADA-only rejection for the submit flow, ADR-0006/0007/0014 2026-07-13
addenda), and `1.11d-2` (ADA-only UTxO filtering instead of whole-wallet rejection, second
ADR-0006/0014 2026-07-13 addenda) are **complete**. The manual Android re-validation PASS
includes a mixed ADA-only/native-asset transaction accepted by preprod with transaction id
`331a79ece991fc9bfd98e9da2a5514f38f7ffeb3a08f1bd7e5a1f75af0e42416`, plus owner-reported
all-native-asset rejection and ADA-only-only checks. The active work is Block 1.12 closure and
the funding-readiness track; Phase 2 planning is in `docs/PHASE_2_PLAN.md`.
