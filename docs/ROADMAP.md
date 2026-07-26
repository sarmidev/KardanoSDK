# Kardano SDK — Roadmap

Kardano SDK is open-source Kotlin Multiplatform infrastructure for native Cardano mobile apps.
This document answers what is delivered, what the project is focusing on now, and which direction
is planned next. For completed implementation detail, use the
[delivery record](DELIVERY_RECORD.md).

## At a Glance

### Delivered — Phase 0: core foundation

The project has a UI-free Kotlin Multiplatform foundation: bounded core primitives, encoding,
structural address handling, documented parser policy, and the architecture decisions needed for
the scoped transaction flow.

### Delivered — Phase 1: bounded preprod demonstration

An Android-primary Playground can restore the cited public fixture, query mock or Blockfrost
preprod UTxOs, build an ADA-only draft, sign it through the fixture-scoped flow, and submit it to
preprod.

The implementation is delivered. Phase 1 closure continues as documentation, release-readiness,
and target-limit reconciliation work; it does not add a new protocol capability.

### Current — make the evidence useful

The current focus is to:

1. Keep the Playground, Quickstart, public materials, and known limits clear for developers.
2. Complete Phase 1 closure and release-readiness records from delivered evidence.
3. Talk with potential loyalty/ticketing integrators and validate whether the Phase 2 problem is
   worth solving.

### Planned direction — Phase 2 native-asset pilot

Phase 2 is a conditional loyalty/ticketing direction, not a delivery schedule or public API
contract. It begins with external problem validation, a provider decision, and a documented
multi-asset model before any native-asset transaction vertical.

### Future — Phase 3 ecosystem adoption

Public integration evidence, maintainership, and later capabilities should follow only where
Phase 2 delivery and external use justify them.

## What Developers Can Do Now

- Run the [Playground in Mock mode](QUICKSTART.md) without a network key.
- Inspect the [delivery record](DELIVERY_RECORD.md), [decision records](DECISIONS/), and
  [testing guide](TESTING.md).
- Report a concrete integration concern or product need through the repository’s GitHub issues.
- If your team has a loyalty/ticketing mobile use case, use the
  [funding and pilot playbook](FUNDING_AND_PILOT_PLAYBOOK.md) contact path to share feedback.

The public landing page is a short entry point; this repository remains the technical source of
truth. See [`site/`](../site/).

## Current Scope and Limits

The Phase 1 transaction flow is experimental, test-only, testnet/preprod-focused, ADA-only, and
bound to the cited public fixture.

It does not implement:

- Mainnet operation.
- Arbitrary wallet import or user-supplied mnemonic/key flows.
- General-purpose signing.
- Native-asset transaction construction.
- Scripts, staking, metadata, multisig, or hardware-wallet support.

Android is the Phase 1 runtime-validation target. iOS and JVM/Desktop share Kotlin targets, but
they do not have equivalent Phase 1 runtime-validation claims. See the
[security policy](SECURITY.md) and [testing guide](TESTING.md) for the full boundary and target
matrix.

## Phase 2 — Native-Asset Pilot and Provider Expansion

**Status: planned direction.** The proposed first vertical is a loyalty or ticketing app using
existing Cardano native assets. Progress is gated; no Phase 2 delivery date is implied.

The intended sequence is:

1. Validate one external pilot scenario and document the architecture/provider decision.
2. Demonstrate the existing shared flow on Android and iOS with appropriate runtime evidence.
3. Represent multi-asset values without losing policy identifiers, asset names, or quantities.
4. Build one preprod native-asset transfer that preserves selected input value through outputs and
   change.
5. Validate the complete path with the selected provider and an external integrator.
6. Consider a script interaction only if a pilot requires it and a separate decision approves it.

The full [Phase 2 plan](PHASE_2_PLAN.md) defines deliverables, exit criteria, and non-goals.

## Phase 3 — Ecosystem Adoption

**Status: future direction.** If Phase 2 produces useful public evidence, the project can focus on
integration material, versioned documentation, maintainer process, public pilot outcomes, and
funding work grounded in delivered milestones.

This is evidence-led future work, not a commitment to a feature set or timeline.

## Funding and Pilot Discovery

The implementation baseline is complete. Owner-led work now includes public release preparation,
pilot discovery, and funding outreach. The detailed process, including feedback questions and
proposal discipline, is in the [funding and pilot playbook](FUNDING_AND_PILOT_PLAYBOOK.md).

## Detailed Records

- [Delivery record](DELIVERY_RECORD.md) — completed Phase 0/1 outcomes and technical evidence.
- [Phase 1 plan](PHASE_1_PLAN.md) — scoped implementation record and remaining Phase 1 closure.
- [Decision records](DECISIONS/) — architecture and dependency decisions.
- [Testing guide](TESTING.md) — commands, target matrix, fixture policy, and environment limits.
- [Release process](RELEASING.md) — release prerequisites and verification.
- [Security policy](SECURITY.md) — reporting path and current boundaries.

## Operating Principle

Each phase should deliver something real, tested, and documented. The project does not widen
scope by hiding risks in vague future work.
