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
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * JVM/desktop-only end-to-end test for the unsigned transaction-draft checkpoint (Block 1.9c).
 *
 * This is the **only** place [PlaygroundPresenter.presentTransactionDraft] is exercised end to
 * end: it calls `:wallet`'s [ReadOnlyWallet.restore], which reaches `:crypto`'s native
 * derivation backend and cannot load under `:shared:testAndroidHostTest` (host JVM, Android
 * target) — see [PlaygroundTransactionDraftPresenterTest] for the native-free coverage of
 * [PlaygroundPresenter.mapTransactionDraftResult]/[PlaygroundPresenter.presentTxBuildError] that
 * does run there, and [PlaygroundWalletBalanceDesktopTest]'s KDoc for the same split.
 *
 * Uses the default [InMemoryChainQueryProvider], which has no fake UTxOs seeded for the
 * fixture's self-generated address — asserting the honest "no UTxOs"
 * ([org.sarmidev.kardano.tx.TxBuildError.NoInputs]) result (same ADR-0013 §7 pattern as
 * [PlaygroundWalletBalanceDesktopTest]'s zero balance), not a self-generated draft golden.
 */
class PlaygroundTransactionDraftDesktopTest {

    @Test
    fun presentTransactionDraft_withDefaultMockProvider_reportsNoUtxosAsFailure() = runTest {
        val provider = InMemoryChainQueryProvider()

        val presentation = PlaygroundPresenter.presentTransactionDraft(provider)

        val failure = assertIs<TransactionDraftPresentation.Failure>(presentation)
        assertTrue(failure.message.contains("UTxOs"), "got: ${failure.message}")
    }

    @Test
    fun presentTransactionDraft_withSeededUtxosForRestoredAddress_reportsSuccess() = runTest {
        // Restore the same wallet the checkpoint restores internally, then seed the mock
        // provider with a fake UTxO for exactly that address, so the checkpoint's own
        // getUtxos(wallet.address) call finds it — demonstrating the success path without a
        // live Blockfrost preprod call or an invented golden transaction.
        val wallet = when (val result = ReadOnlyWallet.restore(TestWalletFixture.words, Network.TESTNET)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> error("restore should succeed: ${result.error}")
        }
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { 0x77 }).getOrNull())
        val ref = requireNotNull(UtxoRef.of(txHash, 0L).getOrNull())
        val coin = requireNotNull(Lovelace.of(20_000_000L).getOrNull())
        val seededUtxo = Utxo(ref, Value(coin))
        val provider = InMemoryChainQueryProvider(
            utxosByAddress = mapOf(wallet.address to listOf(seededUtxo)),
        )

        val presentation = PlaygroundPresenter.presentTransactionDraft(provider)

        val success = assertIs<TransactionDraftPresentation.Success>(presentation)
        val rowByLabel = success.rows.associate { it.label to it.value }
        assertTrue(rowByLabel["Selected inputs"] == "1", "got: ${rowByLabel["Selected inputs"]}")
        assertTrue(rowByLabel.containsKey("Fee"), "expected a Fee row")
        assertTrue(rowByLabel.containsKey("Body size"), "expected a Body size row")
    }

    @Test
    fun presentTransactionDraft_withNativeAssetUtxoForRestoredAddress_reportsReadableFailure() = runTest {
        // Block 1.11d: the ADA-only MVP must reject, not silently build around, a UTxO the
        // mock/live provider flagged as carrying native assets/tokens — reproducing (without
        // a live preprod call) the manual Android finding that a funded-but-mixed address
        // caused a preprod ValueNotConservedUTxO rejection at submit time.
        val wallet = when (val result = ReadOnlyWallet.restore(TestWalletFixture.words, Network.TESTNET)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> error("restore should succeed: ${result.error}")
        }
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { 0x99.toByte() }).getOrNull())
        val ref = requireNotNull(UtxoRef.of(txHash, 0L).getOrNull())
        val coin = requireNotNull(Lovelace.of(20_000_000L).getOrNull())
        val nativeAssetUtxo = Utxo(ref, Value(coin, hasNativeAssets = true))
        val provider = InMemoryChainQueryProvider(
            utxosByAddress = mapOf(wallet.address to listOf(nativeAssetUtxo)),
        )

        val presentation = PlaygroundPresenter.presentTransactionDraft(provider)

        val failure = assertIs<TransactionDraftPresentation.Failure>(presentation)
        assertTrue(failure.message.contains("native assets", ignoreCase = true), "got: ${failure.message}")
        assertTrue(failure.message.contains("ADA-only", ignoreCase = true), "got: ${failure.message}")
    }
}
