package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs

class UtxoRefTest {

    private fun txHash(fill: Byte): TxHash =
        assertIs<KardanoResult.Ok<TxHash>>(TxHash.of(ByteArray(TxHash.SIZE) { fill })).value

    @Test
    fun ofAcceptsZeroIndex() {
        val ref = assertIs<KardanoResult.Ok<UtxoRef>>(UtxoRef.of(txHash(1), 0L)).value
        assertEquals(0L, ref.outputIndex)
    }

    @Test
    fun ofAcceptsPositiveAndMaxIndex() {
        for (index in listOf(1L, 42L, Long.MAX_VALUE)) {
            val ref = assertIs<KardanoResult.Ok<UtxoRef>>(UtxoRef.of(txHash(1), index)).value
            assertEquals(index, ref.outputIndex)
        }
    }

    @Test
    fun ofRejectsNegativeIndex() {
        for (index in listOf(-1L, Long.MIN_VALUE)) {
            val err = assertIs<KardanoResult.Err<UtxoRefError>>(UtxoRef.of(txHash(1), index))
            assertEquals(UtxoRefError.NegativeIndex(index), err.error)
        }
    }

    @Test
    fun equalHashAndIndexAreEqual() {
        val a = assertIs<KardanoResult.Ok<UtxoRef>>(UtxoRef.of(txHash(1), 7L)).value
        val b = assertIs<KardanoResult.Ok<UtxoRef>>(UtxoRef.of(txHash(1), 7L)).value
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }

    @Test
    fun differentIndexIsNotEqual() {
        val a = assertIs<KardanoResult.Ok<UtxoRef>>(UtxoRef.of(txHash(1), 7L)).value
        val b = assertIs<KardanoResult.Ok<UtxoRef>>(UtxoRef.of(txHash(1), 8L)).value
        assertFalse(a == b)
    }

    @Test
    fun differentHashIsNotEqual() {
        val a = assertIs<KardanoResult.Ok<UtxoRef>>(UtxoRef.of(txHash(1), 7L)).value
        val b = assertIs<KardanoResult.Ok<UtxoRef>>(UtxoRef.of(txHash(2), 7L)).value
        assertFalse(a == b)
    }
}
