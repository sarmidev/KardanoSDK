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
- `Hex` — a bounded, generic hex encoder/decoder. `Hex.encode` and `Hex.decode` both return a
  `KardanoResult` (`<String, HexError>` and `<ByteArray, HexError>` respectively; neither
  throws). `Hex.decode` accepts mixed case and rejects odd-length, non-hex, and over-limit
  input (`Hex.MAX_INPUT_CHARS`) before allocating; `Hex.encode` emits canonical lowercase and
  rejects over-limit input (`Hex.MAX_ENCODE_INPUT_BYTES`, set to half of
  `Hex.MAX_INPUT_CHARS` so encoded output always stays within what `Hex.decode` accepts as
  input) before allocating the doubled-length output buffer. Neither interprets the bytes it
  converts. `Hex.encode`'s `KardanoResult` return type is a pre-alpha API change from an
  earlier, unbounded, non-failable signature — see `CHANGELOG.md`.
- `Bech32` — a bounded, generic Bech32/Bech32m codec (the encoding layer of BIP-173/BIP-350).
  It works at the **5-bit data layer**: `Bech32.encode(hrp, data, variant)` takes 5-bit data
  values (`0..31`) and emits canonical lowercase; `Bech32.decode(input)` auto-detects the
  `Bech32Variant`, returns a `KardanoResult<Bech32Decoded, Bech32Error>` (never throws),
  rejects mixed case, and validates the HRP, separator, data charset, variant checksum, and
  the SDK-owned limits (`MAX_INPUT_CHARS`, `MAX_HRP_CHARS`, `MAX_DATA_VALUES`) before
  allocating. It performs structural checksum/charset validation only; it does not apply
  Cardano HRP semantics or parse addresses. A 5-bit/8-bit `convertBits` helper is internal and
  bounds its output in both directions before allocating: `MAX_DATA_BYTES` for the 8-bit
  (5→8) direction and `MAX_DATA_VALUES` for the 5-bit (8→5) direction — the latter closes a
  gap where only the former was enforced (finding W6-3).
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
  definite-length arrays (`CborArray`), definite-length maps (`CborMap`, an ordered list of
  `CborEntry` pairs — not a Kotlin `Map`), and (added narrowly in Block 1.10b, ADR-0015 §3 /
  ADR-0001 addendum) the three fixed major-type-7 simple values `false`/`true` (`CborBool`) and
  `null` (`CborNull`). `Cbor.decode` returns a `KardanoResult<CborValue,
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
  compatibility. Tags (incl. bignum tags 2/3), `undefined`, every other simple value, floats,
  indefinite lengths, reserved additional info, non-canonical encodings, out-of-range
  integers/counts, over-deep nesting, over-large collections, malformed UTF-8, over-limit
  input, and trailing bytes are rejected with a typed `CborError`, never normalized.
  `Cbor.encode`'s assembled output is also bounded: per-element limits alone do not stop a
  wide, flat collection of many near-limit elements from assembling into an output larger
  than any single limit, so the running total is checked with `Long` arithmetic (reusing
  `CBOR_MAX_INPUT_BYTES` as the output bound) and rejected with `CborError.OutputTooLong`
  before the final buffer is allocated or concatenated.
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
  bytes. It also exposes `bech32`, the validated source string exactly as passed to
  `Address.parse` (not an independently encoded value and not a `toBech32` re-encoder, which
  stays deferred to Block 1.7); `bech32` is excluded from `equals`/`hashCode`/`toString` so the
  structural equality contract is unchanged. **Structural validation only**: it does not prove an address exists on-chain, is
  owned, is controllable, or is spendable, it does not verify a credential is a real
  key/script hash, and it does not check that a pointer refers to an on-chain certificate.
  Byron (type 8) addresses, Base58, and raw-byte/hex constructors are deferred beyond Block
  0.7 (`Address.parse` remains the only *parsing* constructor).
- **Address generation (Block 1.7a)** — a minimal, structural base-address builder and a
  canonical Bech32 encoder, gated on
  [docs/DECISIONS/0012-address-encoding-and-roundtrip.md](../docs/DECISIONS/0012-address-encoding-and-roundtrip.md):
  - `AddressCredential.keyHash(hash)` / `AddressCredential.scriptHash(hash)` — public
    factories on `AddressCredential`'s now-public companion. Each returns a
    `KardanoResult<AddressCredential, AddressError>`, length-checking `hash` (must be
    exactly 28 bytes, a `blake2b-224` digest) and defensive-copying it before returning
    `AddressError.InvalidCredentialLength` on a mismatch or the credential on success.
  - `Address.baseAddress(network, paymentCredential, stakeCredential)` — builds a CIP-19
    base address (header types 0-3) from two already-computed credentials and a `Network`,
    returning `KardanoResult<Address, AddressError>`. This is the only generation builder in
    1.7a; enterprise, reward/stake, and pointer builders remain deferred. The builder accepts
    either `Network` (a pure function, used by `:core`'s own tests to roundtrip cited
    mainnet vectors); callers needing the "no mainnet" boundary (for example the sample app)
    enforce it themselves by only ever passing `Network.TESTNET`.
  - `Address.toBech32(): String` — returns the canonical lowercase Bech32 encoding derived
    from the address's own bytes and HRP, computed once at construction for both parsed and
    generated addresses. Unlike `bech32` (the exact, unmodified source string for a *parsed*
    address, or the same canonical value for a *generated* one, since generation has no
    separate source), `toBech32()` canonicalizes **every currently supported parsed type**
    (base, enterprise, reward, pointer; mainnet and testnet), not only base, because it only
    depends on the address's own `rawBytes + hrp`.
  - Structural construction/encoding only, same disclaimer as `Address.parse`: none of these
    APIs prove an address exists on-chain, is owned, or is spendable, and they do not verify
    that a credential hash is a real key/script hash.
  - `:crypto` is not touched by this capability: hashing a derived public key into a
    28-byte credential hash stays a two-call composition the caller performs directly
    (`ExtendedPublicKey.publicKeyBytes()` → `Hashing.blake2b224(...)`).

## Out of scope

- UI / Compose.
- Cryptography, key handling, mnemonics, or transaction signing. See
  [docs/DECISIONS/0004-crypto-strategy.md](../docs/DECISIONS/0004-crypto-strategy.md) for
  the future cryptography strategy.
- Network/IO, providers, or wallet behavior.
- The CBOR subset above covers primitives plus definite-length arrays and maps, plus the three
  fixed simple values `false`/`true`/`null` (no tags, bignums, floats, `undefined`, or any
  other simple value, and no indefinite lengths) and does not interpret Cardano semantics. The
  `Bech32` codec is generic and does not restrict the HRP to Cardano prefixes;
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
