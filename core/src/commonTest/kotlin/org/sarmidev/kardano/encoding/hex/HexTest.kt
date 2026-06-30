package org.sarmidev.kardano.encoding.hex

import org.sarmidev.kardano.KardanoResult
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

class HexTest {

    @Test
    fun encodeEmptyReturnsEmptyString() {
        assertEquals("", Hex.encode(ByteArray(0)))
    }

    @Test
    fun encodeSingleBytesBoundaries() {
        assertEquals("00", Hex.encode(byteArrayOf(0x00)))
        assertEquals("0f", Hex.encode(byteArrayOf(0x0f)))
        assertEquals("10", Hex.encode(byteArrayOf(0x10)))
        assertEquals("ff", Hex.encode(byteArrayOf(0xff.toByte())))
    }

    @Test
    fun encodeMultiByteConcatenatesLowercase() {
        assertEquals("00102fff", Hex.encode(byteArrayOf(0x00, 0x10, 0x2f, 0xff.toByte())))
    }

    @Test
    fun encodeOutputIsLowercase() {
        val encoded = Hex.encode(byteArrayOf(0xab.toByte(), 0xcd.toByte(), 0xef.toByte()))
        assertEquals("abcdef", encoded)
        assertEquals(encoded.lowercase(), encoded)
    }

    @Test
    fun decodeEmptyReturnsEmptyBytes() {
        val ok = assertIs<KardanoResult.Ok<ByteArray>>(Hex.decode(""))
        assertEquals(0, ok.value.size)
    }

    @Test
    fun decodeLowercase() {
        val ok = assertIs<KardanoResult.Ok<ByteArray>>(Hex.decode("00102fff"))
        assertTrue(byteArrayOf(0x00, 0x10, 0x2f, 0xff.toByte()).contentEquals(ok.value))
    }

    @Test
    fun decodeUppercaseMatchesLowercase() {
        val ok = assertIs<KardanoResult.Ok<ByteArray>>(Hex.decode("ABCDEF"))
        assertTrue(byteArrayOf(0xab.toByte(), 0xcd.toByte(), 0xef.toByte()).contentEquals(ok.value))
    }

    @Test
    fun decodeMixedCaseMatchesLowercase() {
        val ok = assertIs<KardanoResult.Ok<ByteArray>>(Hex.decode("aBcDeF"))
        assertTrue(byteArrayOf(0xab.toByte(), 0xcd.toByte(), 0xef.toByte()).contentEquals(ok.value))
    }

    @Test
    fun decodeOddLengthRejected() {
        val err = assertIs<KardanoResult.Err<HexError>>(Hex.decode("abc"))
        assertEquals(HexError.OddLength(3), err.error)
    }

    @Test
    fun decodeInvalidCharacterRejectedWithIndexAndChar() {
        val err = assertIs<KardanoResult.Err<HexError>>(Hex.decode("0g"))
        assertEquals(HexError.InvalidCharacter(1, 'g'), err.error)
    }

    @Test
    fun decodeInvalidCharacterReportsFirstOccurrence() {
        val err = assertIs<KardanoResult.Err<HexError>>(Hex.decode("zz"))
        assertEquals(HexError.InvalidCharacter(0, 'z'), err.error)
    }

    @Test
    fun decodeInputExceedingMaxRejected() {
        val tooLong = "0".repeat(Hex.MAX_INPUT_CHARS + 1)
        val err = assertIs<KardanoResult.Err<HexError>>(Hex.decode(tooLong))
        assertEquals(HexError.InputTooLong(Hex.MAX_INPUT_CHARS, Hex.MAX_INPUT_CHARS + 1), err.error)
    }

    @Test
    fun roundTripDecodeOfEncode() {
        val samples = listOf(
            ByteArray(0),
            byteArrayOf(0x00),
            byteArrayOf(0xff.toByte()),
            byteArrayOf(0x00, 0x10, 0x2f, 0x80.toByte(), 0xff.toByte()),
        )
        for (sample in samples) {
            val ok = assertIs<KardanoResult.Ok<ByteArray>>(Hex.decode(Hex.encode(sample)))
            assertTrue(sample.contentEquals(ok.value))
        }
    }

    @Test
    fun encodeOfDecodeIsCanonicalLowercase() {
        val ok = assertIs<KardanoResult.Ok<ByteArray>>(Hex.decode("ABCDEF"))
        assertEquals("abcdef", Hex.encode(ok.value))
    }
}
