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
  malformed/blank bodies), cancellation rethrow, oversized-page rejection, and the UTxO
  cap: an internal `UtxoPaginationPolicy` test seam (not public) exercises an exact-cap
  empty one-item probe (`Ok`), an exact-cap probe HTTP 404 (`Ok`, same empty/end
  semantics as ordinary UTxO pagination), a non-empty probe (`ResultTruncated`), and a
  non-404 probe HTTP failure (typed `RemoteStatus`), without allocating 10_000 entries.
  `UtxoPaginationPolicyTest` asserts construction-time bounds (positive
  `pageCount`/`maxPages`, `maxPages < Int.MAX_VALUE`, checked `pageCount * maxPages`)
  using extreme `Int` values only — no large page allocations.
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
- `BlockfrostOkHttpEngineTest` (androidHostTest) asserts the effective OkHttp client
  Ktor 3.5.1 would build from the production `defaultHttpClient` engine config
  (`retryOnConnectionFailure == false` after Ktor's default `config` lambda), and that
  a preconfigured client alone is overwritten by that default. The standalone
  `blockfrostOkHttpClient()` helper is still asserted as defense in depth. That is the
  engine-level submit-replay switch, not Ktor `HttpRequestRetry`, and is not a live
  connection-failure replay.
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

Documentation and claim-language checks:

```bash
rg -n "TESTING|fixtures|test vector|commonTest|jvmTest|iosSimulatorArm64Test|testAndroidHostTest" README.md docs/ core/README.md shared/README.md
python3 -m unittest scripts.tests.test_check_restricted_claims scripts.tests.test_check_handoff_archive
python3 scripts/check_handoff_archive.py
python3 scripts/check_restricted_claims.py
```

`scripts/check_restricted_claims.py` classifies each restricted-claim phrase
match on its own (never a whole-line exclusion), reports `path:line:column`,
and prefers the longest phrase. It enumerates tracked files with
`git ls-files -z` and scans `.md`, `.mdc`, `.html`, `.kt`, `.kts`, `.swift`,
`.xml`, `.properties`, `.toml`, `.yaml`, `.yml`, and `.json`. Exclusions are
exact files only. CI runs the unit tests and the archive byte check before the
scan. It does not scan credentials.

`scripts/check_handoff_archive.py` restores the six documented archive link
rewrites at the byte level (no newline normalization) and hashes the result
with SHA-256. The archived snapshot keeps its original trailing blank line;
`.gitattributes` scopes `whitespace=-blank-at-eof` to that file only so
`git diff --check` stays clean without a global whitespace suppress.

Full-history credential scan (Gitleaks CLI, not a third-party Action wrapper):

```bash
python3 -m unittest scripts.tests.test_gitleaks_allowlist
python3 scripts/install_gitleaks.py
python3 scripts/check_gitleaks.py
```

The installer verifies the official `gitleaks_*_checksums.txt` digest and the
selected archive digest, reads the expected member into memory, and writes the
binary through an exclusive temporary sibling (mode `0755`) before an atomic
replace. It refuses a destination symlink and a world-writable archive member.
The binary is written to `.gitleaks-bin/` (gitignored) and is never committed.
CI runs the helper/installer/allowlist tests before install and scan. Output
is redacted. Allowlists are match-level only (cited CIP-19 payment-credential
hex **and** an exact repo-root path, including the helper). See
`.gitleaks.toml` and `docs/RELEASING.md`.
