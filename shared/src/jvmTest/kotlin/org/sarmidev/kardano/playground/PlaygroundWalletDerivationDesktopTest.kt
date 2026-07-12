package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.address.AddressType
import org.sarmidev.kardano.primitives.Network
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * JVM/desktop-only end-to-end test for the test-wallet + address-generation checkpoint
 * (Block 1.6d, extended by Block 1.7b).
 *
 * This is the **only** place [PlaygroundPresenter.presentTestWallet] is exercised end to end:
 * it reaches `:crypto`'s native derivation and public-key-projection backends, which cannot
 * load under `:shared:testAndroidHostTest` (host JVM, Android target) — see
 * [PlaygroundWalletPresenterTest] for the native-free coverage that does run there.
 *
 * The golden payment-credential fingerprint is the CIP-19 payment credential cited in Block
 * 1.5b's `HashingVectorsTest` and reproduced end to end by `:crypto`'s
 * `PublicKeyProjectionDeviceTest` for the same mnemonic and path. There is no externally cited
 * golden for the stake credential or for a full generated `addr_test` string (see
 * [TestWalletFixture]'s KDoc): this test asserts only the cited payment credential plus a
 * structural generate-then-parse round trip, never a self-generated address as if it were an
 * external vector.
 */
class PlaygroundWalletDerivationDesktopTest {

    @Test
    fun presentTestWallet_matchesGoldenPathsFingerprintAndGeneratesRoundtrippingAddress() {
        val presentation = PlaygroundPresenter.presentTestWallet()

        assertIs<WalletPresentation.Success>(presentation)
        assertTrue(presentation.fingerprintMatchesVector, "fingerprint should match the cited vector")

        val rowByLabel = presentation.rows.associate { it.label to it.value }
        assertEquals("m/1852'/1815'/0'/0/0", rowByLabel["Payment path"])
        assertEquals("m/1852'/1815'/0'/2/0", rowByLabel["Stake path"])
        assertEquals(
            "9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e",
            rowByLabel["Payment credential (Blake2b-224)"],
        )
        assertEquals("ok", rowByLabel["Address round-trip"])

        val generatedAddress = requireNotNull(rowByLabel["Generated address"])
        assertTrue(
            generatedAddress.startsWith("addr_test1"),
            "expected a testnet base address, got: $generatedAddress",
        )

        val parsed = when (val result = Address.parse(generatedAddress)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> error("generated address should re-parse, got: ${result.error}")
        }
        assertEquals(Network.TESTNET, parsed.network)
        assertEquals(AddressType.BASE, parsed.type)
    }
}
