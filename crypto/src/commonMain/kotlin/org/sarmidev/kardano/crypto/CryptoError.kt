package org.sarmidev.kardano.crypto

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
