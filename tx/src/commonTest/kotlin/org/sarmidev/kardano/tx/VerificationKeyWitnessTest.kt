package org.sarmidev.kardano.tx

import org.sarmidev.kardano.KardanoResult
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Structural tests for [VerificationKeyWitness] (ADR-0015 §1/§3/§5, Block 1.10b).
 *
 * `:tx` is crypto-free: these are synthetic fixture bytes, not a real signature or key.
 */
class VerificationKeyWitnessTest {

    // Synthetic fixture bytes only; not a real verification key or signature.
    private val fixtureVkey = ByteArray(32) { (it + 1).toByte() }
    private val fixtureSignature = ByteArray(64) { (it + 100).toByte() }

    @Test
    fun of_correctLengths_isOk() {
        val result = VerificationKeyWitness.of(fixtureVkey, fixtureSignature)

        assertTrue(result is KardanoResult.Ok)
    }

    @Test
    fun of_wrongVkeyLength_isInvalidVerificationKeyLength() {
        val tooShort = fixtureVkey.copyOf(31)

        val result = VerificationKeyWitness.of(tooShort, fixtureSignature)

        assertEquals(
            KardanoResult.Err(
                TxBuildError.InvalidVerificationKeyLength(expectedBytes = 32, actualBytes = 31),
            ),
            result,
        )
    }

    @Test
    fun of_wrongSignatureLength_isInvalidSignatureLength() {
        val tooShort = fixtureSignature.copyOf(63)

        val result = VerificationKeyWitness.of(fixtureVkey, tooShort)

        assertEquals(
            KardanoResult.Err(
                TxBuildError.InvalidSignatureLength(expectedBytes = 64, actualBytes = 63),
            ),
            result,
        )
    }

    @Test
    fun vkeyBytesAndSignatureBytes_returnIndependentCopies() {
        val witness = okWitness(VerificationKeyWitness.of(fixtureVkey, fixtureSignature))

        val exposedVkey = witness.vkeyBytes()
        exposedVkey[0] = 0x7F
        val exposedSignature = witness.signatureBytes()
        exposedSignature[0] = 0x7F

        assertFalse(witness.vkeyBytes()[0] == 0x7F.toByte())
        assertFalse(witness.signatureBytes()[0] == 0x7F.toByte())
    }

    @Test
    fun of_doesNotRetainCallerArrayReferences() {
        val callerVkey = fixtureVkey.copyOf()
        val callerSignature = fixtureSignature.copyOf()
        val witness = okWitness(VerificationKeyWitness.of(callerVkey, callerSignature))

        callerVkey[0] = 0x7F
        callerSignature[0] = 0x7F

        assertFalse(witness.vkeyBytes()[0] == 0x7F.toByte())
        assertFalse(witness.signatureBytes()[0] == 0x7F.toByte())
    }

    @Test
    fun equals_basedOnByteContent() {
        val a = okWitness(VerificationKeyWitness.of(fixtureVkey, fixtureSignature))
        val b = okWitness(VerificationKeyWitness.of(fixtureVkey.copyOf(), fixtureSignature.copyOf()))

        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }

    @Test
    fun toString_isStructuralAndDoesNotRenderBytes() {
        val witness = okWitness(VerificationKeyWitness.of(fixtureVkey, fixtureSignature))

        assertEquals("VerificationKeyWitness()", witness.toString())
    }

    private fun okWitness(
        result: KardanoResult<VerificationKeyWitness, TxBuildError>,
    ): VerificationKeyWitness = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }
}
