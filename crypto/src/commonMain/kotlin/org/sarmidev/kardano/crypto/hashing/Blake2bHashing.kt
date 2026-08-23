package org.sarmidev.kardano.crypto.hashing

import org.kotlincrypto.hash.blake2.BLAKE2b
import org.sarmidev.kardano.KardanoResult

/**
 * The default [Hashing] implementation, backed by the KotlinCrypto `blake2` library.
 *
 * This adapter is `internal`: the KotlinCrypto types never appear in the public API. The
 * bit-strength argument to [BLAKE2b] is the digest length in bits, so 224 and 256 produce
 * [HashDigest.SIZE_224]- and [HashDigest.SIZE_256]-byte digests respectively.
 */
internal class Blake2bHashing : Hashing {

    override fun blake2b224(input: ByteArray): KardanoResult<HashDigest, CryptoError> =
        hash(bitStrength = 224, expectedSize = HashDigest.SIZE_224, input = input)

    override fun blake2b256(input: ByteArray): KardanoResult<HashDigest, CryptoError> =
        hash(bitStrength = 256, expectedSize = HashDigest.SIZE_256, input = input)

    /**
     * Computes a Blake2b digest and wraps it in a size-validated [HashDigest].
     *
     * [input]'s length is checked against [Hashing.MAX_INPUT_BYTES] before anything else, so
     * an oversized array is rejected before the defensive copy below allocates a second
     * buffer of the same (oversized) size. The [input] is defensively copied before it reaches
     * the backend, and every backend failure is mapped to a [CryptoError.HashingFailed] rather
     * than thrown, so this operation honors the [Hashing] contract of never throwing.
     */
    private fun hash(
        bitStrength: Int,
        expectedSize: Int,
        input: ByteArray,
    ): KardanoResult<HashDigest, CryptoError> {
        if (input.size > Hashing.MAX_INPUT_BYTES) {
            return KardanoResult.Err(CryptoError.InputTooLong(Hashing.MAX_INPUT_BYTES, input.size))
        }
        return try {
            val digest = BLAKE2b(bitStrength).digest(input.copyOf())
            HashDigest.of(digest, expectedSize)
        } catch (t: Throwable) {
            val detail = t.message ?: t::class.simpleName ?: "hashing failed"
            KardanoResult.Err(CryptoError.HashingFailed(detail))
        }
    }
}
