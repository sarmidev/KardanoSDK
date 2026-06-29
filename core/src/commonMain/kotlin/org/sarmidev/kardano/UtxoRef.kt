package org.sarmidev.kardano

/**
 * A structural reference to a transaction output: a [txHash] plus a non-negative
 * [outputIndex].
 *
 * This is structural only: it does not verify that the referenced output exists, that it is
 * unspent, or that it is spendable.
 *
 * The constructor is private; create instances with [of].
 *
 * @property txHash the hash of the transaction that produced the output.
 * @property outputIndex the zero-based index of the output within that transaction; always
 *   in `0..Long.MAX_VALUE`.
 */
public class UtxoRef private constructor(
    public val txHash: TxHash,
    public val outputIndex: Long,
) {

    /** Value equality based on [txHash] content and [outputIndex]. */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is UtxoRef) return false
        return outputIndex == other.outputIndex && txHash == other.txHash
    }

    /** Hash code derived from [txHash] and [outputIndex]. */
    override fun hashCode(): Int = 31 * txHash.hashCode() + outputIndex.hashCode()

    /** Structural description of the reference. */
    override fun toString(): String = "UtxoRef(txHash=$txHash, outputIndex=$outputIndex)"

    public companion object {

        /**
         * Creates a [UtxoRef] from [txHash] and [outputIndex].
         *
         * @param txHash the hash of the transaction that produced the output.
         * @param outputIndex the output index; must be in `0..Long.MAX_VALUE`.
         * @return [KardanoResult.Ok] with the [UtxoRef] for a non-negative [outputIndex],
         *   or [KardanoResult.Err] with [UtxoRefError.NegativeIndex] if it is negative.
         *   Never throws.
         */
        public fun of(
            txHash: TxHash,
            outputIndex: Long,
        ): KardanoResult<UtxoRef, UtxoRefError> =
            if (outputIndex < 0L) {
                KardanoResult.Err(UtxoRefError.NegativeIndex(outputIndex))
            } else {
                KardanoResult.Ok(UtxoRef(txHash, outputIndex))
            }
    }
}

/**
 * A typed error produced when creating a [UtxoRef].
 */
public sealed interface UtxoRefError {

    /**
     * The provided output [index] was negative, which is outside the allowed
     * `0..Long.MAX_VALUE` range.
     *
     * @property index the rejected negative output index.
     */
    public data class NegativeIndex(public val index: Long) : UtxoRefError
}
