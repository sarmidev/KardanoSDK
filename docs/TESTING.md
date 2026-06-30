# Testing Guide — Kardano SDK (Phase 0)

How tests, fixtures, and external test vectors are organized in this repository. This
guide complements the testing rules in
[docs/AI_WORKING_AGREEMENT.md](AI_WORKING_AGREEMENT.md) (the "Unit testing policy" and
"Test integrity rules" sections) and does not replace them. If anything here ever
conflicts with the working agreement, the working agreement wins.

> Phase 0 status: pre-alpha, experimental. Not audited. Not for real funds. No
> cryptography, key handling, or transaction signing is implemented or tested.

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

- `:core` — UI-free SDK core. Shared logic tests go in `core/src/commonTest`. A minimal
  `core/src/jvmTest` smoke test verifies JVM test wiring for the module. As Phase 0
  primitives and parsers land, their tests belong in `core/src/commonTest`.
- `:shared` — sample/UI host. It already carries example tests in `commonTest`, `jvmTest`,
  `androidHostTest`, and `iosTest` that demonstrate the wiring per target. Protocol
  vectors and SDK-logic tests belong in `:core`, not here.

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
- Desktop (JVM) tests: `./gradlew :shared:jvmTest`
- Android host (JVM-hosted) tests: `./gradlew :shared:testAndroidHostTest`
- iOS simulator tests: `./gradlew :shared:iosSimulatorArm64Test`

Documentation checks (no banned marketing/security words; keyword presence):

```bash
rg -n "TESTING|fixtures|test vector|commonTest|jvmTest|iosSimulatorArm64Test|testAndroidHostTest" README.md docs/ core/README.md shared/README.md
rg -n -i "secure|safe|hardened|audited|production-ready|guaranteed|cryptographically safe|bank-grade|battle-tested" README.md docs/ core/README.md shared/README.md
```
