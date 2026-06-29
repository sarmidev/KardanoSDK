package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs

class AssetNameTest {

    @Test
    fun ofAcceptsLengthsInRange() {
        for (size in listOf(0, 1, AssetName.MAX_SIZE)) {
            val ok = assertIs<KardanoResult.Ok<AssetName>>(AssetName.of(ByteArray(size)))
            assertEquals(size, ok.value.toByteArray().size)
        }
    }

    @Test
    fun ofRejectsLengthAboveMax() {
        val size = AssetName.MAX_SIZE + 1
        val err = assertIs<KardanoResult.Err<ByteSizeError>>(AssetName.of(ByteArray(size)))
        assertEquals(ByteSizeError.Range(AssetName.MIN_SIZE, AssetName.MAX_SIZE, size), err.error)
    }

    @Test
    fun constructionMakesDefensiveCopy() {
        val source = ByteArray(4) { 1 }
        val assetName = assertIs<KardanoResult.Ok<AssetName>>(AssetName.of(source)).value
        source[0] = 9
        assertEquals(1.toByte(), assetName.toByteArray()[0])
    }

    @Test
    fun accessorReturnsDefensiveCopy() {
        val assetName = assertIs<KardanoResult.Ok<AssetName>>(AssetName.of(ByteArray(4) { 1 })).value
        val exposed = assetName.toByteArray()
        exposed[0] = 9
        assertEquals(1.toByte(), assetName.toByteArray()[0])
    }

    @Test
    fun equalContentIsEqual() {
        val a = assertIs<KardanoResult.Ok<AssetName>>(AssetName.of(byteArrayOf(1, 2, 3))).value
        val b = assertIs<KardanoResult.Ok<AssetName>>(AssetName.of(byteArrayOf(1, 2, 3))).value
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }

    @Test
    fun emptyNamesAreEqual() {
        val a = assertIs<KardanoResult.Ok<AssetName>>(AssetName.of(ByteArray(0))).value
        val b = assertIs<KardanoResult.Ok<AssetName>>(AssetName.of(ByteArray(0))).value
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }

    @Test
    fun differentContentIsNotEqual() {
        val a = assertIs<KardanoResult.Ok<AssetName>>(AssetName.of(byteArrayOf(1, 2, 3))).value
        val b = assertIs<KardanoResult.Ok<AssetName>>(AssetName.of(byteArrayOf(1, 2, 4))).value
        assertFalse(a == b)
    }
}
