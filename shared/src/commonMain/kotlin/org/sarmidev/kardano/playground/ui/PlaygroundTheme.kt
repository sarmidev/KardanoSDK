package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/**
 * The Sarmidev-owned Material 3 theme for the sample Playground (Block 1.12-pre-d, replacing the
 * Kotlin/KMP-inspired palette from 1.12-pre-b).
 *
 * The palette is derived from the project's own icon mark (see `docs/HANDOFF.md`): a violet-to-
 * blue "K" stroke beside a cyan-tinted, Cardano-style dot cluster. Primary follows the mark's
 * violet, secondary its blue extreme, and tertiary a darker cyan accent that echoes the dot
 * cluster without duplicating Cardano's own brand blue. Both schemes use a cool, slightly
 * lilac-tinted neutral for background/surface rather than pure white/black, so the mark (and the
 * launcher icon built from the same source, see `androidApp/.../ic_launcher_*`) reads clearly on
 * top in either theme. This is sample-app styling in `:shared`; it is not part of the SDK public
 * API and carries no protocol meaning.
 */
private val LightColors = lightColorScheme(
    primary = Color(0xFF5B3FD1),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFE6DFFF),
    onPrimaryContainer = Color(0xFF200A66),
    secondary = Color(0xFF216BB9),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFD9E8FA),
    onSecondaryContainer = Color(0xFF06304F),
    tertiary = Color(0xFF006E88),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFC8ECF5),
    onTertiaryContainer = Color(0xFF00272F),
    background = Color(0xFFFAF9FF),
    onBackground = Color(0xFF1B1B21),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1B1B21),
    surfaceVariant = Color(0xFFE9E7F0),
    onSurfaceVariant = Color(0xFF49454E),
    outline = Color(0xFF7A757F),
    error = Color(0xFFB3261E),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFF9DEDC),
    onErrorContainer = Color(0xFF410E0B),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFCDBDFF),
    onPrimary = Color(0xFF33217A),
    primaryContainer = Color(0xFF3C2B78),
    onPrimaryContainer = Color(0xFFE6DFFF),
    secondary = Color(0xFFA6CEFF),
    onSecondary = Color(0xFF00315C),
    secondaryContainer = Color(0xFF173D66),
    onSecondaryContainer = Color(0xFFD9E8FA),
    tertiary = Color(0xFF8FE3FF),
    onTertiary = Color(0xFF00363F),
    tertiaryContainer = Color(0xFF004C59),
    onTertiaryContainer = Color(0xFFC8ECF5),
    background = Color(0xFF0E0C13),
    onBackground = Color(0xFFE7E0E8),
    surface = Color(0xFF16131D),
    onSurface = Color(0xFFE7E0E8),
    surfaceVariant = Color(0xFF272230),
    onSurfaceVariant = Color(0xFFCAC4CF),
    outline = Color(0xFF948F99),
    error = Color(0xFFF2B8B5),
    onError = Color(0xFF601410),
    errorContainer = Color(0xFF8C1D18),
    onErrorContainer = Color(0xFFF9DEDC),
)

/**
 * Sample-app-only brand tokens that Material 3's core color roles don't cover: the five
 * decorative accent hues used by capability/step-number dots in [PlaygroundLanding], and the
 * fixed background/foreground pairs painted behind each [Badge]/[StepStatus] chip in
 * [StatusBadge]/[StatusChip]. Centralized here — via [LocalKardanoBrand] — so no other file in
 * `playground/ui` redeclares its own hex constants (Block 1.12-pre-d).
 */
internal data class KardanoBrandColors(
    val accents: List<Color>,
    val chipNeutralBg: Color,
    val chipNeutralFg: Color,
    val chipInfoBg: Color,
    val chipInfoFg: Color,
    val chipSuccessBg: Color,
    val chipSuccessFg: Color,
    val chipLiveBg: Color,
    val chipLiveFg: Color,
    val chipLoadingBg: Color,
    val chipLoadingFg: Color,
    val chipErrorBg: Color,
    val chipErrorFg: Color,
)

private val LightBrandColors = KardanoBrandColors(
    accents = listOf(
        Color(0xFF5B3FD1),
        Color(0xFF216BB9),
        Color(0xFF006E88),
        Color(0xFF12876F),
        Color(0xFFA23593),
    ),
    chipNeutralBg = Color(0xFFE9E7F0),
    chipNeutralFg = Color(0xFF433A54),
    chipInfoBg = Color(0xFFD9E8FA),
    chipInfoFg = Color(0xFF0B3C66),
    chipSuccessBg = Color(0xFFD6F1E1),
    chipSuccessFg = Color(0xFF0F6D3F),
    chipLiveBg = Color(0xFFFFE3C2),
    chipLiveFg = Color(0xFF7A4100),
    chipLoadingBg = Color(0xFFE6DFFF),
    chipLoadingFg = Color(0xFF3F2A99),
    chipErrorBg = Color(0xFFFBDAD7),
    chipErrorFg = Color(0xFF8A1C16),
)

private val DarkBrandColors = KardanoBrandColors(
    accents = listOf(
        Color(0xFFCDBDFF),
        Color(0xFFA6CEFF),
        Color(0xFF8FE3FF),
        Color(0xFF7CDDC0),
        Color(0xFFF0A8E0),
    ),
    chipNeutralBg = Color(0xFF3A3444),
    chipNeutralFg = Color(0xFFE3DEEA),
    chipInfoBg = Color(0xFF173D66),
    chipInfoFg = Color(0xFFD9E8FA),
    chipSuccessBg = Color(0xFF14432B),
    chipSuccessFg = Color(0xFFA7E6C3),
    chipLiveBg = Color(0xFF5C3B00),
    chipLiveFg = Color(0xFFFFD9A0),
    chipLoadingBg = Color(0xFF3C2B78),
    chipLoadingFg = Color(0xFFE6DFFF),
    chipErrorBg = Color(0xFF601410),
    chipErrorFg = Color(0xFFF9DEDC),
)

/** The active [KardanoBrandColors], provided by [KardanoPlaygroundTheme]. Defaults to light. */
internal val LocalKardanoBrand = staticCompositionLocalOf { LightBrandColors }

/**
 * Applies the Sarmidev-owned [MaterialTheme] used across the Playground, following the system
 * light/dark setting by default, and provides [LocalKardanoBrand] alongside it. Wraps [content]
 * so every step card, badge, and diagnostics tool renders against the same palette.
 */
@Composable
internal fun KardanoPlaygroundTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    CompositionLocalProvider(
        LocalKardanoBrand provides if (darkTheme) DarkBrandColors else LightBrandColors,
    ) {
        MaterialTheme(
            colorScheme = if (darkTheme) DarkColors else LightColors,
            content = content,
        )
    }
}
