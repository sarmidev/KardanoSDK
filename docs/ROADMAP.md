# Kardano SDK - Roadmap

## Current Status

The project has been created from the Kotlin Multiplatform wizard.

Selected targets:

- Android.
- iOS.
- JVM/Desktop.

Current priority:

> Build a safe Phase 0 foundation before implementing wallet behavior, signing or transaction submission.

## Phase 0 - Safe Core Foundation

Goal:

Create the technical base of Kardano SDK with strong tests, documentation and security boundaries.

Expected outputs:

- Project guidance and AI working agreement.
- Security policy.
- Parser and CBOR policy ADR.
- SDK-oriented module plan.
- Testing strategy.
- Documentation strategy.
- Core primitives.
- Encoding utilities.
- Address validation strategy.
- Crypto strategy document.

Strict non-goals:

- No transaction signing.
- No custom cryptography.
- No real mnemonics or private keys.
- No real funds.
- No production-ready claims.

## Phase 0 Suggested Task Order

### 0.1 Project Rules And Docs

Status: in progress.

Deliverables:

- `docs/AI_WORKING_AGREEMENT.md`
- `SECURITY.md`
- Cursor rules.
- CBOR/parser ADR.
- `docs/PROJECT_BRIEF.md`
- `docs/ROADMAP.md`
- `docs/HANDOFF.md`

Acceptance criteria:

- The project has clear AI coding rules.
- Security-sensitive boundaries are explicit.
- The business/product context is documented.

### 0.2 Module Structure

Goal:

Move from wizard-generated app structure toward an SDK-oriented structure.

Candidate modules:

- `:core`
- `:crypto`
- `:wallet`
- `:tx`
- `:provider`
- `:sample:android`
- `:sample:ios`
- `:sample:desktop`

Phase 0 should start with the minimum necessary modules. Avoid over-splitting before code exists.

Acceptance criteria:

- Gradle sync works.
- Android target compiles.
- JVM/Desktop target compiles.
- iOS target compiles where available.
- Existing sample apps still run or are intentionally adjusted.

### 0.3 Testing Infrastructure

Goal:

Set up a unit-test-first workflow.

Deliverables:

- Common tests.
- JVM tests.
- Android tests where useful.
- iOS/native test awareness.
- Fixture folder structure.
- Rules for external test vectors.

Acceptance criteria:

- Tests can be run locally.
- Test naming is consistent.
- Fixtures are not invented to match implementation bugs.

### 0.4 Core Primitives

Goal:

Introduce safe value types for basic Cardano concepts.

Candidate primitives:

- `Network`
- `Lovelace`
- `TxHash`
- `PolicyId`
- `AssetName`
- `Address`
- `UtxoRef`

Acceptance criteria:

- Length and range checks exist.
- Invalid values are rejected.
- Public APIs have KDoc.
- Unit tests cover valid, invalid and edge cases.
- ByteArray wrappers use defensive copies and content equality.

### 0.5 Encoding Utilities

Goal:

Implement or integrate safe encoding utilities needed by later phases.

Candidate areas:

- Hex.
- Base encodings if required.
- Bech32 after explicit decision.

Acceptance criteria:

- Valid vectors pass.
- Invalid checksums fail.
- Malformed input is rejected.
- No lenient parser behavior is introduced to make tests pass.

### 0.6 CBOR Decision And Minimal Support

Goal:

Decide how Kardano SDK will handle CBOR safely.

Options to evaluate:

- Vetted KMP library.
- Small constrained internal subset.
- Platform-specific or wrapper approach.

Acceptance criteria:

- Decision is documented in an ADR.
- Parser limits are named.
- No allocation from untrusted declared length.
- Non-canonical, trailing or unsupported encodings are rejected unless explicitly documented.
- Integer range policy is defined.

### 0.7 Address Validation

Goal:

Support structural Cardano address parsing and validation.

Acceptance criteria:

- Network id is preserved and checked.
- Mainnet/testnet/preprod/preview distinctions are not ignored.
- KDoc states validation is structural only.
- Tests include valid addresses, malformed addresses, wrong checksums and network mismatches.

### 0.8 Crypto Strategy

Goal:

Document future crypto approach before implementing anything.

Acceptance criteria:

- No handwritten cryptography.
- Candidate libraries or bindings are evaluated.
- Mnemonic, derivation and signing remain out of Phase 0 implementation.
- Future implementation requires external vectors and review.

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

