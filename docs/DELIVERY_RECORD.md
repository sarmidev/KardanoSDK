# Kardano SDK — Delivery Record

## Purpose

This is the technical history for work that has already been delivered. It complements the
[roadmap](ROADMAP.md), which describes the current focus and planned direction without repeating
every implementation decision.

Use this document when you need to know what landed, why a boundary exists, or where to find the
supporting evidence. The most detailed sources remain the linked decision records, tests, and
Phase 1 plan.

## Reading Guide

- [Roadmap](ROADMAP.md) — delivered scope, current focus, planned direction, and limits.
- [Phase 1 plan](PHASE_1_PLAN.md) — the scoped implementation plan and remaining Phase 1 closure
  work.
- [Decision records](DECISIONS/) — architecture, dependency, serialization, provider, and signing
  decisions.
- [Testing guide](TESTING.md) — current verification commands, target matrix, fixture policy, and
  environment limits.
- [Handoff](HANDOFF.md) — detailed session context for maintainers and future work sessions.

## Phase 0 — Core Foundation

**Status: delivered.** Phase 0 established the UI-free Kotlin Multiplatform foundation before
wallet, transaction, provider, or signing behavior was added.

### 0.1 Governance and project record

Delivered:

- The AI working agreement, security policy, project brief, roadmap, handoff record, and decision
  record structure.
- Explicit boundaries: no handwritten cryptography, no real mnemonic or private-key material, no
  real funds, and no readiness claims beyond available evidence.

Primary references:

- [AI working agreement](AI_WORKING_AGREEMENT.md)
- [Security policy](SECURITY.md)
- [Project brief](PROJECT_BRIEF.md)

### 0.2 Module structure and testing foundation

Delivered:

- A dependency-free, UI-free `:core` module and an initially separate `:shared` sample/UI host.
- A target strategy covering Android, iOS, and JVM/Desktop.
- Common/JVM/Android-host test organization, fixture conventions, and external-vector policy.

Later delivery added focused modules where dependency and ownership boundaries required them:
`:provider`, `:provider-blockfrost`, `:crypto`, `:wallet`, `:tx`, and
`:crypto-signing-backend`.

Primary references:

- [Module-structure decision](DECISIONS/0002-module-structure.md)
- [Testing guide](TESTING.md)

### 0.3 Core primitives and bounded parsing

Delivered:

- Typed core primitives for network, lovelace, transaction hashes, policy identifiers, asset
  names, and UTxO references.
- Bounded hex and Bech32/Bech32m codecs, including the Cardano HRP allowlist.
- A documented definite-length CBOR subset with explicit input, nesting, and collection limits.
- Structural CIP-19 Shelley address parsing for base, pointer, enterprise, and reward addresses.

The parsing policy rejects malformed, unsupported, trailing, and non-canonical input rather than
normalizing it. Address parsing is structural only: it does not establish ownership, on-chain
existence, spendability, or balance.

Primary references:

- [CBOR and parser policy](DECISIONS/0001-cbor-and-parser-policy.md)
- [Core package structure](DECISIONS/0003-core-package-structure.md)
- [Address encoding and round-trip](DECISIONS/0012-address-encoding-and-roundtrip.md)

### 0.4 Crypto strategy and Phase 0 closure

Delivered:

- A documented backend-delegation strategy before cryptographic behavior was implemented.
- A Phase 0 closure review covering target compilation, typed errors, defensive byte handling,
  parser limits, and cited-vector policy.

Primary reference:

- [Crypto strategy](DECISIONS/0004-crypto-strategy.md)

## Phase 1 — Bounded Preprod Demonstration

**Implementation status: delivered.** The remaining `1.12` work is closure and release-readiness
documentation, not a new protocol capability. The demonstration is Android-primary,
fixture-scoped, ADA-only, and testnet/preprod-focused. It is experimental and not for mainnet
funds or user-supplied keys.

### 1.1 Scope and Android Playground

Delivered:

- A documented MVP boundary: restore a test fixture, derive an address, query UTxOs, build an
  ADA-only draft, sign it locally through the scoped flow, and submit it to preprod.
- The Android-primary Playground and shared Android/iOS/JVM/Desktop UI code.
- A recurring Android checkpoint model rather than a final-only sample validation step.

Primary references:

- [Phase 1 architecture and scope](DECISIONS/0005-phase-1-architecture-and-scope.md)
- [Phase 1 plan](PHASE_1_PLAN.md)

### 1.2 Provider boundary and preprod access

Delivered:

- Provider-neutral query, protocol-parameter, and transaction-submission boundaries.
- An in-memory mock provider with deterministic test-only sample data.
- A Blockfrost preprod provider and an opt-in Playground mode using an operator-supplied project
  id held in non-persistent UI state.
- ADA-only UTxO handling that excludes UTxOs containing native assets from Phase 1 input
  selection.

Primary references:

- [Provider boundary and strategy](DECISIONS/0006-provider-boundary-and-strategy.md)
- [HTTP client and Blockfrost provider](DECISIONS/0007-http-client-and-blockfrost-provider.md)

### 1.3 Fixture restoration, derivation, and address generation

Delivered:

- Icarus/CIP-3 restoration for the cited public test fixture.
- CIP-1852 private derivation and public-key projection through delegated backends.
- Testnet Shelley address generation and structural round-trip parsing.
- A read-only wallet handle that retains only the derived public state needed by the demo flow.

Runtime evidence is Android-primary. iOS compilation/linking is covered where documented, but
Phase 1 does not claim iOS runtime parity.

Primary references:

- [Mnemonic, seed, and key derivation](DECISIONS/0009-mnemonic-seed-and-key-derivation.md)
- [Derivation backend and public-key projection](DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md)
- [Wallet boundary](DECISIONS/0013-wallet-boundary-and-read-only-state.md)

### 1.4 ADA-only transaction construction

Delivered:

- An ADA-only transaction-body builder with bounded coin selection, fee/change calculation,
  canonical serialization for its supported subset, and typed errors.
- Explicit handling for unsupported native-asset UTxOs: Phase 1 never selects them as inputs.
- A Playground checkpoint that displays an unsigned draft without representing it as a
  general-purpose transaction API.

Primary reference:

- [Minimal ADA transaction builder](DECISIONS/0014-minimal-ada-transaction-builder.md)

### 1.5 Scoped signing and preprod submission

Delivered:

- A backend-delegated extended Ed25519-BIP32 signing path behind a narrow API.
- Full transaction assembly from verification-key witnesses, without putting cryptography in the
  transaction module.
- Fixture-scoped testnet/preprod signing for ADA-only single-payment builder drafts.
- Blockfrost preprod submission with typed response/error handling.
- A manual Android re-validation of the mixed UTxO case: only ADA-only inputs were selected and
  the preprod result matched the locally signed transaction identifier.

This is not an arbitrary-wallet or general-purpose signing capability.

Primary references:

- [Transaction signing scope](DECISIONS/0015-transaction-signing.md)
- [Signing backend gate](DECISIONS/0016-transaction-signing-backend-gate.md)
- [Submission boundary](DECISIONS/0017-transaction-submission-boundary.md)

### 1.6 Playground architecture, mock flow, and brand

Delivered:

- A lightweight MVI split for the guided Playground flow.
- A deterministic Mock-mode path through Wallet → Funds → Build → Sign → Submit; mock submission
  reports that it does not contact a network.
- Overview, guided-flow, and roadmap views with scope labels and technical-detail disclosure.
- A first-party violet/blue/cyan brand mark and matching light/dark theme across the Playground
  and host-app icons.

Primary references:

- [Phase 1 plan](PHASE_1_PLAN.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

### 1.7 Remaining Phase 1 closure

Current closure work:

- Reconcile public documentation and release-readiness records with the delivered implementation.
- Keep target limitations explicit: Android is the runtime-validation target; iOS and JVM/Desktop
  are shared targets with the limits documented in the testing guide and README.
- Keep the Phase 2 handoff constrained to the documented pilot and architecture gates.

Primary references:

- [Phase 1 closure plan](PHASE_1_PLAN.md)
- [Release process](RELEASING.md)

## Historical Verification Summary

The project uses cited specifications and upstream sources for protocol-sensitive vectors. Detailed
commands and target expectations are in [TESTING.md](TESTING.md).

The delivered Phase 1 evidence includes:

- JVM tests for portable modules and the macOS signing path.
- Android host tests plus Android runtime checkpoints where native backends require them.
- iOS compilation/linking checks where the local macOS/Xcode environment supports them.
- Android manual checks for the bounded mock and preprod fixture flow.

The target matrix must distinguish executed runtime checks from compile/link checks. The README,
testing guide, and security policy remain authoritative for current limits.

## Current Limits Carried From Phase 1

- Mainnet, arbitrary wallet import, user-supplied mnemonic/key flows, and general-purpose signing
  are not implemented.
- Native-asset transaction construction, scripts, staking, metadata, multisig, and hardware-wallet
  support are not implemented.
- The demonstration is ADA-only, testnet/preprod-focused, and bound to the public test fixture.
- Android is the Phase 1 runtime-validation target. iOS and JVM/Desktop share targets but do not
  have equivalent Phase 1 runtime-validation claims.

## Related Future Direction

The [roadmap](ROADMAP.md) and [Phase 2 plan](PHASE_2_PLAN.md) define the next candidate direction:
a loyalty/ticketing native-asset pilot, gated by external problem validation, a provider decision,
and a documented multi-asset model. It is not a delivery schedule or public API contract.
