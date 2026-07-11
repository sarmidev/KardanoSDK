package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult

/**
 * A minimal, backend-neutral interface for the Blake2b hash digests Cardano uses.
 *
 * Blake2b-224 backs credential hashes and Blake2b-256 backs transaction, datum, and script
 * hashes. This interface names no cryptographic library: the concrete implementation is a
 * swappable adapter behind it, so consumers depend only on this SDK's types.
 *
 * Operations compute a digest structurally; they do not sign, derive keys, or interpret the
 * input in any Cardano-specific way. They return [KardanoResult] and never throw, which keeps
 * the API compatible with Swift/ObjC interop (a thrown exception would crash iOS consumers).
 *
 * @see <a href="https://www.rfc-editor.org/rfc/rfc7693">RFC 7693 (BLAKE2)</a>
 */
public interface Hashing {

    /**
     * Computes the Blake2b-224 digest of [input].
     *
     * @param input the bytes to hash. Not modified.
     * @return [KardanoResult.Ok] with a [HashDigest] of length [HashDigest.SIZE_224], or
     *   [KardanoResult.Err] with a [CryptoError] if the backend fails or produces an
     *   unexpected length. Never throws.
     */
    public fun blake2b224(input: ByteArray): KardanoResult<HashDigest, CryptoError>

    /**
     * Computes the Blake2b-256 digest of [input].
     *
     * @param input the bytes to hash. Not modified.
     * @return [KardanoResult.Ok] with a [HashDigest] of length [HashDigest.SIZE_256], or
     *   [KardanoResult.Err] with a [CryptoError] if the backend fails or produces an
     *   unexpected length. Never throws.
     */
    public fun blake2b256(input: ByteArray): KardanoResult<HashDigest, CryptoError>

    public companion object {

        /**
         * Returns the default [Hashing] implementation.
         *
         * The concrete backend is an internal implementation detail and is not part of the
         * public API.
         *
         * @return a ready-to-use [Hashing] instance.
         */
        public fun default(): Hashing = Blake2bHashing()
    }
}
