package org.sarmidev.kardano.provider

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash

/**
 * A Cardano transaction-submission boundary.
 *
 * This is deliberately a **separate interface** from [ChainQueryProvider], not an additional
 * method on it. ADR-0006 pre-committed to this split when it introduced the read-only query
 * boundary: submission is sequenced after local signing exists (Block 1.10) and is
 * semantically different from a read — it is a single mutating, non-idempotent, non-retryable
 * (without care) action against the network, rather than a query with a stable answer. See
 * ADR-0017 for the full rationale.
 *
 * The input is raw signed transaction CBOR bytes rather than any `:tx`-module type
 * (for example a `SignedTransaction`), because `:provider` does not and must not depend on
 * `:tx` — `:tx` already depends on `:provider` for its read models, and a dependency the other
 * way would create a cycle. Callers extract the bytes themselves (for example via
 * `SignedTransaction.cbor()`) and pass them here.
 *
 * All operations are `suspend` and return a [KardanoResult]; they do not throw. Returning
 * failures as [KardanoResult] rather than throwing keeps the API usable across the Swift/ObjC
 * interop boundary, where a thrown exception would crash iOS consumers.
 *
 * A provider is bound to a single [network] at construction, mirroring [ChainQueryProvider].
 */
public interface TxSubmitProvider {

    /**
     * The network this provider is bound to. A concrete implementation may reject a
     * submission that is structurally destined for a different network, but this interface
     * does not require that check (unlike [ChainQueryProvider.getUtxos], there is no address
     * to compare against here).
     */
    public val network: Network

    /**
     * Submits [transactionCbor] — the full signed `transaction` CBOR (body, witness set, and
     * the remaining Shelley `transaction` array elements) — to the network this provider is
     * bound to.
     *
     * Implementations must treat [transactionCbor] as untrusted input they do not own: take a
     * defensive copy before using it across any suspend/network boundary, since nothing stops
     * the caller from mutating its array while the call is in flight.
     *
     * This call is a single mutating action, not a query: submitting the same bytes twice may
     * be rejected the second time (for example as already-seen or as a UTxO conflict) even
     * though the first submission succeeded. Callers are responsible for not resubmitting
     * blindly.
     *
     * @param transactionCbor the full signed transaction CBOR bytes to submit. Never mutated
     *   or retained beyond the call.
     * @return [KardanoResult.Ok] with the accepted transaction's [TxHash], or
     *   [KardanoResult.Err] with a [SubmitError]. Never throws.
     */
    public suspend fun submit(transactionCbor: ByteArray): KardanoResult<TxHash, SubmitError>
}
