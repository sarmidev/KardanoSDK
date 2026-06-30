package org.sarmidev.kardano.primitives

import org.sarmidev.kardano.KardanoResult

/**
 * A structural container for a 32-byte Cardano transaction hash.
 *
 * Holds exactly [SIZE] bytes. This is a structural byte container only: it does not verify
 * the hash's origin, that the bytes are a correct digest of any transaction, that the
 * transaction exists on-chain, and it does not parse or render any hex representation
 * (hex is a later Phase 0 concern).
 *
 * The constructor is private; create instances with [of]. The wrapped bytes are copied on
 * construction and on every read, so the internal array is never shared or mutable.
 */
public class TxHash private constructor(bytes: ByteArray) {

    private val bytes: ByteArray = bytes.copyOf()

    /**
     * Returns a copy of the wrapped bytes.
     *
     * @return a fresh [ByteArray] of length [SIZE]; mutating it does not affect this
     *   [TxHash].
     */
    public fun toByteArray(): ByteArray = bytes.copyOf()

    /** Value equality based on byte content. */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is TxHash) return false
        return bytes.contentEquals(other.bytes)
    }

    /** Hash code derived from byte content. */
    override fun hashCode(): Int = bytes.contentHashCode()

    /** Structural description that does not render the wrapped bytes. */
    override fun toString(): String = "TxHash(size=$SIZE)"

    public companion object {

        /** The exact number of bytes a [TxHash] holds. */
        public const val SIZE: Int = 32

        /**
         * Creates a [TxHash] from [bytes].
         *
         * @param bytes the candidate hash bytes; must be exactly [SIZE] bytes. The array is
         *   copied defensively, so later mutations of the caller's array do not affect the
         *   returned [TxHash].
         * @return [KardanoResult.Ok] with the [TxHash] when [bytes] has length [SIZE], or
         *   [KardanoResult.Err] with [ByteSizeError.Fixed] otherwise. Never throws.
         */
        public fun of(bytes: ByteArray): KardanoResult<TxHash, ByteSizeError> =
            if (bytes.size != SIZE) {
                KardanoResult.Err(ByteSizeError.Fixed(SIZE, bytes.size))
            } else {
                KardanoResult.Ok(TxHash(bytes))
            }
    }
}
