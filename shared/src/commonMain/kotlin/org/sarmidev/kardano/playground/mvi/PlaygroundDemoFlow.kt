package org.sarmidev.kardano.playground.mvi

import org.sarmidev.kardano.playground.MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE
import org.sarmidev.kardano.playground.SignedTransactionPresentation
import org.sarmidev.kardano.playground.SubmitTransactionPresentation
import org.sarmidev.kardano.playground.TransactionDraftPresentation
import org.sarmidev.kardano.playground.WalletBalancePresentation
import org.sarmidev.kardano.playground.WalletPresentation

/**
 * The visitor-facing outcome of one guided-demo step (Block 1.12-pre-e), derived from its
 * `*Presentation` value. [INFO] is a distinct, non-error resting state used for exactly one
 * case today — the mock Submit step's honest "this provider does not support submission"
 * result (see [PlaygroundDemoFlow.outcome]) — so the demo can present an *expected*, non-red
 * stopping point without either hiding it as a generic error or misrepresenting it as a
 * completed submission.
 */
internal enum class StepOutcome { NOT_STARTED, WORKING, DONE, INFO, ERROR }

/**
 * Presentation-only step ordering, gating, and outcome classification for the guided demo
 * (Block 1.12-pre-e). Pure and non-suspend — it reads [PlaygroundState] and the existing
 * `*Presentation` sealed types directly and computes nothing that reaches an SDK API; it exists
 * only so [org.sarmidev.kardano.playground.PlaygroundScreen] and
 * [PlaygroundReducer] can share one definition of "what does this step's current result mean"
 * and "can the visitor move on", each independently unit-testable in `commonTest`.
 */
internal object PlaygroundDemoFlow {

    /** The five guided-flow steps, in the fixed order the demo walks them. */
    private val ORDER: List<PlaygroundStep> = listOf(
        PlaygroundStep.WALLET,
        PlaygroundStep.FUNDS,
        PlaygroundStep.BUILD,
        PlaygroundStep.SIGN,
        PlaygroundStep.SUBMIT,
    )

    /** The 1-based position of [step] in the fixed order (for "Step N of 5" copy). */
    fun stepNumber(step: PlaygroundStep): Int = ORDER.indexOf(step) + 1

    /** The total number of guided-demo steps. */
    val stepCount: Int = ORDER.size

    /** The step after [step], or `null` if [step] is the last one ([PlaygroundStep.SUBMIT]). */
    fun nextStep(step: PlaygroundStep): PlaygroundStep? = ORDER.getOrNull(ORDER.indexOf(step) + 1)

    /** The step before [step], or `null` if [step] is the first one ([PlaygroundStep.WALLET]). */
    fun previousStep(step: PlaygroundStep): PlaygroundStep? = ORDER.getOrNull(ORDER.indexOf(step) - 1)

    /**
     * Classifies [step]'s current result in [state] into a [StepOutcome].
     *
     * The one non-obvious case: [PlaygroundStep.SUBMIT] under the default mock provider always
     * returns a [SubmitTransactionPresentation.Failure] whose message is exactly
     * [MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE] (ADR-0017 — the mock never fakes an accepted
     * submission). That specific, expected combination — the effective provider remains mock
     * ([PlaygroundState.isLivePreprodActive] is false) and that exact message — is classified as
     * [StepOutcome.INFO], not [StepOutcome.ERROR]: it is the demo working as designed, not a
     * failure. The switch alone does not activate live requests while the project id is blank.
     * Any other Submit failure (including that same message appearing after live preprod became
     * active) is [StepOutcome.ERROR].
     */
    fun outcome(state: PlaygroundState, step: PlaygroundStep): StepOutcome = when (step) {
        PlaygroundStep.WALLET -> when {
            state.walletLoading -> StepOutcome.WORKING
            state.wallet is WalletPresentation.Success -> StepOutcome.DONE
            state.wallet is WalletPresentation.Failure -> StepOutcome.ERROR
            else -> StepOutcome.NOT_STARTED
        }
        PlaygroundStep.FUNDS -> when (state.funds) {
            is WalletBalancePresentation.Empty -> StepOutcome.NOT_STARTED
            is WalletBalancePresentation.Loading -> StepOutcome.WORKING
            is WalletBalancePresentation.Success -> StepOutcome.DONE
            is WalletBalancePresentation.Failure -> StepOutcome.ERROR
        }
        PlaygroundStep.BUILD -> when (state.draft) {
            is TransactionDraftPresentation.Empty -> StepOutcome.NOT_STARTED
            is TransactionDraftPresentation.Loading -> StepOutcome.WORKING
            is TransactionDraftPresentation.Success -> StepOutcome.DONE
            is TransactionDraftPresentation.Failure -> StepOutcome.ERROR
        }
        PlaygroundStep.SIGN -> when (state.signed) {
            is SignedTransactionPresentation.Empty -> StepOutcome.NOT_STARTED
            is SignedTransactionPresentation.Loading -> StepOutcome.WORKING
            is SignedTransactionPresentation.Success -> StepOutcome.DONE
            is SignedTransactionPresentation.Failure -> StepOutcome.ERROR
        }
        PlaygroundStep.SUBMIT -> when (val submit = state.submit) {
            is SubmitTransactionPresentation.Empty -> StepOutcome.NOT_STARTED
            is SubmitTransactionPresentation.Loading -> StepOutcome.WORKING
            is SubmitTransactionPresentation.Success -> StepOutcome.DONE
            is SubmitTransactionPresentation.Failure ->
                if (!state.isLivePreprodActive && submit.message == MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE) {
                    StepOutcome.INFO
                } else {
                    StepOutcome.ERROR
                }
        }
    }

    /**
     * Whether the visitor can move on from [PlaygroundState.demoStep] via
     * [PlaygroundIntent.ContinueDemo]: the current step's [outcome] must be [StepOutcome.DONE]
     * or [StepOutcome.INFO] (the honest mock-stop is a valid place to continue to the Summary
     * screen from — the demo has nothing further to run).
     */
    fun canContinue(state: PlaygroundState): Boolean =
        when (outcome(state, state.demoStep)) {
            StepOutcome.DONE, StepOutcome.INFO -> true
            StepOutcome.NOT_STARTED, StepOutcome.WORKING, StepOutcome.ERROR -> false
        }

    /** How many of the five steps currently have a [StepOutcome.DONE] or [StepOutcome.INFO] result. */
    fun completedSteps(state: PlaygroundState): Int =
        ORDER.count { step ->
            when (outcome(state, step)) {
                StepOutcome.DONE, StepOutcome.INFO -> true
                else -> false
            }
        }

    // --- Friendly reasons for a subset of PlaygroundPresenter failure messages ---

    private const val NO_UTXOS_MESSAGE = "No UTxOs available to build a transaction from."
    private const val ALL_NATIVE_ASSET_PREFIX =
        "This wallet has no ADA-only UTxOs to spend — only UTxOs containing native assets/tokens."

    /**
     * Maps a subset of known [org.sarmidev.kardano.playground.PlaygroundPresenter] failure
     * messages for [step] to a short, plain-language sentence, or `null` if [message] is not
     * one of the mapped cases (the UI then falls back to a generic per-step headline). The raw
     * [message] is always still reachable under a step's "Technical details" — this only adds a
     * friendlier headline on top, it never replaces or hides the underlying message.
     */
    fun friendlyReason(step: PlaygroundStep, message: String): String? = when {
        message == NO_UTXOS_MESSAGE ->
            "This wallet has no test money to spend yet."
        message.startsWith(ALL_NATIVE_ASSET_PREFIX) ->
            "This wallet's test money is held in tokens this demo can't spend. The demo sends " +
                "ADA only."
        message.startsWith("Insufficient funds") ->
            "This wallet doesn't hold enough test money for this payment."
        message.startsWith("Transport error") ->
            "Couldn't reach the test network. Check your connection and try again."
        message.startsWith("Remote status") ->
            "The test network reported a problem handling this request."
        message == "Rate limited" ->
            "The test network is asking us to slow down. Wait a moment and try again."
        message.startsWith("Network mismatch") ->
            "This request was addressed to the wrong network."
        else -> if (step == PlaygroundStep.SUBMIT && message == MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE) {
            "This demo runs offline, so there is no network to send to."
        } else {
            null
        }
    }

    // --- Truncation for plain-language result lines ---

    private const val ADDRESS_PREFIX_CHARS = 10
    private const val ADDRESS_SUFFIX_CHARS = 8
    private const val ID_PREFIX_CHARS = 7
    private const val ID_SUFFIX_CHARS = 6

    /**
     * Shortens a bech32 address (for example `addr_test1...`) to a readable
     * `"<prefix>…<suffix>"` form for the demo's plain-language result lines. Returns [value]
     * unchanged if it is already short enough that truncating would not shorten it.
     */
    fun shortenAddress(value: String): String =
        shorten(value, ADDRESS_PREFIX_CHARS, ADDRESS_SUFFIX_CHARS)

    /**
     * Shortens a hex transaction/reference id to a readable `"<prefix>…<suffix>"` form for the
     * demo's plain-language result lines. Returns [value] unchanged if it is already short
     * enough that truncating would not shorten it.
     */
    fun shortenId(value: String): String = shorten(value, ID_PREFIX_CHARS, ID_SUFFIX_CHARS)

    private fun shorten(value: String, prefixChars: Int, suffixChars: Int): String {
        if (value.length <= prefixChars + suffixChars) return value
        return "${value.take(prefixChars)}…${value.takeLast(suffixChars)}"
    }
}
