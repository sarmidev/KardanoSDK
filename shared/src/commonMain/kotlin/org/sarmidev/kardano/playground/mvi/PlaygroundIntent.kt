package org.sarmidev.kardano.playground.mvi

/**
 * The two cited public CIP-19 testnet vectors the diagnostics Provider explorer offers as
 * one-tap seed addresses (see [org.sarmidev.kardano.provider.InMemoryChainQueryProvider]).
 */
internal enum class SeedAddressKind {
    WITH_UTXOS,
    EMPTY,
}

/**
 * User actions dispatched to [PlaygroundViewModel]. [PlaygroundScreen][org.sarmidev.kardano.playground.PlaygroundScreen]
 * only dispatches intents and renders [PlaygroundState]; it never computes a result itself.
 *
 * Grouped by area: provider selection, the guided flow (Wallet -> Funds -> Build -> Sign ->
 * Submit), flow-wide controls, and the diagnostics tools. None of these intents change SDK
 * behavior — each maps to an existing `:core`/`:crypto`/`:wallet`/`:tx`/`:provider` call already
 * made by [org.sarmidev.kardano.playground.PlaygroundPresenter] or
 * [org.sarmidev.kardano.playground.data.PlaygroundProviderFactory].
 */
internal sealed interface PlaygroundIntent {

    // --- Section navigation (Block 1.12-pre-c-2, restructured into a linear demo journey in
    // Block 1.12-pre-e; sample-app only) ---

    /** Shows the [PlaygroundSection.WELCOME] landing screen. */
    data object NavigateToWelcome : PlaygroundIntent

    /** Shows the [PlaygroundSection.DEMO] guided-flow screen at its current [PlaygroundState.demoStep]. */
    data object NavigateToDemo : PlaygroundIntent

    /** Shows the [PlaygroundSection.SUMMARY] recap screen. */
    data object NavigateToSummary : PlaygroundIntent

    /** Shows the [PlaygroundSection.ABOUT] screen (capabilities, code examples, Diagnostics). */
    data object NavigateToAbout : PlaygroundIntent

    /** Shows the [PlaygroundSection.ROADMAP] screen. */
    data object NavigateToRoadmap : PlaygroundIntent

    /**
     * Advances [PlaygroundState.demoStep] to the next step, or — from the last step — moves to
     * [PlaygroundSection.SUMMARY]. A no-op unless
     * [org.sarmidev.kardano.playground.mvi.PlaygroundDemoFlow.canContinue] is true for the
     * current state (the current step must have a [org.sarmidev.kardano.playground.mvi.StepOutcome.DONE]
     * or [org.sarmidev.kardano.playground.mvi.StepOutcome.INFO] outcome). Presentation-only —
     * it calls no SDK itself.
     */
    data object ContinueDemo : PlaygroundIntent

    /**
     * Steps [PlaygroundState.demoStep] back one step. A no-op on the first
     * ([PlaygroundStep.WALLET]) step. Never clears a step's result — going back and forward
     * again still shows whatever the step last produced. Presentation-only.
     */
    data object BackDemo : PlaygroundIntent

    /**
     * Selects (or, if already selected, collapses) the roadmap card whose detail is shown.
     * Presentation only — it drives [PlaygroundState.selectedRoadmapPhase] and calls no SDK.
     */
    data class SelectRoadmapPhase(val phase: RoadmapPhase) : PlaygroundIntent

    // --- Provider selection ---

    /**
     * Toggles the "Use live Blockfrost (preprod)" switch. An actual change increments
     * [PlaygroundState.flowGeneration] and clears provider-backed step/diagnostic results.
     */
    data class ToggleLiveBlockfrost(val enabled: Boolean) : PlaygroundIntent

    /**
     * Updates the in-memory (never persisted/logged) Blockfrost `project_id` field. An actual
     * string change increments [PlaygroundState.flowGeneration] and clears provider-backed
     * step/diagnostic results.
     */
    data class UpdateProjectId(val value: String) : PlaygroundIntent

    // --- Guided flow: Wallet -> Funds -> Build -> Sign -> Submit ---

    /** Restores/refreshes the test-only fixture wallet and its generated address (Wallet step). */
    data object RestoreWallet : PlaygroundIntent

    /** Queries the active provider for the fixture wallet's balance (Funds step). */
    data object QueryFunds : PlaygroundIntent

    /** Builds the unsigned minimal-ADA transaction draft (Build step). */
    data object BuildDraft : PlaygroundIntent

    /** Builds and signs the draft, but does not submit it (Sign step). */
    data object SignTransaction : PlaygroundIntent

    /** Builds, signs, and submits the draft to the active submit provider (Submit step). */
    data object SubmitTransaction : PlaygroundIntent

    // --- Flow-wide controls ---

    /**
     * Resets every guided-flow step back to its initial/empty state, and (Block 1.12-pre-e)
     * also returns [PlaygroundState.demoStep] to [PlaygroundStep.WALLET] and
     * [PlaygroundState.section] to [PlaygroundSection.DEMO] — serving both the mid-demo "Start
     * over" control and the Summary screen's "Run the demo again" control. Provider selection
     * ([PlaygroundState.useLiveBlockfrost], [PlaygroundState.projectId]),
     * [PlaygroundState.technicalDetailsExpanded], diagnostics inputs, and *completed*
     * diagnostic results are preserved. In-flight diagnostic Loading values become Empty.
     * Increments [PlaygroundState.flowGeneration] and the diagnostic request tokens so
     * in-flight provider-backed results are discarded.
     */
    data object ResetFlow : PlaygroundIntent

    /** Toggles the expanded/technical view for one guided-flow step. */
    data class ToggleTechnicalDetails(val step: PlaygroundStep) : PlaygroundIntent

    /**
     * Toggles the landing overview's "Code examples" section (Block 1.12-pre-c). Presentation
     * only — it shows/hides static illustrative snippets and calls no SDK.
     */
    data object ToggleCodeExamples : PlaygroundIntent

    // --- Diagnostics: Address Parser, Hex Decoder, CBOR Decoder, Provider explorer ---

    /** Updates the Address Parser input field (does not parse yet). */
    data class UpdateAddressInput(val value: String) : PlaygroundIntent

    /** Parses the current Address Parser input via [org.sarmidev.kardano.address.Address.parse]. */
    data object ParseAddress : PlaygroundIntent

    /** Updates the Hex Decoder input field (does not decode yet). */
    data class UpdateHexInput(val value: String) : PlaygroundIntent

    /** Decodes the current Hex Decoder input. */
    data object DecodeHex : PlaygroundIntent

    /** Updates the CBOR Decoder input field (does not decode yet). */
    data class UpdateCborInput(val value: String) : PlaygroundIntent

    /** Decodes the current CBOR Decoder input. */
    data object DecodeCbor : PlaygroundIntent

    /**
     * Updates the generic Provider explorer's address field. An actual change increments
     * [PlaygroundState.providerUtxosRequestToken] and clears the UTxO result so a previous
     * address's rows cannot remain under the new value.
     */
    data class UpdateProviderAddressInput(val value: String) : PlaygroundIntent

    /**
     * Fills the Provider explorer's address field with one of the two cited seed vectors.
     * An actual change increments [PlaygroundState.providerUtxosRequestToken] and clears the
     * UTxO result, same as [UpdateProviderAddressInput].
     */
    data class FillSeedAddress(val kind: SeedAddressKind) : PlaygroundIntent

    /** Loads UTxOs for the Provider explorer's current address from the active provider. */
    data object LoadProviderUtxos : PlaygroundIntent

    /** Loads protocol parameters for the Provider explorer from the active provider. */
    data object LoadProviderParams : PlaygroundIntent
}
