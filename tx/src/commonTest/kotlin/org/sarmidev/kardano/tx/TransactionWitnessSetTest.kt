package org.sarmidev.kardano.tx

import org.sarmidev.kardano.KardanoResult
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/** Structural tests for [TransactionWitnessSet] (ADR-0015 §1/§3, Block 1.10b). */
class TransactionWitnessSetTest {

    // Synthetic fixture bytes only; not a real verification key or signature.
    private fun fixtureWitness(): VerificationKeyWitness = okWitness(
        VerificationKeyWitness.of(
            vkey = ByteArray(32) { (it + 1).toByte() },
            signature = ByteArray(64) { (it + 100).toByte() },
        ),
    )

    @Test
    fun of_withOneWitness_isOk() {
        val result = TransactionWitnessSet.of(listOf(fixtureWitness()))

        val set = okSet(result)
        assertEquals(1, set.verificationKeyWitnesses.size)
    }

    @Test
    fun of_withNoWitnesses_isEmptyWitnessSet() {
        val result = TransactionWitnessSet.of(emptyList())

        assertEquals(KardanoResult.Err(TxBuildError.EmptyWitnessSet), result)
    }

    @Test
    fun verificationKeyWitnesses_isAnIndependentSnapshot() {
        val source = mutableListOf(fixtureWitness())
        val set = okSet(TransactionWitnessSet.of(source))

        source.add(fixtureWitness())

        assertTrue(set.verificationKeyWitnesses.size == 1, "construction must snapshot the source list")
    }

    private fun okSet(
        result: KardanoResult<TransactionWitnessSet, TxBuildError>,
    ): TransactionWitnessSet = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }

    private fun okWitness(
        result: KardanoResult<VerificationKeyWitness, TxBuildError>,
    ): VerificationKeyWitness = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }
}
