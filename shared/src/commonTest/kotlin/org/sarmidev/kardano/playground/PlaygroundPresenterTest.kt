package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.address.AddressError
import org.sarmidev.kardano.address.AddressType
import org.sarmidev.kardano.address.PointerField
import org.sarmidev.kardano.encoding.bech32.CardanoBech32Error
import org.sarmidev.kardano.encoding.bech32.CardanoHrp
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.NetworkError
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Unit tests for [PlaygroundPresenter].
 *
 * Error-message tests construct [AddressError] variants **directly** rather than hunting
 * for an input string that triggers each case, so the tests are not fragile with respect to
 * parser internals. A small number of end-to-end tests go through [Address.parse] to
 * confirm the presenter wires the Ok/Err paths correctly.
 *
 * The end-to-end valid vector is copied verbatim from CIP-19:
 * https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md
 */
class PlaygroundPresenterTest {

    // --- presentAddressError: directly-constructed variants ---

    @Test
    fun emptyPayload_containsDescription() {
        val msg = PlaygroundPresenter.presentAddressError(AddressError.EmptyPayload)
        assertTrue(msg.contains("Empty payload", ignoreCase = true), "got: $msg")
    }

    @Test
    fun unsupportedAddressType_containsNibble() {
        // Byron header nibble (8) is the canonical unsupported-type example.
        val msg = PlaygroundPresenter.presentAddressError(AddressError.UnsupportedAddressType(8))
        assertTrue(msg.contains("8"), "got: $msg")
    }

    @Test
    fun hrpNetworkMismatch_containsHrpAndNetwork() {
        val msg = PlaygroundPresenter.presentAddressError(
            AddressError.HrpNetworkMismatch(CardanoHrp.ADDR_TEST, Network.MAINNET),
        )
        assertTrue(msg.contains("addr_test", ignoreCase = true), "got: $msg")
        assertTrue(msg.contains("MAINNET", ignoreCase = true), "got: $msg")
    }

    @Test
    fun hrpFamilyMismatch_containsHrpAndType() {
        val msg = PlaygroundPresenter.presentAddressError(
            AddressError.HrpFamilyMismatch(CardanoHrp.STAKE, AddressType.ENTERPRISE),
        )
        assertTrue(msg.contains("stake", ignoreCase = true), "got: $msg")
        assertTrue(msg.contains("ENTERPRISE", ignoreCase = true), "got: $msg")
    }

    @Test
    fun invalidPayloadLength_containsExpectedAndActual() {
        val msg = PlaygroundPresenter.presentAddressError(
            AddressError.InvalidPayloadLength(AddressType.ENTERPRISE, 29, 30),
        )
        assertTrue(msg.contains("29"), "got: $msg")
        assertTrue(msg.contains("30"), "got: $msg")
    }

    @Test
    fun truncatedPointer_containsPointerDescription() {
        val msg = PlaygroundPresenter.presentAddressError(AddressError.TruncatedPointer)
        assertTrue(msg.contains("pointer", ignoreCase = true), "got: $msg")
    }

    @Test
    fun pointerValueOutOfRange_containsFieldName() {
        val msg = PlaygroundPresenter.presentAddressError(
            AddressError.PointerValueOutOfRange(PointerField.SLOT),
        )
        assertTrue(msg.contains("SLOT", ignoreCase = true), "got: $msg")
    }

    @Test
    fun nonCanonicalPointer_containsFieldName() {
        val msg = PlaygroundPresenter.presentAddressError(
            AddressError.NonCanonicalPointer(PointerField.TRANSACTION_INDEX),
        )
        assertTrue(msg.contains("TRANSACTION_INDEX", ignoreCase = true), "got: $msg")
    }

    @Test
    fun trailingPointerBytes_containsConsumedAndTotal() {
        val msg = PlaygroundPresenter.presentAddressError(
            AddressError.TrailingPointerBytes(consumed = 40, actual = 42),
        )
        assertTrue(msg.contains("40"), "got: $msg")
        assertTrue(msg.contains("42"), "got: $msg")
    }

    @Test
    fun wrappedBech32Error_containsInnerDetail() {
        // Construct the wrapped variant directly; no string parsing needed.
        val msg = PlaygroundPresenter.presentAddressError(
            AddressError.Bech32(CardanoBech32Error.UnsupportedHrp("foo")),
        )
        assertTrue(msg.contains("foo", ignoreCase = true), "got: $msg")
    }

    @Test
    fun wrappedNetworkError_containsId() {
        val msg = PlaygroundPresenter.presentAddressError(
            AddressError.UnsupportedNetworkId(NetworkError.UnsupportedNetworkId(99)),
        )
        assertTrue(msg.contains("99"), "got: $msg")
    }

    // --- End-to-end through Address.parse ---

    /**
     * Happy path: CIP-19 type-06 testnet enterprise (key) address.
     *
     * Vector source: CIP-19 "Test vectors" section, type-06 testnet.
     * https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md
     */
    @Test
    fun happyPath_enterpriseTestnet_producesSuccessRows() {
        // CIP-19 type-06 testnet (enterprise key, testnet)
        val address = "addr_test1vz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerspjrlsz"

        val presentation = PlaygroundPresenter.presentAddress(Address.parse(address))

        assertIs<AddressPresentation.Success>(presentation)
        val labels = presentation.rows.map { it.label }
        val values = presentation.rows.map { it.value }

        assertTrue("Network" in labels, "rows: $labels")
        assertTrue(values.any { it.contains("TESTNET") }, "values: $values")
        assertTrue(values.any { it.contains("ENTERPRISE") }, "values: $values")
        assertTrue(values.any { it.contains("addr_test") }, "values: $values")
    }

    /**
     * CIP-19 type-14 testnet reward (stake key) address — confirms REWARD type and stake
     * credential row are produced.
     *
     * Vector source: CIP-19 "Test vectors" section, type-14 testnet.
     * https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md
     */
    @Test
    fun happyPath_rewardTestnet_producesStakeCredential() {
        val address = "stake_test1uqehkck0lajq8gr28t9uxnuvgcqrc6070x3k9r8048z8y5gssrtvn"

        val presentation = PlaygroundPresenter.presentAddress(Address.parse(address))

        assertIs<AddressPresentation.Success>(presentation)
        val values = presentation.rows.map { it.value }
        assertTrue(values.any { it.contains("REWARD") }, "values: $values")
        assertTrue(values.any { it.contains("TESTNET") }, "values: $values")
    }

    @Test
    fun invalidInput_producesFailureWithMessage() {
        val presentation = PlaygroundPresenter.presentAddress(
            Address.parse("not-a-valid-bech32-address"),
        )

        assertIs<AddressPresentation.Failure>(presentation)
        assertTrue(presentation.message.isNotBlank(), "message should not be blank")
    }

    // --- Empty state ---

    @Test
    fun presentAddress_neverProducesEmpty() {
        // presentAddress always returns Success or Failure; Empty is the initial UI-only state.
        val valid = "addr_test1vz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerspjrlsz"
        val invalid = "not-valid"
        assertFalse(PlaygroundPresenter.presentAddress(Address.parse(valid)) is AddressPresentation.Empty)
        assertFalse(PlaygroundPresenter.presentAddress(Address.parse(invalid)) is AddressPresentation.Empty)
    }
}
