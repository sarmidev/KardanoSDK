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

Goal:

Introduce value types for basic Cardano concepts.

Candidate primitives:

- `Network`
- `Lovelace`
- `TxHash`
- `PolicyId`
- `AssetName`
- `Address`
- `UtxoRef`

Acceptance criteria:

- Public APIs have KDoc.
- Invalid values are rejected.
- Valid, invalid and edge cases are tested.
- ByteArray wrappers use defensive copies.
- ByteArray equality uses `contentEquals` / `contentHashCode`.
- No silent truncation of numeric values.

### 0.5 Encoding Utilities

Goal:

Implement or decide bounded utilities for public encoded formats.

Candidate areas:

- Hex.
- Bech32.
- Base encodings only if needed.

Acceptance criteria:

- Strings are allowed for encoded public formats.
- Internal binary representation should use byte wrappers.
- Invalid characters are rejected.
- Invalid checksums are rejected.
- Tests include official or cited vectors where possible.
- Parsers are not made lenient to pass tests.

### 0.6 CBOR And Parser Strategy

Goal:

Decide how Kardano SDK will handle CBOR and binary parsers before implementation.

Options to evaluate:

- Vetted KMP library.
- Small constrained internal subset.
- Wrapper/platform-specific approach.

Acceptance criteria:

- ADR exists for CBOR/parser policy.
- Named parser limits are defined.
- No allocation directly from untrusted declared length.
- Max input size, max depth and max element count are defined.
- Unsupported, malformed, trailing or non-canonical encodings are rejected unless explicitly documented.
- Integer range policy is defined.
- Bignum/BigInteger support is explicitly in or out of Phase 0.

### 0.7 Address Parsing And Structural Validation

Goal:

Support structural validation of Cardano addresses.

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

