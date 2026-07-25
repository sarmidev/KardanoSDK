package org.sarmidev.kardano.provider

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef

/**
 * An in-memory [ChainQueryProvider] backed entirely by hardcoded data.
 *
 * This is a sample/test double, not a real provider. **All data it returns is fake and for
 * testing only** — the UTxOs are not real on-chain outputs, they are not committed chain
 * fixtures, and they involve no real funds, no network, and no secrets. It exists so that
 * wallet and Playground work can proceed against a stable, offline read boundary before the
 * real Blockfrost preprod provider is introduced (Block 1.3b).
 *
 * By default it is bound to [Network.TESTNET] (used for the Phase 1 preprod checkpoint; note
 * that [Network.TESTNET] covers all test networks and does not by itself identify preprod).
 * The default seed data recognizes two documented addresses:
 *
 * - [SEED_ADDRESS_WITH_UTXOS] returns a small list of fake UTxOs.
 * - [SEED_ADDRESS_EMPTY] (and any other valid address) returns an empty list.
 *
 * @param network the network this provider is bound to; defaults to [Network.TESTNET].
 * @param utxosByAddress the seed map of address to fake UTxOs; defaults to [defaultSeed].
 * @param protocolParameters the fake protocol parameters to return; defaults to
 *   [DEFAULT_PROTOCOL_PARAMETERS].
 * @param tip the fake chain tip to return; defaults to [DEFAULT_TIP].
 */
public class InMemoryChainQueryProvider(
    override val network: Network = Network.TESTNET,
    private val utxosByAddress: Map<Address, List<Utxo>> = defaultSeed(),
    private val protocolParameters: ProtocolParameters = DEFAULT_PROTOCOL_PARAMETERS,
    private val tip: ChainTip = DEFAULT_TIP,
) : ChainQueryProvider {

    /**
     * Returns the seeded fake UTxOs for [address], or an empty list if the address is not
     * seeded. Fails with [ProviderError.NetworkMismatch] if the address network differs from
     * [network].
     */
    override suspend fun getUtxos(address: Address): KardanoResult<List<Utxo>, ProviderError> {
        if (address.network != network) {
            return KardanoResult.Err(
                ProviderError.NetworkMismatch(expected = network, actual = address.network),
            )
        }
        return KardanoResult.Ok(utxosByAddress[address] ?: emptyList())
    }

    /** Returns the fake [protocolParameters]. */
    override suspend fun getProtocolParameters():
        KardanoResult<ProtocolParameters, ProviderError> =
        KardanoResult.Ok(protocolParameters)

    /** Returns the fake chain [tip]. */
    override suspend fun getTip(): KardanoResult<ChainTip, ProviderError> =
        KardanoResult.Ok(tip)

    public companion object {

        /**
         * A valid CIP-19 testnet enterprise address (public test vector) that the default
         * seed maps to a non-empty list of fake UTxOs. Use it to exercise the "has UTxOs"
         * path in the Playground checkpoint.
         */
        public const val SEED_ADDRESS_WITH_UTXOS: String =
            "addr_test1vz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerspjrlsz"

        /**
         * A valid CIP-19 testnet base address (public test vector) that the default seed maps
         * to an empty list. Use it to exercise the "no UTxOs" empty state in the Playground
         * checkpoint.
         */
        public const val SEED_ADDRESS_EMPTY: String =
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"

        /**
         * Fake, illustrative protocol parameters for offline testing. The values resemble
         * commonly published Cardano parameters but are fixed test data and are not read from
         * any live network.
         */
        public val DEFAULT_PROTOCOL_PARAMETERS: ProtocolParameters = ProtocolParameters(
            minFeeCoefficient = 44L,
            minFeeConstant = 155_381L,
            keyDeposit = 2_000_000L,
            poolDeposit = 500_000_000L,
            maxTxSize = 16_384L,
            coinsPerUtxoByte = 4_310L,
        )

        /** A fake, fixed chain tip for offline testing. */
        public val DEFAULT_TIP: ChainTip = ChainTip(slot = 50_000_000L, blockHeight = 2_000_000L)

        /**
         * Builds the default seed map: [SEED_ADDRESS_WITH_UTXOS] maps to two fake UTxOs and
         * [SEED_ADDRESS_EMPTY] maps to an empty list. Both seed strings are valid CIP-19
         * testnet vectors; if either fails to parse it is simply omitted, so this never
         * throws.
         */
        public fun defaultSeed(): Map<Address, List<Utxo>> {
            val seed = LinkedHashMap<Address, List<Utxo>>()
            Address.parse(SEED_ADDRESS_WITH_UTXOS).getOrNull()?.let { address ->
                seed[address] = listOf(
                    fakeUtxo(seedByte = 0x11, outputIndex = 0L, lovelace = 5_000_000L),
                    fakeUtxo(seedByte = 0x22, outputIndex = 1L, lovelace = 12_500_000L),
                )
            }
            Address.parse(SEED_ADDRESS_EMPTY).getOrNull()?.let { address ->
                seed[address] = emptyList()
            }
            return seed
        }

        /**
         * Builds one fake [Utxo] from hardcoded, known-valid inputs: a 32-byte transaction
         * hash filled with [seedByte], the given [outputIndex], and an ADA [lovelace] amount.
         * The inputs are constants chosen to be in range, so the underlying factories always
         * succeed; a failure would be a programming error in this test double rather than
         * runtime input handling.
         */
        private fun fakeUtxo(seedByte: Int, outputIndex: Long, lovelace: Long): Utxo {
            val hashBytes = ByteArray(TxHash.SIZE) { seedByte.toByte() }
            val txHash = requireNotNull(TxHash.of(hashBytes).getOrNull()) {
                "seed TxHash bytes are hardcoded to a valid length"
            }
            val ref = requireNotNull(UtxoRef.of(txHash, outputIndex).getOrNull()) {
                "seed output index is hardcoded non-negative"
            }
            val coin = requireNotNull(Lovelace.of(lovelace).getOrNull()) {
                "seed lovelace amount is hardcoded non-negative"
            }
            return Utxo(ref, Value(coin))
        }
    }
}
