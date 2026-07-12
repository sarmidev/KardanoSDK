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
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import org.sarmidev.kardano.Greeting
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.provider.blockfrost.BlockfrostChainQueryProvider
import org.sarmidev.kardano.provider.blockfrost.BlockfrostConfig

/**
 * The SDK Playground screen: a diagnostic surface for visually verifying existing `:core` and
 * `:crypto` SDK behavior on Android (Blocks 1.2, 1.3, and 1.6d).
 *
 * Covers [Address.parse] with typed [org.sarmidev.kardano.address.AddressError] display,
 * a Hex decoder, a CBOR decoder, a test-wallet derivation checkpoint, and a read-only Provider
 * section. The test-wallet section restores [TestWalletFixture]'s cited test-only mnemonic and
 * shows only the resulting CIP-1852 path and Blake2b-224 fingerprint — never the mnemonic,
 * seed, or any raw key bytes; all derivation, public-key projection, and hashing logic is
 * `:crypto`'s, called through [KeyDerivation]/[Hashing] and formatted here, not reimplemented.
 * The provider section defaults to the in-memory mock ([InMemoryChainQueryProvider],
 * fake/test-only, no network); a "Use live Blockfrost (preprod)" toggle switches to a live
 * [BlockfrostChainQueryProvider] built from a runtime `project_id`. That key is held only in
 * non-persistent Compose state (never stored or logged) and live calls hit real preprod (test
 * funds). This is sample/diagnostic code in `:shared` and is not part of the SDK public API.
 * No signing, address generation, wallet persistence, or transaction logic.
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

    var walletResult by remember { mutableStateOf<WalletPresentation>(WalletPresentation.Empty) }

    val mockProvider = remember { InMemoryChainQueryProvider() }
    var providerAddressInput by remember {
        mutableStateOf(InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS)
    }
    // Live-Blockfrost toggle and key. The key is held only in non-persistent Compose state
    // (remember, not rememberSaveable): it is never persisted, saved, or logged.
    var useLive by remember { mutableStateOf(false) }
    var projectId by remember { mutableStateOf("") }
    val liveProvider = remember(projectId) {
        projectId.trim().takeIf { it.isNotBlank() }?.let { key ->
            BlockfrostChainQueryProvider.create(BlockfrostConfig(projectId = key))
        }
    }
    val activeProvider: ChainQueryProvider =
        if (useLive && liveProvider != null) liveProvider else mockProvider

    var utxosResult by remember {
        mutableStateOf<ProviderUtxosPresentation>(ProviderUtxosPresentation.Empty)
    }
    var utxosRequest by remember { mutableStateOf(0) }
    var paramsResult by remember {
        mutableStateOf<ProviderParamsPresentation>(ProviderParamsPresentation.Empty)
    }
    var paramsRequest by remember { mutableStateOf(0) }

    // One-shot suspend loads triggered by incrementing a request token. Using LaunchedEffect
    // keeps the screen dependent only on the Compose runtime (no extra coroutine artifact).
    // The effect reads the currently active provider (mock or live) at launch.
    LaunchedEffect(utxosRequest) {
        if (utxosRequest == 0) return@LaunchedEffect
        utxosResult = ProviderUtxosPresentation.Loading
        utxosResult = PlaygroundPresenter.presentProviderUtxos(activeProvider, providerAddressInput)
    }
    LaunchedEffect(paramsRequest) {
        if (paramsRequest == 0) return@LaunchedEffect
        paramsResult = ProviderParamsPresentation.Loading
        paramsResult = PlaygroundPresenter.presentProviderParams(activeProvider)
    }

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

        // --- Test Wallet / Address Generation checkpoint (Block 1.6d, extended by 1.7b) ---
        HorizontalDivider()
        Text("Test Wallet & Address Generation", style = MaterialTheme.typography.titleMedium)
        Text(
            text = "Restores a test-only wallet from a public cited vector (no real funds, " +
                "no real mnemonic), derives its payment and stake keys, and generates a " +
                "structural addr_test base address from their credential hashes — then " +
                "parses that address straight back. No signing, no transaction logic. Shows " +
                "only the derivation paths, credential hashes, and the generated address — " +
                "never the mnemonic, seed, or any private/raw key bytes.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(
            onClick = { walletResult = PlaygroundPresenter.presentTestWallet() },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Restore test wallet & generate address")
        }
        WalletResultCard(walletResult)

        // --- Provider (read-only: mock or live Blockfrost) ---
        HorizontalDivider()
        Text("Provider", style = MaterialTheme.typography.titleMedium)
        Text(
            text = if (useLive) {
                "Live Blockfrost preprod — real network calls. Your project_id is used only " +
                    "for these requests and is not stored. Preprod uses test funds."
            } else {
                "Read-only query boundary backed by an in-memory mock. Data is " +
                    "fake/test-only — no network, no funds, no secrets."
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
        ) {
            Text(
                text = "Use live Blockfrost (preprod)",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f),
            )
            Switch(checked = useLive, onCheckedChange = { useLive = it })
        }
        if (useLive) {
            OutlinedTextField(
                value = projectId,
                onValueChange = { projectId = it },
                label = { Text("Blockfrost project_id (preprod, not stored)") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
        }
        OutlinedTextField(
            value = providerAddressInput,
            onValueChange = { providerAddressInput = it },
            label = { Text("Preprod address (addr_test1…)") },
            modifier = Modifier.fillMaxWidth(),
            maxLines = 4,
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Button(
                onClick = {
                    providerAddressInput = InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS
                },
                modifier = Modifier.weight(1f),
            ) {
                Text("Seed: has UTxOs")
            }
            Button(
                onClick = {
                    providerAddressInput = InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY
                },
                modifier = Modifier.weight(1f),
            ) {
                Text("Seed: empty")
            }
        }
        Button(
            onClick = { utxosRequest += 1 },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Load UTxOs")
        }
        ProviderUtxosCard(utxosResult)

        Button(
            onClick = { paramsRequest += 1 },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Load protocol params")
        }
        ProviderParamsCard(paramsResult)
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
private fun WalletResultCard(presentation: WalletPresentation) {
    when (presentation) {
        is WalletPresentation.Empty -> Unit
        is WalletPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
                ResultRow(
                    "Matches cited vector",
                    if (presentation.fingerprintMatchesVector) "yes" else "no",
                )
            }
        }
        is WalletPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun ProviderUtxosCard(presentation: ProviderUtxosPresentation) {
    when (presentation) {
        is ProviderUtxosPresentation.Empty -> Unit
        is ProviderUtxosPresentation.Loading -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "Loading…",
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
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
        is ProviderParamsPresentation.Loading -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "Loading…",
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
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
