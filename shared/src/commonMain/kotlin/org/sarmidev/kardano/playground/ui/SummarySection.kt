package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import org.sarmidev.kardano.playground.SubmitTransactionPresentation
import org.sarmidev.kardano.playground.mvi.PlaygroundState

/**
 * The Summary screen (Block 1.12-pre-e): the guided demo's closing recap. Restates, in plain
 * language, what the SDK actually did — the last recap line honestly reflecting whether the
 * Submit step ran in mock or live mode — followed by an explicit "what this demo is not" scope
 * list, and a primary *Run the demo again* action plus secondary links into About and Roadmap.
 * Pure presentation; it uses the recorded Submit result — rather than the current provider
 * switch — to pick the correct last recap line and calls no SDK.
 */
@Composable
internal fun SummarySection(
    state: PlaygroundState,
    onRunAgain: () -> Unit,
    onOpenAbout: () -> Unit,
    onOpenRoadmap: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
        SectionHeader(title = DemoCopy.Summary.TITLE, subtitle = DemoCopy.Summary.INTRO)

        OutlinedCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                DemoCopy.Summary.recapLines(
                    wasLiveSubmission = state.submit is SubmitTransactionPresentation.Success,
                )
                    .forEachIndexed { index, line -> RecapLine(index + 1, line) }
            }
        }

        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                text = DemoCopy.Summary.SCOPE_HEADING,
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.semantics { heading() },
            )
            DemoCopy.Summary.SCOPE_LINES.forEach { line ->
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
                    Text(
                        text = "•",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = line,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        Button(onClick = onRunAgain, modifier = Modifier.fillMaxWidth()) {
            Text(DemoCopy.Summary.RUN_AGAIN_BUTTON)
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            TextButton(onClick = onOpenAbout) { Text(DemoCopy.Summary.ABOUT_LINK) }
            TextButton(onClick = onOpenRoadmap) { Text(DemoCopy.Summary.ROADMAP_LINK) }
        }
    }
}

@Preview
@Composable
private fun SummarySectionPreview() {
    KardanoPlaygroundTheme {
        SummarySection(
            state = PlaygroundState.initial(),
            onRunAgain = {},
            onOpenAbout = {},
            onOpenRoadmap = {},
        )
    }
}

@Composable
private fun RecapLine(number: Int, text: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {
        Text(
            text = "$number.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}
