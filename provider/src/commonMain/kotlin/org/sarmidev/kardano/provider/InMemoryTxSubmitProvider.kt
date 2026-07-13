package org.sarmidev.kardano.provider

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash

/**
 * A [TxSubmitProvider] that never submits anything.
 *
 * This is a sample/test double, not a real provider, and it must never fake acceptance: every
 * call to [submit] returns [SubmitError.SubmissionNotSupported], regardless of input. It does
 * not decode, validate, or otherwise inspect [transactionCbor][submit] — because it never
 * submits, there is no meaningful validation for it to perform, and attempting one would
 * invite exactly the kind of partial, misleading "looks valid" signal a mock that fakes
 * success would give.
 *
 * It exists so that wallet and Playground submit-checkpoint work can be exercised against a
 * stable, offline, unmistakably-non-submitting double, and so downstream error-mapping code
 * has a [SubmitError] to map even before a real backend provider is wired in.
 *
 * @param network the network this provider is bound to; defaults to [Network.TESTNET].
 */
public class InMemoryTxSubmitProvider(
    override val network: Network = Network.TESTNET,
) : TxSubmitProvider {

    /**
     * Always returns [KardanoResult.Err] with [SubmitError.SubmissionNotSupported], including
     * for empty [transactionCbor]. Never inspects [transactionCbor] and never reports success.
     */
    override suspend fun submit(transactionCbor: ByteArray): KardanoResult<TxHash, SubmitError> =
        KardanoResult.Err(SubmitError.SubmissionNotSupported)
}
