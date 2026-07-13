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
import org.sarmidev.kardano.provider.InMemoryTxSubmitProvider
import org.sarmidev.kardano.provider.TxSubmitProvider
import org.sarmidev.kardano.provider.blockfrost.BlockfrostChainQueryProvider
import org.sarmidev.kardano.provider.blockfrost.BlockfrostConfig
import org.sarmidev.kardano.provider.blockfrost.BlockfrostTxSubmitProvider

/**
 * The SDK Playground screen: a diagnostic surface for visually verifying existing `:core`,
 * `:crypto`, `:wallet`, `:tx`, and `:provider` SDK behavior on Android (Blocks 1.2, 1.3, 1.6d,
 * 1.7b, 1.8b, 1.9c, 1.10c, and 1.11).
 *
 * Covers [Address.parse] with typed [org.sarmidev.kardano.address.AddressError] display,
 * a Hex decoder, a CBOR decoder, a test-wallet derivation + address-generation checkpoint, a
 * read-only Provider section, a read-only Wallet Balance checkpoint, an unsigned Transaction
 * Draft checkpoint, a Signed Transaction (not submitted) checkpoint, and a Submit Transaction
 * (preprod) checkpoint. The test-wallet section restores [TestWalletFixture]'s cited test-only
 * mnemonic and shows only the resulting CIP-1852 paths, Blake2b-224 credential hashes, and
 * generated address — never the mnemonic, seed, or any raw key bytes; all derivation,
 * public-key projection, hashing, and address-encoding logic is `:crypto`'s/`:core`'s, called
 * through [KeyDerivation]/[Hashing]/[Address] and formatted here, not reimplemented. The Wallet
 * Balance section restores the same fixture through `:wallet`'s `ReadOnlyWallet.restore`
 * (always `Network.TESTNET`) and queries whichever provider is currently active for that
 * wallet's balance; a zero balance under the mock is the expected result, not a failure. The
 * Transaction Draft section restores the same fixture again and calls `:tx`'s
 * `TransactionBuilder.build` to build a minimal, unsigned, single-payment ADA transaction from
 * that wallet's UTxOs — no signing, no witness construction, no transaction id, no submission;
 * under the mock, the restored address has no seeded UTxOs, so this normally reports "no
 * UTxOs", the expected mock result. The Signed Transaction section (Block 1.10c) builds that
 * same unsigned draft again and signs it through `:wallet`'s `ReadOnlyWallet.signTransaction`,
 * always passing [TestWalletFixture.words] and `Network.TESTNET` explicitly, then shows only
 * the transaction id, witness count, a truncated signed-transaction CBOR preview, and an
 * explicit "signed, not submitted" label — no submission until Block 1.11c below. The Submit
 * Transaction (preprod) section (Block 1.11c) builds and signs that same draft once more, then
 * calls `:provider`'s [TxSubmitProvider.submit] with the signed CBOR: under the default mock
 * ([InMemoryTxSubmitProvider]) submission always reports the honest, explicit
 * "does not support submission" failure (it never fakes an accepted id); only live Blockfrost
 * preprod ([BlockfrostTxSubmitProvider]) can accept a real submission, and only after the
 * fixture address is funded from a preprod faucet. The provider section defaults to the
 * in-memory mock ([InMemoryChainQueryProvider], fake/test-only, no network); a "Use live
 * Blockfrost (preprod)" toggle switches both the query and submit provider to their live
 * Blockfrost preprod counterparts, built from the same runtime `project_id`. That key is held
 * only in non-persistent Compose state (never stored or logged) and live calls hit real preprod
 * (test funds). This is sample/diagnostic code in `:shared` and is not part of the SDK public
 * API. No mainnet anywhere in this screen.
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

    // Submit-transaction boundary (Block 1.11c), wired the same way as activeProvider above:
    // a fake/test-only in-memory mock by default, a live Blockfrost preprod provider once the
    // toggle and the same project_id field above are both set. No second key field is added.
    val mockSubmitProvider = remember { InMemoryTxSubmitProvider() }
    val liveSubmitProvider = remember(projectId) {
        projectId.trim().takeIf { it.isNotBlank() }?.let { key ->
            BlockfrostTxSubmitProvider.create(BlockfrostConfig(projectId = key))
        }
    }
    val activeSubmitProvider: TxSubmitProvider =
        if (useLive && liveSubmitProvider != null) liveSubmitProvider else mockSubmitProvider

    var utxosResult by remember {
        mutableStateOf<ProviderUtxosPresentation>(ProviderUtxosPresentation.Empty)
    }
    var utxosRequest by remember { mutableStateOf(0) }
    var paramsResult by remember {
        mutableStateOf<ProviderParamsPresentation>(ProviderParamsPresentation.Empty)
    }
    var paramsRequest by remember { mutableStateOf(0) }

    var walletBalanceResult by remember {
        mutableStateOf<WalletBalancePresentation>(WalletBalancePresentation.Empty)
    }
    var walletBalanceRequest by remember { mutableStateOf(0) }

    var transactionDraftResult by remember {
        mutableStateOf<TransactionDraftPresentation>(TransactionDraftPresentation.Empty)
    }
    var transactionDraftRequest by remember { mutableStateOf(0) }

    var signedTransactionResult by remember {
        mutableStateOf<SignedTransactionPresentation>(SignedTransactionPresentation.Empty)
    }
    var signedTransactionRequest by remember { mutableStateOf(0) }

    var submitTransactionResult by remember {
        mutableStateOf<SubmitTransactionPresentation>(SubmitTransactionPresentation.Empty)
    }
    var submitTransactionRequest by remember { mutableStateOf(0) }

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
    // Restores TestWalletFixture's cited test-only mnemonic (always Network.TESTNET — Phase 1
    // never constructs a mainnet wallet here) and queries whichever provider is currently
    // active (mock or live), same request-token pattern as the Provider section above.
    LaunchedEffect(walletBalanceRequest) {
        if (walletBalanceRequest == 0) return@LaunchedEffect
        walletBalanceResult = WalletBalancePresentation.Loading
        walletBalanceResult = PlaygroundPresenter.presentWalletBalance(activeProvider)
    }
    // Same restore-then-query pattern as walletBalanceRequest above, but building an unsigned
    // minimal ADA transaction draft through :tx instead of summing a balance.
    LaunchedEffect(transactionDraftRequest) {
        if (transactionDraftRequest == 0) return@LaunchedEffect
        transactionDraftResult = TransactionDraftPresentation.Loading
        transactionDraftResult = PlaygroundPresenter.presentTransactionDraft(activeProvider)
    }
    // Builds the same unsigned draft as transactionDraftRequest above, then signs it through
    // :wallet's ReadOnlyWallet.signTransaction (Block 1.10c) — never submitted.
    LaunchedEffect(signedTransactionRequest) {
        if (signedTransactionRequest == 0) return@LaunchedEffect
        signedTransactionResult = SignedTransactionPresentation.Loading
        signedTransactionResult = PlaygroundPresenter.presentSignedTransaction(activeProvider)
    }
    // Builds and signs the same draft as signedTransactionRequest above, then calls
    // activeSubmitProvider.submit(...) directly — under the mock this always reports the
    // honest "does not support submission" failure (Block 1.11a/b), never a fake accepted id;
    // only live Blockfrost preprod can actually accept a submission. No polling: the accepted
    // id (if any) is shown once, for manual explorer lookup.
    LaunchedEffect(submitTransactionRequest) {
        if (submitTransactionRequest == 0) return@LaunchedEffect
        submitTransactionResult = SubmitTransactionPresentation.Loading
        submitTransactionResult =
            PlaygroundPresenter.presentSubmitTransaction(activeProvider, activeSubmitProvider)
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

        // --- Wallet Balance (read-only; Block 1.8b) ---
        HorizontalDivider()
        Text("Wallet Balance (read-only)", style = MaterialTheme.typography.titleMedium)
        Text(
            text = "Restores the same test-only wallet as above (always testnet) and queries " +
                "the provider selected in the Provider section for its balance — no signing, " +
                "no transaction logic. Mock provider data is fake/test-only: it has no fake " +
                "UTxOs seeded for this generated address, so it normally shows 0 UTxOs / 0 " +
                "lovelace here, which is the expected mock result, not a failure. Live " +
                "Blockfrost preprod can show a non-zero balance only after this address is " +
                "funded with test ADA from a preprod faucet. Shows only the generated address, " +
                "UTxO count, and balance in lovelace — never the mnemonic, seed, or any " +
                "private/raw key bytes.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(
            onClick = { walletBalanceRequest += 1 },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Query wallet balance")
        }
        WalletBalanceCard(walletBalanceResult)

        // --- Transaction Draft (unsigned; Block 1.9c) ---
        HorizontalDivider()
        Text("Transaction Draft (unsigned)", style = MaterialTheme.typography.titleMedium)
        Text(
            text = "Restores the same test-only wallet as above (always testnet), queries the " +
                "provider selected in the Provider section for its UTxOs and current protocol " +
                "parameters, and builds a minimal single-payment ADA transaction draft through " +
                "TransactionBuilder — no signing, no witness construction, no transaction id, " +
                "no submission. Mock provider data has no fake UTxOs seeded for this generated " +
                "wallet address, so this normally reports \"no UTxOs\", which is the expected " +
                "mock result, not a failure. Live Blockfrost preprod can build a real draft only " +
                "after this address is funded with test ADA from a preprod faucet. Shows only " +
                "input/output counts, the fee and change in lovelace, the encoded body size, " +
                "and a truncated hex preview of the body bytes.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(
            onClick = { transactionDraftRequest += 1 },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Build transaction draft")
        }
        TransactionDraftCard(transactionDraftResult)

        // --- Signed Transaction (not submitted; Block 1.10c) ---
        HorizontalDivider()
        Text("Signed Transaction (not submitted)", style = MaterialTheme.typography.titleMedium)
        Text(
            text = "Builds the same unsigned draft as above (always testnet, same test-only " +
                "fixture), then signs it through ReadOnlyWallet.signTransaction — never " +
                "submitted, that is Block 1.11. Mock provider data has no fake UTxOs seeded " +
                "for this generated wallet address, so this normally reports \"no UTxOs\", " +
                "the expected mock result, not a failure. Live Blockfrost preprod can sign a " +
                "real draft only after this address is funded with test ADA from a preprod " +
                "faucet. Shows only the transaction id, witness count, a truncated hex " +
                "preview of the signed transaction CBOR, and an explicit not-submitted label " +
                "— never the mnemonic, seed, or any private/raw key bytes, and never the full " +
                "signed CBOR.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(
            onClick = { signedTransactionRequest += 1 },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Sign transaction")
        }
        SignedTransactionCard(signedTransactionResult)

        // --- Submit Transaction (preprod; Block 1.11c) ---
        HorizontalDivider()
        Text("Submit Transaction (preprod)", style = MaterialTheme.typography.titleMedium)
        Text(
            text = "Builds and signs the same fixture transaction as above (always testnet), " +
                "then submits it through whichever submit provider is currently active. Under " +
                "the mock (default), submission always reports an explicit \"does not support " +
                "submission\" failure — it never fakes an accepted transaction id. Enable " +
                "\"Use live Blockfrost (preprod)\" above and provide a project_id to submit " +
                "for real: Blockfrost preprod only, never mainnet, and only test ADA (never " +
                "real funds). On acceptance this shows only the accepted transaction id, the " +
                "locally-signed transaction id, whether they match, and an explicit " +
                "submitted/preprod/test-fixture label — no automatic polling; use the shown id " +
                "to look the transaction up manually on a preprod explorer.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(
            onClick = { submitTransactionRequest += 1 },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Submit transaction")
        }
        SubmitTransactionCard(submitTransactionResult)
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
private fun WalletBalanceCard(presentation: WalletBalancePresentation) {
    when (presentation) {
        is WalletBalancePresentation.Empty -> Unit
        is WalletBalancePresentation.Loading -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "Loading…",
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        is WalletBalancePresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
            }
        }
        is WalletBalancePresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun TransactionDraftCard(presentation: TransactionDraftPresentation) {
    when (presentation) {
        is TransactionDraftPresentation.Empty -> Unit
        is TransactionDraftPresentation.Loading -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "Loading…",
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        is TransactionDraftPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
            }
        }
        is TransactionDraftPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun SignedTransactionCard(presentation: SignedTransactionPresentation) {
    when (presentation) {
        is SignedTransactionPresentation.Empty -> Unit
        is SignedTransactionPresentation.Loading -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "Loading…",
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        is SignedTransactionPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
            }
        }
        is SignedTransactionPresentation.Failure -> ErrorCard(presentation.message)
    }
}

@Composable
private fun SubmitTransactionCard(presentation: SubmitTransactionPresentation) {
    when (presentation) {
        is SubmitTransactionPresentation.Empty -> Unit
        is SubmitTransactionPresentation.Loading -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "Loading…",
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        is SubmitTransactionPresentation.Success -> ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                presentation.rows.forEach { row -> ResultRow(row.label, row.value) }
            }
        }
        is SubmitTransactionPresentation.Failure -> ErrorCard(presentation.message)
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
