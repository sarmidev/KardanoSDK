# Kardano SDK - Handoff

## Purpose

This file exists so the project can be resumed by the owner, Cursor, ChatGPT or another AI assistant without relying on chat history.

Update it at the end of each work session.

## Current Project Context

Kardano SDK is an open-source Kotlin Multiplatform SDK for native Cardano mobile apps.

Current project identity:

- Name: Kardano SDK.
- Package/group: `org.sarmidev.kardano`.
- Main targets: Android, iOS, JVM/Desktop.
- Current status: Phase 0 in progress. Blocks 0.1 (Project Governance And AI Rules),
  0.2 (SDK-Oriented Module Structure), and 0.3 (Testing Infrastructure) are complete: a
  UI-free `:core` module exists, `:shared` depends on it, and the testing foundation
  (test source-set strategy, fixture layout, test-vector policy in `docs/TESTING.md`) is
  in place. Block 0.4 (Core Primitives) is complete: `KardanoResult`, `Network`,
  `Lovelace`, and the byte-backed primitives (`TxHash`, `PolicyId`, `AssetName`, `UtxoRef`)
  and their tests have landed in `:core`.   ADR-0001 (CBOR/parser policy) is now Accepted
  (constrained internal Bech32/Bech32m and CBOR subset; no external dependency). Block 0.5
  (Encoding Utilities) is complete: a generic, bounded `Hex` codec, a generic, bounded
  Bech32/Bech32m codec, and the Cardano HRP allowlist wrappers (`CardanoBech32` /
  `CardanoHrp` / `CardanoBech32Error`) have landed in `:core`. The next block is 0.6 (CBOR
  subset).

Business goal:

> Build the first credible mobile-first KMP SDK for Cardano apps, focused on shared Android/iOS Cardano logic.

Technical goal for Phase 0:

> Create a tested, documented foundation before implementing wallet creation, transaction signing or real network flows.

## Important Files

Read these first:

- `docs/PROJECT_BRIEF.md`
- `docs/ROADMAP.md`
- `docs/AI_WORKING_AGREEMENT.md`
- `docs/SECURITY.md`
- `docs/DECISIONS/0001-cbor-and-parser-policy.md` or equivalent ADR path
- Cursor rule files, usually under `.cursor/rules/`

If paths differ, locate files by name.

## Current Phase

Current phase:

- Phase 0 - Core Foundation.

Block status:

- Block 0.1 Project Governance And AI Rules: complete (all deliverables exist and are
  consistent — see `docs/ROADMAP.md`).
- Block 0.2 SDK-Oriented Module Structure: complete. UI-free `:core` module introduced;
  `Platform` moved into it; `:shared` depends on `:core` and remains the sample/UI host.
  The `:core` + `:shared` split is the settled Phase 0 module structure; further splits are
  deferred. See `docs/DECISIONS/0002-module-structure.md`.
- Block 0.3 Testing Infrastructure: complete. Added `docs/TESTING.md` (test source-set
  strategy, fixture layout, external test-vector policy), a `core/.../resources/fixtures/`
  folder structure with placeholder READMEs citing future sources, and a minimal `:core`
  `jvmTest` smoke test. See `docs/ROADMAP.md` Block 0.3 Outcome.
- Block 0.4 Core Primitives: complete. First step landed a shared `KardanoResult<T, E>`
  (`Ok` / `Err`) type, `Network` (`TESTNET` = 0, `MAINNET` = 1) with a typed `fromId`, and
  `Lovelace` (`@JvmInline value class` over `Long`, range `0..Long.MAX_VALUE`, negatives
  rejected, no arithmetic). Final step added byte-backed structural value types: `TxHash`
  (32 bytes), `PolicyId` (28 bytes), `AssetName` (0..32 bytes) sharing a `ByteSizeError`,
  and `UtxoRef` (`TxHash` + non-negative output index) with `UtxoRefError`. All have
  valid/invalid/edge tests in `core/src/commonTest`. `Address` was deferred to Block 0.7.
  See `docs/ROADMAP.md` Block 0.4 Outcome.
- Block 0.5 Encoding Utilities: complete. The Hex step landed a generic, bounded `Hex`
  codec in `:core` (`Hex.encode` / `Hex.decode`) with a typed `HexError`
  (`InputTooLong` / `OddLength` / `InvalidCharacter`), a named limit `Hex.MAX_INPUT_CHARS`,
  canonical lowercase encoding, mixed-case decoding, and validation before allocation. The
  Bech32 step landed a generic, bounded Bech32/Bech32m codec in `:core` (`Bech32.encode` /
  `Bech32.decode`, `Bech32Variant`, `Bech32Decoded`, `Bech32Error`) working at the 5-bit data
  layer: variant auto-detection on decode, mixed-case rejection, lowercase encoder output,
  HRP/separator/charset/checksum validation, and SDK-owned limits (`MAX_INPUT_CHARS`,
  `MAX_HRP_CHARS`, `MAX_DATA_VALUES`, plus `MAX_DATA_BYTES` for the internal `convertBits`)
  enforced with typed errors before allocation. Tests use the official BIP-173/BIP-350
  vectors verbatim plus edge/limit/round-trip cases. The final step added the Cardano HRP
  allowlist wrappers (`CardanoHrp`, `CardanoBech32`, `CardanoBech32Error`): `encode` takes a
  `CardanoHrp` and forces Bech32; `decode` delegates to the engine, then checks the HRP
  allowlist first and the variant second, rejecting Bech32m and non-allowlisted HRPs with a
  typed error while propagating generic failures via `Underlying`. HRP allowlist plus Bech32
  checksum/charset validation only — no address parsing, header inspection, or network-id
  reading. No dependencies or Gradle changes. See `docs/ROADMAP.md` Block 0.5 Outcome.

Next recommended task: Block 0.6 (CBOR subset) per ADR-0001 (RFC 8949 Appendix A vectors,
no external dependency, no AI-invented vectors).

Current modules:

- `:core` (UI-free SDK core seed)
- `:shared` (sample/UI host; builds the iOS `Shared` framework)
- `:androidApp`, `:desktopApp`, and `iosApp` (Xcode entry point)

Current priority:

- Keep scope tight.
- Avoid custom crypto.
- Avoid transaction signing.
- Build tests and docs from the start.
- Work through the Phase 0 blocks in `docs/ROADMAP.md` from 0.3 through 0.9.

## Decisions Already Made

- The project is mobile-first and KMP-first.
- Android and iOS are primary targets.
- JVM/Desktop is included for fast testing, demos and tooling.
- Web/Wasm is not a priority for Phase 0.
- Phase 0 must not implement transaction signing.
- Phase 0 must not implement custom cryptography.
- Public APIs must be documented.
- Unit tests are required for primitives, parsers, encoders and validators.
- CBOR must not be implemented before a documented technical decision.
- Parser limits and anti-DoS behavior must be explicit.
- Address validation must preserve and check network id.
- iOS/Swift error handling must be considered from the beginning.

## Open Decisions

These should be resolved before or during Phase 0 implementation:

1. Final module structure:
   - A UI-free `:core` module has been introduced (ADR-0002). The final structure is still
     open: whether/when to add `:crypto`, `:wallet`, `:tx`, `:provider`, and whether
     `:shared` later becomes a dedicated `:sample:*` module.

2. CBOR strategy: **Resolved** (ADR-0001 Accepted) — constrained internal CBOR subset
   (definite-length only), no external dependency. Implementation follows ADR-0001.

3. Bech32 strategy: **Resolved and implemented** (ADR-0001 Accepted) — a constrained internal
   generic Bech32/Bech32m codec has landed in `:core` with verbatim BIP-173/BIP-350 vectors and
   no external dependency, plus the Cardano HRP allowlist wrappers (`CardanoBech32`). Block 0.5
   is complete.

4. Crypto strategy:
   - Which library or binding will eventually support Ed25519/BIP32/CIP-1852?
   - What targets are supported?

5. Test vector sources:
   - The authoritative spec sources are now documented in `docs/TESTING.md` (Bech32/Bech32m
     → BIP-173/350; CBOR → RFC 8949 Appendix A; addresses → CIP-19). The specific
     tooling/reference repos used to copy vectors verbatim are still chosen per feature as
     it is implemented.

## What Not To Do Yet

Do not implement:

- Mnemonic generation.
- Private key handling.
- Transaction signing.
- Transaction submission.
- Real wallet flows.
- Plutus support.
- Staking or delegation.
- Hardware wallet behavior.
- Production security claims.

Do not use:

- Invented test vectors for protocol behavior.
- Handwritten cryptographic algorithms.
- Lenient parsers that accept malformed input to make tests pass.
- `ByteArray == ByteArray` for content equality.

## Session Update Template

At the end of each session, update this section.

### Last Session Summary

Date: 2026-06-29

Summary:

- Implemented the Cardano HRP allowlist wrappers step of Block 0.5, completing the block.
  Added three new `:core` source files: `CardanoHrp` (allowlist enum `ADDR` / `ADDR_TEST` /
  `STAKE` / `STAKE_TEST` with a lowercase `value` and an `internal fromValue` lookup),
  `CardanoBech32` (`object` with `encode(hrp: CardanoHrp, data5Bit): KardanoResult<String,
  CardanoBech32Error>` forcing `Bech32Variant.BECH32`, and `decode(input): KardanoResult<
  Bech32Decoded, CardanoBech32Error>`), and `CardanoBech32Error` (`Underlying` /
  `UnsupportedHrp` / `UnsupportedVariant`).
- Design decisions: the wrappers expose no variant parameter (Cardano uses Bech32, not
  Bech32m); `decode` delegates to the generic engine, then checks the HRP allowlist **first**
  and the variant **second** — so a Bech32m string with an unsupported HRP returns
  `UnsupportedHrp` (the more domain-specific error) and a Bech32m string with an allowlisted
  HRP returns `UnsupportedVariant`. `Bech32Decoded` is reused; no new carrier type. KDoc on
  every public declaration states this is HRP allowlist + Bech32 checksum/charset validation
  only, not CIP-19 structural address validation, phrased defensively ("does not prove").
- Added `CardanoBech32Test` in `core/src/commonTest`: valid strings are generated with the
  generic engine (no real addresses, no funds, no CIP-19 vectors). Covers encode/decode/
  round-trip for the four HRPs, unsupported-HRP rejection, propagated generic checksum and
  charset errors via `Underlying`, Bech32m rejection, and the HRP-before-variant check order.
- The generic engine was not modified; no dependencies or Gradle changes.

Files changed this step:

- `core/src/commonMain/kotlin/org/sarmidev/kardano/CardanoHrp.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/CardanoBech32.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/CardanoBech32Error.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/CardanoBech32Test.kt` (new)
- `core/README.md`, `docs/ROADMAP.md`, `docs/HANDOFF.md`

### Previous Session Summary

Date: 2026-06-29

Summary:

- Implemented the Bech32/Bech32m step of Block 0.5 Encoding Utilities: a generic, bounded
  Bech32/Bech32m codec in `:core` per ADR-0001. Added `Bech32` (`object`) with
  `encode(hrp, data, variant): KardanoResult<String, Bech32Error>` and
  `decode(input): KardanoResult<Bech32Decoded, Bech32Error>` (neither throws), a
  `Bech32Variant` enum (`BECH32` / `BECH32M`, internal checksum constants), a `Bech32Decoded`
  carrier (regular class — not `data class` — with defensive copies, `contentEquals` /
  `contentHashCode`, and a `toData5BitArray()` accessor), and a typed `Bech32Error` sealed
  interface.
- Why: ADR-0001 sequences Block 0.5 as Hex first, then Bech32/Bech32m.
- Design: the public API works at the **5-bit data layer** (each data value `0..31`), which
  is exactly what the official BIP-173/350 generic vectors validate; the 5/8-bit `convertBits`
  helper is internal. `decode` auto-detects the variant from the checksum constant, rejects
  mixed case, and validates length / separator (last `1`) / HRP (chars `33..126`, length) /
  data charset / checksum, allocating the result only after all checks. `encode` rejects data
  values outside `0..31` (`DataValueOutOfRange`) and emits canonical lowercase.
- Limits (SDK-owned, revisable, enforced before allocation with typed errors):
  `MAX_INPUT_CHARS = 1023`, `MAX_HRP_CHARS = 83`, `MAX_DATA_VALUES = 1016` (5-bit layer), and
  `MAX_DATA_BYTES = 640` (8-bit `convertBits` output only). BIP-173's 90-char cap is
  intentionally not applied (CIP-19 addresses can exceed it).
- Added `Bech32Test` in `core/src/commonTest` using the official BIP-173 and BIP-350 valid and
  invalid vectors verbatim (cited inline), plus mixed-case, HRP, separator, charset, checksum,
  cross-variant, over-limit, padding, and round-trip cases. No AI-invented vectors.

Files changed:

- `core/src/commonMain/kotlin/org/sarmidev/kardano/Bech32.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/Bech32Variant.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/Bech32Decoded.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/Bech32Error.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/Bech32Test.kt` (new)
- `core/README.md`, `core/src/commonTest/resources/fixtures/README.md`,
  `core/src/commonTest/resources/fixtures/bech32/README.md`, `docs/ROADMAP.md`,
  `docs/HANDOFF.md`

Tests run:

- `./gradlew :core:jvmTest` (pass), `./gradlew :core:testAndroidHostTest` (pass),
  `./gradlew :core:compileTestKotlinIosSimulatorArm64` (iOS test sources compile).

Docs updated:

- `core/README.md`, both fixture `README.md` files, `docs/ROADMAP.md`, `docs/HANDOFF.md`.

Decisions made:

- Public Bech32 API operates at the 5-bit data layer; `convertBits` (5/8-bit) is internal.
  This lets the official generic vectors validate the HRP/charset/checksum layer directly,
  without forcing a 5→8 conversion that those vectors are not required to satisfy.
- `Bech32Decoded` is a regular class (not `data class`) so its `ByteArray` uses
  `contentEquals` / `contentHashCode` and defensive copies.
- Added `MAX_DATA_VALUES` as a new SDK-owned 5-bit-layer limit alongside the three limit
  names ADR-0001 lists (`MAX_INPUT_CHARS`, `MAX_HRP_CHARS`, `MAX_DATA_BYTES`); `MAX_DATA_BYTES`
  now bounds only the internal `convertBits` 8-bit output.
- The "overall max length exceeded" invalid vectors are rejected via the SDK HRP-length limit
  (their HRP is 84 chars, exceeding the 83-char `MAX_HRP_CHARS`), not via BIP-173's 90-char
  overall cap, consistent with ADR-0001.
- Block 0.5 stays **in progress** (not complete) until the Cardano HRP allowlist wrappers are
  added (deferred to a follow-up / Block 0.7).

Risks or concerns:

- The numeric limit values are SDK-owned starting points (documented as revisable). They are
  chosen to accept all official vectors and keep the limits mutually consistent backstops.
- iOS simulator tests were not executed (environment can fail); only the iOS test sources
  were compiled (`compileTestKotlinIosSimulatorArm64`).

Next recommended task:

- Either add the Cardano HRP allowlist wrappers (`addr`, `addr_test`, `stake`, `stake_test`)
  on top of the generic engine, or move to Block 0.6 (CBOR subset) per ADR-0001 (RFC 8949
  Appendix A vectors). Do not add dependencies; do not implement crypto or signing.

## Prompt For Cursor Business/Product Work

Use this prompt in Cursor Ask mode when working on business or product strategy:

```text
Act as a product and business strategy advisor for Kardano SDK.

Use these files as source of truth:
- docs/PROJECT_BRIEF.md
- docs/ROADMAP.md
- docs/HANDOFF.md
- docs/AI_WORKING_AGREEMENT.md
- docs/SECURITY.md
- ADR files under docs/DECISIONS/

Do not edit source code.

Focus only on:
- product positioning
- MVP scope
- roadmap
- adoption strategy
- Cardano ecosystem fit
- grants and funding
- documentation strategy
- developer experience

If you recommend changes, explain why and list the exact docs that should be updated.
```

## Prompt For Cursor Technical Planning

Use this prompt before implementation tasks:

```text
Act as a senior Kotlin Multiplatform engineer and security-conscious SDK maintainer.

Read:
- docs/PROJECT_BRIEF.md
- docs/ROADMAP.md
- docs/HANDOFF.md
- docs/AI_WORKING_AGREEMENT.md
- docs/SECURITY.md
- ADR files under docs/DECISIONS/

Do not edit files yet.

Plan the next small implementation task.

Return:
- objective
- files likely affected
- tests required
- docs required
- risks
- exact acceptance criteria
- whether this is appropriate for Agent mode
```

## Prompt For Updating This Handoff

Use this at the end of a Cursor session:

```text
Update docs/HANDOFF.md with the latest session state.

Include:
- what changed
- why it changed
- files touched
- tests run
- docs updated
- decisions made
- current risks
- next recommended task

Do not modify source code.
```

