# Kardano SDK - Roadmap

## Current Status

Phase 0 (Core Foundation) is complete. Blocks 0.1 through 0.9 are done: governance/AI
rules, the UI-free `:core` module structure, testing infrastructure, core primitives,
encoding utilities (Hex, Bech32/Bech32m, Cardano HRP wrappers), the definite-length CBOR
subset, core package organization, structural CIP-19 address parsing, the crypto strategy
ADR, and the Phase 0 closure review.

Selected targets:

- Android.
- iOS.
- JVM/Desktop.

Current priority:

> Phase 0 is closed. Phase 1 Block 1.1 (planning), Block 1.2 (Android SDK Playground),
> Block 1.3a (Provider Read-Only Boundary — interface, models, and mock in `:provider`),
> Block 1.3b-pre (`Address.bech32` source string in `:core`), Block 1.3b (Blockfrost
> preprod provider in `:provider-blockfrost`, with a live Playground toggle), Block 1.4
> (Crypto Evaluation And Module Decision, docs-only; ADR-0008), Block 1.5a (Kotlin-2.4.0
> compatibility spike, **PASS**), Block 1.5b-pre (crypto vector-source gate, docs-only), and
> Block 1.5b (create `:crypto`, wire Blake2b-224/256 behind `Hashing`) are complete. The
> vector gate **passed for both digest sizes**: Blake2b-224 pinned to CIP-19 and Blake2b-256
> pinned to the IntersectMBO Plutus `blake2b_256` conformance goldens (`IntersectMBO/plutus`
> @`5e18824e`, Apache-2.0; ADR-0008 §7). Block 1.5b found that Apollo 1.8.8 ships no Blake2b,
> so the hashing-only backend is KotlinCrypto `org.kotlincrypto.hash:blake2` `0.8.0` (Apollo
> and `bip32-ed25519` not added this block; reserved for 1.6 / 1.10; ADR-0008 §8). Block 1.6
> (mnemonic / seed / key derivation) is split into 1.6a–1.6d (ADR-0009). **Block 1.6a is
> complete** (docs-only): the scheme is pinned to the Icarus/CIP-3 restoration path only
> (Byron/Ledger/Trezor variants deferred; restore-only, generation deferred), the
> per-algorithm dependency table is verified against published artifacts (the main Apollo
> artifact does not enter 1.6 — its mnemonic API lacks checksum validation and its PBKDF2
> takes a String salt; Ed25519-BIP32 arrives via the standalone
> `dev.allain:bip32-ed25519:2.3.0` in 1.6c; 1.6b uses cryptography-kotlin PBKDF2 +
> KotlinCrypto `sha2`), and the vector gate passed for all three families (Trezor
> `vectors.json` @`b57a5ad7` MIT; CIP-3 `Icarus.md` @`a36e1ebc` CC-BY-4.0;
> `IntersectMBO/cardano-addresses` golden `addresses_5574d91d` @`46d01319` Apache-2.0).
> **Block 1.6b closed its `To verify in 1.6b` gate: cryptography-kotlin's PBKDF2 failed on
> Android** (its JDK provider needs JCA `PBKDF2WithHmacSHA512`, API 26+, vs this repo's
> `minSdk = 24`), so 1.6b adopted the ADR-0009 §3 platform-seam fallback instead — BouncyCastle
> on JVM/Android, Apple CommonCrypto on iOS; no hand-written PBKDF2. `Mnemonic.parse` and
> `IcarusMasterKey.fromMnemonic` are implemented and pass the cited Trezor/CIP-3 vectors on JVM
> and Android. On iOS, an inline C interop shim (`kardano_ccpbkdf2_hmac_sha512` in
> `pbkdf2raw.def`) adapts `CCKeyDerivationPBKDF`'s password to a raw byte pointer, and **both
> iOS compile targets pass** (`:crypto:compileKotlinIosSimulatorArm64` and
> `:crypto:compileKotlinIosArm64`). **iOS runtime execution of the vectors is still future
> verification** — no iOS-simulator/device test run has exercised this binding. **Block
> 1.6c's original gate narrowed it to private derivation only** (ADR-0009); its first
> follow-up (ADR-0010) then **swapped the derivation backend's coordinate to
> `org.hyperledger.identus:bip32-ed25519:1.8.8`** (identical wrapper API) and **verified
> private derivation on real Android runtime** — `KeyDerivation.derivePrivate` now works
> on Android, JVM, and compiles/links on iOS; the earlier Android-derivation blocker is
> resolved, not merely downgraded. The same follow-up added `ExtendedPublicKey` and
> `KeyDerivation.publicKey(...)` for JVM/iOS, backed by libsodium's
> `crypto_scalarmult_ed25519_base_noclamp`, verified byte-for-byte against the cited
> `addr_xvk` goldens on JVM (iOS compile/link verified) — but opened a separate, Android
> public-key-projection blocker (the published Android build of that backend was missing the
> required symbol). **A second follow-up then closed that Android-projection blocker too**:
> `KeyDerivation.publicKey` now delegates on Android to `com.goterl:lazysodium-android:5.2.0`
> (a fuller libsodium build than the JVM/iOS backend's Android native library), verified on
> real Android runtime — a physical device (API 35) plus API 24/36 emulators — reproducing
> the cited `addr_xvk` golden and cross-checked against the CIP-19 payment credential.
> `KeyDerivationError.PublicKeyProjectionUnavailable` remains declared but no current target
> returns it. Full write-up: ADR-0009 "Block 1.6c gate result" and ADR-0010.

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
- `:provider` (read-only chain query boundary + in-memory mock; added in Block 1.3a)
- `:provider-blockfrost` (Blockfrost preprod provider: Ktor + kotlinx-serialization; added in
  Block 1.3b; depends on `:provider` + `:core`)
- `:shared` (sample/UI host; builds the iOS `Shared` framework)
- `:androidApp`
- `:desktopApp`
- `iosApp` (Xcode entry point)

Deferred candidate future modules (names are not final; do not create yet):

- `:crypto`
- `:wallet`
- `:tx`
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

Status: complete.

Goal:

Document the future cryptography approach before implementing any crypto behavior.

Important:

No custom cryptography in Phase 0.

Outcome:

- Added `docs/DECISIONS/0004-crypto-strategy.md` (ADR-0004, Accepted): records the
  crypto strategy before any implementation lands.
- Strategy decisions recorded: no handwritten crypto; all future crypto delegated to
  externally maintained libraries or platform bindings selected through documented
  evaluation per algorithm; crypto isolated from the dependency-free `:core`; likely
  end state is a separate module (candidate name `:crypto`, not final, extracted when
  justified per ADR-0002/ADR-0003); seam pattern (expect/actual vs. common interface)
  chosen per algorithm during evaluation; key-material lifecycle policy (defensive copies,
  opaque handles, best-effort clearing — no guarantee); typed-error / `KardanoResult`
  policy for failable APIs; test-vector policy (official vectors only, cited verbatim;
  no vectors added in this block).
- Future algorithm scope enumerated: Ed25519, Ed25519-BIP32 (Cardano extended-key
  scheme), BIP-32 derivation, CIP-1852 paths, BIP-39 / CIP-3, PBKDF2-HMAC-SHA-512,
  HMAC-SHA-512, SHA-256 / SHA-512, Blake2b-224, Blake2b-256, platform randomness (CSPRNG),
  and key-material lifecycle. VRF / KES and Plutus keccak / sha3 marked out of scope.
- Candidate evaluation: four candidate categories (JVM/Android JCA-style provider;
  C library via cinterop; pure-Kotlin / KMP-native provider; Cardano-specific binding)
  with a reusable evaluation template. All candidate fields are `Unverified`; all
  `Decision status` entries are `Needs investigation`. No candidate is selected.
- Target support matrix (Android, iOS, JVM/Desktop — Web/Wasm deferred) and
  platform-specific concerns (randomness sourcing, JVM/GC clearing limitations,
  iOS/Swift interop, JCA provider variance for Blake2b) documented.
- Seven open questions listed.
- Fixed `docs/SECURITY.md` principle 1 (previously named BouncyCastle/libsodium as if
  selected; now points to ADR-0004 with no library named) and the crypto scope row
  (now links to ADR-0004).
- Fixed `docs/AI_WORKING_AGREEMENT.md` crypto lines (previously named concrete libraries
  and mandated expect/actual; now references ADR-0004 and allows either seam).
- No Kotlin, Gradle, dependency, fixture, or test changes.

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

Status: complete.

Goal:

Check that the project is ready to start Phase 1/MVP work.

Outcome:

- Review/documentation/verification block only — no new SDK features, no Kotlin behavior
  changes, no Gradle or dependency changes, no crypto/signing/key/mnemonic code, no
  validator relaxation.
- Verification: `./gradlew :core:jvmTest`, `:core:testAndroidHostTest`, and
  `:core:compileTestKotlinIosSimulatorArm64` all pass / compile (BUILD SUCCESSFUL). iOS
  simulator *execution* is macOS/Xcode-gated and was not run; only the iOS test sources
  were compiled.
- Heuristic policy scans run and every hit manually classified. No `ByteArray ==` in
  `:core`. The banned-word hits are all the banned-word lists themselves, negated/factual
  disclaimers ("Not audited.", "Not for real funds."), or the "safe to test" round-trip
  guidance — no new or misleading positive claims. The mnemonic/private-key and
  crypto/signing hits are all policy text, non-goals, ADR-0004, out-of-scope notes, or
  KDoc that describes a credential as a `blake2b-224` hash while stating it is **not**
  verified — no implementation code, no real keys/mnemonics/funds.
- Confirmed: `explicitApi()` holds; public failable APIs return `KardanoResult` / sealed
  errors (`Address.parse`, `Cbor`/`Bech32`/`CardanoBech32`/`Hex` codecs, primitive `of` /
  `fromId` factories); named parser limits and the strict "reject, never normalize" policy
  are documented and implemented; tests cite BIP-173/350, RFC 8949 Appendix A, and CIP-19
  vectors verbatim. No Byron/Base58 or raw-byte/hex `Address` constructor exists
  (`Address.parse` is the only constructor); no dependency or Gradle drift (clean working
  tree; no dynamic versions).
- Docs reconciled: this "Current Status" header and `docs/HANDOFF.md` updated to "Phase 0
  complete"; `docs/TESTING.md` gained the two `:core` verification commands it had omitted
  (an omission, not a contradiction). No standalone closure document was created —
  `docs/ROADMAP.md` (this Outcome) and `docs/HANDOFF.md` are the closure record.

Acceptance criteria:

- All Phase 0 docs are updated.
- Tests pass on available targets.
- Public APIs have KDoc.
- Security docs are consistent.
- `docs/HANDOFF.md` reflects the current state.
- Open decisions are listed.
- No transaction signing or real wallet flow exists yet.

## Phase 1 - MVP Transaction Flow

Block 1.1 (Phase 1 Scope And Architecture Plan) is complete. It was a planning/documentation
block — no wallet, crypto, provider, tx, or Android UI code, no Gradle or dependency changes.
Implementation starts at **Block 1.2**, not in Block 1.1. The working Phase 1 block plan is
recorded in `docs/PHASE_1_PLAN.md`.

Goal:

Enable a native mobile app to create or restore a wallet, query UTxOs, build a simple transaction, sign locally and submit to Cardano preprod.

Planning principle:

Phase 1 should progress through small blocks with Android checkpoints. The Android app
must become a recurring validation surface, not something checked only at the end.

Proposed block sequence:

- `1.1` Phase 1 Scope And Architecture Plan — **Status: complete.** Outcome: MVP flow fixed
  (create/restore test wallet, derive address, query UTxOs, build a minimal ADA-only tx, sign
  locally, submit to preprod, show result in Android); native assets placed out of the first
  MVP; Android set as the primary Phase 1 validation target with iOS/JVM-Desktop compile-only
  unless explicitly revisited; module/package strategy recorded as decision criteria only (no
  Gradle module created; crypto/provider/network dependencies are the likely trigger; `:core`
  stays dependency-free; `:shared` stays the sample/UI host, not the SDK's long-term home);
  provider strategy set to mock/stub first with Blockfrost as the first real preprod target
  and a minimal API (concrete selection deferred to Block 1.3); crypto decision path kept at
  Block 1.4/1.5 against ADR-0004 with no library selected here; the address
  encoding/round-trip prerequisite (before Block 1.7) and the CBOR tx map-ordering
  prerequisite (before Block 1.9) recorded as deferred, each resolved in its own block. See
  `docs/PHASE_1_PLAN.md` ("Block 1.1 Decisions") and
  `docs/DECISIONS/0005-phase-1-architecture-and-scope.md` (ADR-0005, Accepted). No Kotlin,
  Gradle, or dependency changes; Android baseline build verified
  (`./gradlew :androidApp:assembleDebug :core:jvmTest`).
- `1.2` Android SDK Playground — **Status: complete.** Outcome: added the
  `org.sarmidev.kardano.playground` package in `:shared` `commonMain` with a pure
  UI-free `PlaygroundPresenter` (maps `Address.parse` / `Hex` / `Cbor` results to display
  models; `presentAddressError` is `internal` for direct unit testing) and a
  `PlaygroundScreen` Composable (address parser with typed `AddressError` display, Hex
  decoder, CBOR decoder). `App.kt` replaced to render `PlaygroundScreen` inside
  `MaterialTheme`; `:core` is unchanged; `:androidApp` is unchanged; no new dependencies
  or Gradle modules. Tests in `:shared` `commonTest` cover `presentAddressError` with
  directly-constructed `AddressError` variants plus 2 cited CIP-19 happy-path vectors
  (type-06 enterprise testnet, type-14 reward testnet), 1 invalid input test, and 1
  Empty-state test; the protocol test-vector suite stays in `:core`. All build and test
  commands pass; manual Android checkpoint verified (see `docs/PHASE_1_PLAN.md` Block 1.2 outcome).
- `1.3` Provider Read-Only Boundary — **complete (1.3a + 1.3b-pre + 1.3b).** 1.3a added the
  `:provider` module (KMP, depends only on `:core`) with a read-only `ChainQueryProvider`
  (suspend + `KardanoResult`), provider-neutral ADA-only models (`Utxo`, `Value`,
  `ProtocolParameters`, `ChainTip`, sealed `ProviderError` with a transport-agnostic
  `RemoteStatus`), and an `InMemoryChainQueryProvider` mock with fake/test-only seed data,
  wired into the Playground "Provider" section. 1.3b-pre added `Address.bech32` (the validated
  source string) to `:core`. 1.3b added `:provider-blockfrost` (`BlockfrostChainQueryProvider`,
  Ktor + kotlinx-serialization, internal DTOs, ADA-only + 404-as-empty mapping, error mapping,
  MockEngine fixture tests, opt-in live test) and a live-Blockfrost Playground toggle (ADR-0007;
  no secrets committed). Submit is split out and deferred to Block 1.11 (ADR-0006 refines
  ADR-0005 §5). The real Blockfrost preprod provider lives in `:provider-blockfrost` (HTTP client
  + API-key config + sanitized fixtures + opt-in live test). See
  `docs/DECISIONS/0006-provider-boundary-and-strategy.md` and
  `docs/DECISIONS/0007-http-client-and-blockfrost-provider.md`.
- `1.4` Crypto Evaluation And Module Decision — **Status: complete (docs-only).** Outcome:
  added ADR-0008 (`Accepted` for module/seam/process only; no final dependency-fitness claim
  while compatibility is untested). Decided now: `:crypto` deferred to Block 1.5; the seam is a
  `commonMain` common interface/adapter (`Hashing`, later `KeyDerivation`/`Signing`) returning
  `KardanoResult`, with `expect`/`actual` as fallback; the first algorithm boundary in 1.5 is
  Blake2b-224/256 behind `Hashing` with official cited vectors (RFC 7693 / Cardano context).
  Provisional: candidate selection is provisional, with Hyperledger Identus Apollo +
  `bip32-ed25519` as the provisional lead (Kotlin 2.4.0 compatibility To verify in 1.5a);
  bloxbean cardano-client-lib rejected as a shipped dependency (no iOS/KMP), retained as a
  JVM-only vector oracle. Source-cited matrix; unknowns marked `Unverified`/`To verify in 1.5a`;
  neutral review fields. No Kotlin/Gradle/dependency/module changes. See
  `docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md`.
- `1.5` Crypto Primitives Needed For Wallet — split into `1.5a` and `1.5b`.
  - `1.5a` throwaway Kotlin-2.4.0 compatibility spike — **Status: complete (PASS).** The
    provisional candidate (`org.hyperledger.identus:apollo:1.8.8` + `dev.allain:bip32-ed25519:2.3.0`)
    resolved and compiled on Android + JVM + iosSimulatorArm64 under Kotlin 2.4.0 / AGP 9.0.1
    (`:crypto-spike:compileKotlinJvm`, `:crypto-spike:compileKotlinIosSimulatorArm64`,
    `:crypto-spike:testAndroidHostTest`). Correction: `secp256k1-kmp` arrives transitively as
    `fr.acinq.secp256k1:secp256k1-kmp:0.16.0`; the `org.hyperledger.identus` companion was not
    needed. Proves resolve + compile only, not runtime correctness. Scratch module discarded; no
    dependency committed. See ADR-0008 §6.
  - `1.5b-pre` crypto vector-source gate — **Status: complete (docs-only); PASS for both sizes.**
    A blocking gate ran before any module/code, searching for exact official cited Blake2b
    known-answer vectors. Blake2b-224 **PASS** (CIP-19: `addr_vk1w0l2sr…` + the payment credential
    from the full CIP-19 address `addr1qx2fxv2umyhttk…`, via `:core` `Address.parse`).
    Blake2b-256 **PASS** — IntersectMBO Plutus `blake2b_256` conformance goldens
    (`IntersectMBO/plutus` @`5e18824e2e0e30656c81d182e0ca512b75e7e57c`, Apache-2.0): input `#`
    (empty) → `0e5751c0…f12fe3a8`, input `2e7ea8…1d200` (25 bytes) → `91c60f99…ee401624`; the
    builtin hashes the raw UPLC bytestring literal only. The empty-input digest previously seen only
    in a non-official third-party repo is now confirmed in this official Intersect source. No
    module/dependency/API/Gradle change. See ADR-0008 §7.
  - `1.5b` crypto module + hashing boundary — **Status: complete.** Created the `:crypto` KMP
    module (Android library + JVM + iosArm64 + iosSimulatorArm64, `explicitApi()`, depends only on
    `:core`) and wired Blake2b-224/256 behind the backend-neutral `Hashing` interface, with
    `HashDigest` (defensive-copy byte container) and the sealed `CryptoError`. Backend correction:
    Apollo 1.8.8 ships no Blake2b (verified in `apollo-jvm-1.8.8.jar` and source tags
    `v1.7.2`–`v1.8.7`), so the hashing-only backend is KotlinCrypto `org.kotlincrypto.hash:blake2`
    `0.8.0` (pinned in the catalog). Apollo and `bip32-ed25519` were not added this block; both are
    reserved for the later key-derivation blocks (1.6 / 1.10). Tests use only the pinned cited
    vectors (CIP-19 for 224; IntersectMBO/plutus goldens for 256), no generated digests.
    `./gradlew :crypto:jvmTest :crypto:testAndroidHostTest :crypto:compileKotlinIosSimulatorArm64
    :core:jvmTest` — all BUILD SUCCESSFUL. See ADR-0008 §8.
- `1.6` Mnemonic / Seed / Key Derivation — restore a test wallet and derive keys. Split into
  four gated subphases (ADR-0009, `docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md`);
  Icarus/CIP-3 restoration path only; restore-only (mnemonic generation and the CSPRNG
  decision deferred).
  - `1.6a` API / dependency / vector-source decision — **Status: complete (docs-only).**
    ADR-0009 records: module placement (`:crypto`; no `:wallet` yet, extraction trigger
    recorded); the Icarus/CIP-3 scheme (PBKDF2-HMAC-SHA-512 over the entropy, 4096
    iterations, 96 bytes, CIP-3 bit tweaks; plain BIP-39 seed not exposed; English wordlist
    only — lowercase ASCII English-wordlist input accepted; non-conforming input rejected,
    not normalized); the verified dependency table (main Apollo
    artifact rejected for 1.6 via published-artifact inspection — no checksum validation in
    its mnemonic API, String-salt PBKDF2; `dev.allain:bip32-ed25519:2.3.0` verified to
    expose `deriveBytes`/`deriveBytesPub`/`fromNonextended` for 1.6c; cryptography-kotlin
    0.6.0 PBKDF2 + `org.kotlincrypto.hash:sha2:0.8.0` for 1.6b, with the Android
    API-24/25 JCA item marked `To verify in 1.6b` and a platform-seam fallback recorded);
    the vector gate (PASS ×3: Trezor `vectors.json`, CIP-3 `Icarus.md`, cardano-addresses
    Shelley goldens — URL + commit + license pinned); the public API sketch, the sealed
    `MnemonicError`/`KeyDerivationError` model, and the key-material rules (opaque handles,
    no private-key byte accessor, mnemonics input-only and never echoed). No Kotlin,
    Gradle, dependency, or module changes.
  - `1.6b` BIP-39/CIP-3 mnemonic-to-master-key — **Status: complete on JVM/Android with
    executed vectors; iOS compile targets pass; iOS runtime vector execution still future
    work.** Closed the `To verify in 1.6b` gate: cryptography-kotlin's PBKDF2 fails on
    Android (its JDK provider requires JCA `PBKDF2WithHmacSHA512`, API 26+, vs `minSdk = 24`;
    `testAndroidHostTest` cannot detect this since it runs on the host JVM). Adopted ADR-0009
    §3's platform-seam fallback: BouncyCastle `PKCS5S2ParametersGenerator` (JVM + Android) and
    Apple CommonCrypto `CCKeyDerivationPBKDF` (iOS); no hand-written PBKDF2. Implemented
    `Mnemonic.parse` (word count, English wordlist, checksum, entropy) and
    `IcarusMasterKey.fromMnemonic` (PBKDF2-HMAC-SHA-512 + CIP-3 bit tweaks). Tests pass the
    cited Trezor `vectors.json` entropy round-trips and both CIP-3 `Icarus.md` vectors on JVM
    and Android (`:crypto:jvmTest`, `:crypto:testAndroidHostTest`). **iOS cinterop resolved for
    the compile target:** the shipped `platform.CoreCrypto.CCKeyDerivationPBKDF` binds
    `password` as `String`; a first attempt used `noStringConversion` directly on it (same
    delegated Apple primitive, no hand-written crypto) but produced a klib with zero
    declarations in this build environment. The fix is an inline C interop shim
    (`kardano_ccpbkdf2_hmac_sha512`) in `pbkdf2raw.def`'s glue block, adapting `password` to a
    raw byte pointer and delegating verbatim to `CCKeyDerivationPBKDF` — verified bindable with
    `klib dump-metadata` before the Kotlin actuals were updated to call it.
    `:crypto:compileKotlinIosSimulatorArm64` and `:crypto:compileKotlinIosArm64` both pass.
    **iOS runtime execution of the CIP-3/BIP-39 vectors has not been verified** — no
    iOS-simulator/device test run has exercised this binding; that remains future work. Also
    found and fixed during review: the checked-in BIP-39 English wordlist had transcription
    errors versus the canonical `bitcoin/bips` source; regenerated and verified against a fresh
    download of the pinned commit, with a structural test guarding wordlist shape going
    forward.
  - `1.6c` Ed25519-BIP32 + CIP-1852 derivation — **Status: private derivation and
    public-key projection are both verified on JVM, real Android runtime, and iOS
    compile/link.** The original `To verify in 1.6c` gate (ADR-0009) narrowed the block to
    private derivation only, with a confirmed `UnsatisfiedLinkError` on Android host JVM for
    the pinned `dev.allain:bip32-ed25519:2.3.0` backend, and no public-key-from-private-key
    primitive in that backend. A first follow-up gate
    ([ADR-0010](DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md))
    closed both, with one new gap opened in the process: (1) **swapped the derivation
    backend's coordinate** to `org.hyperledger.identus:bip32-ed25519:1.8.8` (identical
    wrapper API — `deriveBytes`/`deriveBytesPub`/`fromNonextended`, `UInt` index, same map
    keys) and **verified private derivation on real Android runtime**
    (`:crypto:connectedAndroidDeviceTest`, not host JVM) — this AAR ships the native `.so`
    the prior republish omitted, resolving the Android-derivation blocker outright; (2)
    **implemented `ExtendedPublicKey`/`KeyDerivation.publicKey(key)` for JVM/iOS**, backed by
    libsodium's `crypto_scalarmult_ed25519_base_noclamp` over the derived key's left 32-byte
    scalar, verified byte-for-byte against the cited `addr_xvk` goldens on JVM (iOS
    compile/link verified) — but the published Android build of that same backend was
    missing the required symbol, opening a new, separate Android public-key-projection
    blocker. **A second follow-up gate then closed that blocker too**: `KeyDerivation.
    publicKey` now delegates on Android to `com.goterl:lazysodium-android:5.2.0` (its AAR
    bundles a fuller libsodium `.so` that does export the symbol on all four ABIs), verified
    on real Android runtime — a physical device (API 35) plus API 24/36 emulators —
    reproducing the cited `addr_xvk` golden with a cross-check against the CIP-19 payment
    credential pinned in 1.5b. `KeyDerivationError.PublicKeyProjectionUnavailable` remains
    declared but no current target returns it. Implemented `Cip1852Path`/`Cip1852Role`
    (SDK-owned, `Long`-validated), `ExtendedPrivateKey`/`ExtendedPublicKey` (opaque, no raw
    private-key accessor), and both `KeyDerivation` methods. Tests pass the cited
    `IntersectMBO/cardano-addresses` golden `root_xsk`/`acct_xsk`/`addr_xsk`/`addr_xvk`
    values on JVM (`:crypto:jvmTest`) and on real Android runtime
    (`:crypto:connectedAndroidDeviceTest`, both derivation and projection). Full write-up:
    ADR-0009 "Block 1.6c gate result" and ADR-0010.
  - `1.6d` test-wallet fixture + Android checkpoint — **delivered.** `:shared` gained a
    project dependency on `:crypto` (no new external dependency) and a "Test Wallet
    (derivation)" Playground section: `TestWalletFixture` restores the cited test-only
    mnemonic, `PlaygroundPresenter.presentTestWallet()` derives `m/1852'/1815'/0'/0/0`,
    projects the public key, and computes its Blake2b-224 fingerprint — displaying only the
    path, the fingerprint, whether it matches the cited golden, and typed state; no raw/hex
    public key; addresses belong to 1.7. `PlaygroundWalletPresenterTest` (`commonTest`) covers
    error mapping/path formatting/invalid-mnemonic rejection without any native call (safe
    under `testAndroidHostTest`); `PlaygroundWalletDerivationDesktopTest` (`jvmTest`) is the
    only end-to-end fingerprint golden check. Android runtime coverage for the native path
    stays `:crypto:connectedAndroidDeviceTest`; the Android Playground checkpoint itself was
    confirmed via `adb`-driven UI interaction on the API 36 and API 24 emulators (path,
    fingerprint, and "matches cited vector: yes" all render, no crash/ANR, no noticeable
    freeze on API 24).
- `1.7` Address Generation — generate Shelley testnet addresses and roundtrip through
  `Address.parse`. Split into 1.7a/1.7b (see `docs/PHASE_1_PLAN.md`).
  - `1.7a` ADR-0012 + `:core` generation capability — **Status: complete.** Outcome:
    [ADR-0012](DECISIONS/0012-address-encoding-and-roundtrip.md) resolved the ADR-0005 §6
    address encoding/round-trip prerequisite and fixed the `:core` API shape. `AddressCredential`
    gained a public companion with `keyHash(hash)`/`scriptHash(hash)` factories (`HASH_SIZE`
    and the parser-only `of(...)` stay `internal`); `Address` gained `baseAddress(network,
    paymentCredential, stakeCredential)` (CIP-19 base, header types 0-3 only — enterprise/
    reward/pointer builders deferred) and `toBech32()` (a new private `canonicalBech32`
    field, canonical lowercase Bech32 from the address's own bytes, computed for both parsed
    and generated addresses). `bech32` is unchanged — still the exact parse-time source
    string (equal to `toBech32()` only for a generated address, which has no separate
    source). No new `AddressError` variant; its KDoc now covers construction/encoding, not
    just parsing. `:crypto` untouched — no new API needed. New `AddressGenerationTest.kt`
    (22 tests) rebuilds every cited CIP-19 base vector from its own decoded bytes and asserts
    `toBech32()` matches; `AddressTest.kt` gained 20 `toBech32()` canonicalization tests
    across every parsed type (base/enterprise/reward/pointer, mainnet + testnet), with all
    existing non-canonical rejection tests unchanged. Verified: `:core:jvmTest`,
    `:core:testAndroidHostTest`, `:core:compileKotlinIosSimulatorArm64`; `:core` stays
    dependency-free.
  - `1.7b` `:shared` Android checkpoint — **Status: complete.** Outcome: extended the
    existing Test Wallet section (Block 1.6d) into a combined derivation + structural
    address-generation checkpoint, per ADR-0011 §2 (`:shared` calls SDK APIs and displays
    results; no protocol logic). `:crypto` untouched. `TestWalletFixture` replaced its single
    `path` with `paymentPath` (`m/1852'/1815'/0'/0/0`) and `stakePath`
    (`m/1852'/1815'/0'/2/0`); the cited golden payment fingerprint is unchanged, and no golden
    was invented for the stake credential or a full generated address — both are computed at
    runtime and labelled as checkpoint output, not an external vector.
    `PlaygroundPresenter.presentTestWalletWithWords` derives both keys from one restored
    master key, hashes each with `Hashing.default().blake2b224(...)`, builds two
    `AddressCredential.keyHash(...)` credentials, calls
    `Address.baseAddress(Network.TESTNET, paymentCredential, stakeCredential)`, and
    immediately re-parses `address.toBech32()` for a structural round trip; all key handles
    and the mnemonic are cleared in `finally`. Displayed rows are limited to both path
    strings, both full credential-hash hex (public CIP-19 credentials, not secret key
    material), the generated `addr_test1...` address, and an "ok"/"mismatch" round-trip row —
    never mnemonic/seed/private/root/raw-public-key bytes. `PlaygroundScreen`'s section was
    renamed "Test Wallet & Address Generation" with reworded, factual copy (test-only
    fixture, no real funds, no signing, structural generation only).
    `PlaygroundWalletPresenterTest` (every target) covers the new path names and unchanged
    error/pre-native-rejection cases; `PlaygroundWalletDerivationDesktopTest` (JVM-only,
    native) asserts both paths, the cited golden payment-credential hex, an
    `addr_test1`-prefixed generated address parsing back as `Network.TESTNET` /
    `AddressType.BASE`, and a positive round trip — the generated address string itself is
    never pinned as a golden. Verified: `:shared:jvmTest`, `:shared:testAndroidHostTest`,
    `:shared:compileKotlinIosSimulatorArm64`, `:core:jvmTest`; lints clean; no banned words or
    mnemonic/seed/private/raw-key exposure found.
- `1.8` Wallet State Read-Only — show generated address, UTxOs, and test ADA balance. Split
  into 1.8a/1.8b (see `docs/PHASE_1_PLAN.md`).
  - `1.8a` `:wallet` module + read-only API — **Status: complete.** Outcome:
    [ADR-0013](DECISIONS/0013-wallet-boundary-and-read-only-state.md) resolved the
    `:wallet` module/ownership/API-shape decision ADR-0011 §2 deferred here: holding wallet
    state and composing it with a provider query is the ADR-0009 §1 extraction trigger firing
    for the first time, so a new module (not a package) was created. New module `:wallet`
    (`org.sarmidev.kardano.wallet`), targets mirroring `:provider`; depends on `:core`,
    `:crypto`, and `:provider` only (never `:provider-blockfrost`, no new external
    `commonMain` dependency). `ReadOnlyWallet.restore(words, network)` restores a mnemonic,
    derives the account-0 payment/stake keys, hashes and builds a base address via `:core`'s
    1.7a API, clearing all key handles in `finally`; the returned handle retains only
    `network`/`address`/`paymentPath`/`stakePath`. `ReadOnlyWallet.balance(provider)` queries
    a caller-supplied `ChainQueryProvider` and sums lovelace into `WalletBalance`, rejecting
    `Long` overflow (`WalletError.BalanceOverflow`) rather than truncating. `WalletError` wraps
    each upstream typed error (`MnemonicError`/`KeyDerivationError`/`CryptoError`/
    `AddressError`/`ProviderError`) rather than inventing a parallel taxonomy; no
    `WalletState`/`WalletAddress`/`TestWallet` type was added. Confirmed and documented
    (ADR-0013 §7) that a restored wallet's generated address is not seeded by
    `InMemoryChainQueryProvider`'s default data and stays zero-balance under the mock —
    `defaultSeed()` was not changed to fake a funded wallet. 15 new tests (14 native-free —
    balance summation/overflow/provider-error-wrapping via an `internal of(...)` test-only
    factory, direct `WalletError` variant construction, pre-native-call mnemonic rejection —
    plus 1 JVM-only end-to-end `restore` test against the same cited
    `IntersectMBO/cardano-addresses` mnemonic already pinned in `:crypto`). Verified:
    `:wallet:jvmTest`, `:wallet:testAndroidHostTest`, `:wallet:compileKotlinIosSimulatorArm64`,
    `:wallet:compileKotlinIosArm64`, `:core:jvmTest` (regression); `:core`/`:crypto`/
    `:provider` sources unchanged; lints clean; no banned words or mnemonic/seed/private/
    raw-key exposure found.
  - `1.8b` `:shared` Android checkpoint — **Status: complete.** Outcome: added `:wallet` as a
    `:shared` `commonMain` dependency (no other Gradle module changed; `:wallet` still depends
    on `:core`/`:crypto`/`:provider` only). New "Wallet Balance (read-only)" Playground section
    calls `PlaygroundPresenter.presentWalletBalance(provider)`, which restores
    `TestWalletFixture`'s cited mnemonic via `ReadOnlyWallet.restore(TestWalletFixture.words,
    Network.TESTNET)` (always testnet, per the Phase 1 no-mainnet boundary — ADR-0013 §3) and
    queries whichever `ChainQueryProvider` is currently active (mock or live) via
    `wallet.balance(provider)`; `:shared` reimplements none of mnemonic parsing, derivation,
    hashing, address generation, or balance summation. New `WalletBalancePresentation`
    (`Empty`/`Loading`/`Success`/`Failure`) and `presentWalletError` (delegating to the
    existing per-type error presenters, plus one message for `WalletError.BalanceOverflow`).
    Displays only the generated `addr_test1...` address, UTxO count, and balance in lovelace
    (no existing lovelace→ADA formatting pattern existed in `:shared`, so none was added); a
    zero balance/UTxO count under the default mock renders as a normal success with
    explanatory copy, per ADR-0013 §7, not as a failure. 6 new commonTest cases
    (`PlaygroundWalletBalancePresenterTest`, native-free — zero-balance-is-success, every
    `WalletError` variant's message delegation) plus 2 new jvmTest cases
    (`PlaygroundWalletBalanceDesktopTest` — the only place `presentWalletBalance`/
    `ReadOnlyWallet.restore` run end to end together, asserting the honest zero balance and the
    `Network.TESTNET` restore call). Verified: `:shared:jvmTest`, `:shared:testAndroidHostTest`,
    `:shared:compileKotlinIosSimulatorArm64`, `:wallet:jvmTest`, `:wallet:testAndroidHostTest`,
    `:androidApp:assembleDebug`; lints clean; no banned words or mnemonic/seed/private/raw-key
    exposure found.
- `1.9` Transaction Builder Minimal — build a simple unsigned ADA transaction draft. Split
  into 1.9a/1.9b-1/1.9b-2/1.9c (see `docs/PHASE_1_PLAN.md`).
  - `1.9a` ADR / decision record — **Status: complete (docs-only).** Outcome:
    [ADR-0014](DECISIONS/0014-minimal-ada-transaction-builder.md) resolves the builder's
    blocking decisions, including the CBOR tx map-ordering item ADR-0005 §6 deferred here.
    Block 1.9b creates a new `:tx` Gradle module (`org.sarmidev.kardano.tx`) depending on
    `:core` and `:provider` only (not `:wallet`/`:shared`/`:provider-blockfrost`/`:crypto`);
    Block 1.9 builds the **unsigned `transaction_body`** only (inputs, outputs, fee, optional
    ttl) and emits its canonical CBOR, with no witness set, signing, or submit, and the
    transaction id computed by the caller via `:crypto`. Cardano CBOR uses RFC 7049 §3.9
    canonical (length-first) map ordering (CIP-21 / ledger CDDL / `cardano-api`); `:core`'s
    subset is reused unchanged because the MVP body's single-byte integer keys make length-first
    and `:core`'s RFC 8949 bytewise order byte-identical (heterogeneous-key maps must revisit
    this later without weakening `:core`). Inputs sorted by ledger `(transaction_id, index)`
    order and encoded as an untagged array; outputs use the legacy `[address, coin]` array form;
    fee = `minFeeCoefficient * txSize + minFeeConstant` over the whole-transaction size estimate
    (one witness per input; an estimate until Block 1.10); Babbage/Conway min-UTxO
    `(160 + serializedOutputBytes) * coinsPerUtxoByte` enforced (zero change omitted, dust
    rejected); sealed `TxBuildError`; structural/CDDL tests only (no invented goldens, no
    signing tests). No Kotlin/Gradle/dependency changes.
  - `1.9b-1` `:tx` module + `transaction_body` serialization — **Status: complete.** New
    `:tx` Gradle module (`org.sarmidev.kardano.tx`, depending on `:core` + `:provider` only).
    `TransactionBodySerializer.serialize` orders/validates/encodes an already fully specified
    `TransactionBodyRequest` (explicit inputs/outputs/fee/ttl) into the canonical
    `transaction_body` via `:core`'s unchanged CBOR subset; inputs sorted by ledger
    `(transaction_id, index)` order with duplicates rejected
    (`TxBuildError.DuplicateInput`); outputs use the legacy `[address, coin]` form; output
    addresses checked against the request's network (`TxBuildError.NetworkMismatch`); empty
    inputs/outputs rejected (`TxBuildError.NoInputs`/`NoOutputs`, the latter an
    implementation-discovered addition to ADR-0014 §8). `TxBuildError` exposes the full
    ADR-0014 §8 error surface plus these additions up front (KDoc marks
    unreachable-until-1.9b-2 variants). No coin selection or fee/change loop yet — deferred to
    `1.9b-2` to keep the diff focused. Structural/CDDL tests only; no invented goldens.
  - `1.9b-2` fee/change coin-selection builder — **Status: complete.** New
    `TransactionBuildRequest` + `TransactionBuilder.build`, delegating body encoding to
    `TransactionBodySerializer.serialize` (no duplicated CBOR logic). Largest-first selection
    over `List<Utxo>` + `ProtocolParameters`, tie-broken by the same ledger order the
    serializer uses; fee = `minFeeCoefficient * txSize + minFeeConstant` with `txSize` from the
    real encoded body plus a sized-but-unbuilt witness set (checked arithmetic, generic CBOR
    head sizing, no `N < 24` shortcut); bounded fixed-point loop that, on non-convergence,
    rebuilds once more with the conservative (`maxOf`) of the last two fee estimates;
    Babbage/Conway min-UTxO enforcement (payment/change checked, zero change omitted, dust
    rejected once against the final result, never folded into the fee). The initial cut reused
    all existing `TxBuildError` variants; the follow-up review microfix then added
    `InvalidProtocolParameters(field, value)` (rejects a negative `minFeeCoefficient`/
    `minFeeConstant`/`maxTxSize`/`coinsPerUtxoByte`) and `FeeEstimateDidNotConverge(encodedFee,
    recomputedFee)` (the bounded loop's final conservative rebuild still re-estimating a higher
    fee than it encoded). No `:core`/`:provider`/Gradle changes.
  - `1.9c` `:shared` Android Playground "Transaction Draft (unsigned)" checkpoint —
    **Status: complete.** `PlaygroundPresenter.presentTransactionDraft` restores the
    `TestWalletFixture` mnemonic (`ReadOnlyWallet.restore`, always `Network.TESTNET`), queries
    the currently active `ChainQueryProvider` for candidate UTxOs and protocol parameters, and
    calls `TransactionBuilder.build` for a fixed 2 ADA payment to a reused cited CIP-19 testnet
    vector (`InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY`) with change to the wallet's own
    address; `:shared` adds no coin-selection, fee, or CBOR logic of its own. Success shows
    input/output counts, fee/change in lovelace, body size, and a truncated body-CBOR hex
    preview, always labeled unsigned; failure shows a cause-distinguishing message mapped from
    `TxBuildError`. No transaction id/body hash is computed (needs `:crypto`, deferred to
    `1.10`). `:shared` gained an explicit `:tx` dependency; no other module changed.
- `1.10` Transaction Signing — sign a testnet/preprod transaction locally. Split into
  `1.10a`/`1.10b-pre`/`1.10b`/`1.10c` (ADR-0015,
  `docs/DECISIONS/0015-transaction-signing.md`).
  - `1.10a` Transaction Signing ADR — **Status: complete (docs-only).** Outcome: ADR-0015
    resolves signing ownership (no new module — `:crypto` owns a backend-neutral `Signing`
    primitive, `:tx` owns crypto-free witness-set/full-`transaction` CBOR assembly from supplied
    `(vkey, signature)` pairs, `:wallet` owns orchestration through an explicitly-scoped,
    non-general-purpose entry point and gains a `:wallet → :tx` dependency, `:shared` displays
    only); scope (testnet/preprod only, the existing test fixture/restored wallet only, ADA-only
    single-payment `TransactionBuilder` drafts only — no mainnet/native assets/scripts/metadata/
    multisig) **and its fixture-only enforcement boundary (§2a)** — because `:wallet` cannot
    depend on `:shared`, it cannot itself recognize `TestWalletFixture`; Block 1.10 introduces no
    general-purpose wallet signing API, and the fixture-only scope is enforced instead by the
    Phase 1 call sites/checkpoint/tests passing the cited words/path and `Network.TESTNET`
    explicitly; the signing message (Ed25519-BIP32 signs
    the 32-byte `bodyHash = Blake2b-256(TransactionDraft.bodyCbor())`, i.e. the tx id — not the
    raw body bytes); the fee stance (Block 1.9's one-witness-per-input estimate can over-estimate
    for the single-key wallet, so 1.10 signs the existing body unchanged and defers exact
    witness-aware fee minimization); the artifact (full signed `transaction` CBOR + witness count
    + tx id, making the tx id displayable for the first time — the item ADR-0014 §2 deferred
    here); a **blocking backend gate** (see 1.10b-pre); the error model (`:crypto` `SigningError`,
    typed `:tx` assembly errors, `:wallet` wrapping, `finally` key clearing); the test/vector
    policy (no invented vectors; a citable extended-key KAT; structural CBOR tests; Android
    runtime verification); the Playground checkpoint; and the guardrail reconciliation. Narrows
    the "No transaction signing" guardrail to Block 1.10 scope while keeping every other ban. No
    Kotlin/Gradle/dependency/source changes.
  - `1.10b-pre` Signing backend + vector-source gate — **Status: complete. Gate result: backend
    ADOPTED and VERIFIED; Block 1.10b unblocked** (ADR-0016 §9i,
    `docs/DECISIONS/0016-transaction-signing-backend-gate.md`).
    Symbol-level inspection of the resolved artifacts confirmed **none can sign an extended key**:
    `org.hyperledger.identus:bip32-ed25519:1.8.8`'s native library exports only
    `derive_bytes`/`derive_bytes_pub`/`from_nonextended` (no `sign` symbol in the shipped Rust
    cdylib), Apollo's `KMMEdPrivateKey.sign` is BouncyCastle standard **seed-based** RFC-8032
    Ed25519, and the ionspin/lazysodium libsodium API is seed-based (`ed25519SkToSeed` confirms the
    `seed‖pk` layout). The **extended-key KAT is pinned**: the reference `ed25519-bip32 0.4.2`
    (MIT OR Apache-2.0) `xprv_sign` vector (64-byte extended scalar signs `"Hello World"` ⇒ fixed
    64-byte signature via `XPrv::sign`), with the CIP-0100 32-byte-body-hash vector as a secondary
    reproduce-to-confirm example; a plain RFC-8032 Ed25519 vector does **not** pass. ADR-0016 §8
    records that the recommended unblock path — a disposable `scratch-signing-backend` module
    exposing the crate's `XPrv::sign`/`verify` via a Gobley-0.3.7 uniffi/KMP wrapper, plus a second
    disposable `scratch-signing-backend:android` sibling module for the Android leg — has now
    **run, all four legs passing**: **JVM PASS** (real Gobley/JNA bindings, KAT reproduced, symbol
    proof), **iOS PASS** (compile/link, symbol proof), and **Android PASS** — a real
    `connectedAndroidDeviceTest` reproduces the KAT *through the packaged Kotlin/JNA bindings* on
    both a physical device and an emulator. Gobley's own Android Gradle integration remains
    incompatible with this repo's AGP 9.0.1 pin (upstream-confirmed, `gobley/gobley#153`); the
    Android leg instead invoked the same `gobley-uniffi-bindgen` CLI directly (library mode) and
    hand-wired the result into this SDK's `androidLibrary {}` KMP DSL. **That spike has now been
    ADOPTED and VERIFIED (ADR-0016 §9i)** into the permanent, project-owned module
    **`:crypto-signing-backend`** (crate `kardano-ed25519-bip32-signing`, `publish = false`,
    `ed25519-bip32 = "0.4.2"` pinned + `Cargo.lock`), landed as Option R1 (no Rust/Cargo/Gobley
    Gradle plugin; 8 committed native artifacts + pre-generated UniFFI bindings). Every §7d leg was
    re-run and **passes against the real module**: `jvmTest` 4/4 (macOS arm64);
    `connectedAndroidDeviceTest` 4/4 physical (Android 15) + 4/4 emulator (API 24) through the
    packaged bindings; `compileKotlinIosArm64` + `linkDebugTestIosSimulatorArm64` green; `nm`/`llvm-nm`
    symbol proof on all 8 artifacts. The disposable scratch modules are deleted; JVM native coverage
    is macOS-only by design (no CI in-repo; Linux/Windows = future work, ADR-0016 §9 R3). **Block
    1.10b is unblocked**, though the adoption block added no signing code and no `:crypto`→backend
    dependency.
  - `1.10b` `:crypto` `Signing` + `:tx` assembly + `:wallet` orchestration — **Status:
    complete** (ADR-0015 §9 result note). `:crypto` gained `Signing`/`SigningError` over the
    adopted `:crypto-signing-backend` plus a module-internal `extendedPrivateKeyBytesForSigning()`
    accessor (no public private-key byte exposure); `:tx` gained
    `VerificationKeyWitness`/`TransactionWitnessSet`/`SignedTransaction`/`TransactionAssembler`
    (still crypto-free; `:core`'s CBOR subset gained narrow `true`/`false`/`null` simple-value
    support this required, per the ADR-0001 addendum); `:wallet` gained the `:wallet → :tx`
    dependency and `ReadOnlyWallet.signTransaction(words, network, draft)` returning
    `WalletSignedTransaction`. All verification commands pass: `jvmTest` for
    `:crypto`/`:tx`/`:wallet`/`:crypto-signing-backend`; `testAndroidHostTest` for
    `:crypto`/`:tx`/`:wallet`; `:crypto-signing-backend:connectedAndroidDeviceTest` on a physical
    device and an emulator; `compileKotlinIosArm64` for all four modules; and
    `:crypto-signing-backend:linkDebugTestIosSimulatorArm64`.
  - `1.10c` `:shared` Android "Signed Transaction (not submitted)" checkpoint — **Status:
    complete, including manual Android runtime checkpoint.**
    `PlaygroundPresenter` gained a shared `buildTransactionDraft` helper (extracted from the
    1.9c `presentTransactionDraft`, reused unchanged by both checkpoints so they build the
    identical unsigned draft) and `presentSignedTransaction`, which signs that draft by calling
    `:wallet`'s `ReadOnlyWallet.signTransaction` with the cited fixture words/path and
    `Network.TESTNET` explicitly (ADR-0015 §2a). `PlaygroundScreen` gained a "Signed Transaction
    (not submitted)" section displaying the tx id, witness count, a truncated signed-tx CBOR
    preview, and the explicit "signed, not submitted — testnet-only, test fixture, no real funds"
    label. No submit code (Block 1.11). `:shared` gained no new Gradle module dependency (`:tx`
    and `:wallet` were already present from 1.9c/1.8b). While wiring this up, a pre-existing gap
    surfaced and was fixed as the minimum compile-forced change this block's guardrail allows:
    `PlaygroundPresenter.presentWalletError`/`presentTxBuildError` had not been updated for the
    `WalletError.Signing`/`WalletError.TransactionAssembly` and
    `TxBuildError.InvalidVerificationKeyLength`/`InvalidSignatureLength`/`EmptyWitnessSet`
    variants Block 1.10b added — `:shared` did not compile without those `when` branches (plus a
    new `presentSigningError` for `SigningError`); no `:crypto`/`:tx`/`:wallet` behavior changed.
    Tests: `PlaygroundSignedTransactionPresenterTest` (`commonTest`, native-free error-mapping)
    and `PlaygroundSignedTransactionDesktopTest` (`jvmTest`-only, end-to-end sign-and-display,
    plus the honest "no UTxOs" default-mock case). All verification commands pass:
    `:shared:jvmTest`, `:shared:testAndroidHostTest`, `:shared:compileKotlinIosArm64`,
    `:shared:compileKotlinIosSimulatorArm64`. The project owner then verified the new section
    manually on Android with live Blockfrost preprod: after correcting the preprod `project_id`,
    "Sign transaction" displayed a transaction id, witness count `1`, a truncated signed-CBOR
    preview (`288B total`), and the "signed, not submitted — testnet-only, test fixture, no real
    funds" label, with no submit action invoked.
- `1.11` Submit Transaction — submit a signed transaction to preprod. Split into
  `1.11a`/`1.11b`/`1.11c`/`1.11d`/`1.11d-2` (ADR-0017, plus the ADR-0006/0007/0014 2026-07-13
  addenda for `1.11d`, and a second ADR-0006/0014 2026-07-13 addendum for `1.11d-2`). `1.11a`
  (`:provider` boundary — `TxSubmitProvider`, `SubmitError`,
  `InMemoryTxSubmitProvider`, which never fakes success) — **Status: complete.** `1.11b`
  (`:provider-blockfrost`'s `BlockfrostTxSubmitProvider`: `POST /tx/submit`,
  `Content-Type: application/cbor`, quoted-hex-string response mapped to `TxHash`, HTTP status
  mapped to `SubmitError` including a parsed Blockfrost error-envelope `detail`; MockEngine
  tests only, no automated live submit test) — **Status: complete.** `1.11c` (`:shared`
  "Submit Transaction (preprod)" Playground checkpoint: builds and signs the same fixture
  draft as Block 1.10c, then calls `TxSubmitProvider.submit(...)` directly — no new `:wallet`
  orchestration method; `activeSubmitProvider` wired alongside `activeProvider`, defaulting to
  `InMemoryTxSubmitProvider()` and switching to `BlockfrostTxSubmitProvider` under the existing
  live toggle/`project_id`; shows the accepted id, local id, match status, and a
  submitted/preprod/fixture label on success, every `SubmitError` variant on failure, no
  polling) — **Status: implementation complete.** Its manual Android checkpoint was attempted
  and found a real bug: a preprod address funded with mixed (ADA + native-asset) UTxOs let a
  draft build and sign, then the node rejected the submitted transaction with
  `ValueNotConservedUTxO` — the build silently dropped the native assets those inputs carried.
  `1.11d` (ADA-only rejection — **Status: superseded by `1.11d-2` below**) first fixed this
  honestly rather than working around it: `:provider`'s `Value` gains a
  `hasNativeAssets: Boolean = false` presence flag (no quantities/policy ids/asset names, still
  current); `:provider-blockfrost`'s `mapUtxo` sets it whenever a Blockfrost `amount` entry's
  `unit != "lovelace"`, instead of silently dropping that entry (still current); but `:tx`'s
  `TransactionBuilder.build` initially rejected the **entire** candidate list with
  `TxBuildError.UnsupportedFeature` if any candidate input had the flag set — too broad for a
  real wallet with a *mix* of ADA-only and native-asset UTxOs, which `1.11d-2` immediately
  narrows. `1.11d-2` (ADA-only UTxO filtering, not whole-wallet rejection — **Status:
  implementation complete; manual re-validation partial pass**): `TransactionBuilder.build` now
  drops every candidate with the flag set **before** coin selection, then builds normally from
  the remaining ADA-only candidates — `TxBuildError.UnsupportedFeature` is returned only if
  that leaves no candidates at all, and the usual `TxBuildError.InsufficientFunds` (its
  `available` total reflecting only the ADA-only candidates) fires if those remaining
  candidates still cannot cover `payment + fee`; a native-asset UTxO is never selected as an
  input either way. `:shared`'s `presentTxBuildError` rewords the `UnsupportedFeature` message
  to "This wallet has no ADA-only UTxOs to spend — only UTxOs containing native assets/tokens.
  Phase 1 only builds ADA-only transactions." New/updated tests across `:tx` and `:shared` cover
  the mixed-sufficient success case, the mixed-insufficient failure case (proving the
  native-asset UTxO's lovelace is excluded), and the all-native-asset failure case (see
  `docs/PHASE_1_PLAN.md` `1.11d`/`1.11d-2` for the full list). Manual Android re-validation has
  a partial pass: the mixed ADA-only + native-asset case built, signed, and submitted from
  ADA-only UTxOs, and the accepted transaction id matched the locally signed id
  (`331a79ece991fc9bfd98e9da2a5514f38f7ffeb3a08f1bd7e5a1f75af0e42416`). Block 1.11 as a whole
  is not complete until the remaining all-native-asset rejection and ADA-only-only build/submit
  checks are run and recorded (see `docs/HANDOFF.md`).
- `1.12` Phase 1 Closure / MVP Review — verify the full Android demo flow and document
  remaining limitations.

Expected packages/modules (candidate names, not committed; per Block 1.1 / ADR-0005 these
start as packages and are extracted into Gradle modules only when a block introduces
dependency or ownership pressure that justifies the split — see ADR-0002/0003):

- `crypto`
- `wallet`
- `tx`
- `provider`
- `provider-blockfrost`

Expected capabilities:

- Wallet create/restore.
- Address generation.
- UTxO fetching.
- Protocol parameter fetching.
- ADA-only transaction builder.
- Fee and change calculation.
- Local signing.
- CBOR serialization.
- Submit transaction.

Deferred out of the first MVP (per Block 1.1 / ADR-0005):

- Native asset transaction builder.
- Providers other than the first preprod target (Koios, Maestro, Ogmios, Kupo).
- Byron/Base58 address support.

Acceptance criteria (reconciled by Block 1.1 / ADR-0005 to Android-primary):

- End-to-end ADA-only preprod transaction works, verified through the Android app.
- Android sample works and is the primary Phase 1 validation surface.
- iOS and JVM/Desktop targets compile; functional demos are deferred to Phase 1 closure
  (Block 1.12) or Phase 2 unless a future block explicitly revisits this.
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

