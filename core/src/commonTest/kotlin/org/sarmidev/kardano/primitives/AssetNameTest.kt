package org.sarmidev.kardano.primitives

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.hex.Hex
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

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

    @Test
    fun toStringDoesNotRenderBytes() {
        // Recognizable, non-empty byte content. The structural toString must not leak it.
        val assetName = assertIs<KardanoResult.Ok<AssetName>>(
            AssetName.of(byteArrayOf(0xAB.toByte(), 0xCD.toByte())),
        ).value
        val text = assetName.toString()
        assertTrue(text.contains("size="), "toString should keep a structural marker")
        assertFalse(
            text.contains(Hex.encode(assetName.toByteArray())),
            "toString must not render the wrapped bytes",
        )
    }
}
