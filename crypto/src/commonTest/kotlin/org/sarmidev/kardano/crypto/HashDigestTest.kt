package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Structural tests for [HashDigest], exercising the module-internal size-validating factory
 * directly (no hashing backend involved).
 */
class HashDigestTest {

    @Test
    fun of_rejectsWrongLength() {
        when (val result = HashDigest.of(ByteArray(10), HashDigest.SIZE_224)) {
            is KardanoResult.Ok -> fail("expected Err for a wrong-length digest")
            is KardanoResult.Err ->
                assertEquals(CryptoError.InvalidDigestLength(HashDigest.SIZE_224, 10), result.error)
        }
    }

    @Test
    fun of_defensiveCopyOnConstruction() {
        val source = ByteArray(HashDigest.SIZE_224) { it.toByte() }
        val digest = okDigest(HashDigest.of(source, HashDigest.SIZE_224))

        source[0] = 99

        assertEquals(0, digest.toByteArray()[0], "mutating the source array must not affect the digest")
    }

    @Test
    fun toByteArray_returnsIndependentCopy() {
        val digest = okDigest(HashDigest.of(ByteArray(HashDigest.SIZE_256), HashDigest.SIZE_256))

        val out = digest.toByteArray()
        out[0] = 7

        assertEquals(0, digest.toByteArray()[0], "mutating the returned array must not affect the digest")
    }

    @Test
    fun toString_isStructuralAndDoesNotRenderBytes() {
        val digest224 = okDigest(HashDigest.of(ByteArray(HashDigest.SIZE_224) { 0xAB.toByte() }, HashDigest.SIZE_224))
        val digest256 = okDigest(HashDigest.of(ByteArray(HashDigest.SIZE_256), HashDigest.SIZE_256))

        assertEquals("HashDigest(size=28)", digest224.toString())
        assertEquals("HashDigest(size=32)", digest256.toString())
        assertFalse(digest224.toString().contains("ab"), "toString must not render the wrapped bytes")
    }

    @Test
    fun equalsAndHashCode_areByContent() {
        val bytes = ByteArray(HashDigest.SIZE_224) { it.toByte() }
        val a = okDigest(HashDigest.of(bytes, HashDigest.SIZE_224))
        val b = okDigest(HashDigest.of(bytes.copyOf(), HashDigest.SIZE_224))

        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())

        val differentBytes = ByteArray(HashDigest.SIZE_224) { (it + 1).toByte() }
        val c = okDigest(HashDigest.of(differentBytes, HashDigest.SIZE_224))
        assertNotEquals(a, c)
    }

    @Test
    fun size_reportsDigestLength() {
        val digest = okDigest(HashDigest.of(ByteArray(HashDigest.SIZE_256), HashDigest.SIZE_256))
        assertTrue(digest.size == HashDigest.SIZE_256)
    }

    private fun okDigest(result: KardanoResult<HashDigest, CryptoError>): HashDigest =
        when (result) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }
}
