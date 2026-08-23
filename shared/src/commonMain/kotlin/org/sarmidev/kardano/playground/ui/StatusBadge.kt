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

// Each chip's background/foreground pair now comes from LocalKardanoBrand (PlaygroundTheme.kt),
// which supplies distinct light- and dark-theme values — see [Chip] below. No hex constants are
// declared in this file (Block 1.12-pre-d); this keeps dark mode from reusing light-mode chip
// colors verbatim.

/** The visual tone of a [Badge]; each maps to a fixed background/foreground pair. */
internal enum class BadgeTone { NEUTRAL, INFO, SUCCESS, LIVE }

/**
 * A short status label shown as a rounded chip — for example `MOCK`, `LIVE PREPROD`, `TESTNET`,
 * `ADA-only`, `SIGNED`, or `SUBMITTED`. Purely presentational.
 */
internal data class Badge(val text: String, val tone: BadgeTone)

/**
 * The progress tone of one guided-flow step, driving its [StatusChip] colors. [INFO] (Block
 * 1.12-pre-e) is a distinct, neutral "stopped on purpose" tone — used only for the mock Submit
 * step's honest not-supported outcome — so that expected, non-error resting point is never
 * painted the same red as a real failure, nor the same green as a completed submission.
 */
internal enum class StepTone { IDLE, LOADING, SUCCESS, INFO, ERROR }

/** A per-step status line (for example "Ready", "Restoring…", "Failed"). */
internal data class StepStatus(val label: String, val tone: StepTone)

@Composable
internal fun StatusBadge(badge: Badge) {
    val brand = LocalKardanoBrand.current
    val bg = when (badge.tone) {
        BadgeTone.NEUTRAL -> brand.chipNeutralBg
        BadgeTone.INFO -> brand.chipInfoBg
        BadgeTone.SUCCESS -> brand.chipSuccessBg
        BadgeTone.LIVE -> brand.chipLiveBg
    }
    val fg = when (badge.tone) {
        BadgeTone.NEUTRAL -> brand.chipNeutralFg
        BadgeTone.INFO -> brand.chipInfoFg
        BadgeTone.SUCCESS -> brand.chipSuccessFg
        BadgeTone.LIVE -> brand.chipLiveFg
    }
    Chip(text = badge.text, background = bg, foreground = fg)
}

@Composable
internal fun StatusChip(status: StepStatus) {
    val brand = LocalKardanoBrand.current
    val bg = when (status.tone) {
        StepTone.IDLE -> brand.chipNeutralBg
        StepTone.LOADING -> brand.chipLoadingBg
        StepTone.SUCCESS -> brand.chipSuccessBg
        StepTone.INFO -> brand.chipInfoBg
        StepTone.ERROR -> brand.chipErrorBg
    }
    val fg = when (status.tone) {
        StepTone.IDLE -> brand.chipNeutralFg
        StepTone.LOADING -> brand.chipLoadingFg
        StepTone.SUCCESS -> brand.chipSuccessFg
        StepTone.INFO -> brand.chipInfoFg
        StepTone.ERROR -> brand.chipErrorFg
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
