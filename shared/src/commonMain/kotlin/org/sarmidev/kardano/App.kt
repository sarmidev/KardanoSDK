package org.sarmidev.kardano

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import org.sarmidev.kardano.playground.PlaygroundScreen
import org.sarmidev.kardano.playground.ui.KardanoPlaygroundTheme

/**
 * Root composable for the Kardano SDK sample app.
 *
 * Applies the Kotlin/KMP-inspired [KardanoPlaygroundTheme] (Block 1.12-pre-b) and delegates to
 * [PlaygroundScreen] (Block 1.2: Android SDK Playground). This is sample/diagnostic code in
 * `:shared`; it is not part of the SDK public API.
 */
@Composable
@Preview
fun App() {
    KardanoPlaygroundTheme {
        PlaygroundScreen()
    }
}
