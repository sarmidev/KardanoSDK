package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

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

    @Test
    fun toStringDoesNotRenderBytes() {
        // Recognizable byte content (0xAB). The structural toString must not leak it.
        val hash = assertIs<KardanoResult.Ok<TxHash>>(
            TxHash.of(ByteArray(TxHash.SIZE) { 0xAB.toByte() }),
        ).value
        val text = hash.toString()
        assertTrue(text.contains("size="), "toString should keep a structural marker")
        assertFalse(
            text.contains(Hex.encode(hash.toByteArray())),
            "toString must not render the wrapped bytes",
        )
    }
}
