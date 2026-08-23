package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.okhttp.OkHttp
import okhttp3.OkHttpClient

/**
 * Builds the OkHttp client used as Ktor's Android engine.
 *
 * OkHttp defaults to [OkHttpClient.Builder.retryOnConnectionFailure] `true`, which can
 * replay a request after a connection failure — including `POST /tx/submit`. That is
 * engine-level behavior, distinct from Ktor's `HttpRequestRetry` plugin (this module does
 * not install that plugin). This builder sets `retryOnConnectionFailure(false)` so OkHttp
 * cannot replay a submit.
 */
internal fun blockfrostOkHttpClient(): OkHttpClient =
    OkHttpClient.Builder()
        .retryOnConnectionFailure(false)
        .build()

internal actual fun defaultHttpClient(config: BlockfrostConfig): HttpClient =
    HttpClient(OkHttp) {
        engine {
            preconfigured = blockfrostOkHttpClient()
        }
        configureBlockfrost(config)
    }
