package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

class Bech32Test {

    // Valid Bech32 strings, copied verbatim from BIP-173.
    // Source: https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki (Test vectors)
    private val bip173Valid = listOf(
        "A12UEL5L",
        "a12uel5l",
        "an83characterlonghumanreadablepartthatcontainsthenumber1andtheexcludedcharactersbio1tt5tgs",
        "abcdef1qpzry9x8gf2tvdw0s3jn54khce6mua7lmqqqxw",
        "11qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqc8247j",
        "split1checkupstagehandshakeupstreamerranterredcaperred2y9e3w",
        "?1ezyfcl",
    )

    // Invalid Bech32 strings (with the spec's reason), copied verbatim from BIP-173.
    // Control-character HRP prefixes are written with \u escapes.
    // Source: https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki (Test vectors)
    private val bip173Invalid = listOf(
        "\u00201nwldj5", // 0x20 + 1nwldj5: HRP character out of range
        "\u007F1axkwrx", // 0x7F + 1axkwrx: HRP character out of range
        "\u00801eym55h", // 0x80 + 1eym55h: HRP character out of range
        // overall max length exceeded (the HRP is 84 chars; rejected by the SDK HRP-length
        // limit, which matches BIP-173's 83-char HRP maximum — NOT by BIP-173's 90-char
        // overall cap, which ADR-0001 says not to apply to Cardano-mode APIs).
        "an84characterslonghumanreadablepartthatcontainsthenumber1andtheexcludedcharactersbio1569pvx",
        "pzry9x0s0muk", // No separator character
        "1pzry9x0s0muk", // Empty HRP
        "x1b4n0q5v", // Invalid data character
        "li1dgmt3", // Too short checksum
        "de1lg7wt\u00FF", // de1lg7wt + 0xFF: Invalid character in checksum
        "A1G7SGD8", // checksum calculated with uppercase form of HRP
        "10a06t8", // empty HRP
        "1qzzfhee", // empty HRP
    )

    // Valid Bech32m strings, copied verbatim from BIP-350.
    // Source: https://github.com/bitcoin/bips/blob/master/bip-0350.mediawiki (Test vectors)
    private val bip350Valid = listOf(
        "A1LQFN3A",
        "a1lqfn3a",
        "an83characterlonghumanreadablepartthatcontainsthetheexcludedcharactersbioandnumber11sg7hg6",
        "abcdef1l7aum6echk45nj3s0wdvt2fg8x9yrzpqzd3ryx",
        "11llllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllludsr8",
        "split1checkupstagehandshakeupstreamerranterredcaperredlc445v",
        "?1v759aa",
    )

    // Invalid Bech32m strings (with the spec's reason), copied verbatim from BIP-350.
    // Source: https://github.com/bitcoin/bips/blob/master/bip-0350.mediawiki (Test vectors)
    private val bip350Invalid = listOf(
        "\u00201xj0phk", // 0x20 + 1xj0phk: HRP character out of range
        "\u007F1g6xzxy", // 0x7F + 1g6xzxy: HRP character out of range
        "\u00801vctc34", // 0x80 + 1vctc34: HRP character out of range
        // overall max length exceeded; rejected by the SDK HRP-length limit (see BIP-173 note).
        "an84characterslonghumanreadablepartthatcontainsthetheexcludedcharactersbioandnumber11d6pts4",
        "qyrz8wqd2c9m", // No separator character
        "1qyrz8wqd2c9m", // Empty HRP
        "y1b0jsk6g", // Invalid data character
        "lt1igcx5c0", // Invalid data character
        "in1muywd", // Too short checksum
        "mm1crxm3i", // Invalid character in checksum
        "au1s5cgom", // Invalid character in checksum
        "M1VUXWEZ", // checksum calculated with uppercase form of HRP
        "16plkw9", // empty HRP
        "1p2gdwpf", // empty HRP
    )

    private fun assertValid(input: String, expected: Bech32Variant) {
        val decoded = assertIs<KardanoResult.Ok<Bech32Decoded>>(
            Bech32.decode(input),
            "decode($input) should succeed",
        )
        assertEquals(expected, decoded.value.variant, "variant for $input")
        val reEncoded = assertIs<KardanoResult.Ok<String>>(
            Bech32.encode(decoded.value.hrp, decoded.value.toData5BitArray(), decoded.value.variant),
            "encode for $input should succeed",
        )
        assertEquals(input.lowercase(), reEncoded.value, "re-encode for $input is canonical lowercase")
    }

    private fun assertInvalid(input: String) {
        assertIs<KardanoResult.Err<Bech32Error>>(
            Bech32.decode(input),
            "decode($input) should be rejected",
        )
    }

    @Test
    fun bip173ValidVectorsDecodeAsBech32AndReEncodeLowercase() {
        for (input in bip173Valid) assertValid(input, Bech32Variant.BECH32)
    }

    @Test
    fun bip350ValidVectorsDecodeAsBech32mAndReEncodeLowercase() {
        for (input in bip350Valid) assertValid(input, Bech32Variant.BECH32M)
    }

    @Test
    fun bip173InvalidVectorsRejected() {
        for (input in bip173Invalid) assertInvalid(input)
    }

    @Test
    fun bip350InvalidVectorsRejected() {
        for (input in bip350Invalid) assertInvalid(input)
    }

    @Test
    fun mixedCaseRejected() {
        // A valid lowercase string with one upper-case data character makes the input mixed case.
        val err = assertIs<KardanoResult.Err<Bech32Error>>(Bech32.decode("a12uEl5l"))
        assertEquals(Bech32Error.MixedCase, err.error)
    }

    @Test
    fun invalidHrpCharacterRejected() {
        val err = assertIs<KardanoResult.Err<Bech32Error>>(Bech32.decode("\u00201nwldj5"))
        assertEquals(Bech32Error.HrpCharOutOfRange(0, ' '), err.error)
    }

    @Test
    fun missingSeparatorRejected() {
        val err = assertIs<KardanoResult.Err<Bech32Error>>(Bech32.decode("pzry9x0s0muk"))
        assertEquals(Bech32Error.MissingSeparator, err.error)
    }

    @Test
    fun emptyHrpRejected() {
        val err = assertIs<KardanoResult.Err<Bech32Error>>(Bech32.decode("1qzzfhee"))
        assertEquals(Bech32Error.EmptyHrp, err.error)
    }

    @Test
    fun dataPartTooShortRejected() {
        // "li1dgmt3": only five data characters after the separator, fewer than the six-symbol checksum.
        val err = assertIs<KardanoResult.Err<Bech32Error>>(Bech32.decode("li1dgmt3"))
        assertEquals(Bech32Error.DataPartTooShort(5), err.error)
    }

    @Test
    fun invalidDataCharacterRejected() {
        // "x1b4n0q5v": 'b' is not part of the Bech32 alphabet; it sits at index 2 of the input.
        val err = assertIs<KardanoResult.Err<Bech32Error>>(Bech32.decode("x1b4n0q5v"))
        assertEquals(Bech32Error.InvalidDataCharacter(2, 'b'), err.error)
    }

    @Test
    fun checksumMismatchRejected() {
        // "A1G7SGD8": uniform case (accepted) but its checksum was computed over the uppercase HRP.
        val err = assertIs<KardanoResult.Err<Bech32Error>>(Bech32.decode("A1G7SGD8"))
        assertEquals(Bech32Error.InvalidChecksum, err.error)
    }

    @Test
    fun variantIsDetectedPerString() {
        // No string is valid under both variants, so detection must distinguish them.
        val asBech32 = assertIs<KardanoResult.Ok<Bech32Decoded>>(Bech32.decode("A12UEL5L"))
        assertEquals(Bech32Variant.BECH32, asBech32.value.variant)
        val asBech32m = assertIs<KardanoResult.Ok<Bech32Decoded>>(Bech32.decode("A1LQFN3A"))
        assertEquals(Bech32Variant.BECH32M, asBech32m.value.variant)
    }

    @Test
    fun encodeRejectsDataValueOutOfRange() {
        val aboveRange = assertIs<KardanoResult.Err<Bech32Error>>(
            Bech32.encode("a", byteArrayOf(32), Bech32Variant.BECH32),
        )
        assertEquals(Bech32Error.DataValueOutOfRange(0, 32), aboveRange.error)

        val negative = assertIs<KardanoResult.Err<Bech32Error>>(
            Bech32.encode("a", byteArrayOf(0xFF.toByte()), Bech32Variant.BECH32),
        )
        assertEquals(Bech32Error.DataValueOutOfRange(0, -1), negative.error)
    }

    @Test
    fun encodeRejectsEmptyHrp() {
        val err = assertIs<KardanoResult.Err<Bech32Error>>(
            Bech32.encode("", ByteArray(0), Bech32Variant.BECH32),
        )
        assertEquals(Bech32Error.EmptyHrp, err.error)
    }

    @Test
    fun encodeRejectsHrpTooLong() {
        val hrp = "a".repeat(Bech32.MAX_HRP_CHARS + 1)
        val err = assertIs<KardanoResult.Err<Bech32Error>>(
            Bech32.encode(hrp, ByteArray(0), Bech32Variant.BECH32),
        )
        assertEquals(Bech32Error.HrpTooLong(Bech32.MAX_HRP_CHARS, Bech32.MAX_HRP_CHARS + 1), err.error)
    }

    @Test
    fun encodeRejectsDataValuesTooLong() {
        val data = ByteArray(Bech32.MAX_DATA_VALUES + 1)
        val err = assertIs<KardanoResult.Err<Bech32Error>>(
            Bech32.encode("a", data, Bech32Variant.BECH32),
        )
        assertEquals(
            Bech32Error.DataValuesTooLong(Bech32.MAX_DATA_VALUES, Bech32.MAX_DATA_VALUES + 1),
            err.error,
        )
    }

    @Test
    fun decodeRejectsInputTooLong() {
        // A synthetic in-charset string longer than the SDK limit (not a protocol vector).
        val input = "a1" + "q".repeat(Bech32.MAX_INPUT_CHARS)
        val err = assertIs<KardanoResult.Err<Bech32Error>>(Bech32.decode(input))
        assertEquals(Bech32Error.InputTooLong(Bech32.MAX_INPUT_CHARS, input.length), err.error)
    }

    @Test
    fun decodeRejectsHrpTooLong() {
        // A synthetic over-limit HRP (not a protocol vector); rejected before checksum.
        val input = "a".repeat(Bech32.MAX_HRP_CHARS + 1) + "1qqqqqq"
        val err = assertIs<KardanoResult.Err<Bech32Error>>(Bech32.decode(input))
        assertEquals(Bech32Error.HrpTooLong(Bech32.MAX_HRP_CHARS, Bech32.MAX_HRP_CHARS + 1), err.error)
    }

    @Test
    fun roundTripBech32LayerPreservesHrpDataAndVariant() {
        // Representative non-protocol 5-bit data arrays.
        val samples = listOf(
            ByteArray(0),
            byteArrayOf(0, 1, 2, 31),
            byteArrayOf(31, 0, 17, 5, 9, 30, 12),
        )
        for (variant in Bech32Variant.entries) {
            for (data in samples) {
                val encoded = assertIs<KardanoResult.Ok<String>>(
                    Bech32.encode("kardano", data, variant),
                )
                val decoded = assertIs<KardanoResult.Ok<Bech32Decoded>>(
                    Bech32.decode(encoded.value),
                )
                assertEquals("kardano", decoded.value.hrp)
                assertEquals(variant, decoded.value.variant)
                assertTrue(data.contentEquals(decoded.value.toData5BitArray()))
            }
        }
    }

    @Test
    fun convertBitsRoundTrip8To5To8() {
        // Representative non-protocol 8-bit byte arrays.
        val samples = listOf(
            ByteArray(0),
            byteArrayOf(0x00),
            byteArrayOf(0xff.toByte()),
            byteArrayOf(0x00, 0x10, 0x2f, 0x80.toByte(), 0xff.toByte()),
        )
        for (bytes in samples) {
            val to5 = assertIs<KardanoResult.Ok<ByteArray>>(
                Bech32.convertBits(bytes, 8, 5, pad = true),
            )
            val back = assertIs<KardanoResult.Ok<ByteArray>>(
                Bech32.convertBits(to5.value, 5, 8, pad = false),
            )
            assertTrue(bytes.contentEquals(back.value))
        }
    }

    @Test
    fun convertBitsRejectsInvalidPadding() {
        // A single 5-bit value carries 5 bits, which cannot form a complete 8-bit group
        // without padding; with pad = false this is invalid leftover.
        val err = assertIs<KardanoResult.Err<Bech32Error>>(
            Bech32.convertBits(byteArrayOf(1), 5, 8, pad = false),
        )
        assertEquals(Bech32Error.InvalidPadding, err.error)
    }

    @Test
    fun convertBitsRejectsOverLimitOutput() {
        // Enough 5-bit values that a 5->8 conversion would exceed MAX_DATA_BYTES.
        val data = ByteArray(1100) // all-zero 5-bit values
        val err = assertIs<KardanoResult.Err<Bech32Error>>(
            Bech32.convertBits(data, 5, 8, pad = true),
        )
        assertEquals(Bech32.MAX_DATA_BYTES, assertIs<Bech32Error.DataTooLong>(err.error).max)
    }

    private fun decode(hrp: String, data: ByteArray, variant: Bech32Variant): Bech32Decoded {
        val encoded = assertIs<KardanoResult.Ok<String>>(Bech32.encode(hrp, data, variant))
        return assertIs<KardanoResult.Ok<Bech32Decoded>>(Bech32.decode(encoded.value)).value
    }

    @Test
    fun decodedToStringDoesNotDumpDataValues() {
        // Recognizable 5-bit data values. toString may include the public HRP and the
        // value count, but must not dump the data values themselves.
        val data = byteArrayOf(17, 23, 9, 30, 1)
        val text = decode("kardano", data, Bech32Variant.BECH32).toString()
        assertTrue(text.contains("dataValues="), "toString should keep the structural count")
        assertTrue(text.contains("kardano"), "the public HRP may appear")
        assertFalse(text.contains(data.joinToString()), "must not dump the 5-bit values")
        assertFalse(text.contains(data.contentToString()), "must not dump the 5-bit values")
    }

    @Test
    fun decodedEqualityAndHashCode() {
        val data = byteArrayOf(1, 2, 3, 31, 0)
        val a = decode("kardano", data, Bech32Variant.BECH32)
        val b = decode("kardano", data, Bech32Variant.BECH32)
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())

        // Different HRP, different data, and different variant are each not equal.
        assertFalse(a == decode("cardano", data, Bech32Variant.BECH32))
        assertFalse(a == decode("kardano", byteArrayOf(1, 2, 3, 31, 1), Bech32Variant.BECH32))
        assertFalse(a == decode("kardano", data, Bech32Variant.BECH32M))
    }
}
