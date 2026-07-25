# Phase 2 Plan — Native-Asset Pilot And Provider Expansion

## Purpose

Phase 2 turns the Phase 1 ADA-only, test-only preprod demonstration into a pilot-ready
Kotlin Multiplatform integration path for a loyalty or ticketing app that uses existing Cardano
native assets.

This is a direction and work plan, not a delivery promise or public API contract. Each block needs
an approved scope, tests, documentation, and a reviewable implementation before the next begins.

## Product thesis

Kardano SDK gives Android and iOS teams a shared Kotlin layer for Cardano wallet and transaction
flows without requiring a WebView or duplicated platform business logic.

The first Phase 2 vertical is loyalty/ticketing because it has an understandable mobile use case:
an app reads a user's balance, identifies an existing ticket or loyalty asset, and transfers it
without losing other assets in the selected UTxOs.

## Phase 2 outcomes

- A functional Android and iOS integration demonstration, not only compilation.
- A provider capability decision based on pilot requirements.
- Multi-asset values represented without dropping policy ids, asset names, or quantities.
- Native-asset input selection and change preservation.
- One documented loyalty/ticketing transfer flow on preprod.
- At least one external integration experiment, letter of interest, or pilot agreement.

## Explicit non-goals

- Mainnet as a prerequisite for Phase 2.
- Arbitrary wallet import or a general-purpose signing API before a dedicated decision.
- A full Plutus framework.
- Minting, marketplace logic, or defining how a ticket/loyalty asset is issued.
- Staking, governance, metadata, multisig, or hardware-wallet support unless a later approved
  block requires one.

## Sequence

### 2.0 Pilot And Architecture Gate

Objective: validate the loyalty/ticketing problem before expanding protocol scope.

Deliverables:

- 10–15 structured conversations with potential integrators.
- A one-page pilot scenario: actor, asset, transaction, success condition, and failure cases.
- An ADR defining the multi-asset model, ownership boundaries, supported transaction subset, and
  provider selection criteria.
- A written decision on the next provider after evaluating Blockfrost, Koios, Ogmios/Kupo, and
  Maestro against the pilot.

Exit criteria:

- One primary scenario is selected.
- The scenario has an external interested party or a documented substitute test scenario.
- The SDK scope does not silently widen into a wallet app or full Plutus implementation.

### 2.1 Cross-Platform Integration Proof

Objective: demonstrate the existing shared flow on Android and iOS.

Deliverables:

- Reproducible Android and iOS sample run instructions.
- Runtime verification appropriate to the available iOS environment.
- A small integration-oriented API example that uses public SDK APIs rather than Playground-only
  classes.
- Updated target matrix that distinguishes executed runtime checks from compile/link checks.

Exit criteria:

- A developer can follow a documented path to run each host sample.
- Existing Phase 1 behavior and scope limits stay intact.

### 2.2 Multi-Asset Value Foundation

Objective: represent and query native assets without loss.

Deliverables:

- Provider-neutral multi-asset `Value` design with policy id, asset name, and quantity.
- Blockfrost mapping that preserves all asset components.
- Typed errors and bounded input handling for asset data.
- External vectors or provider fixtures cited in tests.
- Migration path from Phase 1's `hasNativeAssets` flag.

Exit criteria:

- A queried UTxO can be represented without silently dropping native assets.
- Existing ADA-only callers either retain behavior through an explicit API or receive a typed,
  documented migration path.

### 2.3 Native-Asset Transaction Vertical

Objective: build a minimal preprod transaction that transfers an existing native asset and
preserves all selected input assets through outputs and change.

Deliverables:

- Multi-asset input selection.
- Fee and minimum-ADA calculation reviewed against the target Cardano era.
- Token-preserving change.
- Valid, invalid, and edge tests using cited fixtures.
- Playground or sample demonstration of the loyalty/ticketing flow.

Exit criteria:

- A preprod test transaction transfers an existing asset and preserves selected input value.
- The implementation never turns an unsupported value into an ADA-only transaction.

### 2.4 Provider And Pilot Validation

Objective: add the provider selected by 2.0 and validate the complete vertical with an external
integrator.

Deliverables:

- Provider implementation and capability matrix.
- Pilot runbook, feedback record, and integration issue list.
- Public sample and documented limits.

Exit criteria:

- At least one external party has attempted the integration or provided a written commitment to
  attempt it against the delivered scope.

### 2.5 Conditional Script Interaction

Objective: consider one script interaction only if the Phase 2 pilot requires it.

Potential subset:

- Script hash.
- Datum and redeemer representation.
- Inline datum.
- Reference input.
- One preprod script interaction.

This block requires a separate ADR and test-vector/source policy before implementation. It is not
approved merely because Phase 2 exists.

## Evidence and funding cadence

Each completed block must create evidence useful outside the repository:

| Block | Evidence |
|---|---|
| 2.0 | Pilot scenario, ADR, partner feedback summary |
| 2.1 | Android/iOS demo recording and quickstart |
| 2.2 | Public API reference, fixtures, migration note |
| 2.3 | Preprod transaction demonstration and integration sample |
| 2.4 | Pilot outcome and provider capability matrix |
| 2.5 | Only if explicitly justified by the pilot |

The funding strategy, external tasks, and proposal material live in
[FUNDING_AND_PILOT_PLAYBOOK.md](FUNDING_AND_PILOT_PLAYBOOK.md).
