# ADR-0007: HTTP Client And Blockfrost Preprod Provider

| Field   | Value                                             |
|---------|---------------------------------------------------|
| Status  | **Accepted**                                      |
| Scope   | Phase 1 Block 1.3b provider implementation        |
| Phase   | Phase 1 (Block 1.3b)                              |
| Updated | 2026-07-05                                        |

---

## Context

ADR-0006 defined a read-only, provider-neutral `ChainQueryProvider` in `:provider`, shipped a
fake in-memory mock (Block 1.3a), and deferred the first real preprod provider to Block 1.3b.
ADR-0005 named Blockfrost as that first target. This ADR records the concrete Block 1.3b
decisions: the HTTP/JSON dependency, the new `:provider-blockfrost` module, the response
mapping, the secrets policy, and the Android live checkpoint.

This ADR **depends on** the `Address.bech32` microchange landed separately as Block 1.3b-pre:
`:core` `Address` exposes the exact validated source string, which the Blockfrost
address-keyed endpoints require. ADR-0007 does not introduce that change; it consumes it.

`:core` and `:provider` must remain free of any HTTP dependency, so the network client and the
Blockfrost-specific wire models need their own module.

---

## Decision

### 1. A new `:provider-blockfrost` Gradle module

Block 1.3b creates a Kotlin Multiplatform `:provider-blockfrost` module (Android library + JVM
+ iosArm64 + iosSimulatorArm64, `explicitApi()`) that `api`-depends on `:provider` (to
re-expose the neutral interface and models) and `implementation`-depends on `:core`. This is
the dependency trigger ADR-0002/ADR-0005/ADR-0006 anticipated: the HTTP client and JSON
parsing land here, keeping `:core` and `:provider` HTTP-free.

### 2. HTTP client and serialization dependency (rationale)

The module adds Ktor (client) and kotlinx-serialization-json, pinned in the version catalog
(no dynamic versions):

- `commonMain`: `ktor-client-core`, `ktor-client-content-negotiation`,
  `ktor-serialization-kotlinx-json`, `kotlinx-serialization-json`.
- Per-platform engines: `ktor-client-okhttp` (Android), `ktor-client-cio` (JVM),
  `ktor-client-darwin` (iOS).
- `commonTest`: `ktor-client-mock` (plus `kotlin-test`, `kotlinx-coroutines-test`).
- The `org.jetbrains.kotlin.plugin.serialization` plugin is applied at the module (version =
  Kotlin version).

Rationale (per the "no dependency without a documented rationale" guardrail): Ktor is the
standard KMP HTTP client with first-party engines for every target the SDK ships, and
kotlinx-serialization is the standard KMP JSON layer with a compile-time model. Both are
isolated to `:provider-blockfrost`. The engine seam (`internal expect fun defaultHttpClient`)
lets tests inject a `MockEngine`-backed client through the provider's `internal` constructor,
so no real engine or network is needed for unit tests.

### 3. Blockfrost network to `Network` mapping

`BlockfrostNetwork { PREPROD, PREVIEW, MAINNET }` carries the Blockfrost base URL and maps to
the SDK `Network`: `PREPROD` and `PREVIEW` both map to `Network.TESTNET` (network id `0` cannot
distinguish them), `MAINNET` maps to `Network.MAINNET`. `BlockfrostConfig(projectId, network =
PREPROD)` is the public config. The provider is bound to `network` and returns
`ProviderError.NetworkMismatch` for an address on a different network before any HTTP call.

### 4. Response mapping (Blockfrost shapes stay internal)

All Blockfrost JSON models are `internal @Serializable` DTOs in `:provider-blockfrost`; they
never leave the module. `BlockfrostChainQueryProvider` maps them to the neutral `:provider`
models:

- `getUtxos`: `GET /addresses/{address.bech32}/utxos?page=n&count=100&order=asc`, paginated up
  to a bounded `MAX_PAGES`. `tx_hash` decodes via `Hex` + `TxHash.of`, `output_index` via
  `UtxoRef.of`, and the summed `lovelace` amounts via `Lovelace.of` + `Value`.
- `getProtocolParameters`: `GET /epochs/latest/parameters`, mapping the fee/deposit/size subset
  (string lovelace fields parsed to `Long`).
- `getTip`: `GET /blocks/latest`, mapping `slot` and `height`.

Two documented relaxations/limits:

- **ADA-only:** only the `lovelace` component is summed into `Value.coin` (matches the
  ADR-0006 ADA-only `Value`). This does not fail the UTxO. (See the 2026-07-13 addendum below:
  a non-`lovelace` unit no longer passes silently — it now sets `Value.hasNativeAssets`.)
- **404-as-empty (scoped to `getUtxos`):** a Blockfrost `404` for an address that has never
  appeared on-chain returns `Ok(emptyList())`, not an error. Other endpoints keep `404` as
  `ProviderError.NotFound`.

### 5. Error mapping (HTTP stays inside the module)

The provider never throws (it propagates only coroutine cancellation). Failures map to the
neutral `ProviderError`: transport exceptions to `Transport`, `429` to `RateLimited`, `404` to
`NotFound` (except the `getUtxos` empty case), any other non-2xx to `RemoteStatus(code)`, and
JSON/parse or `:core`-factory failures to `Deserialization`. HTTP status codes are translated
to `RemoteStatus` **only inside** `:provider-blockfrost`; `:provider` keeps `RemoteStatus` as
the neutral public error.

### 6. Secrets / configuration policy

No key is ever committed. `BlockfrostConfig.projectId` is a runtime value supplied by the
caller:

- Manual Android verification: a Playground `project_id` text field held only in non-persistent
  Compose state (`remember`, not `rememberSaveable`); never stored or logged.
- Local integration test: reads `BLOCKFROST_PROJECT_ID` from the environment; skipped when
  absent and excluded from the default suite.
- Default unit tests: `MockEngine` + committed sanitized fixtures only; no network, no key.

`.gitignore` already covers `local.properties`.

### 7. Android live checkpoint

The Playground provider section gains a "Use live Blockfrost (preprod)" switch and a
`project_id` field. When enabled with a non-blank key it builds
`BlockfrostChainQueryProvider.create(...)` and feeds it into the existing, provider-agnostic
presenter, so the same UI drives the mock or the live provider.

---

## Consequences

- `:provider-blockfrost` exists and is depended on by `:shared` (Playground). `:core` and
  `:provider` remain HTTP-free; `:provider`'s public API is unchanged.
- The SDK now has a real read path against preprod, verifiable on Android with the owner's own
  key, without committing secrets or requiring the network in CI.
- Adding a second provider later reuses the neutral `:provider` surface without reshaping it.

---

## Non-goals

- No transaction submission (deferred to Block 1.11, ADR-0006).
- No wallet, crypto, transaction building, or signing.
- No native-asset value model (ADA-only mapping).
- No `toBech32` encoder in `:core` (address re-encoding stays deferred to Block 1.7); the
  provider uses the `Address.bech32` source string from Block 1.3b-pre.
- No functional iOS/JVM network demo (the Darwin/CIO engines are compile-verified only here).

---

## Follow-up work

- Block 1.11: `TxSubmitProvider` and a submit-result model, once signing exists.
- Block 1.7: address encoding/round-trip (`toBech32`), which may supersede reliance on the
  stored source string.
- ADR-0005 (`docs/DECISIONS/0005-phase-1-architecture-and-scope.md`) and ADR-0006
  (`docs/DECISIONS/0006-provider-boundary-and-strategy.md`) remain the governing decisions this
  ADR implements.

---

## Addendum (2026-07-13): native-asset amounts now flagged, not silently dropped (Block 1.11d)

ADR-0006's own 2026-07-13 addendum records why: a manual Android submit checkpoint found a
mixed (ADA + native-asset) preprod UTxO caused a node-side `ValueNotConservedUTxO` rejection,
because §4 above's mapping silently dropped the non-`lovelace` amount entries it saw.

The resulting, narrowly-scoped change to `mapUtxo`: any `amount` entry whose `unit` is not
`lovelace` now sets the mapped `Value.hasNativeAssets` to `true` (in addition to being excluded
from the summed `coin`, unchanged from before). Quantities, policy ids, and asset names of
those entries are still not represented or stored anywhere. No other mapping, endpoint, or
error-handling decision in this ADR changes.

---

## Addendum (2026-08-23): `BlockfrostConfig` is no longer a data class

§3 introduced `BlockfrostConfig(projectId, network = PREPROD)` as the public config. It shipped
as a `data class` with a hand-written redacted `toString()`, but the compiler-generated
`equals` / `hashCode` / `copy` / `componentN` still retained the raw `projectId`.

A repository-wide search found no call site that compared, hashed, copied, or destructured a
`BlockfrostConfig`. Value equality is therefore not required. This addendum records the
pre-alpha source change:

- `BlockfrostConfig` is a regular class. Equality is referential (identity). `hashCode` is the
  identity hash and is not derived from `projectId`.
- `toString` remains redacted (`projectId=<redacted>`).
- The public `projectId` and `network` accessors remain: the HTTP factory sends `projectId` as
  the `project_id` header, and both providers bind `network`.
- `copy` / `componentN` are not generated.

No other decision in this ADR changes.

---

## Addendum (2026-08-23): read-path `RemoteStatus` detail and UTxO cap failure

§4's `getUtxos` pagination ("up to a bounded `MAX_PAGES`") previously returned the accumulated
list as success after the last permitted page, including when that page was still full (10_000
UTxOs with the production 100×100 bound). That is a silent partial result. The implementation
now returns `ProviderError.ResultTruncated(fetchedCount, cap)` when the final permitted page is
full. Tests inject an internal `UtxoPaginationPolicy` so the cap path can be exercised without
allocating a 10_000-entry page; that seam is not public.

§5's error mapping now parses an optional `detail` for `ProviderError.RemoteStatus`, matching
`SubmitError.RemoteStatus`. Detail is taken from the response body only (Blockfrost's
`{status_code, error, message}` envelope, or a truncated raw body). Request headers and request
configuration, including `project_id`, are never read into `detail`. Coroutine cancellation is
still rethrown.

No other decision in this ADR changes.
