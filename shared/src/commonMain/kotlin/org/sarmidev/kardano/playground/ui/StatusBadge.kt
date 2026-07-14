package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

// Fixed chip color pairs (background + foreground) chosen to stay readable in both the light
// and dark themes, since each chip paints its own background. Sample-app styling only.
private val ChipNeutralBg = Color(0xFFE7E0EB)
private val ChipNeutralFg = Color(0xFF433A54)
private val ChipInfoBg = Color(0xFFDBE4FF)
private val ChipInfoFg = Color(0xFF1E3A8A)
private val ChipSuccessBg = Color(0xFFD6F1E1)
private val ChipSuccessFg = Color(0xFF0F6D3F)
private val ChipLiveBg = Color(0xFFFFE0C2)
private val ChipLiveFg = Color(0xFF8A4B00)
private val ChipLoadingBg = Color(0xFFE9E0FF)
private val ChipLoadingFg = Color(0xFF4B2FBF)
private val ChipErrorBg = Color(0xFFFBDAD7)
private val ChipErrorFg = Color(0xFF8A1C16)

/** The visual tone of a [Badge]; each maps to a fixed background/foreground pair. */
internal enum class BadgeTone { NEUTRAL, INFO, SUCCESS, LIVE }

/**
 * A short status label shown as a rounded chip — for example `MOCK`, `LIVE PREPROD`, `TESTNET`,
 * `ADA-only`, `SIGNED`, or `SUBMITTED`. Purely presentational.
 */
internal data class Badge(val text: String, val tone: BadgeTone)

/** The progress tone of one guided-flow step, driving its [StatusChip] colors. */
internal enum class StepTone { IDLE, LOADING, SUCCESS, ERROR }

/** A per-step status line (for example "Ready", "Restoring…", "Failed"). */
internal data class StepStatus(val label: String, val tone: StepTone)

@Composable
internal fun StatusBadge(badge: Badge) {
    val bg = when (badge.tone) {
        BadgeTone.NEUTRAL -> ChipNeutralBg
        BadgeTone.INFO -> ChipInfoBg
        BadgeTone.SUCCESS -> ChipSuccessBg
        BadgeTone.LIVE -> ChipLiveBg
    }
    val fg = when (badge.tone) {
        BadgeTone.NEUTRAL -> ChipNeutralFg
        BadgeTone.INFO -> ChipInfoFg
        BadgeTone.SUCCESS -> ChipSuccessFg
        BadgeTone.LIVE -> ChipLiveFg
    }
    Chip(text = badge.text, background = bg, foreground = fg)
}

@Composable
internal fun StatusChip(status: StepStatus) {
    val bg = when (status.tone) {
        StepTone.IDLE -> ChipNeutralBg
        StepTone.LOADING -> ChipLoadingBg
        StepTone.SUCCESS -> ChipSuccessBg
        StepTone.ERROR -> ChipErrorBg
    }
    val fg = when (status.tone) {
        StepTone.IDLE -> ChipNeutralFg
        StepTone.LOADING -> ChipLoadingFg
        StepTone.SUCCESS -> ChipSuccessFg
        StepTone.ERROR -> ChipErrorFg
    }
    Chip(text = status.label, background = bg, foreground = fg)
}

/** A row of [Badge]s that wraps onto multiple lines on narrow screens. */
@Composable
internal fun BadgeRow(badges: List<Badge>) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        badges.forEach { StatusBadge(it) }
    }
}

@Composable
private fun Chip(text: String, background: Color, foreground: Color) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelSmall,
        color = foreground,
        modifier = Modifier
            .background(background, RoundedCornerShape(50))
            .padding(horizontal = 10.dp, vertical = 4.dp),
    )
}
