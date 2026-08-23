package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import org.sarmidev.kardano.playground.LabeledRow

/**
 * One card in the guided demo (Block 1.12-pre-b; reworked into a plain-language single-step card
 * in Block 1.12-pre-e). Presents exactly one step as a self-contained unit: a numbered heading
 * with a live [status] chip, a one-line [explanation] of what the SDK does and why, one primary
 * [action] button (which shows a spinner while [actionLoading]), a plain-language
 * [resultHeadline]/[resultDetail] pair once the step has something to report, an optional
 * [guidance] line pointing at what happens next, an optional collapsible [details] block behind
 * a "Technical details" toggle, and an optional [secondaryActions] row (Continue / Back / Try
 * again). This is a pure presentation shell — it dispatches [onAction]/[onToggleDetails]
 * callbacks and renders provided content; it holds no SDK logic and reads no state itself.
 */
@Composable
internal fun FlowStepCard(
    stepNumber: Int,
    stepCount: Int,
    title: String,
    explanation: String,
    status: StepStatus,
    actionLabel: String,
    actionLoading: Boolean,
    onAction: () -> Unit,
    modifier: Modifier = Modifier,
    resultHeadline: String? = null,
    resultDetail: String? = null,
    resultIsError: Boolean = false,
    guidance: String? = null,
    showDetailsToggle: Boolean = false,
    detailsExpanded: Boolean = false,
    onToggleDetails: () -> Unit = {},
    details: @Composable ColumnScope.() -> Unit = {},
    secondaryActions: (@Composable RowScope.() -> Unit)? = null,
) {
    ElevatedCard(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics(mergeDescendants = true) {
                        heading()
                        contentDescription = "$title, ${status.label}"
                    },
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StepNumber(stepNumber, stepCount)
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                StatusChip(status)
            }

            Text(
                text = explanation,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Button(
                onClick = onAction,
                enabled = !actionLoading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (actionLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                    Text(
                        text = "  $actionLabel",
                        modifier = Modifier.politeLiveRegion(),
                    )
                } else {
                    Text(actionLabel)
                }
            }

            if (resultHeadline != null) {
                ResultHeadline(resultHeadline, isError = resultIsError)
            }
            if (resultDetail != null) {
                ResultDetail(resultDetail)
            }
            if (guidance != null) {
                Text(
                    text = guidance,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }

            if (showDetailsToggle) {
                TextButton(
                    onClick = onToggleDetails,
                    modifier = Modifier
                        .fillMaxWidth()
                        .disclosureSemantics(
                            expanded = detailsExpanded,
                            label = if (detailsExpanded) {
                                "Technical details expanded"
                            } else {
                                "Technical details collapsed"
                            },
                            onToggle = onToggleDetails,
                        ),
                ) {
                    Text(if (detailsExpanded) "Hide technical details" else "Technical details")
                }
                if (detailsExpanded) details()
            }

            if (secondaryActions != null) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    content = secondaryActions,
                )
            }
        }
    }
}

@Composable
private fun StepNumber(number: Int, count: Int) {
    Surface(
        color = MaterialTheme.colorScheme.primary,
        shape = CircleShape,
        modifier = Modifier
            .size(28.dp)
            .semantics { contentDescription = "Step $number of $count" },
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(
                text = number.toString(),
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onPrimary,
                textAlign = TextAlign.Center,
            )
        }
    }
}

/** A short, bold plain-language headline summarizing a step's result — success/info or error. */
@Composable
internal fun ResultHeadline(text: String, isError: Boolean = false) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleSmall,
        color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
        modifier = if (isError) Modifier.assertiveLiveRegion() else Modifier.politeLiveRegion(),
    )
}

/** A supporting sentence under a [ResultHeadline], selectable for values worth copying. */
@Composable
internal fun ResultDetail(text: String) {
    SelectionContainer {
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

// ---------------------------------------------------------------------------
// Shared result primitives (used by both the guided flow and diagnostics)
// ---------------------------------------------------------------------------

/**
 * A single labeled key/value line. Wraps the value in a [SelectionContainer] so the owner can
 * long-press/select and copy it (for example a generated `addr_test1…` address, to fund it
 * from a preprod faucet) without any clipboard API surface.
 */
@Composable
internal fun ResultRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.outline,
            modifier = Modifier.weight(0.42f),
        )
        SelectionContainer(modifier = Modifier.weight(0.58f)) {
            Text(text = value, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/** Renders every [rows] entry as a [ResultRow] inside a subtle container. */
@Composable
internal fun LabeledRows(rows: List<LabeledRow>, caption: String? = null) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = MaterialTheme.shapes.medium,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            if (caption != null) {
                Text(
                    text = caption,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            rows.forEach { row -> ResultRow(row.label, row.value) }
        }
    }
}

/** A readable inline error placed directly under the step or tool that produced it. */
@Composable
internal fun ErrorInline(message: String) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        shape = MaterialTheme.shapes.medium,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            text = message,
            modifier = Modifier.padding(12.dp).assertiveLiveRegion(),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onErrorContainer,
        )
    }
}

/** A per-step/tool loading placeholder. */
@Composable
internal fun LoadingInline() {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
        Text(
            text = "Working…",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.politeLiveRegion(),
        )
    }
}
