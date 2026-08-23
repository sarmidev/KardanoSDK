# ADR-0019: TransactionDraft Network and Phase 1 Scope Binding

| Field   | Value                                                                 |
|---------|------------------------------------------------------------------------|
| Status  | **Accepted** — implements ADR-0018 Option 3.                           |
| Scope   | Bind `TransactionDraft` to the network and Phase 1 draft kind that produced it; validate that binding at `:wallet` signing time; recognize the Phase 1 fixture by a cited public identity rather than by storing its mnemonic. |
| Phase   | Pre-release hardening (post-Phase 1, pre-first-public-release)         |
| Updated | 2026-08-23                                                            |

---

## Context

ADR-0018 recorded that `ReadOnlyWallet.signTestnetFixtureTransaction` could sign a
mainnet-built draft whenever the caller also passed `Network.TESTNET`, because
`TransactionDraft` carried no network (or scope) of its own and the `network` argument was
unread (`@Suppress("UNUSED_PARAMETER")`). ADR-0018 adopted a Kotlin `@RequiresOptIn`
intent signal and a scope-explicit rename as immediate API honesty, and scheduled Option 3
— bind network and supported scope onto the draft itself — as a separately designed ADR.
That is this document.

The gap is not theoretical. `TransactionBuilder.build` and `TransactionBodySerializer.serialize`
already accept `Network.MAINNET` as a self-consistent build target (address parsing and
`:core` vector tests require that). A compiled `:wallet` artifact therefore let a caller
construct a mainnet body and sign it under a declared-testnet argument that the signer never
compared to anything on the draft.

ADR-0015 §2a originally made fixture-only / testnet-only signing a **call-site discipline**,
because `:wallet` cannot depend on `:shared` and therefore cannot import
`TestWalletFixture`. That dependency direction stands. What this ADR changes is the
enforcement *mechanism*: the draft now carries the network and Phase 1 scope it was built
under, and the signer reads those fields. Fixture recognition uses a cited **public**
derived identity (a payment-credential fingerprint), not a `:wallet → :shared` edge and not
a copy of the mnemonic phrase in production code.

---

## Decision

### 1. `TransactionDraft` carries `network` and `scope`

`TransactionDraft` gains two immutable, constructor-stamped properties:

- `network: Network` — the network every encoded output address was validated against
  (`TransactionBodyRequest.network` / `TransactionBuildRequest.network`).
- `scope: TransactionDraftScope` — a sealed marker naming the construction path that
  produced the draft.

```kotlin
public sealed interface TransactionDraftScope {
    public data object Phase1AdaOnlySinglePayment : TransactionDraftScope
}
```

`Phase1AdaOnlySinglePayment` is the only scope this SDK currently produces: an ADA-only
unsigned body with one payment output and an optional change output, from
`TransactionBodySerializer` / `TransactionBuilder`. Future draft kinds (native assets,
scripts, metadata) require a new sealed variant and their own ADR; they must not reuse this
marker.

Both values are stamped **only** inside `:tx`'s `internal` constructor:

- `TransactionBodySerializer.serialize` sets `network = request.network` and
  `scope = TransactionDraftScope.Phase1AdaOnlySinglePayment`.
- `TransactionBuilder.build` inherits the same stamp because it delegates encoding to the
  serializer. It does not re-stamp.

`network` and `scope` participate in `equals`, `hashCode`, `toString`, and public KDoc.
Callers cannot construct a `TransactionDraft` from outside `:tx`.

**Mainnet draft construction remains available.** `Network.MAINNET` stays an ordinary,
unguarded enum constant. Address parsing, provider configuration, and `TransactionBuilder`
self-consistency checks continue to accept it. Signing, not building, is what rejects a
mainnet draft.

### 2. Signing validates the bound draft before any key material is touched

`ReadOnlyWallet.signTestnetFixtureTransaction(words, network, draft)` keeps its name and
its `@ExperimentalKardanoSigningScope` opt-in (ADR-0018). The `network` parameter is no
longer decorative: it is a **cross-check** against `draft.network`.

Validation order, **before** `Mnemonic.parse`, derivation, or `Signing.sign`:

1. `draft.scope` is `TransactionDraftScope.Phase1AdaOnlySinglePayment`.
2. `draft.network == Network.TESTNET`.
3. The declared `network` argument equals `draft.network`.
4. Draft shape is compatible with the Phase 1 ADA-only single-payment flow
   (`selectedInputs` non-empty, `outputs.size` in `1..2`).

Failures return a wallet-owned `WalletError.SigningScopeViolation` whose sealed
`SigningScopeViolationReason` names the exact check that failed. This is orchestration
policy, not a `TxBuildError`: `:tx` stays crypto-free and does not know about signing.

### 3. Fixture identity is a cited public credential, not a stored mnemonic

After the §2 checks pass, signing restores/derives through the existing `:crypto` /
`:core` APIs and compares the derived payment-credential fingerprint (Blake2b-224 of the
account-0 external public key at `m/1852'/1815'/0'/0/0`) to the cited IntersectMBO
`cardano-addresses` / CIP-19 golden
`9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e`.

- The mnemonic phrase itself is **not** stored in `commonMain` production code.
- `:wallet` still does not depend on `:shared`.
- Exact fixture words pass; a different structurally valid BIP-39 mnemonic fails with
  `SigningScopeViolationReason.UnrecognizedFixtureIdentity` **before** `Signing.sign`.
- The fingerprint is a public credential hash, not a secret. It is test-only because it
  identifies the published Shelley golden, not a funded wallet.

This amends ADR-0015 §2a's "call-site only" fixture narrative without reversing the
`:wallet ↛ :shared` rule.

### 4. `:crypto` `Signing` stays a byte signer and is marked as such

`Signing.sign` signs a 32-byte body hash with an `ExtendedPrivateKey`. It cannot, and does
not, authorize transaction scope, network, or fixture identity — those checks live in
`:wallet`. To keep that layer from reading as ordinary integration API, `:crypto` applies
its own `@RequiresOptIn` annotation to the public `Signing` surface. No new module
dependency is added (`:wallet` already depends on `:crypto`; `:crypto` does not depend on
`:wallet` or `:tx`).

### 5. What this does not do

- It does not implement any cryptographic algorithm in this repository.
- It does not restrict `Network.MAINNET` or `BlockfrostNetwork.MAINNET` globally.
- It does not remove general address/network parsing.
- It does not add a `:wallet → :shared` dependency.
- It does not claim that a consumer who builds from a patched copy of the source cannot
  delete these checks. The goal is an honest, hard-to-miss signal and a working runtime
  rejection for a good-faith integrator of the compiled artifact, not a claim about
  unmodified-source impossibility.

---

## Swift / Kotlin distinction

Kotlin's `@RequiresOptIn` (`ExperimentalKardanoSigningScope` on the wallet entry point, and
the `:crypto` raw-signing annotation) is a **Kotlin-compiler-only** mechanism. When
`:wallet` / `:crypto` are consumed through the compiled `:shared` framework from Swift, a
Swift caller sees ordinary functions with no enforced opt-in.

The **runtime** checks in §2 and §3 **do** cross that boundary: they execute in shared
Kotlin code, so a Swift caller that passes a mainnet draft, a mismatched declared network,
an unsupported scope, or a non-fixture mnemonic receives a typed
`WalletError.SigningScopeViolation` the same way a Kotlin caller does.

Effective iOS signals are therefore: the scope-explicit function name, its KDoc, the
exported `TransactionDraft.network` / `TransactionDraft.scope` properties, and the runtime
`SigningScopeViolation` errors — not a Swift compile-time opt-in gate.

---

## Consequences

- A compiled `:wallet` artifact no longer signs a mainnet-built draft under a declared
  `TESTNET` argument, or a testnet draft under a declared `MAINNET` argument.
- A compiled `:wallet` artifact no longer signs with an arbitrary valid BIP-39 mnemonic.
- `TransactionDraft.equals` / `hashCode` change (pre-alpha; no compatibility alias).
- ADR-0018 Option 3 is implemented. The ADR-0018 opt-in signal is retained, not replaced.
- ADR-0015 §2a is amended: fixture-only scope is now a `:wallet` runtime check against a
  cited public identity, still without a `:wallet → :shared` edge.

## Rejected alternatives

- **Reject `network != TESTNET` only, leaving the draft unbound.** Rejected in ADR-0018
  §Context: it does not close the mainnet-draft + declared-TESTNET path.
- **Have `:wallet` depend on `:shared` to import `TestWalletFixture`.** Rejected: that
  inverts ADR-0011 §3.
- **Store the fixture mnemonic in `:wallet` production code.** Rejected: the phrase is a
  secret-shaped value even when it is a published test vector; a public credential
  fingerprint is enough to recognize it.
- **Hide or restrict `Network.MAINNET`.** Rejected: address parsing and provider
  configuration must keep representing mainnet structurally.
- **Put signing-scope policy inside `:tx` or `:crypto`.** Rejected: `:tx` is crypto-free;
  `:crypto` `Signing` is a byte signer and must not grow a transaction-scope contract.

## Follow-up work

- A later ADR that introduces a new draft kind must add a new `TransactionDraftScope`
  variant and an explicit signing-policy decision for it.
- General-purpose / mainnet wallet signing remains out of scope until its own ADR.

## Relation to prior ADRs

- Implements ADR-0018 Option 3.
- Amends ADR-0015 §2a enforcement (call-site discipline → runtime check against a bound
  draft and a cited public identity) without reversing `:wallet ↛ :shared`.
- Does not supersede ADR-0014 (unsigned body), ADR-0013 (`:wallet` boundary), or
  ADR-0009/0010/0016 (crypto backends).
