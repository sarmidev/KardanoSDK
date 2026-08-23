package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kardanosdk.shared.generated.resources.Res
import kardanosdk.shared.generated.resources.kardano_mark_dark
import kardanosdk.shared.generated.resources.kardano_mark_light
import org.jetbrains.compose.resources.painterResource

/**
 * The Playground's shared hero card (Block 1.12-pre-c, visually refreshed in 1.12-pre-d;
 * generalized in Block 1.12-pre-e into a reusable shell for both the Welcome and About screens):
 * the project's own icon mark via [BrandMark], an optional badge, [title]/[subtitle], and
 * arbitrary screen-specific [content] painted underneath. Presentation only — it reads no SDK
 * state and computes nothing.
 */
@Composable
internal fun HeroCard(
    title: String,
    subtitle: String,
    modifier: Modifier = Modifier,
    badgeText: String? = null,
    content: @Composable ColumnScope.() -> Unit = {},
) {
    Box(
        modifier = modifier
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
                        text = title,
                        style = MaterialTheme.typography.headlineSmall,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.semantics { heading() },
                    )
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            if (badgeText != null) {
                BadgeRow(listOf(Badge(badgeText, BadgeTone.INFO)))
            }

            content()
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
