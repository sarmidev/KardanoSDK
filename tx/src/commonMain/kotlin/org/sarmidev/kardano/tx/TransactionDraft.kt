package org.sarmidev.kardano.tx

import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.UtxoRef

/**
 * The result of [TransactionBodySerializer.serialize]: the canonical unsigned
 * `transaction_body` CBOR bytes plus the structured summary that produced them.
 *
 * Every [TransactionDraft] is produced by [TransactionBodySerializer.serialize]. It may be
 * reached directly, with a caller-supplied [fee], or indirectly through
 * [TransactionBuilder.build], which selects inputs and estimates/decides [fee] before
 * delegating to [TransactionBodySerializer.serialize] for the actual encoding. Both paths
 * stamp [network] from the request and [scope] as
 * [TransactionDraftScope.Phase1AdaOnlySinglePayment] (ADR-0019). The constructor is
 * `internal`: callers outside `:tx` cannot forge these fields.
 *
 * This is an unsigned, unsubmitted structural artifact only (ADR-0014 §2): it carries no
 * witness set, is not a full `transaction`, and has no signature or transaction id. The
 * transaction id (`Blake2b-256` of [bodyCbor]) is left to a caller that already depends on
 * `:crypto` (ADR-0014 §2); `:tx` never hashes or signs.
 *
 * Instances guarantee the bytes returned by [bodyCbor] are the exact encoding of
 * [selectedInputs] (in ledger order), [outputs], [fee], and [ttl].
 *
 * Mainnet construction of a [TransactionDraft] remains available: [network] may be
 * [Network.MAINNET] when the request asked for it. Signing, not building, is what rejects a
 * mainnet draft (ADR-0019 §1).
 *
 * @property selectedInputs the inputs that were encoded, in the ledger
 *   `(transaction_id, index)` ascending order (ADR-0014 §4) — not necessarily the order the
 *   caller originally supplied them in.
 * @property outputs the outputs that were encoded, in the order supplied.
 * @property fee the fee that was encoded (body field `2`).
 * @property ttl the ttl that was encoded (body field `3`), or null if the field was omitted.
 * @property network the network every encoded output address was validated against.
 * @property scope the construction path that produced this draft. Production constructors
 *   always stamp [TransactionDraftScope.Phase1AdaOnlySinglePayment].
 */
public class TransactionDraft internal constructor(
    selectedInputs: List<UtxoRef>,
    outputs: List<TransactionOutput>,
    public val fee: Lovelace,
    public val ttl: Long?,
    bodyCborBytes: ByteArray,
    public val network: Network,
    public val scope: TransactionDraftScope,
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

    /**
     * Value equality based on [selectedInputs], [outputs], [fee], [ttl], the body bytes,
     * [network], and [scope].
     */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is TransactionDraft) return false
        return selectedInputs == other.selectedInputs &&
            outputs == other.outputs &&
            fee == other.fee &&
            ttl == other.ttl &&
            bodyBytes.contentEquals(other.bodyBytes) &&
            network == other.network &&
            scope == other.scope
    }

    /**
     * Hash code derived from [selectedInputs], [outputs], [fee], [ttl], the body bytes,
     * [network], and [scope].
     */
    override fun hashCode(): Int {
        var result = selectedInputs.hashCode()
        result = 31 * result + outputs.hashCode()
        result = 31 * result + fee.hashCode()
        result = 31 * result + (ttl?.hashCode() ?: 0)
        result = 31 * result + bodyBytes.contentHashCode()
        result = 31 * result + network.hashCode()
        result = 31 * result + scope.hashCode()
        return result
    }

    /** Structural description that does not render the body bytes. */
    override fun toString(): String =
        "TransactionDraft(inputs=${selectedInputs.size}, outputs=${outputs.size}, " +
            "fee=$fee, ttl=$ttl, network=$network, scope=$scope, bodyBytes=${bodyBytes.size})"
}
