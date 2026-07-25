package org.sarmidev.kardano.crypto.derivation

import org.sarmidev.kardano.KardanoResult
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Structural tests for [ExtendedPrivateKey], exercising key-material handling rules (ADR-0009
 * §7) with synthetic fixture bytes. Not key material from any real or golden derivation.
 */
class ExtendedPrivateKeyTest {

    // Synthetic fixture bytes only; not derived from any mnemonic or real key material.
    private val fixtureXsk = ByteArray(64) { (it + 1).toByte() }
    private val fixtureChainCode = ByteArray(32) { (it + 100).toByte() }

    @Test
    fun of_correctLengths_isOk() {
        val result = ExtendedPrivateKey.of(fixtureXsk, fixtureChainCode)

        assertTrue(result is KardanoResult.Ok)
    }

    @Test
    fun of_wrongXskLength_isInvalidKeyMaterial() {
        val tooShort = fixtureXsk.copyOf(63)

        val result = ExtendedPrivateKey.of(tooShort, fixtureChainCode)

        assertEquals(
            KardanoResult.Err(KeyDerivationError.InvalidKeyMaterial(expectedBytes = 64, actualBytes = 63)),
            result,
        )
    }

    @Test
    fun of_wrongChainCodeLength_isInvalidKeyMaterial() {
        val tooShort = fixtureChainCode.copyOf(31)

        val result = ExtendedPrivateKey.of(fixtureXsk, tooShort)

        assertEquals(
            KardanoResult.Err(KeyDerivationError.InvalidKeyMaterial(expectedBytes = 32, actualBytes = 31)),
            result,
        )
    }

    @Test
    fun xskBytesForTesting_returnsXskFollowedByChainCode() {
        val key = okKey(ExtendedPrivateKey.of(fixtureXsk, fixtureChainCode))

        val bytes = key.xskBytesForTesting()

        assertEquals(96, bytes.size)
        assertTrue(bytes.copyOfRange(0, 64).contentEquals(fixtureXsk))
        assertTrue(bytes.copyOfRange(64, 96).contentEquals(fixtureChainCode))
    }

    @Test
    fun xskBytesForTesting_returnsIndependentCopy() {
        val key = okKey(ExtendedPrivateKey.of(fixtureXsk, fixtureChainCode))

        val first = key.xskBytesForTesting()
        first[0] = 0x7F

        assertFalse(
            key.xskBytesForTesting()[0] == 0x7F.toByte(),
            "mutating a returned copy must not affect the ExtendedPrivateKey's internal bytes",
        )
    }

    @Test
    fun of_doesNotRetainCallerArrayReference() {
        val callerXsk = fixtureXsk.copyOf()
        val key = okKey(ExtendedPrivateKey.of(callerXsk, fixtureChainCode))

        callerXsk[0] = 0x7F

        assertFalse(
            key.xskBytesForTesting()[0] == 0x7F.toByte(),
            "mutating the caller's array after construction must not affect the ExtendedPrivateKey",
        )
    }

    @Test
    fun extendedPrivateKeyBytesForSigning_returnsXskFollowedByChainCode() {
        val key = okKey(ExtendedPrivateKey.of(fixtureXsk, fixtureChainCode))

        val bytes = key.extendedPrivateKeyBytesForSigning()

        assertEquals(96, bytes.size)
        assertTrue(bytes.copyOfRange(0, 64).contentEquals(fixtureXsk))
        assertTrue(bytes.copyOfRange(64, 96).contentEquals(fixtureChainCode))
    }

    @Test
    fun extendedPrivateKeyBytesForSigning_returnsIndependentCopy() {
        val key = okKey(ExtendedPrivateKey.of(fixtureXsk, fixtureChainCode))

        val first = key.extendedPrivateKeyBytesForSigning()
        first[0] = 0x7F

        assertFalse(
            key.extendedPrivateKeyBytesForSigning()[0] == 0x7F.toByte(),
            "mutating a returned copy must not affect the ExtendedPrivateKey's internal bytes",
        )
    }

    @Test
    fun clear_wipesKeyBytesOnThisInstanceOnly() {
        val key = okKey(ExtendedPrivateKey.of(fixtureXsk, fixtureChainCode))

        key.clear()

        assertTrue(
            key.xskBytesForTesting().all { it == 0.toByte() },
            "clear() must zero the retained xsk and chain code",
        )
    }

    @Test
    fun toString_isStructuralAndDoesNotRenderKeyBytes() {
        val key = okKey(ExtendedPrivateKey.of(fixtureXsk, fixtureChainCode))

        assertEquals("ExtendedPrivateKey()", key.toString())
    }

    private fun okKey(
        result: KardanoResult<ExtendedPrivateKey, KeyDerivationError>,
    ): ExtendedPrivateKey = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }
}
