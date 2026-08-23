package org.sarmidev.kardano.playground.mvi

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withContext
import org.sarmidev.kardano.playground.LabeledRow
import org.sarmidev.kardano.playground.PlaygroundProviderMode
import org.sarmidev.kardano.playground.ProviderParamsPresentation
import org.sarmidev.kardano.playground.ProviderUtxosPresentation
import org.sarmidev.kardano.playground.SignedTransactionPresentation
import org.sarmidev.kardano.playground.SubmitTransactionPresentation
import org.sarmidev.kardano.playground.TransactionDraftPresentation
import org.sarmidev.kardano.playground.WalletBalancePresentation
import org.sarmidev.kardano.playground.data.PlaygroundProviderFactory
import org.sarmidev.kardano.playground.domain.BuildTransactionDraftUseCase
import org.sarmidev.kardano.playground.domain.LoadProviderParamsUseCase
import org.sarmidev.kardano.playground.domain.LoadProviderUtxosUseCase
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
import kotlin.test.assertIs
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
        loadProviderUtxos: LoadProviderUtxosUseCase = LoadProviderUtxosUseCase.Default,
        loadProviderParams: LoadProviderParamsUseCase = LoadProviderParamsUseCase.Default,
        providerFactory: PlaygroundProviderFactory = PlaygroundProviderFactory(),
    ): PlaygroundViewModel = PlaygroundViewModel(
        restoreWallet = RestoreWalletUseCase.Default,
        queryWalletFunds = queryWalletFunds,
        buildTransactionDraft = buildTransactionDraft,
        signTransaction = signTransaction,
        submitTransaction = submitTransaction,
        loadProviderUtxos = loadProviderUtxos,
        loadProviderParams = loadProviderParams,
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

        val latest = WalletBalancePresentation.Success(
            rows = listOf(LabeledRow("Balance", "latest")),
            providerMode = PlaygroundProviderMode.Mock,
            flowGeneration = 1L,
        )
        vm.dispatch(PlaygroundIntent.QueryFunds)
        assertEquals(WalletBalancePresentation.Loading, vm.state.value.funds)
        assertEquals(1L, vm.state.value.flowGeneration)

        first.complete(WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "stale"))))
        advanceUntilIdle()
        assertEquals(WalletBalancePresentation.Loading, vm.state.value.funds)

        second.complete(WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "latest"))))
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
        val funds = assertIs<WalletBalancePresentation.Success>(vm.state.value.funds)
        assertEquals(PlaygroundProviderMode.LivePreprod, funds.providerMode)
        assertEquals(vm.state.value.flowGeneration, funds.flowGeneration)
    }

    @Test
    fun queryFunds_defaultState_stampsMockProvenance() = runTest {
        val vm = viewModel(
            queryWalletFunds = QueryWalletFundsUseCase {
                WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "0 lovelace")))
            },
        )

        vm.dispatch(PlaygroundIntent.QueryFunds)

        val funds = assertIs<WalletBalancePresentation.Success>(vm.state.value.funds)
        assertEquals(PlaygroundProviderMode.Mock, funds.providerMode)
        assertEquals(0L, funds.flowGeneration)
        assertEquals(0L, vm.state.value.flowGeneration)
    }

    // --- Non-cooperative cancellation: identity checks discard stale results ---

    @Test
    fun queryFunds_nonCancellableResultAfterResetFlow_isDiscardedByGeneration() = runTest {
        val pending = CompletableDeferred<WalletBalancePresentation>()
        val vm = viewModel(
            queryWalletFunds = QueryWalletFundsUseCase {
                withContext(NonCancellable) { pending.await() }
            },
        )

        vm.dispatch(PlaygroundIntent.QueryFunds)
        assertEquals(WalletBalancePresentation.Loading, vm.state.value.funds)

        vm.dispatch(PlaygroundIntent.ResetFlow)
        assertEquals(WalletBalancePresentation.Empty, vm.state.value.funds)
        assertEquals(1L, vm.state.value.flowGeneration)

        pending.complete(WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "stale"))))
        advanceUntilIdle()

        assertEquals(WalletBalancePresentation.Empty, vm.state.value.funds)
    }

    @Test
    fun queryFunds_nonCancellableResultAfterProviderToggle_isDiscardedByGeneration() = runTest {
        val pending = CompletableDeferred<WalletBalancePresentation>()
        val vm = viewModel(
            queryWalletFunds = QueryWalletFundsUseCase {
                withContext(NonCancellable) { pending.await() }
            },
        )

        vm.dispatch(PlaygroundIntent.QueryFunds)
        vm.dispatch(PlaygroundIntent.ToggleLiveBlockfrost(true))
        assertEquals(WalletBalancePresentation.Empty, vm.state.value.funds)

        pending.complete(WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "stale"))))
        advanceUntilIdle()

        assertEquals(WalletBalancePresentation.Empty, vm.state.value.funds)
        assertTrue(vm.state.value.useLiveBlockfrost)
    }

    @Test
    fun loadProviderUtxos_nonCancellableResultAfterAddressEdit_isDiscarded() = runTest {
        val pending = CompletableDeferred<ProviderUtxosPresentation>()
        val vm = viewModel(
            loadProviderUtxos = LoadProviderUtxosUseCase { _, _ ->
                withContext(NonCancellable) { pending.await() }
            },
        )
        val originalAddress = vm.state.value.providerAddressInput

        vm.dispatch(PlaygroundIntent.LoadProviderUtxos)
        assertEquals(ProviderUtxosPresentation.Loading, vm.state.value.providerUtxos)
        assertEquals(1L, vm.state.value.providerUtxosRequestToken)

        vm.dispatch(PlaygroundIntent.UpdateProviderAddressInput("addr_test1other"))
        assertEquals(ProviderUtxosPresentation.Empty, vm.state.value.providerUtxos)
        assertEquals(2L, vm.state.value.providerUtxosRequestToken)
        assertEquals("addr_test1other", vm.state.value.providerAddressInput)

        pending.complete(
            ProviderUtxosPresentation.Success(listOf(LabeledRow("UTxOs", "stale-for-previous-address"))),
        )
        advanceUntilIdle()

        assertEquals(ProviderUtxosPresentation.Empty, vm.state.value.providerUtxos)
        assertTrue(originalAddress != vm.state.value.providerAddressInput)
    }

    @Test
    fun loadProviderUtxos_nonCancellableResultAfterFillSeedAddress_isDiscarded() = runTest {
        val pending = CompletableDeferred<ProviderUtxosPresentation>()
        val vm = viewModel(
            loadProviderUtxos = LoadProviderUtxosUseCase { _, _ ->
                withContext(NonCancellable) { pending.await() }
            },
        )

        vm.dispatch(PlaygroundIntent.LoadProviderUtxos)
        assertEquals(ProviderUtxosPresentation.Loading, vm.state.value.providerUtxos)

        vm.dispatch(PlaygroundIntent.FillSeedAddress(SeedAddressKind.EMPTY))
        assertEquals(ProviderUtxosPresentation.Empty, vm.state.value.providerUtxos)
        assertEquals(2L, vm.state.value.providerUtxosRequestToken)

        pending.complete(ProviderUtxosPresentation.Success(listOf(LabeledRow("UTxOs", "stale"))))
        advanceUntilIdle()

        assertEquals(ProviderUtxosPresentation.Empty, vm.state.value.providerUtxos)
    }

    @Test
    fun loadProviderUtxos_repeatedNonCancellableLoads_onlyLatestTokenApplies() = runTest {
        val first = CompletableDeferred<ProviderUtxosPresentation>()
        val second = CompletableDeferred<ProviderUtxosPresentation>()
        var calls = 0
        val vm = viewModel(
            loadProviderUtxos = LoadProviderUtxosUseCase { _, _ ->
                withContext(NonCancellable) {
                    calls++
                    if (calls == 1) first.await() else second.await()
                }
            },
        )

        vm.dispatch(PlaygroundIntent.LoadProviderUtxos)
        assertEquals(1L, vm.state.value.providerUtxosRequestToken)
        vm.dispatch(PlaygroundIntent.LoadProviderUtxos)
        assertEquals(2L, vm.state.value.providerUtxosRequestToken)
        assertEquals(ProviderUtxosPresentation.Loading, vm.state.value.providerUtxos)

        first.complete(ProviderUtxosPresentation.Success(listOf(LabeledRow("UTxOs", "stale"))))
        advanceUntilIdle()
        assertEquals(ProviderUtxosPresentation.Loading, vm.state.value.providerUtxos)

        val latest = ProviderUtxosPresentation.Success(listOf(LabeledRow("UTxOs", "latest")))
        second.complete(latest)
        advanceUntilIdle()
        assertEquals(latest, vm.state.value.providerUtxos)
        assertEquals(2L, vm.state.value.providerUtxosRequestToken)
    }

    @Test
    fun loadProviderParams_repeatedNonCancellableLoads_onlyLatestTokenApplies() = runTest {
        val first = CompletableDeferred<ProviderParamsPresentation>()
        val second = CompletableDeferred<ProviderParamsPresentation>()
        var calls = 0
        val vm = viewModel(
            loadProviderParams = LoadProviderParamsUseCase {
                withContext(NonCancellable) {
                    calls++
                    if (calls == 1) first.await() else second.await()
                }
            },
        )

        vm.dispatch(PlaygroundIntent.LoadProviderParams)
        assertEquals(1L, vm.state.value.providerParamsRequestToken)
        vm.dispatch(PlaygroundIntent.LoadProviderParams)
        assertEquals(2L, vm.state.value.providerParamsRequestToken)

        first.complete(ProviderParamsPresentation.Success(listOf(LabeledRow("minFeeA", "stale"))))
        advanceUntilIdle()
        assertEquals(ProviderParamsPresentation.Loading, vm.state.value.providerParams)

        val latest = ProviderParamsPresentation.Success(listOf(LabeledRow("minFeeA", "latest")))
        second.complete(latest)
        advanceUntilIdle()
        assertEquals(latest, vm.state.value.providerParams)
    }

    @Test
    fun loadProviderUtxos_nonCancellableResultAfterResetFlow_isDiscarded() = runTest {
        val pending = CompletableDeferred<ProviderUtxosPresentation>()
        val vm = viewModel(
            loadProviderUtxos = LoadProviderUtxosUseCase { _, _ ->
                withContext(NonCancellable) { pending.await() }
            },
        )

        vm.dispatch(PlaygroundIntent.LoadProviderUtxos)
        assertEquals(ProviderUtxosPresentation.Loading, vm.state.value.providerUtxos)

        vm.dispatch(PlaygroundIntent.ResetFlow)
        assertEquals(ProviderUtxosPresentation.Empty, vm.state.value.providerUtxos)
        assertEquals(2L, vm.state.value.providerUtxosRequestToken)

        pending.complete(ProviderUtxosPresentation.Success(listOf(LabeledRow("UTxOs", "stale"))))
        advanceUntilIdle()

        assertEquals(ProviderUtxosPresentation.Empty, vm.state.value.providerUtxos)
    }

    @Test
    fun loadProviderParams_nonCancellableResultAfterProjectIdChange_isDiscarded() = runTest {
        val pending = CompletableDeferred<ProviderParamsPresentation>()
        val vm = viewModel(
            loadProviderParams = LoadProviderParamsUseCase {
                withContext(NonCancellable) { pending.await() }
            },
        )

        vm.dispatch(PlaygroundIntent.LoadProviderParams)
        assertEquals(ProviderParamsPresentation.Loading, vm.state.value.providerParams)

        vm.dispatch(PlaygroundIntent.UpdateProjectId("newer-id"))
        assertEquals(ProviderParamsPresentation.Empty, vm.state.value.providerParams)
        assertEquals(2L, vm.state.value.providerParamsRequestToken)

        pending.complete(ProviderParamsPresentation.Success(listOf(LabeledRow("minFeeA", "stale"))))
        advanceUntilIdle()

        assertEquals(ProviderParamsPresentation.Empty, vm.state.value.providerParams)
    }

    @Test
    fun resetFlow_preservesCompletedDiagnosticsAndClearsLoading() = runTest {
        val pending = CompletableDeferred<ProviderParamsPresentation>()
        val utxos = ProviderUtxosPresentation.Success(listOf(LabeledRow("UTxOs", "kept")))
        val vm = viewModel(
            loadProviderUtxos = LoadProviderUtxosUseCase { _, _ -> utxos },
            loadProviderParams = LoadProviderParamsUseCase {
                withContext(NonCancellable) { pending.await() }
            },
        )

        vm.dispatch(PlaygroundIntent.LoadProviderUtxos)
        assertEquals(utxos, vm.state.value.providerUtxos)

        vm.dispatch(PlaygroundIntent.LoadProviderParams)
        assertEquals(ProviderParamsPresentation.Loading, vm.state.value.providerParams)

        vm.dispatch(PlaygroundIntent.ResetFlow)
        assertEquals(utxos, vm.state.value.providerUtxos)
        assertEquals(ProviderParamsPresentation.Empty, vm.state.value.providerParams)

        pending.complete(ProviderParamsPresentation.Success(listOf(LabeledRow("minFeeA", "stale"))))
        advanceUntilIdle()
        assertEquals(ProviderParamsPresentation.Empty, vm.state.value.providerParams)
        assertEquals(utxos, vm.state.value.providerUtxos)
    }

    @Test
    fun toggleLiveOff_invalidatesFactoryCacheImmediately() = runTest {
        val factory = PlaygroundProviderFactory()
        val vm = viewModel(providerFactory = factory)

        vm.dispatch(PlaygroundIntent.ToggleLiveBlockfrost(true))
        vm.dispatch(PlaygroundIntent.UpdateProjectId("session-id"))
        val first = factory.queryProvider(useLive = true, projectId = "session-id")

        vm.dispatch(PlaygroundIntent.ToggleLiveBlockfrost(false))
        val second = factory.queryProvider(useLive = true, projectId = "session-id")

        assertTrue(first !== second, "disabling live mode must drop the cache before the next lookup")
    }

    @Test
    fun updateProjectId_invalidatesFactoryCacheImmediately() = runTest {
        val factory = PlaygroundProviderFactory()
        val vm = viewModel(providerFactory = factory)

        vm.dispatch(PlaygroundIntent.ToggleLiveBlockfrost(true))
        vm.dispatch(PlaygroundIntent.UpdateProjectId("session-id-a"))
        val first = factory.queryProvider(useLive = true, projectId = "session-id-a")

        vm.dispatch(PlaygroundIntent.UpdateProjectId("session-id-b"))
        val rebuilt = factory.queryProvider(useLive = true, projectId = "session-id-a")

        assertTrue(first !== rebuilt, "an actual project-id change must drop the cache immediately")
    }
}
