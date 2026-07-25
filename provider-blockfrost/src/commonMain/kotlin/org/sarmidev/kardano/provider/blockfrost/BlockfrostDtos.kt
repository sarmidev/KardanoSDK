package org.sarmidev.kardano.provider.blockfrost

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Internal wire models for the Blockfrost JSON responses this provider consumes.
 *
 * These types are deliberately `internal`: they are the Blockfrost-specific response shape and
 * must not leak out of `:provider-blockfrost`. [BlockfrostChainQueryProvider] maps them into
 * the provider-neutral models declared in `:provider`. Fields the SDK does not use are ignored
 * by the tolerant JSON reader ([blockfrostJson]).
 */

/** One entry of the `GET /addresses/{address}/utxos` response array. */
@Serializable
internal data class BlockfrostUtxoDto(
    @SerialName("tx_hash") val txHash: String,
    @SerialName("output_index") val outputIndex: Long,
    val amount: List<BlockfrostAmountDto> = emptyList(),
)

/** One `{unit, quantity}` amount entry; `unit == "lovelace"` for the ADA component. */
@Serializable
internal data class BlockfrostAmountDto(
    val unit: String,
    val quantity: String,
)

/** The subset of `GET /epochs/latest/parameters` the SDK maps to `ProtocolParameters`. */
@Serializable
internal data class BlockfrostEpochParametersDto(
    @SerialName("min_fee_a") val minFeeA: Long,
    @SerialName("min_fee_b") val minFeeB: Long,
    @SerialName("key_deposit") val keyDeposit: String,
    @SerialName("pool_deposit") val poolDeposit: String,
    @SerialName("max_tx_size") val maxTxSize: Long,
    @SerialName("coins_per_utxo_size") val coinsPerUtxoSize: String,
)

/** The subset of `GET /blocks/latest` the SDK maps to `ChainTip`. */
@Serializable
internal data class BlockfrostBlockDto(
    val slot: Long,
    val height: Long,
)

/**
 * Blockfrost's JSON error envelope, returned alongside non-2xx statuses (for example from
 * `POST /tx/submit`). All fields are optional/nullable because not every non-2xx response is
 * this exact shape (some are backend-level HTML/plaintext, not this JSON envelope).
 */
@Serializable
internal data class BlockfrostErrorDto(
    @SerialName("status_code") val statusCode: Int? = null,
    val error: String? = null,
    val message: String? = null,
)
