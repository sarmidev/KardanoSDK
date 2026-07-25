package org.sarmidev.kardano.playground

import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.provider.InMemoryTxSubmitProvider
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.provider.Value
import org.sarmidev.kardano.wallet.ReadOnlyWallet
import kotlin.test.Test
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * JVM/desktop-only end-to-end test for the submit-transaction checkpoint (Block 1.11c).
 *
 * This is the **only** place [PlaygroundPresenter.presentSubmitTransaction] is exercised end to
 * end: like [PlaygroundSignedTransactionDesktopTest] before it, it reaches `:wallet`'s
 * [ReadOnlyWallet.restore]/`ReadOnlyWallet.signTransaction`, which reach `:crypto`'s native
 * derivation/signing backend and cannot load under `:shared:testAndroidHostTest` (host JVM,
 * Android target) — see [PlaygroundSubmitTransactionPresenterTest] for the native-free
 * result-mapping coverage that does run there.
 *
 * Uses [InMemoryTxSubmitProvider] throughout — never a live Blockfrost preprod call — because
 * that provider always returns [org.sarmidev.kardano.provider.SubmitError.SubmissionNotSupported]
 * (Block 1.11a/b), it never fakes an accepted transaction id. That means there is no automated
 * end-to-end *success* path to test here: an actual accepted submission only comes from a real
 * Blockfrost preprod call, which is exactly what these tests must not perform.
 */
class PlaygroundSubmitTransactionDesktopTest {

    @Test
    fun presentSubmitTransaction_withDefaultMockProvider_reportsNoUtxosAsFailure() = runTest {
        val queryProvider = InMemoryChainQueryProvider()
        val submitProvider = InMemoryTxSubmitProvider()

        val presentation = PlaygroundPresenter.presentSubmitTransaction(queryProvider, submitProvider)

        val failure = assertIs<SubmitTransactionPresentation.Failure>(presentation)
        assertTrue(failure.message.contains("UTxOs"), "got: ${failure.message}")
    }

    @Test
    fun presentSubmitTransaction_withSeededUtxosAndMockSubmitProvider_neverFakesSuccess() = runTest {
        // Restore the same wallet the checkpoint restores internally, then seed the mock query
        // provider with a fake UTxO for exactly that address, so the checkpoint's build-and-sign
        // steps succeed and it actually reaches submitProvider.submit(...) — demonstrating that
        // even once signing succeeds, the mock submit provider still reports its honest
        // not-supported failure rather than a fake accepted id.
        val wallet = when (val result = ReadOnlyWallet.restore(TestWalletFixture.words, Network.TESTNET)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> error("restore should succeed: ${result.error}")
        }
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { 0x77.toByte() }).getOrNull())
        val ref = requireNotNull(UtxoRef.of(txHash, 0L).getOrNull())
        val coin = requireNotNull(Lovelace.of(20_000_000L).getOrNull())
        val seededUtxo = Utxo(ref, Value(coin))
        val queryProvider = InMemoryChainQueryProvider(
            utxosByAddress = mapOf(wallet.address to listOf(seededUtxo)),
        )
        val submitProvider = InMemoryTxSubmitProvider()

        val presentation = PlaygroundPresenter.presentSubmitTransaction(queryProvider, submitProvider)

        val failure = assertIs<SubmitTransactionPresentation.Failure>(presentation)
        assertTrue(
            failure.message.contains("not support", ignoreCase = true),
            "expected the mock's explicit not-supported failure, got: ${failure.message}",
        )
    }
}
