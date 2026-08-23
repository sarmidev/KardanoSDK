# ADR-0006: Provider Read-Only Boundary And Strategy

| Field   | Value                                            |
|---------|--------------------------------------------------|
| Status  | **Accepted**                                     |
| Scope   | Phase 1 Block 1.3 provider boundary and strategy |
| Phase   | Phase 1 (Block 1.3a)                             |
| Updated | 2026-07-05                                       |

---

## Context

ADR-0005 (Phase 1 architecture and scope) set the provider strategy at a high level:
a mock/stub provider first, then Blockfrost as the first real preprod target, with a
minimal public API to avoid locking the surface around Blockfrost's response shape. It also
listed the MVP provider data scope as "UTxOs for an address, protocol parameters needed for
fee/build logic, and a submit endpoint", and named a candidate ADR-0006 to be created when
Block 1.3 records its provider decisions.

Block 1.3 implements that boundary. This ADR records the concrete decisions. `:core` must
stay UI-free and dependency-free, and `:shared` must stay the sample/UI host (not the
long-term home for provider logic), so the provider needs its own home.

Block 1.3 is split into two sub-blocks:

- **1.3a** (this change): a dependency-free, provider-neutral, read-only interface; minimal
  ADA-only read models; an in-memory mock; Playground wiring; tests.
- **1.3b** (deferred): the first real Blockfrost preprod provider, which introduces an HTTP
  client dependency, API-key configuration, and committed sanitized response fixtures.

---

## Decision

### 1. A new `:provider` Gradle module

Block 1.3a creates a Kotlin Multiplatform `:provider` module (Android library + JVM +
iosArm64 + iosSimulatorArm64, `explicitApi()`) depending only on `:core`. This is the
ownership trigger ADR-0002/ADR-0003/ADR-0005 anticipated: the provider interface cannot live
in `:core` (which stays dependency-free and structural) and must not become permanent in
`:shared` (the sample/UI host). Creating the module now — even before any HTTP dependency —
is justified by that ownership boundary, not by dependency pressure.

`:provider` `commonMain` adds **no** new dependency in 1.3a: `suspend` is a language feature
and needs no coroutines artifact, and the mock returns directly. Only `:provider`
`commonTest` adds `kotlinx-coroutines-test` (for `runTest`), pinned in the version catalog.

The future `:provider-blockfrost` (1.3b) is a separate module depending on `:provider` and
`:core`; it is where the HTTP client dependency lands, keeping `:provider` dependency-light.

### 2. Read-only interface: `ChainQueryProvider`

The boundary is a read-only `ChainQueryProvider` with:

- `val network: Network` — the provider is bound to one network at construction.
- `suspend fun getUtxos(address): KardanoResult<List<Utxo>, ProviderError>`
- `suspend fun getProtocolParameters(): KardanoResult<ProtocolParameters, ProviderError>`
- `suspend fun getTip(): KardanoResult<ChainTip, ProviderError>` (optional health/liveness).

All operations are `suspend` and return `KardanoResult`; none throw. Returning failures as
`KardanoResult` instead of throwing keeps the API compatible with Swift/ObjC interop, where a
thrown exception would crash iOS consumers.

### 3. Relationship to ADR-0005 (submit is deferred, by refinement)

ADR-0005 §5 listed UTxOs, protocol parameters, and a submit endpoint together as the MVP
provider scope. This ADR **refines** that: it separates the read-only query boundary
(`ChainQueryProvider`, this block) from transaction submission, which moves to a distinct
`TxSubmitProvider` introduced in Block 1.11, after local signing exists and a submit-result
model is meaningful. This is a precision refinement of ADR-0005, not a reversal: the MVP
still needs submit; it is simply not part of the read-only boundary and is sequenced with the
signing work. ADR-0005 carries a one-line cross-reference to this refinement.

### 4. Provider-neutral models (no backend leakage)

The read models live in `:provider` and describe protocol concepts, not any backend's JSON:

- `Utxo` = `UtxoRef` (reused from `:core`) + `Value`.
- `Value` = ADA-only, wrapping `Lovelace` (`:core`) as `coin`. Native assets are out of the
  first MVP (ADR-0005); the type is designed to leave room for future multiasset support, and
  no binary/source compatibility is promised for that future addition. (See the 2026-07-13
  addendum below: `Value` gained a `hasNativeAssets` presence flag in Block 1.11d — still no
  quantities, policy ids, or asset names.)
- `ProtocolParameters` = a small set of fee/build fields as `Long`s (`minFeeCoefficient`,
  `minFeeConstant`, `keyDeposit`, `poolDeposit`, `maxTxSize`, `coinsPerUtxoByte`). It may grow
  at Block 1.9 (transaction builder) and does not mirror any provider's field names.
- `ChainTip` = `slot` + `blockHeight` (coarse liveness only).
- `ProviderError` (sealed) = `Transport`, `RemoteStatus(code)`, `NotFound`,
  `Deserialization`, `RateLimited`, `NetworkMismatch(expected, actual)`, `Unknown`. The
  status variant is named `RemoteStatus`, deliberately transport-agnostic rather than
  `HttpStatus`, so the read boundary does not assume HTTP; the 1.3b Blockfrost module maps
  HTTP status codes into it. No Blockfrost-specific variants exist in `:provider`.

An empty-but-valid UTxO query returns `Ok(emptyList())`, not an error.

### 5. Network binding and pagination

The provider is bound to a `Network` at construction; `getUtxos` returns
`ProviderError.NetworkMismatch` when the queried address is on a different network. For the
Phase 1 preprod checkpoint the provider is bound to `Network.TESTNET`; note that
`Network.TESTNET` covers all Cardano test networks and does not by itself identify preprod
versus preview.

Pagination is a provider-internal concern: `getUtxos` returns a bounded `List<Utxo>` and no
page cursor types appear in the public API. The 1.3b Blockfrost implementation will aggregate
its paged responses internally up to a bounded maximum.

### 6. Mock-first; the mock is fake/test-only

Block 1.3a ships exactly one implementation: `InMemoryChainQueryProvider`, a documented
sample/test double backed entirely by hardcoded data. Its data is fake and for testing only —
not real on-chain outputs, not committed chain fixtures, no funds, no network, no secrets. It
recognizes two documented seed addresses (both valid public CIP-19 testnet vectors): one that
returns fake UTxOs and one that returns an empty list.

### 7. Secrets / configuration policy for 1.3b

Block 1.3a introduces no secrets. When the real Blockfrost provider is built (1.3b), an API
key must never be committed. The intended paths:

- Manual Android verification: a runtime text field where the owner pastes their own preprod
  key; never stored, never committed.
- Programmatic/tests: read from a gitignored `local.properties` entry or an environment
  variable; ensure `.gitignore` covers key files (`local.properties`, `*.env`,
  `secrets*.properties`).

Real-network calls are excluded from the default unit-test suite (opt-in, env-gated). Fixture
JSON is introduced only in 1.3b, alongside the real response shapes, for error-mapping tests.

---

## Consequences

- A `:provider` module now exists, depended on by `:shared` (for the Playground) and, in the
  future, by wallet/tx modules. `:core` and `:androidApp` are unchanged.
- Wallet Block 1.8 (`Wallet State Read-Only`) can proceed against the mock without a live
  network or config.
- The public provider API stays small and backend-neutral, so introducing Blockfrost (1.3b)
  or a second provider later does not require reshaping it.
- ADR-0005 §5 gains a cross-reference noting that submit is split out and deferred to Block
  1.11 per this ADR.

---

## Non-goals

- No real Blockfrost/network implementation, no HTTP client dependency, no API keys, no
  secrets in Block 1.3a.
- No transaction submission in the read-only interface (deferred to Block 1.11).
- No wallet, crypto, transaction building, or signing.
- No native-asset model.
- No claim that the mock's data is real, on-chain, or spendable.

---

## Follow-up work

- Block 1.3b: `:provider-blockfrost` preprod provider (HTTP client, API-key config, sanitized
  fixtures, error-mapping tests, opt-in network integration test).
- Block 1.11: `TxSubmitProvider` and a submit-result model, once signing exists.
- ADR-0002 (`docs/DECISIONS/0002-module-structure.md`), ADR-0003
  (`docs/DECISIONS/0003-core-package-structure.md`), and ADR-0005
  (`docs/DECISIONS/0005-phase-1-architecture-and-scope.md`) remain the governing decisions
  this ADR aligns with and, for ADR-0005 §5, refines.

---

## Addendum (2026-07-13): native-asset presence flag for Block 1.11d

A manual Android submit checkpoint (Block 1.11c) found that a preprod address funded with
mixed (ADA + native-asset) UTxOs let a draft build, sign, and submit, only for the node to
reject it with `ValueNotConservedUTxO` — the built transaction implicitly dropped the native
assets those inputs carried, which the ledger does not allow. §4 above's `Value` had no way to
represent that a UTxO carried native assets at all, so nothing downstream could reject it
honestly.

This addendum records the resulting, narrowly-scoped change:

- `Value` gains exactly one new field: `hasNativeAssets: Boolean = false`. The default
  preserves every existing call site's ADA-only behavior.
- No quantities, policy ids, or asset names are represented — this is presence detection only,
  not the multiasset support §4 already anticipated as a future, compatibility-unconstrained
  addition.
- A concrete `ChainQueryProvider` (`:provider-blockfrost`, Block 1.11d) sets the flag when it
  detects a non-`lovelace` amount unit; `:tx`'s `TransactionBuilder` (ADR-0014 §8, narrowed in
  the 1.11d-2 addendum) filters out every candidate input carrying it before building, only
  failing with `TxBuildError.UnsupportedFeature` if that leaves no candidates at all.

No other decision in this ADR changes.

---

## Addendum (2026-08-23): `RemoteStatus` detail and `ResultTruncated`

§4's `ProviderError` list shipped `RemoteStatus(code)` with no optional detail, while the later
`SubmitError.RemoteStatus` (ADR-0017) carried `detail: String?`. That asymmetry is closed:
`ProviderError.RemoteStatus` is now `RemoteStatus(code, detail?)`. [detail] is parsed response
text when a concrete backend provides one; it must not include request headers or request
configuration.

§5 said pagination is a provider-internal concern and that a concrete implementation aggregates
paged responses up to a bounded maximum. A full last page is not enough to claim that more
items exist. `ProviderError.ResultTruncated(fetchedCount, cap)` is the typed failure only after
a one-item probe of the next page is non-empty. An empty probe (including a backend 404
that the concrete provider already treats as empty/end-of-results on ordinary pages) is
a complete `Ok` at exactly the cap. A page larger than the requested count is an invalid remote payload
(`Deserialization`), not ordinary truncation. `getUtxos` still returns a bounded `List<Utxo>`
on success; page cursors remain out of the public API.

Adding `detail` to `RemoteStatus` and adding the `ResultTruncated` subtype are pre-alpha
source breaks. Default `detail = null` keeps existing `RemoteStatus(code)` source call sites
compiling; binary compatibility and exhaustive-`when` compatibility are not claimed.

No other decision in this ADR changes.
