package org.sarmidev.kardano.playground.mvi

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.sarmidev.kardano.playground.LabeledRow
import org.sarmidev.kardano.playground.SignedTransactionPresentation
import org.sarmidev.kardano.playground.SubmitTransactionPresentation
import org.sarmidev.kardano.playground.TransactionDraftPresentation
import org.sarmidev.kardano.playground.WalletBalancePresentation
import org.sarmidev.kardano.playground.data.PlaygroundProviderFactory
import org.sarmidev.kardano.playground.domain.BuildTransactionDraftUseCase
import org.sarmidev.kardano.playground.domain.QueryWalletFundsUseCase
import org.sarmidev.kardano.playground.domain.RestoreWalletUseCase
import org.sarmidev.kardano.playground.domain.SignTransactionUseCase
import org.sarmidev.kardano.playground.domain.SubmitTransactionUseCase
import org.sarmidev.kardano.provider.ChainQueryProvider
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * `jvmTest`-only unit tests for [PlaygroundViewModel] (Block 1.12-pre-a).
 *
 * Every SDK-calling use case is faked here — these tests exercise only the ViewModel's own
 * wiring (which use case gets called with which provider, how its result folds into
 * [PlaygroundState] through [PlaygroundReducer]) and never reach `:crypto`'s native backend or
 * a real provider. They live in `jvmTest` (not `commonTest`) only because
 * [androidx.lifecycle.ViewModel.viewModelScope] needs a `Dispatchers.Main` implementation to
 * dispatch on, which `kotlinx-coroutines-test` (already a `jvmTest` dependency) provides via
 * [Dispatchers.setMain] — the same reason [PlaygroundReducerTest] stays `commonTest`-only
 * (pure, non-suspend, no dispatcher needed) while these do not.
 *
 * [UnconfinedTestDispatcher] makes every `viewModelScope.launch` body run eagerly up to its
 * first real suspension point, so a fake use case that returns immediately already has its
 * result folded into [PlaygroundViewModel.state] by the time `dispatch(...)` returns — no
 * `advanceUntilIdle()` needed except where a test explicitly suspends the fake use case (see
 * [queryFunds_setsLoadingWhileTheOperationIsInFlight]).
 */
@OptIn(ExperimentalCoroutinesApi::class)
class PlaygroundViewModelTest {

    @BeforeTest
    fun setUpMainDispatcher() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @AfterTest
    fun tearDownMainDispatcher() {
        Dispatchers.resetMain()
    }

    private fun viewModel(
        queryWalletFunds: QueryWalletFundsUseCase = QueryWalletFundsUseCase.Default,
        buildTransactionDraft: BuildTransactionDraftUseCase = BuildTransactionDraftUseCase.Default,
        signTransaction: SignTransactionUseCase = SignTransactionUseCase.Default,
        submitTransaction: SubmitTransactionUseCase = SubmitTransactionUseCase.Default,
        providerFactory: PlaygroundProviderFactory = PlaygroundProviderFactory(),
    ): PlaygroundViewModel = PlaygroundViewModel(
        restoreWallet = RestoreWalletUseCase.Default,
        queryWalletFunds = queryWalletFunds,
        buildTransactionDraft = buildTransactionDraft,
        signTransaction = signTransaction,
        submitTransaction = submitTransaction,
        providerFactory = providerFactory,
    )

    // --- Query funds ---

    @Test
    fun queryFunds_success_isSurfacedInState() = runTest {
        val expected = WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "5000000 lovelace")))
        val vm = viewModel(queryWalletFunds = QueryWalletFundsUseCase { expected })

        vm.dispatch(PlaygroundIntent.QueryFunds)

        assertEquals(expected, vm.state.value.funds)
    }

    @Test
    fun queryFunds_failure_isSurfacedInState() = runTest {
        val expected = WalletBalancePresentation.Failure("Network mismatch: provider=MAINNET, address=TESTNET")
        val vm = viewModel(queryWalletFunds = QueryWalletFundsUseCase { expected })

        vm.dispatch(PlaygroundIntent.QueryFunds)

        assertEquals(expected, vm.state.value.funds)
    }

    @Test
    fun queryFunds_setsLoadingWhileTheOperationIsInFlight() = runTest {
        val pending = CompletableDeferred<WalletBalancePresentation>()
        val vm = viewModel(queryWalletFunds = QueryWalletFundsUseCase { pending.await() })

        vm.dispatch(PlaygroundIntent.QueryFunds)
        assertEquals(WalletBalancePresentation.Loading, vm.state.value.funds)

        val expected = WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "0 lovelace")))
        pending.complete(expected)
        advanceUntilIdle()

        assertEquals(expected, vm.state.value.funds)
    }

    // --- Build draft ---

    @Test
    fun buildDraft_success_isSurfacedInState() = runTest {
        val expected = TransactionDraftPresentation.Success(listOf(LabeledRow("Fee", "170000 lovelace")))
        val vm = viewModel(buildTransactionDraft = BuildTransactionDraftUseCase { expected })

        vm.dispatch(PlaygroundIntent.BuildDraft)

        assertEquals(expected, vm.state.value.draft)
    }

    @Test
    fun buildDraft_adaOnlyNativeAssetFailure_isSurfacedInState() = runTest {
        // Block 1.11d/1.11d-2 ADA-only filtering message, unchanged by this refactor.
        val message = "This wallet has no ADA-only UTxOs to spend — only UTxOs containing " +
            "native assets/tokens. Phase 1 only builds ADA-only transactions."
        val expected = TransactionDraftPresentation.Failure(message)
        val vm = viewModel(buildTransactionDraft = BuildTransactionDraftUseCase { expected })

        vm.dispatch(PlaygroundIntent.BuildDraft)

        val failure = vm.state.value.draft
        assertEquals(expected, failure)
    }

    // --- Sign ---

    @Test
    fun signTransaction_success_isSurfacedInState() = runTest {
        val expected = SignedTransactionPresentation.Success(listOf(LabeledRow("Witnesses", "1")))
        val vm = viewModel(signTransaction = SignTransactionUseCase { expected })

        vm.dispatch(PlaygroundIntent.SignTransaction)

        assertEquals(expected, vm.state.value.signed)
    }

    @Test
    fun signTransaction_failure_isSurfacedInState() = runTest {
        val expected = SignedTransactionPresentation.Failure("Signing failed: backend failed: boom")
        val vm = viewModel(signTransaction = SignTransactionUseCase { expected })

        vm.dispatch(PlaygroundIntent.SignTransaction)

        assertEquals(expected, vm.state.value.signed)
    }

    // --- Submit ---

    @Test
    fun submitTransaction_successWithMatchingIds_isSurfacedInState() = runTest {
        val expected = SubmitTransactionPresentation.Success(
            listOf(LabeledRow("Ids match", "yes"), LabeledRow("Status", "submitted to preprod")),
        )
        val vm = viewModel(submitTransaction = SubmitTransactionUseCase { _, _ -> expected })

        vm.dispatch(PlaygroundIntent.SubmitTransaction)

        assertEquals(expected, vm.state.value.submit)
    }

    @Test
    fun submitTransaction_successWithMismatchedIds_isSurfacedInState() = runTest {
        val expected = SubmitTransactionPresentation.Success(
            listOf(
                LabeledRow("Ids match", "no"),
                LabeledRow("Note", "Accepted id differs from the locally computed id."),
            ),
        )
        val vm = viewModel(submitTransaction = SubmitTransactionUseCase { _, _ -> expected })

        vm.dispatch(PlaygroundIntent.SubmitTransaction)

        assertEquals(expected, vm.state.value.submit)
    }

    @Test
    fun submitTransaction_failure_isSurfacedInState() = runTest {
        val expected = SubmitTransactionPresentation.Failure(
            "This provider does not support submission (mock) — enable live Blockfrost preprod " +
                "to submit for real.",
        )
        val vm = viewModel(submitTransaction = SubmitTransactionUseCase { _, _ -> expected })

        vm.dispatch(PlaygroundIntent.SubmitTransaction)

        assertEquals(expected, vm.state.value.submit)
    }

    // --- Guided-demo navigation (Block 1.12-pre-e): routes through the reducer, calls no use case ---

    @Test
    fun continueDemo_and_backDemo_routeThroughTheReducerWithoutCallingAnyUseCase() = runTest {
        var useCaseCalls = 0
        val vm = viewModel(
            queryWalletFunds = QueryWalletFundsUseCase {
                useCaseCalls++
                WalletBalancePresentation.Success(emptyList())
            },
        )

        // ContinueDemo is a no-op (Wallet step unresolved) — no use case, no state change.
        vm.dispatch(PlaygroundIntent.ContinueDemo)
        assertEquals(PlaygroundStep.WALLET, vm.state.value.demoStep)
        assertEquals(0, useCaseCalls)

        // BackDemo on the first step is also a no-op.
        vm.dispatch(PlaygroundIntent.BackDemo)
        assertEquals(PlaygroundStep.WALLET, vm.state.value.demoStep)
        assertEquals(0, useCaseCalls)
    }

    @Test
    fun canContinue_isTrueAfterAFakedSuccessfulFundsResult() = runTest {
        val expected = WalletBalancePresentation.Success(listOf(LabeledRow("Test ADA", "5 ADA")))
        val vm = viewModel(queryWalletFunds = QueryWalletFundsUseCase { expected })
        vm.dispatch(PlaygroundIntent.NavigateToDemo)

        // Move the cursor to FUNDS the same way ContinueDemo would once WALLET is resolved.
        vm.dispatch(PlaygroundIntent.QueryFunds)
        assertFalse(PlaygroundDemoFlow.canContinue(vm.state.value.copy(demoStep = PlaygroundStep.WALLET)))

        val fundsResolvedState = vm.state.value.copy(demoStep = PlaygroundStep.FUNDS)
        assertTrue(PlaygroundDemoFlow.canContinue(fundsResolvedState))
    }

    // --- Provider selection wiring ---

    @Test
    fun queryFunds_withDefaultState_usesTheMockProviderFromTheFactory() = runTest {
        val factory = PlaygroundProviderFactory()
        var received: ChainQueryProvider? = null
        val vm = viewModel(
            queryWalletFunds = QueryWalletFundsUseCase { provider ->
                received = provider
                WalletBalancePresentation.Success(emptyList())
            },
            providerFactory = factory,
        )

        vm.dispatch(PlaygroundIntent.QueryFunds)

        val expectedMock = factory.queryProvider(useLive = false, projectId = "")
        assertTrue(received === expectedMock, "expected the same mock provider instance the factory returns")
    }

    @Test
    fun queryFunds_slowResultAfterResetFlow_isDiscarded() = runTest {
        val pending = CompletableDeferred<WalletBalancePresentation>()
        val vm = viewModel(queryWalletFunds = QueryWalletFundsUseCase { pending.await() })

        vm.dispatch(PlaygroundIntent.QueryFunds)
        assertEquals(WalletBalancePresentation.Loading, vm.state.value.funds)
        assertEquals(0L, vm.state.value.flowGeneration)

        vm.dispatch(PlaygroundIntent.ResetFlow)
        assertEquals(WalletBalancePresentation.Empty, vm.state.value.funds)
        assertEquals(1L, vm.state.value.flowGeneration)

        pending.complete(WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "stale"))))
        advanceUntilIdle()

        assertEquals(WalletBalancePresentation.Empty, vm.state.value.funds)
        assertEquals(1L, vm.state.value.flowGeneration)
    }

    @Test
    fun queryFunds_slowResultAfterProviderToggle_isDiscarded() = runTest {
        val pending = CompletableDeferred<WalletBalancePresentation>()
        val vm = viewModel(queryWalletFunds = QueryWalletFundsUseCase { pending.await() })

        vm.dispatch(PlaygroundIntent.QueryFunds)
        assertEquals(WalletBalancePresentation.Loading, vm.state.value.funds)

        vm.dispatch(PlaygroundIntent.ToggleLiveBlockfrost(true))
        assertEquals(WalletBalancePresentation.Empty, vm.state.value.funds)
        assertEquals(1L, vm.state.value.flowGeneration)

        pending.complete(WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "stale"))))
        advanceUntilIdle()

        assertEquals(WalletBalancePresentation.Empty, vm.state.value.funds)
        assertTrue(vm.state.value.useLiveBlockfrost)
    }

    @Test
    fun queryFunds_projectIdChangeDuringRequest_onlyLatestGenerationApplies() = runTest {
        val first = CompletableDeferred<WalletBalancePresentation>()
        val second = CompletableDeferred<WalletBalancePresentation>()
        var calls = 0
        val vm = viewModel(
            queryWalletFunds = QueryWalletFundsUseCase {
                calls++
                if (calls == 1) first.await() else second.await()
            },
        )

        vm.dispatch(PlaygroundIntent.QueryFunds)
        assertEquals(WalletBalancePresentation.Loading, vm.state.value.funds)

        vm.dispatch(PlaygroundIntent.UpdateProjectId("newer-id"))
        assertEquals(WalletBalancePresentation.Empty, vm.state.value.funds)
        assertEquals(1L, vm.state.value.flowGeneration)

        val latest = WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "latest")))
        vm.dispatch(PlaygroundIntent.QueryFunds)
        assertEquals(WalletBalancePresentation.Loading, vm.state.value.funds)
        assertEquals(1L, vm.state.value.flowGeneration)

        first.complete(WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "stale"))))
        advanceUntilIdle()
        assertEquals(WalletBalancePresentation.Loading, vm.state.value.funds)

        second.complete(latest)
        advanceUntilIdle()
        assertEquals(latest, vm.state.value.funds)
        assertEquals(1L, vm.state.value.flowGeneration)
        assertEquals("newer-id", vm.state.value.projectId)
    }

    @Test
    fun queryFunds_afterEnablingLiveBlockfrostWithProjectId_usesTheLiveProviderFromTheFactory() = runTest {
        val factory = PlaygroundProviderFactory()
        var received: ChainQueryProvider? = null
        val vm = viewModel(
            queryWalletFunds = QueryWalletFundsUseCase { provider ->
                received = provider
                WalletBalancePresentation.Success(emptyList())
            },
            providerFactory = factory,
        )

        vm.dispatch(PlaygroundIntent.ToggleLiveBlockfrost(true))
        vm.dispatch(PlaygroundIntent.UpdateProjectId("test-project-id"))
        vm.dispatch(PlaygroundIntent.QueryFunds)

        val expectedLive = factory.queryProvider(useLive = true, projectId = "test-project-id")
        assertTrue(received === expectedLive, "expected the same live provider instance the factory returns")
    }
}
