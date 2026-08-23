package org.sarmidev.kardano.crypto.hashing

/**
 * A typed, backend-neutral error returned by a [Hashing] operation.
 *
 * These variants describe failure categories without naming or leaking the shape of any
 * specific cryptographic backend. A concrete [Hashing] implementation is responsible for
 * mapping its backend's failures into these variants, so the public API stays independent of
 * the library that computes the digest.
 */
public sealed interface CryptoError {

    /**
     * The candidate input exceeded [Hashing.MAX_INPUT_BYTES]. The limit is checked before the
     * input is defensively copied, so an oversized caller-built array does not force a second
     * large allocation before hashing even starts.
     *
     * @property max the maximum number of input bytes allowed ([Hashing.MAX_INPUT_BYTES]).
     * @property actual the number of input bytes that were provided.
     */
    public data class InputTooLong(public val max: Int, public val actual: Int) : CryptoError

    /**
     * The backend failed while computing a digest.
     *
     * @property message a short, human-readable description of the failure. It carries no
     *   backend type; a concrete implementation derives it from the caught failure's message.
     */
    public data class HashingFailed(public val message: String) : CryptoError

    /**
     * A digest was rejected because its length did not match the expected size for the
     * requested algorithm.
     *
     * @property expected the exact number of bytes the digest was expected to have.
     * @property actual the number of bytes that were produced.
     */
    public data class InvalidDigestLength(
        public val expected: Int,
        public val actual: Int,
    ) : CryptoError
}
