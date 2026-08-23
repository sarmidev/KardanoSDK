package org.sarmidev.kardano.playground

import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.provider.Value
import org.sarmidev.kardano.wallet.ReadOnlyWallet
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * JVM/desktop-only end-to-end test for the signed-transaction checkpoint (Block 1.10c).
 *
 * This is the **only** place [PlaygroundPresenter.presentSignedTransaction] is exercised end to
 * end: it calls `:wallet`'s [ReadOnlyWallet.restore]/`ReadOnlyWallet.signTestnetFixtureTransaction`,
 * which reach `:crypto`'s native derivation/signing backend and cannot load under
 * `:shared:testAndroidHostTest` (host JVM, Android target) — see
 * [PlaygroundSignedTransactionPresenterTest] for the native-free error-mapping coverage that
 * does run there, and [PlaygroundTransactionDraftDesktopTest]'s KDoc for the same split applied
 * to the unsigned draft checkpoint.
 *
 * Uses the default [InMemoryChainQueryProvider] for the "no UTxOs" case, and a provider seeded
 * with a fake UTxO for the fixture's own restored address for the success case — same technique
 * as [PlaygroundTransactionDraftDesktopTest], not a self-generated draft/signature golden.
 */
class PlaygroundSignedTransactionDesktopTest {

    @Test
    fun presentSignedTransaction_withDefaultMockProvider_reportsNoUtxosAsFailure() = runTest {
        val provider = InMemoryChainQueryProvider()

        val presentation = PlaygroundPresenter.presentSignedTransaction(provider)

        val failure = assertIs<SignedTransactionPresentation.Failure>(presentation)
        assertTrue(failure.message.contains("UTxOs"), "got: ${failure.message}")
    }

    @Test
    fun presentSignedTransaction_withSeededUtxosForRestoredAddress_reportsSuccess() = runTest {
        // Restore the same wallet the checkpoint restores internally, then seed the mock
        // provider with a fake UTxO for exactly that address, so the checkpoint's own
        // getUtxos(wallet.address) call finds it — demonstrating the sign-and-display success
        // path without a live Blockfrost preprod call or an invented golden signature.
        val wallet = when (val result = ReadOnlyWallet.restore(TestWalletFixture.words, Network.TESTNET)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> error("restore should succeed: ${result.error}")
        }
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { 0x88.toByte() }).getOrNull())
        val ref = requireNotNull(UtxoRef.of(txHash, 0L).getOrNull())
        val coin = requireNotNull(Lovelace.of(20_000_000L).getOrNull())
        val seededUtxo = Utxo(ref, Value(coin))
        val provider = InMemoryChainQueryProvider(
            utxosByAddress = mapOf(wallet.address to listOf(seededUtxo)),
        )

        val presentation = PlaygroundPresenter.presentSignedTransaction(provider)

        val success = assertIs<SignedTransactionPresentation.Success>(presentation)
        val rowByLabel = success.rows.associate { it.label to it.value }

        val transactionId = requireNotNull(rowByLabel["Transaction id"])
        assertEquals(64, transactionId.length, "expected a 32-byte hex transaction id, got: $transactionId")
        assertTrue(transactionId.all { it.isDigit() || it in 'a'..'f' }, "not lowercase hex: $transactionId")

        assertEquals("1", rowByLabel["Witnesses"], "expected exactly one witness")

        val cborPreview = requireNotNull(rowByLabel["Signed tx CBOR (preview)"])
        assertTrue(cborPreview.contains("…") && cborPreview.contains("B total)"), "got: $cborPreview")

        assertEquals(
            "signed, not submitted — testnet-only, test fixture, no real funds",
            rowByLabel["Status"],
        )

        // Never the mnemonic, seed, private key, or full (untruncated) signed CBOR. Checked only
        // against the hex-bearing fields (the label text is free-form English and would trivially
        // "contain" short fixture words like "test" as substrings of unrelated words).
        val hexFields = listOf(transactionId, cborPreview)
        for (word in TestWalletFixture.words) {
            for (field in hexFields) {
                assertFalse(field.contains(word), "leaked fixture mnemonic word '$word' in: $field")
            }
        }
        assertTrue(cborPreview.contains("…"), "expected the CBOR preview to be truncated, got: $cborPreview")
    }
}
