# ADR-0017: Transaction Submission Boundary

| Field   | Value                                                                |
|---------|------------------------------------------------------------------------|
| Status  | **Accepted** (Block 1.11a). Records only the `:provider` submission interface, error type, and in-memory double; no Blockfrost implementation and no `:shared` checkpoint yet (§7). |
| Scope   | Block 1.11a — provider-neutral transaction-submission boundary          |
| Phase   | Phase 1 (Block 1.11a)                                                   |
| Updated | 2026-07-13                                                              |

---

## Context

ADR-0006 (`0006-provider-boundary-and-strategy.md`) defined the read-only `ChainQueryProvider`
boundary and, in its §3, pre-committed to splitting transaction submission out into a distinct
`TxSubmitProvider`, sequenced after local signing exists and a submit-result model is
meaningful. ADR-0007 (`0007-http-client-and-blockfrost-provider.md`) then built the concrete
Blockfrost read provider and its secrets/error-mapping conventions, which the future Blockfrost
submit implementation should reuse rather than reinvent.

Local signing (Block 1.10, ADR-0015/ADR-0016) is now complete: `:wallet`'s
`ReadOnlyWallet.signTransaction` produces a `WalletSignedTransaction` whose
`signedTransaction.cbor()` is a full signed `transaction` CBOR byte array, ready to submit.
Block 1.11 is the first block that submits anything to Cardano preprod. This ADR records the
Block 1.11a decision: the `:provider` boundary itself (interface, error type, non-submitting
double). It does not implement Blockfrost submission or touch `:shared` — those are Block 1.11b
and 1.11c (§7).

---

## Decision

### 1. A new, separate interface: `TxSubmitProvider`

Submission is **not** an additional method on `ChainQueryProvider`. It is a new interface in
`:provider`:

```kotlin
public interface TxSubmitProvider {
    public val network: Network
    public suspend fun submit(transactionCbor: ByteArray): KardanoResult<TxHash, SubmitError>
}
```

Rationale for the split (elaborating ADR-0006 §3):

- **Different mutation semantics.** Every `ChainQueryProvider` method is a read with a stable
  answer; `submit` is a single mutating, non-idempotent action against the network. Resubmitting
  the same bytes may be rejected the second time even though the first call succeeded. Mixing
  that into a "query" interface would misrepresent it.
- **Different failure taxonomy.** Read failures (`ProviderError`) are about *fetching* a
  resource (not found, rate limited, transport, decode). Submission failures are about the
  network's *judgment on a transaction* (rejected as malformed/conflicting, in addition to the
  same transport/rate-limit/decode categories a read can hit). Forcing these into one sealed
  type would blur that distinction for every caller, including ones that only ever read.
- **Different implementation cost/readiness.** A read-only mock (`InMemoryChainQueryProvider`)
  can safely fabricate plausible data because reads are idempotent and low-stakes. A
  submit-capable mock cannot safely fabricate an "accepted" result without lying about having
  broadcast a transaction (§4). Keeping submission a separate, smaller interface makes that
  never-fake-success constraint easy to see and audit at the type level.
- **Independent evolution.** A consumer that only ever reads (for example a future
  balance-only integration) should not be forced to depend on, implement, or reason about
  submission at all.

`network` mirrors `ChainQueryProvider.network`: a submit provider is bound to one network at
construction. Unlike `getUtxos`, `submit` has no address to compare against, so this interface
does not itself require a per-call network check; a concrete implementation may add one.

### 2. Input: raw CBOR `ByteArray`, not a `:tx` type

`submit` takes `transactionCbor: ByteArray`, not `SignedTransaction` (from `:tx`) and not a
`WalletSignedTransaction` (from `:wallet`). This is a hard dependency-direction constraint, not
a style preference: `:tx` already depends on `:provider` for its read models (`Utxo`,
`ProtocolParameters`, in `TransactionBuildRequest`), so `:provider` accepting a `:tx` type would
create a module dependency cycle. `:provider` must stay the lower-level module.

Callers extract the bytes themselves — for example `walletSigned.signedTransaction.cbor()` —
and pass them to `submit`. This keeps `:provider` exactly as dependency-light as
`ChainQueryProvider` already is (per ADR-0006 §1, `commonMain` adds no third-party dependency in
this sub-block either).

### 3. Return: `TxHash`, not a new wrapper type

On success, `submit` returns the accepted transaction's `TxHash` (the existing `:core` 32-byte
hash container), not a Blockfrost-shaped response object or a new `SubmitResult` wrapper type.
`TxHash` is already the SDK's neutral representation of a transaction id (used by
`WalletSignedTransaction.transactionId`), so reusing it:

- avoids inventing a parallel "submission accepted" type that only differs from `TxHash` by
  name;
- lets a caller directly compare the accepted id against the locally-computed
  `walletSigned.transactionId` if it wants to detect a mismatch, without unwrapping anything;
- keeps the MVP surface minimal, consistent with ADR-0006's stated preference for a small,
  backend-neutral API.

A tx-id mismatch between the locally signed hash and a backend-reported id is not modeled as a
`SubmitError` variant: the provider only ever sees bytes in and a hash out, so comparing that
hash against a caller's expectation is the caller's concern (planned for the `:shared` Block
1.11c checkpoint), not the provider boundary's.

### 4. `SubmitError`: a distinct sealed type from `ProviderError`

```kotlin
public sealed interface SubmitError {
    public data object SubmissionNotSupported : SubmitError
    public data object EmptyTransaction : SubmitError
    public data class Rejected(public val code: Int, public val detail: String) : SubmitError
    public data class Transport(public val message: String) : SubmitError
    public data class RemoteStatus(public val code: Int, public val detail: String? = null) : SubmitError
    public data object RateLimited : SubmitError
    public data class Deserialization(public val detail: String) : SubmitError
    public data object Unknown : SubmitError
}
```

- `SubmissionNotSupported` exists specifically for providers that deliberately do not submit
  (§5) — it is not a generic "not implemented" placeholder for missing features elsewhere.
- `EmptyTransaction` covers the trivial invalid-input case (no bytes) before any backend call,
  mirroring how `ChainQueryProvider` checks network mismatch before any HTTP call (ADR-0007
  §4/§5's "fail fast, before the network" pattern).
- `Rejected(code, detail)` is new relative to `ProviderError` and is the reason submission gets
  its own error type rather than reusing `ProviderError` verbatim: a node-level validation
  rejection (malformed body, bad/missing witness, already-spent input) is a distinct, expected
  failure category for submission that has no read-path analogue.
- `Transport`, `RemoteStatus`, `RateLimited`, `Deserialization`, `Unknown` mirror the equivalent
  `ProviderError` variants and the same naming discipline (`RemoteStatus`, not `HttpStatus`,
  per ADR-0006 §4) — Block 1.11b's Blockfrost implementation is expected to map HTTP statuses
  into these the same way `BlockfrostChainQueryProvider` maps them into `ProviderError` (ADR-0007
  §5). `RemoteStatus` additionally carries an optional `detail` because a submit rejection body
  is more often worth surfacing to a user than a read failure's.
- `ProviderError.NotFound` and `ProviderError.NetworkMismatch` have no `SubmitError` analogue in
  this sub-block: "not found" describes a queried resource, not a submission outcome, and this
  interface does not perform the network-mismatch check `ChainQueryProvider.getUtxos` does (§1).

### 5. `InMemoryTxSubmitProvider`: never fakes success

Block 1.11a ships exactly one implementation, mirroring `InMemoryChainQueryProvider`'s role as
the offline default: `InMemoryTxSubmitProvider`. Every call to `submit`, for any input
including empty bytes, returns `KardanoResult.Err(SubmitError.SubmissionNotSupported)`. It
performs **no** validation or decoding of `transactionCbor` — because it never submits, there is
nothing for validation to protect against, and adding partial validation would risk implying a
"looks valid" signal a mock that never talks to a network cannot actually back up. This is the
concrete embodiment of the guardrail that a mock must not fake successful submission.

Downstream callers (Block 1.11c's Playground checkpoint) are expected to map
`SubmissionNotSupported` to an explicit "this provider does not submit" message, distinct from
any real rejection.

### 6. Defensive copying across the suspend/network boundary

`TxSubmitProvider.submit`'s KDoc requires that a concrete implementation take a defensive copy
of `transactionCbor` before using it across any suspend/network boundary (for example before
handing it to an HTTP client whose write may be scheduled on another dispatcher or delayed).
`transactionCbor` is treated as untrusted, caller-owned input for the duration of the call, per
the workspace `ByteArray` correctness guardrail. `InMemoryTxSubmitProvider` has no network
boundary to cross and does not read `transactionCbor` at all, so it has nothing to copy; the
requirement is documented on the interface for every future implementation (starting with
Block 1.11b's Blockfrost provider).

### 7. Planned sub-block split

- **1.11a** (this change): `:provider` boundary — `TxSubmitProvider`, `SubmitError`,
  `InMemoryTxSubmitProvider`, contract tests, this ADR, `provider/README.md`. No Blockfrost
  implementation, no `:shared` change.
- **1.11b** (deferred): `:provider-blockfrost`'s `BlockfrostTxSubmitProvider` — `POST
  {baseUrl}/tx/submit`, `Content-Type: application/cbor`, `project_id` header (reusing
  `BlockfrostConfig`/`configureBlockfrost` from ADR-0007), raw CBOR request body, and mapping
  the `200` JSON hex-string response into a `TxHash` and non-2xx statuses into `SubmitError`.
  MockEngine tests only; no automated live submit (destructive, needs funded preprod ADA).
- **1.11c** (deferred): `:shared` Playground "Submit Transaction (preprod)" checkpoint below
  the existing 1.10c "Signed Transaction" section, gated behind the live Blockfrost toggle,
  reusing the 1.10c build/sign flow, and the accompanying manual Android checkpoint.

  > **Result (Blocks 1.11b/1.11c): IMPLEMENTED.** Both deferred sub-blocks above have since
  > shipped, exactly as designed:
  > - `:provider-blockfrost` gained `BlockfrostTxSubmitProvider` — `POST {baseUrl}/tx/submit`,
  >   `Content-Type: application/cbor`, the `project_id` header via the existing
  >   `BlockfrostConfig`/`configureBlockfrost` (ADR-0007), a raw CBOR request body, and mapping
  >   the `200` JSON hex-string response into a `TxHash` and non-2xx statuses into `SubmitError`.
  > - `:shared` gained the Playground "Submit Transaction (preprod)" checkpoint, below the
  >   1.10c "Signed Transaction" section, gated behind the live Blockfrost toggle and reusing
  >   the 1.10c build/sign flow, with the accompanying manual Android checkpoint completed.
  > - `CHANGELOG.md`, `docs/ROADMAP.md`, `README.md`, and `shared/README.md` all describe
  >   submission as delivered; this result note reconciles this ADR's own header/§7 text (which
  >   is left as an accurate record of the Block 1.11a-only decision at the time this ADR was
  >   written) with that shipped state.

---

## Consequences

- `:provider` now has two independent interfaces (`ChainQueryProvider`, `TxSubmitProvider`)
  instead of one read-and-write interface; a consumer picks up only what it needs.
- `:provider`'s dependency graph is unchanged (still depends only on `:core`; no new
  third-party dependency in `commonMain`), and no dependency cycle with `:tx` is introduced.
- The public API surface a future Blockfrost submit provider must satisfy is fixed now, so
  1.11b can be implemented and reviewed as a small, focused diff against a stable interface.
- No behavior changes anywhere else in the SDK: `:wallet`, `:tx`, `:crypto`, `:core`, and
  `:shared` are untouched by this sub-block.

---

## Non-goals

- No Blockfrost (or any other real network) submission implementation (Block 1.11b).
- No `:shared` Playground submission checkpoint or UI change (Block 1.11c).
- No change to `:wallet`, `:tx`, `:crypto`, `:core`, or any signing code.
- No wallet-level submit orchestration method; `:wallet` continues to only restore, query
  balance, and sign. Whether `:shared` calls `TxSubmitProvider.submit` directly with
  `walletSigned.signedTransaction.cbor()` (the current plan) or a future orchestration helper is
  introduced remains a Block 1.11c decision, not one this ADR needs to make.
- No mainnet, no real mnemonics/private keys/funds, no native assets/scripts/metadata/multisig.

---

## Follow-up work

- Block 1.11b: `BlockfrostTxSubmitProvider` in `:provider-blockfrost`.
- Block 1.11c: `:shared` submit checkpoint and the mandatory manual Android checkpoint for
  `1.11` in `docs/PHASE_1_PLAN.md`.
- ADR-0006 (`docs/DECISIONS/0006-provider-boundary-and-strategy.md`) and ADR-0007
  (`docs/DECISIONS/0007-http-client-and-blockfrost-provider.md`) remain the governing decisions
  this ADR implements and extends.
