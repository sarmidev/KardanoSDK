package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.sarmidev.kardano.playground.mvi.RoadmapPhase

/** The status of a roadmap [PhaseEntry]; each maps to a [Badge] tone. */
private enum class PhaseStatus(val label: String, val tone: BadgeTone) {
    DONE("Done", BadgeTone.SUCCESS),
    CURRENT("Current", BadgeTone.INFO),
    PLANNED("Planned", BadgeTone.NEUTRAL),
    FUTURE("Future", BadgeTone.LIVE),
}

/**
 * One roadmap card's static copy. [capabilities] are the highlights shown when the card is
 * expanded; [note] is an optional honesty/scope line (used to frame Phase 2/3 as candidate,
 * non-committed direction). Presentation-only sample-app content — not a public API contract.
 */
private data class PhaseEntry(
    val phase: RoadmapPhase,
    val title: String,
    val status: PhaseStatus,
    val tagline: String,
    val capabilities: List<String>,
    val note: String?,
)

private val roadmap = listOf(
    PhaseEntry(
        phase = RoadmapPhase.PHASE_0,
        title = "Phase 0 — Foundation",
        status = PhaseStatus.DONE,
        tagline = "The dependency-free SDK core.",
        capabilities = listOf(
            "Core primitives (bytes, hex, Lovelace, typed references).",
            "Hex, Bech32/Bech32m, and a minimal CBOR subset.",
            "Structural CIP-19 address parsing (decode-only).",
            "Bounded parsers with named limits and typed errors.",
            "A UI-free, multiplatform :core module.",
        ),
        note = "Parsing and encoding only — no wallet, signing, or network yet.",
    ),
    PhaseEntry(
        phase = RoadmapPhase.PHASE_1,
        title = "Phase 1 — MVP transaction flow",
        status = PhaseStatus.CURRENT,
        tagline = "An end-to-end ADA-only flow on preprod.",
        capabilities = listOf(
            "A test-only wallet fixture and key derivation.",
            "A provider boundary with an in-memory mock and Blockfrost preprod.",
            "An ADA-only transaction draft (coin selection, fee, change).",
            "Local signing for the test flow.",
            "Submit to preprod.",
            "The Android Playground checkpoint.",
        ),
        note = "Testnet/preprod-focused and ADA-only — no mainnet flow, no multi-asset.",
    ),
    PhaseEntry(
        phase = RoadmapPhase.PHASE_2,
        title = "Phase 2 — Wallet and provider expansion",
        status = PhaseStatus.PLANNED,
        tagline = "Room to grow the wallet and provider story.",
        capabilities = listOf(
            "A wallet persistence model.",
            "Better account and address discovery.",
            "Richer UTxO views.",
            "Multiple provider backends.",
            "Improved transaction history / read models.",
            "Clearer app-integration APIs.",
            "More developer samples.",
            "Native-assets exploration, if explicitly planned later.",
        ),
        note = "Candidate/future direction — not a commitment, and no dates.",
    ),
    PhaseEntry(
        phase = RoadmapPhase.PHASE_3,
        title = "Phase 3 — Advanced transaction capabilities",
        status = PhaseStatus.FUTURE,
        tagline = "Where an ambitious Cardano toolkit could go.",
        capabilities = listOf(
            "A broader transaction builder.",
            "Multi-asset transaction support.",
            "Metadata and certificates exploration.",
            "Staking and delegation exploration.",
            "A hardware-wallet boundary exploration.",
            "Richer Android / iOS / JVM examples.",
            "Ecosystem integrations and tooling.",
        ),
        note = "Aspirational direction — explicitly not promised, scoped, or scheduled.",
    ),
)

/**
 * The dedicated roadmap screen (Block 1.12-pre-c-2): one card per [RoadmapPhase], each showing a
 * title, a status badge (Done / Current / Planned / Future), and a tagline. Tapping a card
 * expands its detail (highlights + a scope note) via [onSelect]; the currently expanded card is
 * [selected]. Pure presentation — every string is static sample-app copy, framed as direction
 * rather than a committed public API or delivery schedule; it reads no SDK state and calls no SDK.
 */
@Composable
internal fun RoadmapScreen(selected: RoadmapPhase?, onSelect: (RoadmapPhase) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionHeader(
            title = "Roadmap",
            subtitle = "Where the SDK is today and where it could go. This is a sample-app " +
                "overview — not a committed public API or delivery schedule.",
        )
        roadmap.forEach { entry ->
            PhaseCard(
                entry = entry,
                expanded = entry.phase == selected,
                onClick = { onSelect(entry.phase) },
            )
        }
    }
}

@Composable
private fun PhaseCard(entry: PhaseEntry, expanded: Boolean, onClick: () -> Unit) {
    OutlinedCard(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = entry.title,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                StatusBadge(Badge(entry.status.label, entry.status.tone))
            }
            Text(
                text = entry.tagline,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            if (expanded) {
                HorizontalDivider()
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    entry.capabilities.forEach { line -> BulletLine(line) }
                }
                if (entry.note != null) {
                    Text(
                        text = entry.note,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                Text(
                    text = "Tap for details",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

@Composable
private fun BulletLine(text: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
        Text(
            text = "•",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = text,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}
