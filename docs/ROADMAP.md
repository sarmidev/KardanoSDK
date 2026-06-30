# Kardano SDK - Roadmap

## Current Status

The project has been created from the Kotlin Multiplatform wizard.

Selected targets:

- Android.
- iOS.
- JVM/Desktop.

Current priority:

> Build a disciplined Phase 0 foundation before implementing wallet behavior, signing or transaction submission.

## Phase 0 - Core Foundation

Goal:

Create the technical base of Kardano SDK before wallet creation, transaction signing, transaction building or real network flows.

Phase 0 is complete only when the repository has structure, tests, documentation, primitives, parser policies and technical decisions strong enough to start the real MVP.

Strict non-goals:

- No transaction signing.
- No custom cryptography.
- No real mnemonics or private keys.
- No real funds.
- No claims of deployment readiness.

## Phase 0 Work Blocks

### 0.1 Project Governance And AI Rules

Status: complete.

Goal:

Define how humans and AI agents work in the repository.

Deliverables:

- `docs/AI_WORKING_AGREEMENT.md`
- `docs/SECURITY.md`
- Cursor rules.
- `docs/PROJECT_BRIEF.md`
- `docs/ROADMAP.md`
- `docs/HANDOFF.md`
- Initial decision record structure.

Acceptance criteria:

- Phase 0 boundaries are explicit.
- AI agents know what they can and cannot do.
- Security-sensitive areas are documented.
- No code implementation starts without rules.

### 0.2 SDK-Oriented Module Structure

Status: complete.

Goal:

Move from wizard-generated app structure toward a clean SDK architecture.

Outcome:

- Introduced a UI-free `:core` module (see `docs/DECISIONS/0002-module-structure.md`).
- Moved the `Platform` `expect`/`actual` declarations from `:shared` into `:core`.
- `:shared` now depends on `:core` and remains the sample/UI host (keeps Compose and builds
  the iOS `Shared` framework). Sample apps are unchanged.
- This `:core` + `:shared` split is the settled Phase 0 module structure; further splits are
  deferred until there is code to justify them.

Current modules:

- `:core` (UI-free SDK core seed)
- `:shared` (sample/UI host; builds the iOS `Shared` framework)
- `:androidApp`
- `:desktopApp`
- `iosApp` (Xcode entry point)

Deferred candidate future modules (names are not final; do not create yet):

- `:crypto`
- `:wallet`
- `:tx`
- `:provider`
- `:sample:android`
- `:sample:ios`
- `:sample:desktop`

Important:

Do not over-split too early. Start with the minimum structure that keeps the SDK clean.

Acceptance criteria:

- Gradle sync works.
- Android target compiles.
- JVM/Desktop target compiles.
- iOS target compiles where available.
- Sample apps remain usable or are intentionally adjusted.
- No business logic is hidden inside sample apps.

### 0.3 Testing Infrastructure

Status: complete.

Goal:

Create the testing foundation before implementing protocol logic.

Deliverables:

- `commonTest` structure.
- `jvmTest` structure.
- Android test strategy.
- iOS/native test awareness.
- Fixture folder structure.
- Test vector policy.

Outcome:

- Added `docs/TESTING.md` documenting test source-set expectations (`commonTest`,
  `jvmTest`, Android host tests, iOS tests), fixture layout, the external test-vector
  policy (verbatim from cited specs; no AI-invented vectors), and the verification commands.
- Added a fixture folder structure under `core/src/commonTest/resources/fixtures/` with a
  top-level `README.md` and placeholder subfolders (`bech32/`, `cbor/`, `address/`) that
  name their future authoritative sources (BIP-173/350, RFC 8949 Appendix A, CIP-19). No
  protocol vectors are added yet. A note in `shared/src/commonTest/resources/fixtures/`
  keeps protocol vectors in `:core`.
- Added a minimal `:core` `jvmTest` smoke test (`JvmTestWiringTest`) that verifies JVM test
  wiring without adding protocol behavior.
- Linked `docs/TESTING.md` from `README.md`, `core/README.md`, and `shared/README.md`.
- Verified: `:core:jvmTest`, `:shared:jvmTest`, and `:shared:testAndroidHostTest` pass.
  `:shared:iosSimulatorArm64Test` compiles and links; running the simulator requires a
  macOS/Xcode iOS simulator SDK and could not execute on the current machine.

Acceptance criteria:

- Unit tests can run locally.
- Test naming is consistent.
- Fixtures are clearly separated from implementation.
- External vectors must cite their source.
- AI must not invent vectors to match implementation behavior.

### 0.4 Core Primitives

Status: complete.

Goal:

Introduce value types for basic Cardano concepts.

Candidate primitives:

- `Network`
- `Lovelace`
- `TxHash`
- `PolicyId`
- `AssetName`
- `Address` (deferred to Block 0.7)
- `UtxoRef`

Outcome (first step):

- Added a shared `KardanoResult<T, E>` (`Ok` / `Err`) typed success-or-failure type in
  `:core`, used by failable factories instead of throwing (throwing across the Swift/ObjC
  boundary crashes iOS).
- Added `Network` (`TESTNET` = 0, `MAINNET` = 1) with `Network.fromId` returning a typed
  error for unsupported ids. It makes no preview/preprod claim beyond the network id.
- Added `Lovelace`, a `@JvmInline value class` over `Long` with the documented range
  `0..Long.MAX_VALUE`; `Lovelace.of` rejects negatives without truncation. Maximum ADA
  supply enforcement is deferred (a protocol concern, not a structural primitive concern).
  No arithmetic operators are exposed yet, avoiding overflow surface.
- Tests in `core/src/commonTest` cover valid/invalid/edge cases for both types. No fixtures
  or external vectors were added (these are hand-written primitive cases, not protocol
  vectors). No dependencies or Gradle changes; ADR-0001 was Open at the time of this step;
  it is now Accepted.

Outcome (final step):

- Added byte-backed structural value types in `:core`: `TxHash` (exactly 32 bytes),
  `PolicyId` (exactly 28 bytes), `AssetName` (0..32 bytes), and `UtxoRef` (a `TxHash` plus a
  non-negative output index, `0..Long.MAX_VALUE`). The three byte-length types share a
  `ByteSizeError` (`Fixed` / `Range`); `UtxoRef` has its own `UtxoRefError.NegativeIndex`.
- Each byte container copies its input on construction, returns a copy from `toByteArray()`,
  and uses `contentEquals` / `contentHashCode` for equality. `toString()` is structural and
  does not render bytes or hex. These are structural containers only: they do not verify
  hash/script origin, on-chain existence, spendability, or any hex representation.
- Tests in `core/src/commonTest` cover exact-length and range validation, length boundaries,
  defensive copying (construction and accessor), and content equality/hashCode, plus
  `UtxoRef` index validation. Hand-written cases only; no fixtures or external vectors.
- `Address` is deferred to Block 0.7 because address parsing and structural (CIP-19)
  validation belong there. No hex string APIs were added (hex is Block 0.5). No
  dependencies or Gradle changes; ADR-0001 was Open at the time of this step; it is now
  Accepted.

Acceptance criteria:

- Public APIs have KDoc.
- Invalid values are rejected.
- Valid, invalid and edge cases are tested.
- ByteArray wrappers use defensive copies.
- ByteArray equality uses `contentEquals` / `contentHashCode`.
- No silent truncation of numeric values.

### 0.5 Encoding Utilities

Goal:

Implement bounded utilities for public encoded formats.

Decision status:

- ADR-0001 (CBOR/parser policy) is **Accepted**: Bech32/Bech32m use a constrained internal
  implementation with no external dependency. Hex lands first, then Bech32/Bech32m must be
  implemented according to ADR-0001 (variant support, mixed-case rejection, lowercase
  encoder output, HRP/separator/charset/checksum/padding validation, SDK-owned Cardano-mode
  limits, and the `addr`/`addr_test`/`stake`/`stake_test` HRP allowlist).

Candidate areas:

- Hex.
- Bech32.
- Base encodings only if needed.

Status: complete (Hex, the generic Bech32/Bech32m engine, and the Cardano HRP allowlist
wrappers have landed).

Outcome (Hex step):

- Added a generic, bounded `Hex` codec in `:core` (`Hex.encode` / `Hex.decode`) with a typed
  `HexError` (`InputTooLong`, `OddLength`, `InvalidCharacter`). `encode` emits canonical
  lowercase; `decode` returns `KardanoResult<ByteArray, HexError>` (never throws), accepts
  lowercase/uppercase/mixed case (hex is checksum-free, so case is unambiguous to decode),
  and rejects odd-length, non-hex, and over-limit input. A named SDK-owned limit
  `Hex.MAX_INPUT_CHARS` is enforced, and length/characters are validated before the output
  `ByteArray` is allocated (no allocation from an untrusted length; no silent truncation).
- Tests in `core/src/commonTest` cover encode/decode/round-trip valid/invalid/edge cases with
  hand-written hex (no external protocol vectors needed for plain hex). No primitive-specific
  hex helpers were added; no dependencies or Gradle changes.

Outcome (Bech32/Bech32m engine step):

- Added a generic, bounded Bech32/Bech32m codec in `:core` per ADR-0001: `Bech32.encode` /
  `Bech32.decode` working at the 5-bit data layer, a `Bech32Variant` enum (`BECH32` /
  `BECH32M`), a `Bech32Decoded` carrier (regular class, defensive copies, `contentEquals` /
  `contentHashCode`, `toData5BitArray()` accessor), and a typed `Bech32Error`. `decode`
  auto-detects the variant, rejects mixed case, and validates HRP / separator / data charset /
  variant checksum; the encoder emits canonical lowercase. SDK-owned named limits
  (`MAX_INPUT_CHARS = 1023`, `MAX_HRP_CHARS = 83`, `MAX_DATA_VALUES = 1016`, and
  `MAX_DATA_BYTES = 640` for the internal 5/8-bit `convertBits` only) are enforced with typed
  errors before allocation; BIP-173's 90-character cap is intentionally not applied. Both
  APIs return `KardanoResult` and never throw.
- Tests in `core/src/commonTest` use the official BIP-173 and BIP-350 valid and invalid
  vectors verbatim (cited inline), plus mixed-case, HRP, separator, charset, checksum,
  cross-variant, over-limit, padding, and round-trip cases. No AI-invented protocol vectors;
  no dependencies or Gradle changes. The "overall max length exceeded" invalid vectors are
  rejected via the SDK HRP-length limit (their HRP is 84 chars), not via the 90-char cap.
Outcome (Cardano HRP allowlist wrappers step):

- Added thin Cardano-facing wrappers over the generic engine: `CardanoHrp` (the allowlist
  enum `ADDR` / `ADDR_TEST` / `STAKE` / `STAKE_TEST` carrying the lowercase HRP value),
  `CardanoBech32` (an `object` with `encode(hrp, data5Bit)` and `decode(input)`), and a typed
  `CardanoBech32Error` (`Underlying` / `UnsupportedHrp` / `UnsupportedVariant`). `encode`
  takes a `CardanoHrp` and forces `Bech32Variant.BECH32`; `decode` delegates to
  `Bech32.decode` and, on success, checks the HRP allowlist first and the variant second, so
  a Bech32m string with an unsupported HRP returns `UnsupportedHrp` while a Bech32m string
  with an allowlisted HRP returns `UnsupportedVariant`. Generic failures propagate via
  `Underlying`. Both return `KardanoResult` and never throw.
- This is HRP allowlist plus Bech32 checksum/charset validation only per ADR-0001 — not
  CIP-19 structural address validation. The wrappers do not parse payloads, inspect header
  bytes, or read the network id; `Address` and structural validation remain in Block 0.7.
- Tests in `core/src/commonTest` generate valid strings with the generic engine (no real
  addresses, no funds, no CIP-19 vectors) and cover encode/decode/round-trip for the four
  HRPs, unsupported HRP rejection, propagated generic checksum/charset errors, Bech32m
  rejection, and the HRP-before-variant check order. No engine change, no dependencies, no
  Gradle changes. Block 0.5 is complete; the next block is 0.6 (CBOR subset).

Acceptance criteria:

- Strings are allowed for encoded public formats.
- Internal binary representation should use byte wrappers.
- Invalid characters are rejected.
- Invalid checksums are rejected.
- Bech32/Bech32m implementation follows ADR-0001.
- Tests include official or cited vectors where possible (Bech32 → BIP-173, Bech32m →
  BIP-350); no AI-invented protocol vectors.
- Parsers are not made lenient to pass tests.

### 0.6 CBOR And Parser Strategy

Goal:

Implement the CBOR subset and binary parsers according to ADR-0001.

Decision status:

- ADR-0001 (CBOR/parser policy) is **Accepted**: the CBOR subset is a constrained internal
  implementation (definite-length only) with no external dependency. Implementation must
  follow ADR-0001 (supported major types within signed `Long` range; byte/text strings,
  arrays, maps with explicit limits; reject indefinite lengths, tags including bignum tags
  2 and 3, floats/simple/null/undefined, trailing bytes, out-of-range integers, and
  duplicate map keys; canonical map ordering in deterministic/Cardano mode).

Status: complete (primitives + definite-length arrays/maps landed).

Outcome (first step — primitive values):

- Added a bounded CBOR decoder/encoder to `:core` for the definite-length **primitive
  subset only**: `Cbor.decode` / `Cbor.encode` over a sealed `CborValue` (`CborUnsigned`,
  `CborNegative` within the signed `Long` range; `CborByteString` and `CborTextString`,
  definite-length), with a typed `CborError`. Both return `KardanoResult` and never throw.
  The encoder emits canonical (shortest-form) definite-length output; `CborByteString` uses
  defensive copies and `contentEquals` / `contentHashCode`.
- Named SDK-owned limits `CBOR_MAX_INPUT_BYTES` (`1 shl 20`), `CBOR_MAX_BYTESTRING_BYTES`
  and `CBOR_MAX_STRING_BYTES` (`1 shl 16`, deliberately below the input limit so each string
  is bounded independently) are enforced before allocation. No buffer is allocated from an
  untrusted declared length: a declared length is validated against the total input limit,
  then the remaining bytes, then the named limit, before any copy. `CBOR_MAX_NESTING_DEPTH`
  and `CBOR_MAX_COLLECTION_ELEMENTS` are intentionally deferred to the arrays/maps substep.
- Rejected with typed errors (never normalized): indefinite lengths, reserved additional
  info (28/29/30), non-canonical integer/length encodings, integers outside signed `Long`
  (`IntegerOutOfRange`), byte/text string length prefixes outside signed `Long`
  (`LengthOutOfRange`, so a `uint64` length with bit 63 set is rejected rather than
  reinterpreted as a negative declared length), malformed UTF-8, over-limit input, trailing
  bytes, arrays (major 4) and maps (major 5, deferred), tags (major 6, incl. bignum 2/3),
  and floats/simple values (major 7).
- Tests in `core/src/commonTest` (`CborDecodeTest`, `CborEncodeTest`) use RFC 8949
  Appendix A vectors verbatim for supported positive examples plus hand-written edge cases
  (commented with the rule exercised) for malformed/non-canonical/over-limit/unsupported/
  trailing-byte cases, including explicit `Long.MAX_VALUE` / `Long.MIN_VALUE` boundary and
  `uint64`-overflow rejection cases. No AI-invented protocol vectors; no dependencies or
  Gradle changes.

Outcome (arrays/maps substep — completes Block 0.6):

- Extended the subset to definite-length arrays (major type 4) and maps (major type 5).
  `CborValue` gained `CborArray` (ordered `List<CborValue>`) and `CborMap` (an ordered list of
  `CborEntry` pairs, deliberately not a Kotlin `Map` so the canonical key order is explicit);
  both are regular classes with defensive copies, content-based equality, and structural
  `toString`. Added the named limits `CBOR_MAX_NESTING_DEPTH` (64) and
  `CBOR_MAX_COLLECTION_ELEMENTS` (65536).
- Decoder threads a nesting depth and reads definite-length collections only: the declared
  element/entry count is validated (canonical prefix, signed-`Long` range, then against
  `CBOR_MAX_COLLECTION_ELEMENTS`) before any element is read, and the depth limit is checked
  when a collection head is reached — no list is sized from an untrusted count. Maps enforce
  the Phase 0 deterministic rule (per ADR-0001, RFC 8949 §4.2.1) by comparing each key's
  recorded canonical encoded bytes against the previous key's: keys must be strictly ascending
  (`NonCanonicalMapKeyOrder` otherwise) with no duplicates (`DuplicateMapKey`). Unsupported
  child/key types are rejected through the normal child decode.
- Encoder is recursive with the same limits and emits canonical definite-length arrays/maps.
  For maps it requires the caller to supply already-canonical, duplicate-free entries and
  rejects otherwise (`NonCanonicalMapKeyOrder` / `DuplicateMapKey`) — it does not sort or
  deduplicate, consistent with the SDK-wide "reject, never normalize" rule. Tags, bignums,
  floats/simple/null/undefined, and indefinite lengths remain unrepresentable in `CborValue`
  and so cannot be encoded.
- New typed errors: `MaxNestingDepthExceeded`, `CollectionTooLarge`, `NonCanonicalMapKeyOrder`,
  `DuplicateMapKey`; the now-dead `ArraysNotSupportedYet` / `MapsNotSupportedYet` variants were
  removed. The Phase 0 deterministic map-ordering rule is documented as ADR-0001 / RFC 8949
  §4.2.1 and is explicitly not asserted as final Cardano transaction-serialization
  compatibility (Cardano historically used RFC 7049 length-first ordering); that is left to the
  future tx-serialization work.
- Tests use the RFC 8949 Appendix A array/map vectors verbatim (decode + canonical-encode +
  round-trip) plus hand-written rule tests for the element-count and nesting-depth limits,
  indefinite collections, non-canonical map order, duplicate keys, nested unsupported values,
  trailing bytes, truncation, and a "no silent sorting" encoder case. No AI-invented vectors;
  no dependencies or Gradle changes.

Acceptance criteria:

- ADR exists for CBOR/parser policy. (Done — ADR-0001 Accepted.)
- Named parser limits are defined.
- No allocation directly from untrusted declared length.
- Max input size, max depth and max element count are defined.
- Unsupported, malformed, trailing or non-canonical encodings are rejected unless explicitly documented.
- Integer range policy is defined.
- Bignum/BigInteger support is explicitly in or out of Phase 0. (Out — rejected per ADR-0001.)
- Tests use RFC 8949 Appendix A vectors for supported types; no AI-invented protocol vectors.

### 0.6.5 Core Package Organization

Status: complete.

Goal:

Reorganize the flat `org.sarmidev.kardano` package in `:core` into purpose-named packages
before Block 0.7, with no behavior change.

Outcome:

- Moved the existing `:core` sources into `org.sarmidev.kardano.primitives`,
  `org.sarmidev.kardano.encoding.hex`, `org.sarmidev.kardano.encoding.bech32`, and
  `org.sarmidev.kardano.encoding.cbor`. `KardanoResult` and `Platform` / `getPlatform`
  stay at the root package; `:shared` and the sample apps are untouched.
- This is a package move only (no new Gradle modules, no dependencies, no behavior change).
  Class/type names are unchanged; in this pre-alpha SDK the fully qualified names and
  imports changed. Gradle module splits are deferred. See
  `docs/DECISIONS/0003-core-package-structure.md`.
- `org.sarmidev.kardano.address` is intentionally not created yet; it arrives with the real
  code in Block 0.7.

Acceptance criteria:

- `:core` compiles on common, JVM, Android, and iOS simulator test sources.
- `:core:jvmTest` and `:core:testAndroidHostTest` pass; `:shared` builds with no source
  changes.
- No `internal` API was widened to `public`; `explicitApi()` still holds.
- No dependencies or Gradle module changes.

### 0.7 Address Parsing And Structural Validation

Goal:

Support structural validation of Cardano addresses. The `Address` value type (deferred
from Block 0.4) is introduced here, alongside the parsing/validation it depends on.

Status: complete. Block 0.7 covers structural CIP-19 parsing of the Shelley Bech32 address
families — base (0-3), pointer (4-5), enterprise (6-7), and reward/stake (14-15) — across
mainnet and testnet, decode-only, via `Address.parse`. It landed in three steps:
single-credential Shelley addresses, base addresses, and pointer addresses.

Outcome (first step — single-credential Shelley addresses):

- Added the `org.sarmidev.kardano.address` package with `Address` (and `Address.parse`),
  `AddressType` (`ENTERPRISE`, `REWARD` only — KDoc states this is the Step 1 subset and
  more CIP-19 types may follow), `AddressCredential` + `CredentialKind` (`KEY` / `SCRIPT`),
  and a typed `AddressError`. All return `KardanoResult`; nothing throws.
- `Address.parse` covers the single-credential, fixed-length Shelley types only: enterprise
  (`addr` / `addr_test`, CIP-19 header types 6/7) and reward/stake (`stake` / `stake_test`,
  header types 14/15). It decodes through `CardanoBech32`, converts the 5-bit data to bytes
  via the existing internal `Bech32.convertBits` (`pad = false`, so non-zero padding is
  rejected), reads the header byte, resolves the network id through `Network`, and enforces
  HRP↔network and HRP↔family agreement. Unsupported header types (base 0-3, pointer 4-5,
  Byron 8, reserved), wrong payload/credential lengths, bad checksums, and bad padding are
  rejected with typed errors — nothing is normalized.
- `AddressCredential` has a private constructor and is built only by the parser through an
  internal, length-validated `of(...)` factory returning `KardanoResult`; there is no public
  unvalidated constructor. All byte arrays are defensively copied on construction and on
  every accessor, use `contentEquals` / `contentHashCode`, and `toString` renders no bytes.
- Structural only: KDoc states parsing does not prove an address exists on-chain, is owned,
  is controllable, or is spendable, and does not verify the credential is a real key/script
  hash. The network id is preserved and exposed; preview vs preprod is not distinguished
  (both network id 0).
- Tests in `core/src/commonTest` use the CIP-19 "Test vectors" `type-06/07/14/15` mainnet
  and testnet addresses verbatim (cited) for valid cases; invalid/edge cases are labeled
  hand-written rule tests derived from a cited vector (decode, mutate one field, re-encode)
  for bad checksum, Bech32m, non-allowlisted HRP, network mismatch, family mismatch,
  unsupported type (base/pointer/Byron), wrong length, empty payload, defensive copies, and
  `toString`. No AI-invented vectors; no dependencies or Gradle changes.
- Deferred to later steps: base addresses (types 0-3), pointer addresses (types 4-5),
  Byron/Base58, and hex/raw-byte address constructors.

Outcome (second step — base addresses):

- Extended `Address.parse` to the two-credential Shelley **base** types (CIP-19 header
  types 0-3, `addr` / `addr_test`, fixed 57-byte payload = 1 header + 28-byte payment
  credential + 28-byte delegation/stake credential), adding `AddressType.BASE`. The four
  header types are distinguished by the two low type-nibble bits: bit 0 selects a script
  (vs key) payment part and bit 1 selects a script (vs key) delegation part. Pointer (4-5),
  Byron (8), and reserved types are still rejected with `UnsupportedAddressType`.
- Replaced the ambiguous single `Address.credential` property with two explicit nullable
  properties, `paymentCredential: AddressCredential?` and `stakeCredential: AddressCredential?`.
  Presence follows the type: enterprise → payment only; reward/stake → stake only; base →
  both. This is a breaking source-level change to the Step 1 API, acceptable in this
  pre-alpha SDK with no external consumers (ADR-0003); `AddressCredential` / `CredentialKind`
  are unchanged, and equality/`hashCode` now include both credentials.
- The `addr` / `addr_test` HRP family now accepts both base and enterprise; the per-type
  length check expects 57 bytes for base and 29 for the single-credential types. All bytes
  remain defensively copied; `toString` renders no bytes; structural-only KDoc is unchanged
  in intent (no ownership/existence/spendability/balance claims).
- Tests use the CIP-19 `type-00/01/02/03` mainnet and testnet base vectors verbatim (cited)
  for valid parses across all four payment/stake key/script combinations, plus credential
  presence tests, base equality (including a labeled derived rule object that differs only in
  the stake credential), and labeled derived rule tests for wrong base length, base under a
  `stake` HRP, and a base HRP/network mismatch. Step 1 enterprise/reward tests were migrated
  to the new `paymentCredential` / `stakeCredential` accessors. No AI-invented vectors; no
  dependencies or Gradle changes.

Outcome (third step — pointer addresses):

- Extended `Address.parse` to the Shelley **pointer** types (CIP-19 header types 4-5,
  `addr` / `addr_test`), adding `AddressType.POINTER`. A pointer address is a 28-byte payment
  credential (key for type 4, script for type 5) followed by a chain pointer instead of an
  inline delegation credential, so its payload is variable length and uses a dedicated parse
  path rather than the fixed-length check.
- Added `AddressPointer` (the three non-negative `Long` coordinates `slot` /
  `transactionIndex` / `certificateIndex`, built only via a range-validated internal factory),
  a `PointerField` enum (`SLOT` / `TRANSACTION_INDEX` / `CERTIFICATE_INDEX`), and a new
  nullable `Address.pointer` property. Presence now: enterprise → payment only; reward → stake
  only; base → payment + stake; pointer → payment + pointer (`stakeCredential` null,
  `pointer` non-null). `equals` / `hashCode` include `pointer`.
- The pointer is decoded as three CIP-19 variable-length unsigned integers (big-endian
  base-128, continuation-bit framing). Named constants bound the decode: `MAX_POINTER_FIELD_BYTES`
  (9, = the 63-bit non-negative `Long` range), `MIN_POINTER_PAYLOAD_SIZE` (32). The decoder
  iterates over the already-bounded payload (no allocation from an untrusted length), checks
  the overflow guard **before** each 7-bit shift (so signed-`Long` wraparound is never relied
  on), and rejects (never normalizes): truncated fields (`TruncatedPointer`), non-canonical
  over-long leading-zero encodings (`NonCanonicalPointer`, stricter than the lenient ledger
  decoder, per Phase 0 parser policy), over-byte/over-range fields (`PointerValueOutOfRange`),
  and trailing bytes after the third coordinate (`TrailingPointerBytes`). The `addr` /
  `addr_test` HRP family now accepts pointer in addition to base and enterprise.
- Tests use the CIP-19 `type-04/05` mainnet and testnet pointer vectors verbatim (cited),
  asserting `AddressType.POINTER`, the payment credential kind, `stakeCredential == null`,
  `pointer != null`, and the spec-documented coordinates `(2498243, 27, 3)`; plus labeled
  derived rule tests for pointer HRP network/family mismatch, payload too short, truncated
  (continuation-at-end and dropped-byte), non-canonical, over-limit, and trailing bytes. The
  Step-1/2 `rejectsUnsupportedPointerType` test was removed (type 4 is now valid); Byron type-8
  stays unsupported. No AI-invented vectors; no dependencies or Gradle changes.

Block 0.7 closure:

- Block 0.7 covers structural CIP-19 parsing of the Shelley Bech32 address families — base
  (0-3), pointer (4-5), enterprise (6-7), and reward/stake (14-15) — across mainnet and
  testnet, decode-only, via `Address.parse` (the only constructor). Parsing is structural only
  and never normalizes input.
- Rejecting non-canonical (over-long, leading-zero) pointer variable-length integers is an
  accepted Phase 0 parser decision. It is stricter than the historically lenient ledger
  decoder, and is consistent with the Phase 0 guardrail "reject malformed, non-canonical, or
  unsupported input — never normalize it" (and the CBOR/Bech32 precedent).

Deferred beyond Block 0.7 (each is a separate future decision, not a Block 0.7 step):

- Byron / bootstrap addresses (header type 8): Base58-encoded and Byron-specific (CRC, address
  attributes, address-type tags, CBOR structure). These need a Base58 codec, CRC handling, and
  Byron-specific CBOR (including tag handling the Phase 0 definite-length CBOR subset currently
  rejects), so they form a distinct legacy parser/codec domain that warrants its own future
  block, with its own verbatim vectors and any needed ADR/policy work.
- Raw-byte / hex `Address` constructors (e.g. `Address.fromBytes` / `fromHex`): public-API and
  round-trip design that implies an address encoding/round-trip policy (canonical re-encoding,
  `toBech32`) Phase 0 has not defined. Deferred until an address encoding/round-trip ADR exists
  (likely alongside transaction serialization). `Address.parse` remains the only constructor
  for now.

Acceptance criteria:

- Network id is preserved.
- Mainnet/testnet/preprod/preview distinctions are not ignored.
- KDoc states validation is structural only.
- Validation does not claim ownership, existence, spendability or balance.
- Tests include valid addresses, malformed addresses, wrong checksums and network mismatches.

### 0.8 Crypto Strategy Document

Goal:

Document the future cryptography approach before implementing any crypto behavior.

Important:

No custom cryptography in Phase 0.

Deliverables:

- Crypto strategy document or ADR.
- Candidate library/binding evaluation.
- Target support matrix.
- Required test vector sources.

Acceptance criteria:

- No mnemonic generation implemented yet.
- No private key handling implemented yet.
- No transaction signing implemented yet.
- Future crypto implementation requires external vectors and review.
- Android, iOS and JVM/Desktop compatibility is considered.

### 0.9 Phase 0 Closure Review

Goal:

Check that the project is ready to start Phase 1/MVP work.

Acceptance criteria:

- All Phase 0 docs are updated.
- Tests pass on available targets.
- Public APIs have KDoc.
- Security docs are consistent.
- `docs/HANDOFF.md` reflects the current state.
- Open decisions are listed.
- No transaction signing or real wallet flow exists yet.

## Phase 1 - MVP Transaction Flow

Goal:

Enable a native mobile app to create or restore a wallet, query UTxOs, build a simple transaction, sign locally and submit to Cardano preprod.

Expected modules:

- `wallet`
- `tx`
- `provider`
- `provider-blockfrost`

Expected capabilities:

- Wallet create/restore.
- Address generation.
- UTxO fetching.
- Protocol parameter fetching.
- ADA transaction builder.
- Native asset transaction builder.
- Fee and change calculation.
- Local signing.
- CBOR serialization.
- Submit transaction.

Acceptance criteria:

- End-to-end preprod transaction works.
- Android sample works.
- iOS sample works.
- JVM/Desktop demo or CLI works.
- Tests and docs are updated.

## Phase 2 - Plutus Lite And Provider Expansion

Goal:

Support simple dApp-like mobile flows without trying to replace full advanced Plutus tooling.

Candidate capabilities:

- Datum representation.
- Redeemer representation.
- Script hash.
- Inline datum.
- Reference inputs.
- Simple script interaction example.
- Ogmios provider.
- Kupo provider.
- Koios or Maestro provider.

Non-goal:

- Full Plutus framework.

## Phase 3 - Ecosystem Adoption

Goal:

Make Kardano SDK visible and credible in the Cardano ecosystem.

Deliverables:

- Public docs.
- Sample videos.
- Benchmarks.
- External pilot.
- Catalyst or Intersect proposal.
- Contributor guide.
- Issues labeled for new contributors.

Success criteria:

- At least one wallet or dApp experiments with the SDK.
- The demo is easy to run.
- The project can credibly request funding based on delivered work.

## Operating Principle

Each phase should deliver something real, tested and documented.

Do not move to the next phase by hiding risk in vague future work.

