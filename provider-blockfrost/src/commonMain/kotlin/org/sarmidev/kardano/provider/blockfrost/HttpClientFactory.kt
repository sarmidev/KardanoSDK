package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.HttpClientConfig
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
 * Applies the shared Blockfrost client configuration (JSON content negotiation and the
 * `project_id` header) so every platform actual configures the client identically. The
 * per-request URL is built by [BlockfrostChainQueryProvider] from
 * [BlockfrostNetwork.baseUrl], so no base URL is set here.
 */
internal fun HttpClientConfig<*>.configureBlockfrost(config: BlockfrostConfig) {
    install(ContentNegotiation) {
        json(blockfrostJson)
    }
    defaultRequest {
        header("project_id", config.projectId)
    }
}
