package org.sarmidev.kardano.playground

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import org.sarmidev.kardano.Greeting
import org.sarmidev.kardano.address.Address

/**
 * The SDK Playground screen: a diagnostic surface for visually verifying existing `:core`
 * SDK behavior on Android (Block 1.2).
 *
 * Covers [Address.parse] with typed [org.sarmidev.kardano.address.AddressError] display,
 * a Hex decoder, and a CBOR decoder. This is sample/diagnostic code in `:shared` and is
 * not part of the SDK public API. No wallet, crypto, provider, or transaction logic.
 */
@Composable
internal fun PlaygroundScreen() {
    val platformLabel = remember { Greeting().greet() }

    var addressInput by remember { mutableStateOf("") }
    var addressResult by remember { mutableStateOf<AddressPresentation>(AddressPresentation.Empty) }

    var hexInput by remember { mutableStateOf("") }
    var hexResult by remember { mutableStateOf<HexPresentation?>(null) }

    var cborInput by remember { mutableStateOf("") }
    var cborResult by remember { mutableStateOf<CborPresentation?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Header
        Text(
            text = "Kardano SDK Playground",
            style = MaterialTheme.typography.titleLarge,
        )
        Text(
            text = platformLabel,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.outline,
        )

        // --- Address Parser ---
        HorizontalDivider()
        Text("Address Parser", style = MaterialTheme.typography.titleMedium)
        Text(
            text = "Structural validation only — CIP-19 Shelley Bech32 (testnet or mainnet).",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedTextField(
            value = addressInput,
            onValueChange = { addressInput = it },
            label = { Text("addr_test1… or stake_test1…") },
            modifier = Modifier.fillMaxWidth(),
            maxLines = 4,
        )
        Button(
            onClick = {
                addressResult = PlaygroundPresenter.presentAddress(
                    Address.parse(addressInput.trim()),
                )
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Parse")
        }
        AddressResultCard(addressResult)

        // --- Hex Decoder ---
        HorizontalDivider()
        Text("Hex Decoder", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = hexInput,
            onValueChange = { hexInput = it },
            label = { Text("Hex string (e.g. 010203)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Button(
            onClick = { hexResult = PlaygroundPresenter.presentHexDecode(hexInput) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Decode")
        }
        hexResult?.let { HexResultCard(it) }

        // --- CBOR Decoder ---
        HorizontalDivider()
        Text("CBOR Decoder", style = MaterialTheme.typography.titleMedium)
        Text(
            text = "Paste CBOR as hex (e.g. 43010203 = 3-byte bytestring).",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedTextField(
            value = cborInput,
            onValueChange = { cborInput = it },
            label = { Text("CBOR hex") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Button(
            onClick = { cborResult = PlaygroundPresenter.presentCbor(cborInput) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Decode")
        }
        cborResult?.let { CborResultCard(it) }
    }
}

// ---------------------------------------------------------------------------
// Result cards
// ---------------------------------------------------------------------------

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
private fun ResultRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.outline,
            modifier = Modifier.weight(0.42f),
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(0.58f),
        )
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
