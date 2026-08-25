package org.sarmidev.kardano.playground.ui

import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.collapse
import androidx.compose.ui.semantics.expand
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription

/**
 * Expanded/collapsed disclosure semantics shared by Technical details, Advanced, roadmap
 * phases, code examples, and Diagnostics. [label] is a short stateDescription such as
 * "Technical details expanded". [onToggle] is exposed as the accessibility expand/collapse
 * action (Compose has no boolean `expanded` property; those actions plus [stateDescription]
 * are the supported expanded/collapsed state).
 */
internal fun Modifier.disclosureSemantics(
    expanded: Boolean,
    label: String,
    onToggle: () -> Unit,
): Modifier = semantics {
    stateDescription = label
    if (expanded) {
        collapse { onToggle(); true }
    } else {
        expand { onToggle(); true }
    }
}

/** Polite live region for loading, success, and informational-stop copy. */
internal fun Modifier.politeLiveRegion(): Modifier =
    semantics { liveRegion = LiveRegionMode.Polite }

/** Assertive live region for errors. */
internal fun Modifier.assertiveLiveRegion(): Modifier =
    semantics { liveRegion = LiveRegionMode.Assertive }
