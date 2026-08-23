package org.sarmidev.kardano.tx

/**
 * Marks which construction path produced a [TransactionDraft] (ADR-0019).
 *
 * [TransactionBodySerializer] and [TransactionBuilder] stamp exactly one value today:
 * [Phase1AdaOnlySinglePayment]. Phase 1 signing rejects any other [TransactionDraftScope]
 * (ADR-0019). A future draft kind (native assets, scripts, metadata) must add its own
 * variant and its own signing-policy ADR rather than reuse this marker.
 */
public sealed interface TransactionDraftScope {

    /**
     * An ADA-only unsigned body with one payment output and an optional change output, produced
     * by [TransactionBodySerializer.serialize] or [TransactionBuilder.build].
     *
     * This is the only scope Phase 1 signing accepts. Mainnet construction of this scope remains
     * available; signing, not building, is what rejects a mainnet draft (ADR-0019 §1).
     */
    public data object Phase1AdaOnlySinglePayment : TransactionDraftScope
}

/**
 * Never stamped by [TransactionBodySerializer] or [TransactionBuilder]. Present so
 * signing-policy tests can construct a draft whose scope Phase 1 signing rejects.
 */
internal data object UnsupportedTransactionDraftScope : TransactionDraftScope
