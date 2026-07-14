package org.sarmidev.kardano.playground.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/**
 * A Kotlin/KMP-inspired Material 3 theme for the sample Playground (Block 1.12-pre-b).
 *
 * The palette is drawn from Kotlin/KMP brand hues — a purple lead, a blue secondary, and an
 * orange tertiary — kept at restrained contrast so the guided flow reads calmly rather than
 * as a saturated diagnostics form. This is sample-app styling in `:shared`; it is not part of
 * the SDK public API and carries no protocol meaning.
 */
private val KotlinPurple = Color(0xFF7F52FF)
private val KmpBlue = Color(0xFF3B6FF5)
private val KmpOrange = Color(0xFFF08A24)

private val LightColors = lightColorScheme(
    primary = KotlinPurple,
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFEADDFF),
    onPrimaryContainer = Color(0xFF250057),
    secondary = KmpBlue,
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFDBE4FF),
    onSecondaryContainer = Color(0xFF00164F),
    tertiary = KmpOrange,
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFFFE0C2),
    onTertiaryContainer = Color(0xFF301400),
    background = Color(0xFFFBF8FF),
    onBackground = Color(0xFF1B1B21),
    surface = Color(0xFFFBF8FF),
    onSurface = Color(0xFF1B1B21),
    surfaceVariant = Color(0xFFE7E0EB),
    onSurfaceVariant = Color(0xFF49454E),
    outline = Color(0xFF7A757F),
    error = Color(0xFFB3261E),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFF9DEDC),
    onErrorContainer = Color(0xFF410E0B),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFCBBEFF),
    onPrimary = Color(0xFF35138C),
    primaryContainer = Color(0xFF4C29A6),
    onPrimaryContainer = Color(0xFFEADDFF),
    secondary = Color(0xFFB4C5FF),
    onSecondary = Color(0xFF002A78),
    secondaryContainer = Color(0xFF1F3F8F),
    onSecondaryContainer = Color(0xFFDBE4FF),
    tertiary = Color(0xFFFFB77C),
    onTertiary = Color(0xFF4E2600),
    tertiaryContainer = Color(0xFF6E3900),
    onTertiaryContainer = Color(0xFFFFE0C2),
    background = Color(0xFF141218),
    onBackground = Color(0xFFE7E0E8),
    surface = Color(0xFF141218),
    onSurface = Color(0xFFE7E0E8),
    surfaceVariant = Color(0xFF49454E),
    onSurfaceVariant = Color(0xFFCAC4CF),
    outline = Color(0xFF948F99),
    error = Color(0xFFF2B8B5),
    onError = Color(0xFF601410),
    errorContainer = Color(0xFF8C1D18),
    onErrorContainer = Color(0xFFF9DEDC),
)

/**
 * Applies the Kotlin/KMP-inspired [MaterialTheme] used across the Playground, following the
 * system light/dark setting by default. Wraps [content] so every step card, badge, and
 * diagnostics tool renders against the same palette.
 */
@Composable
internal fun KardanoPlaygroundTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
