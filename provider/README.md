# :provider

The read-only Cardano chain query boundary for Kardano SDK, introduced in Phase 1 Block 1.3a.

## Status

Phase 1 — pre-alpha, experimental. Not audited. Not for real funds.

## Role

- Defines `ChainQueryProvider`: a minimal, provider-neutral, read-only interface for querying
  UTxOs by address, protocol parameters, and an optional chain-tip liveness signal.
- Defines the provider-neutral read models: `Utxo`, `Value` (ADA-only for the first MVP),
  `ProtocolParameters`, `ChainTip`, and the sealed `ProviderError`.
- Ships one implementation in 1.3a: `InMemoryChainQueryProvider`, a documented sample/test
  double whose data is **fake and test-only** (no network, no funds, no secrets, no committed
  chain fixtures).

All operations are `suspend` and return `KardanoResult` (they never throw), which keeps the
API compatible with Swift/ObjC interop.

## Boundaries

- Depends only on `:core`. `commonMain` adds no third-party dependency; only `commonTest`
  uses `kotlinx-coroutines-test`.
- Transaction submission is intentionally out of scope here. Per
  [ADR-0006](../docs/DECISIONS/0006-provider-boundary-and-strategy.md), the read-only query
  boundary is split from a future `TxSubmitProvider` (Block 1.11).
- The first real preprod provider (Blockfrost) is deferred to Block 1.3b and will live in a
  separate `:provider-blockfrost` module, which is where the HTTP client dependency and
  API-key configuration land. `ProviderError` stays backend-neutral (for example
  `RemoteStatus(code)`, not `HttpStatus`).

## Testing

- Contract tests: `./gradlew :provider:jvmTest`
- Android host tests: `./gradlew :provider:testAndroidHostTest`
- iOS simulator compile: `./gradlew :provider:compileKotlinIosSimulatorArm64`

See [docs/TESTING.md](../docs/TESTING.md) for the testing strategy and test-vector policy,
and [docs/DECISIONS/0006-provider-boundary-and-strategy.md](../docs/DECISIONS/0006-provider-boundary-and-strategy.md)
for the provider boundary decisions.
