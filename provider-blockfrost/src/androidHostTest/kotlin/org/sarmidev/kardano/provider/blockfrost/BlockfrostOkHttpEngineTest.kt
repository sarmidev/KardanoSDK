package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.engine.okhttp.OkHttpConfig
import okhttp3.OkHttpClient
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Engine-level OkHttp replay is distinct from Ktor's `HttpRequestRetry` plugin.
 *
 * Ktor 3.5.1's default `OkHttpConfig.config` sets `retryOnConnectionFailure(true)` and
 * `OkHttpEngine.createOkHttpClient` applies that lambda after `preconfigured.newBuilder()`.
 * These tests assert the effective engine client used by the production [defaultHttpClient]
 * Ktor `HttpClient`, not only the standalone [blockfrostOkHttpClient] helper. They do not
 * induce a live connection-failure replay.
 */
class BlockfrostOkHttpEngineTest {

    @Test
    fun blockfrostOkHttpClientDisablesRetryOnConnectionFailure() {
        val client = blockfrostOkHttpClient()
        assertFalse(
            client.retryOnConnectionFailure,
            "preconfigured helper must disable retry (defense in depth)",
        )
    }

    @Test
    fun preconfiguredClientAloneIsOverwrittenByKtorDefaultRetry() {
        val preconfigured = blockfrostOkHttpClient()
        assertFalse(preconfigured.retryOnConnectionFailure)
        val afterKtorDefaults = preconfigured.newBuilder()
            .apply(ktor351DefaultOkHttpConfig)
            .build()
        assertTrue(
            afterKtorDefaults.retryOnConnectionFailure,
            "Ktor 3.5.1 default OkHttpConfig.config sets retryOnConnectionFailure(true) " +
                "after preconfigured.newBuilder(); preconfigured alone is not enough",
        )
    }

    @Test
    fun defaultHttpClientEffectiveEngineDisablesRetryAfterKtorApply() {
        val client = defaultHttpClient(BlockfrostConfig(projectId = "test-project-id"))
        try {
            val engineConfig = client.engine.config as OkHttpConfig
            val effective = ktor351EffectiveOkHttpClient(engineConfig)
            assertFalse(
                effective.retryOnConnectionFailure,
                "effective Ktor OkHttp engine client must have retryOnConnectionFailure=false",
            )
        } finally {
            client.close()
        }
    }

    /**
     * Ktor 3.5.1 default `OkHttpConfig.config` lambda
     * (`ktor-client-okhttp` `OkHttpConfig.kt`).
     */
    private val ktor351DefaultOkHttpConfig: OkHttpClient.Builder.() -> Unit = {
        followRedirects(false)
        followSslRedirects(false)
        retryOnConnectionFailure(true)
    }

    /**
     * Mirrors Ktor 3.5.1 `OkHttpEngine.createOkHttpClient`:
     * `(preconfigured ?: prototype).newBuilder().apply(config.config)`.
     *
     * The composed `config` lambda is `internal` to `ktor-client-okhttp`; this test seam
     * reads the live [HttpClient] engine's `OkHttpConfig` so the assertion is against the
     * effective engine configuration, not a reconstructed copy of our own helper.
     */
    private fun ktor351EffectiveOkHttpClient(engineConfig: OkHttpConfig): OkHttpClient {
        val configField = OkHttpConfig::class.java.getDeclaredField("config")
        configField.isAccessible = true
        @Suppress("UNCHECKED_CAST")
        val ktorConfig = configField.get(engineConfig) as OkHttpClient.Builder.() -> Unit
        return (engineConfig.preconfigured ?: OkHttpClient()).newBuilder()
            .apply(ktorConfig)
            .build()
    }
}
