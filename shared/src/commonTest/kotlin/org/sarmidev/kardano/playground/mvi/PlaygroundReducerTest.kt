package org.sarmidev.kardano.playground.mvi

import org.sarmidev.kardano.playground.LabeledRow
import org.sarmidev.kardano.playground.MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE
import org.sarmidev.kardano.playground.ProviderParamsPresentation
import org.sarmidev.kardano.playground.ProviderUtxosPresentation
import org.sarmidev.kardano.playground.SignedTransactionPresentation
import org.sarmidev.kardano.playground.SubmitTransactionPresentation
import org.sarmidev.kardano.playground.TransactionDraftPresentation
import org.sarmidev.kardano.playground.WalletBalancePresentation
import org.sarmidev.kardano.playground.WalletPresentation
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Unit tests for [PlaygroundReducer] (Block 1.12-pre-a).
 *
 * [PlaygroundReducer] is pure and non-suspend, so every test here constructs a
 * [PlaygroundState] and/or a `*Presentation` value directly and calls [PlaygroundReducer]
 * functions synchronously — no coroutine, no native backend, no provider call. This runs on
 * every target, including `:shared:testAndroidHostTest`, the same native-backend constraint
 * [org.sarmidev.kardano.playground.PlaygroundWalletPresenterTest] documents.
 */
class PlaygroundReducerTest {

    // --- Default mock initial state ---

    @Test
    fun initialState_defaultsToMockAndEmptyEverySteps() {
        val state = PlaygroundState.initial()

        assertFalse(state.useLiveBlockfrost)
        assertEquals("", state.projectId)
        assertEquals(0L, state.flowGeneration)
        assertEquals(0L, state.providerUtxosRequestToken)
        assertEquals(0L, state.providerParamsRequestToken)
        assertEquals(0L, state.fundsRequestToken)
        assertEquals(0L, state.draftRequestToken)
        assertEquals(0L, state.signedRequestToken)
        assertEquals(0L, state.submitRequestToken)
        assertEquals(WalletPresentation.Empty, state.wallet)
        assertFalse(state.walletLoading)
        assertEquals(WalletBalancePresentation.Empty, state.funds)
        assertEquals(TransactionDraftPresentation.Empty, state.draft)
        assertEquals(SignedTransactionPresentation.Empty, state.signed)
        assertEquals(SubmitTransactionPresentation.Empty, state.submit)
        assertTrue(state.technicalDetailsExpanded.isEmpty())
        assertEquals(InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS, state.providerAddressInput)
        assertFalse(state.codeExamplesExpanded)
        assertEquals(PlaygroundSection.WELCOME, state.section)
        assertEquals(RoadmapPhase.PHASE_1, state.selectedRoadmapPhase)
        assertEquals(PlaygroundStep.WALLET, state.demoStep)
    }

    // --- Section navigation (Block 1.12-pre-c-2, restructured in Block 1.12-pre-e) ---

    @Test
    fun navigationIntents_switchSectionOnly() {
        val state = PlaygroundState.initial()

        val demo = PlaygroundReducer.reduce(state, PlaygroundIntent.NavigateToDemo)
        assertEquals(PlaygroundSection.DEMO, demo.section)
        // Navigation touches nothing but the section.
        assertEquals(state.copy(section = PlaygroundSection.DEMO), demo)

        val roadmap = PlaygroundReducer.reduce(demo, PlaygroundIntent.NavigateToRoadmap)
        assertEquals(PlaygroundSection.ROADMAP, roadmap.section)

        val about = PlaygroundReducer.reduce(roadmap, PlaygroundIntent.NavigateToAbout)
        assertEquals(PlaygroundSection.ABOUT, about.section)

        val summary = PlaygroundReducer.reduce(about, PlaygroundIntent.NavigateToSummary)
        assertEquals(PlaygroundSection.SUMMARY, summary.section)

        val welcome = PlaygroundReducer.reduce(summary, PlaygroundIntent.NavigateToWelcome)
        assertEquals(PlaygroundSection.WELCOME, welcome.section)
    }

    // --- Guided-demo cursor: ContinueDemo / BackDemo (Block 1.12-pre-e) ---

    @Test
    fun continueDemo_isNoOpWhileTheCurrentStepIsUnresolved() {
        val state = PlaygroundState.initial()
        assertEquals(PlaygroundStep.WALLET, state.demoStep)

        val next = PlaygroundReducer.reduce(state, PlaygroundIntent.ContinueDemo)

        assertEquals(state, next)
    }

    @Test
    fun continueDemo_advancesToTheNextStepOnceTheCurrentStepIsDone() {
        val walletDone = PlaygroundState.initial().copy(
            wallet = WalletPresentation.Success(
                rows = listOf(LabeledRow("Generated address", "addr_test1abc")),
                fingerprintMatchesVector = true,
            ),
        )

        val next = PlaygroundReducer.reduce(walletDone, PlaygroundIntent.ContinueDemo)

        assertEquals(PlaygroundStep.FUNDS, next.demoStep)
        assertEquals(PlaygroundSection.WELCOME, next.section, "Continuing a step must not change section")
    }

    @Test
    fun continueDemo_advancesOnTheHonestMockStopInfoOutcome() {
        val mockStopped = PlaygroundState.initial().copy(
            demoStep = PlaygroundStep.SUBMIT,
            submit = SubmitTransactionPresentation.Failure(MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE),
        )

        val next = PlaygroundReducer.reduce(mockStopped, PlaygroundIntent.ContinueDemo)

        assertEquals(PlaygroundSection.SUMMARY, next.section)
    }

    @Test
    fun continueDemo_fromTheLastStepMovesToSummaryInsteadOfAdvancingDemoStep() {
        val submitDone = PlaygroundState.initial().copy(
            demoStep = PlaygroundStep.SUBMIT,
            submit = SubmitTransactionPresentation.Success(
                listOf(LabeledRow("Ids match", "yes")),
            ),
        )

        val next = PlaygroundReducer.reduce(submitDone, PlaygroundIntent.ContinueDemo)

        assertEquals(PlaygroundStep.SUBMIT, next.demoStep)
        assertEquals(PlaygroundSection.SUMMARY, next.section)
    }

    @Test
    fun continueDemo_doesNotAdvanceOnAnErrorOutcome() {
        val errored = PlaygroundState.initial().copy(
            wallet = WalletPresentation.Failure("boom"),
        )

        val next = PlaygroundReducer.reduce(errored, PlaygroundIntent.ContinueDemo)

        assertEquals(errored, next)
    }

    @Test
    fun backDemo_isNoOpOnTheFirstStep() {
        val state = PlaygroundState.initial()

        val next = PlaygroundReducer.reduce(state, PlaygroundIntent.BackDemo)

        assertEquals(state, next)
    }

    @Test
    fun backDemo_stepsBackWithoutClearingResults() {
        val walletDone = WalletPresentation.Success(
            rows = listOf(LabeledRow("Generated address", "addr_test1abc")),
            fingerprintMatchesVector = true,
        )
        val onFunds = PlaygroundState.initial().copy(
            demoStep = PlaygroundStep.FUNDS,
            wallet = walletDone,
        )

        val back = PlaygroundReducer.reduce(onFunds, PlaygroundIntent.BackDemo)

        assertEquals(PlaygroundStep.WALLET, back.demoStep)
        assertEquals(walletDone, back.wallet, "going back must not clear the wallet step's result")
    }

    // --- Roadmap phase selection: tap to expand, tap again to collapse ---

    @Test
    fun selectRoadmapPhase_selectsNewPhaseThenTogglesItOff() {
        val state = PlaygroundState.initial()
        assertEquals(RoadmapPhase.PHASE_1, state.selectedRoadmapPhase)

        val phase2 = PlaygroundReducer.reduce(
            state,
            PlaygroundIntent.SelectRoadmapPhase(RoadmapPhase.PHASE_2),
        )
        assertEquals(RoadmapPhase.PHASE_2, phase2.selectedRoadmapPhase)

        // Tapping the already-selected phase collapses its detail.
        val collapsed = PlaygroundReducer.reduce(
            phase2,
            PlaygroundIntent.SelectRoadmapPhase(RoadmapPhase.PHASE_2),
        )
        assertNull(collapsed.selectedRoadmapPhase)

        val phase0 = PlaygroundReducer.reduce(
            collapsed,
            PlaygroundIntent.SelectRoadmapPhase(RoadmapPhase.PHASE_0),
        )
        assertEquals(RoadmapPhase.PHASE_0, phase0.selectedRoadmapPhase)
    }

    // --- Provider selection: project id + live toggle ---

    @Test
    fun updateProjectId_sameValue_isNoOp() {
        val state = PlaygroundState.initial().copy(projectId = "abc123", flowGeneration = 4L)

        val next = PlaygroundReducer.reduce(state, PlaygroundIntent.UpdateProjectId("abc123"))

        assertEquals(state, next)
    }

    @Test
    fun updateProjectId_actualChange_incrementsGenerationAndClearsProviderResults() {
        val dirty = PlaygroundState.initial().copy(
            funds = WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "0 lovelace"))),
            draft = TransactionDraftPresentation.Failure("stale draft"),
            signed = SignedTransactionPresentation.Loading,
            submit = SubmitTransactionPresentation.Loading,
            providerUtxos = ProviderUtxosPresentation.Loading,
            providerParams = ProviderParamsPresentation.Loading,
            wallet = WalletPresentation.Success(
                rows = listOf(LabeledRow("Generated address", "addr_test1abc")),
                fingerprintMatchesVector = true,
            ),
            flowGeneration = 2L,
        )

        val next = PlaygroundReducer.reduce(dirty, PlaygroundIntent.UpdateProjectId("abc123"))

        assertEquals("abc123", next.projectId)
        assertEquals(3L, next.flowGeneration)
        assertEquals(1L, next.fundsRequestToken)
        assertEquals(1L, next.draftRequestToken)
        assertEquals(1L, next.signedRequestToken)
        assertEquals(1L, next.submitRequestToken)
        assertEquals(1L, next.providerUtxosRequestToken)
        assertEquals(1L, next.providerParamsRequestToken)
        assertEquals(WalletBalancePresentation.Empty, next.funds)
        assertEquals(TransactionDraftPresentation.Empty, next.draft)
        assertEquals(SignedTransactionPresentation.Empty, next.signed)
        assertEquals(SubmitTransactionPresentation.Empty, next.submit)
        assertEquals(ProviderUtxosPresentation.Empty, next.providerUtxos)
        assertEquals(ProviderParamsPresentation.Empty, next.providerParams)
        assertEquals(dirty.wallet, next.wallet, "wallet restore is local and must survive a project-id change")
    }

    @Test
    fun toggleLiveBlockfrost_sameValue_isNoOp() {
        val state = PlaygroundState.initial().copy(useLiveBlockfrost = true, flowGeneration = 1L)

        val next = PlaygroundReducer.reduce(state, PlaygroundIntent.ToggleLiveBlockfrost(true))

        assertEquals(state, next)
    }

    @Test
    fun toggleLiveBlockfrost_actualChange_incrementsGenerationAndClearsProviderResults() {
        val dirty = PlaygroundState.initial().copy(
            projectId = "abc123",
            funds = WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "0 lovelace"))),
            draft = TransactionDraftPresentation.Success(listOf(LabeledRow("Fee", "1"))),
            flowGeneration = 0L,
        )

        val next = PlaygroundReducer.reduce(dirty, PlaygroundIntent.ToggleLiveBlockfrost(true))

        assertTrue(next.useLiveBlockfrost)
        assertEquals("abc123", next.projectId)
        assertEquals(1L, next.flowGeneration)
        assertEquals(1L, next.fundsRequestToken)
        assertEquals(1L, next.draftRequestToken)
        assertEquals(1L, next.signedRequestToken)
        assertEquals(1L, next.submitRequestToken)
        assertEquals(1L, next.providerUtxosRequestToken)
        assertEquals(1L, next.providerParamsRequestToken)
        assertEquals(WalletBalancePresentation.Empty, next.funds)
        assertEquals(TransactionDraftPresentation.Empty, next.draft)

        val backOff = PlaygroundReducer.reduce(next, PlaygroundIntent.ToggleLiveBlockfrost(false))
        assertFalse(backOff.useLiveBlockfrost)
        assertEquals(2L, backOff.flowGeneration)
        assertEquals(2L, backOff.fundsRequestToken)
        assertEquals(2L, backOff.draftRequestToken)
        assertEquals(2L, backOff.signedRequestToken)
        assertEquals(2L, backOff.submitRequestToken)
        assertEquals(2L, backOff.providerUtxosRequestToken)
        assertEquals(2L, backOff.providerParamsRequestToken)
    }

    // --- Technical details toggling ---

    @Test
    fun toggleTechnicalDetails_expandsThenCollapsesOnlyThatStep() {
        val state = PlaygroundState.initial()

        val expanded = PlaygroundReducer.reduce(
            state,
            PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.FUNDS),
        )
        assertEquals(setOf(PlaygroundStep.FUNDS), expanded.technicalDetailsExpanded)

        val stillExpandedForOtherStep = PlaygroundReducer.reduce(
            expanded,
            PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.SIGN),
        )
        assertEquals(
            setOf(PlaygroundStep.FUNDS, PlaygroundStep.SIGN),
            stillExpandedForOtherStep.technicalDetailsExpanded,
        )

        val collapsedFunds = PlaygroundReducer.reduce(
            stillExpandedForOtherStep,
            PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.FUNDS),
        )
        assertEquals(setOf(PlaygroundStep.SIGN), collapsedFunds.technicalDetailsExpanded)
    }

    // --- Landing "Code examples" toggle (Block 1.12-pre-c) ---

    @Test
    fun toggleCodeExamples_flipsFlagAndTouchesNothingElse() {
        val state = PlaygroundState.initial()

        val expanded = PlaygroundReducer.reduce(state, PlaygroundIntent.ToggleCodeExamples)
        assertTrue(expanded.codeExamplesExpanded)
        // The landing toggle is presentation-only: it leaves the rest of the state untouched.
        assertEquals(state.copy(codeExamplesExpanded = true), expanded)

        val collapsed = PlaygroundReducer.reduce(expanded, PlaygroundIntent.ToggleCodeExamples)
        assertFalse(collapsed.codeExamplesExpanded)
        assertEquals(state, collapsed)
    }

    // --- Reset flow: clears guided-flow results, keeps provider config + diagnostics ---

    @Test
    fun resetFlow_clearsGuidedStepsButKeepsProviderConfigAndDiagnostics() {
        val walletRow = LabeledRow("Generated address", "addr_test1abc")
        val dirty = PlaygroundState.initial().copy(
            useLiveBlockfrost = true,
            projectId = "abc123",
            wallet = WalletPresentation.Success(listOf(walletRow), fingerprintMatchesVector = true),
            walletLoading = true,
            funds = WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "0 lovelace"))),
            draft = TransactionDraftPresentation.Failure("No UTxOs available to build a transaction from."),
            signed = SignedTransactionPresentation.Loading,
            submit = SubmitTransactionPresentation.Loading,
            technicalDetailsExpanded = setOf(PlaygroundStep.BUILD),
            addressInput = "addr_test1xyz",
            providerAddressInput = InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY,
            demoStep = PlaygroundStep.SUBMIT,
            section = PlaygroundSection.SUMMARY,
        )

        val reset = PlaygroundReducer.reduce(dirty, PlaygroundIntent.ResetFlow)

        assertEquals(WalletPresentation.Empty, reset.wallet)
        assertFalse(reset.walletLoading)
        assertEquals(WalletBalancePresentation.Empty, reset.funds)
        assertEquals(TransactionDraftPresentation.Empty, reset.draft)
        assertEquals(SignedTransactionPresentation.Empty, reset.signed)
        assertEquals(SubmitTransactionPresentation.Empty, reset.submit)

        // ResetFlow (Block 1.12-pre-e) also returns the guided-demo cursor to the start.
        assertEquals(PlaygroundStep.WALLET, reset.demoStep)
        assertEquals(PlaygroundSection.DEMO, reset.section)

        // Provider config and diagnostics input/expanded-details are preserved.
        assertTrue(reset.useLiveBlockfrost)
        assertEquals("abc123", reset.projectId)
        assertEquals(setOf(PlaygroundStep.BUILD), reset.technicalDetailsExpanded)
        assertEquals("addr_test1xyz", reset.addressInput)
        assertEquals(InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY, reset.providerAddressInput)
        assertEquals(1L, reset.flowGeneration, "ResetFlow must bump generation so in-flight results are stale")
        assertEquals(1L, reset.fundsRequestToken)
        assertEquals(1L, reset.draftRequestToken)
        assertEquals(1L, reset.signedRequestToken)
        assertEquals(1L, reset.submitRequestToken)
        assertEquals(1L, reset.providerUtxosRequestToken)
        assertEquals(1L, reset.providerParamsRequestToken)
    }

    @Test
    fun resetFlow_convertsDiagnosticLoadingToEmptyButKeepsCompletedResults() {
        val utxosDone = ProviderUtxosPresentation.Success(listOf(LabeledRow("UTxOs", "2")))
        val dirty = PlaygroundState.initial().copy(
            providerUtxos = utxosDone,
            providerParams = ProviderParamsPresentation.Loading,
            providerUtxosRequestToken = 4L,
            providerParamsRequestToken = 2L,
        )

        val reset = PlaygroundReducer.reduce(dirty, PlaygroundIntent.ResetFlow)

        assertEquals(utxosDone, reset.providerUtxos, "completed UTxO result must survive ResetFlow")
        assertEquals(ProviderParamsPresentation.Empty, reset.providerParams)
        assertEquals(5L, reset.providerUtxosRequestToken)
        assertEquals(3L, reset.providerParamsRequestToken)
    }

    @Test
    fun applyFundsResult_staleGeneration_isIgnored() {
        val result = WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "1 lovelace")))
        val current = PlaygroundState.initial().copy(flowGeneration = 3L)

        val next = PlaygroundReducer.applyFundsResult(current, result, generation = 2L)

        assertEquals(current, next)
    }

    @Test
    fun applyFundsResult_currentGeneration_isApplied() {
        val result = WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "1 lovelace")))
        val current = PlaygroundState.initial().copy(flowGeneration = 3L)

        val next = PlaygroundReducer.applyFundsResult(current, result, generation = 3L)

        assertEquals(result, next.funds)
        assertEquals(3L, next.flowGeneration)
    }

    @Test
    fun applyFundsResult_staleToken_isIgnored() {
        val result = WalletBalancePresentation.Success(listOf(LabeledRow("Balance", "stale")))
        val current = PlaygroundState.initial().copy(fundsRequestToken = 3L)

        val next = PlaygroundReducer.applyFundsResult(current, result, requestToken = 2L)

        assertEquals(current, next)
    }

    // --- Diagnostics text inputs + seed fill ---

    @Test
    fun updateAddressInput_updatesOnlyAddressInput() {
        val state = PlaygroundState.initial()
        val next = PlaygroundReducer.reduce(state, PlaygroundIntent.UpdateAddressInput("addr_test1abc"))
        assertEquals("addr_test1abc", next.addressInput)
    }

    @Test
    fun fillSeedAddress_withUtxos_setsProviderAddressInputToWithUtxosVector() {
        val state = PlaygroundState.initial().copy(providerAddressInput = "")
        val next = PlaygroundReducer.reduce(
            state,
            PlaygroundIntent.FillSeedAddress(SeedAddressKind.WITH_UTXOS),
        )
        assertEquals(InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS, next.providerAddressInput)
        assertEquals(1L, next.providerUtxosRequestToken)
        assertEquals(ProviderUtxosPresentation.Empty, next.providerUtxos)
    }

    @Test
    fun fillSeedAddress_empty_setsProviderAddressInputToEmptyVector() {
        val state = PlaygroundState.initial()
        val next = PlaygroundReducer.reduce(
            state,
            PlaygroundIntent.FillSeedAddress(SeedAddressKind.EMPTY),
        )
        assertEquals(InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY, next.providerAddressInput)
        assertEquals(1L, next.providerUtxosRequestToken)
        assertEquals(ProviderUtxosPresentation.Empty, next.providerUtxos)
    }

    @Test
    fun updateProviderAddressInput_sameValue_isNoOp() {
        val state = PlaygroundState.initial().copy(providerUtxosRequestToken = 3L)

        val next = PlaygroundReducer.reduce(
            state,
            PlaygroundIntent.UpdateProviderAddressInput(state.providerAddressInput),
        )

        assertEquals(state, next)
    }

    @Test
    fun updateProviderAddressInput_actualChange_incrementsUtxoTokenAndClearsResult() {
        val dirty = PlaygroundState.initial().copy(
            providerUtxos = ProviderUtxosPresentation.Success(listOf(LabeledRow("UTxOs", "1"))),
            providerParams = ProviderParamsPresentation.Success(listOf(LabeledRow("minFeeA", "44"))),
            providerUtxosRequestToken = 2L,
        )

        val next = PlaygroundReducer.reduce(
            dirty,
            PlaygroundIntent.UpdateProviderAddressInput("addr_test1changed"),
        )

        assertEquals("addr_test1changed", next.providerAddressInput)
        assertEquals(3L, next.providerUtxosRequestToken)
        assertEquals(ProviderUtxosPresentation.Empty, next.providerUtxos)
        assertEquals(dirty.providerParams, next.providerParams, "params are address-independent")
    }

    @Test
    fun applyProviderUtxosResult_staleTokenOrAddress_isIgnored() {
        val result = ProviderUtxosPresentation.Success(listOf(LabeledRow("UTxOs", "stale")))
        val current = PlaygroundState.initial().copy(
            providerUtxosRequestToken = 2L,
            providerAddressInput = "addr-b",
        )

        assertEquals(
            current,
            PlaygroundReducer.applyProviderUtxosResult(
                current,
                result,
                requestToken = 1L,
                address = "addr-b",
            ),
        )
        assertEquals(
            current,
            PlaygroundReducer.applyProviderUtxosResult(
                current,
                result,
                requestToken = 2L,
                address = "addr-a",
            ),
        )
    }

    @Test
    fun applyProviderParamsResult_staleToken_isIgnored() {
        val result = ProviderParamsPresentation.Success(listOf(LabeledRow("minFeeA", "1")))
        val current = PlaygroundState.initial().copy(providerParamsRequestToken = 3L)

        val next = PlaygroundReducer.applyProviderParamsResult(current, result, requestToken = 2L)

        assertEquals(current, next)
    }

    @Test
    fun applyProviderUtxosResult_currentIdentity_isApplied() {
        val result = ProviderUtxosPresentation.Success(listOf(LabeledRow("UTxOs", "current")))
        val current = PlaygroundState.initial().copy(
            providerUtxosRequestToken = 2L,
            providerAddressInput = "addr-b",
        )

        val next = PlaygroundReducer.applyProviderUtxosResult(
            current,
            result,
            requestToken = 2L,
            address = "addr-b",
        )

        assertEquals(result, next.providerUtxos)
    }

    @Test
    fun applyProviderParamsResult_currentToken_isApplied() {
        val result = ProviderParamsPresentation.Success(listOf(LabeledRow("minFeeA", "44")))
        val current = PlaygroundState.initial().copy(providerParamsRequestToken = 3L)

        val next = PlaygroundReducer.applyProviderParamsResult(current, result, requestToken = 3L)

        assertEquals(result, next.providerParams)
    }

    // --- Loading transitions ---

    @Test
    fun startFundsLoading_setsFundsToLoading() {
        val next = PlaygroundReducer.startFundsLoading(
            PlaygroundState.initial().copy(fundsRequestToken = 2L),
        )
        assertEquals(WalletBalancePresentation.Loading, next.funds)
        assertEquals(3L, next.fundsRequestToken)
    }

    @Test
    fun startFundsLoading_clearsCompletedDownstreamAndIncrementsTheirTokens() {
        val dirty = PlaygroundState.initial().copy(
            draft = TransactionDraftPresentation.Success(listOf(LabeledRow("Fee", "1"))),
            signed = SignedTransactionPresentation.Success(listOf(LabeledRow("Witnesses", "1"))),
            submit = SubmitTransactionPresentation.Loading,
            draftRequestToken = 3L,
            signedRequestToken = 2L,
            submitRequestToken = 1L,
        )

        val next = PlaygroundReducer.startFundsLoading(dirty)

        assertEquals(WalletBalancePresentation.Loading, next.funds)
        assertEquals(TransactionDraftPresentation.Empty, next.draft)
        assertEquals(SignedTransactionPresentation.Empty, next.signed)
        assertEquals(SubmitTransactionPresentation.Empty, next.submit)
        assertEquals(4L, next.draftRequestToken)
        assertEquals(3L, next.signedRequestToken)
        assertEquals(2L, next.submitRequestToken)
    }

    @Test
    fun startDraftLoading_incrementsRequestToken() {
        val next = PlaygroundReducer.startDraftLoading(
            PlaygroundState.initial().copy(draftRequestToken = 1L),
        )
        assertEquals(TransactionDraftPresentation.Loading, next.draft)
        assertEquals(2L, next.draftRequestToken)
    }

    @Test
    fun startDraftLoading_clearsCompletedSignAndSubmitAndIncrementsTheirTokens() {
        val dirty = PlaygroundState.initial().copy(
            signed = SignedTransactionPresentation.Success(listOf(LabeledRow("Witnesses", "1"))),
            submit = SubmitTransactionPresentation.Success(listOf(LabeledRow("Status", "submitted"))),
            signedRequestToken = 5L,
            submitRequestToken = 4L,
        )

        val next = PlaygroundReducer.startDraftLoading(dirty)

        assertEquals(TransactionDraftPresentation.Loading, next.draft)
        assertEquals(SignedTransactionPresentation.Empty, next.signed)
        assertEquals(SubmitTransactionPresentation.Empty, next.submit)
        assertEquals(6L, next.signedRequestToken)
        assertEquals(5L, next.submitRequestToken)
    }

    @Test
    fun startSignedLoading_incrementsRequestToken() {
        val next = PlaygroundReducer.startSignedLoading(
            PlaygroundState.initial().copy(signedRequestToken = 4L),
        )
        assertEquals(SignedTransactionPresentation.Loading, next.signed)
        assertEquals(5L, next.signedRequestToken)
    }

    @Test
    fun startSignedLoading_clearsCompletedSubmitAndIncrementsItsToken() {
        val dirty = PlaygroundState.initial().copy(
            submit = SubmitTransactionPresentation.Success(listOf(LabeledRow("Status", "submitted"))),
            submitRequestToken = 7L,
        )

        val next = PlaygroundReducer.startSignedLoading(dirty)

        assertEquals(SignedTransactionPresentation.Loading, next.signed)
        assertEquals(SubmitTransactionPresentation.Empty, next.submit)
        assertEquals(8L, next.submitRequestToken)
    }

    @Test
    fun startSubmitLoading_incrementsRequestToken() {
        val next = PlaygroundReducer.startSubmitLoading(
            PlaygroundState.initial().copy(submitRequestToken = 0L),
        )
        assertEquals(SubmitTransactionPresentation.Loading, next.submit)
        assertEquals(1L, next.submitRequestToken)
    }

    @Test
    fun startWalletLoading_setsWalletLoadingFlag() {
        val next = PlaygroundReducer.startWalletLoading(PlaygroundState.initial())
        assertTrue(next.walletLoading)
    }

    @Test
    fun startProviderUtxosLoading_incrementsRequestToken() {
        val next = PlaygroundReducer.startProviderUtxosLoading(
            PlaygroundState.initial().copy(providerUtxosRequestToken = 4L),
        )
        assertEquals(ProviderUtxosPresentation.Loading, next.providerUtxos)
        assertEquals(5L, next.providerUtxosRequestToken)
    }

    @Test
    fun startProviderParamsLoading_incrementsRequestToken() {
        val next = PlaygroundReducer.startProviderParamsLoading(
            PlaygroundState.initial().copy(providerParamsRequestToken = 1L),
        )
        assertEquals(ProviderParamsPresentation.Loading, next.providerParams)
        assertEquals(2L, next.providerParamsRequestToken)
    }

    // --- applyX: fold a *Presentation result back into state ---

    @Test
    fun applyWalletResult_setsWalletAndClearsLoading() {
        val loading = PlaygroundReducer.startWalletLoading(PlaygroundState.initial())
        val result = WalletPresentation.Success(
            rows = listOf(LabeledRow("Generated address", "addr_test1abc")),
            fingerprintMatchesVector = true,
        )

        val next = PlaygroundReducer.applyWalletResult(loading, result)

        assertEquals(result, next.wallet)
        assertFalse(next.walletLoading)
    }

    @Test
    fun applyFundsResult_success_isSurfacedInState() {
        val result = WalletBalancePresentation.Success(
            listOf(LabeledRow("UTxO count", "2"), LabeledRow("Balance", "5000000 lovelace")),
        )
        val next = PlaygroundReducer.applyFundsResult(PlaygroundState.initial(), result)
        assertIs<WalletBalancePresentation.Success>(next.funds)
        assertEquals(result, next.funds)
    }

    @Test
    fun applyFundsResult_failure_isSurfacedInState() {
        val result = WalletBalancePresentation.Failure("Network mismatch: provider=MAINNET, address=TESTNET")
        val next = PlaygroundReducer.applyFundsResult(PlaygroundState.initial(), result)
        val failure = assertIs<WalletBalancePresentation.Failure>(next.funds)
        assertTrue(failure.message.contains("Network mismatch"))
    }

    @Test
    fun applyDraftResult_success_isSurfacedInState() {
        val result = TransactionDraftPresentation.Success(listOf(LabeledRow("Fee", "170000 lovelace")))
        val next = PlaygroundReducer.applyDraftResult(PlaygroundState.initial(), result)
        assertEquals(result, next.draft)
    }

    @Test
    fun applyDraftResult_adaOnlyNativeAssetFailure_isSurfacedInState() {
        // Block 1.11d/1.11d-2 ADA-only filtering message, unchanged by this refactor.
        val message = "This wallet has no ADA-only UTxOs to spend — only UTxOs containing " +
            "native assets/tokens. Phase 1 only builds ADA-only transactions. (all candidate " +
            "UTxOs carry native assets)"
        val result = TransactionDraftPresentation.Failure(message)

        val next = PlaygroundReducer.applyDraftResult(PlaygroundState.initial(), result)

        val failure = assertIs<TransactionDraftPresentation.Failure>(next.draft)
        assertTrue(failure.message.contains("native", ignoreCase = true))
        assertTrue(failure.message.contains("ADA-only"))
    }

    @Test
    fun applySignedResult_success_isSurfacedInState() {
        val result = SignedTransactionPresentation.Success(
            listOf(LabeledRow("Witnesses", "1"), LabeledRow("Status", "signed, not submitted")),
        )
        val next = PlaygroundReducer.applySignedResult(PlaygroundState.initial(), result)
        assertEquals(result, next.signed)
    }

    @Test
    fun applySignedResult_failure_isSurfacedInState() {
        val result = SignedTransactionPresentation.Failure("Signing failed: backend failed: boom")
        val next = PlaygroundReducer.applySignedResult(PlaygroundState.initial(), result)
        val failure = assertIs<SignedTransactionPresentation.Failure>(next.signed)
        assertTrue(failure.message.contains("Signing failed"))
    }

    @Test
    fun applySubmitResult_success_isSurfacedInState() {
        val result = SubmitTransactionPresentation.Success(
            listOf(LabeledRow("Ids match", "yes"), LabeledRow("Status", "submitted to preprod")),
        )
        val next = PlaygroundReducer.applySubmitResult(PlaygroundState.initial(), result)
        assertEquals(result, next.submit)
    }

    @Test
    fun applySubmitResult_failure_isSurfacedInState() {
        val result = SubmitTransactionPresentation.Failure(
            "This provider does not support submission (mock) — enable live Blockfrost preprod " +
                "to submit for real.",
        )
        val next = PlaygroundReducer.applySubmitResult(PlaygroundState.initial(), result)
        val failure = assertIs<SubmitTransactionPresentation.Failure>(next.submit)
        assertTrue(failure.message.contains("not support", ignoreCase = true))
    }
}
