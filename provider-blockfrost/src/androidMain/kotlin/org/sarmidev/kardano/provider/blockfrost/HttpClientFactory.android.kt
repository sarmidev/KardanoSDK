package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.okhttp.OkHttp
import io.ktor.client.engine.okhttp.OkHttpConfig
import okhttp3.OkHttpClient

/**
 * Builds the OkHttp client used as Ktor's Android `preconfigured` starting point.
 *
 * Defense in depth only. Ktor 3.5.1's `OkHttpEngine.createOkHttpClient` does
 * `(preconfigured ?: prototype).newBuilder().apply(config.config)`, and the default
 * `OkHttpConfig.config` lambda sets `retryOnConnectionFailure(true)` on that builder.
 * A preconfigured client with retry disabled is therefore overwritten unless
 * [applyBlockfrostOkHttpEngineConfig] also appends `retryOnConnectionFailure(false)`
 * onto the engine `config` block so it runs last.
 */
internal fun blockfrostOkHttpClient(): OkHttpClient =
    OkHttpClient.Builder()
        .retryOnConnectionFailure(false)
        .build()

/**
 * Appends `retryOnConnectionFailure(false)` onto the Ktor OkHttp engine `config` so it
 * runs after Ktor 3.5.1's default `retryOnConnectionFailure(true)`.
 *
 * This is the setting that determines the effective engine client. Callers should also
 * set [OkHttpConfig.preconfigured] to [blockfrostOkHttpClient] as defense in depth.
 */
internal fun OkHttpConfig.applyBlockfrostOkHttpEngineConfig() {
    config {
        retryOnConnectionFailure(false)
    }
}

internal actual fun defaultHttpClient(config: BlockfrostConfig): HttpClient =
    HttpClient(OkHttp) {
        engine {
            preconfigured = blockfrostOkHttpClient()
            applyBlockfrostOkHttpEngineConfig()
        }
        configureBlockfrost(config)
    }
