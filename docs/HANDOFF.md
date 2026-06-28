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
- Current status: Phase 0 in progress. Blocks 0.1 (Project Governance And AI Rules) and
  0.2 (SDK-Oriented Module Structure) are complete: a UI-free `:core` module exists and
  `:shared` depends on it. Next is Block 0.3 (Testing Infrastructure).

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
- Block 0.3 Testing Infrastructure: not started (next recommended task).

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
   - Which official specs/tools/repos will be used?

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

- Documentation-only cleanup to close Block 0.2 after `:core` was introduced and verified.
- Why: the docs still had inconsistencies from introducing `:core` (it was listed both as a
  current module and as a deferred candidate), the root README listed only `:shared` test
  commands, and Block 0.2 was still marked in progress.
- Marked Block 0.2 complete in `docs/ROADMAP.md`, removed `:core` from the deferred candidate
  list (it now appears only under current modules), and recorded that the `:core` + `:shared`
  split is the settled Phase 0 module structure.
- Added the `:core` JVM test command to `README.md` and clarified tests run per module.
- Updated this handoff: marked Block 0.2 complete and set Block 0.3 Testing Infrastructure as
  the next recommended task.

Files changed:

- `docs/ROADMAP.md`
- `docs/HANDOFF.md`
- `README.md`

Tests run:

- None. This is a documentation-only change, so no Gradle tasks were run.

Docs updated:

- `docs/ROADMAP.md`
- `docs/HANDOFF.md`
- `README.md`

Decisions made:

- The current `:core` + `:shared` structure is the settled Phase 0 module structure;
  Block 0.2 is complete and further module splits are deferred until code justifies them.
- ADR-0002 stays Accepted; ADR-0001 (CBOR/parser policy) stays Open. No ADR changes needed.

Risks or concerns:

- `:shared` still carries Compose because the iOS app needs a Kotlin-produced UI framework;
  the UI-free direction lives in `:core`. A later step may migrate `:shared` to a dedicated
  `:sample:*` module (touches the Xcode project).
- No `LICENSE` file exists yet; license selection remains an owner decision.

Next recommended task:

- Begin Block 0.3 Testing Infrastructure (commonTest/jvmTest structure, fixture folders,
  test-vector policy). Do not add further modules without a documented reason.

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

