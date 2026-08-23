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
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
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
        title = "Phase 2 — Native-asset pilot",
        status = PhaseStatus.PLANNED,
        tagline = "A loyalty/ticketing flow with a provider chosen for the pilot.",
        capabilities = listOf(
            "A cross-platform Android and iOS integration proof.",
            "A multi-asset value model that preserves queried assets.",
            "Native-asset input selection and token-preserving change.",
            "One minimal loyalty/ticketing asset-transfer example.",
            "A provider capability decision based on pilot needs.",
            "An external integration experiment or partner feedback.",
        ),
        note = "Planned direction — pilot-gated, not a commitment, and no dates.",
    ),
    PhaseEntry(
        phase = RoadmapPhase.PHASE_3,
        title = "Phase 3 — Ecosystem adoption",
        status = PhaseStatus.FUTURE,
        tagline = "From a proven mobile pilot to an open-source integration path.",
        capabilities = listOf(
            "Versioned public docs, releases, and integration samples.",
            "Pilot outcomes, videos, and benchmark methodology.",
            "Contributor onboarding and maintainer processes.",
            "Funding requests grounded in delivered milestones.",
            "Further transaction capabilities only when adoption evidence supports them.",
            "Future exploration of scripts, metadata, staking, and hardware-wallet boundaries.",
        ),
        note = "Future direction — explicitly not promised, scoped, or scheduled.",
    ),
)

/**
 * The dedicated roadmap screen (Block 1.12-pre-c-2, given a back control in Block 1.12-pre-e now
 * that it is reached as a secondary screen rather than a top-level tab): one card per
 * [RoadmapPhase], each showing a title, a status badge (Done / Current / Planned / Future), and
 * a tagline. Tapping a card expands its detail (highlights + a scope note) via [onSelect]; the
 * currently expanded card is [selected]. [onBack] returns to the guided demo. Pure presentation
 * — every string is static sample-app copy, framed as direction rather than a committed public
 * API or delivery schedule; it reads no SDK state and calls no SDK.
 */
@Composable
internal fun RoadmapScreen(
    selected: RoadmapPhase?,
    onSelect: (RoadmapPhase) -> Unit,
    onBack: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        TextButton(onClick = onBack) { Text(DemoCopy.About.BACK_TO_DEMO) }
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
    OutlinedCard(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .disclosureSemantics(
                expanded = expanded,
                label = if (expanded) {
                    "${entry.title} expanded"
                } else {
                    "${entry.title} collapsed"
                },
                onToggle = onClick,
            ),
    ) {
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
                    modifier = Modifier
                        .weight(1f)
                        .semantics { heading() },
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
