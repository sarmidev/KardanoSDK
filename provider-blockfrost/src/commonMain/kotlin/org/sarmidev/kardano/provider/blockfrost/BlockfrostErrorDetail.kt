package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.statement.HttpResponse
import io.ktor.client.statement.bodyAsChannel
import io.ktor.utils.io.ByteReadChannel
import io.ktor.utils.io.cancel
import io.ktor.utils.io.readRemaining
import kotlinx.io.readByteArray
import kotlinx.serialization.decodeFromString

/** Public error-detail character budget (envelope fields and raw prefix). */
internal const val MAX_ERROR_DETAIL_CHARS: Int = 500

/**
 * Marker appended when the public detail is a prefix, not the complete body or field.
 * The rendered string stays within [MAX_ERROR_DETAIL_CHARS] (prefix + marker).
 */
internal const val ERROR_DETAIL_TRUNCATED_MARKER: String = " [truncated]"

/**
 * UTF-8 byte budget for the error-body prefix: enough for [MAX_ERROR_DETAIL_CHARS] + 1
 * code points at the 4-byte UTF-8 worst case, so the reader can tell whether the body
 * continues past the public limit without materializing the rest.
 */
internal const val MAX_ERROR_DETAIL_READ_BYTES: Int = (MAX_ERROR_DETAIL_CHARS + 1) * 4

internal class BoundedErrorRead(
    val text: String,
    val bodyMayContinue: Boolean,
)

/**
 * Reads at most [MAX_ERROR_DETAIL_READ_BYTES] from [channel] and does not pull the
 * remainder. If the budget is filled, the channel is cancelled so a large body is not
 * materialized. [kotlin.coroutines.cancellation.CancellationException] propagates.
 */
internal suspend fun readBoundedErrorPrefix(channel: ByteReadChannel): BoundedErrorRead {
    val packet = channel.readRemaining(MAX_ERROR_DETAIL_READ_BYTES.toLong())
    val bytes = packet.readByteArray()
    val bodyMayContinue = bytes.size >= MAX_ERROR_DETAIL_READ_BYTES
    if (bodyMayContinue) {
        channel.cancel()
    }
    return BoundedErrorRead(
        text = bytes.decodeToString(),
        bodyMayContinue = bodyMayContinue,
    )
}

/**
 * Maps a bounded body prefix to public detail. A filled byte budget is treated as an
 * incomplete body: the JSON envelope is not parsed (it may be cut mid-object) and a
 * factual truncated prefix is returned. A complete small body may be parsed; `message`
 * and `error` are then limited to [MAX_ERROR_DETAIL_CHARS].
 *
 * Returns `null` only when the prefix is blank. Never reads request headers or
 * configuration.
 */
internal fun detailFromBoundedRead(read: BoundedErrorRead): String? {
    val raw = read.text
    if (raw.isBlank()) return null
    if (read.bodyMayContinue) {
        return boundPublicDetail(raw, addMarker = true)
    }
    val dto = try {
        blockfrostJson.decodeFromString<BlockfrostErrorDto>(raw)
    } catch (_: Exception) {
        null
    }
    val fromEnvelope = dto?.message?.takeIf { it.isNotBlank() }
        ?: dto?.error?.takeIf { it.isNotBlank() }
    if (fromEnvelope != null) {
        return if (fromEnvelope.length > MAX_ERROR_DETAIL_CHARS) {
            boundPublicDetail(fromEnvelope, addMarker = true)
        } else {
            fromEnvelope
        }
    }
    val trimmed = raw.trim()
    return if (trimmed.length > MAX_ERROR_DETAIL_CHARS) {
        boundPublicDetail(trimmed, addMarker = true)
    } else {
        trimmed
    }
}

/**
 * Reads a bounded prefix of [response]'s body channel and maps it to public detail.
 * Does not call [io.ktor.client.statement.bodyAsText] and does not read request metadata.
 */
internal suspend fun detailFromBlockfrostResponse(response: HttpResponse): String? =
    detailFromBoundedRead(readBoundedErrorPrefix(response.bodyAsChannel()))

internal fun boundPublicDetail(text: String, addMarker: Boolean): String {
    val trimmed = text.trim()
    if (!addMarker) return trimmed.take(MAX_ERROR_DETAIL_CHARS)
    val contentBudget = MAX_ERROR_DETAIL_CHARS - ERROR_DETAIL_TRUNCATED_MARKER.length
    return trimmed.take(contentBudget) + ERROR_DETAIL_TRUNCATED_MARKER
}
