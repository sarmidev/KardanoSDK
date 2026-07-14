package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp

// Kotlin/KMP-inspired hues used only by the in-app, Compose-drawn mark below. No external logo
// asset is bundled — the mark is drawn with Compose shapes, so there is no third-party image
// license to track for this sample app.
private val MarkPurple = Color(0xFF7F52FF)
private val MarkBlue = Color(0xFF3B6FF5)
private val MarkOrange = Color(0xFFF08A24)

/**
 * The Playground's landing hero (Block 1.12-pre-c, building on the 1.12-pre-b visual refresh):
 * a Compose-drawn geometric mark, the "Kardano SDK" title and "Kotlin Multiplatform Cardano SDK"
 * subtitle, a one-line value statement, the platform/scope badge row
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
                KmpMark()
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
 * A distinct, in-app geometric mark drawn entirely with Compose shapes: a rounded square with a
 * purple→blue→orange gradient and two white forward chevrons suggesting the guided flow. It is
 * intentionally not the Kotlin or Cardano logo — no external image asset is used, so there is
 * no third-party artwork license to document.
 */
@Composable
private fun KmpMark() {
    Box(
        modifier = Modifier
            .size(52.dp)
            .background(
                brush = Brush.linearGradient(listOf(MarkOrange, MarkPurple, MarkBlue)),
                shape = RoundedCornerShape(16.dp),
            ),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(30.dp)) {
            val w = size.width
            val h = size.height
            val strokeWidth = w * 0.16f
            val stroke = Stroke(width = strokeWidth, cap = StrokeCap.Round, join = StrokeJoin.Round)

            fun chevronAt(startX: Float): Path = Path().apply {
                moveTo(startX, h * 0.24f)
                lineTo(startX + w * 0.22f, h * 0.5f)
                lineTo(startX, h * 0.76f)
            }

            drawPath(chevronAt(w * 0.22f), color = Color.White, style = stroke)
            drawPath(chevronAt(w * 0.5f), color = Color.White.copy(alpha = 0.7f), style = stroke)
        }
    }
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
