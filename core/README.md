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

## Package layout

The SDK logic is organized into purpose-named packages (see
[docs/DECISIONS/0003-core-package-structure.md](../docs/DECISIONS/0003-core-package-structure.md)):

- `org.sarmidev.kardano` — cross-cutting types: `KardanoResult`, `Platform` / `getPlatform`.
- `org.sarmidev.kardano.primitives` — `Network`, `Lovelace`, `TxHash`, `PolicyId`,
  `AssetName`, `UtxoRef`, `UtxoRefError`, `ByteSizeError`.
- `org.sarmidev.kardano.encoding.hex` — `Hex`, `HexError`.
- `org.sarmidev.kardano.encoding.bech32` — `Bech32`, `Bech32Variant`, `Bech32Decoded`,
  `Bech32Error`, `CardanoHrp`, `CardanoBech32`, `CardanoBech32Error`.
- `org.sarmidev.kardano.encoding.cbor` — `Cbor`, `CborValue`, `CborError`.
- `org.sarmidev.kardano.address` — `Address`, `AddressType`, `AddressCredential`,
  `CredentialKind`, `AddressPointer`, `PointerField`, `AddressError`.

These are packages within the single `:core` module, not separate Gradle modules; Gradle
module splits are deferred (ADR-0003). This is a pre-alpha SDK: type names are stable across
this reorganization, but fully qualified names and imports moved into the packages above.

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
- `Cbor` — a bounded decoder/encoder for the Phase 0 definite-length CBOR subset (RFC 8949).
  Supported types, exposed as the sealed `CborValue`: unsigned integers (`CborUnsigned`) and
  negative integers (`CborNegative`) within the signed `Long` range, definite-length byte
  strings (`CborByteString`), definite-length UTF-8 text strings (`CborTextString`),
  definite-length arrays (`CborArray`), and definite-length maps (`CborMap`, an ordered list of
  `CborEntry` pairs — not a Kotlin `Map`). `Cbor.decode` returns a `KardanoResult<CborValue,
  CborError>` and `Cbor.encode` returns a `KardanoResult<ByteArray, CborError>` (neither
  throws). The encoder emits canonical (shortest-form) definite-length output. SDK-owned named
  limits (`CBOR_MAX_INPUT_BYTES`, `CBOR_MAX_BYTESTRING_BYTES`, `CBOR_MAX_STRING_BYTES`,
  `CBOR_MAX_NESTING_DEPTH` = 64, `CBOR_MAX_COLLECTION_ELEMENTS` = 65536) are enforced before any
  buffer is allocated or any collection element is read, and no buffer is allocated from an
  untrusted declared length or element count. Maps follow the Phase 0 deterministic rule (per
  ADR-0001, RFC 8949 §4.2.1): keys must be in strictly ascending order by the bytewise
  comparison of their canonical encoding, with no duplicates — the decoder rejects maps that
  violate this (`NonCanonicalMapKeyOrder` / `DuplicateMapKey`) and the encoder requires
  already-ordered, duplicate-free entries and rejects rather than reordering. This Phase 0
  deterministic rule is not asserted to be final Cardano transaction-serialization
  compatibility. Tags (incl. bignum tags 2/3), floats/simple/null/undefined, indefinite
  lengths, reserved additional info, non-canonical encodings, out-of-range integers/counts,
  over-deep nesting, over-large collections, malformed UTF-8, over-limit input, and trailing
  bytes are rejected with a typed `CborError`, never normalized.
- `Address` — structural CIP-19 address parsing (Block 0.7). `Address.parse(bech32)`
  returns a `KardanoResult<Address, AddressError>` (never throws) for the Shelley address
  types parsed so far: base (`addr` / `addr_test`, CIP-19 header types 0-3), pointer
  (`addr` / `addr_test`, header types 4/5), enterprise (`addr` / `addr_test`, header types
  6/7), and reward/stake (`stake` / `stake_test`, header types 14/15). It decodes via
  `CardanoBech32`, converts the 5-bit data to bytes, reads the header byte, resolves the
  network id through `Network`, and rejects any disagreement between the HRP and the header
  network nibble or address family, unsupported header types, bad lengths, and bad
  checksums/padding with a typed `AddressError` — nothing is normalized. It exposes the
  `Network`, `AddressType`, the `CardanoHrp`, two explicit nullable credentials
  (`paymentCredential` and `stakeCredential`, each an `AddressCredential` — a `CredentialKind`,
  `KEY` or `SCRIPT`, plus a 28-byte hash), and a nullable chain `pointer`. Which are non-null
  depends on the type: enterprise has only `paymentCredential`, reward/stake has only
  `stakeCredential`, base has both (for base, `stakeCredential` is the CIP-19 delegation
  credential and may itself be a script hash), and pointer has `paymentCredential` plus
  `pointer`. A pointer address's delegation part is a chain pointer (`AddressPointer`: the
  three non-negative `Long` coordinates `slot` / `transactionIndex` / `certificateIndex`),
  decoded from three CIP-19 variable-length unsigned integers; over-long (non-canonical),
  truncated, out-of-range, and trailing-byte pointer encodings are rejected with a typed
  `AddressError` (the pointer overflow check runs before each shift, so no signed-`Long`
  wraparound is relied on). `AddressCredential` and `AddressPointer` have private constructors
  and are built only by the parser through length/range-validated internal factories. All byte
  arrays are defensively copied and use content equality; `toString` renders no credential
  bytes. **Structural validation only**: it does not prove an address exists on-chain, is
  owned, is controllable, or is spendable, it does not verify a credential is a real
  key/script hash, and it does not check that a pointer refers to an on-chain certificate.
  Byron (type 8) addresses, Base58, and raw-byte/hex constructors are deferred beyond Block
  0.7 (`Address.parse` is the only constructor).

## Out of scope

- UI / Compose.
- Cryptography, key handling, mnemonics, or transaction signing.
- Network/IO, providers, or wallet behavior.
- The CBOR subset above covers primitives plus definite-length arrays and maps only (no tags,
  bignums, floats, simple values, or indefinite lengths) and does not interpret Cardano
  semantics. The `Bech32` codec is generic and does not restrict the HRP to Cardano prefixes;
  the `CardanoBech32` wrappers add the HRP allowlist but perform no address parsing or CIP-19
  structural validation (that belongs to `Address`). Primitive-specific hex helpers (e.g.
  `TxHash.fromHex`) are intentionally not added; use the generic `Hex` utility.
- `Address` parsing covers the base, pointer, enterprise, and reward/stake Shelley CIP-19
  Bech32 types — the settled Block 0.7 scope. Byron addresses, Base58 decoding, and
  raw-byte/hex address constructors are deferred beyond Block 0.7 (see
  [docs/ROADMAP.md](../docs/ROADMAP.md)).

## Consumers

`:shared` depends on `:core`. The sample apps depend on `:shared`, so they receive `:core`
transitively; they do not depend on `:core` directly yet.

## Testing

Shared SDK-logic tests go in `core/src/commonTest`; a minimal `core/src/jvmTest` smoke test
verifies JVM test wiring. Fixtures live under `core/src/commonTest/resources/fixtures/`. See
[docs/TESTING.md](../docs/TESTING.md) for source-set expectations and the test-vector policy.

- Core (JVM) tests: `./gradlew :core:jvmTest`
