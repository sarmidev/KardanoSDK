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
  in place. Next is Block 0.4 (Core Primitives).

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

Next recommended task: Block 0.4 Core Primitives.

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

- Executed Block 0.3 Testing Infrastructure: a small, reviewable testing-foundation pass.
- Why: the roadmap requires a documented testing strategy, fixture layout, and test-vector
  policy before any protocol logic is implemented, so later primitive/parser work lands on
  a consistent, documented base.
- Added `docs/TESTING.md` describing test source-set expectations (`commonTest`, `jvmTest`,
  Android host tests, iOS tests), fixture folder layout, the external test-vector policy
  (verbatim from cited specs; no AI-invented vectors; validators not weakened), and the
  verification commands.
- Added a fixture folder structure under `core/src/commonTest/resources/fixtures/` with a
  top-level `README.md` and placeholder subfolders (`bech32/`, `cbor/`, `address/`) naming
  future authoritative sources (BIP-173/350, RFC 8949 Appendix A, CIP-19). No protocol
  vectors were added. Added a `shared/.../fixtures/README.md` note keeping protocol vectors
  in `:core`.
- Added a minimal `:core` `jvmTest` smoke test (`JvmTestWiringTest`) verifying JVM test
  wiring; no production code changed.
- Linked `docs/TESTING.md` from `README.md`, `core/README.md`, and `shared/README.md`, and
  marked Block 0.3 complete in `docs/ROADMAP.md`.

Files changed:

- `docs/TESTING.md` (new)
- `core/src/commonTest/resources/fixtures/README.md` (new)
- `core/src/commonTest/resources/fixtures/bech32/README.md` (new)
- `core/src/commonTest/resources/fixtures/cbor/README.md` (new)
- `core/src/commonTest/resources/fixtures/address/README.md` (new)
- `shared/src/commonTest/resources/fixtures/README.md` (new)
- `core/src/jvmTest/kotlin/org/sarmidev/kardano/JvmTestWiringTest.kt` (new)
- `README.md`
- `core/README.md`
- `shared/README.md`
- `docs/ROADMAP.md`
- `docs/HANDOFF.md`

Tests run:

- `./gradlew :core:jvmTest` — pass (includes the new `JvmTestWiringTest`).
- `./gradlew :shared:jvmTest` — pass.
- `./gradlew :shared:testAndroidHostTest` — pass.
- `./gradlew :shared:iosSimulatorArm64Test` — compiles and links, but the simulator run did
  not execute on this machine: "Xcode does not support simulator tests for
  ios_simulator_arm64. Check that requested SDK is installed." This is an environment/SDK
  limitation, not a code failure.

Docs updated:

- `docs/TESTING.md` (new), `README.md`, `core/README.md`, `shared/README.md`,
  `docs/ROADMAP.md`, `docs/HANDOFF.md`.

Decisions made:

- Block 0.3 is complete: the testing strategy, fixture layout, and test-vector policy are
  documented and the source-set wiring is exercised by passing JVM/Android host tests.
- Protocol vectors live in `:core` fixtures, added only alongside the feature that uses
  them; `:shared` carries no protocol vectors.
- No dependencies added. ADR-0001 (CBOR/parser policy) stays Open; ADR-0002 stays Accepted.

Risks or concerns:

- `:shared:iosSimulatorArm64Test` could not run on this machine (missing iOS simulator SDK);
  iOS test execution should be confirmed on a macOS/Xcode environment with a simulator
  installed. The iOS test target does compile and link.
- Fixture subfolders are intentionally empty of vectors; reviewers should not expect vectors
  until the matching Phase 0 feature (Bech32/CBOR/address) is implemented.
- `:shared` still carries Compose (iOS UI framework dependency); UI-free direction lives in
  `:core`. No `LICENSE` file exists yet; license selection remains an owner decision.

Next recommended task:

- Begin Block 0.4 Core Primitives (e.g. `Network`, `Lovelace`, byte-wrapper value types) in
  `:core`, with valid/invalid/edge tests in `core/src/commonTest`. Do not implement crypto,
  signing, or add modules without a documented reason; ADR-0001 must be resolved before any
  CBOR/Bech32 implementation.

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

