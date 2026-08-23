# Testing Guide — Kardano SDK

How tests, fixtures, and external test vectors are organized in this repository. This
guide complements the testing rules in
[docs/AI_WORKING_AGREEMENT.md](AI_WORKING_AGREEMENT.md) (the "Unit testing policy" and
"Test integrity rules" sections) and does not replace them. If anything here ever
conflicts with the working agreement, the working agreement wins.

> The Phase 1 demo is experimental and testnet/preprod-focused. It includes scoped fixture
> restoration, signing, and submission; it does not cover mainnet or user-supplied key material.

---

## Test source sets

Tests live in Kotlin Multiplatform source sets. Put each test in the narrowest source
set that can express it.

- `commonTest` — the default home for tests. Uses `kotlin.test` so the same tests run on
  every target (JVM, Android, iOS). Deterministic, UI-free SDK logic (primitives,
  encoders, parsers, validators) is tested here so coverage is shared across platforms.
- `jvmTest` — JVM-only tests, or tests that depend on JVM-only test tooling. Keep
  protocol behavior in `commonTest`; use `jvmTest` only when a test genuinely cannot be
  expressed in common code.
- Android host tests (`androidHostTest`) — JVM-hosted unit tests for the Android target.
  They run on the local JVM (no emulator/device) via the `withHostTest { }` configuration
  in the module Gradle files. Use these for Android-target-specific behavior only.
- iOS tests (`iosTest` / native targets) — Kotlin/Native tests for the iOS targets. They
  run on the iOS simulator and require macOS with Xcode. Use these for iOS-target-specific
  behavior only.

Guidance:

- Prefer `commonTest`. Only drop to a platform source set when the behavior or tooling is
  platform-specific.
- Test naming: one test class per unit under test, named `<Unit>Test`; test functions use
  descriptive lowerCamelCase names that state the expected behavior (for example,
  `rejectsInvalidChecksum`). Cover valid, invalid, and edge cases for every unit.

### Where tests live today

- `:core` — UI-free primitives, encodings, structural addresses, and CBOR.
- `:crypto` — mnemonic parsing, seed/key derivation, hashing, and scoped signing adapters.
- `:crypto-signing-backend` — generated/native signing backend seam and known-answer tests.
- `:provider` and `:provider-blockfrost` — provider-neutral models plus Blockfrost wire mapping.
- `:wallet` and `:tx` — wallet orchestration and ADA-only transaction behavior.
- `:shared` — Playground MVI, sample-flow wiring, and presentation mapping. Protocol vectors and
  SDK behavior remain owned by their corresponding SDK module rather than the Compose UI.

---

## Fixture folder layout

Fixtures (test input/expected-output data) are kept separate from implementation and from
test code. They live under the `commonTest` resources of the module that owns the logic:

```
core/src/commonTest/resources/fixtures/
  README.md         (fixture policy + index)
  bech32/README.md   (future BIP-173 / BIP-350 vectors)
  cbor/README.md     (future RFC 8949 Appendix A vectors)
  address/README.md  (future CIP-19 vectors)
```

- One subfolder per spec/area. Each subfolder has a `README.md` naming the authoritative
  source for the vectors that will go there.
- Protocol vectors may live inline in tests or in fixture files. When added, they must land
  alongside the implementation that uses them, with the authoritative source cited.
- `:shared` carries no protocol fixtures; see
  `shared/src/commonTest/resources/fixtures/README.md`.

---

## External test-vector policy

This policy is mandatory for any security-sensitive unit (checksums, CBOR, addresses).

- Vectors must be copied verbatim from cited specifications or from a trusted reference
  implementation. Do not paraphrase, reformat, or "clean up" the values.
- Generated or AI-invented vectors are not allowed. An AI agent must never produce its own
  "expected" outputs for checksum, CBOR, or address tests.
- Every fixture file (or fixture block) cites its source spec and URL in a header comment.
- Include both valid and invalid vectors where the spec provides them. Invalid vectors
  must stay invalid; do not modify them to make a parser accept them.
- Never weaken a validator to make a test pass. If a test fails, fix the implementation or
  correct the cited test data — never relax the acceptance criteria.
- Round-trip direction: `decode(encode(x)) == x` is fine to test. `encode(decode(y)) == y`
  must not be used to normalize or accept non-canonical input; if tested, also assert that
  non-canonical input is rejected before decoding.

### Required external vector sources

- Bech32 / Bech32m — BIP-173 and BIP-350 valid and invalid vectors.
- CBOR — RFC 8949 Appendix A examples for each supported type.
- Addresses — CIP-19 examples (testnet preferred) plus known-bad inputs.

---

## Verification commands

Run tests per module. iOS simulator tests require macOS with Xcode.

- Core (JVM) tests: `./gradlew :core:jvmTest`
- Core Android host (JVM-hosted) tests: `./gradlew :core:testAndroidHostTest`
- Core iOS test sources compile: `./gradlew :core:compileTestKotlinIosSimulatorArm64`
- Crypto, wallet, shared, and signing-backend JVM tests: run on macOS because the committed JVM
  signing artifacts target macOS hosts:
  `./gradlew :crypto:jvmTest :crypto-signing-backend:jvmTest :wallet:jvmTest :shared:jvmTest`
- Provider (JVM) tests: `./gradlew :provider:jvmTest :provider-blockfrost:jvmTest`
- `BlockfrostConfigTest` asserts that `toString`, `assertEquals` failure text, and
  `List`/`Set`/`Map` rendering never include the project id, and that two configs with
  the same fields are not equal (identity equality; the type is no longer a `data class`).
- `BlockfrostChainQueryProviderTest` covers `403`/`500` response-body detail (and
  malformed/blank bodies), cancellation rethrow, and the UTxO cap: an internal
  `UtxoPaginationPolicy` test seam (not public) exercises `ProviderError.ResultTruncated`
  when the last permitted page is full, and `Ok` when that page is short, without
  allocating 10_000 entries.
- `PlaygroundProviderPresenterTest` / `PlaygroundDemoFlowTest` cover every
  `ProviderError` variant, including `RemoteStatus` with and without `detail` and
  `ResultTruncated`.
- `BlockfrostHttpTimeoutTest` asserts the documented 10s/30s/30s `HttpTimeout` bounds
  through an internal policy seam (no 30s sleep), that `configureBlockfrost` installs
  the plugin, that a delayed `MockEngine` handler with a shortened request timeout maps
  to `Transport` for both read and submit, and that submit is attempted once.
- `BlockfrostErrorDetailTest` covers empty/malformed bodies, a huge raw body, a complete
  envelope with a long `message` field, and a UTF-8 4-byte code point split by the byte
  budget. Public detail stays within 500 characters; a filled byte budget is not parsed
  as JSON.
- `BlockfrostOkHttpEngineTest` (androidHostTest) asserts
  `blockfrostOkHttpClient().retryOnConnectionFailure == false`. That is the engine-level
  submit-replay switch, not Ktor `HttpRequestRetry`.
- Wallet and transaction (JVM) tests: `./gradlew :wallet:jvmTest :tx:jvmTest`
- Desktop (JVM) tests: `./gradlew :shared:jvmTest`
- Android host (JVM-hosted) tests: `./gradlew :shared:testAndroidHostTest`
- iOS simulator tests: `./gradlew :shared:iosSimulatorArm64Test`

Playground operation-lifecycle coverage lives in `:shared`:

- `PlaygroundViewModelTest` (jvmTest) — a slow fake query discarded after ResetFlow, after a
  live-provider toggle, and after a project-id change (only the latest generation applies).
  `NonCancellable` gated fakes also complete after Job cancellation so generation / request-token
  / address-identity checks — not cooperative cancellation — discard stale UTxO and params
  results after ResetFlow, address edit/fill, repeated loads, and provider-configuration changes.
  Repeated same-generation Funds, Build, Sign, and Submit requests discard the first
  `NonCancellable` completion; Wallet restore is synchronous and has no request token.
  Upstream reruns discard in-flight and completed downstream results (Funds clears
  Build/Sign/Submit; Build clears Sign/Submit; Sign clears Submit) so Continue cannot
  advance on a stale later step.
  Toggle-off and project-id change invalidate the live factory cache before the next lookup.
- `PlaygroundReducerTest` (commonTest) — diagnostic and guided-operation request tokens
  increment on each start and on ResetFlow / provider-configuration change; starting Funds,
  Build, or Sign clears completed downstream guided results and increments those tokens;
  ResetFlow converts diagnostic Loading to Empty and keeps completed diagnostic results;
  stale token/address applies are no-ops.
- `PlaygroundProviderFactoryTest` (commonTest) — Mock vs LivePreprod mode, live-cache reuse,
  cache drop when the id changes or live mode is disabled, and explicit `invalidateLiveCache()`
  without an intervening mock lookup (dummy ids never appear in assertion messages).
- `PlaygroundTransactionDraftPresenterTest` — `InsufficientFunds` includes
  `excludedNativeAssetUtxoCount` / `excludedNativeAssetLovelace` when those fields are non-zero.
- `PlaygroundMockFlowDesktopTest` (jvmTest) — the seeded guided mock flow is unchanged
  (Funds/Build/Sign succeed; Submit still reports submission not supported).

The full Phase 1 target matrix is intentionally not equivalent across platforms:

- Android is the runtime validation surface for the Playground.
- iOS simulator/device execution requires a local macOS/Xcode environment; compile/link checks are
  run where that environment is unavailable.
- JVM signing runtime coverage currently requires the committed macOS native artifacts. Linux and
  Windows JVM signing artifacts are not included.

Documentation checks (no banned marketing/security words; keyword presence):

```bash
rg -n "TESTING|fixtures|test vector|commonTest|jvmTest|iosSimulatorArm64Test|testAndroidHostTest" README.md docs/ core/README.md shared/README.md
rg -n -i "secure|safe|hardened|audited|production-ready|guaranteed|cryptographically safe|bank-grade|battle-tested" README.md docs/ core/README.md shared/README.md
```
