package org.sarmidev.kardano.playground

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import org.sarmidev.kardano.Greeting
import org.sarmidev.kardano.playground.mvi.PlaygroundIntent
import org.sarmidev.kardano.playground.mvi.PlaygroundSection
import org.sarmidev.kardano.playground.mvi.PlaygroundState
import org.sarmidev.kardano.playground.mvi.PlaygroundStep
import org.sarmidev.kardano.playground.mvi.PlaygroundViewModel
import org.sarmidev.kardano.playground.ui.Badge
import org.sarmidev.kardano.playground.ui.BadgeTone
import org.sarmidev.kardano.playground.ui.DiagnosticsSection
import org.sarmidev.kardano.playground.ui.ErrorInline
import org.sarmidev.kardano.playground.ui.FlowStepCard
import org.sarmidev.kardano.playground.ui.FlowStepper
import org.sarmidev.kardano.playground.ui.KardanoPlaygroundTheme
import org.sarmidev.kardano.playground.ui.LabeledRows
import org.sarmidev.kardano.playground.ui.LoadingInline
import org.sarmidev.kardano.playground.ui.PlaygroundHeader
import org.sarmidev.kardano.playground.ui.PlaygroundLanding
import org.sarmidev.kardano.playground.ui.ResultRow
import org.sarmidev.kardano.playground.ui.RoadmapScreen
import org.sarmidev.kardano.playground.ui.SectionHeader
import org.sarmidev.kardano.playground.ui.StepStatus
import org.sarmidev.kardano.playground.ui.StepTone

/**
 * The SDK Playground screen: a small developer-facing landing/demo of the Kardano SDK MVP,
 * restructured into an MVI architecture in Block 1.12-pre-a, given its guided visual/UX
 * presentation in Block 1.12-pre-b, and fronted by a landing/overview area in Block 1.12-pre-c.
 *
 * This composable is a pure renderer: it reads [PlaygroundState] from [PlaygroundViewModel] and
 * dispatches [PlaygroundIntent]s for every user action — it computes nothing itself. All
 * SDK-calling logic lives in [PlaygroundViewModel], its use cases (`playground/domain`), and its
 * provider factory (`playground/data`), which call [PlaygroundPresenter]; the UI package
 * (`playground/ui`) holds only presentation-shell composables (header/landing, step card,
 * badges, diagnostics), none of which reach an SDK API.
 *
 * ### Section navigation (Block 1.12-pre-c-2)
 *
 * A top navigation row switches between three sample-app sections driven by
 * [PlaygroundState.section]: **Overview** (the landing hero + [PlaygroundLanding] — what the SDK
 * does today, a developer-friendly flow preview, optional code snippets, and a link into the
 * roadmap), **Try SDK** (the interactive flow + diagnostics), and **Roadmap**
 * ([RoadmapScreen] — Phase 0–3 cards with tap-to-expand detail). Navigation and roadmap phase
 * selection are presentation-only state; they call no SDK.
 *
 * ### Interactive flow (unchanged behavior)
 *
 * In the **Try SDK** section, the SDK MVP is exercised as a step-based guided flow — **Wallet →
 * Funds → Build → Sign → Submit** — setting up [TestWalletFixture]'s cited test-only mnemonic
 * (never a real mnemonic, never real funds), querying whichever provider is active (an in-memory
 * mock by default, or live Blockfrost preprod once configured) for that wallet's balance,
 * building a minimal unsigned ADA-only transaction draft, signing it, and finally submitting it.
 * A visually secondary **Diagnostics** area holds standalone tools (Address Parser, Hex Decoder,
 * CBOR Decoder, and a generic Provider explorer) unrelated to the fixture wallet. Testnet/preprod
 * only, everywhere; no mainnet, no real mnemonic/private-key display, and no full (untruncated)
 * CBOR display — see [PlaygroundState] and [PlaygroundPresenter] for the exact display rules
 * each `*Presentation` type follows.
 *
 * The root container (Block 1.12-pre-b polish) paints a subtle theme-derived gradient — from
 * [MaterialTheme.colorScheme]'s `surface` into its `background`, continuing the tone
 * [org.sarmidev.kardano.playground.ui.PlaygroundHeader]'s own gradient ends on — instead of the
 * platform's default (white) window background, and applies [Modifier.safeDrawingPadding] so
 * content never starts under the status bar and the controls at the bottom are never hidden
 * behind the navigation bar. [Modifier.safeDrawingPadding] is a Compose-Multiplatform-common API
 * (`expect`/`actual` per target); no Android-specific inset code was added here.
 *
 * This is sample/diagnostic code in `:shared`. It is not part of the SDK public API.
 */
@Composable
internal fun PlaygroundScreen() {
    val platformLabel = remember { Greeting().greet() }
    val viewModel = viewModel { PlaygroundViewModel() }
    val state by viewModel.state.collectAsStateWithLifecycle()
    val dispatch: (PlaygroundIntent) -> Unit = viewModel::dispatch

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(MaterialTheme.colorScheme.surface, MaterialTheme.colorScheme.background),
                ),
            )
            .safeDrawingPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        SectionNav(current = state.section, dispatch = dispatch)

        when (state.section) {
            PlaygroundSection.OVERVIEW -> OverviewSection(state, platformLabel, dispatch)
            PlaygroundSection.TRY_SDK -> TrySdkSection(state, dispatch)
            PlaygroundSection.ROADMAP -> RoadmapScreen(
                selected = state.selectedRoadmapPhase,
                onSelect = { dispatch(PlaygroundIntent.SelectRoadmapPhase(it)) },
            )
        }
    }
}

/** The top navigation between the Overview, Try SDK, and Roadmap sections (sample-app only). */
@Composable
private fun SectionNav(current: PlaygroundSection, dispatch: (PlaygroundIntent) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        NavButton("Overview", current == PlaygroundSection.OVERVIEW, Modifier.weight(1f)) {
            dispatch(PlaygroundIntent.NavigateToOverview)
        }
        NavButton("Try SDK", current == PlaygroundSection.TRY_SDK, Modifier.weight(1f)) {
            dispatch(PlaygroundIntent.NavigateToTrySdk)
        }
        NavButton("Roadmap", current == PlaygroundSection.ROADMAP, Modifier.weight(1f)) {
            dispatch(PlaygroundIntent.NavigateToRoadmap)
        }
    }
}

@Composable
private fun NavButton(label: String, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    if (selected) {
        Button(onClick = onClick, modifier = modifier) { Text(label) }
    } else {
        OutlinedButton(onClick = onClick, modifier = modifier) { Text(label) }
    }
}

/** The Overview section: the landing hero plus [PlaygroundLanding]. */
@Composable
private fun OverviewSection(
    state: PlaygroundState,
    platformLabel: String,
    dispatch: (PlaygroundIntent) -> Unit,
) {
    PlaygroundHeader(
        platformLabel = platformLabel,
        onTryFlow = { dispatch(PlaygroundIntent.NavigateToTrySdk) },
    )
    PlaygroundLanding(
        codeExamplesExpanded = state.codeExamplesExpanded,
        onToggleCodeExamples = { dispatch(PlaygroundIntent.ToggleCodeExamples) },
        onOpenRoadmap = { dispatch(PlaygroundIntent.NavigateToRoadmap) },
    )
}

/** The Try SDK section: the guided transaction flow, reset control, and secondary diagnostics. */
@Composable
private fun TrySdkSection(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        SectionHeader(
            title = "Try it: the transaction flow",
            subtitle = "Run each step against the mock provider, or switch on preprod below.",
        )
        FlowStepper(flowCompletion(state))
        ProviderConfigCard(state, dispatch)

        WalletStep(state, dispatch)
        FundsStep(state, dispatch)
        BuildStep(state, dispatch)
        SignStep(state, dispatch)
        SubmitStep(state, dispatch)

        OutlinedButton(
            onClick = { dispatch(PlaygroundIntent.ResetFlow) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Reset flow")
        }

        DiagnosticsSection(state, dispatch)
    }
}

private fun flowCompletion(state: PlaygroundState): List<Boolean> = listOf(
    state.wallet is WalletPresentation.Success,
    state.funds is WalletBalancePresentation.Success,
    state.draft is TransactionDraftPresentation.Success,
    state.signed is SignedTransactionPresentation.Success,
    state.submit is SubmitTransactionPresentation.Success,
)

/** The shared "Live Blockfrost (preprod)" toggle and `project_id` field driving every step. */
@Composable
private fun ProviderConfigCard(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(text = "Provider", style = MaterialTheme.typography.titleSmall)
                    Text(
                        text = if (state.useLiveBlockfrost) {
                            "Live Blockfrost preprod — real network calls, test funds only."
                        } else {
                            "In-memory mock — fake local UTxOs, test-only, no network. Submit is " +
                                "not supported here."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = state.useLiveBlockfrost,
                    onCheckedChange = { dispatch(PlaygroundIntent.ToggleLiveBlockfrost(it)) },
                )
            }
            if (state.useLiveBlockfrost) {
                OutlinedTextField(
                    value = state.projectId,
                    onValueChange = { dispatch(PlaygroundIntent.UpdateProjectId(it)) },
                    label = { Text("Blockfrost project_id (preprod, not stored)") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Guided flow steps: Wallet -> Funds -> Build -> Sign -> Submit
// ---------------------------------------------------------------------------

@Composable
private fun WalletStep(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    val wallet = state.wallet
    val status = when {
        state.walletLoading -> StepStatus("Creating…", StepTone.LOADING)
        wallet is WalletPresentation.Success -> StepStatus("Ready", StepTone.SUCCESS)
        wallet is WalletPresentation.Failure -> StepStatus("Failed", StepTone.ERROR)
        else -> StepStatus("Not started", StepTone.IDLE)
    }
    FlowStepCard(
        stepNumber = 1,
        title = "Create test wallet",
        explanation = "Set up the built-in test-only wallet and generate its testnet address.",
        status = status,
        badges = listOf(Badge("TESTNET", BadgeTone.NEUTRAL)),
        actionLabel = if (state.walletLoading) "Creating…" else "Create test wallet",
        actionLoading = state.walletLoading,
        onAction = { dispatch(PlaygroundIntent.RestoreWallet) },
        showDetailsToggle = wallet is WalletPresentation.Success,
        detailsExpanded = PlaygroundStep.WALLET in state.technicalDetailsExpanded,
        onToggleDetails = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.WALLET)) },
        keyOutput = {
            when (wallet) {
                is WalletPresentation.Empty -> if (state.walletLoading) LoadingInline()
                is WalletPresentation.Success ->
                    wallet.rows.value("Generated address")?.let { ResultRow("Generated address", it) }
                is WalletPresentation.Failure -> ErrorInline(wallet.message)
            }
        },
        details = {
            if (wallet is WalletPresentation.Success) {
                Text(
                    text = "Under the hood this calls ReadOnlyWallet.restore(...) with a cited " +
                        "public test-only mnemonic fixture — never a real wallet, mnemonic, or " +
                        "private key, and never real funds.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                LabeledRows(
                    wallet.rows + LabeledRow(
                        "Matches cited vector",
                        if (wallet.fingerprintMatchesVector) "yes" else "no",
                    ),
                )
            }
        },
    )
}

@Composable
private fun FundsStep(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    val funds = state.funds
    FlowStepCard(
        stepNumber = 2,
        title = "Check available test ADA",
        explanation = "Query the wallet's balance and UTxO count from the active provider " +
            "(mock or preprod).",
        status = presentationStatus(
            isLoading = funds is WalletBalancePresentation.Loading,
            isSuccess = funds is WalletBalancePresentation.Success,
            isFailure = funds is WalletBalancePresentation.Failure,
            successLabel = "Loaded",
        ),
        badges = listOf(providerBadge(state.useLiveBlockfrost)),
        actionLabel = "Query wallet balance",
        actionLoading = funds is WalletBalancePresentation.Loading,
        onAction = { dispatch(PlaygroundIntent.QueryFunds) },
        showDetailsToggle = funds is WalletBalancePresentation.Success,
        detailsExpanded = PlaygroundStep.FUNDS in state.technicalDetailsExpanded,
        onToggleDetails = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.FUNDS)) },
        keyOutput = {
            when (funds) {
                is WalletBalancePresentation.Empty -> Unit
                is WalletBalancePresentation.Loading -> LoadingInline()
                is WalletBalancePresentation.Success -> {
                    funds.rows.value("Balance")?.let { ResultRow("Balance", it) }
                    funds.rows.value("UTxO count")?.let { ResultRow("UTxO count", it) }
                }
                is WalletBalancePresentation.Failure -> ErrorInline(funds.message)
            }
        },
        details = { if (funds is WalletBalancePresentation.Success) LabeledRows(funds.rows) },
    )
}

@Composable
private fun BuildStep(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    val draft = state.draft
    FlowStepCard(
        stepNumber = 3,
        title = "Prepare a transaction",
        explanation = "Build a minimal, unsigned, ADA-only transaction draft from the wallet's UTxOs.",
        status = presentationStatus(
            isLoading = draft is TransactionDraftPresentation.Loading,
            isSuccess = draft is TransactionDraftPresentation.Success,
            isFailure = draft is TransactionDraftPresentation.Failure,
            successLabel = "Built",
        ),
        badges = listOf(Badge("ADA-only", BadgeTone.NEUTRAL)),
        actionLabel = "Build transaction draft",
        actionLoading = draft is TransactionDraftPresentation.Loading,
        onAction = { dispatch(PlaygroundIntent.BuildDraft) },
        showDetailsToggle = draft is TransactionDraftPresentation.Success,
        detailsExpanded = PlaygroundStep.BUILD in state.technicalDetailsExpanded,
        onToggleDetails = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.BUILD)) },
        keyOutput = {
            when (draft) {
                is TransactionDraftPresentation.Empty -> Unit
                is TransactionDraftPresentation.Loading -> LoadingInline()
                is TransactionDraftPresentation.Success -> {
                    draft.rows.value("Selected inputs")?.let { ResultRow("Selected inputs", it) }
                    draft.rows.value("Fee")?.let { ResultRow("Fee", it) }
                    draft.rows.value("Change")?.let { ResultRow("Change", it) }
                }
                is TransactionDraftPresentation.Failure -> ErrorInline(draft.message)
            }
        },
        details = { if (draft is TransactionDraftPresentation.Success) LabeledRows(draft.rows) },
    )
}

@Composable
private fun SignStep(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    val signed = state.signed
    FlowStepCard(
        stepNumber = 4,
        title = "Sign it locally",
        explanation = "Sign the draft on-device with the fixture wallet — nothing is sent yet.",
        status = presentationStatus(
            isLoading = signed is SignedTransactionPresentation.Loading,
            isSuccess = signed is SignedTransactionPresentation.Success,
            isFailure = signed is SignedTransactionPresentation.Failure,
            successLabel = "Signed",
        ),
        badges = if (signed is SignedTransactionPresentation.Success) {
            listOf(Badge("SIGNED", BadgeTone.SUCCESS))
        } else {
            emptyList()
        },
        actionLabel = "Sign transaction",
        actionLoading = signed is SignedTransactionPresentation.Loading,
        onAction = { dispatch(PlaygroundIntent.SignTransaction) },
        showDetailsToggle = signed is SignedTransactionPresentation.Success,
        detailsExpanded = PlaygroundStep.SIGN in state.technicalDetailsExpanded,
        onToggleDetails = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.SIGN)) },
        keyOutput = {
            when (signed) {
                is SignedTransactionPresentation.Empty -> Unit
                is SignedTransactionPresentation.Loading -> LoadingInline()
                is SignedTransactionPresentation.Success -> {
                    signed.rows.value("Transaction id")?.let { ResultRow("Transaction id", it) }
                    signed.rows.value("Witnesses")?.let { ResultRow("Witnesses", it) }
                }
                is SignedTransactionPresentation.Failure -> ErrorInline(signed.message)
            }
        },
        details = { if (signed is SignedTransactionPresentation.Success) LabeledRows(signed.rows) },
    )
}

@Composable
private fun SubmitStep(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    val submit = state.submit
    FlowStepCard(
        stepNumber = 5,
        title = "Send it to preprod",
        explanation = "Submit the signed transaction to the active provider " +
            "(the mock reports \"not supported\"; live preprod can accept the submission).",
        status = presentationStatus(
            isLoading = submit is SubmitTransactionPresentation.Loading,
            isSuccess = submit is SubmitTransactionPresentation.Success,
            isFailure = submit is SubmitTransactionPresentation.Failure,
            successLabel = "Submitted",
        ),
        badges = buildList {
            add(providerBadge(state.useLiveBlockfrost))
            if (submit is SubmitTransactionPresentation.Success) add(Badge("SUBMITTED", BadgeTone.SUCCESS))
        },
        actionLabel = "Submit transaction",
        actionLoading = submit is SubmitTransactionPresentation.Loading,
        onAction = { dispatch(PlaygroundIntent.SubmitTransaction) },
        showDetailsToggle = submit is SubmitTransactionPresentation.Success,
        detailsExpanded = PlaygroundStep.SUBMIT in state.technicalDetailsExpanded,
        onToggleDetails = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.SUBMIT)) },
        keyOutput = {
            when (submit) {
                is SubmitTransactionPresentation.Empty -> Unit
                is SubmitTransactionPresentation.Loading -> LoadingInline()
                is SubmitTransactionPresentation.Success -> {
                    submit.rows.value("Accepted transaction id")
                        ?.let { ResultRow("Accepted transaction id", it) }
                    submit.rows.value("Ids match")?.let { ResultRow("Ids match", it) }
                }
                is SubmitTransactionPresentation.Failure -> ErrorInline(submit.message)
            }
        },
        details = { if (submit is SubmitTransactionPresentation.Success) LabeledRows(submit.rows) },
    )
}

// ---------------------------------------------------------------------------
// Small presentation helpers
// ---------------------------------------------------------------------------

private fun List<LabeledRow>.value(label: String): String? =
    firstOrNull { it.label == label }?.value

private fun providerBadge(useLive: Boolean): Badge =
    if (useLive) Badge("LIVE PREPROD", BadgeTone.LIVE) else Badge("MOCK", BadgeTone.INFO)

private fun presentationStatus(
    isLoading: Boolean,
    isSuccess: Boolean,
    isFailure: Boolean,
    successLabel: String,
): StepStatus = when {
    isLoading -> StepStatus("Working…", StepTone.LOADING)
    isSuccess -> StepStatus(successLabel, StepTone.SUCCESS)
    isFailure -> StepStatus("Failed", StepTone.ERROR)
    else -> StepStatus("Not started", StepTone.IDLE)
}

// ---------------------------------------------------------------------------
// Preview
// ---------------------------------------------------------------------------

@Preview
@Composable
private fun PlaygroundScreenPreview() {
    KardanoPlaygroundTheme {
        PlaygroundScreen()
    }
}
