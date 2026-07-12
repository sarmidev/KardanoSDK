package org.sarmidev.kardano.playground

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * JVM/desktop-only end-to-end test for the test-wallet derivation checkpoint (Block 1.6d).
 *
 * This is the **only** place [PlaygroundPresenter.presentTestWallet] is exercised end to end:
 * it reaches `:crypto`'s native derivation and public-key-projection backends, which cannot
 * load under `:shared:testAndroidHostTest` (host JVM, Android target) — see
 * [PlaygroundWalletPresenterTest] for the native-free coverage that does run there.
 *
 * The golden fingerprint is the CIP-19 payment credential cited in Block 1.5b's
 * `HashingVectorsTest` and reproduced end to end by `:crypto`'s
 * `PublicKeyProjectionDeviceTest` for the same mnemonic and path.
 */
class PlaygroundWalletDerivationDesktopTest {

    @Test
    fun presentTestWallet_matchesGoldenPathAndFingerprint() {
        val presentation = PlaygroundPresenter.presentTestWallet()

        assertIs<WalletPresentation.Success>(presentation)
        assertTrue(presentation.fingerprintMatchesVector, "fingerprint should match the cited vector")

        val rowByLabel = presentation.rows.associate { it.label to it.value }
        assertEquals("m/1852'/1815'/0'/0/0", rowByLabel["Path"])
        assertEquals(
            "9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e",
            rowByLabel["Fingerprint (Blake2b-224)"],
        )
    }
}
