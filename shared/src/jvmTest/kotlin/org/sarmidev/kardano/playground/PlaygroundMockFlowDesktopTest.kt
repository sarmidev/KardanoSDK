package org.sarmidev.kardano.playground

import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.playground.data.PlaygroundProviderFactory
import org.sarmidev.kardano.playground.mvi.PlaygroundDemoFlow
import org.sarmidev.kardano.playground.mvi.PlaygroundState
import org.sarmidev.kardano.playground.mvi.PlaygroundStep
import org.sarmidev.kardano.playground.mvi.StepOutcome
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.wallet.ReadOnlyWallet
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * JVM/desktop-only end-to-end test for the seeded default mock provider (Block 1.12-pre-c-3).
 *
 * Reaches `:crypto`'s native derivation and signing backends via [ReadOnlyWallet], which cannot
 * load under `:shared:testAndroidHostTest` (host JVM, Android target) — the same native-vs-host
 * split [PlaygroundTransactionDraftDesktopTest] documents. Unlike that test (which uses the raw
 * [InMemoryChainQueryProvider] default to assert the honest "no UTxOs" path), this exercises the
 * provider [PlaygroundProviderFactory] actually hands the guided flow in the default mock mode:
 * the demo wallet's own restored address is pre-seeded with fake ADA-only UTxOs, so Funds/Build/
 * Sign all succeed, while Submit still honestly reports "submission not supported".
 *
 * All data here is fake/offline/test-only sample data (see
 * [org.sarmidev.kardano.playground.data.PlaygroundMockSampleData]); nothing touches a network or
 * real funds.
 */
class PlaygroundMockFlowDesktopTest {

    /**
     * The Playground mock seeds the demo wallet's *own* restored address. This locks that
     * consistency: the address the flow queries is the address the mock funds — so the seeding
     * cannot silently regress to "no UTxOs" if derivation output ever shifts.
     */
    @Test
    fun defaultMockProvider_seedsExactlyTheRestoredFixtureAddress() = runTest {
        val wallet = when (val result = ReadOnlyWallet.restore(TestWalletFixture.words, Network.TESTNET)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> error("restore should succeed: ${result.error}")
        }
        val provider = PlaygroundProviderFactory().queryProvider(useLive = false, projectId = "")

        val utxos = when (val result = provider.getUtxos(wallet.address)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> error("mock query should not fail: ${result.error}")
        }

        assertEquals(2, utxos.size, "expected the two seeded fake UTxOs at the restored address")
        assertTrue(utxos.none { it.value.hasNativeAssets }, "seeded demo UTxOs must be ADA-only")
    }

    @Test
    fun defaultMockProvider_reportsNonZeroBalanceForTheDemoWallet() = runTest {
        val provider = PlaygroundProviderFactory().queryProvider(useLive = false, projectId = "")

        val presentation = PlaygroundPresenter.presentWalletBalance(provider)

        val success = assertIs<WalletBalancePresentation.Success>(presentation)
        val rowByLabel = success.rows.associate { it.label to it.value }
        assertEquals("2", rowByLabel["UTxO count"], "expected the two seeded fake UTxOs")
        assertEquals("13000000 lovelace", rowByLabel["Balance"], "expected 5 ADA + 8 ADA seeded")
    }

    @Test
    fun defaultMockProvider_buildsAndSignsPastMissingUtxos() = runTest {
        val provider = PlaygroundProviderFactory().queryProvider(useLive = false, projectId = "")

        val draft = PlaygroundPresenter.presentTransactionDraft(provider)
        val draftSuccess = assertIs<TransactionDraftPresentation.Success>(draft)
        val draftRows = draftSuccess.rows.associate { it.label to it.value }
        assertTrue(draftRows.containsKey("Fee"), "expected a Fee row in the built draft")

        val signed = PlaygroundPresenter.presentSignedTransaction(provider)
        val signedSuccess = assertIs<SignedTransactionPresentation.Success>(signed)
        val signedRows = signedSuccess.rows.associate { it.label to it.value }
        assertTrue(signedRows.containsKey("Transaction id"), "expected a signed Transaction id row")
    }

    @Test
    fun defaultMockProvider_submitReachesTheHonestNotSupportedMessage() = runTest {
        val factory = PlaygroundProviderFactory()
        val queryProvider = factory.queryProvider(useLive = false, projectId = "")
        val submitProvider = factory.submitProvider(useLive = false, projectId = "")

        val presentation = PlaygroundPresenter.presentSubmitTransaction(queryProvider, submitProvider)

        val failure = assertIs<SubmitTransactionPresentation.Failure>(presentation)
        assertTrue(
            failure.message.contains("does not support submission", ignoreCase = true),
            "expected the mock's honest not-supported message, got: ${failure.message}",
        )

        // Block 1.12-pre-e: ties the demo's honest "stopped on purpose" story to this actual
        // presenter output, not a hand-copied literal — see PlaygroundDemoFlowTest for the
        // literal-constant version of this same assertion.
        val state = PlaygroundState.initial().copy(
            demoStep = PlaygroundStep.SUBMIT,
            useLiveBlockfrost = false,
            submit = failure,
        )
        assertEquals(StepOutcome.INFO, PlaygroundDemoFlow.outcome(state, PlaygroundStep.SUBMIT))
    }
}
