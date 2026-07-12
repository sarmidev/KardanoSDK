package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.mnemonic.MnemonicError
import org.sarmidev.kardano.primitives.Network
import kotlin.test.Test
import kotlin.test.assertIs

/**
 * Native-free tests for [ReadOnlyWallet.restore]'s mnemonic-rejection paths.
 *
 * [org.sarmidev.kardano.crypto.mnemonic.Mnemonic.parse] rejects invalid input before
 * [ReadOnlyWallet.restore] ever calls into `:crypto`'s native derivation backend, so these
 * cases run under both `:wallet:jvmTest` and `:wallet:testAndroidHostTest`. See
 * [ReadOnlyWalletRestoreDesktopTest] for the JVM-only end-to-end success path that does reach
 * native code.
 */
class ReadOnlyWalletRestoreMnemonicTest {

    @Test
    fun restore_withInvalidWordCount_returnsMnemonicErrorWithoutReachingNativeCode() {
        val result = ReadOnlyWallet.restore(listOf("test", "walk", "nut", "penalty"), Network.TESTNET)

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val mnemonicError = assertIs<WalletError.Mnemonic>(err.error)
        assertIs<MnemonicError.InvalidWordCount>(mnemonicError.error)
    }

    @Test
    fun restore_withWordNotInWordlist_returnsMnemonicErrorWithoutReachingNativeCode() {
        val words = listOf(
            "test", "walk", "nut", "penalty", "hip", "pave",
            "soap", "entry", "language", "right", "filter", "notaword",
        )

        val result = ReadOnlyWallet.restore(words, Network.TESTNET)

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val mnemonicError = assertIs<WalletError.Mnemonic>(err.error)
        assertIs<MnemonicError.WordNotInWordlist>(mnemonicError.error)
    }
}
