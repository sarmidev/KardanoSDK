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
  and their tests have landed in `:core`. Next is Block 0.5 (Encoding Utilities).

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

Next recommended task: Block 0.5 Encoding Utilities. ADR-0001 (CBOR/parser policy) stays
Open and must be resolved before any Bech32/CBOR implementation.

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

2. CBOR strategy:
   - Vetted KMP library?
   - Small constrained internal subset?
   - Wrapper/platform-specific approach?

3. Bech32 strategy:
   - Implement internally with external vectors?
   - Use a vetted library?

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

- Completed Block 0.4 Core Primitives by adding the remaining byte-backed value types in
  `:core`: a small, reviewable pass building on the earlier `KardanoResult`/`Network`/
  `Lovelace` step.
- Why: Block 0.4 calls for value types for basic Cardano concepts; these byte containers are
  the structural ones that do not depend on hex/Bech32/CBOR or address parsing, so they can
  land now while `Address` waits for Block 0.7.
- Added `ByteSizeError` (`Fixed(expected, actual)` / `Range(min, max, actual)`), a shared
  typed error for byte-length validation.
- Added `TxHash` (exactly 32 bytes) and `PolicyId` (exactly 28 bytes): private constructor,
  `of(bytes)` returning `KardanoResult<_, ByteSizeError>`, defensive copy on construction and
  from `toByteArray()`, `equals`/`hashCode` via `contentEquals`/`contentHashCode`, and a
  structural `toString()` that does not render bytes or hex.
- Added `AssetName` (0..32 bytes, empty valid) with the same shape, using
  `ByteSizeError.Range` for out-of-range lengths.
- Added `UtxoRef` (regular class, not a data class) wrapping a `TxHash` and a non-negative
  `outputIndex` (`0..Long.MAX_VALUE`), with `UtxoRefError.NegativeIndex` and equality based
  on `txHash` content plus index.
- Added valid/invalid/edge tests in `core/src/commonTest` (`TxHashTest`, `PolicyIdTest`,
  `AssetNameTest`, `UtxoRefTest`) covering exact-length/range validation, length boundaries,
  defensive copying (construction and accessor), and content equality/hashCode. Hand-written
  cases only; no fixtures or external vectors.
- Updated `core/README.md` and `docs/ROADMAP.md` (Block 0.4 marked complete; `Address`
  recorded as deferred to Block 0.7) and this handoff. No Gradle, dependency, or ADR changes.

Files changed:

- `core/src/commonMain/kotlin/org/sarmidev/kardano/ByteSizeError.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/TxHash.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/PolicyId.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/AssetName.kt` (new)
- `core/src/commonMain/kotlin/org/sarmidev/kardano/UtxoRef.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/TxHashTest.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/PolicyIdTest.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/AssetNameTest.kt` (new)
- `core/src/commonTest/kotlin/org/sarmidev/kardano/UtxoRefTest.kt` (new)
- `core/README.md`
- `docs/ROADMAP.md`
- `docs/HANDOFF.md`

Tests run:

- `./gradlew :core:compileKotlinJvm` — pass.
- `./gradlew :core:jvmTest` — pass.
- `./gradlew :core:testAndroidHostTest` — pass.
- `./gradlew :core:compileTestKotlinIosSimulatorArm64` — pass (compiles and links the iOS
  test binary; the simulator run itself was not executed).

Docs updated:

- `core/README.md`, `docs/ROADMAP.md`, `docs/HANDOFF.md`.

Decisions made:

- Block 0.4 is complete. The byte-backed primitives (`TxHash`, `PolicyId`, `AssetName`,
  `UtxoRef`) join the earlier `KardanoResult`/`Network`/`Lovelace`. `Address` is deferred to
  Block 0.7 (address parsing / CIP-19 validation), not dropped.
- `TxHash`/`PolicyId`/`AssetName` share one `ByteSizeError` because they fail only on length;
  `UtxoRef` keeps its own `UtxoRefError` for the distinct negative-index case.
- `UtxoRef` is a regular class (not a `data class`) so its generated `copy()` cannot bypass
  the non-negative-index factory check.
- No hex APIs were added (hex is Block 0.5). No dependencies added. ADR-0001 (CBOR/parser
  policy) stays Open; ADR-0002 stays Accepted.

Risks or concerns:

- These types do not validate cryptographic correctness, hash origin, on-chain existence, or
  spendability; KDoc states they are structural containers only.
- `toString()` is intentionally byte-free; callers needing a textual form must wait for the
  hex utilities in Block 0.5.
- The byte primitives wrap an already-materialized caller `ByteArray`, so the parser
  anti-DoS "never allocate from an untrusted length" rule is not triggered here; that rule
  still applies to the future Bech32/CBOR parsers.
- iOS simulator tests were not executed on this machine (missing simulator SDK noted in
  prior sessions); the iOS test binary compiles and links.

Next recommended task:

- Begin Block 0.5 Encoding Utilities (hex first; Bech32 only after ADR-0001 is resolved).
  ADR-0001 (CBOR/parser policy) must move from Open to Accepted before any Bech32/CBOR code.
  Do not implement crypto or signing.

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

