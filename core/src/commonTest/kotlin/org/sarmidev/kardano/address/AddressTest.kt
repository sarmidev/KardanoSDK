package org.sarmidev.kardano.address

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.bech32.Bech32
import org.sarmidev.kardano.encoding.bech32.Bech32Variant
import org.sarmidev.kardano.encoding.bech32.CardanoBech32
import org.sarmidev.kardano.encoding.bech32.CardanoHrp
import org.sarmidev.kardano.primitives.Network
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Tests for [Address.parse].
 *
 * Valid cases use the CIP-19 "Test vectors" enterprise (type 6/7) and reward (type 14/15)
 * example addresses copied verbatim from the spec. Invalid/edge cases are hand-written rule
 * tests that take a cited CIP-19 vector, decode it, mutate one field, and re-encode it; they
 * are NOT CIP-19 vectors and are labeled as such on each test.
 *
 * Source (valid vectors, verbatim): CIP-19, "Test vectors" section.
 * https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md
 */
class AddressTest {

    // --- CIP-19 Test vectors (verbatim from the spec) ---
    // https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md
    private companion object {
        // mainnet base (types 0-3)
        const val MAINNET_TYPE_00 =
            "addr1qx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgse35a3x"
        const val MAINNET_TYPE_01 =
            "addr1z8phkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gten0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs9yc0hh"
        const val MAINNET_TYPE_02 =
            "addr1yx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerkr0vd4msrxnuwnccdxlhdjar77j6lg0wypcc9uar5d2shs2z78ve"
        const val MAINNET_TYPE_03 =
            "addr1x8phkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gt7r0vd4msrxnuwnccdxlhdjar77j6lg0wypcc9uar5d2shskhj42g"

        // mainnet
        const val MAINNET_TYPE_06 =
            "addr1vx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzers66hrl8"
        const val MAINNET_TYPE_07 =
            "addr1w8phkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gtcyjy7wx"
        const val MAINNET_TYPE_14 =
            "stake1uyehkck0lajq8gr28t9uxnuvgcqrc6070x3k9r8048z8y5gh6ffgw"
        const val MAINNET_TYPE_15 =
            "stake178phkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gtcccycj5"

        // testnet base (types 0-3)
        const val TESTNET_TYPE_00 =
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"
        const val TESTNET_TYPE_01 =
            "addr_test1zrphkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gten0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgsxj90mg"
        const val TESTNET_TYPE_02 =
            "addr_test1yz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerkr0vd4msrxnuwnccdxlhdjar77j6lg0wypcc9uar5d2shsf5r8qx"
        const val TESTNET_TYPE_03 =
            "addr_test1xrphkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gt7r0vd4msrxnuwnccdxlhdjar77j6lg0wypcc9uar5d2shs4p04xh"

        // testnet
        const val TESTNET_TYPE_06 =
            "addr_test1vz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerspjrlsz"
        const val TESTNET_TYPE_07 =
            "addr_test1wrphkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gtcl6szpr"
        const val TESTNET_TYPE_14 =
            "stake_test1uqehkck0lajq8gr28t9uxnuvgcqrc6070x3k9r8048z8y5gssrtvn"
        const val TESTNET_TYPE_15 =
            "stake_test17rphkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gtcljw6kf"

        // pointer (types 4-5). CIP-19 documents the pointer used to generate every type-04 /
        // type-05 vector below as (slot=2498243, transactionIndex=27, certificateIndex=3).
        const val MAINNET_TYPE_04 =
            "addr1gx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer5pnz75xxcrzqf96k"
        const val MAINNET_TYPE_05 =
            "addr128phkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gtupnz75xxcrtw79hu"
        const val TESTNET_TYPE_04 =
            "addr_test1gz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer5pnz75xxcrdw5vky"
        const val TESTNET_TYPE_05 =
            "addr_test12rphkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gtupnz75xxcryqrvmw"

        // CIP-19 documented pointer coordinates for the type-04 / type-05 vectors.
        const val POINTER_SLOT = 2498243L
        const val POINTER_TX_INDEX = 27L
        const val POINTER_CERT_INDEX = 3L
    }

    // ----- Valid cases (CIP-19 vectors, verbatim) -----

    @Test
    fun parsesMainnetEnterpriseKeyVector() {
        val address = ok(Address.parse(MAINNET_TYPE_06))
        assertEquals(Network.MAINNET, address.network)
        assertEquals(AddressType.ENTERPRISE, address.type)
        assertEquals(CardanoHrp.ADDR, address.hrp)
        val payment = assertNotNull(address.paymentCredential)
        assertEquals(CredentialKind.KEY, payment.kind)
        assertEquals(28, payment.hashBytes().size)
        assertNull(address.stakeCredential)
        assertEquals(29, address.toByteArray().size)
    }

    @Test
    fun parsesMainnetEnterpriseScriptVector() {
        val address = ok(Address.parse(MAINNET_TYPE_07))
        assertEquals(Network.MAINNET, address.network)
        assertEquals(AddressType.ENTERPRISE, address.type)
        assertEquals(CardanoHrp.ADDR, address.hrp)
        val payment = assertNotNull(address.paymentCredential)
        assertEquals(CredentialKind.SCRIPT, payment.kind)
        assertEquals(28, payment.hashBytes().size)
        assertNull(address.stakeCredential)
    }

    @Test
    fun parsesMainnetRewardKeyVector() {
        val address = ok(Address.parse(MAINNET_TYPE_14))
        assertEquals(Network.MAINNET, address.network)
        assertEquals(AddressType.REWARD, address.type)
        assertEquals(CardanoHrp.STAKE, address.hrp)
        val stake = assertNotNull(address.stakeCredential)
        assertEquals(CredentialKind.KEY, stake.kind)
        assertNull(address.paymentCredential)
        assertEquals(29, address.toByteArray().size)
    }

    @Test
    fun parsesMainnetRewardScriptVector() {
        val address = ok(Address.parse(MAINNET_TYPE_15))
        assertEquals(Network.MAINNET, address.network)
        assertEquals(AddressType.REWARD, address.type)
        assertEquals(CardanoHrp.STAKE, address.hrp)
        val stake = assertNotNull(address.stakeCredential)
        assertEquals(CredentialKind.SCRIPT, stake.kind)
        assertNull(address.paymentCredential)
    }

    @Test
    fun parsesTestnetEnterpriseKeyVector() {
        val address = ok(Address.parse(TESTNET_TYPE_06))
        assertEquals(Network.TESTNET, address.network)
        assertEquals(AddressType.ENTERPRISE, address.type)
        assertEquals(CardanoHrp.ADDR_TEST, address.hrp)
        val payment = assertNotNull(address.paymentCredential)
        assertEquals(CredentialKind.KEY, payment.kind)
        assertNull(address.stakeCredential)
    }

    @Test
    fun parsesTestnetEnterpriseScriptVector() {
        val address = ok(Address.parse(TESTNET_TYPE_07))
        assertEquals(Network.TESTNET, address.network)
        assertEquals(AddressType.ENTERPRISE, address.type)
        assertEquals(CardanoHrp.ADDR_TEST, address.hrp)
        val payment = assertNotNull(address.paymentCredential)
        assertEquals(CredentialKind.SCRIPT, payment.kind)
        assertNull(address.stakeCredential)
    }

    @Test
    fun parsesTestnetRewardKeyVector() {
        val address = ok(Address.parse(TESTNET_TYPE_14))
        assertEquals(Network.TESTNET, address.network)
        assertEquals(AddressType.REWARD, address.type)
        assertEquals(CardanoHrp.STAKE_TEST, address.hrp)
        val stake = assertNotNull(address.stakeCredential)
        assertEquals(CredentialKind.KEY, stake.kind)
        assertNull(address.paymentCredential)
    }

    @Test
    fun parsesTestnetRewardScriptVector() {
        val address = ok(Address.parse(TESTNET_TYPE_15))
        assertEquals(Network.TESTNET, address.network)
        assertEquals(AddressType.REWARD, address.type)
        assertEquals(CardanoHrp.STAKE_TEST, address.hrp)
        val stake = assertNotNull(address.stakeCredential)
        assertEquals(CredentialKind.SCRIPT, stake.kind)
        assertNull(address.paymentCredential)
    }

    // ----- Valid base cases (CIP-19 vectors, verbatim) -----

    @Test
    fun parsesMainnetBaseKeyKeyVector() {
        val address = ok(Address.parse(MAINNET_TYPE_00))
        assertEquals(Network.MAINNET, address.network)
        assertEquals(AddressType.BASE, address.type)
        assertEquals(CardanoHrp.ADDR, address.hrp)
        val payment = assertNotNull(address.paymentCredential)
        val stake = assertNotNull(address.stakeCredential)
        assertEquals(CredentialKind.KEY, payment.kind)
        assertEquals(CredentialKind.KEY, stake.kind)
        assertEquals(28, payment.hashBytes().size)
        assertEquals(28, stake.hashBytes().size)
        assertEquals(57, address.toByteArray().size)
    }

    @Test
    fun parsesMainnetBaseScriptKeyVector() {
        val address = ok(Address.parse(MAINNET_TYPE_01))
        assertEquals(Network.MAINNET, address.network)
        assertEquals(AddressType.BASE, address.type)
        assertEquals(CardanoHrp.ADDR, address.hrp)
        assertEquals(CredentialKind.SCRIPT, assertNotNull(address.paymentCredential).kind)
        assertEquals(CredentialKind.KEY, assertNotNull(address.stakeCredential).kind)
    }

    @Test
    fun parsesMainnetBaseKeyScriptVector() {
        val address = ok(Address.parse(MAINNET_TYPE_02))
        assertEquals(Network.MAINNET, address.network)
        assertEquals(AddressType.BASE, address.type)
        assertEquals(CardanoHrp.ADDR, address.hrp)
        assertEquals(CredentialKind.KEY, assertNotNull(address.paymentCredential).kind)
        assertEquals(CredentialKind.SCRIPT, assertNotNull(address.stakeCredential).kind)
    }

    @Test
    fun parsesMainnetBaseScriptScriptVector() {
        val address = ok(Address.parse(MAINNET_TYPE_03))
        assertEquals(Network.MAINNET, address.network)
        assertEquals(AddressType.BASE, address.type)
        assertEquals(CardanoHrp.ADDR, address.hrp)
        assertEquals(CredentialKind.SCRIPT, assertNotNull(address.paymentCredential).kind)
        assertEquals(CredentialKind.SCRIPT, assertNotNull(address.stakeCredential).kind)
    }

    @Test
    fun parsesTestnetBaseKeyKeyVector() {
        val address = ok(Address.parse(TESTNET_TYPE_00))
        assertEquals(Network.TESTNET, address.network)
        assertEquals(AddressType.BASE, address.type)
        assertEquals(CardanoHrp.ADDR_TEST, address.hrp)
        assertEquals(CredentialKind.KEY, assertNotNull(address.paymentCredential).kind)
        assertEquals(CredentialKind.KEY, assertNotNull(address.stakeCredential).kind)
        assertEquals(57, address.toByteArray().size)
    }

    @Test
    fun parsesTestnetBaseScriptKeyVector() {
        val address = ok(Address.parse(TESTNET_TYPE_01))
        assertEquals(Network.TESTNET, address.network)
        assertEquals(AddressType.BASE, address.type)
        assertEquals(CardanoHrp.ADDR_TEST, address.hrp)
        assertEquals(CredentialKind.SCRIPT, assertNotNull(address.paymentCredential).kind)
        assertEquals(CredentialKind.KEY, assertNotNull(address.stakeCredential).kind)
    }

    @Test
    fun parsesTestnetBaseKeyScriptVector() {
        val address = ok(Address.parse(TESTNET_TYPE_02))
        assertEquals(Network.TESTNET, address.network)
        assertEquals(AddressType.BASE, address.type)
        assertEquals(CardanoHrp.ADDR_TEST, address.hrp)
        assertEquals(CredentialKind.KEY, assertNotNull(address.paymentCredential).kind)
        assertEquals(CredentialKind.SCRIPT, assertNotNull(address.stakeCredential).kind)
    }

    @Test
    fun parsesTestnetBaseScriptScriptVector() {
        val address = ok(Address.parse(TESTNET_TYPE_03))
        assertEquals(Network.TESTNET, address.network)
        assertEquals(AddressType.BASE, address.type)
        assertEquals(CardanoHrp.ADDR_TEST, address.hrp)
        assertEquals(CredentialKind.SCRIPT, assertNotNull(address.paymentCredential).kind)
        assertEquals(CredentialKind.SCRIPT, assertNotNull(address.stakeCredential).kind)
    }

    // ----- Valid pointer cases (CIP-19 vectors, verbatim) -----

    @Test
    fun parsesMainnetPointerKeyVector() {
        val address = ok(Address.parse(MAINNET_TYPE_04))
        assertEquals(Network.MAINNET, address.network)
        assertEquals(AddressType.POINTER, address.type)
        assertEquals(CardanoHrp.ADDR, address.hrp)
        val payment = assertNotNull(address.paymentCredential)
        assertEquals(CredentialKind.KEY, payment.kind)
        assertEquals(28, payment.hashBytes().size)
        assertNull(address.stakeCredential)
        val pointer = assertNotNull(address.pointer)
        assertEquals(POINTER_SLOT, pointer.slot)
        assertEquals(POINTER_TX_INDEX, pointer.transactionIndex)
        assertEquals(POINTER_CERT_INDEX, pointer.certificateIndex)
    }

    @Test
    fun parsesMainnetPointerScriptVector() {
        val address = ok(Address.parse(MAINNET_TYPE_05))
        assertEquals(Network.MAINNET, address.network)
        assertEquals(AddressType.POINTER, address.type)
        assertEquals(CardanoHrp.ADDR, address.hrp)
        assertEquals(CredentialKind.SCRIPT, assertNotNull(address.paymentCredential).kind)
        assertNull(address.stakeCredential)
        val pointer = assertNotNull(address.pointer)
        assertEquals(POINTER_SLOT, pointer.slot)
        assertEquals(POINTER_TX_INDEX, pointer.transactionIndex)
        assertEquals(POINTER_CERT_INDEX, pointer.certificateIndex)
    }

    @Test
    fun parsesTestnetPointerKeyVector() {
        val address = ok(Address.parse(TESTNET_TYPE_04))
        assertEquals(Network.TESTNET, address.network)
        assertEquals(AddressType.POINTER, address.type)
        assertEquals(CardanoHrp.ADDR_TEST, address.hrp)
        assertEquals(CredentialKind.KEY, assertNotNull(address.paymentCredential).kind)
        assertNull(address.stakeCredential)
        val pointer = assertNotNull(address.pointer)
        assertEquals(POINTER_SLOT, pointer.slot)
        assertEquals(POINTER_TX_INDEX, pointer.transactionIndex)
        assertEquals(POINTER_CERT_INDEX, pointer.certificateIndex)
    }

    @Test
    fun parsesTestnetPointerScriptVector() {
        val address = ok(Address.parse(TESTNET_TYPE_05))
        assertEquals(Network.TESTNET, address.network)
        assertEquals(AddressType.POINTER, address.type)
        assertEquals(CardanoHrp.ADDR_TEST, address.hrp)
        assertEquals(CredentialKind.SCRIPT, assertNotNull(address.paymentCredential).kind)
        assertNull(address.stakeCredential)
        val pointer = assertNotNull(address.pointer)
        assertEquals(POINTER_SLOT, pointer.slot)
        assertEquals(POINTER_TX_INDEX, pointer.transactionIndex)
        assertEquals(POINTER_CERT_INDEX, pointer.certificateIndex)
    }

    // ----- Credential presence contract -----

    @Test
    fun enterpriseHasOnlyPaymentCredential() {
        val address = ok(Address.parse(MAINNET_TYPE_06))
        assertNotNull(address.paymentCredential)
        assertNull(address.stakeCredential)
        assertNull(address.pointer)
    }

    @Test
    fun rewardHasOnlyStakeCredential() {
        val address = ok(Address.parse(MAINNET_TYPE_14))
        assertNull(address.paymentCredential)
        assertNotNull(address.stakeCredential)
        assertNull(address.pointer)
    }

    @Test
    fun baseHasBothCredentials() {
        val address = ok(Address.parse(MAINNET_TYPE_00))
        assertNotNull(address.paymentCredential)
        assertNotNull(address.stakeCredential)
        assertNull(address.pointer)
    }

    @Test
    fun pointerHasPaymentCredentialAndPointer() {
        val address = ok(Address.parse(MAINNET_TYPE_04))
        assertNotNull(address.paymentCredential)
        assertNull(address.stakeCredential)
        assertNotNull(address.pointer)
    }

    // ----- Defensive copy / equality / toString -----

    @Test
    fun toByteArrayReturnsDefensiveCopy() {
        val address = ok(Address.parse(MAINNET_TYPE_06))
        val first = address.toByteArray()
        first[0] = (first[0] + 1).toByte()
        assertFalse(first.contentEquals(address.toByteArray()))
    }

    @Test
    fun credentialHashBytesReturnsDefensiveCopy() {
        val credential = assertNotNull(ok(Address.parse(MAINNET_TYPE_06)).paymentCredential)
        val first = credential.hashBytes()
        first[0] = (first[0] + 1).toByte()
        assertFalse(first.contentEquals(credential.hashBytes()))
    }

    @Test
    fun equalAddressesAreEqualWithEqualHashCode() {
        val a = ok(Address.parse(MAINNET_TYPE_06))
        val b = ok(Address.parse(MAINNET_TYPE_06))
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }

    @Test
    fun differentAddressesAreNotEqual() {
        val a = ok(Address.parse(MAINNET_TYPE_06))
        val b = ok(Address.parse(MAINNET_TYPE_07))
        assertFalse(a == b)
    }

    @Test
    fun equalBaseAddressesAreEqualWithEqualHashCode() {
        val a = ok(Address.parse(MAINNET_TYPE_00))
        val b = ok(Address.parse(MAINNET_TYPE_00))
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }

    @Test
    fun baseAddressesDifferingOnlyInStakeCredentialAreNotEqual() {
        // Labeled derived rule object (NOT a CIP-19 vector): take CIP-19 mainnet type-00,
        // keep its 28-byte payment part, and flip one byte of the 28-byte stake (delegation)
        // part, then re-encode under addr. Both parse as valid base addresses that share a
        // payment credential but differ in the stake credential, so they must not be equal.
        val payload = payloadOf(MAINNET_TYPE_00)
        val mutatedPayload = payload.copyOf()
        val stakeStart = 1 + 28
        mutatedPayload[stakeStart] = (mutatedPayload[stakeStart].toInt() xor 0x01).toByte()

        val original = ok(Address.parse(MAINNET_TYPE_00))
        val mutated = ok(Address.parse(reencode(CardanoHrp.ADDR, mutatedPayload)))

        assertEquals(original.paymentCredential, mutated.paymentCredential)
        assertFalse(original.stakeCredential == mutated.stakeCredential)
        assertFalse(original == mutated)
    }

    @Test
    fun equalPointerAddressesAreEqualWithEqualHashCode() {
        val a = ok(Address.parse(MAINNET_TYPE_04))
        val b = ok(Address.parse(MAINNET_TYPE_04))
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }

    @Test
    fun toStringRendersNoBytesOrHex() {
        val rendered = ok(Address.parse(MAINNET_TYPE_06)).toString()
        assertTrue(rendered.startsWith("Address("))
        assertTrue(rendered.contains("bytes=29"))
        // No hex/byte content of the credential is rendered.
        assertFalse(rendered.contains("2fxv"))
    }

    @Test
    fun pointerToStringRendersNoBytesOrHex() {
        val rendered = ok(Address.parse(MAINNET_TYPE_04)).toString()
        assertTrue(rendered.startsWith("Address("))
        assertTrue(rendered.contains("bytes=35"))
        // No hex/byte content of the payment credential is rendered.
        assertFalse(rendered.contains("2fxv"))
    }

    // ----- Invalid / edge cases -----
    // Hand-written rule tests. Each derives its input from a cited CIP-19 vector by
    // decoding, mutating one field, and re-encoding. These are NOT CIP-19 vectors.

    @Test
    fun rejectsBadChecksum() {
        // Rule test derived from CIP-19 mainnet type-06: flip the final data character so
        // the Bech32 checksum no longer validates.
        val last = MAINNET_TYPE_06.last()
        val replacement = if (last == 'l') 'q' else 'l'
        val mutated = MAINNET_TYPE_06.dropLast(1) + replacement
        val error = err(Address.parse(mutated))
        assertTrue(error is AddressError.Bech32)
    }

    @Test
    fun rejectsBech32mVariant() {
        // Rule test derived from CIP-19 mainnet type-06: re-encode the same payload as
        // Bech32m under the same HRP. Cardano addresses use Bech32, so this is rejected.
        val payload = payloadOf(MAINNET_TYPE_06)
        val data5 = ok(Bech32.convertBits(payload, 8, 5, pad = true))
        val bech32m = ok(Bech32.encode(CardanoHrp.ADDR.value, data5, Bech32Variant.BECH32M))
        val error = err(Address.parse(bech32m))
        assertTrue(error is AddressError.Bech32)
    }

    @Test
    fun rejectsNonAllowlistedHrp() {
        // Rule test derived from CIP-19 mainnet type-06: re-encode the same payload under a
        // non-Cardano HRP.
        val payload = payloadOf(MAINNET_TYPE_06)
        val data5 = ok(Bech32.convertBits(payload, 8, 5, pad = true))
        val foreign = ok(Bech32.encode("btc", data5, Bech32Variant.BECH32))
        val error = err(Address.parse(foreign))
        assertTrue(error is AddressError.Bech32)
    }

    @Test
    fun rejectsHrpNetworkMismatch() {
        // Rule test derived from CIP-19 testnet type-06: flip the header network nibble to
        // mainnet (1) while keeping the addr_test HRP.
        val payload = payloadOf(TESTNET_TYPE_06)
        payload[0] = ((payload[0].toInt() and 0xF0) or 0x01).toByte()
        val mutated = reencode(CardanoHrp.ADDR_TEST, payload)
        val error = err(Address.parse(mutated))
        assertTrue(error is AddressError.HrpNetworkMismatch)
        assertEquals(CardanoHrp.ADDR_TEST, error.hrp)
        assertEquals(Network.MAINNET, error.headerNetwork)
    }

    @Test
    fun rejectsHrpFamilyMismatch() {
        // Rule test derived from CIP-19 mainnet type-06 (enterprise): re-encode the payment
        // payload under the stake HRP. Header network (mainnet) matches stake, but the
        // family does not.
        val payload = payloadOf(MAINNET_TYPE_06)
        val mutated = reencode(CardanoHrp.STAKE, payload)
        val error = err(Address.parse(mutated))
        assertTrue(error is AddressError.HrpFamilyMismatch)
        assertEquals(AddressType.ENTERPRISE, error.type)
    }

    @Test
    fun rejectsBaseWrongPayloadLength() {
        // Rule test derived from CIP-19 mainnet type-06: set the header type nibble to 0
        // (base) but keep the 29-byte single-credential payload. A base address requires 57
        // bytes, so the length check rejects it.
        val payload = payloadOf(MAINNET_TYPE_06)
        payload[0] = (payload[0].toInt() and 0x0F).toByte()
        val mutated = reencode(CardanoHrp.ADDR, payload)
        val error = err(Address.parse(mutated))
        assertTrue(error is AddressError.InvalidPayloadLength)
        assertEquals(AddressType.BASE, error.type)
        assertEquals(57, error.expected)
        assertEquals(29, error.actual)
    }

    @Test
    fun rejectsBaseUnderStakeHrp() {
        // Rule test derived from CIP-19 mainnet type-00 (base): re-encode the base payload
        // under the stake HRP. Header network (mainnet) matches stake, but the family does
        // not (stake HRP expects a reward address).
        val payload = payloadOf(MAINNET_TYPE_00)
        val mutated = reencode(CardanoHrp.STAKE, payload)
        val error = err(Address.parse(mutated))
        assertTrue(error is AddressError.HrpFamilyMismatch)
        assertEquals(AddressType.BASE, error.type)
    }

    @Test
    fun rejectsBaseHrpNetworkMismatch() {
        // Rule test derived from CIP-19 testnet type-00 (base): flip the header network
        // nibble to mainnet (1) while keeping the addr_test HRP.
        val payload = payloadOf(TESTNET_TYPE_00)
        payload[0] = ((payload[0].toInt() and 0xF0) or 0x01).toByte()
        val mutated = reencode(CardanoHrp.ADDR_TEST, payload)
        val error = err(Address.parse(mutated))
        assertTrue(error is AddressError.HrpNetworkMismatch)
        assertEquals(CardanoHrp.ADDR_TEST, error.hrp)
        assertEquals(Network.MAINNET, error.headerNetwork)
    }

    @Test
    fun rejectsUnsupportedByronType() {
        // Rule test derived from CIP-19 mainnet type-06: set the header type nibble to 8
        // (Byron), which this step does not support.
        assertUnsupportedType(MAINNET_TYPE_06, typeNibble = 8)
    }

    @Test
    fun rejectsTooLongPayload() {
        // Rule test derived from CIP-19 mainnet type-06: append one byte to the payload.
        val payload = payloadOf(MAINNET_TYPE_06) + ByteArray(1)
        val mutated = reencode(CardanoHrp.ADDR, payload)
        val error = err(Address.parse(mutated))
        assertTrue(error is AddressError.InvalidPayloadLength)
        assertEquals(AddressType.ENTERPRISE, error.type)
        assertEquals(29, error.expected)
        assertEquals(30, error.actual)
    }

    @Test
    fun rejectsTooShortPayload() {
        // Rule test derived from CIP-19 mainnet type-06: drop the final payload byte.
        val full = payloadOf(MAINNET_TYPE_06)
        val payload = full.copyOfRange(0, full.size - 1)
        val mutated = reencode(CardanoHrp.ADDR, payload)
        val error = err(Address.parse(mutated))
        assertTrue(error is AddressError.InvalidPayloadLength)
        assertEquals(28, error.actual)
    }

    @Test
    fun rejectsEmptyPayload() {
        // Rule test: encode an empty payload under a Cardano HRP (no header byte present).
        val empty = ok(CardanoBech32.encode(CardanoHrp.ADDR, ByteArray(0)))
        val error = err(Address.parse(empty))
        assertTrue(error is AddressError.EmptyPayload)
    }

    // ----- Invalid / edge pointer cases -----
    // Hand-written rule tests derived from the cited CIP-19 mainnet type-04 vector by
    // decoding, mutating the pointer region, and re-encoding. These are NOT CIP-19 vectors.

    @Test
    fun rejectsPointerHrpNetworkMismatch() {
        // Rule test derived from CIP-19 testnet type-04: flip the header network nibble to
        // mainnet (1) while keeping the addr_test HRP.
        val payload = payloadOf(TESTNET_TYPE_04)
        payload[0] = ((payload[0].toInt() and 0xF0) or 0x01).toByte()
        val error = err(Address.parse(reencode(CardanoHrp.ADDR_TEST, payload)))
        assertTrue(error is AddressError.HrpNetworkMismatch)
        assertEquals(CardanoHrp.ADDR_TEST, error.hrp)
        assertEquals(Network.MAINNET, error.headerNetwork)
    }

    @Test
    fun rejectsPointerUnderStakeHrp() {
        // Rule test derived from CIP-19 mainnet type-04 (pointer): re-encode the pointer
        // payload under the stake HRP. Header network (mainnet) matches stake, but the family
        // does not (stake expects a reward address).
        val payload = payloadOf(MAINNET_TYPE_04)
        val error = err(Address.parse(reencode(CardanoHrp.STAKE, payload)))
        assertTrue(error is AddressError.HrpFamilyMismatch)
        assertEquals(AddressType.POINTER, error.type)
    }

    @Test
    fun rejectsPointerPayloadTooShortForPointer() {
        // Rule test derived from CIP-19 mainnet type-06 (29-byte enterprise payload): set the
        // header type nibble to 4 (pointer). 29 bytes is too short for a pointer (header + 28
        // credential leaves no room for any of the three coordinates).
        val payload = payloadOf(MAINNET_TYPE_06)
        payload[0] = ((payload[0].toInt() and 0x0F) or 0x40).toByte()
        val error = err(Address.parse(reencode(CardanoHrp.ADDR, payload)))
        assertTrue(error is AddressError.TruncatedPointer)
    }

    @Test
    fun rejectsTruncatedPointerContinuationAtEnd() {
        // Rule test derived from CIP-19 mainnet type-04: set the continuation bit on the final
        // payload byte (the certificate-index terminator), so the last coordinate claims a
        // following byte that does not exist.
        val payload = payloadOf(MAINNET_TYPE_04)
        val last = payload.size - 1
        payload[last] = (payload[last].toInt() or 0x80).toByte()
        val error = err(Address.parse(reencode(CardanoHrp.ADDR, payload)))
        assertTrue(error is AddressError.TruncatedPointer)
    }

    @Test
    fun rejectsTruncatedPointerDroppedByte() {
        // Rule test derived from CIP-19 mainnet type-04: drop the final payload byte (the
        // certificate-index coordinate), leaving fewer than three complete coordinates.
        val full = payloadOf(MAINNET_TYPE_04)
        val payload = full.copyOfRange(0, full.size - 1)
        val error = err(Address.parse(reencode(CardanoHrp.ADDR, payload)))
        assertTrue(error is AddressError.TruncatedPointer)
    }

    @Test
    fun rejectsNonCanonicalPointerInteger() {
        // Rule test derived from CIP-19 mainnet type-04: prepend a 0x80 leading-zero group to
        // the slot coordinate. The value is unchanged but the encoding is over-long, which the
        // Phase 0 parser rejects rather than normalizing.
        val full = payloadOf(MAINNET_TYPE_04)
        val pointerStart = 1 + 28
        val mutated = full.copyOfRange(0, pointerStart) +
            byteArrayOf(0x80.toByte()) +
            full.copyOfRange(pointerStart, full.size)
        val error = err(Address.parse(reencode(CardanoHrp.ADDR, mutated)))
        assertTrue(error is AddressError.NonCanonicalPointer)
        assertEquals(PointerField.SLOT, error.field)
    }

    @Test
    fun rejectsPointerFieldOverLimit() {
        // Rule test derived from CIP-19 mainnet type-04: replace the slot coordinate with a
        // well-formed (terminating) but over-long encoding of 10 bytes (nine 0xFF continuation
        // bytes then a 0x01 terminator). This exceeds MAX_POINTER_FIELD_BYTES; it is fully
        // present, so it is rejected as out of range rather than truncated.
        val full = payloadOf(MAINNET_TYPE_04)
        val prefix = full.copyOfRange(0, 1 + 28)
        val overlongSlot = ByteArray(9) { 0xFF.toByte() } + byteArrayOf(0x01.toByte())
        val mutated = prefix + overlongSlot
        val error = err(Address.parse(reencode(CardanoHrp.ADDR, mutated)))
        assertTrue(error is AddressError.PointerValueOutOfRange)
        assertEquals(PointerField.SLOT, error.field)
    }

    @Test
    fun rejectsTrailingBytesAfterPointer() {
        // Rule test derived from CIP-19 mainnet type-04: append one byte after the certificate
        // index. The three coordinates decode fully, but a byte remains.
        val full = payloadOf(MAINNET_TYPE_04)
        val mutated = full + byteArrayOf(0x00)
        val error = err(Address.parse(reencode(CardanoHrp.ADDR, mutated)))
        assertTrue(error is AddressError.TrailingPointerBytes)
        assertEquals(full.size, error.consumed)
        assertEquals(mutated.size, error.actual)
    }

    // ----- helpers -----

    private fun assertUnsupportedType(vector: String, typeNibble: Int) {
        val payload = payloadOf(vector)
        payload[0] = (((typeNibble shl 4) and 0xF0) or (payload[0].toInt() and 0x0F)).toByte()
        val mutated = reencode(CardanoHrp.ADDR, payload)
        val error = err(Address.parse(mutated))
        assertTrue(error is AddressError.UnsupportedAddressType)
        assertEquals(typeNibble, error.headerTypeNibble)
    }

    private fun payloadOf(address: String): ByteArray {
        val decoded = ok(CardanoBech32.decode(address))
        return ok(Bech32.convertBits(decoded.toData5BitArray(), 5, 8, pad = false))
    }

    private fun reencode(hrp: CardanoHrp, payload: ByteArray): String {
        val data5 = ok(Bech32.convertBits(payload, 8, 5, pad = true))
        return ok(CardanoBech32.encode(hrp, data5))
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
