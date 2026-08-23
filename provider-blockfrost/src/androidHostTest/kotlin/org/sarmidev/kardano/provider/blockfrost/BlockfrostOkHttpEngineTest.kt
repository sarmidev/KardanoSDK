package org.sarmidev.kardano.provider.blockfrost

import kotlin.test.Test
import kotlin.test.assertFalse

/**
 * Engine-level OkHttp replay is distinct from Ktor's `HttpRequestRetry` plugin.
 * Android production clients must use [blockfrostOkHttpClient], which disables
 * `retryOnConnectionFailure` so a connection failure cannot replay submit.
 */
class BlockfrostOkHttpEngineTest {

    @Test
    fun blockfrostOkHttpClientDisablesRetryOnConnectionFailure() {
        val client = blockfrostOkHttpClient()
        assertFalse(
            client.retryOnConnectionFailure,
            "OkHttp must not replay a failed connection (including POST /tx/submit)",
        )
    }
}
