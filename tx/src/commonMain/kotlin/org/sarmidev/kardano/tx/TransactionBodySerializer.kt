package org.sarmidev.kardano.tx

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.encoding.cbor.CborValue
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.UtxoRef

/**
 * Serializes an already fully specified [TransactionBodyRequest] into a canonical, unsigned
 * Cardano `transaction_body` (ADR-0014 §2).
 *
 * This is the Block 1.9b-1 entry point: it orders and validates the caller-supplied inputs
 * and outputs, then encodes the Conway `transaction_body` map through `:core`'s unchanged
 * CBOR subset (ADR-0014 §3), using the legacy output form (§5) and the ledger input ordering
 * (§4). It performs **no** coin selection and computes **no** fee — the largest-first,
 * fee/change fixed-point builder (§6-7) is deferred to Block 1.9b-2.
 */
public object TransactionBodySerializer {

    /** Body map key for the inputs field (ADR-0014 §2; CDDL `transaction_body` key `0`). */
    private const val FIELD_INPUTS: Long = 0L

    /** Body map key for the outputs field (ADR-0014 §2; CDDL `transaction_body` key `1`). */
    private const val FIELD_OUTPUTS: Long = 1L

    /** Body map key for the fee field (ADR-0014 §2; CDDL `transaction_body` key `2`). */
    private const val FIELD_FEE: Long = 2L

    /** Body map key for the ttl field (ADR-0014 §2; CDDL `transaction_body` key `3`). */
    private const val FIELD_TTL: Long = 3L

    /**
     * Serializes [request] into a [TransactionDraft] carrying the canonical
     * `transaction_body` CBOR bytes, stamped with [TransactionBodyRequest.network] and
     * [TransactionDraftScope.Phase1AdaOnlySinglePayment] (ADR-0019). Mainnet requests are
     * accepted here; signing, not this serializer, rejects a mainnet draft.
     *
     * @param request the already-decided inputs, outputs, fee, and optional ttl.
     * @return [KardanoResult.Ok] with the [TransactionDraft], or [KardanoResult.Err] with a
     *   [TxBuildError] if [TransactionBodyRequest.inputs] is empty
     *   ([TxBuildError.NoInputs]), [TransactionBodyRequest.outputs] is empty
     *   ([TxBuildError.NoOutputs]), an output's address network disagrees with
     *   [TransactionBodyRequest.network] ([TxBuildError.NetworkMismatch]), two inputs share a
     *   `(transaction_id, index)` pair ([TxBuildError.DuplicateInput]), or CBOR encoding
     *   fails ([TxBuildError.Serialization]). Never throws.
     */
    public fun serialize(
        request: TransactionBodyRequest,
    ): KardanoResult<TransactionDraft, TxBuildError> {
        if (request.inputs.isEmpty()) {
            return KardanoResult.Err(TxBuildError.NoInputs)
        }
        if (request.outputs.isEmpty()) {
            return KardanoResult.Err(TxBuildError.NoOutputs)
        }

        for (output in request.outputs) {
            val actual = output.address.network
            if (actual != request.network) {
                return KardanoResult.Err(TxBuildError.NetworkMismatch(request.network, actual))
            }
        }

        val sortedInputs = when (val result = sortAndDedupeInputs(request.inputs)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> return result
        }

        val bodyMap = buildBodyMap(sortedInputs, request.outputs, request.fee, request.ttl)
        val bodyBytes = when (val result = Cbor.encode(bodyMap)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err ->
                return KardanoResult.Err(TxBuildError.Serialization(result.error))
        }

        return KardanoResult.Ok(
            TransactionDraft(
                selectedInputs = sortedInputs,
                outputs = request.outputs,
                fee = request.fee,
                ttl = request.ttl,
                bodyCborBytes = bodyBytes,
                network = request.network,
                scope = TransactionDraftScope.Phase1AdaOnlySinglePayment,
            ),
        )
    }

    /**
     * Sorts [inputs] ascending by [LedgerInputOrder] (ADR-0014 §4) and rejects duplicate
     * `(transaction_id, index)` pairs.
     */
    private fun sortAndDedupeInputs(
        inputs: List<UtxoRef>,
    ): KardanoResult<List<UtxoRef>, TxBuildError> {
        val sorted = inputs.sortedWith(LedgerInputOrder)
        for (i in 1 until sorted.size) {
            if (LedgerInputOrder.compare(sorted[i - 1], sorted[i]) == 0) {
                return KardanoResult.Err(TxBuildError.DuplicateInput(sorted[i]))
            }
        }
        return KardanoResult.Ok(sorted)
    }

    /**
     * Builds the Conway `transaction_body` map (ADR-0014 §2) with keys `0`/`1`/`2` and, when
     * [ttl] is supplied, `3`, in ascending order.
     */
    private fun buildBodyMap(
        inputs: List<UtxoRef>,
        outputs: List<TransactionOutput>,
        fee: Lovelace,
        ttl: Long?,
    ): CborValue.CborMap {
        val entries = mutableListOf(
            CborValue.CborEntry(CborValue.CborUnsigned(FIELD_INPUTS), encodeInputs(inputs)),
            CborValue.CborEntry(CborValue.CborUnsigned(FIELD_OUTPUTS), encodeOutputs(outputs)),
            CborValue.CborEntry(
                CborValue.CborUnsigned(FIELD_FEE),
                CborValue.CborUnsigned(fee.value),
            ),
        )
        if (ttl != null) {
            entries.add(
                CborValue.CborEntry(CborValue.CborUnsigned(FIELD_TTL), CborValue.CborUnsigned(ttl)),
            )
        }
        return CborValue.CborMap(entries)
    }

    /**
     * Encodes the inputs field as a plain, untagged, definite-length array (ADR-0014 §4): no
     * `#6.258` set tag. Each element is [TxCborSupport.encodeInput].
     */
    private fun encodeInputs(inputs: List<UtxoRef>): CborValue.CborArray =
        CborValue.CborArray(inputs.map { TxCborSupport.encodeInput(it) })

    /**
     * Encodes the outputs field using [TxCborSupport.encodeOutput] per element: the
     * legacy/Alonzo array form (ADR-0014 §5), `[address_bytes, coin]`, with no datum-hash
     * element.
     */
    private fun encodeOutputs(outputs: List<TransactionOutput>): CborValue.CborArray =
        CborValue.CborArray(outputs.map { TxCborSupport.encodeOutput(it) })
}
