package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.okhttp.OkHttp

internal actual fun defaultHttpClient(config: BlockfrostConfig): HttpClient =
    HttpClient(OkHttp) {
        configureBlockfrost(config)
    }
