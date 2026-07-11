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

#### 1.6b BIP-39 / CIP-3 mnemonic-to-master-key (blocked by the ADR-0009 gates)

- Scope: mnemonic parsing (word count, wordlist, checksum), entropy extraction, and the
  Icarus master key (96 bytes) only. No derivation paths, no addresses, no
  signing, no generation.
- Adds only the dependencies assigned in ADR-0009 (pinned in the catalog). Before
  accepting the wiring it must close the `To verify in 1.6b` item (PBKDF2-SHA-512 coverage per
  target, including Android API 24/25); if it fails, use the platform-seam fallback — never
  handwritten PBKDF2.
- Tests in `crypto/commonTest` with the cited vectors verbatim (Trezor + CIP-3), plus
  labeled derived invalid/edge cases and structural key-material tests.

#### 1.6c Ed25519-BIP32 + CIP-1852 (blocked until 1.6b closes)

- Scope: a `KeyDerivation` seam over `bip32-ed25519` (private and public/soft derivation),
  SDK-owned CIP-1852 path types (`account'`/`role`/`index`). No signing; no
  address generation (that is 1.7, which also requires the encoding ADR).
- Must close the `To verify in 1.6c` item: byte layouts and V2 scheme confirmed against
  the goldens; native loading on Android; iosSimulatorArm64 compile **and link** (1.5a only proved
  compile). An iOS link failure reopens the dependency decision (ADR-0008 §4
  fallback).
- Tests against the cardano-addresses goldens (decoded with `:core`'s generic
  `Bech32.decode`; the CIP-5 HRPs are intentionally outside `CardanoBech32`'s
  allowlist).

#### 1.6d Test-wallet fixture / Android checkpoint (blocked until 1.6c closes)

- A fixture built exclusively from the cited public vector (`test walk nut …`),
  labeled test-only. No real funds, no real mnemonics.
- Playground: `:shared` gains a project dependency on `:crypto` (no new
  external dependency). Shows **only publicly derived metadata**: the CIP-1852 path used, the
  Blake2b-224 fingerprint of the derived public key (via the existing `Hashing`, which must
  match the CIP-19 payment credential fixed in 1.5b), and the typed
  success/error state. **No** raw public key or hex is shown unless a later plan
  justifies it; nothing about private bytes, seed, or words. Addresses are
  part of the 1.7 checkpoint.

Android checkpoint (1.6d):

- Restore the fixture test wallet and see the derivation path + Blake2b-224
  fingerprint matching the cited vector; invalid mnemonic input -> typed error
  without crash.

### 1.7 Address Generation

Generate Shelley addresses from derived keys.

Objective:

- Create the payment credential and stake credential from keys.
- Generate a testnet base address.
- Produce Bech32.
- Verify roundtrip with `Address.parse`.
- Define the address encoding/roundtrip policy if it does not already exist.

Android checkpoint:

- Generate an `addr_test` address in the app and parse it immediately, showing its
  structure.

### 1.8 Wallet State Read-Only

Connect wallet + provider without building transactions yet.

Objective:

- Show the generated address.
- Query UTxOs for that address.
- Show the test ADA balance.
- Allow a manual refresh.

Android checkpoint:

- Receive ADA from a preprod faucet at the generated address and see balance/UTxOs in the app.

### 1.9 Transaction Builder Minimal

Build a simple ADA transaction.

Objective:

- Select inputs.
- Create the destination output.
- Compute change.
- Compute the fee.
- Include minimal validity parameters if applicable.
- Generate the transaction body / CBOR needed for future signing.

Android checkpoint:

- Enter a destination address + amount, build a draft transaction, and see a
  summary before signing.

### 1.10 Transaction Signing

Sign a testnet/preprod transaction locally.

Objective:

- Use only test keys.
- Sign the transaction body.
- Produce a witness / signed transaction according to the chosen format.
- Keep tests backed by official vectors or verified references when available.

Android checkpoint:

- Build and sign a transaction, showing the tx id or signed CBOR without submitting it yet.

### 1.11 Submit Transaction

Submit the signed transaction to preprod.

Objective:

- Implement submit via the provider.
- Handle submit errors.
- Show the tx id or a comprehensible error.
- Optionally allow simple polling or an external link.

Android checkpoint:

- Submit a preprod transaction from the app and see either an accepted result or an
  explainable error.

### 1.12 Phase 1 Closure / MVP Review

Close Phase 1 with a review of the full flow.

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
- `1.11`: transaction submitted to preprod.

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
published artifacts (Apollo is not used in 1.6; `dev.allain:bip32-ed25519:2.3.0` for 1.6c;
cryptography-kotlin PBKDF2 + KotlinCrypto `sha2` for 1.6b), the vector gate (PASS across all
three families: Trezor `vectors.json`, CIP-3 `Icarus.md`, `IntersectMBO/cardano-addresses`
goldens), the API sketch, the error model, and the key-material rules. The next step is `1.6b`
(mnemonic-to-master-key), which before accepting its wiring must close the `To verify in 1.6b` item
from ADR-0009. There is no wallet, tx, or signing yet.
