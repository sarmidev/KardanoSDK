package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.crypto.mnemonic.MnemonicError
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.tx.TransactionBodyRequest
import org.sarmidev.kardano.tx.TransactionBodySerializer
import org.sarmidev.kardano.tx.TransactionDraft
import org.sarmidev.kardano.tx.TransactionOutput
import kotlin.test.Test
import kotlin.test.assertIs
import kotlin.test.fail

/**
 * Native-free tests for [ReadOnlyWallet.signTransaction]'s mnemonic-rejection paths.
 *
 * [org.sarmidev.kardano.crypto.mnemonic.Mnemonic.parse] rejects invalid input before
 * [ReadOnlyWallet.signTransaction] ever calls into `:crypto`'s native derivation/signing
 * backends, so these cases run under both `:wallet:jvmTest` and
 * `:wallet:testAndroidHostTest`, mirroring [ReadOnlyWalletRestoreMnemonicTest]. See
 * [ReadOnlyWalletSignTransactionDesktopTest] for the JVM-only end-to-end success path that does
 * reach native code.
 *
 * The [TransactionDraft] fixture reuses the CIP-19 "Test vectors" testnet base (type-00)
 * address already cited verbatim in `:core`'s `AddressTest`, mirroring
 * `TransactionBodySerializerTest`. Building it needs no native cryptography (`:tx` is
 * crypto-free).
 */
class ReadOnlyWalletSignTransactionMnemonicTest {

    private companion object {
        const val TESTNET_TYPE_00 =
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"
    }

    private fun fixtureDraft(): TransactionDraft {
        val address = requireNotNull(Address.parse(TESTNET_TYPE_00).getOrNull())
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { 1 }).getOrNull())
        val utxoRef = requireNotNull(UtxoRef.of(txHash, 0L).getOrNull())
        val fee = requireNotNull(Lovelace.of(170_000L).getOrNull())
        val output = TransactionOutput(address, requireNotNull(Lovelace.of(2_000_000L).getOrNull()))
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef),
            outputs = listOf(output),
            fee = fee,
        )
        return when (val result = TransactionBodySerializer.serialize(request)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected a valid fixture draft but got Err(${result.error})")
        }
    }

    @Test
    fun signTransaction_withInvalidWordCount_returnsMnemonicErrorWithoutReachingNativeCode() {
        val result = ReadOnlyWallet.signTransaction(
            listOf("test", "walk", "nut", "penalty"),
            Network.TESTNET,
            fixtureDraft(),
        )

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val mnemonicError = assertIs<WalletError.Mnemonic>(err.error)
        assertIs<MnemonicError.InvalidWordCount>(mnemonicError.error)
    }

    @Test
    fun signTransaction_withWordNotInWordlist_returnsMnemonicErrorWithoutReachingNativeCode() {
        val words = listOf(
            "test", "walk", "nut", "penalty", "hip", "pave",
            "soap", "entry", "language", "right", "filter", "notaword",
        )

        val result = ReadOnlyWallet.signTransaction(words, Network.TESTNET, fixtureDraft())

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val mnemonicError = assertIs<WalletError.Mnemonic>(err.error)
        assertIs<MnemonicError.WordNotInWordlist>(mnemonicError.error)
    }
}
