package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.unit.dp
import kardanosdk.shared.generated.resources.Res
import kardanosdk.shared.generated.resources.kardano_mark_dark
import kardanosdk.shared.generated.resources.kardano_mark_light
import org.jetbrains.compose.resources.painterResource

/**
 * The Playground's landing hero (Block 1.12-pre-c, building on the 1.12-pre-b visual refresh;
 * given the Sarmidev-owned brand mark in 1.12-pre-d): the project's own icon mark via
 * [BrandMark], the "Kardano SDK" title and "Kotlin Multiplatform Cardano SDK" subtitle, a
 * one-line value statement, the platform/scope badge row
 * (`KMP`/`Android`/`iOS`/`JVM`/`Preprod`/`ADA-only MVP`), the concise test-only framing, and a
 * CTA that scrolls to the interactive flow via [onTryFlow]. Presentation only — it reads no SDK
 * state and computes nothing; the active provider mode is shown by the flow's provider card and
 * per-step badges, not here.
 */
@Composable
internal fun PlaygroundHeader(platformLabel: String, onTryFlow: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                brush = Brush.verticalGradient(
                    listOf(
                        MaterialTheme.colorScheme.primaryContainer,
                        MaterialTheme.colorScheme.surface,
                    ),
                ),
                shape = RoundedCornerShape(20.dp),
            )
            .padding(20.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                BrandMark(modifier = Modifier.size(52.dp))
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        text = "Kardano SDK",
                        style = MaterialTheme.typography.headlineSmall,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Text(
                        text = "Kotlin Multiplatform Cardano SDK",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Text(
                text = "Build Cardano wallet and transaction flows from shared Kotlin code.",
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurface,
            )

            BadgeRow(
                listOf(
                    Badge("KMP", BadgeTone.INFO),
                    Badge("Android", BadgeTone.NEUTRAL),
                    Badge("iOS", BadgeTone.NEUTRAL),
                    Badge("JVM", BadgeTone.NEUTRAL),
                    Badge("Preprod", BadgeTone.INFO),
                    Badge("ADA-only MVP", BadgeTone.NEUTRAL),
                ),
            )

            Text(
                text = "Uses a cited test-only fixture wallet throughout — never real funds, " +
                    "mnemonics, or private keys. Running on $platformLabel.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Button(onClick = onTryFlow, modifier = Modifier.fillMaxWidth()) {
                Text("Try the transaction flow below  ↓")
            }
        }
    }
}

/**
 * The Sarmidev-owned Kardano SDK mark (Block 1.12-pre-d): a violet-to-blue "K" beside a
 * cyan-tinted, Cardano-style dot cluster, the same first-party artwork the app icon is built
 * from (see `docs/HANDOFF.md`). Picks the saturated variant
 * ([Res.drawable.kardano_mark_light]) for light surfaces or the white/lilac variant
 * ([Res.drawable.kardano_mark_dark]) for dark surfaces, following [isSystemInDarkTheme] — the
 * same signal [KardanoPlaygroundTheme] uses to pick its color scheme, so the mark and the
 * surrounding hero always agree.
 */
@Composable
internal fun BrandMark(modifier: Modifier = Modifier) {
    val mark = if (isSystemInDarkTheme()) {
        painterResource(Res.drawable.kardano_mark_dark)
    } else {
        painterResource(Res.drawable.kardano_mark_light)
    }
    Image(painter = mark, contentDescription = "Kardano SDK", modifier = modifier)
}

/**
 * A compact, horizontally readable indicator of the guided flow's five steps. Completed steps
 * (each corresponding to a `Success` presentation) are tinted with the primary color; the rest
 * are muted. Presentation only — it derives nothing and calls no SDK.
 */
@Composable
internal fun FlowStepper(completed: List<Boolean>) {
    val labels = listOf("Wallet", "Funds", "Build", "Sign", "Submit")
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        labels.forEachIndexed { index, label ->
            val done = completed.getOrElse(index) { false }
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = if (done) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.outline
                },
            )
            if (index != labels.lastIndex) {
                Text(
                    text = "›",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }
    }
}
