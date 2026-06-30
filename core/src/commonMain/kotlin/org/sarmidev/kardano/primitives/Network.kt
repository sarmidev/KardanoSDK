package org.sarmidev.kardano.primitives

import org.sarmidev.kardano.KardanoResult

/**
 * A Cardano network, identified by its protocol network id.
 *
 * Cardano addresses and related structures carry a network id in their header. This type
 * represents only the network ids the protocol defines:
 *
 * - [TESTNET] (`0`)
 * - [MAINNET] (`1`)
 *
 * It does not distinguish between specific test networks (for example preview and preprod):
 * those share network id `0`, so the network id alone cannot tell them apart. Do not read
 * any preview/preprod distinction into this type.
 *
 * @property id the protocol network id (`0` for testnet, `1` for mainnet).
 */
public enum class Network(public val id: Int) {

    /** The Cardano test network family, protocol network id `0`. */
    TESTNET(0),

    /** The Cardano main network, protocol network id `1`. */
    MAINNET(1);

    public companion object {

        /**
         * Resolves a [Network] from its protocol network [id].
         *
         * @param id the protocol network id to resolve.
         * @return [KardanoResult.Ok] with the matching [Network] for `0` or `1`, or
         *   [KardanoResult.Err] with [NetworkError.UnsupportedNetworkId] for any other
         *   value. Never throws.
         */
        public fun fromId(id: Int): KardanoResult<Network, NetworkError> = when (id) {
            TESTNET.id -> KardanoResult.Ok(TESTNET)
            MAINNET.id -> KardanoResult.Ok(MAINNET)
            else -> KardanoResult.Err(NetworkError.UnsupportedNetworkId(id))
        }
    }
}

/**
 * A typed error produced when resolving a [Network].
 */
public sealed interface NetworkError {

    /**
     * The requested network [id] is not a network id this SDK recognizes.
     *
     * @property id the unsupported network id that was provided.
     */
    public data class UnsupportedNetworkId(public val id: Int) : NetworkError
}
