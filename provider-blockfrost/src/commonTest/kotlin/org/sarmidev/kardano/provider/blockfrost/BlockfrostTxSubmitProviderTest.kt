package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.MockRequestHandleScope
import io.ktor.client.engine.mock.respond
import io.ktor.client.request.HttpRequestData
import io.ktor.client.request.HttpResponseData
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpMethod
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.OutgoingContent
import io.ktor.http.headersOf
import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.hex.Hex
import org.sarmidev.kardano.provider.SubmitError
import kotlin.coroutines.cancellation.CancellationException
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/**
 * Tests for [BlockfrostTxSubmitProvider] using a Ktor [MockEngine] and the sanitized
 * [BlockfrostFixtures]. No real network, no keys, no live submission.
 */
class BlockfrostTxSubmitProviderTest {

    private val sampleCbor: ByteArray = byteArrayOf(0x83.toByte(), 0xa4.toByte(), 0x00, 0x01, 0x02)

    // ----- success -----

    @Test
    fun submitSendsExpectedRequestAndMapsAcceptedId() = runTest {
        var captured: HttpRequestData? = null
        val provider = provider {
            captured = it
            json(BlockfrostFixtures.SUBMIT_ACCEPTED)
        }

        val txHash = ok(provider.submit(sampleCbor))

        assertEquals(BlockfrostFixtures.TX_HASH_A, Hex.encode(txHash.toByteArray()))

        val request = requireNotNull(captured) { "expected the provider to make an HTTP request" }
        assertEquals(HttpMethod.Post, request.method)
        assertTrue(
            request.url.encodedPath.endsWith("/tx/submit"),
            "expected path to end with /tx/submit, got: ${request.url.encodedPath}",
        )
        assertEquals("test-project-id", request.headers["project_id"])
        val content = request.body
        assertTrue(content is OutgoingContent.ByteArrayContent, "expected a raw ByteArray body")
        assertContentEquals(sampleCbor, content.bytes())
        assertEquals("application/cbor", content.contentType?.toString())
    }

    @Test
    fun submitAcceptsUnquotedResponseBody() = runTest {
        val provider = providerReturning(BlockfrostFixtures.SUBMIT_ACCEPTED_UNQUOTED)

        val txHash = ok(provider.submit(sampleCbor))

        assertEquals(BlockfrostFixtures.TX_HASH_A, Hex.encode(txHash.toByteArray()))
    }

    // ----- empty input -----

    @Test
    fun submitWithEmptyBytesReturnsEmptyTransactionWithoutHttpCall() = runTest {
        var called = false
        val provider = provider {
            called = true
            json(BlockfrostFixtures.SUBMIT_ACCEPTED)
        }

        val error = err(provider.submit(ByteArray(0)))

        assertEquals(SubmitError.EmptyTransaction, error)
        assertEquals(false, called)
    }

    // ----- malformed success body -----

    @Test
    fun submitMapsNonHexAcceptedBodyToDeserialization() = runTest {
        val provider = providerReturning(BlockfrostFixtures.SUBMIT_ACCEPTED_NOT_HEX)

        val error = err(provider.submit(sampleCbor))

        assertTrue(error is SubmitError.Deserialization, "expected Deserialization, got: $error")
    }

    @Test
    fun submitMapsWrongLengthAcceptedBodyToDeserialization() = runTest {
        val provider = providerReturning(BlockfrostFixtures.SUBMIT_ACCEPTED_TOO_SHORT)

        val error = err(provider.submit(sampleCbor))

        assertTrue(error is SubmitError.Deserialization, "expected Deserialization, got: $error")
    }

    // ----- error mapping -----

    @Test
    fun submitMaps400ToRejectedWithParsedDetail() = runTest {
        val provider = provider { json(BlockfrostFixtures.SUBMIT_REJECTED_BODY, HttpStatusCode.BadRequest) }

        val error = err(provider.submit(sampleCbor))

        assertTrue(error is SubmitError.Rejected, "expected Rejected, got: $error")
        assertEquals(400, error.code)
        assertTrue(
            error.detail.contains("sanitized", ignoreCase = true),
            "expected the parsed message in detail, got: ${error.detail}",
        )
    }

    @Test
    fun submitMaps403ToRemoteStatusWithParsedDetail() = runTest {
        val provider = provider { json(BlockfrostFixtures.FORBIDDEN_BODY, HttpStatusCode.Forbidden) }

        val error = err(provider.submit(sampleCbor))

        assertTrue(error is SubmitError.RemoteStatus, "expected RemoteStatus, got: $error")
        assertEquals(403, error.code)
        assertTrue(error.detail?.contains("sanitized", ignoreCase = true) == true)
    }

    @Test
    fun submitMaps404ToRemoteStatus() = runTest {
        val provider = provider { json("{}", HttpStatusCode.NotFound) }

        val error = err(provider.submit(sampleCbor))

        assertTrue(error is SubmitError.RemoteStatus, "expected RemoteStatus, got: $error")
        assertEquals(404, error.code)
    }

    @Test
    fun submitMaps418ToRemoteStatus() = runTest {
        val provider = provider { json("{}", HttpStatusCode(418, "I'm a Teapot")) }

        val error = err(provider.submit(sampleCbor))

        assertTrue(error is SubmitError.RemoteStatus, "expected RemoteStatus, got: $error")
        assertEquals(418, error.code)
    }

    @Test
    fun submitMaps425ToRemoteStatus() = runTest {
        val provider = provider { json("{}", HttpStatusCode(425, "Too Early")) }

        val error = err(provider.submit(sampleCbor))

        assertTrue(error is SubmitError.RemoteStatus, "expected RemoteStatus, got: $error")
        assertEquals(425, error.code)
    }

    @Test
    fun submitMaps429ToRateLimited() = runTest {
        val provider = provider { json("{}", HttpStatusCode.TooManyRequests) }

        val error = err(provider.submit(sampleCbor))

        assertEquals(SubmitError.RateLimited, error)
    }

    @Test
    fun submitMaps500ToRemoteStatus() = runTest {
        val provider = provider { json("{}", HttpStatusCode.InternalServerError) }

        val error = err(provider.submit(sampleCbor))

        assertTrue(error is SubmitError.RemoteStatus, "expected RemoteStatus, got: $error")
        assertEquals(500, error.code)
    }

    // ----- transport / cancellation -----

    @Test
    fun submitMapsTransportExceptionToTransport() = runTest {
        val provider = provider { throw RuntimeException("connection reset") }

        val error = err(provider.submit(sampleCbor))

        assertTrue(error is SubmitError.Transport, "expected Transport, got: $error")
    }

    @Test
    fun submitRethrowsCancellationInsteadOfSwallowingIt() = runTest {
        val provider = provider { throw CancellationException("cancelled") }

        assertFailsWith<CancellationException> {
            provider.submit(sampleCbor)
        }
    }

    // ----- helpers -----

    private fun MockRequestHandleScope.json(
        body: String,
        status: HttpStatusCode = HttpStatusCode.OK,
    ): HttpResponseData =
        respond(body, status, headersOf(HttpHeaders.ContentType, "application/json"))

    private fun provider(
        network: BlockfrostNetwork = BlockfrostNetwork.PREPROD,
        handler: suspend MockRequestHandleScope.(HttpRequestData) -> HttpResponseData,
    ): BlockfrostTxSubmitProvider {
        val config = BlockfrostConfig(projectId = "test-project-id", network = network)
        val client = HttpClient(MockEngine) {
            configureBlockfrost(config)
            engine { addHandler(handler) }
        }
        return BlockfrostTxSubmitProvider(config, client)
    }

    private fun providerReturning(
        body: String,
        status: HttpStatusCode = HttpStatusCode.OK,
    ): BlockfrostTxSubmitProvider = provider { json(body, status) }

    private fun <T> ok(result: KardanoResult<T, SubmitError>): T {
        assertTrue(result is KardanoResult.Ok, "expected Ok but was $result")
        return result.value
    }

    private fun err(result: KardanoResult<*, SubmitError>): SubmitError {
        assertTrue(result is KardanoResult.Err, "expected Err but was $result")
        return result.error
    }
}
