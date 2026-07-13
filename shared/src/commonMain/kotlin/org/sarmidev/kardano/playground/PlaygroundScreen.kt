package org.sarmidev.kardano.playground

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import org.sarmidev.kardano.Greeting
import org.sarmidev.kardano.playground.mvi.PlaygroundIntent
import org.sarmidev.kardano.playground.mvi.PlaygroundState
import org.sarmidev.kardano.playground.mvi.PlaygroundStep
import org.sarmidev.kardano.playground.mvi.PlaygroundViewModel
import org.sarmidev.kardano.playground.mvi.SeedAddressKind

/**
 * The SDK Playground screen: a guided-flow diagnostic surface for visually verifying existing
 * `:core`, `:crypto`, `:wallet`, `:tx`, and `:provider` SDK behavior (Blocks 1.2 through 1.11,
 * restructured into an MVI architecture in Block 1.12-pre-a).
 *
 * This composable is now a pure renderer: it reads [PlaygroundState] from [PlaygroundViewModel]
 * and dispatches [PlaygroundIntent]s for every user action — it computes nothing itself, and
 * holds no state of its own beyond [platformLabel] (a static display string). All SDK-calling
 * logic lives in [PlaygroundViewModel], its use cases (`playground/domain`), and its provider
 * factory (`playground/data`), which in turn call [PlaygroundPresenter] — never reimplemented
 * here.
 *
 * The screen reads top to bottom as a guided flow — **Wallet → Funds → Build → Sign → Submit**
 * — restoring [TestWalletFixture]'s cited test-only mnemonic (never a real mnemonic, never real
 * funds), querying whichever provider is active (an in-memory mock by default, or live
 * Blockfrost preprod once configured) for that wallet's balance, building a minimal unsigned
 * ADA-only transaction draft, signing it, and finally submitting it — followed by a
 * **Diagnostics** area with standalone tools (Address Parser, Hex Decoder, CBOR Decoder, and a
 * generic Provider explorer) unrelated to the fixture wallet. Testnet/preprod only, everywhere;
 * no mainnet, no real mnemonic/private-key display, and no full (untruncated) CBOR display —
 * see [PlaygroundState] and [PlaygroundPresenter] for the exact display-safety rules each
 * `*Presentation` type already follows.
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
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(text = "Kardano SDK Playground", style = MaterialTheme.typography.titleLarge)
        Text(
            text = platformLabel,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.outline,
        )
        Text(
            text = "Testnet/preprod only. Uses a cited test-only fixture wallet throughout — " +
                "never real funds, mnemonics, or private keys.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        GuidedFlowSection(state, dispatch)
        DiagnosticsSection(state, dispatch)
    }
}

// ---------------------------------------------------------------------------
// Guided flow: Wallet -> Funds -> Build -> Sign -> Submit
// ---------------------------------------------------------------------------

@Composable
private fun GuidedFlowSection(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    HorizontalDivider()
    Text(text = "Guided flow", style = MaterialTheme.typography.titleLarge)

    StepSection(
        title = "1. Wallet",
        description = "Restore the test-only fixture wallet and generate its address.",
        step = PlaygroundStep.WALLET,
        expandedSteps = state.technicalDetailsExpanded,
        dispatch = dispatch,
    ) { expanded ->
        Button(
            onClick = { dispatch(PlaygroundIntent.RestoreWallet) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (state.walletLoading) "Restoring…" else "Restore test wallet")
        }
        WalletResultCard(state.wallet, expanded)
    }

    StepSection(
        title = "2. Funds",
        description = if (state.useLiveBlockfrost) {
            "Live Blockfrost preprod — real network calls, test funds only."
        } else {
            "Query the fixture wallet's balance from the in-memory mock (fake/test-only)."
        },
        step = PlaygroundStep.FUNDS,
        expandedSteps = state.technicalDetailsExpanded,
        dispatch = dispatch,
    ) { expanded ->
        ProviderConfigRow(state, dispatch)
        Button(
            onClick = { dispatch(PlaygroundIntent.QueryFunds) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Query wallet balance")
        }
        WalletBalanceCard(state.funds, expanded)
    }

    StepSection(
        title = "3. Build",
        description = "Build a minimal, unsigned, ADA-only transaction draft from the " +
            "wallet's UTxOs — no signing, no submission.",
        step = PlaygroundStep.BUILD,
        expandedSteps = state.technicalDetailsExpanded,
        dispatch = dispatch,
    ) { expanded ->
        Button(
            onClick = { dispatch(PlaygroundIntent.BuildDraft) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Build transaction draft")
        }
        TransactionDraftCard(state.draft, expanded)
    }

    StepSection(
        title = "4. Sign",
        description = "Sign the same draft with the fixture wallet — not submitted yet.",
        step = PlaygroundStep.SIGN,
        expandedSteps = state.technicalDetailsExpanded,
        dispatch = dispatch,
    ) { expanded ->
        Button(
            onClick = { dispatch(PlaygroundIntent.SignTransaction) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Sign transaction")
        }
        SignedTransactionCard(state.signed, expanded)
    }

    StepSection(
        title = "5. Submit",
        description = "Submit the signed transaction to the active provider (mock always " +
            "reports \"not supported\"; live Blockfrost preprod can accept a real submission).",
        step = PlaygroundStep.SUBMIT,
        expandedSteps = state.technicalDetailsExpanded,
        dispatch = dispatch,
    ) { expanded ->
        Button(
            onClick = { dispatch(PlaygroundIntent.SubmitTransaction) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Submit transaction")
        }
        SubmitTransactionCard(state.submit, expanded)
    }

    Button(
        onClick = { dispatch(PlaygroundIntent.ResetFlow) },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Reset flow")
    }
}

/** The "Use live Blockfrost (preprod)" toggle and `project_id` field shared by every step. */
@Composable
private fun ProviderConfigRow(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = "Use live Blockfrost (preprod)",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f),
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
            label = { Text("Blockfrost project_id (preprod, not stored)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
    }
}

/**
 * A titled guided-flow section with a per-step "technical details" toggle
 * ([PlaygroundIntent.ToggleTechnicalDetails]): [content] receives whether [step] is currently
 * expanded and decides how much detail its result card shows.
 */
@Composable
private fun StepSection(
    title: String,
    description: String,
    step: PlaygroundStep,
    expandedSteps: Set<PlaygroundStep>,
    dispatch: (PlaygroundIntent) -> Unit,
    content: @Composable (expanded: Boolean) -> Unit,
) {
    HorizontalDivider()
    val expanded = step in expandedSteps
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text = title, style = MaterialTheme.typography.titleMedium)
        TextButton(onClick = { dispatch(PlaygroundIntent.ToggleTechnicalDetails(step)) }) {
            Text(if (expanded) "Hide details" else "Details")
        }
    }
    Text(
        text = description,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        content(expanded)
    }
}

// ---------------------------------------------------------------------------
// Diagnostics: Address Parser, Hex Decoder, CBOR Decoder, generic Provider explorer
// ---------------------------------------------------------------------------

@Composable
private fun DiagnosticsSection(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    HorizontalDivider()
    Text(text = "Diagnostics", style = MaterialTheme.typography.titleLarge)
    Text(
        text = "Standalone structural tools for :core/:provider APIs — unrelated to the " +
            "fixture wallet above.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )

    HorizontalDivider()
    Text("Address Parser", style = MaterialTheme.typography.titleMedium)
    Text(
        text = "Structural validation only — CIP-19 Shelley Bech32 (testnet or mainnet).",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    OutlinedTextField(
        value = state.addressInput,
        onValueChange = { dispatch(PlaygroundIntent.UpdateAddressInput(it)) },
        label = { Text("addr_test1… or stake_test1…") },
        modifier = Modifier.fillMaxWidth(),
        maxLines = 4,
    )
    Button(
        onClick = { dispatch(PlaygroundIntent.ParseAddress) },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Parse")
    }
    AddressResultCard(state.addressResult)

    HorizontalDivider()
    Text("Hex Decoder", style = MaterialTheme.typography.titleMedium)
    OutlinedTextField(
        value = state.hexInput,
        onValueChange = { dispatch(PlaygroundIntent.UpdateHexInput(it)) },
        label = { Text("Hex string (e.g. 010203)") },
        modifier = Modifier.fillMaxWidth(),
        singleLine = true,
    )
    Button(
        onClick = { dispatch(PlaygroundIntent.DecodeHex) },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Decode")
    }
    state.hexResult?.let { HexResultCard(it) }

    HorizontalDivider()
    Text("CBOR Decoder", style = MaterialTheme.typography.titleMedium)
    Text(
        text = "Paste CBOR as hex (e.g. 43010203 = 3-byte bytestring).",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    OutlinedTextField(
        value = state.cborInput,
        onValueChange = { dispatch(PlaygroundIntent.UpdateCborInput(it)) },
        label = { Text("CBOR hex") },
        modifier = Modifier.fillMaxWidth(),
        singleLine = true,
    )
    Button(
        onClick = { dispatch(PlaygroundIntent.DecodeCbor) },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Decode")
    }
    state.cborResult?.let { CborResultCard(it) }

    HorizontalDivider()
    Text("Provider explorer", style = MaterialTheme.typography.titleMedium)
    Text(
        text = "Query an arbitrary address against whichever provider is currently active " +
            "in the Funds step above (mock or live Blockfrost preprod).",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    OutlinedTextField(
        value = state.providerAddressInput,
        onValueChange = { dispatch(PlaygroundIntent.UpdateProviderAddressInput(it)) },
        label = { Text("Preprod address (addr_test1…)") },
        modifier = Modifier.fillMaxWidth(),
        maxLines = 4,
    )
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Button(
            onClick = { dispatch(PlaygroundIntent.FillSeedAddress(SeedAddressKind.WITH_UTXOS)) },
            modifier = Modifier.weight(1f),
        ) {
            Text("Seed: has UTxOs")
        }
        Button(
            onClick = { dispatch(PlaygroundIntent.FillSeedAddress(SeedAddressKind.EMPTY)) },
            modifier = Modifier.weight(1f),
        ) {
            Text("Seed: empty")
        }
    }
    Button(
        onClick = { dispatch(PlaygroundIntent.LoadProviderUtxos) },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Load UTxOs")
    }
    ProviderUtxosCard(state.providerUtxos)

    Button(
        onClick = { dispatch(PlaygroundIntent.LoadProviderParams) },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Load protocol params")
    }
    ProviderParamsCard(state.providerParams)
}

// ---------------------------------------------------------------------------
// Result cards
// ---------------------------------------------------------------------------

/** The single row shown when a step's technical details are collapsed. */
private fun summaryRow(rows: List<LabeledRow>): LabeledRow =
    rows.lastOrNull { it.label == "Status" } ?: rows.lastOrNull() ?: LabeledRow("Result", "ok")

@Composable
private fun AddressResultCard(presentation: AddressPresentation) {
    when (presentation) {
        is AddressPresentation.Empty -> Unit
        is AddressPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
            }
        }
        is AddressPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun HexResultCard(presentation: HexPresentation) {
    when (presentation) {
        is HexPresentation.EncodeSuccess -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp)) {
                ResultRow("Encoded", presentation.hex)
            }
        }
        is HexPresentation.DecodeSuccess -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                ResultRow("Bytes", "${presentation.byteCount}")
                ResultRow("Re-encoded hex", presentation.hex)
            }
        }
        is HexPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun CborResultCard(presentation: CborPresentation) {
    when (presentation) {
        is CborPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                ResultRow("Decoded", presentation.summary)
                ResultRow("Round-trip", if (presentation.roundTripOk) "ok" else "mismatch")
            }
        }
        is CborPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun WalletResultCard(presentation: WalletPresentation, expanded: Boolean) {
    when (presentation) {
        is WalletPresentation.Empty -> Unit
        is WalletPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                if (expanded) {
                    presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
                    ResultRow(
                        "Matches cited vector",
                        if (presentation.fingerprintMatchesVector) "yes" else "no",
                    )
                } else {
                    val row = presentation.rows.firstOrNull { it.label == "Generated address" }
                        ?: summaryRow(presentation.rows)
                    ResultRow(row.label, row.value)
                }
            }
        }
        is WalletPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun ProviderUtxosCard(presentation: ProviderUtxosPresentation) {
    when (presentation) {
        is ProviderUtxosPresentation.Empty -> Unit
        is ProviderUtxosPresentation.Loading -> LoadingCard()
        is ProviderUtxosPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(
                    text = "${presentation.rows.size} UTxO(s)",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.outline,
                )
                presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
            }
        }
        is ProviderUtxosPresentation.NoUtxos -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = presentation.message,
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        is ProviderUtxosPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun ProviderParamsCard(presentation: ProviderParamsPresentation) {
    when (presentation) {
        is ProviderParamsPresentation.Empty -> Unit
        is ProviderParamsPresentation.Loading -> LoadingCard()
        is ProviderParamsPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(
                    text = "Protocol params",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.outline,
                )
                presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
            }
        }
        is ProviderParamsPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun WalletBalanceCard(presentation: WalletBalancePresentation, expanded: Boolean) {
    when (presentation) {
        is WalletBalancePresentation.Empty -> Unit
        is WalletBalancePresentation.Loading -> LoadingCard()
        is WalletBalancePresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                if (expanded) {
                    presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
                } else {
                    val row = presentation.rows.firstOrNull { it.label == "Balance" }
                        ?: summaryRow(presentation.rows)
                    ResultRow(row.label, row.value)
                }
            }
        }
        is WalletBalancePresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun TransactionDraftCard(presentation: TransactionDraftPresentation, expanded: Boolean) {
    when (presentation) {
        is TransactionDraftPresentation.Empty -> Unit
        is TransactionDraftPresentation.Loading -> LoadingCard()
        is TransactionDraftPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                if (expanded) {
                    presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
                } else {
                    ResultRow(summaryRow(presentation.rows).label, summaryRow(presentation.rows).value)
                }
            }
        }
        is TransactionDraftPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun SignedTransactionCard(presentation: SignedTransactionPresentation, expanded: Boolean) {
    when (presentation) {
        is SignedTransactionPresentation.Empty -> Unit
        is SignedTransactionPresentation.Loading -> LoadingCard()
        is SignedTransactionPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                if (expanded) {
                    presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
                } else {
                    ResultRow(summaryRow(presentation.rows).label, summaryRow(presentation.rows).value)
                }
            }
        }
        is SignedTransactionPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun SubmitTransactionCard(presentation: SubmitTransactionPresentation, expanded: Boolean) {
    when (presentation) {
        is SubmitTransactionPresentation.Empty -> Unit
        is SubmitTransactionPresentation.Loading -> LoadingCard()
        is SubmitTransactionPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                if (expanded) {
                    presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
                } else {
                    ResultRow(summaryRow(presentation.rows).label, summaryRow(presentation.rows).value)
                }
            }
        }
        is SubmitTransactionPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun LoadingCard() {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = "Loading…",
            modifier = Modifier.padding(12.dp),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

// Wraps the value in a SelectionContainer so the owner can long-press/select and copy it
// (e.g. the generated addr_test1… address, to fund it from a preprod faucet) without any
// clipboard API surface. Applied here, once, so every ResultRow value across every card
// (generated address, wallet balance address, CBOR preview, etc.) becomes copyable.
@Composable
private fun ResultRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.outline,
            modifier = Modifier.weight(0.42f),
        )
        SelectionContainer(modifier = Modifier.weight(0.58f)) {
            Text(
                text = value,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun ErrorCard(message: String) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = message,
            modifier = Modifier.padding(12.dp),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.error,
        )
    }
}

// ---------------------------------------------------------------------------
// Preview
// ---------------------------------------------------------------------------

@Preview
@Composable
private fun PlaygroundScreenPreview() {
    MaterialTheme {
        PlaygroundScreen()
    }
}
