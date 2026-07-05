# :provider-blockfrost

The first real read-only Cardano chain provider for Kardano SDK, backed by the Blockfrost API.
Introduced in Phase 1 Block 1.3b.

## Status

Phase 1 — pre-alpha, experimental. Not audited. Not for real funds (preprod uses test funds).

## Role

- Implements `ChainQueryProvider` (from `:provider`) against Blockfrost:
  `BlockfrostChainQueryProvider`.
- Maps Blockfrost JSON responses to the provider-neutral models (`Utxo`, `ProtocolParameters`,
  `ChainTip`, `ProviderError`). The Blockfrost wire shapes are `internal` and never leave this
  module.
- Selects the network with `BlockfrostNetwork { PREPROD, PREVIEW, MAINNET }` (carries the base
  URL; `PREPROD`/`PREVIEW` map to `Network.TESTNET`, `MAINNET` to `Network.MAINNET`).

All operations are `suspend` and return `KardanoResult` (they never throw, except to propagate
coroutine cancellation), which keeps the API compatible with Swift/ObjC interop.

## Scope and limits (first MVP)

- Read-only: `getUtxos`, `getProtocolParameters`, `getTip`. No submit (deferred to Block 1.11,
  see [ADR-0006](../docs/DECISIONS/0006-provider-boundary-and-strategy.md)).
- ADA-only: native-asset amounts in a UTxO are ignored; only the `lovelace` component is mapped.
- `getUtxos` treats a Blockfrost `404` (address never used) as an empty list, not an error.
  Other endpoints keep `404` as `ProviderError.NotFound`.
- UTxO pagination is capped internally.

## Dependencies

Ktor (client) + kotlinx-serialization-json, isolated to this module; `:core` and `:provider`
stay HTTP-free. Per-platform engines: OkHttp (Android), CIO (JVM), Darwin (iOS). See
[ADR-0007](../docs/DECISIONS/0007-http-client-and-blockfrost-provider.md). It depends on the
`Address.bech32` source string landed in Block 1.3b-pre.

## API keys / secrets

No key is committed. `BlockfrostConfig.projectId` is supplied at runtime:

- Android: the Playground `project_id` field (non-persistent Compose state; not stored/logged).
- Local integration test: the `BLOCKFROST_PROJECT_ID` environment variable (opt-in).
- Default unit tests: a Ktor `MockEngine` + committed sanitized fixtures — no network, no key.

## Usage

```kotlin
val provider = BlockfrostChainQueryProvider.create(
    BlockfrostConfig(projectId = myPreprodKey), // BlockfrostNetwork.PREPROD by default
)
when (val result = provider.getTip()) {
    is KardanoResult.Ok -> println(result.value)
    is KardanoResult.Err -> println(result.error)
}
```

## Testing

- Unit (MockEngine) tests: `./gradlew :provider-blockfrost:jvmTest`
- Android host tests: `./gradlew :provider-blockfrost:testAndroidHostTest`
- iOS simulator compile: `./gradlew :provider-blockfrost:compileKotlinIosSimulatorArm64`
- Opt-in live preprod test:
  `BLOCKFROST_PROJECT_ID=preprod... ./gradlew :provider-blockfrost:jvmTest`

See [docs/TESTING.md](../docs/TESTING.md) for the testing strategy and test-vector policy.
