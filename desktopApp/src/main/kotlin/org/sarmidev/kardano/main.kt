package org.sarmidev.kardano

import androidx.compose.ui.res.painterResource
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application

fun main() = application {
    Window(
        onCloseRequest = ::exitApplication,
        title = "Kardano SDK",
        // The Sarmidev-owned mark, loaded from the desktopApp JVM classpath resource added in
        // Block 1.12-pre-d (`src/main/resources/icon.png`) — separate from the :shared module's
        // Compose-multiplatform resources, which desktopApp cannot see (internal visibility).
        icon = painterResource("icon.png"),
    ) {
        App()
    }
}