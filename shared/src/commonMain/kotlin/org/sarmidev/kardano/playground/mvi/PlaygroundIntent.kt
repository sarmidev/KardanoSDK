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

    // --- Provider selection ---

    /** Toggles the "Use live Blockfrost (preprod)" switch. */
    data class ToggleLiveBlockfrost(val enabled: Boolean) : PlaygroundIntent

    /** Updates the in-memory (never persisted/logged) Blockfrost `project_id` field. */
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
     * Resets every guided-flow step back to its initial/empty state. Provider selection
     * ([PlaygroundState.useLiveBlockfrost], [PlaygroundState.projectId]) and diagnostics inputs
     * are preserved — see [PlaygroundReducer.reduce]'s handling of this intent.
     */
    data object ResetFlow : PlaygroundIntent

    /** Toggles the expanded/technical view for one guided-flow step. */
    data class ToggleTechnicalDetails(val step: PlaygroundStep) : PlaygroundIntent

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

    /** Updates the generic Provider explorer's address field. */
    data class UpdateProviderAddressInput(val value: String) : PlaygroundIntent

    /** Fills the Provider explorer's address field with one of the two cited seed vectors. */
    data class FillSeedAddress(val kind: SeedAddressKind) : PlaygroundIntent

    /** Loads UTxOs for the Provider explorer's current address from the active provider. */
    data object LoadProviderUtxos : PlaygroundIntent

    /** Loads protocol parameters for the Provider explorer from the active provider. */
    data object LoadProviderParams : PlaygroundIntent
}
