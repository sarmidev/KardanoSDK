package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/**
 * The developer-facing landing/overview area shown in the Overview section (Block 1.12-pre-c,
 * updated in 1.12-pre-c-2): what the SDK does today, a friendly preview of the transaction flow,
 * optional illustrative code snippets, and a compact link into the dedicated roadmap screen. Pure
 * presentation — the only interactions are the [onToggleCodeExamples] visibility toggle (driven
 * by [codeExamplesExpanded]) and the [onOpenRoadmap] navigation callback. It reads no SDK state
 * and calls no SDK API.
 */
@Composable
internal fun PlaygroundLanding(
    codeExamplesExpanded: Boolean,
    onToggleCodeExamples: () -> Unit,
    onOpenRoadmap: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
        CapabilitiesSection()
        FlowPreviewSection()
        CodeExamplesSection(expanded = codeExamplesExpanded, onToggle = onToggleCodeExamples)
        RoadmapTeaser(onOpenRoadmap = onOpenRoadmap)
    }
}

// ---------------------------------------------------------------------------
// What the SDK does today
// ---------------------------------------------------------------------------

private data class Capability(val title: String, val description: String)

private val capabilities = listOf(
    Capability(
        "Parse and validate addresses",
        "Structural CIP-19 Shelley address parsing (testnet or mainnet forms) — parsing only.",
    ),
    Capability(
        "Create a test wallet",
        "Set up the built-in test-only fixture and derive its testnet address.",
    ),
    Capability(
        "Query UTxOs and balance",
        "Read balances and UTxOs through a provider boundary — an in-memory mock or Blockfrost preprod.",
    ),
    Capability(
        "Build ADA-only drafts",
        "Assemble a minimal unsigned ADA-only transaction with coin selection, fee, and change.",
    ),
    Capability(
        "Sign locally and submit",
        "Sign the draft on-device with the fixture wallet, then submit it to preprod.",
    ),
)

@Composable
private fun CapabilitiesSection() {
    val accents = LocalKardanoBrand.current.accents
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionHeader(
            title = "What the SDK does today",
            subtitle = "The current MVP surface, exercised by the flow below.",
        )
        capabilities.forEachIndexed { index, capability ->
            CapabilityCard(capability, accents[index % accents.size])
        }
    }
}

@Composable
private fun CapabilityCard(capability: Capability, accent: Color) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(14.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Box(
                modifier = Modifier
                    .padding(top = 4.dp)
                    .size(10.dp)
                    .background(accent, CircleShape),
            )
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(text = capability.title, style = MaterialTheme.typography.titleSmall)
                Text(
                    text = capability.description,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Transaction flow preview
// ---------------------------------------------------------------------------

private data class PreviewStep(val label: String, val detail: String)

private val previewSteps = listOf(
    PreviewStep("Create a test wallet", "Set up the fixture wallet and get its testnet address."),
    PreviewStep("Check available test ADA", "Look up the wallet's balance and UTxOs."),
    PreviewStep("Prepare a transaction", "Build an ADA-only draft with fee and change."),
    PreviewStep("Sign it locally", "Sign the draft on-device — nothing is sent yet."),
    PreviewStep("Send it to preprod", "Submit the signed transaction to the preprod network."),
)

@Composable
private fun FlowPreviewSection() {
    val accents = LocalKardanoBrand.current.accents
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionHeader(
            title = "The transaction flow",
            subtitle = "Wallet → Funds → Build → Sign → Submit, in five steps.",
        )
        OutlinedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                previewSteps.forEachIndexed { index, step ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalAlignment = Alignment.Top,
                    ) {
                        NumberDot(index + 1, accents[index % accents.size])
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(text = step.label, style = MaterialTheme.typography.titleSmall)
                            Text(
                                text = step.detail,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                Text(
                    text = "Exact technical details (hex, fees, witnesses, ids) stay behind a " +
                        "toggle on each step below.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun NumberDot(number: Int, accent: Color) {
    Surface(color = accent, shape = CircleShape, modifier = Modifier.size(26.dp)) {
        Box(contentAlignment = Alignment.Center) {
            Text(
                text = number.toString(),
                style = MaterialTheme.typography.labelLarge,
                color = Color.White,
                textAlign = TextAlign.Center,
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Code / example cards (collapsible)
// ---------------------------------------------------------------------------

private data class CodeExample(val title: String, val code: String)

// Deliberately simplified, illustrative snippets — not the exact SDK signatures, and never a
// real mnemonic, private key, or full signed CBOR. See PlaygroundPresenter and the guided flow
// below for the actual calls.
private val codeExamples = listOf(
    CodeExample(
        "Restore a test wallet",
        """
        // Restore the cited test-only fixture wallet (testnet)
        val wallet   = TestWalletFixture.restore()
        val address  = wallet.receiveAddress   // addr_test1…
        """.trimIndent(),
    ),
    CodeExample(
        "Query balance and UTxOs",
        """
        // Read funds through the provider boundary (mock or preprod)
        val utxos    = provider.utxos(address)
        val balance  = utxos.sumOf { it.lovelace }
        """.trimIndent(),
    ),
    CodeExample(
        "Build, sign, and submit",
        """
        // ADA-only draft → sign locally → submit to preprod
        val draft    = TransactionBuilder.payment(from = wallet, lovelace = 1_500_000)
        val signed   = wallet.sign(draft)      // on-device
        val txId     = submitProvider.submit(signed)   // preprod
        """.trimIndent(),
    ),
)

@Composable
private fun CodeExamplesSection(expanded: Boolean, onToggle: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionHeader(
            title = "Code examples",
            subtitle = "Simplified snippets for illustration — not exact API signatures.",
        )
        TextButton(onClick = onToggle, modifier = Modifier.fillMaxWidth()) {
            Text(if (expanded) "Hide code examples" else "Show code examples")
        }
        if (expanded) {
            codeExamples.forEach { CodeExampleCard(it) }
        }
    }
}

@Composable
private fun CodeExampleCard(example: CodeExample) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = example.title, style = MaterialTheme.typography.titleSmall)
                StatusBadge(Badge("simplified", BadgeTone.NEUTRAL))
            }
            CodeBlock(example.code)
        }
    }
}

@Composable
private fun CodeBlock(code: String) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = RoundedCornerShape(10.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        SelectionContainer {
            Text(
                text = code,
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier
                    .horizontalScroll(rememberScrollState())
                    .padding(12.dp),
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Roadmap teaser (links to the dedicated roadmap screen)
// ---------------------------------------------------------------------------

@Composable
private fun RoadmapTeaser(onOpenRoadmap: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionHeader(
            title = "Roadmap",
            subtitle = "Phase 0 and 1 are shipping; Phase 2 and 3 sketch the future direction.",
        )
        OutlinedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                BadgeRow(
                    listOf(
                        Badge("Phase 0 · Done", BadgeTone.SUCCESS),
                        Badge("Phase 1 · Current", BadgeTone.INFO),
                        Badge("Phase 2 · Planned", BadgeTone.NEUTRAL),
                        Badge("Phase 3 · Future", BadgeTone.LIVE),
                    ),
                )
                Text(
                    text = "See how the SDK grows from the shipped foundation and MVP flow toward " +
                        "wallet/provider expansion and advanced transaction features. Phase 2 and " +
                        "3 are candidate direction, not a commitment.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Button(onClick = onOpenRoadmap, modifier = Modifier.fillMaxWidth()) {
                    Text("Open the roadmap  →")
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Shared section header
// ---------------------------------------------------------------------------

/** A section title with an optional one-line subtitle, used across the landing area and flow. */
@Composable
internal fun SectionHeader(title: String, subtitle: String? = null, modifier: Modifier = Modifier) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(text = title, style = MaterialTheme.typography.titleLarge)
        if (subtitle != null) {
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
