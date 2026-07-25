package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.sarmidev.kardano.playground.AddressPresentation
import org.sarmidev.kardano.playground.CborPresentation
import org.sarmidev.kardano.playground.HexPresentation
import org.sarmidev.kardano.playground.LabeledRow
import org.sarmidev.kardano.playground.ProviderParamsPresentation
import org.sarmidev.kardano.playground.ProviderUtxosPresentation
import org.sarmidev.kardano.playground.mvi.PlaygroundIntent
import org.sarmidev.kardano.playground.mvi.PlaygroundState
import org.sarmidev.kardano.playground.mvi.SeedAddressKind

/**
 * The visually secondary **Diagnostics** area (Block 1.12-pre-b): standalone structural tools
 * for `:core`/`:provider` APIs — Address Parser, Hex Decoder, CBOR Decoder, and a generic
 * Provider explorer — unrelated to the guided-flow fixture wallet above. It is collapsed by
 * default so the guided flow stays the focus; the collapse is purely visual view state and
 * carries no SDK meaning. Reads [PlaygroundState] and dispatches [PlaygroundIntent]s only.
 */
@Composable
internal fun DiagnosticsSection(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    var expanded by remember { mutableStateOf(false) }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = "Diagnostics", style = MaterialTheme.typography.titleMedium)
                Text(
                    text = "Structural tools for :core/:provider APIs — separate from the flow above.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            TextButton(onClick = { expanded = !expanded }) {
                Text(if (expanded) "Hide" else "Show")
            }
        }

        if (expanded) {
            AddressParserTool(state, dispatch)
            HexDecoderTool(state, dispatch)
            CborDecoderTool(state, dispatch)
            ProviderExplorerTool(state, dispatch)
        }
    }
}

@Composable
private fun DiagnosticTool(
    title: String,
    subtitle: String? = null,
    content: @Composable () -> Unit,
) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(text = title, style = MaterialTheme.typography.titleSmall)
            if (subtitle != null) {
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            content()
        }
    }
}

@Composable
private fun AddressParserTool(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    DiagnosticTool(
        title = "Address Parser",
        subtitle = "Structural validation only — CIP-19 Shelley Bech32 (testnet or mainnet).",
    ) {
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
        when (val result = state.addressResult) {
            is AddressPresentation.Empty -> Unit
            is AddressPresentation.Success -> LabeledRows(result.rows)
            is AddressPresentation.Failure -> ErrorInline(result.message)
        }
    }
}

@Composable
private fun HexDecoderTool(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    DiagnosticTool(title = "Hex Decoder") {
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
        when (val result = state.hexResult) {
            null -> Unit
            is HexPresentation.EncodeSuccess -> LabeledRows(listOf(LabeledRow("Encoded", result.hex)))
            is HexPresentation.DecodeSuccess -> LabeledRows(
                listOf(
                    LabeledRow("Bytes", result.byteCount.toString()),
                    LabeledRow("Re-encoded hex", result.hex),
                ),
            )
            is HexPresentation.Failure -> ErrorInline(result.message)
        }
    }
}

@Composable
private fun CborDecoderTool(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    DiagnosticTool(
        title = "CBOR Decoder",
        subtitle = "Paste CBOR as hex (e.g. 43010203 = 3-byte bytestring).",
    ) {
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
        when (val result = state.cborResult) {
            null -> Unit
            is CborPresentation.Success -> LabeledRows(
                listOf(
                    LabeledRow("Decoded", result.summary),
                    LabeledRow("Round-trip", if (result.roundTripOk) "ok" else "mismatch"),
                ),
            )
            is CborPresentation.Failure -> ErrorInline(result.message)
        }
    }
}

@Composable
private fun ProviderExplorerTool(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    DiagnosticTool(
        title = "Provider explorer",
        subtitle = "Query an arbitrary address against the active provider (mock or live preprod).",
    ) {
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
            OutlinedButton(
                onClick = { dispatch(PlaygroundIntent.FillSeedAddress(SeedAddressKind.WITH_UTXOS)) },
                modifier = Modifier.weight(1f),
            ) {
                Text("Seed: has UTxOs")
            }
            OutlinedButton(
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
        when (val result = state.providerUtxos) {
            is ProviderUtxosPresentation.Empty -> Unit
            is ProviderUtxosPresentation.Loading -> LoadingInline()
            is ProviderUtxosPresentation.Success -> LabeledRows(
                rows = result.rows,
                caption = "${result.rows.size} UTxO(s)",
            )
            is ProviderUtxosPresentation.NoUtxos -> Text(
                text = result.message,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            is ProviderUtxosPresentation.Failure -> ErrorInline(result.message)
        }
        Button(
            onClick = { dispatch(PlaygroundIntent.LoadProviderParams) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Load protocol params")
        }
        when (val result = state.providerParams) {
            is ProviderParamsPresentation.Empty -> Unit
            is ProviderParamsPresentation.Loading -> LoadingInline()
            is ProviderParamsPresentation.Success -> LabeledRows(
                rows = result.rows,
                caption = "Protocol params",
            )
            is ProviderParamsPresentation.Failure -> ErrorInline(result.message)
        }
    }
}
