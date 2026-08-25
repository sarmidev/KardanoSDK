package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import org.sarmidev.kardano.playground.LabeledRow
import org.sarmidev.kardano.playground.MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE
import org.sarmidev.kardano.playground.SignedTransactionPresentation
import org.sarmidev.kardano.playground.SubmitTransactionPresentation
import org.sarmidev.kardano.playground.TransactionDraftPresentation
import org.sarmidev.kardano.playground.WalletBalancePresentation
import org.sarmidev.kardano.playground.WalletPresentation
import org.sarmidev.kardano.playground.mvi.PlaygroundDemoFlow
import org.sarmidev.kardano.playground.mvi.PlaygroundIntent
import org.sarmidev.kardano.playground.mvi.PlaygroundState
import org.sarmidev.kardano.playground.mvi.PlaygroundStep
import org.sarmidev.kardano.playground.mvi.StepOutcome

/**
 * The single-step-at-a-time guided demo (Block 1.12-pre-e): the plain-language progress line,
 * a compact recap strip of finished steps, one [FlowStepCard] for [PlaygroundState.demoStep],
 * a *Start over* control, and a collapsed *Advanced: connect to a test network* disclosure
 * holding the Mock/Live switch. Reads [PlaygroundState] and dispatches [PlaygroundIntent]s only
 * — the actual step outcome/gating logic lives in [PlaygroundDemoFlow], not here.
 */
@Composable
internal fun DemoStepSection(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        ProgressLine(state)
        RecapStrip(state)
        StepCard(state, dispatch)

        OutlinedButton(
            onClick = { dispatch(PlaygroundIntent.ResetFlow) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(DemoCopy.Chrome.START_OVER_BUTTON)
        }

        AdvancedDisclosure(state, dispatch)
    }
}

@Composable
private fun ProgressLine(state: PlaygroundState) {
    val stepNumber = PlaygroundDemoFlow.stepNumber(state.demoStep)
    val stepCount = PlaygroundDemoFlow.stepCount
    val completed = PlaygroundDemoFlow.completedSteps(state)
    Text(
        text = DemoCopy.Chrome.progress(stepNumber, stepCount),
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.semantics {
            contentDescription =
                "Step $stepNumber of $stepCount, $completed step${if (completed == 1) "" else "s"} complete"
        },
    )
}

@Composable
private fun RecapStrip(state: PlaygroundState) {
    val currentIndex = PlaygroundDemoFlow.stepNumber(state.demoStep) - 1
    if (currentIndex <= 0) return
    val labels = DemoCopy.Summary.recapLines(wasLiveSubmission = state.isLivePreprodActive).take(currentIndex)
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        labels.forEachIndexed { index, label ->
            Text(
                text = DemoCopy.Chrome.recapEntry(index + 1, label),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

// ---------------------------------------------------------------------------
// The single step card
// ---------------------------------------------------------------------------

@Composable
private fun StepCard(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    when (state.demoStep) {
        PlaygroundStep.WALLET -> WalletStepCard(state, dispatch)
        PlaygroundStep.FUNDS -> FundsStepCard(state, dispatch)
        PlaygroundStep.BUILD -> BuildStepCard(state, dispatch)
        PlaygroundStep.SIGN -> SignStepCard(state, dispatch)
        PlaygroundStep.SUBMIT -> SubmitStepCard(state, dispatch)
    }
}

/** The Back / Continue (or See the summary) row shared by every step card. */
private fun continueBackActions(
    state: PlaygroundState,
    dispatch: (PlaygroundIntent) -> Unit,
): @Composable RowScope.() -> Unit = {
    if (PlaygroundDemoFlow.previousStep(state.demoStep) != null) {
        OutlinedButton(
            onClick = { dispatch(PlaygroundIntent.BackDemo) },
            modifier = Modifier.weight(1f),
        ) {
            Text(DemoCopy.Chrome.BACK_BUTTON)
        }
    }
    val isLastStep = PlaygroundDemoFlow.nextStep(state.demoStep) == null
    Button(
        onClick = { dispatch(PlaygroundIntent.ContinueDemo) },
        enabled = PlaygroundDemoFlow.canContinue(state),
        modifier = Modifier.weight(1f),
    ) {
        Text(if (isLastStep) DemoCopy.Chrome.CONTINUE_LAST_STEP_BUTTON else DemoCopy.Chrome.CONTINUE_BUTTON)
    }
}

private fun List<LabeledRow>.value(label: String): String? =
    firstOrNull { it.label == label }?.value

@Composable
private fun WalletStepCard(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    val copy = DemoCopy.steps.getValue(PlaygroundStep.WALLET)
    val wallet = state.wallet
    val outcome = PlaygroundDemoFlow.outcome(state, PlaygroundStep.WALLET)

    val (statusLabel, tone) = statusFor(copy, outcome)
    val (headline, detail) = when {
        outcome == StepOutcome.DONE && wallet is WalletPresentation.Success -> {
            val shortAddress = wallet.rows.value("Generated address")
                ?.let(PlaygroundDemoFlow::shortenAddress) ?: ""
            copy.doneHeadline to DemoCopy.walletDoneDetail(shortAddress)
        }
        outcome == StepOutcome.ERROR && wallet is WalletPresentation.Failure ->
            copy.errorHeadline to (PlaygroundDemoFlow.friendlyReason(PlaygroundStep.WALLET, wallet.message) ?: wallet.message)
        else -> null to null
    }

    FlowStepCard(
        stepNumber = PlaygroundDemoFlow.stepNumber(PlaygroundStep.WALLET),
        stepCount = PlaygroundDemoFlow.stepCount,
        title = copy.title,
        explanation = copy.why,
        status = StepStatus(statusLabel, tone),
        actionLabel = if (outcome == StepOutcome.WORKING) copy.workingLabel else copy.actionLabel,
        actionLoading = outcome == StepOutcome.WORKING,
        onAction = { dispatch(PlaygroundIntent.RestoreWallet) },
        resultHeadline = headline,
        resultDetail = detail,
        resultIsError = outcome == StepOutcome.ERROR,
        guidance = if (outcome == StepOutcome.DONE) copy.guidance else null,
        showDetailsToggle = outcome == StepOutcome.DONE,
        detailsExpanded = PlaygroundStep.WALLET in state.technicalDetailsExpanded,
        onToggleDetails = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.WALLET)) },
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
        secondaryActions = continueBackActions(state, dispatch),
    )
}

@Composable
private fun FundsStepCard(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    val copy = DemoCopy.steps.getValue(PlaygroundStep.FUNDS)
    val funds = state.funds
    val outcome = PlaygroundDemoFlow.outcome(state, PlaygroundStep.FUNDS)

    val (statusLabel, tone) = statusFor(copy, outcome)
    val (headline, detail) = when {
        outcome == StepOutcome.DONE && funds is WalletBalancePresentation.Success -> {
            val ada = funds.rows.value("Test ADA") ?: "0 ADA"
            val hasFunds = ada != "0 ADA"
            val baseDetail = DemoCopy.fundsDoneDetail(hasFunds)
            val fullDetail = if (!hasFunds && state.isLivePreprodActive) {
                "$baseDetail ${DemoCopy.FUNDS_ZERO_BALANCE_GUIDANCE_LIVE}"
            } else {
                baseDetail
            }
            DemoCopy.fundsDoneHeadline(ada) to fullDetail
        }
        outcome == StepOutcome.ERROR && funds is WalletBalancePresentation.Failure ->
            copy.errorHeadline to (PlaygroundDemoFlow.friendlyReason(PlaygroundStep.FUNDS, funds.message) ?: funds.message)
        else -> null to null
    }

    FlowStepCard(
        stepNumber = PlaygroundDemoFlow.stepNumber(PlaygroundStep.FUNDS),
        stepCount = PlaygroundDemoFlow.stepCount,
        title = copy.title,
        explanation = copy.why,
        status = StepStatus(statusLabel, tone),
        actionLabel = if (outcome == StepOutcome.WORKING) copy.workingLabel else copy.actionLabel,
        actionLoading = outcome == StepOutcome.WORKING,
        onAction = { dispatch(PlaygroundIntent.QueryFunds) },
        resultHeadline = headline,
        resultDetail = detail,
        resultIsError = outcome == StepOutcome.ERROR,
        guidance = if (outcome == StepOutcome.DONE) copy.guidance else null,
        showDetailsToggle = outcome == StepOutcome.DONE,
        detailsExpanded = PlaygroundStep.FUNDS in state.technicalDetailsExpanded,
        onToggleDetails = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.FUNDS)) },
        details = { if (funds is WalletBalancePresentation.Success) LabeledRows(funds.rows) },
        secondaryActions = continueBackActions(state, dispatch),
    )
}

@Composable
private fun BuildStepCard(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    val copy = DemoCopy.steps.getValue(PlaygroundStep.BUILD)
    val draft = state.draft
    val outcome = PlaygroundDemoFlow.outcome(state, PlaygroundStep.BUILD)

    val (statusLabel, tone) = statusFor(copy, outcome)
    val (headline, detail) = when {
        outcome == StepOutcome.DONE && draft is TransactionDraftPresentation.Success -> {
            val paymentAda = draft.rows.value("Payment") ?: ""
            val feeAda = draft.rows.value("Network cost") ?: ""
            val changeAda = draft.rows.value("Change back")
            DemoCopy.buildDoneHeadline(paymentAda) to DemoCopy.buildDoneDetail(feeAda, changeAda)
        }
        outcome == StepOutcome.ERROR && draft is TransactionDraftPresentation.Failure ->
            copy.errorHeadline to (PlaygroundDemoFlow.friendlyReason(PlaygroundStep.BUILD, draft.message) ?: draft.message)
        else -> null to null
    }

    FlowStepCard(
        stepNumber = PlaygroundDemoFlow.stepNumber(PlaygroundStep.BUILD),
        stepCount = PlaygroundDemoFlow.stepCount,
        title = copy.title,
        explanation = copy.why,
        status = StepStatus(statusLabel, tone),
        actionLabel = if (outcome == StepOutcome.WORKING) copy.workingLabel else copy.actionLabel,
        actionLoading = outcome == StepOutcome.WORKING,
        onAction = { dispatch(PlaygroundIntent.BuildDraft) },
        resultHeadline = headline,
        resultDetail = detail,
        resultIsError = outcome == StepOutcome.ERROR,
        guidance = if (outcome == StepOutcome.DONE) copy.guidance else null,
        showDetailsToggle = outcome == StepOutcome.DONE,
        detailsExpanded = PlaygroundStep.BUILD in state.technicalDetailsExpanded,
        onToggleDetails = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.BUILD)) },
        details = { if (draft is TransactionDraftPresentation.Success) LabeledRows(draft.rows) },
        secondaryActions = continueBackActions(state, dispatch),
    )
}

@Composable
private fun SignStepCard(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    val copy = DemoCopy.steps.getValue(PlaygroundStep.SIGN)
    val signed = state.signed
    val outcome = PlaygroundDemoFlow.outcome(state, PlaygroundStep.SIGN)

    val (statusLabel, tone) = statusFor(copy, outcome)
    val (headline, detail) = when {
        outcome == StepOutcome.DONE -> copy.doneHeadline to DemoCopy.SIGN_DONE_DETAIL
        outcome == StepOutcome.ERROR && signed is SignedTransactionPresentation.Failure ->
            copy.errorHeadline to (PlaygroundDemoFlow.friendlyReason(PlaygroundStep.SIGN, signed.message) ?: signed.message)
        else -> null to null
    }

    FlowStepCard(
        stepNumber = PlaygroundDemoFlow.stepNumber(PlaygroundStep.SIGN),
        stepCount = PlaygroundDemoFlow.stepCount,
        title = copy.title,
        explanation = copy.why,
        status = StepStatus(statusLabel, tone),
        actionLabel = if (outcome == StepOutcome.WORKING) copy.workingLabel else copy.actionLabel,
        actionLoading = outcome == StepOutcome.WORKING,
        onAction = { dispatch(PlaygroundIntent.SignTransaction) },
        resultHeadline = headline,
        resultDetail = detail,
        resultIsError = outcome == StepOutcome.ERROR,
        guidance = if (outcome == StepOutcome.DONE) copy.guidance else null,
        showDetailsToggle = outcome == StepOutcome.DONE,
        detailsExpanded = PlaygroundStep.SIGN in state.technicalDetailsExpanded,
        onToggleDetails = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.SIGN)) },
        details = { if (signed is SignedTransactionPresentation.Success) LabeledRows(signed.rows) },
        secondaryActions = continueBackActions(state, dispatch),
    )
}

@Composable
private fun SubmitStepCard(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    val copy = DemoCopy.steps.getValue(PlaygroundStep.SUBMIT)
    val submit = state.submit
    val outcome = PlaygroundDemoFlow.outcome(state, PlaygroundStep.SUBMIT)

    val (statusLabel, tone) = statusFor(copy, outcome)
    val (headline, detail) = when {
        outcome == StepOutcome.INFO -> DemoCopy.SUBMIT_MOCK_HEADLINE to DemoCopy.SUBMIT_MOCK_DETAIL
        outcome == StepOutcome.DONE && submit is SubmitTransactionPresentation.Success -> {
            val shortId = submit.rows.value("Accepted transaction id")
                ?.let(PlaygroundDemoFlow::shortenId) ?: ""
            DemoCopy.SUBMIT_LIVE_SUCCESS_HEADLINE to DemoCopy.submitLiveSuccessDetail(shortId)
        }
        outcome == StepOutcome.ERROR && submit is SubmitTransactionPresentation.Failure ->
            copy.errorHeadline to (PlaygroundDemoFlow.friendlyReason(PlaygroundStep.SUBMIT, submit.message) ?: submit.message)
        else -> null to null
    }

    FlowStepCard(
        stepNumber = PlaygroundDemoFlow.stepNumber(PlaygroundStep.SUBMIT),
        stepCount = PlaygroundDemoFlow.stepCount,
        title = copy.title,
        explanation = copy.why,
        status = StepStatus(statusLabel, tone),
        actionLabel = if (outcome == StepOutcome.WORKING) copy.workingLabel else copy.actionLabel,
        actionLoading = outcome == StepOutcome.WORKING,
        onAction = { dispatch(PlaygroundIntent.SubmitTransaction) },
        resultHeadline = headline,
        resultDetail = detail,
        resultIsError = outcome == StepOutcome.ERROR,
        guidance = if (outcome == StepOutcome.DONE || outcome == StepOutcome.INFO) copy.guidance else null,
        showDetailsToggle = outcome == StepOutcome.DONE || outcome == StepOutcome.INFO,
        detailsExpanded = PlaygroundStep.SUBMIT in state.technicalDetailsExpanded,
        onToggleDetails = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(PlaygroundStep.SUBMIT)) },
        details = {
            if (submit is SubmitTransactionPresentation.Success) LabeledRows(submit.rows)
            if (submit is SubmitTransactionPresentation.Failure) {
                Text(
                    text = submit.message,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        secondaryActions = continueBackActions(state, dispatch),
    )
}

private fun statusFor(copy: DemoCopy.StepCopy, outcome: StepOutcome): Pair<String, StepTone> = when (outcome) {
    StepOutcome.NOT_STARTED -> copy.statusNotStarted to StepTone.IDLE
    StepOutcome.WORKING -> copy.statusWorking to StepTone.LOADING
    StepOutcome.DONE -> copy.statusDone to StepTone.SUCCESS
    StepOutcome.INFO -> copy.statusInfo to StepTone.INFO
    StepOutcome.ERROR -> copy.statusError to StepTone.ERROR
}

// ---------------------------------------------------------------------------
// Previews (hand-built PlaygroundState — Block 1.12-pre-e §10)
// ---------------------------------------------------------------------------

@Preview
@Composable
private fun DemoStepSectionMidDemoPreview() {
    val state = PlaygroundState.initial().copy(
        demoStep = PlaygroundStep.FUNDS,
        wallet = WalletPresentation.Success(
            rows = listOf(LabeledRow("Generated address", "addr_test1qxy0000000000000000000000000000000000000000000000000000s68faae")),
            fingerprintMatchesVector = true,
        ),
    )
    KardanoPlaygroundTheme {
        DemoStepSection(state = state, dispatch = {})
    }
}

@Preview
@Composable
private fun DemoStepSectionMockStopPreview() {
    val state = PlaygroundState.initial().copy(
        demoStep = PlaygroundStep.SUBMIT,
        useLiveBlockfrost = false,
        submit = SubmitTransactionPresentation.Failure(MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE),
    )
    KardanoPlaygroundTheme {
        DemoStepSection(state = state, dispatch = {})
    }
}

// ---------------------------------------------------------------------------
// Advanced: connect to a test network (the Mock/Live switch, collapsed by default)
// ---------------------------------------------------------------------------

@Composable
private fun AdvancedDisclosure(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    var expanded by remember { mutableStateOf(false) }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(
            onClick = { expanded = !expanded },
            modifier = Modifier
                .fillMaxWidth()
                .disclosureSemantics(
                    expanded = expanded,
                    label = if (expanded) "Advanced expanded" else "Advanced collapsed",
                    onToggle = { expanded = !expanded },
                ),
        ) {
            Text(
                if (expanded) {
                    DemoCopy.Chrome.Advanced.DISCLOSURE_LABEL_EXPANDED
                } else {
                    DemoCopy.Chrome.Advanced.DISCLOSURE_LABEL
                },
            )
        }
        if (expanded) {
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        text = DemoCopy.Chrome.Advanced.BODY,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = DemoCopy.Chrome.Advanced.SWITCH_LABEL,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Switch(
                            checked = state.useLiveBlockfrost,
                            onCheckedChange = { dispatch(PlaygroundIntent.ToggleLiveBlockfrost(it)) },
                        )
                    }

                    if (state.useLiveBlockfrost) {
                        OutlinedTextField(
                            value = state.projectId,
                            onValueChange = { dispatch(PlaygroundIntent.UpdateProjectId(it)) },
                            label = { Text(DemoCopy.Chrome.Advanced.FIELD_LABEL) },
                            visualTransformation = PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                        )
                        Text(
                            text = DemoCopy.Chrome.Advanced.FIELD_HELPER,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    Text(
                        text = when {
                            state.isLivePreprodActive -> DemoCopy.Chrome.Advanced.ACTIVE_LIVE
                            state.useLiveBlockfrost -> DemoCopy.Chrome.Advanced.CONFIGURATION_REQUIRED
                            else -> DemoCopy.Chrome.Advanced.ACTIVE_MOCK
                        },
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
        }
    }
}
