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
 * Identifies one step of the guided Playground flow (Wallet -> Funds -> Build -> Sign ->
 * Submit), used only for step-scoped UI concerns ([PlaygroundState.technicalDetailsExpanded]) —
 * it carries no SDK semantics of its own.
 */
internal enum class PlaygroundStep {
    WALLET,
    FUNDS,
    BUILD,
    SIGN,
    SUBMIT,
}

/**
 * Which top-level Playground section is currently shown (introduced in Block 1.12-pre-c-2 as
 * `OVERVIEW`/`TRY_SDK`/`ROADMAP`; restructured in Block 1.12-pre-e into a linear guided-demo
 * journey). This is a sample-app navigation concept only — a lightweight in-state switch
 * between the five sections below. It is not an SDK concept and is not part of any public API.
 *
 * The journey is linear rather than tabbed: [WELCOME] (the default landing screen) leads into
 * [DEMO] (the single-step-at-a-time guided flow), which ends at [SUMMARY]; [ABOUT] (the former
 * `OVERVIEW` content, including Diagnostics) and [ROADMAP] are reachable as secondary screens
 * from [WELCOME] and [SUMMARY], each with a way back into [DEMO].
 */
internal enum class PlaygroundSection {
    WELCOME,
    DEMO,
    SUMMARY,
    ABOUT,
    ROADMAP,
}

/**
 * A phase in the sample-app roadmap screen (Block 1.12-pre-c-2). Phase 0/1 describe shipped
 * work; Phase 2/3 are **candidate/future direction, not a commitment**. This enum only selects
 * which roadmap card's detail is expanded ([PlaygroundState.selectedRoadmapPhase]); the phase
 * copy itself lives in the roadmap UI. It is not a public API contract.
 */
internal enum class RoadmapPhase {
    PHASE_0,
    PHASE_1,
    PHASE_2,
    PHASE_3,
}

/**
 * Immutable state for the Playground's guided flow and diagnostics tools (Block 1.12-pre-a).
 *
 * This is the single source of truth [org.sarmidev.kardano.playground.PlaygroundScreen] renders
 * from; it dispatches [PlaygroundIntent]s to [PlaygroundViewModel] and never mutates state
 * itself. Every field is display-ready data — the guided-flow and provider/params fields reuse
 * the existing `*Presentation` sealed types from
 * [org.sarmidev.kardano.playground.PlaygroundPresenter], which already carry only public
 * metadata (never a mnemonic, seed, private/root key byte, or full untruncated CBOR — see each
 * type's KDoc). This class adds no new SDK semantics; it only aggregates presentation state
 * plus the provider-selection and per-step UI flags described below.
 *
 * ### Guided flow (Wallet -> Funds -> Build -> Sign -> Submit)
 *
 * [wallet], [funds], [draft], [signed], and [submit] hold the current presentation for each
 * step. [WalletPresentation] has no `Loading` variant of its own (the restore is synchronous,
 * no native-suspend boundary crossed), so [walletLoading] tracks that step's in-flight state
 * separately; every other step's own `Loading` variant is used directly.
 *
 * ### Provider selection (mock vs live Blockfrost preprod)
 *
 * [useLiveBlockfrost] and [projectId] mirror the existing "Use live Blockfrost (preprod)"
 * toggle and `project_id` field: the default is the in-memory mock; enabling the toggle with a
 * non-blank [projectId] switches both the query and submit provider to live Blockfrost preprod
 * (see [org.sarmidev.kardano.playground.data.PlaygroundProviderFactory]). [projectId] is the
 * session field the visitor typed. The provider factory also retains the last live id as an
 * in-memory cache key so a repeated live request can reuse the same Blockfrost client; that
 * cache is dropped immediately when the id changes or live mode is disabled
 * ([org.sarmidev.kardano.playground.data.PlaygroundProviderFactory.invalidateLiveCache]).
 * Neither copy is persisted or logged.
 *
 * ### Operation generations
 *
 * [flowGeneration] is a monotonic counter. [PlaygroundIntent.ResetFlow], an actual live-provider
 * toggle change, and an actual [projectId] change each increment it. [PlaygroundViewModel]
 * captures the generation when a Funds/Build/Sign/Submit/diagnostic operation starts and ignores
 * any result whose generation is no longer current, so a slow request cannot overwrite the
 * visitor's newer configuration.
 *
 * [fundsRequestToken], [draftRequestToken], [signedRequestToken], and [submitRequestToken]
 * increment on each start of that guided operation, whenever an *upstream* guided step starts
 * (Funds clears Build/Sign/Submit; Build clears Sign/Submit; Sign clears Submit), and whenever
 * ResetFlow or an actual provider-configuration change invalidates in-flight work. Starting an
 * upstream step also sets those downstream presentations to Empty (completed results included)
 * so Continue cannot advance on a stale later step. A repeated same-step request therefore
 * cannot be overwritten by a slower first call that still shares [flowGeneration]. Wallet
 * restore is synchronous (no Job), so it has no request token. The reducer stays a pure
 * function of `(state, intent)` — it never cancels work; the ViewModel holds/cancels
 * [kotlinx.coroutines.Job]s.
 *
 * ### Diagnostics (Address Parser, Hex Decoder, CBOR Decoder, generic Provider explorer)
 *
 * [addressInput]/[addressResult], [hexInput]/[hexResult], [cborInput]/[cborResult], and
 * [providerAddressInput]/[providerUtxos]/[providerParams] back the standalone diagnostic tools
 * shown below the guided flow — unrelated to the fixture wallet, kept for structural
 * exploration of `:core`/`:provider` APIs.
 *
 * [providerUtxosRequestToken] increments on each UTxO load and on an actual explorer-address
 * change (typed or seed-fill) so a result for address A cannot apply after the field shows B,
 * and a repeated load cannot overwrite a newer one. [providerParamsRequestToken] increments on
 * each protocol-parameters load for the same reason. Both are independent of [flowGeneration].
 *
 * ### Technical details
 *
 * [technicalDetailsExpanded] names which steps currently show their expanded/technical view
 * (for example a full hex preview instead of a summary row); collapsed by default.
 *
 * ### Landing/overview (Block 1.12-pre-c)
 *
 * [codeExamplesExpanded] tracks whether the landing overview's "Code examples" section is
 * expanded; collapsed by default. It is a presentation-only flag for the developer-facing
 * landing area shown above the guided flow — it carries no SDK semantics and gates nothing but
 * the visibility of static, illustrative snippets.
 *
 * ### Section navigation + roadmap (Block 1.12-pre-c-2, restructured in Block 1.12-pre-e)
 *
 * [section] selects which top-level sample-app section is shown; it defaults to
 * [PlaygroundSection.WELCOME]. [demoStep] is the single guided-flow step currently shown on the
 * [PlaygroundSection.DEMO] screen (Block 1.12-pre-e's one-step-at-a-time journey); it defaults
 * to [PlaygroundStep.WALLET]. [PlaygroundDemoFlow][org.sarmidev.kardano.playground.mvi.PlaygroundDemoFlow]
 * derives gating (whether the visitor can continue) and outcome classification from [demoStep]
 * plus the matching `*Presentation` field — this class holds only the raw cursor, no derived
 * gating logic. [selectedRoadmapPhase] is the roadmap card whose detail is expanded (null = none
 * expanded). All three are presentation-only navigation state with no SDK semantics.
 */
internal data class PlaygroundState(
    val useLiveBlockfrost: Boolean,
    val projectId: String,
    /**
     * Monotonic operation-generation counter. Incremented by ResetFlow and by actual provider-
     * configuration changes (live toggle or project-id string). Provider-backed results whose
     * captured generation no longer matches this value are discarded.
     */
    val flowGeneration: Long = 0L,
    val wallet: WalletPresentation,
    val walletLoading: Boolean,
    val funds: WalletBalancePresentation,
    val draft: TransactionDraftPresentation,
    val signed: SignedTransactionPresentation,
    val submit: SubmitTransactionPresentation,
    val fundsRequestToken: Long = 0L,
    val draftRequestToken: Long = 0L,
    val signedRequestToken: Long = 0L,
    val submitRequestToken: Long = 0L,
    val technicalDetailsExpanded: Set<PlaygroundStep>,
    val addressInput: String,
    val addressResult: AddressPresentation,
    val hexInput: String,
    val hexResult: HexPresentation?,
    val cborInput: String,
    val cborResult: CborPresentation?,
    val providerAddressInput: String,
    val providerUtxos: ProviderUtxosPresentation,
    val providerParams: ProviderParamsPresentation,
    val providerUtxosRequestToken: Long = 0L,
    val providerParamsRequestToken: Long = 0L,
    val codeExamplesExpanded: Boolean = false,
    val section: PlaygroundSection = PlaygroundSection.WELCOME,
    val selectedRoadmapPhase: RoadmapPhase? = RoadmapPhase.PHASE_1,
    val demoStep: PlaygroundStep = PlaygroundStep.WALLET,
) {
    /**
     * Whether the provider factory can actually use live Blockfrost preprod.
     *
     * Turning on the advanced switch expresses intent only; the factory continues to serve the
     * offline mock until a non-blank project id is present. UI copy and outcome classification
     * must use this effective state rather than [useLiveBlockfrost] alone.
     */
    val isLivePreprodActive: Boolean
        get() = useLiveBlockfrost && projectId.isNotBlank()

    companion object {
        /**
         * The initial state: the Welcome section, the guided demo cursor at the first
         * ([PlaygroundStep.WALLET]) step, the Phase 1 roadmap card pre-expanded, mock provider,
         * every guided step empty/collapsed, and the diagnostics defaults.
         */
        fun initial(): PlaygroundState = PlaygroundState(
            useLiveBlockfrost = false,
            projectId = "",
            flowGeneration = 0L,
            wallet = WalletPresentation.Empty,
            walletLoading = false,
            funds = WalletBalancePresentation.Empty,
            draft = TransactionDraftPresentation.Empty,
            signed = SignedTransactionPresentation.Empty,
            submit = SubmitTransactionPresentation.Empty,
            fundsRequestToken = 0L,
            draftRequestToken = 0L,
            signedRequestToken = 0L,
            submitRequestToken = 0L,
            technicalDetailsExpanded = emptySet(),
            addressInput = "",
            addressResult = AddressPresentation.Empty,
            hexInput = "",
            hexResult = null,
            cborInput = "",
            cborResult = null,
            providerAddressInput = InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS,
            providerUtxos = ProviderUtxosPresentation.Empty,
            providerParams = ProviderParamsPresentation.Empty,
            providerUtxosRequestToken = 0L,
            providerParamsRequestToken = 0L,
            codeExamplesExpanded = false,
            section = PlaygroundSection.WELCOME,
            selectedRoadmapPhase = RoadmapPhase.PHASE_1,
            demoStep = PlaygroundStep.WALLET,
        )
    }
}
