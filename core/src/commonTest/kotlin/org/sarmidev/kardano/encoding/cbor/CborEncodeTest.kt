package org.sarmidev.kardano.encoding.cbor

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.hex.Hex
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Encoder and round-trip tests for the Phase 0 CBOR subset.
 *
 * Positive examples assert canonical output equal to RFC 8949 Appendix A vectors copied
 * verbatim (https://www.rfc-editor.org/rfc/rfc8949#appendix-A). Boundary and rejection cases
 * are hand-written and commented with the rule they exercise.
 */
class CborEncodeTest {

    // RFC 8949 Appendix A — unsigned integers encode to their canonical (shortest) form.
    @Test
    fun encodesAppendixAUnsignedIntegers() {
        val vectors = listOf(
            0L to "00",
            1L to "01",
            10L to "0a",
            23L to "17",
            24L to "1818",
            25L to "1819",
            100L to "1864",
            1000L to "1903e8",
            1000000L to "1a000f4240",
            1000000000000L to "1b000000e8d4a51000",
        )
        for ((value, hex) in vectors) {
            assertEncodes(CborValue.CborUnsigned(value), hex)
        }
    }

    // RFC 8949 Appendix A — negative integers.
    @Test
    fun encodesAppendixANegativeIntegers() {
        val vectors = listOf(
            -1L to "20",
            -10L to "29",
            -100L to "3863",
            -1000L to "3903e7",
        )
        for ((value, hex) in vectors) {
            assertEncodes(CborValue.CborNegative(value), hex)
        }
    }

    // RFC 8949 Appendix A — byte strings.
    @Test
    fun encodesAppendixAByteStrings() {
        assertEncodes(CborValue.CborByteString(ByteArray(0)), "40")
        assertEncodes(CborValue.CborByteString(byteArrayOf(1, 2, 3, 4)), "4401020304")
    }

    // RFC 8949 Appendix A — text strings.
    @Test
    fun encodesAppendixATextStrings() {
        val vectors = listOf(
            "" to "60",
            "a" to "6161",
            "IETF" to "6449455446",
            "\"\\" to "62225c",
            "\u00fc" to "62c3bc",
            "\u6c34" to "63e6b0b4",
            "\uD800\uDD51" to "64f0908591",
        )
        for ((value, hex) in vectors) {
            assertEncodes(CborValue.CborTextString(value), hex)
        }
    }

    // Hand-written boundary: Long.MAX_VALUE is not an Appendix A vector; the expected bytes are
    // 0x1b followed by 0x7fffffffffffffff (2^63 - 1).
    @Test
    fun encodesLongMaxValueUnsigned() {
        assertEncodes(CborValue.CborUnsigned(Long.MAX_VALUE), "1b7fffffffffffffff")
    }

    // Hand-written boundary: Long.MIN_VALUE encodes major-1 argument n = Long.MAX_VALUE.
    @Test
    fun encodesLongMinValueNegative() {
        assertEncodes(CborValue.CborNegative(Long.MIN_VALUE), "3b7fffffffffffffff")
    }

    @Test
    fun roundTripsSupportedValues() {
        val values = listOf(
            CborValue.CborUnsigned(0L),
            CborValue.CborUnsigned(24L),
            CborValue.CborUnsigned(1000000000000L),
            CborValue.CborUnsigned(Long.MAX_VALUE),
            CborValue.CborNegative(-1L),
            CborValue.CborNegative(-1000L),
            CborValue.CborNegative(Long.MIN_VALUE),
            CborValue.CborByteString(byteArrayOf(1, 2, 3, 4)),
            CborValue.CborByteString(ByteArray(0)),
            CborValue.CborTextString("IETF"),
            CborValue.CborTextString("\u6c34"),
        )
        for (value in values) {
            val encoded = assertIs<KardanoResult.Ok<ByteArray>>(Cbor.encode(value)).value
            val decoded = assertIs<KardanoResult.Ok<CborValue>>(Cbor.decode(encoded)).value
            assertEquals(value, decoded, "round-trip for $value")
        }
    }

    // RFC 8949 Appendix A — arrays encode to their canonical definite-length form.
    @Test
    fun encodesAppendixAArrays() {
        assertEncodes(arr(), "80")
        assertEncodes(arr(u(1), u(2), u(3)), "83010203")
        assertEncodes(arr(u(1), arr(u(2), u(3)), arr(u(4), u(5))), "8301820203820405")
        assertEncodes(
            arr(*LongArray(25) { (it + 1).toLong() }.map { u(it) }.toTypedArray()),
            "98190102030405060708090a0b0c0d0e0f101112131415161718181819",
        )
    }

    // RFC 8949 Appendix A — maps (supplied in canonical key order) encode to their exact bytes.
    @Test
    fun encodesAppendixAMaps() {
        assertEncodes(map(), "a0")
        assertEncodes(map(entry(u(1), u(2)), entry(u(3), u(4))), "a201020304")
        assertEncodes(
            map(entry(txt("a"), u(1)), entry(txt("b"), arr(u(2), u(3)))),
            "a26161016162820203",
        )
        assertEncodes(arr(txt("a"), map(entry(txt("b"), txt("c")))), "826161a161626163")
        assertEncodes(
            map(
                entry(txt("a"), txt("A")),
                entry(txt("b"), txt("B")),
                entry(txt("c"), txt("C")),
                entry(txt("d"), txt("D")),
                entry(txt("e"), txt("E")),
            ),
            "a56161614161626142616361436164614461656145",
        )
    }

    @Test
    fun roundTripsCollections() {
        val values = listOf(
            arr(),
            arr(u(1), arr(u(2), u(3)), arr(u(4), u(5))),
            map(),
            map(entry(u(1), u(2)), entry(u(3), u(4))),
            map(entry(txt("a"), u(1)), entry(txt("b"), arr(u(2), u(3)))),
        )
        for (value in values) {
            val encoded = assertIs<KardanoResult.Ok<ByteArray>>(Cbor.encode(value)).value
            val decoded = assertIs<KardanoResult.Ok<CborValue>>(Cbor.decode(encoded)).value
            assertEquals(value, decoded, "round-trip for $value")
        }
    }

    @Test
    fun rejectsArrayOverCollectionLimit() {
        val items = List<CborValue>(Cbor.CBOR_MAX_COLLECTION_ELEMENTS + 1) { u(0) }
        val error = assertIs<KardanoResult.Err<CborError>>(
            Cbor.encode(CborValue.CborArray(items)),
        ).error
        assertEquals(
            CborError.CollectionTooLarge(Cbor.CBOR_MAX_COLLECTION_ELEMENTS, items.size.toLong()),
            error,
        )
    }

    // Nesting one array deeper than the limit is rejected; exactly at the limit is accepted.
    @Test
    fun rejectsNestingDepthExceeded() {
        var atLimit: CborValue = u(0)
        repeat(Cbor.CBOR_MAX_NESTING_DEPTH) { atLimit = arr(atLimit) }
        assertIs<KardanoResult.Ok<ByteArray>>(Cbor.encode(atLimit))

        var overLimit: CborValue = u(0)
        repeat(Cbor.CBOR_MAX_NESTING_DEPTH + 1) { overLimit = arr(overLimit) }
        assertEquals(
            CborError.MaxNestingDepthExceeded(
                Cbor.CBOR_MAX_NESTING_DEPTH,
                Cbor.CBOR_MAX_NESTING_DEPTH + 1,
            ),
            assertIs<KardanoResult.Err<CborError>>(Cbor.encode(overLimit)).error,
        )
    }

    // The encoder rejects non-canonical key order; it does not sort.
    @Test
    fun rejectsNonCanonicalMapKeyOrderOnEncode() {
        val outOfOrder = map(entry(txt("b"), u(1)), entry(txt("a"), u(1)))
        assertEquals(
            CborError.NonCanonicalMapKeyOrder(1),
            assertIs<KardanoResult.Err<CborError>>(Cbor.encode(outOfOrder)).error,
        )
    }

    // Explicit "no silent sorting": a map whose keys are out of canonical order is rejected,
    // never re-emitted as valid, reordered bytes.
    @Test
    fun doesNotSilentlySortMapEntries() {
        val outOfOrder = map(entry(u(3), u(4)), entry(u(1), u(2)))
        val result = Cbor.encode(outOfOrder)
        assertIs<KardanoResult.Err<CborError>>(result)
        assertEquals(CborError.NonCanonicalMapKeyOrder(1), (result).error)
    }

    @Test
    fun rejectsDuplicateMapKeyOnEncode() {
        val duplicate = map(entry(u(1), u(2)), entry(u(1), u(3)))
        assertEquals(
            CborError.DuplicateMapKey(1),
            assertIs<KardanoResult.Err<CborError>>(Cbor.encode(duplicate)).error,
        )
    }

    @Test
    fun rejectsUnsignedWithNegativeValue() {
        val error = assertIs<KardanoResult.Err<CborError>>(
            Cbor.encode(CborValue.CborUnsigned(-1L)),
        ).error
        assertEquals(CborError.UnsignedValueNegative(-1L), error)
    }

    @Test
    fun rejectsNegativeWithNonNegativeValue() {
        val error = assertIs<KardanoResult.Err<CborError>>(
            Cbor.encode(CborValue.CborNegative(0L)),
        ).error
        assertEquals(CborError.NegativeValueNonNegative(0L), error)
    }

    @Test
    fun rejectsByteStringOverNamedLimit() {
        val length = Cbor.CBOR_MAX_BYTESTRING_BYTES + 1
        val error = assertIs<KardanoResult.Err<CborError>>(
            Cbor.encode(CborValue.CborByteString(ByteArray(length))),
        ).error
        assertEquals(CborError.ByteStringTooLong(Cbor.CBOR_MAX_BYTESTRING_BYTES, length.toLong()), error)
    }

    @Test
    fun rejectsTextStringOverNamedLimit() {
        val length = Cbor.CBOR_MAX_STRING_BYTES + 1
        val error = assertIs<KardanoResult.Err<CborError>>(
            Cbor.encode(CborValue.CborTextString("a".repeat(length))),
        ).error
        assertEquals(CborError.TextStringTooLong(Cbor.CBOR_MAX_STRING_BYTES, length.toLong()), error)
    }

    // A lone high surrogate is not valid UTF-8 and must be rejected, not substituted.
    @Test
    fun rejectsInvalidUtf8Text() {
        val error = assertIs<KardanoResult.Err<CborError>>(
            Cbor.encode(CborValue.CborTextString("\uD800")),
        ).error
        assertEquals(CborError.InvalidUtf8, error)
    }

    @Test
    fun byteStringMakesDefensiveCopyOnConstruction() {
        val source = byteArrayOf(1, 2, 3, 4)
        val value = CborValue.CborByteString(source)
        source[0] = 9
        assertTrue(value.toByteArray()[0] == 1.toByte(), "construction must copy the source")
    }

    @Test
    fun byteStringValueEquality() {
        val a = CborValue.CborByteString(byteArrayOf(1, 2, 3))
        val b = CborValue.CborByteString(byteArrayOf(1, 2, 3))
        val c = CborValue.CborByteString(byteArrayOf(1, 2, 4))
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
        assertTrue(a != c)
    }

    @Test
    fun byteStringToStringDoesNotRenderBytes() {
        // Recognizable, non-empty byte content. The structural toString must not leak it.
        val value = CborValue.CborByteString(byteArrayOf(0xAB.toByte(), 0xCD.toByte()))
        val text = value.toString()
        assertTrue(text.contains("size="), "toString should keep a structural marker")
        assertFalse(
            text.contains(Hex.encode(value.toByteArray())),
            "toString must not render the wrapped bytes",
        )
    }

    @Test
    fun arrayMakesDefensiveCopyOnConstruction() {
        val source = mutableListOf<CborValue>(u(1), u(2))
        val array = CborValue.CborArray(source)
        source.add(u(3))
        assertEquals(2, array.items().size, "construction must snapshot the source list")
    }

    @Test
    fun arrayAccessorReturnsIndependentCopy() {
        val array = arr(u(1), u(2))
        val exposed = array.items()
        @Suppress("UNCHECKED_CAST")
        (exposed as MutableList<CborValue>).clear()
        assertEquals(2, array.items().size, "accessor must return a copy, not internal storage")
    }

    @Test
    fun arrayValueEquality() {
        val a = arr(u(1), arr(u(2)))
        val b = arr(u(1), arr(u(2)))
        val c = arr(u(1), arr(u(3)))
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
        assertTrue(a != c)
    }

    @Test
    fun arrayToStringDoesNotRenderElements() {
        val array = arr(u(123456789), txt("secret-marker"))
        val text = array.toString()
        assertTrue(text.contains("size="), "toString should keep a structural marker")
        assertFalse(text.contains("123456789"), "toString must not render elements")
        assertFalse(text.contains("secret-marker"), "toString must not render elements")
    }

    @Test
    fun mapMakesDefensiveCopyOnConstruction() {
        val source = mutableListOf(entry(u(1), u(2)))
        val cborMap = CborValue.CborMap(source)
        source.add(entry(u(3), u(4)))
        assertEquals(1, cborMap.entries().size, "construction must snapshot the source list")
    }

    @Test
    fun mapAccessorReturnsIndependentCopy() {
        val cborMap = map(entry(u(1), u(2)), entry(u(3), u(4)))
        val exposed = cborMap.entries()
        @Suppress("UNCHECKED_CAST")
        (exposed as MutableList<CborValue.CborEntry>).clear()
        assertEquals(2, cborMap.entries().size, "accessor must return a copy, not internal storage")
    }

    @Test
    fun mapValueEquality() {
        val a = map(entry(u(1), u(2)), entry(u(3), u(4)))
        val b = map(entry(u(1), u(2)), entry(u(3), u(4)))
        val c = map(entry(u(1), u(2)), entry(u(3), u(5)))
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
        assertTrue(a != c)
    }

    @Test
    fun mapToStringDoesNotRenderEntries() {
        val cborMap = map(entry(txt("secret-key"), u(987654321)))
        val text = cborMap.toString()
        assertTrue(text.contains("size="), "toString should keep a structural marker")
        assertFalse(text.contains("secret-key"), "toString must not render entries")
        assertFalse(text.contains("987654321"), "toString must not render entries")
    }

    private fun assertEncodes(value: CborValue, expectedHex: String) {
        val encoded = assertIs<KardanoResult.Ok<ByteArray>>(Cbor.encode(value)).value
        assertTrue(
            encoded.contentEquals(bytes(expectedHex)),
            "expected $expectedHex but got ${Hex.encode(encoded)}",
        )
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
