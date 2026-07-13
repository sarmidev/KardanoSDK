package org.sarmidev.kardano.tx

import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.UtxoRef

/**
 * The result of [TransactionBodySerializer.serialize]: the canonical unsigned
 * `transaction_body` CBOR bytes plus the structured summary that produced them.
 *
 * This is an unsigned, unsubmitted structural artifact only (ADR-0014 §2): it carries no
 * witness set, is not a full `transaction`, and [fee] is whatever the caller supplied — this
 * sub-block computes no fee. The transaction id (`Blake2b-256` of [bodyCbor]) is left to a
 * caller that already depends on `:crypto` (ADR-0014 §2); `:tx` never hashes or signs.
 *
 * Instances are only produced by [TransactionBodySerializer.serialize], which guarantees the
 * bytes returned by [bodyCbor] are the exact encoding of [selectedInputs] (in ledger order),
 * [outputs], [fee], and [ttl].
 *
 * @property selectedInputs the inputs that were encoded, in the ledger
 *   `(transaction_id, index)` ascending order (ADR-0014 §4) — not necessarily the order the
 *   caller originally supplied them in.
 * @property outputs the outputs that were encoded, in the order supplied.
 * @property fee the fee that was encoded (body field `2`).
 * @property ttl the ttl that was encoded (body field `3`), or null if the field was omitted.
 */
public class TransactionDraft internal constructor(
    selectedInputs: List<UtxoRef>,
    outputs: List<TransactionOutput>,
    public val fee: Lovelace,
    public val ttl: Long?,
    bodyCborBytes: ByteArray,
) {

    public val selectedInputs: List<UtxoRef> = selectedInputs.toList()

    public val outputs: List<TransactionOutput> = outputs.toList()

    private val bodyBytes: ByteArray = bodyCborBytes.copyOf()

    /**
     * Returns a copy of the canonical unsigned `transaction_body` CBOR bytes.
     *
     * @return a fresh [ByteArray]; mutating it does not affect this [TransactionDraft].
     */
    public fun bodyCbor(): ByteArray = bodyBytes.copyOf()

    /** Value equality based on [selectedInputs], [outputs], [fee], [ttl], and the body bytes. */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is TransactionDraft) return false
        return selectedInputs == other.selectedInputs &&
            outputs == other.outputs &&
            fee == other.fee &&
            ttl == other.ttl &&
            bodyBytes.contentEquals(other.bodyBytes)
    }

    /** Hash code derived from [selectedInputs], [outputs], [fee], [ttl], and the body bytes. */
    override fun hashCode(): Int {
        var result = selectedInputs.hashCode()
        result = 31 * result + outputs.hashCode()
        result = 31 * result + fee.hashCode()
        result = 31 * result + (ttl?.hashCode() ?: 0)
        result = 31 * result + bodyBytes.contentHashCode()
        return result
    }

    /** Structural description that does not render the body bytes. */
    override fun toString(): String =
        "TransactionDraft(inputs=${selectedInputs.size}, outputs=${outputs.size}, " +
            "fee=$fee, ttl=$ttl, bodyBytes=${bodyBytes.size})"
}
