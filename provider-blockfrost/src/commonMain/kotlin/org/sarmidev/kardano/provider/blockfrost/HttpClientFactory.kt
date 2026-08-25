package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.HttpClientConfig
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.request.header
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json

/**
 * Builds the default [HttpClient] for a [BlockfrostChainQueryProvider] on the current
 * platform, using the platform's Ktor engine.
 *
 * This is `internal`: production callers use [BlockfrostChainQueryProvider.create], and tests
 * inject their own [HttpClient] (for example one backed by a mock engine) through the
 * `internal` constructor, so no real engine or network is required to test mapping.
 */
internal expect fun defaultHttpClient(config: BlockfrostConfig): HttpClient

/** The JSON reader used for Blockfrost responses; tolerant of fields the SDK does not model. */
internal val blockfrostJson: Json = Json { ignoreUnknownKeys = true }

/**
 * Applies the shared Blockfrost client configuration (JSON content negotiation, explicit
 * [HttpTimeout] bounds, and the `project_id` header) so every platform actual configures the
 * client identically. The per-request URL is built by [BlockfrostChainQueryProvider] from
 * [BlockfrostNetwork.baseUrl], so no base URL is set here.
 *
 * [HttpTimeout] is installed from `ktor-client-core` (no extra dependency). Default bounds
 * are [BlockfrostHttpTimeoutPolicy.Default]: 10s connect, 30s request, 30s socket. There is
 * no `HttpRequestRetry` plugin: a failed attempt is returned as a typed error. That plugin
 * policy is separate from engine-level replay. On Android, the OkHttp engine used by
 * [defaultHttpClient] sets `engine { config { retryOnConnectionFailure(false) } }` so
 * the effective Ktor engine client has retry disabled: Ktor 3.5.2's default
 * `OkHttpConfig.config` reapplies `retryOnConnectionFailure(true)` after a preconfigured
 * client. A preconfigured client with retry disabled is kept as defense in depth. CIO
 * (JVM) and Darwin (iOS) do not enable an equivalent automatic request replay.
 *
 * @param timeouts test-only override for the installed [HttpTimeout] values. Production
 *   callers use the default.
 */
internal fun HttpClientConfig<*>.configureBlockfrost(
    config: BlockfrostConfig,
    timeouts: BlockfrostHttpTimeoutPolicy = BlockfrostHttpTimeoutPolicy.Default,
) {
    install(ContentNegotiation) {
        json(blockfrostJson)
    }
    install(HttpTimeout) {
        applyBlockfrostTimeouts(timeouts)
    }
    defaultRequest {
        header("project_id", config.projectId)
    }
}
