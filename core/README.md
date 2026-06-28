# :core

The UI-free seed of the Kardano SDK core. This is where the shared, deterministic SDK
logic will live as Phase 0 progresses.

## Status

Phase 0 — pre-alpha, experimental. Not audited. Not for real funds.

## Purpose

- Hold UI-free, Kotlin Multiplatform SDK logic shared across Android, iOS, and JVM/Desktop.
- Stay free of Compose and any UI dependency.
- Use `explicitApi()` so the public surface is deliberate, with KDoc on every public
  declaration.

## Targets

- Android library (`org.sarmidev.kardano.core`)
- JVM/Desktop
- iosArm64, iosSimulatorArm64

## In scope (current)

- `Platform` / `getPlatform()` — a UI-free platform descriptor (`expect`/`actual`).

## Out of scope

- UI / Compose.
- Cryptography, key handling, mnemonics, or transaction signing.
- Network/IO, providers, or wallet behavior.
- Primitives, hex, Bech32, CBOR, and address validation are not implemented yet; they are
  planned for later Phase 0 blocks (see [docs/ROADMAP.md](../docs/ROADMAP.md)).

## Consumers

`:shared` depends on `:core`. The sample apps depend on `:shared`, so they receive `:core`
transitively; they do not depend on `:core` directly yet.

## Testing

Shared SDK-logic tests go in `core/src/commonTest`; a minimal `core/src/jvmTest` smoke test
verifies JVM test wiring. Fixtures live under `core/src/commonTest/resources/fixtures/`. See
[docs/TESTING.md](../docs/TESTING.md) for source-set expectations and the test-vector policy.

- Core (JVM) tests: `./gradlew :core:jvmTest`
