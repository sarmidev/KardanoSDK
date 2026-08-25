package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.HttpTimeoutConfig
import io.ktor.client.plugins.pluginOrNull
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.provider.ProviderError
import org.sarmidev.kardano.provider.SubmitError
import kotlin.coroutines.cancellation.CancellationException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Tests for the explicit [HttpTimeout] policy installed by [configureBlockfrost].
 *
 * Production bounds are asserted through the config-application seam (no 10s/30s sleep).
 * A shortened request timeout plus a delayed [MockEngine] handler exercises the
 * timeout-to-Transport mapping when the plugin fires on the mock engine.
 */
class BlockfrostHttpTimeoutTest {

    @Test
    fun defaultPolicyUsesDocumentedBounds() {
        val policy = BlockfrostHttpTimeoutPolicy.Default
        assertEquals(10_000L, policy.connectTimeoutMillis)
        assertEquals(30_000L, policy.requestTimeoutMillis)
        assertEquals(30_000L, policy.socketTimeoutMillis)
    }

    @Test
    fun applyBlockfrostTimeoutsCopiesPolicyOntoHttpTimeoutConfig() {
        val config = HttpTimeoutConfig()
        config.applyBlockfrostTimeouts(BlockfrostHttpTimeoutPolicy.Default)
        assertEquals(10_000L, config.connectTimeoutMillis)
        assertEquals(30_000L, config.requestTimeoutMillis)
        assertEquals(30_000L, config.socketTimeoutMillis)
    }

    @Test
    fun configureBlockfrostInstallsHttpTimeoutPlugin() {
        val config = BlockfrostConfig(projectId = "test-project-id")
        val client = HttpClient(MockEngine) {
            configureBlockfrost(config)
            engine { addHandler { respond("{}", HttpStatusCode.OK, jsonHeaders) } }
        }
        assertNotNull(
            client.pluginOrNull(HttpTimeout),
            "configureBlockfrost must install HttpTimeout from ktor-client-core",
        )
    }

    @Test
    fun delayedMockResponseMapsToTransportWhenRequestTimeoutElapses() = runTest {
        val shortRequest = BlockfrostHttpTimeoutPolicy(
            connectTimeoutMillis = 10_000L,
            requestTimeoutMillis = 40L,
            socketTimeoutMillis = 30_000L,
        )
        val config = BlockfrostConfig(projectId = "test-project-id")
        val client = HttpClient(MockEngine) {
            configureBlockfrost(config, shortRequest)
            engine {
                addHandler {
                    delay(250)
                    respond("{}", HttpStatusCode.OK, jsonHeaders)
                }
            }
        }
        val provider = BlockfrostChainQueryProvider(config, client)
        val result = provider.getTip()
        assertTrue(result is KardanoResult.Err, "expected timeout Transport, got: $result")
        assertTrue(
            result.error is ProviderError.Transport,
            "expected Transport, got: ${result.error}",
        )
    }

    @Test
    fun delayedSubmitMapsToTransportAndIsNotRetried() = runTest {
        var attempts = 0
        val shortRequest = BlockfrostHttpTimeoutPolicy(
            connectTimeoutMillis = 10_000L,
            requestTimeoutMillis = 40L,
            socketTimeoutMillis = 30_000L,
        )
        val config = BlockfrostConfig(projectId = "test-project-id")
        val client = HttpClient(MockEngine) {
            configureBlockfrost(config, shortRequest)
            engine {
                addHandler {
                    attempts += 1
                    delay(250)
                    respond("\"${BlockfrostFixtures.TX_HASH_A}\"", HttpStatusCode.OK, jsonHeaders)
                }
            }
        }
        val provider = BlockfrostTxSubmitProvider(config, client)
        val result = provider.submit(byteArrayOf(0x83.toByte(), 0x00))
        assertTrue(result is KardanoResult.Err, "expected timeout Transport, got: $result")
        assertTrue(
            result.error is SubmitError.Transport,
            "expected Transport, got: ${result.error}",
        )
        assertEquals(1, attempts, "submit must not be retried after a timeout")
    }

    @Test
    fun getTipRethrowsCancellationDuringTimeoutPath() = runTest {
        val config = BlockfrostConfig(projectId = "test-project-id")
        val client = HttpClient(MockEngine) {
            configureBlockfrost(config)
            engine { addHandler { throw CancellationException("cancelled") } }
        }
        val provider = BlockfrostChainQueryProvider(config, client)
        assertFailsWith<CancellationException> {
            provider.getTip()
        }
    }

    private val jsonHeaders = headersOf(HttpHeaders.ContentType, "application/json")
}
