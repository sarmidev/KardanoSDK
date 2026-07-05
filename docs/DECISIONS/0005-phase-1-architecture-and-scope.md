# ADR-0005: Phase 1 Architecture And Scope

| Field   | Value                               |
|---------|-------------------------------------|
| Status  | **Accepted**                        |
| Scope   | Phase 1 MVP scope and architecture strategy |
| Phase   | Phase 1 (Block 1.1)                 |
| Updated | 2026-07-05                          |

---

## Context

Phase 0 closed with a UI-free `:core` module containing primitives, Hex/Bech32/CardanoBech32
encoding, a bounded CBOR subset, and structural CIP-19 Shelley address parsing (decode-only).
ADR-0004 documented the future cryptography strategy without selecting any concrete library
or binding. `docs/ROADMAP.md` and `docs/PHASE_1_PLAN.md` already sketch a Phase 1 block
sequence (1.1 through 1.12) aimed at an end-to-end preprod transaction flow verified through
an Android app.

Block 1.1 is a planning/documentation block. It must resolve or explicitly defer the open
questions in that sequence before any wallet, crypto, provider, transaction-builder, signing,
or Android UI code is written. This ADR follows the same pre-implementation pattern as
ADR-0001 (CBOR/Bech32 policy) and ADR-0004 (crypto strategy): record the decision before the
implementation block that depends on it.

---

## Decision

### 1. MVP transaction-flow scope

The first end-to-end Phase 1 flow, verified on preprod, is:

1. Create or restore a test wallet.
2. Derive one address.
3. Query UTxOs for that address.
4. Build a minimal ADA-only transaction (one or more inputs, one payment output, one change
   output, a computed fee, a validity interval only if required).
5. Sign the transaction locally.
6. Submit it to preprod.
7. Show the result in the Android app.

Native assets are **out of the first MVP**. Only ADA (payment and change) is supported
initially; native-asset support is reconsidered after Phase 1 closure or in Phase 2.

Android is the **primary** validation target for Phase 1. iOS and JVM/Desktop remain
**compile-only** during Phase 1 unless a future block explicitly revisits this; their
functional checkpoints are deferred to Phase 1 closure (Block 1.12) or Phase 2. This is a
deliberate scope reduction against the current `docs/ROADMAP.md` Phase 1 acceptance criteria
(which lists iOS and JVM/Desktop demos); `docs/ROADMAP.md` is updated alongside this ADR.

### 2. Android validation strategy

Android checkpoints are mandatory per block, not a closing-day activity (see
`docs/PHASE_1_PLAN.md`, "Checkpoints Android obligatorios"). Block 1.2 (Android SDK
Playground) is the first functional checkpoint; it is a diagnostic/testing surface inside the
sample app, not new product UI. Sample-app UI is acceptable as long as `:core` stays UI-free
and business logic does not migrate into the sample app.

The Block 1.1 Android baseline checkpoint is a **build verification**, not a launch
verification: `./gradlew :androidApp:assembleDebug :core:jvmTest` confirms the existing
sample Android app and `:core` still build with no code changes. It does not confirm the app
opens or runs; a manual launch/open check is optional and, if performed, is recorded
separately by the project owner.

### 3. Module architecture

No Gradle module is created in Block 1.1. Instead, this ADR records **decision criteria** for
when and how future modules are introduced, consistent with ADR-0002 ("extract modules only
when justified") and ADR-0003 (package seams inside `:core` ease future extraction):

- Packages first, where the work is dependency-free and ownership boundaries are still
  exploratory.
- Any implementation that introduces crypto, provider, or network dependencies is a likely
  trigger for creating a real Gradle module (candidate names `:crypto`, `:wallet`, `:tx`,
  `:provider`, `:provider-blockfrost`; none of these names are final).
- `:core` remains dependency-free and structural. Crypto, wallet, transaction-building, and
  provider logic do not land inside `:core`.
- `:shared` remains the sample/UI host (and the iOS `Shared` framework producer) and is not
  the long-term home for SDK crypto/wallet/tx/provider logic.
- Actual module creation is deferred to the first implementation block that needs
  dependency/ownership separation — most likely Block 1.3 (provider, which needs an HTTP
  client dependency) or Block 1.4/1.5 (crypto, which needs a crypto library/binding).
- This ADR does not assert that crypto or provider packages will live in `:core` or
  `:shared`; their eventual home is decided by the block that triggers the split.

### 4. Crypto decision path

No crypto algorithm, library, or binding is selected in this block. ADR-0004's candidate
matrix remains `Needs investigation` for every candidate. The crypto evaluation stays
sequenced as Block 1.4 (evaluation and module decision) and Block 1.5 (primitives needed for
wallet), per `docs/PHASE_1_PLAN.md`. Algorithms to resolve first, in priority order for the
Phase 1 MVP: Ed25519-BIP32, BIP-32/CIP-1852 derivation, BIP-39/CIP-3, PBKDF2-HMAC-SHA-512,
HMAC-SHA-512, and Blake2b-224/256.

Read-only blocks (1.2 Android Playground, 1.3 Provider Read-Only Boundary) do not depend on
crypto and may proceed in parallel with the crypto evaluation. ADR-0004 is updated by Block
1.4/1.5 when a candidate evaluation records a verified `Accepted`/`Rejected` decision — not
by this ADR.

### 5. Provider strategy

The first provider implementation is a **mock/stub**, defined alongside a minimal read-only
provider interface in Block 1.3, so wallet and transaction-builder work can proceed without a
live network dependency. **Blockfrost** is the first real preprod provider target, wired in
after the mock exists. Koios, Maestro, Ogmios, and Kupo are deferred to Phase 2.

Minimum data the MVP provider interface must support: UTxOs for an address, protocol
parameters needed for fee/build logic, and a submit endpoint. Transaction history, metadata
queries, and anything beyond this are deferred. The public provider API is kept intentionally
minimal in Block 1.3 to avoid locking its shape around Blockfrost's specific response format
before a second provider is evaluated. A concrete provider-selection ADR (candidate ADR-0006)
is expected when Block 1.3 records its evaluation — not created here.

> **Refinement (ADR-0006, Block 1.3a):** ADR-0006 refines this section by splitting the
> read-only query boundary (`ChainQueryProvider`: UTxOs, protocol parameters, optional chain
> tip) from transaction submission. Submit is not part of the read-only interface; it moves to
> a separate `TxSubmitProvider` in Block 1.11, once local signing exists and a submit-result
> model is meaningful. The MVP still needs submit; it is only resequenced, not removed. See
> `docs/DECISIONS/0006-provider-boundary-and-strategy.md`.

### 6. Transaction strategy

"Minimal ADA transaction" means: one or more inputs selected from the wallet's UTxOs, one
payment output to a destination `addr_test`, one change output, a computed fee, and a
validity interval only if required by the chosen provider/network. No native assets, no
metadata, no certificates, no scripts.

Two serialization prerequisites must be resolved in their own blocks before the transaction
builder can produce final transaction bytes — they are not resolved here:

- **CBOR map ordering for transaction serialization**: Phase 0 (ADR-0001) uses the RFC 8949
  §4.2.1 bytewise deterministic rule for the general-purpose CBOR subset. Whether Cardano
  transaction serialization instead requires RFC 7049 length-first map ordering must be
  decided before Block 1.9 (Transaction Builder Minimal) produces transaction CBOR.
- **Address encoding/round-trip policy**: `Address.parse` is decode-only (Phase 0). Address
  *generation* in Block 1.7 needs an encoding path (for example `toBech32`), which requires
  its own address encoding/round-trip ADR, resolved before or at Block 1.7.

Fee and change scope for the MVP: a direct fee calculation from protocol parameters and a
simple change strategy (Block 1.9). Advanced coin selection is out of scope for Phase 1.

### 7. Scope / risk boundaries

- No mainnet.
- No real private keys, mnemonics, or funds anywhere in Phase 1 work.
- No handwritten cryptographic algorithms (restates ADR-0004 / the project hard rule).
- No transaction signing before the crypto, provider, and transaction-builder scope in this
  ADR is implemented and reviewed at each respective block.
- No validator weakening to make tests pass.
- No new dependencies in Block 1.1; dependencies are introduced only in the implementation
  block that documents why they are needed (for example, an HTTP client in Block 1.3, a
  crypto library in Block 1.4/1.5).
- `:core` stays UI-free and dependency-free; `:shared` stays the sample/UI host and is not
  the long-term home for SDK crypto/wallet/tx/provider logic.

---

## Consequences

- `docs/PHASE_1_PLAN.md` gained a "Decisiones del Bloque 1.1" section recording this ADR's
  decisions in the plan's working language; the existing 1.1-1.12 block list is unchanged.
- `docs/ROADMAP.md` marks Block 1.1 complete and reconciles the Phase 1 acceptance criteria
  to Android-primary, with iOS/Desktop functional demos deferred.
- Block 1.2 (Android SDK Playground) is the next block and is the first Phase 1
  implementation block; no implementation work is authorized by this ADR itself.
- Module extraction, crypto library selection, provider selection, and the two serialization
  prerequisites (CBOR map ordering, address encoding/round-trip) remain open and are each
  resolved in their own future block, as listed above.

---

## Non-goals

- No wallet, crypto, provider, transaction-builder, signing, or Android UI implementation.
- No Gradle module created or renamed.
- No dependency added.
- No crypto library or binding selected (ADR-0004 unchanged by this ADR).
- No concrete provider selected beyond naming Blockfrost as the first real-preprod target;
  no provider code written.
- No claim of readiness, external review, or audit status.

---

## Follow-up work

- Block 1.2: Android SDK Playground (first implementation block; address/Hex/Bech32/CBOR
  diagnostics only, no wallet/crypto/provider/tx).
- Block 1.3: Provider Read-Only Boundary — defines the provider interface, a mock
  implementation, and the first real Blockfrost preprod wiring; likely trigger for a real
  Gradle module and for a short provider-selection ADR (candidate ADR-0006).
- Block 1.4/1.5: Crypto Evaluation And Module Decision, then Crypto Primitives Needed For
  Wallet — updates ADR-0004's candidate matrix with verified facts; likely trigger for a real
  Gradle module.
- Block 1.7: Address Generation — requires an address encoding/round-trip ADR before or at
  this block.
- Block 1.9: Transaction Builder Minimal — requires the CBOR map-ordering decision for
  Cardano transaction serialization before this block.
- ADR-0002 (`docs/DECISIONS/0002-module-structure.md`), ADR-0003
  (`docs/DECISIONS/0003-core-package-structure.md`), and ADR-0004
  (`docs/DECISIONS/0004-crypto-strategy.md`) remain the governing decisions this ADR aligns
  with; this ADR does not supersede them.
