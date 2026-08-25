package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.network.sockets.ConnectTimeoutException
import io.ktor.client.network.sockets.SocketTimeoutException
import io.ktor.client.plugins.HttpRequestTimeoutException
import io.ktor.client.plugins.HttpTimeoutConfig

/**
 * Explicit HTTP timeout bounds installed on every Blockfrost client.
 *
 * Production uses [Default]: 10s connect, 30s request, 30s socket. Tests may inject a shorter
 * [requestTimeoutMillis] so a delayed [io.ktor.client.engine.mock.MockEngine] handler can
 * exercise the timeout-to-Transport path without sleeping for the production 30s request
 * timeout. This type is not part of the public API.
 *
 * These bounds are an upper limit on a single attempt. There is no automatic retry plugin
 * and submit is never retried.
 */
internal class BlockfrostHttpTimeoutPolicy(
    val connectTimeoutMillis: Long,
    val requestTimeoutMillis: Long,
    val socketTimeoutMillis: Long,
) {
    init {
        require(connectTimeoutMillis > 0L) { "connectTimeoutMillis must be positive" }
        require(requestTimeoutMillis > 0L) { "requestTimeoutMillis must be positive" }
        require(socketTimeoutMillis > 0L) { "socketTimeoutMillis must be positive" }
    }

    internal companion object {
        const val CONNECT_TIMEOUT_MS: Long = 10_000L
        const val REQUEST_TIMEOUT_MS: Long = 30_000L
        const val SOCKET_TIMEOUT_MS: Long = 30_000L

        val Default: BlockfrostHttpTimeoutPolicy = BlockfrostHttpTimeoutPolicy(
            connectTimeoutMillis = CONNECT_TIMEOUT_MS,
            requestTimeoutMillis = REQUEST_TIMEOUT_MS,
            socketTimeoutMillis = SOCKET_TIMEOUT_MS,
        )
    }
}

/** Copies [policy] onto a Ktor [HttpTimeoutConfig]. */
internal fun HttpTimeoutConfig.applyBlockfrostTimeouts(policy: BlockfrostHttpTimeoutPolicy) {
    connectTimeoutMillis = policy.connectTimeoutMillis
    requestTimeoutMillis = policy.requestTimeoutMillis
    socketTimeoutMillis = policy.socketTimeoutMillis
}

/**
 * Maps a caught transport exception to a short message. Timeout types become
 * `"request timed out"` when they have no message; other failures keep
 * `"request failed"`. [kotlin.coroutines.cancellation.CancellationException] must be
 * rethrown by the caller before this is used.
 */
internal fun transportFailureMessage(e: Exception): String =
    if (isHttpTimeoutFailure(e)) {
        e.message ?: "request timed out"
    } else {
        e.message ?: "request failed"
    }

internal fun isHttpTimeoutFailure(e: Exception): Boolean =
    e is HttpRequestTimeoutException ||
        e is ConnectTimeoutException ||
        e is SocketTimeoutException
