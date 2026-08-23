package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.tx.TransactionDraftScope

/**
 * Why [ReadOnlyWallet.signTestnetFixtureTransaction] rejected a call before parsing the
 * mnemonic or deriving a key (ADR-0019 §2).
 *
 * Each variant is wallet-owned orchestration policy, not a [org.sarmidev.kardano.tx.TxBuildError]:
 * `:tx` does not know about signing.
 */
public sealed interface SigningScopeViolationReason {

    /**
     * [org.sarmidev.kardano.tx.TransactionDraft.scope] is not the Phase 1 ADA-only
     * single-payment marker this entry point accepts.
     *
     * @property scope the bound scope that was rejected.
     */
    public data class UnsupportedDraftScope(
        public val scope: TransactionDraftScope,
    ) : SigningScopeViolationReason

    /**
     * [org.sarmidev.kardano.tx.TransactionDraft.network] is not [Network.TESTNET].
     *
     * @property draftNetwork the network the draft was built for.
     */
    public data class UnsupportedDraftNetwork(
        public val draftNetwork: Network,
    ) : SigningScopeViolationReason

    /**
     * The caller-declared [network][ReadOnlyWallet.signTestnetFixtureTransaction] does not
     * equal [org.sarmidev.kardano.tx.TransactionDraft.network].
     *
     * @property declared the network argument the caller passed.
     * @property draftNetwork the network bound on the draft.
     */
    public data class DeclaredNetworkMismatch(
        public val declared: Network,
        public val draftNetwork: Network,
    ) : SigningScopeViolationReason

    /**
     * The draft's selected-input / output counts are not the Phase 1 ADA-only single-payment
     * shape (at least one input; one payment output and an optional change output).
     *
     * @property detail a short, non-secret description of the rejected shape.
     */
    public data class UnsupportedDraftShape(
        public val detail: String,
    ) : SigningScopeViolationReason
}
