package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult

/**
 * A structural container for the raw bytes of a Blake2b hash digest.
 *
 * Holds a digest of a fixed byte length (for example [SIZE_224] or [SIZE_256]). This is a
 * structural byte container only: it does not verify how the digest was produced, that the
 * bytes are a correct hash of any particular input, or that any on-chain object exists. It
 * does not parse or render a hex representation.
 *
 * The constructor is private; instances are created inside this module with the internal
 * size-validating [of] factory. The wrapped bytes are copied on construction and on every
 * read, so the internal array is never shared or mutable.
 *
 * @property size the number of bytes this digest holds.
 */
public class HashDigest private constructor(bytes: ByteArray) {

    private val bytes: ByteArray = bytes.copyOf()

    /** The number of bytes this digest holds. */
    public val size: Int get() = bytes.size

    /**
     * Returns a copy of the wrapped digest bytes.
     *
     * @return a fresh [ByteArray] of length [size]; mutating it does not affect this
     *   [HashDigest].
     */
    public fun toByteArray(): ByteArray = bytes.copyOf()

    /** Value equality based on byte content. */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is HashDigest) return false
        return bytes.contentEquals(other.bytes)
    }

    /** Hash code derived from byte content. */
    override fun hashCode(): Int = bytes.contentHashCode()

    /** Structural description that does not render the wrapped bytes. */
    override fun toString(): String = "HashDigest(size=$size)"

    public companion object {

        /** The digest length in bytes of a Blake2b-224 hash. */
        public const val SIZE_224: Int = 28

        /** The digest length in bytes of a Blake2b-256 hash. */
        public const val SIZE_256: Int = 32

        /**
         * Creates a [HashDigest] from [bytes], validating its length against [expectedSize].
         *
         * Internal to the module: callers are the hashing adapters (which pass the digest a
         * backend produced) and this module's structural tests.
         *
         * @param bytes the digest bytes. The array is copied defensively, so later mutations
         *   of the caller's array do not affect the returned [HashDigest].
         * @param expectedSize the exact number of bytes [bytes] must have.
         * @return [KardanoResult.Ok] with the [HashDigest] when `bytes.size == expectedSize`,
         *   or [KardanoResult.Err] with [CryptoError.InvalidDigestLength] otherwise. Never
         *   throws.
         */
        internal fun of(
            bytes: ByteArray,
            expectedSize: Int,
        ): KardanoResult<HashDigest, CryptoError> =
            if (bytes.size != expectedSize) {
                KardanoResult.Err(CryptoError.InvalidDigestLength(expectedSize, bytes.size))
            } else {
                KardanoResult.Ok(HashDigest(bytes))
            }
    }
}
