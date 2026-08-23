package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.HttpResponse
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.ByteArrayContent
import io.ktor.http.isSuccess
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.hex.Hex
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.provider.SubmitError
import org.sarmidev.kardano.provider.TxSubmitProvider
import kotlin.coroutines.cancellation.CancellationException

/**
 * A [TxSubmitProvider] backed by the Blockfrost API.
 *
 * It submits the full signed transaction CBOR to the Blockfrost host selected by
 * [BlockfrostConfig.network] and maps the response into the provider-neutral [TxHash] /
 * [SubmitError] declared in `:provider`. The Blockfrost wire shapes never leave this module.
 *
 * All operations are `suspend` and return a [KardanoResult]; they never throw (a thrown
 * exception across the Swift/ObjC boundary would crash iOS consumers), except to propagate
 * coroutine cancellation. Transport failures (including the explicit
 * [io.ktor.client.plugins.HttpTimeout] bounds installed by [configureBlockfrost]),
 * non-success status codes, and response-decode failures are mapped to [SubmitError]
 * variants. There is no automatic retry; a timed-out or failed submit is not sent again.
 *
 * Instances are created with [create]. Tests use the `internal` constructor to inject an
 * [HttpClient] backed by a mock engine, so mapping can be exercised without a real network.
 * There is deliberately no automated live-network test for this provider (unlike the
 * read-only [BlockfrostChainQueryProvider]'s opt-in live test): submitting is a mutating,
 * non-idempotent action that consumes real preprod test UTxOs, so exercising it against a
 * live node is a manual Android checkpoint, not something to run repeatedly and automatically.
 *
 * @property network the SDK network this provider is bound to, derived from
 *   [BlockfrostConfig.network].
 */
public class BlockfrostTxSubmitProvider internal constructor(
    private val config: BlockfrostConfig,
    private val httpClient: HttpClient,
) : TxSubmitProvider {

    override val network: Network = config.network.toCoreNetwork()

    /**
     * Submits [transactionCbor] to `POST {config.network.baseUrl}/tx/submit` with
     * `Content-Type: application/cbor` and the Blockfrost `project_id` header (applied by
     * [configureBlockfrost] on every request from this client).
     *
     * [transactionCbor] is copied defensively before being handed to the HTTP client, and is
     * never mutated or retained beyond this call. An empty [transactionCbor] is rejected with
     * [SubmitError.EmptyTransaction] before any HTTP call is made.
     */
    override suspend fun submit(transactionCbor: ByteArray): KardanoResult<TxHash, SubmitError> {
        if (transactionCbor.isEmpty()) {
            return KardanoResult.Err(SubmitError.EmptyTransaction)
        }
        val body = transactionCbor.copyOf()

        val response = try {
            httpClient.post("${config.network.baseUrl}/tx/submit") {
                setBody(ByteArrayContent(body, ContentType.parse(CBOR_CONTENT_TYPE)))
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            return KardanoResult.Err(SubmitError.Transport(transportFailureMessage(e)))
        }

        if (!response.status.isSuccess()) {
            return KardanoResult.Err(statusError(response))
        }

        val responseText = try {
            response.bodyAsText()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            return KardanoResult.Err(
                SubmitError.Deserialization(e.message ?: "submit response decode failed"),
            )
        }
        return parseAcceptedTxId(responseText)
    }

    /**
     * Parses a successful `POST /tx/submit` response body into a [TxHash].
     *
     * Blockfrost's `200` response is a JSON string: a 64-character hex transaction id wrapped
     * in double quotes (for example `"d1662b24...908"`). Rather than decoding it as JSON via
     * content negotiation (which would depend on the response actually declaring a JSON
     * content type), the surrounding quotes are stripped deliberately here, from the raw text,
     * before hex-decoding. Anything that is not exactly [TxHash.SIZE] bytes of valid hex after
     * that becomes [SubmitError.Deserialization].
     */
    private fun parseAcceptedTxId(responseText: String): KardanoResult<TxHash, SubmitError> {
        val trimmed = responseText.trim()
        val unquoted = if (trimmed.length >= 2 && trimmed.startsWith("\"") && trimmed.endsWith("\"")) {
            trimmed.substring(1, trimmed.length - 1)
        } else {
            trimmed
        }
        val hashBytes = when (val r = Hex.decode(unquoted)) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err ->
                return KardanoResult.Err(
                    SubmitError.Deserialization("invalid tx id hex: ${r.error}"),
                )
        }
        return when (val r = TxHash.of(hashBytes)) {
            is KardanoResult.Ok -> KardanoResult.Ok(r.value)
            is KardanoResult.Err ->
                KardanoResult.Err(
                    SubmitError.Deserialization("invalid tx id length: ${hashBytes.size}"),
                )
        }
    }

    /**
     * Maps a non-success submit [response] to a provider-neutral [SubmitError]. HTTP status
     * codes are translated only here, inside this module: `400` (the node rejected the
     * transaction itself) to [SubmitError.Rejected], `429` to [SubmitError.RateLimited], and
     * any other non-2xx code (for example `403`, `404`, `418`, `425`, `500`) to
     * [SubmitError.RemoteStatus]. When available, [detailFromBlockfrostBody] extracts a
     * human-readable detail from Blockfrost's JSON error envelope or, failing that, the
     * raw response body. It reads only the response body.
     */
    private suspend fun statusError(response: HttpResponse): SubmitError {
        val bodyText = try {
            response.bodyAsText()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            ""
        }
        val detail = detailFromBlockfrostBody(bodyText)
        return when (response.status) {
            HttpStatusCode.BadRequest -> SubmitError.Rejected(
                code = response.status.value,
                detail = detail ?: "transaction rejected",
            )
            HttpStatusCode.TooManyRequests -> SubmitError.RateLimited
            else -> SubmitError.RemoteStatus(code = response.status.value, detail = detail)
        }
    }

    public companion object {

        /** The `Content-Type` Blockfrost expects for `POST /tx/submit` request bodies. */
        private const val CBOR_CONTENT_TYPE: String = "application/cbor"

        /**
         * Creates a [BlockfrostTxSubmitProvider] with the default platform HTTP client
         * (OkHttp on Android, CIO on JVM, Darwin on iOS) configured from [config].
         *
         * @param config the Blockfrost project id and network target.
         * @return a ready-to-use provider bound to [BlockfrostConfig.network].
         */
        public fun create(config: BlockfrostConfig): BlockfrostTxSubmitProvider =
            BlockfrostTxSubmitProvider(config, defaultHttpClient(config))
    }
}
