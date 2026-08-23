package org.sarmidev.kardano.crypto.hashing

import org.sarmidev.kardano.KardanoResult
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

/**
 * Boundary tests for the [Hashing.MAX_INPUT_BYTES] bound added to close finding W6-1
 * (`docs/AUDIT/2026-08-22-pre-release-audit.md`): [Hashing.blake2b224]/[Hashing.blake2b256]
 * previously enforced no input-size bound before hashing, unlike this SDK's other parser
 * primitives (`Cbor`, `Bech32`). No SDK-invented digest value is asserted here — these tests
 * only exercise the size bound itself (rejection at the boundary, success just under it), not
 * a known-answer vector; see [HashingVectorsTest] for cited digest vectors.
 */
class HashInputBoundTest {

    private val hashing: Hashing = Hashing.default()

    @Test
    fun blake2b224_atLimit_succeeds() {
        val input = ByteArray(Hashing.MAX_INPUT_BYTES)
        val result = hashing.blake2b224(input)
        assertIs<KardanoResult.Ok<HashDigest>>(result)
        assertEquals(HashDigest.SIZE_224, result.value.size)
    }

    @Test
    fun blake2b224_overLimit_isRejected() {
        val input = ByteArray(Hashing.MAX_INPUT_BYTES + 1)
        val error = assertIs<KardanoResult.Err<CryptoError>>(hashing.blake2b224(input)).error
        assertEquals(CryptoError.InputTooLong(Hashing.MAX_INPUT_BYTES, input.size), error)
    }

    @Test
    fun blake2b256_atLimit_succeeds() {
        val input = ByteArray(Hashing.MAX_INPUT_BYTES)
        val result = hashing.blake2b256(input)
        assertIs<KardanoResult.Ok<HashDigest>>(result)
        assertEquals(HashDigest.SIZE_256, result.value.size)
    }

    @Test
    fun blake2b256_overLimit_isRejected() {
        val input = ByteArray(Hashing.MAX_INPUT_BYTES + 1)
        val error = assertIs<KardanoResult.Err<CryptoError>>(hashing.blake2b256(input)).error
        assertEquals(CryptoError.InputTooLong(Hashing.MAX_INPUT_BYTES, input.size), error)
    }
}
