package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.darwin.Darwin

internal actual fun defaultHttpClient(config: BlockfrostConfig): HttpClient =
    HttpClient(Darwin) {
        configureBlockfrost(config)
    }
