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

### 0.7 Address Parsing And Structural Validation

Goal:

Support structural validation of Cardano addresses. The `Address` value type (deferred
from Block 0.4) is introduced here, alongside the parsing/validation it depends on.

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

