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
 * Which top-level Playground section is currently shown (Block 1.12-pre-c-2). This is a
 * sample-app navigation concept only — a lightweight in-state switch between the landing
 * overview, the interactive transaction flow, and the roadmap screen. It is not an SDK concept
 * and is not part of any public API.
 */
internal enum class PlaygroundSection {
    OVERVIEW,
    TRY_SDK,
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
 * (see [org.sarmidev.kardano.playground.data.PlaygroundProviderFactory]). [projectId] is held
 * only in this in-memory state — never persisted, saved, or logged.
 *
 * ### Diagnostics (Address Parser, Hex Decoder, CBOR Decoder, generic Provider explorer)
 *
 * [addressInput]/[addressResult], [hexInput]/[hexResult], [cborInput]/[cborResult], and
 * [providerAddressInput]/[providerUtxos]/[providerParams] back the standalone diagnostic tools
 * shown below the guided flow — unrelated to the fixture wallet, kept for structural
 * exploration of `:core`/`:provider` APIs.
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
 * ### Section navigation + roadmap (Block 1.12-pre-c-2)
 *
 * [section] selects which top-level sample-app section is shown — the landing [OVERVIEW]
 * [PlaygroundSection.OVERVIEW], the interactive [TRY_SDK][PlaygroundSection.TRY_SDK] flow, or the
 * [ROADMAP][PlaygroundSection.ROADMAP] screen; it defaults to `OVERVIEW`.
 * [selectedRoadmapPhase] is the roadmap card whose detail is expanded (null = none expanded).
 * Both are presentation-only navigation state with no SDK semantics.
 */
internal data class PlaygroundState(
    val useLiveBlockfrost: Boolean,
    val projectId: String,
    val wallet: WalletPresentation,
    val walletLoading: Boolean,
    val funds: WalletBalancePresentation,
    val draft: TransactionDraftPresentation,
    val signed: SignedTransactionPresentation,
    val submit: SubmitTransactionPresentation,
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
    val codeExamplesExpanded: Boolean = false,
    val section: PlaygroundSection = PlaygroundSection.OVERVIEW,
    val selectedRoadmapPhase: RoadmapPhase? = RoadmapPhase.PHASE_1,
) {
    companion object {
        /**
         * The initial state: the Overview section, the Phase 1 roadmap card pre-expanded, mock
         * provider, every guided step empty/collapsed, and the diagnostics defaults.
         */
        fun initial(): PlaygroundState = PlaygroundState(
            useLiveBlockfrost = false,
            projectId = "",
            wallet = WalletPresentation.Empty,
            walletLoading = false,
            funds = WalletBalancePresentation.Empty,
            draft = TransactionDraftPresentation.Empty,
            signed = SignedTransactionPresentation.Empty,
            submit = SubmitTransactionPresentation.Empty,
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
            codeExamplesExpanded = false,
            section = PlaygroundSection.OVERVIEW,
            selectedRoadmapPhase = RoadmapPhase.PHASE_1,
        )
    }
}
