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
import androidx.compose.ui.unit.dp
import org.sarmidev.kardano.playground.mvi.PlaygroundIntent
import org.sarmidev.kardano.playground.mvi.PlaygroundState

/**
 * The About screen (formerly the landing/Overview section; Block 1.12-pre-c,
 * restructured as a secondary screen off Welcome/Summary in Block 1.12-pre-e): what the SDK
 * does today in plain language, optional illustrative code snippets, the developer-facing
 * [DiagnosticsSection] (relocated here under "Developer tools", collapsed by default and
 * unrelated to the guided demo's fixture wallet), a link into the dedicated roadmap screen, and
 * a [onBackToDemo] control. Pure presentation — the only interactions are the
 * [onToggleCodeExamples] visibility toggle (driven by [codeExamplesExpanded]), the
 * [onOpenRoadmap]/[onBackToDemo] navigation callbacks, and whatever [PlaygroundIntent]s
 * [DiagnosticsSection] dispatches from [state]. It reads no other SDK state itself.
 */
@Composable
internal fun PlaygroundLanding(
    state: PlaygroundState,
    codeExamplesExpanded: Boolean,
    onToggleCodeExamples: () -> Unit,
    onOpenRoadmap: () -> Unit,
    onBackToDemo: () -> Unit,
    dispatch: (PlaygroundIntent) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
        TextButton(onClick = onBackToDemo) { Text(DemoCopy.About.BACK_TO_DEMO) }
        HeroCard(title = DemoCopy.Welcome.TITLE, subtitle = DemoCopy.Welcome.SUBTITLE)
        CapabilitiesSection()
        CodeExamplesSection(expanded = codeExamplesExpanded, onToggle = onToggleCodeExamples)
        RoadmapTeaser(onOpenRoadmap = onOpenRoadmap)
        DeveloperToolsSection(state, dispatch)
    }
}

// ---------------------------------------------------------------------------
// What the SDK does today (re-copied in plain language — Block 1.12-pre-e)
// ---------------------------------------------------------------------------

@Composable
private fun CapabilitiesSection() {
    val accents = LocalKardanoBrand.current.accents
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionHeader(
            title = "What the SDK does today",
            subtitle = "The current MVP surface, exercised by the guided demo.",
        )
        DemoCopy.About.CAPABILITIES.forEachIndexed { index, capability ->
            CapabilityCard(capability, accents[index % accents.size])
        }
    }
}

@Composable
private fun CapabilityCard(capability: DemoCopy.About.Capability, accent: Color) {
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
// Code / example cards (collapsible)
// ---------------------------------------------------------------------------

private data class CodeExample(val title: String, val code: String)

// Deliberately simplified, illustrative snippets — not the exact SDK signatures, and never a
// real mnemonic, private key, or full signed CBOR. See PlaygroundPresenter and the guided demo
// steps for the actual calls.
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
                TextButton(onClick = onOpenRoadmap, modifier = Modifier.fillMaxWidth()) {
                    Text("Open the roadmap  →")
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Developer tools (the relocated Diagnostics area — Block 1.12-pre-e)
// ---------------------------------------------------------------------------

@Composable
private fun DeveloperToolsSection(state: PlaygroundState, dispatch: (PlaygroundIntent) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionHeader(
            title = "Developer tools",
            subtitle = "Standalone structural tools, unrelated to the guided demo's test wallet.",
        )
        DiagnosticsSection(state, dispatch)
    }
}

// ---------------------------------------------------------------------------
// Shared section header
// ---------------------------------------------------------------------------

/** A section title with an optional one-line subtitle, used across the About screen and demo. */
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
