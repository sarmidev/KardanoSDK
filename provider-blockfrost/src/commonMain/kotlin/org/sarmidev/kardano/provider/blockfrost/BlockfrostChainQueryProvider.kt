package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.get
import io.ktor.client.request.parameter
import io.ktor.http.HttpStatusCode
import io.ktor.http.isSuccess
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.encoding.hex.Hex
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.ChainTip
import org.sarmidev.kardano.provider.ProtocolParameters
import org.sarmidev.kardano.provider.ProviderError
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.provider.Value
import kotlin.coroutines.cancellation.CancellationException

/**
 * A read-only [ChainQueryProvider] backed by the Blockfrost API.
 *
 * It queries the Blockfrost host selected by [BlockfrostConfig.network] and maps the
 * Blockfrost JSON responses into the provider-neutral models declared in `:provider`. The
 * Blockfrost wire shapes never leave this module: callers only ever see [Utxo],
 * [ProtocolParameters], [ChainTip], and [ProviderError].
 *
 * All operations are `suspend` and return a [KardanoResult]; they never throw (a thrown
 * exception across the Swift/ObjC boundary would crash iOS consumers). Transport failures,
 * non-success status codes, and decode failures are mapped to [ProviderError] variants.
 * Transaction submission is not part of this provider (ADR-0006 defers submit to Block 1.11).
 *
 * Scope limits for the first MVP:
 * - Values are ADA-only: only the `lovelace` component is summed into [Value.coin]. Native-asset
 *   quantities, policy ids, and asset names are never represented — but (Block 1.11d) their mere
 *   *presence* is no longer silently dropped: any `amount` entry whose `unit` is not `lovelace`
 *   sets [Value.hasNativeAssets] to `true`, so a caller (for example `:tx`'s
 *   `TransactionBuilder`) can honestly reject a UTxO it cannot fully represent.
 * - `getUtxos` treats a Blockfrost `404` (an address that never appeared on-chain) as an
 *   empty UTxO list, not an error. The other endpoints keep `404` as [ProviderError.NotFound].
 * - UTxO pagination is capped at [MAX_PAGES] pages of [PAGE_COUNT] entries.
 *
 * Instances are created with [create]. Tests use the `internal` constructor to inject an
 * [HttpClient] backed by a mock engine, so mapping can be exercised without a real network.
 *
 * @property network the SDK network this provider is bound to, derived from
 *   [BlockfrostConfig.network]. A query for a resource on a different network fails with
 *   [ProviderError.NetworkMismatch].
 */
public class BlockfrostChainQueryProvider internal constructor(
    private val config: BlockfrostConfig,
    private val httpClient: HttpClient,
) : ChainQueryProvider {

    override val network: Network = config.network.toCoreNetwork()

    override suspend fun getUtxos(address: Address): KardanoResult<List<Utxo>, ProviderError> {
        if (address.network != network) {
            return KardanoResult.Err(
                ProviderError.NetworkMismatch(expected = network, actual = address.network),
            )
        }

        val accumulated = mutableListOf<Utxo>()
        var page = 1
        while (page <= MAX_PAGES) {
            val response = try {
                httpClient.get("${config.network.baseUrl}/addresses/${address.bech32}/utxos") {
                    parameter("page", page)
                    parameter("count", PAGE_COUNT)
                    parameter("order", "asc")
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                return KardanoResult.Err(ProviderError.Transport(e.message ?: "request failed"))
            }

            // A 404 here means the address has never been used on-chain, which is an empty
            // result rather than an error. This relaxation is scoped to getUtxos only.
            if (response.status == HttpStatusCode.NotFound) {
                return KardanoResult.Ok(accumulated)
            }
            if (!response.status.isSuccess()) {
                return KardanoResult.Err(statusError(response.status))
            }

            val dtos = try {
                response.body<List<BlockfrostUtxoDto>>()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                return KardanoResult.Err(
                    ProviderError.Deserialization(e.message ?: "utxo response decode failed"),
                )
            }

            for (dto in dtos) {
                when (val mapped = mapUtxo(dto)) {
                    is KardanoResult.Ok -> accumulated.add(mapped.value)
                    is KardanoResult.Err -> return mapped
                }
            }

            if (dtos.size < PAGE_COUNT) break
            page++
        }
        return KardanoResult.Ok(accumulated)
    }

    override suspend fun getProtocolParameters():
        KardanoResult<ProtocolParameters, ProviderError> {
        val dto = when (val r = getJson<BlockfrostEpochParametersDto>("/epochs/latest/parameters")) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err -> return r
        }
        val keyDeposit = dto.keyDeposit.toLongOrNull()
            ?: return KardanoResult.Err(
                ProviderError.Deserialization("invalid key_deposit: ${dto.keyDeposit}"),
            )
        val poolDeposit = dto.poolDeposit.toLongOrNull()
            ?: return KardanoResult.Err(
                ProviderError.Deserialization("invalid pool_deposit: ${dto.poolDeposit}"),
            )
        val coinsPerUtxoByte = dto.coinsPerUtxoSize.toLongOrNull()
            ?: return KardanoResult.Err(
                ProviderError.Deserialization("invalid coins_per_utxo_size: ${dto.coinsPerUtxoSize}"),
            )
        return KardanoResult.Ok(
            ProtocolParameters(
                minFeeCoefficient = dto.minFeeA,
                minFeeConstant = dto.minFeeB,
                keyDeposit = keyDeposit,
                poolDeposit = poolDeposit,
                maxTxSize = dto.maxTxSize,
                coinsPerUtxoByte = coinsPerUtxoByte,
            ),
        )
    }

    override suspend fun getTip(): KardanoResult<ChainTip, ProviderError> {
        val dto = when (val r = getJson<BlockfrostBlockDto>("/blocks/latest")) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err -> return r
        }
        return KardanoResult.Ok(ChainTip(slot = dto.slot, blockHeight = dto.height))
    }

    /**
     * Fetches [path] (relative to the configured base URL) and decodes the JSON body to [T].
     * Maps transport exceptions to [ProviderError.Transport], non-success status codes via
     * [statusError], and decode failures to [ProviderError.Deserialization]. Never throws
     * except to propagate coroutine cancellation.
     */
    private suspend inline fun <reified T> getJson(path: String): KardanoResult<T, ProviderError> {
        val response = try {
            httpClient.get("${config.network.baseUrl}$path")
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            return KardanoResult.Err(ProviderError.Transport(e.message ?: "request failed"))
        }
        if (!response.status.isSuccess()) {
            return KardanoResult.Err(statusError(response.status))
        }
        return try {
            KardanoResult.Ok(response.body<T>())
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            KardanoResult.Err(ProviderError.Deserialization(e.message ?: "response decode failed"))
        }
    }

    /**
     * Maps a Blockfrost UTxO entry to the neutral [Utxo], summing only the `lovelace`
     * component into [Value.coin]. Any other `amount` entry (`unit != "lovelace"`) is a native
     * asset: its quantity/policy id/asset name are still not represented, but its mere
     * presence sets [Value.hasNativeAssets] to `true` (Block 1.11d) — this mapping no longer
     * silently drops that information. Any value that a `:core` factory rejects (bad hex,
     * wrong hash length, negative index, out-of-range lovelace) becomes a
     * [ProviderError.Deserialization] rather than a thrown exception.
     */
    private fun mapUtxo(dto: BlockfrostUtxoDto): KardanoResult<Utxo, ProviderError> {
        val hashBytes = when (val r = Hex.decode(dto.txHash)) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err ->
                return KardanoResult.Err(
                    ProviderError.Deserialization("invalid tx_hash hex: ${dto.txHash}"),
                )
        }
        val txHash = when (val r = TxHash.of(hashBytes)) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err ->
                return KardanoResult.Err(
                    ProviderError.Deserialization("invalid tx_hash length: ${hashBytes.size}"),
                )
        }
        val ref = when (val r = UtxoRef.of(txHash, dto.outputIndex)) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err ->
                return KardanoResult.Err(
                    ProviderError.Deserialization("invalid output_index: ${dto.outputIndex}"),
                )
        }

        var total = 0L
        var hasNativeAssets = false
        for (amount in dto.amount) {
            if (amount.unit != LOVELACE_UNIT) {
                hasNativeAssets = true
                continue
            }
            val quantity = amount.quantity.toLongOrNull()
                ?: return KardanoResult.Err(
                    ProviderError.Deserialization("invalid lovelace quantity: ${amount.quantity}"),
                )
            if (quantity < 0L || total > Long.MAX_VALUE - quantity) {
                return KardanoResult.Err(
                    ProviderError.Deserialization("lovelace amount out of range"),
                )
            }
            total += quantity
        }

        val coin = when (val r = Lovelace.of(total)) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err ->
                return KardanoResult.Err(
                    ProviderError.Deserialization("invalid lovelace total: $total"),
                )
        }
        return KardanoResult.Ok(Utxo(ref, Value(coin, hasNativeAssets = hasNativeAssets)))
    }

    /**
     * Maps a non-success HTTP status to a provider-neutral [ProviderError]. HTTP status codes
     * are translated to [ProviderError] only here, inside this module: `429` to
     * [ProviderError.RateLimited], `404` to [ProviderError.NotFound], and any other non-2xx
     * code to [ProviderError.RemoteStatus].
     */
    private fun statusError(status: HttpStatusCode): ProviderError = when (status) {
        HttpStatusCode.TooManyRequests -> ProviderError.RateLimited
        HttpStatusCode.NotFound -> ProviderError.NotFound
        else -> ProviderError.RemoteStatus(status.value)
    }

    public companion object {

        /** The Blockfrost amount `unit` value for the ADA (lovelace) component. */
        private const val LOVELACE_UNIT: String = "lovelace"

        /** Entries requested per UTxO page (Blockfrost's maximum page size). */
        private const val PAGE_COUNT: Int = 100

        /** Upper bound on UTxO pages fetched, so a query never loops unbounded. */
        private const val MAX_PAGES: Int = 100

        /**
         * Creates a [BlockfrostChainQueryProvider] with the default platform HTTP client
         * (OkHttp on Android, CIO on JVM, Darwin on iOS) configured from [config].
         *
         * @param config the Blockfrost project id and network target.
         * @return a ready-to-use provider bound to [BlockfrostConfig.network].
         */
        public fun create(config: BlockfrostConfig): BlockfrostChainQueryProvider =
            BlockfrostChainQueryProvider(config, defaultHttpClient(config))
    }
}
