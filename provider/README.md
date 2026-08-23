# :provider

The read-only Cardano chain query boundary for Kardano SDK, introduced in Phase 1 Block 1.3a.

## Status

Phase 1 — pre-alpha, experimental. Testnet/preprod only. No real funds.

## Role

- Defines `ChainQueryProvider`: a minimal, provider-neutral, read-only interface for querying
  UTxOs by address, protocol parameters, and an optional chain-tip liveness signal.
- Defines the provider-neutral read models: `Utxo`, `Value` (ADA-only for the first MVP),
  `ProtocolParameters`, `ChainTip`, and the sealed `ProviderError`. `Value.hasNativeAssets`
  (Block 1.11d) records only whether the output also carried native assets/tokens alongside
  its ADA `coin` — quantities, policy ids, and asset names are still not represented — so a
  concrete provider (`:provider-blockfrost`) and a caller (`:tx`) can detect and reject what
  this ADA-only MVP cannot fully represent, instead of silently dropping it.
- Ships one read implementation in 1.3a: `InMemoryChainQueryProvider`, a documented sample/test
  double whose data is **fake and test-only** (no network, no funds, no secrets, no committed
  chain fixtures).
- Defines `TxSubmitProvider` (Block 1.11a): a minimal, provider-neutral interface for submitting
  a fully signed transaction's raw CBOR bytes, and the sealed `SubmitError`.
- Ships one submit implementation in 1.11a: `InMemoryTxSubmitProvider`, a sample/test double
  that **never submits anything** — every call returns `SubmitError.SubmissionNotSupported`,
  including for empty input; it never fakes acceptance.

All operations are `suspend` and return `KardanoResult` (they never throw), which keeps the
API compatible with Swift/ObjC interop.

## Boundaries

- Depends only on `:core`. `commonMain` adds no third-party dependency; only `commonTest`
  uses `kotlinx-coroutines-test`.
- `TxSubmitProvider` is a separate interface from `ChainQueryProvider`, not an additional
  method on it — submission is a single mutating, non-idempotent action with its own failure
  taxonomy (`SubmitError`), not a read. See
  [ADR-0006](../docs/DECISIONS/0006-provider-boundary-and-strategy.md) for why the split was
  planned and [ADR-0017](../docs/DECISIONS/0017-transaction-submission-boundary.md) for the
  concrete Block 1.11a decision (interface shape, `ByteArray` input, `TxHash` return,
  `SubmitError` taxonomy).
- `TxSubmitProvider.submit` takes raw signed transaction CBOR bytes (`ByteArray`), not a `:tx`
  module type: `:tx` already depends on `:provider`, so `:provider` cannot depend back on
  `:tx` without a cycle. Callers extract the bytes themselves (for example
  `SignedTransaction.cbor()`) before calling `submit`.
- No real backend submit implementation lands in this sub-block. The first real preprod
  Blockfrost submit provider (`BlockfrostTxSubmitProvider`) is deferred to Block 1.11b and will
  live in `:provider-blockfrost`, alongside the existing read-only Blockfrost provider from
  Block 1.3b. `ProviderError`/`SubmitError` stay backend-neutral (for example `RemoteStatus`,
  not `HttpStatus`). `ProviderError.RemoteStatus` carries an optional `detail` (response text
  only). `ProviderError.ResultTruncated` is the typed failure when a paged `getUtxos` hits
  the implementation cap while more items remain; callers must not treat a truncated list as
  complete.

## Testing

- Contract tests: `./gradlew :provider:jvmTest`
- Android host tests: `./gradlew :provider:testAndroidHostTest`
- iOS simulator compile: `./gradlew :provider:compileKotlinIosSimulatorArm64`

See [docs/TESTING.md](../docs/TESTING.md) for the testing strategy and test-vector policy,
[docs/DECISIONS/0006-provider-boundary-and-strategy.md](../docs/DECISIONS/0006-provider-boundary-and-strategy.md)
for the read-only provider boundary decisions, and
[docs/DECISIONS/0017-transaction-submission-boundary.md](../docs/DECISIONS/0017-transaction-submission-boundary.md)
for the submission boundary decisions.
