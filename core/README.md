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
- `Hex` — a bounded, generic hex encoder/decoder. `Hex.encode` emits canonical lowercase;
  `Hex.decode` returns a `KardanoResult<ByteArray, HexError>` (never throws), accepts mixed
  case, and rejects odd-length, non-hex, and over-limit input (`Hex.MAX_INPUT_CHARS`) before
  allocating. It does not interpret the bytes it converts.
- `Bech32` — a bounded, generic Bech32/Bech32m codec (the encoding layer of BIP-173/BIP-350).
  It works at the **5-bit data layer**: `Bech32.encode(hrp, data, variant)` takes 5-bit data
  values (`0..31`) and emits canonical lowercase; `Bech32.decode(input)` auto-detects the
  `Bech32Variant`, returns a `KardanoResult<Bech32Decoded, Bech32Error>` (never throws),
  rejects mixed case, and validates the HRP, separator, data charset, variant checksum, and
  the SDK-owned limits (`MAX_INPUT_CHARS`, `MAX_HRP_CHARS`, `MAX_DATA_VALUES`) before
  allocating. It performs structural checksum/charset validation only; it does not apply
  Cardano HRP semantics or parse addresses. A 5-bit/8-bit `convertBits` helper (bounded by
  `MAX_DATA_BYTES`) is internal.
- `CardanoBech32` — thin Cardano-facing wrappers over `Bech32`. `CardanoBech32.encode` takes
  a `CardanoHrp` (the allowlist `addr` / `addr_test` / `stake` / `stake_test`) and forces the
  Bech32 variant; `CardanoBech32.decode` delegates to `Bech32.decode`, then accepts the
  result only if the HRP is allowlisted (checked first) and the variant is Bech32 (checked
  second), returning a `KardanoResult<Bech32Decoded, CardanoBech32Error>` (never throws).
  Generic engine failures propagate via `CardanoBech32Error.Underlying`. This is HRP
  allowlist plus Bech32 checksum/charset validation only — not CIP-19 structural address
  validation: it does not parse payloads, inspect header bytes, or read the network id.

## Out of scope

- UI / Compose.
- Cryptography, key handling, mnemonics, or transaction signing.
- Network/IO, providers, or wallet behavior.
- CBOR and address validation are not implemented yet; they are planned for later Phase 0
  blocks (see [docs/ROADMAP.md](../docs/ROADMAP.md)). The `Bech32` codec is generic and does
  not restrict the HRP to Cardano prefixes; the `CardanoBech32` wrappers add the HRP allowlist
  but perform no address parsing or CIP-19 structural validation (that belongs to Block 0.7).
  Primitive-specific hex helpers (e.g. `TxHash.fromHex`) are intentionally not added; use the
  generic `Hex` utility.
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
