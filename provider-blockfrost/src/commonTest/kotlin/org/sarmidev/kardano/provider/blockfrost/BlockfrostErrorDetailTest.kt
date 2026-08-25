package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import io.ktor.utils.io.ByteReadChannel
import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.provider.ProviderError
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Bounded error-detail reading: the helper must not materialize more than
 * [MAX_ERROR_DETAIL_READ_BYTES] and public detail must stay within
 * [MAX_ERROR_DETAIL_CHARS].
 */
class BlockfrostErrorDetailTest {

    @Test
    fun emptyBodyYieldsNullDetail() = runTest {
        val read = readBoundedErrorPrefix(ByteReadChannel(ByteArray(0)))
        assertFalse(read.bodyMayContinue)
        assertNull(detailFromBoundedRead(read))
    }

    @Test
    fun blankBodyYieldsNullDetail() = runTest {
        val read = readBoundedErrorPrefix(ByteReadChannel("   ".encodeToByteArray()))
        assertNull(detailFromBoundedRead(read))
    }

    @Test
    fun malformedCompleteBodyUsesRawText() = runTest {
        val raw = "not a json error envelope"
        val read = readBoundedErrorPrefix(ByteReadChannel(raw.encodeToByteArray()))
        assertFalse(read.bodyMayContinue)
        assertEquals(raw, detailFromBoundedRead(read))
    }

    @Test
    fun hugeRawBodyDoesNotParseAndStaysBounded() = runTest {
        val huge = "A".repeat(MAX_ERROR_DETAIL_READ_BYTES + 4_000)
        val read = readBoundedErrorPrefix(ByteReadChannel(huge.encodeToByteArray()))
        assertTrue(read.bodyMayContinue, "byte budget must fill before the rest is read")
        assertTrue(read.text.length <= MAX_ERROR_DETAIL_READ_BYTES)
        val detail = detailFromBoundedRead(read)
        assertNotNull(detail)
        assertTrue(detail.length <= MAX_ERROR_DETAIL_CHARS, "public detail length ${detail.length}")
        assertTrue(detail.endsWith(ERROR_DETAIL_TRUNCATED_MARKER))
        assertFalse(detail.contains("{"), "truncated prefix must not be parsed as JSON")
    }

    @Test
    fun hugeEnvelopeFieldOnCompleteSmallBodyIsCapped() = runTest {
        val longMessage = "m".repeat(MAX_ERROR_DETAIL_CHARS + 80)
        val envelope =
            """{"status_code":403,"error":"Forbidden","message":"$longMessage"}"""
        assertTrue(
            envelope.encodeToByteArray().size < MAX_ERROR_DETAIL_READ_BYTES,
            "this case is a complete small envelope with a long field",
        )
        val read = readBoundedErrorPrefix(ByteReadChannel(envelope.encodeToByteArray()))
        assertFalse(read.bodyMayContinue)
        val detail = detailFromBoundedRead(read)
        assertNotNull(detail)
        assertTrue(detail.length <= MAX_ERROR_DETAIL_CHARS, "public detail length ${detail.length}")
        assertTrue(detail.endsWith(ERROR_DETAIL_TRUNCATED_MARKER))
        assertTrue(detail.startsWith("m"))
    }

    @Test
    fun completeEnvelopeMessageIsUsedWithoutMarker() = runTest {
        val read = readBoundedErrorPrefix(
            ByteReadChannel(BlockfrostFixtures.FORBIDDEN_BODY.encodeToByteArray()),
        )
        assertFalse(read.bodyMayContinue)
        val detail = detailFromBoundedRead(read)
        assertEquals("sanitized: invalid project token", detail)
    }

    @Test
    fun utf8BoundaryDoesNotProduceUnboundedOrBrokenPublicDetail() = runTest {
        // 4-byte code point U+1F600, placed so the byte budget cuts inside it.
        val emoji = "\uD83D\uDE00" // UTF-16 surrogate pair for U+1F600; UTF-8 is 4 bytes
        val emojiBytes = emoji.encodeToByteArray()
        assertEquals(4, emojiBytes.size)
        val prefixLen = MAX_ERROR_DETAIL_READ_BYTES - 1
        val body = ByteArray(prefixLen + emojiBytes.size + 16) { index ->
            when {
                index < prefixLen -> 'x'.code.toByte()
                index < prefixLen + emojiBytes.size -> emojiBytes[index - prefixLen]
                else -> 'y'.code.toByte()
            }
        }
        val read = readBoundedErrorPrefix(ByteReadChannel(body))
        assertTrue(read.bodyMayContinue)
        val detail = detailFromBoundedRead(read)
        assertNotNull(detail)
        assertTrue(detail.length <= MAX_ERROR_DETAIL_CHARS, "public detail length ${detail.length}")
        assertTrue(detail.endsWith(ERROR_DETAIL_TRUNCATED_MARKER))
        assertFalse(
            detail.contains("\uFFFD") && detail.length > MAX_ERROR_DETAIL_CHARS,
            "replacement characters must not push detail past the public bound",
        )
    }

    @Test
    fun providerRemoteStatusDetailFromHugeBodyStaysBounded() = runTest {
        val huge = "B".repeat(20_000)
        val config = BlockfrostConfig(projectId = "test-project-id")
        val client = HttpClient(MockEngine) {
            configureBlockfrost(config)
            engine {
                addHandler {
                    respond(
                        huge,
                        HttpStatusCode.Forbidden,
                        headersOf(HttpHeaders.ContentType, "application/json"),
                    )
                }
            }
        }
        val provider = BlockfrostChainQueryProvider(config, client)
        val result = provider.getTip()
        assertTrue(result is KardanoResult.Err)
        val error = result.error
        assertTrue(error is ProviderError.RemoteStatus)
        val detail = error.detail
        assertNotNull(detail)
        assertTrue(detail.length <= MAX_ERROR_DETAIL_CHARS, "public detail length ${detail.length}")
        assertTrue(detail.endsWith(ERROR_DETAIL_TRUNCATED_MARKER))
        assertFalse(detail.contains("test-project-id"))
    }

    @Test
    fun renderedPublicDetailNeverExceedsBudget() {
        val detail = boundPublicDetail("z".repeat(5_000), addMarker = true)
        assertEquals(MAX_ERROR_DETAIL_CHARS, detail.length)
        assertTrue(detail.endsWith(ERROR_DETAIL_TRUNCATED_MARKER))
    }
}
