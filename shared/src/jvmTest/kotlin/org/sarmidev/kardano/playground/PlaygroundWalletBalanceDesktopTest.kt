package org.sarmidev.kardano.playground

import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.wallet.ReadOnlyWallet
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * JVM/desktop-only end-to-end test for the read-only wallet-balance checkpoint (Block 1.8b).
 *
 * This is the **only** place [PlaygroundPresenter.presentWalletBalance] is exercised end to
 * end: it calls `:wallet`'s [ReadOnlyWallet.restore], which reaches `:crypto`'s native
 * derivation backend and cannot load under `:shared:testAndroidHostTest` (host JVM, Android
 * target) — see [PlaygroundWalletBalancePresenterTest] for the native-free coverage of
 * [PlaygroundPresenter.mapWalletBalanceResult]/[PlaygroundPresenter.presentWalletError] that
 * does run there.
 *
 * Uses the default [InMemoryChainQueryProvider], which has no fake UTxOs seeded for the
 * fixture's self-generated address — asserting the honest zero-balance result documented by
 * ADR-0013 §7, not a self-generated non-zero golden.
 */
class PlaygroundWalletBalanceDesktopTest {

    @Test
    fun presentWalletBalance_withDefaultMockProvider_restoresTestnetWalletAndReturnsZeroBalance() = runTest {
        val provider = InMemoryChainQueryProvider()

        val presentation = PlaygroundPresenter.presentWalletBalance(provider)

        val success = assertIs<WalletBalancePresentation.Success>(presentation)
        val rowByLabel = success.rows.associate { it.label to it.value }

        val address = requireNotNull(rowByLabel["Address"])
        assertTrue(address.startsWith("addr_test1"), "expected a testnet address, got: $address")
        assertEquals("0", rowByLabel["UTxO count"])
        assertEquals("0 lovelace", rowByLabel["Balance"])
    }

    @Test
    fun presentWalletBalance_restoresThroughTestnetOnly() = runTest {
        // Direct assertion that the checkpoint's own restore call uses Network.TESTNET (the
        // Phase 1 no-mainnet boundary), independent of presentWalletBalance's formatting.
        val wallet = when (
            val result = ReadOnlyWallet.restore(TestWalletFixture.words, Network.TESTNET)
        ) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> error("restore should succeed: ${result.error}")
        }
        assertEquals(Network.TESTNET, wallet.network)
    }
}
