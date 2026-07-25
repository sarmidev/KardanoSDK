package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.cio.CIO

internal actual fun defaultHttpClient(config: BlockfrostConfig): HttpClient =
    HttpClient(CIO) {
        configureBlockfrost(config)
    }
