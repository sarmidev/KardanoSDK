package org.sarmidev.kardano.provider.blockfrost

import org.sarmidev.kardano.primitives.Network

/**
 * A Blockfrost network target, carrying the Blockfrost API base URL for that network and its
 * mapping to the SDK's [Network].
 *
 * Note that [Network] cannot distinguish preview from preprod (both use network id `0`), so
 * [PREPROD] and [PREVIEW] both map to [Network.TESTNET]. The provider uses this enum to pick
 * the correct Blockfrost host; the resulting [Network] is only the coarse mainnet/testnet
 * distinction the SDK models.
 *
 * @property baseUrl the Blockfrost API base URL for this network, without a trailing slash.
 */
public enum class BlockfrostNetwork(public val baseUrl: String) {

    /** Cardano preprod test network. Maps to [Network.TESTNET]. */
    PREPROD("https://cardano-preprod.blockfrost.io/api/v0"),

    /** Cardano preview test network. Maps to [Network.TESTNET]. */
    PREVIEW("https://cardano-preview.blockfrost.io/api/v0"),

    /** Cardano main network. Maps to [Network.MAINNET]. */
    MAINNET("https://cardano-mainnet.blockfrost.io/api/v0");

    /**
     * Maps this Blockfrost network to the SDK [Network]. [PREPROD] and [PREVIEW] both map to
     * [Network.TESTNET]; [MAINNET] maps to [Network.MAINNET].
     */
    public fun toCoreNetwork(): Network = when (this) {
        PREPROD, PREVIEW -> Network.TESTNET
        MAINNET -> Network.MAINNET
    }
}
