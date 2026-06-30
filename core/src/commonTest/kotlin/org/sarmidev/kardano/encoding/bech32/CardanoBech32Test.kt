package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class CardanoBech32Test {

    // Representative non-protocol 5-bit data (each value in 0..31). These are not real
    // address payloads; the wrappers do not interpret them.
    private val sampleData = byteArrayOf(0, 1, 2, 31, 17, 5, 9, 30, 12)

    private fun engineEncode(
        hrp: String,
        data: ByteArray = sampleData,
        variant: Bech32Variant = Bech32Variant.BECH32,
    ): String = assertIs<KardanoResult.Ok<String>>(
        Bech32.encode(hrp, data, variant),
        "engine encode($hrp) should succeed",
    ).value

    @Test
    fun encodeAcceptsEachAllowlistedHrp() {
        for (hrp in CardanoHrp.entries) {
            val encoded = assertIs<KardanoResult.Ok<String>>(
                CardanoBech32.encode(hrp, sampleData),
                "encode(${hrp.value}) should succeed",
            )
            assertTrue(
                encoded.value.startsWith(hrp.value + "1"),
                "encoded string for ${hrp.value} should carry the HRP and separator",
            )
        }
    }

    @Test
    fun decodeAcceptsValidBech32ForEachAllowlistedHrp() {
        for (hrp in CardanoHrp.entries) {
            val input = engineEncode(hrp.value)
            val decoded = assertIs<KardanoResult.Ok<Bech32Decoded>>(
                CardanoBech32.decode(input),
                "decode for ${hrp.value} should succeed",
            )
            assertEquals(hrp.value, decoded.value.hrp)
            assertEquals(Bech32Variant.BECH32, decoded.value.variant)
            assertTrue(sampleData.contentEquals(decoded.value.toData5BitArray()))
        }
    }

    @Test
    fun roundTripPreservesHrpAndDataForEachAllowlistedHrp() {
        for (hrp in CardanoHrp.entries) {
            val encoded = assertIs<KardanoResult.Ok<String>>(CardanoBech32.encode(hrp, sampleData))
            val decoded = assertIs<KardanoResult.Ok<Bech32Decoded>>(
                CardanoBech32.decode(encoded.value),
            )
            assertEquals(hrp.value, decoded.value.hrp)
            assertTrue(sampleData.contentEquals(decoded.value.toData5BitArray()))
        }
    }

    @Test
    fun decodeRejectsUnsupportedHrp() {
        // A structurally valid Bech32 string whose HRP is not on the Cardano allowlist.
        val input = engineEncode("btc")
        val err = assertIs<KardanoResult.Err<CardanoBech32Error>>(CardanoBech32.decode(input))
        assertEquals(CardanoBech32Error.UnsupportedHrp("btc"), err.error)
    }

    @Test
    fun decodePropagatesGenericChecksumError() {
        // Mutate the final checksum character to another valid Bech32 charset character and
        // use the first mutation the generic engine reports as InvalidChecksum. This keeps a
        // deterministic InvalidChecksum assertion while avoiding a chance valid/Bech32m
        // decode from a single fixed substitution.
        val valid = engineEncode("addr")
        val charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
        val corrupted = charset.asSequence()
            .filter { it != valid.last() }
            .map { valid.dropLast(1) + it }
            .firstOrNull {
                val decoded = Bech32.decode(it)
                decoded is KardanoResult.Err && decoded.error == Bech32Error.InvalidChecksum
            }
        assertNotNull(corrupted, "expected a checksum-breaking single-character mutation")
        val err = assertIs<KardanoResult.Err<CardanoBech32Error>>(CardanoBech32.decode(corrupted))
        val underlying = assertIs<CardanoBech32Error.Underlying>(err.error)
        assertEquals(Bech32Error.InvalidChecksum, underlying.error)
    }

    @Test
    fun decodePropagatesGenericCharsetError() {
        // 'b' is not part of the Bech32 alphabet; the engine rejects it as a data character.
        val err = assertIs<KardanoResult.Err<CardanoBech32Error>>(CardanoBech32.decode("addr1b4n0q5v"))
        val underlying = assertIs<CardanoBech32Error.Underlying>(err.error)
        assertIs<Bech32Error.InvalidDataCharacter>(underlying.error)
    }

    @Test
    fun decodeRejectsBech32mForAllowlistedHrp() {
        // A valid Bech32m string for an allowlisted HRP is rejected: wrappers are Bech32-only.
        val input = engineEncode("addr", variant = Bech32Variant.BECH32M)
        val err = assertIs<KardanoResult.Err<CardanoBech32Error>>(CardanoBech32.decode(input))
        assertEquals(CardanoBech32Error.UnsupportedVariant(Bech32Variant.BECH32M), err.error)
    }

    @Test
    fun decodeChecksHrpBeforeVariantForBech32mUnsupportedHrp() {
        // A valid Bech32m string with an unsupported HRP: HRP is checked first, so the
        // more domain-specific UnsupportedHrp error wins over UnsupportedVariant.
        val input = engineEncode("btc", variant = Bech32Variant.BECH32M)
        val err = assertIs<KardanoResult.Err<CardanoBech32Error>>(CardanoBech32.decode(input))
        assertEquals(CardanoBech32Error.UnsupportedHrp("btc"), err.error)
    }
}
