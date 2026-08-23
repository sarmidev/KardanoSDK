package org.sarmidev.kardano.playground.mvi

import org.sarmidev.kardano.playground.LabeledRow
import org.sarmidev.kardano.playground.MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE
import org.sarmidev.kardano.playground.PlaygroundPresenter
import org.sarmidev.kardano.playground.SignedTransactionPresentation
import org.sarmidev.kardano.playground.SubmitTransactionPresentation
import org.sarmidev.kardano.playground.TransactionDraftPresentation
import org.sarmidev.kardano.playground.WalletBalancePresentation
import org.sarmidev.kardano.playground.WalletPresentation
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.provider.ProviderError
import org.sarmidev.kardano.tx.TxBuildError
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Unit tests for [PlaygroundDemoFlow] (Block 1.12-pre-e).
 *
 * Pure and non-suspend — every test constructs a [PlaygroundState] and/or a `*Presentation`
 * value directly, the same native-free style [PlaygroundReducerTest] uses.
 */
class PlaygroundDemoFlowTest {

    private val walletSuccess = WalletPresentation.Success(
        rows = listOf(LabeledRow("Generated address", "addr_test1abc")),
        fingerprintMatchesVector = true,
    )

    // --- outcome(): NOT_STARTED / WORKING / DONE / ERROR per step ---

    @Test
    fun outcome_wallet_reflectsWalletLoadingAndResultIndependently() {
        val state = PlaygroundState.initial()
        assertEquals(StepOutcome.NOT_STARTED, PlaygroundDemoFlow.outcome(state, PlaygroundStep.WALLET))

        val loading = state.copy(walletLoading = true)
        assertEquals(StepOutcome.WORKING, PlaygroundDemoFlow.outcome(loading, PlaygroundStep.WALLET))

        val done = state.copy(wallet = walletSuccess)
        assertEquals(StepOutcome.DONE, PlaygroundDemoFlow.outcome(done, PlaygroundStep.WALLET))

        val errored = state.copy(wallet = WalletPresentation.Failure("boom"))
        assertEquals(StepOutcome.ERROR, PlaygroundDemoFlow.outcome(errored, PlaygroundStep.WALLET))
    }

    @Test
    fun outcome_funds_mapsEveryPresentationVariant() {
        val state = PlaygroundState.initial()
        assertEquals(StepOutcome.NOT_STARTED, PlaygroundDemoFlow.outcome(state, PlaygroundStep.FUNDS))

        val loading = state.copy(funds = WalletBalancePresentation.Loading)
        assertEquals(StepOutcome.WORKING, PlaygroundDemoFlow.outcome(loading, PlaygroundStep.FUNDS))

        val done = state.copy(funds = WalletBalancePresentation.Success(emptyList()))
        assertEquals(StepOutcome.DONE, PlaygroundDemoFlow.outcome(done, PlaygroundStep.FUNDS))

        val errored = state.copy(funds = WalletBalancePresentation.Failure("boom"))
        assertEquals(StepOutcome.ERROR, PlaygroundDemoFlow.outcome(errored, PlaygroundStep.FUNDS))
    }

    @Test
    fun outcome_build_mapsEveryPresentationVariant() {
        val state = PlaygroundState.initial()
        assertEquals(StepOutcome.NOT_STARTED, PlaygroundDemoFlow.outcome(state, PlaygroundStep.BUILD))

        val loading = state.copy(draft = TransactionDraftPresentation.Loading)
        assertEquals(StepOutcome.WORKING, PlaygroundDemoFlow.outcome(loading, PlaygroundStep.BUILD))

        val done = state.copy(draft = TransactionDraftPresentation.Success(emptyList()))
        assertEquals(StepOutcome.DONE, PlaygroundDemoFlow.outcome(done, PlaygroundStep.BUILD))

        val errored = state.copy(draft = TransactionDraftPresentation.Failure("boom"))
        assertEquals(StepOutcome.ERROR, PlaygroundDemoFlow.outcome(errored, PlaygroundStep.BUILD))
    }

    @Test
    fun outcome_sign_mapsEveryPresentationVariant() {
        val state = PlaygroundState.initial()
        assertEquals(StepOutcome.NOT_STARTED, PlaygroundDemoFlow.outcome(state, PlaygroundStep.SIGN))

        val loading = state.copy(signed = SignedTransactionPresentation.Loading)
        assertEquals(StepOutcome.WORKING, PlaygroundDemoFlow.outcome(loading, PlaygroundStep.SIGN))

        val done = state.copy(signed = SignedTransactionPresentation.Success(emptyList()))
        assertEquals(StepOutcome.DONE, PlaygroundDemoFlow.outcome(done, PlaygroundStep.SIGN))

        val errored = state.copy(signed = SignedTransactionPresentation.Failure("boom"))
        assertEquals(StepOutcome.ERROR, PlaygroundDemoFlow.outcome(errored, PlaygroundStep.SIGN))
    }

    // --- outcome(): the honesty-critical Submit/mock INFO classification ---

    @Test
    fun outcome_submit_mapsEmptyLoadingAndSuccess() {
        val state = PlaygroundState.initial()
        assertEquals(StepOutcome.NOT_STARTED, PlaygroundDemoFlow.outcome(state, PlaygroundStep.SUBMIT))

        val loading = state.copy(submit = SubmitTransactionPresentation.Loading)
        assertEquals(StepOutcome.WORKING, PlaygroundDemoFlow.outcome(loading, PlaygroundStep.SUBMIT))

        val done = state.copy(submit = SubmitTransactionPresentation.Success(emptyList()))
        assertEquals(StepOutcome.DONE, PlaygroundDemoFlow.outcome(done, PlaygroundStep.SUBMIT))
    }

    @Test
    fun outcome_submit_mockNotSupportedFailure_isInfoUntilLivePreprodIsActuallyConfigured() {
        val mock = PlaygroundState.initial().copy(
            useLiveBlockfrost = false,
            submit = SubmitTransactionPresentation.Failure(MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE),
        )
        assertEquals(StepOutcome.INFO, PlaygroundDemoFlow.outcome(mock, PlaygroundStep.SUBMIT))

        val incompleteLiveConfiguration = mock.copy(useLiveBlockfrost = true, projectId = "   ")
        assertFalse(incompleteLiveConfiguration.isLivePreprodActive)
        assertEquals(
            StepOutcome.INFO,
            PlaygroundDemoFlow.outcome(incompleteLiveConfiguration, PlaygroundStep.SUBMIT),
        )

        val live = mock.copy(useLiveBlockfrost = true, projectId = "preprod-project-id")
        assertTrue(live.isLivePreprodActive)
        assertEquals(StepOutcome.ERROR, PlaygroundDemoFlow.outcome(live, PlaygroundStep.SUBMIT))
    }

    @Test
    fun outcome_submit_anyOtherFailureMessage_isAlwaysError() {
        val state = PlaygroundState.initial().copy(
            submit = SubmitTransactionPresentation.Failure("Transaction rejected (status 400): boom"),
        )
        assertEquals(StepOutcome.ERROR, PlaygroundDemoFlow.outcome(state, PlaygroundStep.SUBMIT))
    }

    // --- canContinue() ---

    @Test
    fun canContinue_isTrueOnlyForDoneOrInfoOutcomes() {
        val notStarted = PlaygroundState.initial()
        assertFalse(PlaygroundDemoFlow.canContinue(notStarted))

        val working = notStarted.copy(walletLoading = true)
        assertFalse(PlaygroundDemoFlow.canContinue(working))

        val errored = notStarted.copy(wallet = WalletPresentation.Failure("boom"))
        assertFalse(PlaygroundDemoFlow.canContinue(errored))

        val done = notStarted.copy(wallet = walletSuccess)
        assertTrue(PlaygroundDemoFlow.canContinue(done))

        val info = notStarted.copy(
            demoStep = PlaygroundStep.SUBMIT,
            submit = SubmitTransactionPresentation.Failure(MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE),
        )
        assertTrue(PlaygroundDemoFlow.canContinue(info))
    }

    // --- completedSteps() ---

    @Test
    fun completedSteps_countsDoneAndInfoOutcomesOnly() {
        val state = PlaygroundState.initial().copy(
            wallet = walletSuccess,
            funds = WalletBalancePresentation.Success(emptyList()),
            draft = TransactionDraftPresentation.Failure("boom"),
            submit = SubmitTransactionPresentation.Failure(MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE),
        )

        assertEquals(3, PlaygroundDemoFlow.completedSteps(state))
    }

    @Test
    fun completedSteps_isZeroForTheInitialState() {
        assertEquals(0, PlaygroundDemoFlow.completedSteps(PlaygroundState.initial()))
    }

    // --- stepNumber / nextStep / previousStep ---

    @Test
    fun stepNumber_andStepCount_matchTheFixedOrder() {
        assertEquals(1, PlaygroundDemoFlow.stepNumber(PlaygroundStep.WALLET))
        assertEquals(2, PlaygroundDemoFlow.stepNumber(PlaygroundStep.FUNDS))
        assertEquals(3, PlaygroundDemoFlow.stepNumber(PlaygroundStep.BUILD))
        assertEquals(4, PlaygroundDemoFlow.stepNumber(PlaygroundStep.SIGN))
        assertEquals(5, PlaygroundDemoFlow.stepNumber(PlaygroundStep.SUBMIT))
        assertEquals(5, PlaygroundDemoFlow.stepCount)
    }

    @Test
    fun nextStep_andPreviousStep_areNullAtTheEnds() {
        assertNull(PlaygroundDemoFlow.previousStep(PlaygroundStep.WALLET))
        assertEquals(PlaygroundStep.FUNDS, PlaygroundDemoFlow.nextStep(PlaygroundStep.WALLET))
        assertNull(PlaygroundDemoFlow.nextStep(PlaygroundStep.SUBMIT))
        assertEquals(PlaygroundStep.SIGN, PlaygroundDemoFlow.previousStep(PlaygroundStep.SUBMIT))
    }

    // --- friendlyReason(): built from real PlaygroundPresenter error mappers, never hand-typed strings ---

    @Test
    fun friendlyReason_noInputs_mapsToPlainSentence() {
        val message = PlaygroundPresenter.presentTxBuildError(TxBuildError.NoInputs)
        assertEquals(
            "This wallet has no test money to spend yet.",
            PlaygroundDemoFlow.friendlyReason(PlaygroundStep.BUILD, message),
        )
    }

    @Test
    fun friendlyReason_insufficientFunds_mapsToPlainSentence() {
        val message = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.InsufficientFunds(required = 5_000_000L, available = 1_000_000L),
        )
        assertEquals(
            "This wallet doesn't hold enough test money for this payment.",
            PlaygroundDemoFlow.friendlyReason(PlaygroundStep.BUILD, message),
        )
    }

    @Test
    fun friendlyReason_allNativeAssetUnsupportedFeature_mapsToPlainSentence() {
        val message = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.UnsupportedFeature("all 1 candidate UTxO(s) carry native assets/tokens"),
        )
        assertEquals(
            "This wallet's test money is held in tokens this demo can't spend. The demo sends " +
                "ADA only.",
            PlaygroundDemoFlow.friendlyReason(PlaygroundStep.BUILD, message),
        )
    }

    @Test
    fun friendlyReason_transportError_mapsToPlainSentence() {
        val message = PlaygroundPresenter.presentProviderError(ProviderError.Transport("boom"))
        assertEquals(
            "Couldn't reach the test network. Check your connection and try again.",
            PlaygroundDemoFlow.friendlyReason(PlaygroundStep.FUNDS, message),
        )
    }

    @Test
    fun friendlyReason_remoteStatus_mapsToPlainSentence() {
        val message = PlaygroundPresenter.presentProviderError(ProviderError.RemoteStatus(500))
        assertEquals(
            "The test network reported a problem handling this request.",
            PlaygroundDemoFlow.friendlyReason(PlaygroundStep.FUNDS, message),
        )
    }

    @Test
    fun friendlyReason_rateLimited_mapsToPlainSentence() {
        val message = PlaygroundPresenter.presentProviderError(ProviderError.RateLimited)
        assertEquals(
            "The test network is asking us to slow down. Wait a moment and try again.",
            PlaygroundDemoFlow.friendlyReason(PlaygroundStep.FUNDS, message),
        )
    }

    @Test
    fun friendlyReason_networkMismatch_mapsToPlainSentence() {
        val message = PlaygroundPresenter.presentProviderError(
            ProviderError.NetworkMismatch(expected = Network.TESTNET, actual = Network.MAINNET),
        )
        assertEquals(
            "This request was addressed to the wrong network.",
            PlaygroundDemoFlow.friendlyReason(PlaygroundStep.FUNDS, message),
        )
    }

    @Test
    fun friendlyReason_mockSubmissionNotSupported_onlyOnSubmitStep() {
        assertEquals(
            "This demo runs offline, so there is no network to send to.",
            PlaygroundDemoFlow.friendlyReason(PlaygroundStep.SUBMIT, MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE),
        )
        // Same literal text on a different step is unmapped (this specific mapping is Submit-only).
        assertNull(
            PlaygroundDemoFlow.friendlyReason(PlaygroundStep.FUNDS, MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE),
        )
    }

    @Test
    fun friendlyReason_unmappedMessage_returnsNull() {
        assertNull(PlaygroundDemoFlow.friendlyReason(PlaygroundStep.BUILD, "some unrecognized message"))
    }

    // --- shortenAddress / shortenId ---

    @Test
    fun shortenAddress_truncatesLongValuesWithAnEllipsis() {
        val address = "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"
        val shortened = PlaygroundDemoFlow.shortenAddress(address)

        assertTrue(shortened.contains("…"))
        assertTrue(shortened.length < address.length)
        assertTrue(address.startsWith(shortened.substringBefore("…")))
        assertTrue(address.endsWith(shortened.substringAfter("…")))
    }

    @Test
    fun shortenAddress_leavesAShortValueUnchanged() {
        assertEquals("addr_test1x", PlaygroundDemoFlow.shortenAddress("addr_test1x"))
        assertEquals("", PlaygroundDemoFlow.shortenAddress(""))
    }

    @Test
    fun shortenId_truncatesALongHexIdWithAnEllipsis() {
        val id = "331a79ece991fc9bfd98e9da2a5514f38f7ffeb3a08f1bd7e5a1f75af0e42416"
        val shortened = PlaygroundDemoFlow.shortenId(id)

        assertTrue(shortened.contains("…"))
        assertTrue(shortened.length < id.length)
    }

    @Test
    fun shortenId_leavesAShortValueUnchanged() {
        assertEquals("abc123", PlaygroundDemoFlow.shortenId("abc123"))
        assertEquals("", PlaygroundDemoFlow.shortenId(""))
    }
}
