package org.sarmidev.kardano.playground.mvi

import org.sarmidev.kardano.playground.AddressPresentation
import org.sarmidev.kardano.playground.CborPresentation
import org.sarmidev.kardano.playground.HexPresentation
import org.sarmidev.kardano.playground.ProviderParamsPresentation
import org.sarmidev.kardano.playground.ProviderUtxosPresentation
import org.sarmidev.kardano.playground.SignedTransactionPresentation
import org.sarmidev.kardano.playground.SubmitTransactionPresentation
import org.sarmidev.kardano.playground.TransactionDraftPresentation
import org.sarmidev.kardano.playground.WalletBalancePresentation
import org.sarmidev.kardano.playground.WalletPresentation
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider

/**
 * Pure, non-suspend state transitions for [PlaygroundState].
 *
 * [reduce] handles every intent that needs no SDK/provider call — section navigation and roadmap
 * phase selection, provider selection, text-field updates, seed-address fill, technical-details
 * toggling, the landing "Code examples" toggle, and [PlaygroundIntent.ResetFlow].
 * Intents that call `:core`/`:crypto`/`:wallet`/`:tx`/`:provider` APIs (restoring the wallet,
 * querying funds, building/signing/submitting, parsing/decoding, loading provider data) are
 * intercepted by [PlaygroundViewModel] before reaching [reduce]; it calls the relevant use case
 * or presenter function and folds the resulting `*Presentation` back into state via the
 * `applyX`/`startXLoading` helpers below. This split keeps every transition in this file
 * testable synchronously, without coroutines or a native backend, in `commonTest`.
 *
 * This object carries no protocol or cryptographic logic of its own — it only shapes UI state.
 */
internal object PlaygroundReducer {

    /** Handles every intent that requires no SDK/provider call. See class KDoc for the split. */
    fun reduce(state: PlaygroundState, intent: PlaygroundIntent): PlaygroundState = when (intent) {
        is PlaygroundIntent.NavigateToWelcome -> state.copy(section = PlaygroundSection.WELCOME)
        is PlaygroundIntent.NavigateToDemo -> state.copy(section = PlaygroundSection.DEMO)
        is PlaygroundIntent.NavigateToSummary -> state.copy(section = PlaygroundSection.SUMMARY)
        is PlaygroundIntent.NavigateToAbout -> state.copy(section = PlaygroundSection.ABOUT)
        is PlaygroundIntent.NavigateToRoadmap -> state.copy(section = PlaygroundSection.ROADMAP)

        // A no-op unless the current step is resolved (DONE or the honest mock-stop INFO); from
        // the last step it moves to the Summary screen instead of stepping demoStep further.
        is PlaygroundIntent.ContinueDemo -> if (!PlaygroundDemoFlow.canContinue(state)) {
            state
        } else {
            val next = PlaygroundDemoFlow.nextStep(state.demoStep)
            if (next == null) {
                state.copy(section = PlaygroundSection.SUMMARY)
            } else {
                state.copy(demoStep = next)
            }
        }

        // A no-op on the first step; never clears a step's result.
        is PlaygroundIntent.BackDemo -> {
            val previous = PlaygroundDemoFlow.previousStep(state.demoStep)
            if (previous == null) state else state.copy(demoStep = previous)
        }

        // Tapping the already-selected phase collapses its detail; tapping another expands it.
        is PlaygroundIntent.SelectRoadmapPhase -> state.copy(
            selectedRoadmapPhase = if (state.selectedRoadmapPhase == intent.phase) {
                null
            } else {
                intent.phase
            },
        )

        is PlaygroundIntent.ToggleLiveBlockfrost -> state.copy(useLiveBlockfrost = intent.enabled)
        is PlaygroundIntent.UpdateProjectId -> state.copy(projectId = intent.value)

        is PlaygroundIntent.ToggleTechnicalDetails -> state.copy(
            technicalDetailsExpanded = if (intent.step in state.technicalDetailsExpanded) {
                state.technicalDetailsExpanded - intent.step
            } else {
                state.technicalDetailsExpanded + intent.step
            },
        )

        is PlaygroundIntent.ToggleCodeExamples ->
            state.copy(codeExamplesExpanded = !state.codeExamplesExpanded)

        // Resets the five guided-flow step results (and the Wallet step's loading flag), and
        // (Block 1.12-pre-e) returns demoStep/section to the start of the demo — serving both a
        // mid-demo "Start over" control and the Summary screen's "Run the demo again" control.
        // Provider selection, technicalDetailsExpanded, and diagnostics inputs/results are
        // intentionally preserved so resetting the flow does not also clear an in-progress
        // diagnostics exploration or provider configuration.
        is PlaygroundIntent.ResetFlow -> state.copy(
            wallet = WalletPresentation.Empty,
            walletLoading = false,
            funds = WalletBalancePresentation.Empty,
            draft = TransactionDraftPresentation.Empty,
            signed = SignedTransactionPresentation.Empty,
            submit = SubmitTransactionPresentation.Empty,
            demoStep = PlaygroundStep.WALLET,
            section = PlaygroundSection.DEMO,
        )

        is PlaygroundIntent.UpdateAddressInput -> state.copy(addressInput = intent.value)
        is PlaygroundIntent.UpdateHexInput -> state.copy(hexInput = intent.value)
        is PlaygroundIntent.UpdateCborInput -> state.copy(cborInput = intent.value)
        is PlaygroundIntent.UpdateProviderAddressInput ->
            state.copy(providerAddressInput = intent.value)

        is PlaygroundIntent.FillSeedAddress -> state.copy(
            providerAddressInput = when (intent.kind) {
                SeedAddressKind.WITH_UTXOS -> InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS
                SeedAddressKind.EMPTY -> InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY
            },
        )

        // Handled by PlaygroundViewModel.dispatch before reaching reduce (they call a use case
        // or presenter function first); listed here only so this `when` stays exhaustive.
        is PlaygroundIntent.RestoreWallet,
        is PlaygroundIntent.QueryFunds,
        is PlaygroundIntent.BuildDraft,
        is PlaygroundIntent.SignTransaction,
        is PlaygroundIntent.SubmitTransaction,
        is PlaygroundIntent.ParseAddress,
        is PlaygroundIntent.DecodeHex,
        is PlaygroundIntent.DecodeCbor,
        is PlaygroundIntent.LoadProviderUtxos,
        is PlaygroundIntent.LoadProviderParams,
        -> state
    }

    // --- Loading transitions (set before a use case/presenter call starts) ---

    fun startWalletLoading(state: PlaygroundState): PlaygroundState = state.copy(walletLoading = true)

    fun startFundsLoading(state: PlaygroundState): PlaygroundState =
        state.copy(funds = WalletBalancePresentation.Loading)

    fun startDraftLoading(state: PlaygroundState): PlaygroundState =
        state.copy(draft = TransactionDraftPresentation.Loading)

    fun startSignedLoading(state: PlaygroundState): PlaygroundState =
        state.copy(signed = SignedTransactionPresentation.Loading)

    fun startSubmitLoading(state: PlaygroundState): PlaygroundState =
        state.copy(submit = SubmitTransactionPresentation.Loading)

    fun startProviderUtxosLoading(state: PlaygroundState): PlaygroundState =
        state.copy(providerUtxos = ProviderUtxosPresentation.Loading)

    fun startProviderParamsLoading(state: PlaygroundState): PlaygroundState =
        state.copy(providerParams = ProviderParamsPresentation.Loading)

    // --- Result transitions (fold a *Presentation result back into state) ---

    fun applyWalletResult(state: PlaygroundState, result: WalletPresentation): PlaygroundState =
        state.copy(wallet = result, walletLoading = false)

    fun applyFundsResult(state: PlaygroundState, result: WalletBalancePresentation): PlaygroundState =
        state.copy(funds = result)

    fun applyDraftResult(state: PlaygroundState, result: TransactionDraftPresentation): PlaygroundState =
        state.copy(draft = result)

    fun applySignedResult(state: PlaygroundState, result: SignedTransactionPresentation): PlaygroundState =
        state.copy(signed = result)

    fun applySubmitResult(state: PlaygroundState, result: SubmitTransactionPresentation): PlaygroundState =
        state.copy(submit = result)

    fun applyAddressResult(state: PlaygroundState, result: AddressPresentation): PlaygroundState =
        state.copy(addressResult = result)

    fun applyHexResult(state: PlaygroundState, result: HexPresentation): PlaygroundState =
        state.copy(hexResult = result)

    fun applyCborResult(state: PlaygroundState, result: CborPresentation): PlaygroundState =
        state.copy(cborResult = result)

    fun applyProviderUtxosResult(
        state: PlaygroundState,
        result: ProviderUtxosPresentation,
    ): PlaygroundState = state.copy(providerUtxos = result)

    fun applyProviderParamsResult(
        state: PlaygroundState,
        result: ProviderParamsPresentation,
    ): PlaygroundState = state.copy(providerParams = result)
}
