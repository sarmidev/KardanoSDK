package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp

/**
 * The Welcome screen (Block 1.12-pre-e): the first thing a first-time viewer sees. States, in
 * plain language, what the guided demo will do and why, previews the five steps, and offers one
 * obvious call to action — [onStartDemo] — plus secondary links into the About and Roadmap
 * screens. Pure presentation; it reads no SDK state and calls no SDK.
 */
@Composable
internal fun WelcomeSection(
    platformLabel: String,
    onStartDemo: () -> Unit,
    onOpenAbout: () -> Unit,
    onOpenRoadmap: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
        HeroCard(
            badgeText = DemoCopy.Welcome.BADGE,
            title = DemoCopy.Welcome.TITLE,
            subtitle = DemoCopy.Welcome.SUBTITLE,
        ) {
            Text(
                text = DemoCopy.Welcome.INTRO,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }

        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            SectionHeader(title = DemoCopy.Welcome.PREVIEW_HEADING)
            DemoCopy.Welcome.PREVIEW_STEPS.forEachIndexed { index, step ->
                PreviewStepLine(index + 1, step)
            }
        }

        Text(
            text = DemoCopy.Welcome.REASSURANCE,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Button(onClick = onStartDemo, modifier = Modifier.fillMaxWidth()) {
            Text(DemoCopy.Welcome.START_BUTTON)
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            TextButton(onClick = onOpenAbout) { Text(DemoCopy.Welcome.ABOUT_LINK) }
            TextButton(onClick = onOpenRoadmap) { Text(DemoCopy.Welcome.ROADMAP_LINK) }
        }

        Text(
            text = DemoCopy.Welcome.footer(platformLabel),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Preview
@Composable
private fun WelcomeSectionPreview() {
    KardanoPlaygroundTheme {
        WelcomeSection(
            platformLabel = "Android",
            onStartDemo = {},
            onOpenAbout = {},
            onOpenRoadmap = {},
        )
    }
}

@Composable
private fun PreviewStepLine(number: Int, text: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.Top,
    ) {
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
