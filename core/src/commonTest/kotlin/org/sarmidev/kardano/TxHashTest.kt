package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs

class TxHashTest {

    @Test
    fun ofAcceptsExactSize() {
        val ok = assertIs<KardanoResult.Ok<TxHash>>(TxHash.of(ByteArray(TxHash.SIZE)))
        assertEquals(TxHash.SIZE, ok.value.toByteArray().size)
    }

    @Test
    fun ofRejectsWrongSizes() {
        for (size in listOf(0, 31, 33)) {
            val err = assertIs<KardanoResult.Err<ByteSizeError>>(TxHash.of(ByteArray(size)))
            assertEquals(ByteSizeError.Fixed(TxHash.SIZE, size), err.error)
        }
    }

    @Test
    fun constructionMakesDefensiveCopy() {
        val source = ByteArray(TxHash.SIZE) { 1 }
        val hash = assertIs<KardanoResult.Ok<TxHash>>(TxHash.of(source)).value
        source[0] = 9
        assertEquals(1.toByte(), hash.toByteArray()[0])
    }

    @Test
    fun accessorReturnsDefensiveCopy() {
        val hash = assertIs<KardanoResult.Ok<TxHash>>(TxHash.of(ByteArray(TxHash.SIZE) { 1 })).value
        val exposed = hash.toByteArray()
        exposed[0] = 9
        assertEquals(1.toByte(), hash.toByteArray()[0])
    }

    @Test
    fun equalContentIsEqual() {
        val a = assertIs<KardanoResult.Ok<TxHash>>(TxHash.of(ByteArray(TxHash.SIZE) { it.toByte() })).value
        val b = assertIs<KardanoResult.Ok<TxHash>>(TxHash.of(ByteArray(TxHash.SIZE) { it.toByte() })).value
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }

    @Test
    fun differentContentIsNotEqual() {
        val a = assertIs<KardanoResult.Ok<TxHash>>(TxHash.of(ByteArray(TxHash.SIZE) { 1 })).value
        val b = assertIs<KardanoResult.Ok<TxHash>>(TxHash.of(ByteArray(TxHash.SIZE) { 2 })).value
        assertFalse(a == b)
    }
}
