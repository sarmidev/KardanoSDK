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
- `KardanoResult<T, E>` — the SDK's typed success-or-failure type (`Ok` / `Err`) used by
  failable APIs instead of throwing.
- `Network` — the Cardano network ids the protocol defines (`TESTNET` = 0, `MAINNET` = 1);
  `Network.fromId` rejects unsupported ids with a typed error.
- `Lovelace` — a non-negative lovelace amount (`0..Long.MAX_VALUE`); `Lovelace.of` rejects
  negative values without truncation.
- `TxHash` (exactly 32 bytes), `PolicyId` (exactly 28 bytes), and `AssetName` (0..32 bytes)
  — structural byte containers with defensive copies, content-based equality, and a shared
  `ByteSizeError` for invalid lengths. They do not parse or render hex.
- `UtxoRef` — a `TxHash` plus a non-negative output index (`0..Long.MAX_VALUE`); structural
  only, it does not check that the output exists or is unspent.

## Out of scope

- UI / Compose.
- Cryptography, key handling, mnemonics, or transaction signing.
- Network/IO, providers, or wallet behavior.
- Hex string APIs, Bech32, CBOR, and address validation are not implemented yet; they are
  planned for later Phase 0 blocks (see [docs/ROADMAP.md](../docs/ROADMAP.md)).
- `Address` is deferred to Block 0.7, where address parsing and structural (CIP-19)
  validation belong.

## Consumers

`:shared` depends on `:core`. The sample apps depend on `:shared`, so they receive `:core`
transitively; they do not depend on `:core` directly yet.

## Testing

Shared SDK-logic tests go in `core/src/commonTest`; a minimal `core/src/jvmTest` smoke test
verifies JVM test wiring. Fixtures live under `core/src/commonTest/resources/fixtures/`. See
[docs/TESTING.md](../docs/TESTING.md) for source-set expectations and the test-vector policy.

- Core (JVM) tests: `./gradlew :core:jvmTest`
