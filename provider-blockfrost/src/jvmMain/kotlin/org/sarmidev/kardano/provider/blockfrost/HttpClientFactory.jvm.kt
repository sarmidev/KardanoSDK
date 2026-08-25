package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.cio.CIO

/**
 * JVM engine is Ktor CIO. CIO has no `retryOnConnectionFailure` switch and does not
 * automatically replay a failed request the way OkHttp's default engine setting can.
 * Engine-level submit replay is therefore not enabled here. Ktor `HttpRequestRetry` is
 * also not installed; see [configureBlockfrost].
 */
internal actual fun defaultHttpClient(config: BlockfrostConfig): HttpClient =
    HttpClient(CIO) {
        configureBlockfrost(config)
    }
