package org.sarmidev.kardano.tx

/**
 * The result of [TransactionAssembler.assemble]: the canonical, full, signed Cardano
 * `transaction` CBOR bytes — `[transaction_body, transaction_witness_set, true, null]`
 * (ADR-0015 §3) — plus the [witnessSet] that produced it.
 *
 * This is a **signed, unsubmitted** structural artifact only (ADR-0015 §3/§7): it embeds the
 * exact [TransactionDraft.bodyCbor] bytes it was assembled from, unchanged, and the supplied
 * [witnessSet]; it carries no transaction id of its own — `:tx` never hashes, so computing and
 * reporting the id (`Blake2b-256` of the same body bytes) is left to a caller that already
 * depends on `:crypto` (ADR-0015 §3), typically `:wallet`. Submitting this transaction is out
 * of scope for Block 1.10 (Block 1.11, ADR-0006).
 *
 * @property witnessSet the witness set this artifact was assembled with.
 */
public class SignedTransaction internal constructor(
    public val witnessSet: TransactionWitnessSet,
    cborBytes: ByteArray,
) {

    private val cborBytes: ByteArray = cborBytes.copyOf()

    /** The number of Shelley key witnesses [witnessSet] carries. */
    public val witnessCount: Int get() = witnessSet.verificationKeyWitnesses.size

    /**
     * Returns a copy of the canonical, full, signed `transaction` CBOR bytes.
     *
     * @return a fresh [ByteArray]; mutating it does not affect this [SignedTransaction].
     */
    public fun cbor(): ByteArray = cborBytes.copyOf()

    /** Structural description that does not render the CBOR bytes. */
    override fun toString(): String =
        "SignedTransaction(witnessCount=$witnessCount, cborBytes=${cborBytes.size})"
}
