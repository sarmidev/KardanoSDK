package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.darwin.Darwin

/**
 * iOS engine is Ktor Darwin (`NSURLSession`). `NSURLSession` does not automatically
 * replay a POST body the way OkHttp's default `retryOnConnectionFailure` can. Engine-level
 * submit replay is therefore not enabled here. Ktor `HttpRequestRetry` is also not
 * installed; see [configureBlockfrost].
 */
internal actual fun defaultHttpClient(config: BlockfrostConfig): HttpClient =
    HttpClient(Darwin) {
        configureBlockfrost(config)
    }
