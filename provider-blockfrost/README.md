# :provider-blockfrost

The first real Cardano chain provider for Kardano SDK, backed by the Blockfrost API. Read-only
support was introduced in Phase 1 Block 1.3b; transaction submission was added in Block 1.11b.

## Status

Phase 1 — pre-alpha, experimental. Testnet/preprod only. No real funds (preprod uses test funds).

## Role

- Implements `ChainQueryProvider` (from `:provider`) against Blockfrost:
  `BlockfrostChainQueryProvider`.
- Implements `TxSubmitProvider` (from `:provider`) against Blockfrost:
  `BlockfrostTxSubmitProvider` (Block 1.11b). Submits full signed transaction CBOR to
  `POST /tx/submit` and maps the accepted transaction id or a failure into the provider-neutral
  `TxHash` / `SubmitError`. See [ADR-0017](../docs/DECISIONS/0017-transaction-submission-boundary.md).
- Maps Blockfrost JSON responses to the provider-neutral models (`Utxo`, `ProtocolParameters`,
  `ChainTip`, `ProviderError`, `SubmitError`). The Blockfrost wire shapes are `internal` and
  never leave this module.
- Selects the network with `BlockfrostNetwork { PREPROD, PREVIEW, MAINNET }` (carries the base
  URL; `PREPROD`/`PREVIEW` map to `Network.TESTNET`, `MAINNET` to `Network.MAINNET`).

All operations are `suspend` and return `KardanoResult` (they never throw, except to propagate
coroutine cancellation), which keeps the API compatible with Swift/ObjC interop.

## Scope and limits (first MVP)

- `getUtxos`, `getProtocolParameters`, `getTip` (read) and `submit` (Block 1.11b).
- ADA-only: only the `lovelace` component is summed into `Value.coin`. Native-asset
  quantities, policy ids, and asset names are never represented — but (Block 1.11d) any
  `amount` entry whose `unit` is not `lovelace` sets `Value.hasNativeAssets = true` rather than
  being silently dropped, so `:tx`'s `TransactionBuilder` can reject a UTxO it cannot fully
  represent instead of building around it.
- `getUtxos` treats a Blockfrost `404` (address never used) as an empty list, not an error.
  Other endpoints keep `404` as `ProviderError.NotFound`.
- UTxO pagination is capped internally.
- `submit` rejects empty input with `SubmitError.EmptyTransaction` before any HTTP call, and
  defensively copies the caller's bytes before handing them to the HTTP client.

## Submitting a transaction (`BlockfrostTxSubmitProvider`)

- Endpoint: `POST {baseUrl}/tx/submit`, `Content-Type: application/cbor`, body = the raw signed
  transaction CBOR bytes.
- Success (`200`): the response body is a JSON string containing a 64-character hex transaction
  id (for example `"d1662b24...908"`). The surrounding quotes are stripped from the raw response
  text deliberately, then the hex is decoded into a `TxHash`; anything else becomes
  `SubmitError.Deserialization`.
- Errors: `400` (the node rejected the transaction) maps to `SubmitError.Rejected(code, detail)`;
  `429` maps to `SubmitError.RateLimited`; any other non-2xx status (`403`, `404`, `418`, `425`,
  `500`, ...) maps to `SubmitError.RemoteStatus(code, detail?)`. When present, `detail` is parsed
  from Blockfrost's `{status_code, error, message}` JSON error envelope, falling back to the raw
  response body.
- There is **no automated live-network test** for `submit`, unlike the read-only provider's
  opt-in `BLOCKFROST_PROJECT_ID` integration test: submitting is a single mutating,
  non-idempotent action that consumes real preprod test UTxOs, so exercising it against a live
  node is a manual Android checkpoint (Block 1.11c), not something run repeatedly and
  automatically.

## Dependencies

Ktor (client) + kotlinx-serialization-json, isolated to this module; `:core` and `:provider`
stay HTTP-free. Per-platform engines: OkHttp (Android), CIO (JVM), Darwin (iOS). See
[ADR-0007](../docs/DECISIONS/0007-http-client-and-blockfrost-provider.md). It depends on the
`Address.bech32` source string landed in Block 1.3b-pre.

## API keys / secrets

No key is committed. `BlockfrostConfig.projectId` is supplied at runtime, for both the
read-only and the submit provider:

- Android: the Playground `project_id` field (session memory in `PlaygroundState` plus an
  in-memory factory cache key; never persisted or logged).
- Local integration test: the `BLOCKFROST_PROJECT_ID` environment variable (opt-in, read-only
  path only — see above for why `submit` has no equivalent automated live test).
- Default unit tests: a Ktor `MockEngine` + committed sanitized fixtures — no network, no key.

## Usage

```kotlin
val queryProvider = BlockfrostChainQueryProvider.create(
    BlockfrostConfig(projectId = myPreprodKey), // BlockfrostNetwork.PREPROD by default
)
when (val result = queryProvider.getTip()) {
    is KardanoResult.Ok -> println(result.value)
    is KardanoResult.Err -> println(result.error)
}

val submitProvider = BlockfrostTxSubmitProvider.create(
    BlockfrostConfig(projectId = myPreprodKey),
)
when (val result = submitProvider.submit(signedTransactionCbor)) {
    is KardanoResult.Ok -> println(result.value) // accepted TxHash
    is KardanoResult.Err -> println(result.error) // typed SubmitError
}
```

## Testing

- Unit (MockEngine) tests: `./gradlew :provider-blockfrost:jvmTest`
- Android host tests: `./gradlew :provider-blockfrost:testAndroidHostTest`
- iOS simulator compile: `./gradlew :provider-blockfrost:compileKotlinIosSimulatorArm64`
- Opt-in live preprod test (read-only path only):
  `BLOCKFROST_PROJECT_ID=preprod... ./gradlew :provider-blockfrost:jvmTest`

See [docs/TESTING.md](../docs/TESTING.md) for the testing strategy and test-vector policy.
