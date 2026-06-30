package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Decoder tests for the Phase 0 CBOR subset.
 *
 * Positive examples are RFC 8949 Appendix A vectors copied verbatim
 * (https://www.rfc-editor.org/rfc/rfc8949#appendix-A). Malformed, non-canonical, over-limit,
 * unsupported, and trailing-byte cases are small hand-written parser edge cases; each is
 * commented with the rule it exercises and is not an official vector unless noted.
 */
class CborDecodeTest {

    // RFC 8949 Appendix A — unsigned integers (major type 0).
    @Test
    fun decodesAppendixAUnsignedIntegers() {
        val vectors = listOf(
            "00" to 0L,
            "01" to 1L,
            "0a" to 10L,
            "17" to 23L,
            "1818" to 24L,
            "1819" to 25L,
            "1864" to 100L,
            "1903e8" to 1000L,
            "1a000f4240" to 1000000L,
            "1b000000e8d4a51000" to 1000000000000L,
        )
        for ((hex, expected) in vectors) {
            assertEquals(CborValue.CborUnsigned(expected), decoded(hex), "vector $hex")
        }
    }

    // RFC 8949 Appendix A — negative integers (major type 1).
    @Test
    fun decodesAppendixANegativeIntegers() {
        val vectors = listOf(
            "20" to -1L,
            "29" to -10L,
            "3863" to -100L,
            "3903e7" to -1000L,
        )
        for ((hex, expected) in vectors) {
            assertEquals(CborValue.CborNegative(expected), decoded(hex), "vector $hex")
        }
    }

    // RFC 8949 Appendix A — byte strings (major type 2).
    @Test
    fun decodesAppendixAByteStrings() {
        assertEquals(CborValue.CborByteString(ByteArray(0)), decoded("40"))
        assertEquals(
            CborValue.CborByteString(byteArrayOf(1, 2, 3, 4)),
            decoded("4401020304"),
        )
    }

    // RFC 8949 Appendix A — text strings (major type 3).
    @Test
    fun decodesAppendixATextStrings() {
        val vectors = listOf(
            "60" to "",
            "6161" to "a",
            "6449455446" to "IETF",
            "62225c" to "\"\\",
            "62c3bc" to "\u00fc",
            "63e6b0b4" to "\u6c34",
            "64f0908591" to "\uD800\uDD51",
        )
        for ((hex, expected) in vectors) {
            assertEquals(CborValue.CborTextString(expected), decoded(hex), "vector $hex")
        }
    }

    // Hand-written boundary: 0x1b + 0x7fffffffffffffff is the largest in-range major-0 value.
    @Test
    fun decodesLongMaxValueUnsigned() {
        assertEquals(
            CborValue.CborUnsigned(Long.MAX_VALUE),
            decoded("1b7fffffffffffffff"),
        )
    }

    // Hand-written boundary: major-1 argument n = Long.MAX_VALUE encodes value -1 - n =
    // Long.MIN_VALUE, the most negative representable value.
    @Test
    fun decodesLongMinValueNegative() {
        assertEquals(
            CborValue.CborNegative(Long.MIN_VALUE),
            decoded("3b7fffffffffffffff"),
        )
    }

    // 0x1bffffffffffffffff is the RFC 8949 Appendix A vector for 18446744073709551615; the SDK
    // subset rejects it because it exceeds Long.MAX_VALUE. 0x1b8000000000000000 (2^63) is the
    // exact boundary just above the range (hand-written).
    @Test
    fun rejectsUnsignedUint64AboveLongMax() {
        assertEquals(CborError.IntegerOutOfRange(0), decodeError("1bffffffffffffffff"))
        assertEquals(CborError.IntegerOutOfRange(0), decodeError("1b8000000000000000"))
    }

    // 0x3bffffffffffffffff is the RFC 8949 Appendix A vector for -18446744073709551616; the SDK
    // subset rejects it because it is below Long.MIN_VALUE. 0x3b8000000000000000 (n = 2^63) is
    // the exact boundary just below the range (hand-written).
    @Test
    fun rejectsNegativeUint64AboveLongMax() {
        assertEquals(CborError.IntegerOutOfRange(1), decodeError("3bffffffffffffffff"))
        assertEquals(CborError.IntegerOutOfRange(1), decodeError("3b8000000000000000"))
    }

    @Test
    fun rejectsEmptyInput() {
        assertEquals(CborError.EmptyInput, assertIs<KardanoResult.Err<CborError>>(Cbor.decode(ByteArray(0))).error)
    }

    // Two unsigned zeros: the first is one complete item, the second is trailing.
    @Test
    fun rejectsTrailingBytes() {
        assertEquals(CborError.TrailingBytes(1, 2), decodeError("0000"))
    }

    // 0x18 needs one argument byte; 0x19ff needs two but only one is present.
    @Test
    fun rejectsTruncatedArgument() {
        assertIs<CborError.UnexpectedEndOfInput>(decodeError("18"))
        assertIs<CborError.UnexpectedEndOfInput>(decodeError("19ff"))
    }

    // Non-canonical integers: a value that fits a shorter head encoded in a longer one.
    @Test
    fun rejectsNonCanonicalInteger() {
        assertEquals(CborError.NonCanonicalInteger(24, 23L), decodeError("1817"))
        assertEquals(CborError.NonCanonicalInteger(25, 255L), decodeError("1900ff"))
        assertEquals(CborError.NonCanonicalInteger(26, 23L), decodeError("1a00000017"))
        assertEquals(CborError.NonCanonicalInteger(27, 23L), decodeError("1b0000000000000017"))
    }

    // Non-canonical byte-string length: length 23 encoded as a uint8 instead of in the head.
    @Test
    fun rejectsNonCanonicalLength() {
        assertEquals(CborError.NonCanonicalLength(24, 23L), decodeError("5817"))
    }

    // Additional info 28, 29, 30 are reserved by RFC 8949.
    @Test
    fun rejectsReservedAdditionalInfo() {
        assertEquals(CborError.ReservedAdditionalInfo(0, 28), decodeError("1c"))
        assertEquals(CborError.ReservedAdditionalInfo(0, 29), decodeError("1d"))
        assertEquals(CborError.ReservedAdditionalInfo(0, 30), decodeError("1e"))
    }

    // Additional info 31 requests an indefinite-length encoding, which the subset rejects.
    @Test
    fun rejectsIndefiniteLength() {
        assertEquals(CborError.IndefiniteLengthNotSupported(2), decodeError("5f"))
        assertEquals(CborError.IndefiniteLengthNotSupported(3), decodeError("7f"))
        assertEquals(CborError.IndefiniteLengthNotSupported(4), decodeError("9f"))
        assertEquals(CborError.IndefiniteLengthNotSupported(5), decodeError("bf"))
    }

    // RFC 8949 Appendix A — arrays (major type 4).
    @Test
    fun decodesAppendixAArrays() {
        assertEquals(arr(), decoded("80"))
        assertEquals(arr(u(1), u(2), u(3)), decoded("83010203"))
        assertEquals(
            arr(u(1), arr(u(2), u(3)), arr(u(4), u(5))),
            decoded("8301820203820405"),
        )
        assertEquals(
            arr(*LongArray(25) { (it + 1).toLong() }.map { u(it) }.toTypedArray()),
            decoded("98190102030405060708090a0b0c0d0e0f101112131415161718181819"),
        )
    }

    // RFC 8949 Appendix A — maps (major type 5). All Appendix A maps are in canonical key order.
    @Test
    fun decodesAppendixAMaps() {
        assertEquals(map(), decoded("a0"))
        assertEquals(map(entry(u(1), u(2)), entry(u(3), u(4))), decoded("a201020304"))
        assertEquals(
            map(entry(txt("a"), u(1)), entry(txt("b"), arr(u(2), u(3)))),
            decoded("a26161016162820203"),
        )
        assertEquals(
            arr(txt("a"), map(entry(txt("b"), txt("c")))),
            decoded("826161a161626163"),
        )
        assertEquals(
            map(
                entry(txt("a"), txt("A")),
                entry(txt("b"), txt("B")),
                entry(txt("c"), txt("C")),
                entry(txt("d"), txt("D")),
                entry(txt("e"), txt("E")),
            ),
            decoded("a56161614161626142616361436164614461656145"),
        )
    }

    // Hand-written: a declared array count above the named limit is rejected before any element
    // is read (only the head bytes are supplied here).
    @Test
    fun rejectsArrayOverCollectionLimit() {
        val count = Cbor.CBOR_MAX_COLLECTION_ELEMENTS + 1
        // 0x9a = major type 4, uint32 count follows.
        val head = byteArrayOf(
            0x9a.toByte(),
            ((count ushr 24) and 0xFF).toByte(),
            ((count ushr 16) and 0xFF).toByte(),
            ((count ushr 8) and 0xFF).toByte(),
            (count and 0xFF).toByte(),
        )
        assertEquals(
            CborError.CollectionTooLarge(Cbor.CBOR_MAX_COLLECTION_ELEMENTS, count.toLong()),
            assertIs<KardanoResult.Err<CborError>>(Cbor.decode(head)).error,
        )
    }

    // Hand-written: the same rule for a map entry count (0xba = major type 5, uint32 count).
    @Test
    fun rejectsMapOverCollectionLimit() {
        val count = Cbor.CBOR_MAX_COLLECTION_ELEMENTS + 1
        val head = byteArrayOf(
            0xba.toByte(),
            ((count ushr 24) and 0xFF).toByte(),
            ((count ushr 16) and 0xFF).toByte(),
            ((count ushr 8) and 0xFF).toByte(),
            (count and 0xFF).toByte(),
        )
        assertEquals(
            CborError.CollectionTooLarge(Cbor.CBOR_MAX_COLLECTION_ELEMENTS, count.toLong()),
            assertIs<KardanoResult.Err<CborError>>(Cbor.decode(head)).error,
        )
    }

    // Hand-written: nesting one level deeper than the limit is rejected. A chain of
    // CBOR_MAX_NESTING_DEPTH single-element arrays (0x81) wrapping a 0x00 is accepted; one more
    // 0x81 exceeds the limit at depth CBOR_MAX_NESTING_DEPTH + 1.
    @Test
    fun rejectsNestingDepthExceeded() {
        val atLimit = "81".repeat(Cbor.CBOR_MAX_NESTING_DEPTH) + "00"
        assertIs<KardanoResult.Ok<CborValue>>(Cbor.decode(bytes(atLimit)))
        val overLimit = "81".repeat(Cbor.CBOR_MAX_NESTING_DEPTH + 1) + "00"
        assertEquals(
            CborError.MaxNestingDepthExceeded(
                Cbor.CBOR_MAX_NESTING_DEPTH,
                Cbor.CBOR_MAX_NESTING_DEPTH + 1,
            ),
            decodeError(overLimit),
        )
    }

    // Indefinite-length arrays (0x9f) and maps (0xbf) are rejected even with a full body.
    @Test
    fun rejectsIndefiniteArraysAndMaps() {
        assertEquals(CborError.IndefiniteLengthNotSupported(4), decodeError("9f00ff"))
        assertEquals(CborError.IndefiniteLengthNotSupported(5), decodeError("bf616100ff"))
    }

    // Hand-written: map keys "b" then "a" are out of canonical (ascending) order.
    @Test
    fun rejectsNonCanonicalMapKeyOrder() {
        assertEquals(CborError.NonCanonicalMapKeyOrder(1), decodeError("a2616201616101"))
    }

    // Hand-written: a map with key 1 repeated ({1:0, 1:0}).
    @Test
    fun rejectsDuplicateMapKey() {
        assertEquals(CborError.DuplicateMapKey(1), decodeError("a201000100"))
    }

    // Hand-written: an unsupported child value inside a collection is rejected through the
    // normal child decode — a tag (0xc0) and a simple value (0xf5) inside a one-element array.
    @Test
    fun rejectsNestedUnsupportedValues() {
        assertEquals(CborError.TagsNotSupported, decodeError("81c000"))
        assertEquals(CborError.FloatOrSimpleNotSupported(21), decodeError("81f5"))
    }

    // Hand-written: an empty array (0x80) is one complete value; the trailing 0x00 is rejected.
    @Test
    fun rejectsTrailingBytesAfterCollection() {
        assertEquals(CborError.TrailingBytes(1, 2), decodeError("8000"))
    }

    // Hand-written: an array declaring three elements but supplying one runs out of input.
    @Test
    fun rejectsTruncatedArray() {
        assertIs<CborError.UnexpectedEndOfInput>(decodeError("8301"))
    }

    // Hand-written: an array count of 0 encoded as a uint8 (0x9800) is not the shortest form.
    @Test
    fun rejectsNonCanonicalCollectionCount() {
        assertEquals(CborError.NonCanonicalLength(24, 0L), decodeError("9800"))
    }

    // Tags (major 6), including bignum tags 2 and 3, are out of scope for Phase 0.
    @Test
    fun rejectsTags() {
        assertEquals(CborError.TagsNotSupported, decodeError("c0"))
        assertEquals(CborError.TagsNotSupported, decodeError("c2"))
        assertEquals(CborError.TagsNotSupported, decodeError("c3"))
    }

    // Floats and simple values (major 7) are out of scope for Phase 0.
    @Test
    fun rejectsFloatsAndSimpleValues() {
        assertEquals(CborError.FloatOrSimpleNotSupported(20), decodeError("f4")) // false
        assertEquals(CborError.FloatOrSimpleNotSupported(21), decodeError("f5")) // true
        assertEquals(CborError.FloatOrSimpleNotSupported(22), decodeError("f6")) // null
        assertEquals(CborError.FloatOrSimpleNotSupported(23), decodeError("f7")) // undefined
        assertEquals(CborError.FloatOrSimpleNotSupported(26), decodeError("fa47c35000")) // float32
        assertEquals(CborError.FloatOrSimpleNotSupported(27), decodeError("fb3ff199999999999a")) // float64
    }

    // A byte string declaring four payload bytes but providing one: the declared length is
    // validated against the remaining bytes before any buffer is allocated.
    @Test
    fun rejectsDeclaredLengthExceedingInput() {
        assertEquals(CborError.DeclaredLengthExceedsInput(4L, 1), decodeError("4401"))
    }

    // Hand-written: a byte-string length encoded as a uint64 with bit 63 set is outside the
    // supported signed Long range. It is rejected as LengthOutOfRange, not reinterpreted as a
    // negative declared length. 0x5b8000000000000000 (2^63) is the boundary; 0x5bffffffffffffffff
    // (2^64 - 1) is the maximum uint64.
    @Test
    fun rejectsByteStringLengthAboveLongMax() {
        assertEquals(CborError.LengthOutOfRange(2), decodeError("5b8000000000000000"))
        assertEquals(CborError.LengthOutOfRange(2), decodeError("5bffffffffffffffff"))
    }

    // Hand-written: the same rule for a text-string length prefix (major type 3).
    @Test
    fun rejectsTextStringLengthAboveLongMax() {
        assertEquals(CborError.LengthOutOfRange(3), decodeError("7b8000000000000000"))
        assertEquals(CborError.LengthOutOfRange(3), decodeError("7bffffffffffffffff"))
    }

    // A byte string whose declared length (with full payload present) exceeds the named limit.
    @Test
    fun rejectsByteStringOverNamedLimit() {
        val length = Cbor.CBOR_MAX_BYTESTRING_BYTES + 1
        val input = ByteArray(5 + length)
        input[0] = 0x5a.toByte() // major type 2, uint32 length follows
        input[1] = ((length ushr 24) and 0xFF).toByte()
        input[2] = ((length ushr 16) and 0xFF).toByte()
        input[3] = ((length ushr 8) and 0xFF).toByte()
        input[4] = (length and 0xFF).toByte()
        val error = assertIs<KardanoResult.Err<CborError>>(Cbor.decode(input)).error
        assertEquals(CborError.ByteStringTooLong(Cbor.CBOR_MAX_BYTESTRING_BYTES, length.toLong()), error)
    }

    // A text string whose declared length (with full payload present) exceeds the named limit.
    @Test
    fun rejectsTextStringOverNamedLimit() {
        val length = Cbor.CBOR_MAX_STRING_BYTES + 1
        val input = ByteArray(5 + length)
        input[0] = 0x7a.toByte() // major type 3, uint32 length follows
        input[1] = ((length ushr 24) and 0xFF).toByte()
        input[2] = ((length ushr 16) and 0xFF).toByte()
        input[3] = ((length ushr 8) and 0xFF).toByte()
        input[4] = (length and 0xFF).toByte()
        for (i in 5 until input.size) {
            input[i] = 0x61 // ASCII 'a', valid UTF-8, so the limit check is what rejects it
        }
        val error = assertIs<KardanoResult.Err<CborError>>(Cbor.decode(input)).error
        assertEquals(CborError.TextStringTooLong(Cbor.CBOR_MAX_STRING_BYTES, length.toLong()), error)
    }

    // 0x61 declares a one-byte text string; 0xff is not valid UTF-8.
    @Test
    fun rejectsInvalidUtf8() {
        assertEquals(CborError.InvalidUtf8, decodeError("61ff"))
    }

    @Test
    fun decodedByteStringIsDefensivelyCopied() {
        val value = assertIs<CborValue.CborByteString>(decoded("4401020304"))
        val exposed = value.toByteArray()
        exposed[0] = 9
        assertTrue(value.toByteArray()[0] == 1.toByte(), "accessor must return a copy")
    }

    private fun decoded(hex: String): CborValue {
        val result = Cbor.decode(bytes(hex))
        return assertIs<KardanoResult.Ok<CborValue>>(result).value
    }

    private fun decodeError(hex: String): CborError {
        val result = Cbor.decode(bytes(hex))
        return assertIs<KardanoResult.Err<CborError>>(result).error
    }

    private fun u(value: Long): CborValue.CborUnsigned = CborValue.CborUnsigned(value)
    private fun txt(value: String): CborValue.CborTextString = CborValue.CborTextString(value)
    private fun arr(vararg items: CborValue): CborValue.CborArray =
        CborValue.CborArray(items.toList())
    private fun entry(key: CborValue, value: CborValue): CborValue.CborEntry =
        CborValue.CborEntry(key, value)
    private fun map(vararg entries: CborValue.CborEntry): CborValue.CborMap =
        CborValue.CborMap(entries.toList())
}

/** Decodes a hex string into bytes using the SDK's own (separately tested) [Hex] codec. */
internal fun bytes(hex: String): ByteArray =
    assertIs<KardanoResult.Ok<ByteArray>>(Hex.decode(hex)).value
