package org.sarmidev.kardano

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import org.sarmidev.kardano.playground.PlaygroundScreen

/**
 * Root composable for the Kardano SDK sample app.
 *
 * Applies [MaterialTheme] and delegates to [PlaygroundScreen] (Block 1.2: Android SDK
 * Playground). This is sample/diagnostic code in `:shared`; it is not part of the SDK
 * public API.
 */
@Composable
@Preview
fun App() {
    MaterialTheme {
        PlaygroundScreen()
    }
}
