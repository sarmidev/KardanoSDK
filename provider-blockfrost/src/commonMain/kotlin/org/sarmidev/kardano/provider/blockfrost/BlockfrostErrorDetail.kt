package org.sarmidev.kardano.provider.blockfrost

import kotlinx.serialization.decodeFromString

/** Upper bound on how much of a raw (non-JSON-envelope) error body is kept as detail. */
internal const val MAX_ERROR_DETAIL_CHARS: Int = 500

/**
 * Extracts a short, human-readable detail from a Blockfrost error [bodyText]: the JSON
 * envelope's `message` field, falling back to `error`, falling back to the raw (truncated)
 * body if the envelope cannot be parsed. Returns `null` only when [bodyText] is blank.
 *
 * Reads only the response body. It must never be passed request headers, the `project_id`,
 * or any other request configuration.
 */
internal fun detailFromBlockfrostBody(bodyText: String): String? {
    if (bodyText.isBlank()) return null
    val dto = try {
        blockfrostJson.decodeFromString<BlockfrostErrorDto>(bodyText)
    } catch (_: Exception) {
        null
    }
    val fromEnvelope = dto?.message?.takeIf { it.isNotBlank() }
        ?: dto?.error?.takeIf { it.isNotBlank() }
    return fromEnvelope ?: bodyText.trim().take(MAX_ERROR_DETAIL_CHARS)
}
