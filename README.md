# Kardano SDK

Open-source Kotlin Multiplatform SDK for native Cardano mobile apps, with shared core
logic for Android, iOS, and JVM/Desktop. Group: `org.sarmidev.kardano`.

## Status

> **Phase 0 — pre-alpha, experimental. Not audited. Not for real funds.**

Phase 0 builds a tested, documented foundation before any wallet creation, transaction
signing, or real network flows. The SDK core is UI-free. This is not the MVP and must not
be used with mainnet funds or real private keys.

## In scope (Phase 0)

- Project structure, module boundaries, and governance/AI working rules.
- Testing infrastructure and test-vector policy.
- Core primitives (byte wrappers, value types).
- Hex and base encoding utilities.
- Bech32 / Bech32m investigation and implementation decision.
- Minimal documented CBOR subset policy and implementation decision.
- Structural address parsing and validation (CIP-19).
- Crypto strategy documentation (`expect`/strategy only — no implementations).

## Out of scope (Phase 0)

- Transaction building, serialization for submission, or signing.
- Custom cryptography or handwritten cryptographic algorithms.
- Key generation, mnemonics (BIP-39), or HD derivation.
- Real mnemonics, private keys, or anything touching real funds.
- Network/IO, node clients, wallet connection, or provider integration.
- Plutus support, staking/delegation, governance, Hydra, or Mithril.
- Full CIP-30/CIP-95 support.

## Documentation

- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) — product summary, positioning, scope.
- [docs/ROADMAP.md](docs/ROADMAP.md) — phases and Phase 0 work blocks.
- [docs/HANDOFF.md](docs/HANDOFF.md) — current state and session handoff.
- [docs/AI_WORKING_AGREEMENT.md](docs/AI_WORKING_AGREEMENT.md) — how humans and AI agents change this repo.
- [docs/TESTING.md](docs/TESTING.md) — test source sets, fixture layout, and test-vector policy.
- [docs/SECURITY.md](docs/SECURITY.md) — security policy and reporting.
- [docs/DECISIONS/](docs/DECISIONS/) — architecture decision records (ADRs).

## Building and testing

This is a Kotlin Multiplatform project targeting Android, iOS, and JVM/Desktop. Current
modules:

- `:core` — UI-free SDK core seed (no Compose). See [core/README.md](core/README.md).
- `:shared` — temporary sample/UI host; builds the iOS `Shared` framework. See [shared/README.md](shared/README.md).
- `:androidApp`, `:desktopApp` — sample apps (plus the `iosApp` Xcode entry point).

Build:

- Android app: `./gradlew :androidApp:assembleDebug`
- Desktop app:
  - Hot reload: `./gradlew :desktopApp:hotRun --auto`
  - Standard run: `./gradlew :desktopApp:run`
- iOS app: open the `iosApp` directory in Xcode and run it from there.

Test (run per module, e.g. `:core` and `:shared`). See [docs/TESTING.md](docs/TESTING.md)
for source-set expectations, fixture layout, and the test-vector policy:

- Core (JVM) tests: `./gradlew :core:jvmTest`
- Android tests: `./gradlew :shared:testAndroidHostTest`
- Desktop tests: `./gradlew :shared:jvmTest`
- iOS tests: `./gradlew :shared:iosSimulatorArm64Test`

## Security and contact

Kardano SDK is in Phase 0 (pre-alpha) and has not been audited. Do not use it with mainnet
funds or real private keys. To report a security issue, please follow the process in
[docs/SECURITY.md](docs/SECURITY.md): open a GitHub Security Advisory on this repository, or
email the maintainer directly, instead of filing a public issue.

## License

A license has not yet been selected for this repository.

---

Learn more about [Kotlin Multiplatform](https://www.jetbrains.com/help/kotlin-multiplatform-dev/get-started.html).
