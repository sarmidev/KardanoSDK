package org.sarmidev.kardano.tx

import org.sarmidev.kardano.encoding.cbor.CborValue
import org.sarmidev.kardano.primitives.UtxoRef

/**
 * Shared per-entry CBOR encoders for the `transaction_body` `inputs`/`outputs` fields
 * (ADR-0014 §4-5).
 *
 * [TransactionBodySerializer] uses these to build the actual body array elements.
 * [TransactionBuilder] uses [encodeOutput] alone to measure a candidate output's exact
 * encoded byte size for the min-ADA formula (ADR-0014 §7), so the size it computes from can
 * never drift from what the serializer would actually emit. Kept `internal` so this is never
 * part of `:tx`'s public API.
 */
internal object TxCborSupport {

    /** `transaction_input = [transaction_id, index]` (ADR-0014 §4), untagged. */
    internal fun encodeInput(ref: UtxoRef): CborValue.CborArray =
        CborValue.CborArray(
            listOf(
                CborValue.CborByteString(ref.txHash.toByteArray()),
                CborValue.CborUnsigned(ref.outputIndex),
            ),
        )

    /** Legacy/Alonzo `[address, coin]` output form (ADR-0014 §5), no datum-hash element. */
    internal fun encodeOutput(output: TransactionOutput): CborValue.CborArray =
        CborValue.CborArray(
            listOf(
                CborValue.CborByteString(output.address.toByteArray()),
                CborValue.CborUnsigned(output.amount.value),
            ),
        )
}
