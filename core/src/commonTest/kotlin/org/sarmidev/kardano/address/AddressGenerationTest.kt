package org.sarmidev.kardano.address

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.bech32.Bech32
import org.sarmidev.kardano.encoding.bech32.CardanoBech32
import org.sarmidev.kardano.encoding.bech32.CardanoHrp
import org.sarmidev.kardano.primitives.Network
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Tests for [AddressCredential.keyHash], [AddressCredential.scriptHash], and
 * [Address.baseAddress] (Block 1.7a generation; see
 * [ADR-0012](../../../../../../docs/DECISIONS/0012-address-encoding-and-roundtrip.md)).
 *
 * Valid builder cases rebuild the CIP-19 "Test vectors" base addresses (already cited
 * verbatim in [AddressTest]) from their own decoded credential bytes, through the public
 * generation API, and assert the rebuilt address's canonical Bech32 matches the cited
 * string. The vector string constants are duplicated from [AddressTest] rather than shared,
 * matching this codebase's existing per-file test convention; both copies must stay
 * byte-for-byte identical to the cited spec. Invalid/edge cases are hand-written rule tests
 * using synthetic (non-vector) byte arrays, not CIP-19 vectors.
 *
 * Source (valid vectors, verbatim): CIP-19, "Test vectors" section.
 * https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md
 */
class AddressGenerationTest {

    // --- CIP-19 Test vectors (verbatim from the spec; base addresses only) ---
    // https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md
    private companion object {
        const val MAINNET_TYPE_00 =
            "addr1qx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgse35a3x"
        const val MAINNET_TYPE_01 =
            "addr1z8phkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gten0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs9yc0hh"
        const val MAINNET_TYPE_02 =
            "addr1yx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerkr0vd4msrxnuwnccdxlhdjar77j6lg0wypcc9uar5d2shs2z78ve"
        const val MAINNET_TYPE_03 =
            "addr1x8phkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gt7r0vd4msrxnuwnccdxlhdjar77j6lg0wypcc9uar5d2shskhj42g"
        const val TESTNET_TYPE_00 =
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"
        const val TESTNET_TYPE_01 =
            "addr_test1zrphkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gten0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgsxj90mg"
        const val TESTNET_TYPE_02 =
            "addr_test1yz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerkr0vd4msrxnuwnccdxlhdjar77j6lg0wypcc9uar5d2shsf5r8qx"
        const val TESTNET_TYPE_03 =
            "addr_test1xrphkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gt7r0vd4msrxnuwnccdxlhdjar77j6lg0wypcc9uar5d2shs4p04xh"

        const val HASH_SIZE = 28
    }

    // ----- Valid builder cases: rebuild each cited base vector from its own bytes -----

    @Test
    fun buildsMainnetBaseKeyKeyVector() =
        assertRebuildsVector(MAINNET_TYPE_00, Network.MAINNET, CredentialKind.KEY, CredentialKind.KEY)

    @Test
    fun buildsMainnetBaseScriptKeyVector() =
        assertRebuildsVector(MAINNET_TYPE_01, Network.MAINNET, CredentialKind.SCRIPT, CredentialKind.KEY)

    @Test
    fun buildsMainnetBaseKeyScriptVector() =
        assertRebuildsVector(MAINNET_TYPE_02, Network.MAINNET, CredentialKind.KEY, CredentialKind.SCRIPT)

    @Test
    fun buildsMainnetBaseScriptScriptVector() =
        assertRebuildsVector(MAINNET_TYPE_03, Network.MAINNET, CredentialKind.SCRIPT, CredentialKind.SCRIPT)

    @Test
    fun buildsTestnetBaseKeyKeyVector() =
        assertRebuildsVector(TESTNET_TYPE_00, Network.TESTNET, CredentialKind.KEY, CredentialKind.KEY)

    @Test
    fun buildsTestnetBaseScriptKeyVector() =
        assertRebuildsVector(TESTNET_TYPE_01, Network.TESTNET, CredentialKind.SCRIPT, CredentialKind.KEY)

    @Test
    fun buildsTestnetBaseKeyScriptVector() =
        assertRebuildsVector(TESTNET_TYPE_02, Network.TESTNET, CredentialKind.KEY, CredentialKind.SCRIPT)

    @Test
    fun buildsTestnetBaseScriptScriptVector() =
        assertRebuildsVector(TESTNET_TYPE_03, Network.TESTNET, CredentialKind.SCRIPT, CredentialKind.SCRIPT)

    // ----- parse -> generate -> parse structural roundtrip -----

    @Test
    fun parseGenerateParseRoundtripsStructurally() {
        val parsed = ok(Address.parse(TESTNET_TYPE_00))
        val payment = requireNotNull(parsed.paymentCredential)
        val stake = requireNotNull(parsed.stakeCredential)

        val rebuilt = ok(Address.baseAddress(Network.TESTNET, payment, stake))
        assertEquals(parsed, rebuilt)

        val reparsed = ok(Address.parse(rebuilt.toBech32()))
        assertEquals(rebuilt, reparsed)
        assertEquals(parsed, reparsed)
    }

    // ----- Invalid / edge cases: credential length -----
    // Hand-written rule tests using synthetic byte arrays. These are NOT CIP-19 vectors.

    @Test
    fun keyHashRejectsTooShortInput() {
        val error = err(AddressCredential.keyHash(ByteArray(HASH_SIZE - 1)))
        assertTrue(error is AddressError.InvalidCredentialLength)
        assertEquals(HASH_SIZE, error.expected)
        assertEquals(HASH_SIZE - 1, error.actual)
    }

    @Test
    fun keyHashRejectsTooLongInput() {
        val error = err(AddressCredential.keyHash(ByteArray(HASH_SIZE + 1)))
        assertTrue(error is AddressError.InvalidCredentialLength)
        assertEquals(HASH_SIZE, error.expected)
        assertEquals(HASH_SIZE + 1, error.actual)
    }

    @Test
    fun scriptHashRejectsTooShortInput() {
        val error = err(AddressCredential.scriptHash(ByteArray(HASH_SIZE - 1)))
        assertTrue(error is AddressError.InvalidCredentialLength)
        assertEquals(HASH_SIZE, error.expected)
        assertEquals(HASH_SIZE - 1, error.actual)
    }

    @Test
    fun keyHashRejectsEmptyInput() {
        val error = err(AddressCredential.keyHash(ByteArray(0)))
        assertTrue(error is AddressError.InvalidCredentialLength)
        assertEquals(0, error.actual)
    }

    // ----- Defensive copies -----

    @Test
    fun keyHashCopiesInputDefensively() {
        val original = ByteArray(HASH_SIZE) { it.toByte() }
        val credential = ok(AddressCredential.keyHash(original))
        original[0] = (original[0] + 1).toByte()
        assertFalse(original.contentEquals(credential.hashBytes()))
    }

    @Test
    fun scriptHashCopiesInputDefensively() {
        val original = ByteArray(HASH_SIZE) { it.toByte() }
        val credential = ok(AddressCredential.scriptHash(original))
        original[0] = (original[0] + 1).toByte()
        assertFalse(original.contentEquals(credential.hashBytes()))
    }

    @Test
    fun baseAddressToByteArrayReturnsDefensiveCopy() {
        val built = ok(Address.baseAddress(Network.TESTNET, syntheticKeyHash(0), syntheticKeyHash(1)))
        val first = built.toByteArray()
        first[0] = (first[0] + 1).toByte()
        assertFalse(first.contentEquals(built.toByteArray()))
    }

    // ----- HRP / network derivation -----

    @Test
    fun baseAddressUsesTestnetHrp() {
        val built = ok(Address.baseAddress(Network.TESTNET, syntheticKeyHash(0), syntheticKeyHash(1)))
        assertEquals(CardanoHrp.ADDR_TEST, built.hrp)
        assertTrue(built.toBech32().startsWith("addr_test1"))
    }

    @Test
    fun baseAddressUsesMainnetHrp() {
        val built = ok(Address.baseAddress(Network.MAINNET, syntheticKeyHash(0), syntheticKeyHash(1)))
        assertEquals(CardanoHrp.ADDR, built.hrp)
        assertTrue(built.toBech32().startsWith("addr1"))
    }

    // ----- bech32 vs toBech32() for a generated address -----

    @Test
    fun generatedAddressBech32EqualsCanonicalToBech32() {
        val built = ok(Address.baseAddress(Network.TESTNET, syntheticKeyHash(0), syntheticKeyHash(1)))
        assertEquals(built.toBech32(), built.bech32)
    }

    // ----- equals / hashCode / toString on generated addresses -----

    @Test
    fun equalGeneratedAddressesAreEqualWithEqualHashCode() {
        val payment = syntheticKeyHash(0)
        val stake = syntheticKeyHash(1)
        val a = ok(Address.baseAddress(Network.TESTNET, payment, stake))
        val b = ok(Address.baseAddress(Network.TESTNET, payment, stake))
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
        assertEquals(a.toBech32(), b.toBech32())
    }

    @Test
    fun differentlyKeyedGeneratedAddressesAreNotEqual() {
        val a = ok(Address.baseAddress(Network.TESTNET, syntheticKeyHash(0), syntheticKeyHash(1)))
        val b = ok(Address.baseAddress(Network.TESTNET, syntheticKeyHash(2), syntheticKeyHash(1)))
        assertFalse(a == b)
    }

    @Test
    fun generatedAddressToStringRendersNoBytesOrHex() {
        val built = ok(Address.baseAddress(Network.TESTNET, syntheticKeyHash(0), syntheticKeyHash(1)))
        val rendered = built.toString()
        assertTrue(rendered.startsWith("Address("))
        assertTrue(rendered.contains("bytes=57"))
    }

    // ----- helpers -----

    private fun assertRebuildsVector(
        vector: String,
        network: Network,
        paymentKind: CredentialKind,
        stakeKind: CredentialKind,
    ) {
        val payload = payloadOf(vector)
        val paymentHash = payload.copyOfRange(1, 1 + HASH_SIZE)
        val stakeHash = payload.copyOfRange(1 + HASH_SIZE, 1 + 2 * HASH_SIZE)

        val payment = ok(credentialOf(paymentKind, paymentHash))
        val stake = ok(credentialOf(stakeKind, stakeHash))

        val built = ok(Address.baseAddress(network, payment, stake))
        assertEquals(vector, built.toBech32())
        assertEquals(network, built.network)
        assertEquals(AddressType.BASE, built.type)
        assertEquals(paymentKind, built.paymentCredential?.kind)
        assertEquals(stakeKind, built.stakeCredential?.kind)
    }

    private fun credentialOf(
        kind: CredentialKind,
        hash: ByteArray,
    ): KardanoResult<AddressCredential, AddressError> = when (kind) {
        CredentialKind.KEY -> AddressCredential.keyHash(hash)
        CredentialKind.SCRIPT -> AddressCredential.scriptHash(hash)
    }

    /** A structurally valid but synthetic (non-vector) 28-byte key-hash credential. */
    private fun syntheticKeyHash(seed: Int): AddressCredential =
        ok(AddressCredential.keyHash(ByteArray(HASH_SIZE) { (it + seed).toByte() }))

    private fun payloadOf(address: String): ByteArray {
        val decoded = ok(CardanoBech32.decode(address))
        return ok(Bech32.convertBits(decoded.toData5BitArray(), 5, 8, pad = false))
    }

    private fun <T> ok(result: KardanoResult<T, *>): T {
        assertTrue(result is KardanoResult.Ok, "expected Ok but was $result")
        return result.value
    }

    private fun err(result: KardanoResult<*, *>): AddressError {
        assertTrue(result is KardanoResult.Err, "expected Err but was $result")
        return result.error as AddressError
    }
}
