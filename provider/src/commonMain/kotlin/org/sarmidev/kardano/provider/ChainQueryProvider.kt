package org.sarmidev.kardano.provider

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.primitives.Network

/**
 * A read-only Cardano chain query boundary.
 *
 * This interface defines the minimal read surface the Phase 1 MVP needs before wallet and
 * transaction work: unspent outputs for an address, protocol parameters for future
 * fee/build logic, and an optional chain-tip health signal. It is intentionally minimal and
 * provider-neutral so its shape is not locked around any specific backend's response format.
 *
 * Transaction submission is deliberately **not** part of this interface. ADR-0006 refines
 * ADR-0005 by splitting the read-only query boundary from a future `TxSubmitProvider`, which
 * is introduced in Block 1.11 once local signing exists and a submit-result model is
 * meaningful.
 *
 * All operations are `suspend` and return a [KardanoResult]; they do not throw. Returning
 * failures as [KardanoResult] rather than throwing keeps the API usable across the
 * Swift/ObjC interop boundary, where a thrown exception would crash iOS consumers.
 *
 * A provider is bound to a single [network] at construction. For the Phase 1 preprod
 * checkpoint the provider is bound to [Network.TESTNET]; note that [Network.TESTNET] covers
 * all Cardano test networks and does not by itself identify preprod versus preview.
 */
public interface ChainQueryProvider {

    /**
     * The network this provider is bound to. Queries for a resource on a different network
     * fail with [ProviderError.NetworkMismatch].
     */
    public val network: Network

    /**
     * Returns the unspent outputs held at [address].
     *
     * An address that exists but holds no unspent outputs returns [KardanoResult.Ok] with an
     * empty list (an empty result is not an error). The returned list is bounded; how a
     * concrete implementation handles backend pagination is an internal detail and is not
     * reflected in this API. If a concrete implementation hits its accumulation cap while
     * more items remain, it returns [ProviderError.ResultTruncated] rather than a partial
     * success list.
     *
     * @param address the address to query. Its network must match [network].
     * @return [KardanoResult.Ok] with the (possibly empty) list of [Utxo], or
     *   [KardanoResult.Err] with a [ProviderError] (including
     *   [ProviderError.NetworkMismatch] if the address network differs from [network], or
     *   [ProviderError.ResultTruncated] if pagination hit the implementation cap).
     *   Never throws.
     */
    public suspend fun getUtxos(address: Address): KardanoResult<List<Utxo>, ProviderError>

    /**
     * Returns the current protocol parameters needed for future fee/build logic.
     *
     * @return [KardanoResult.Ok] with the [ProtocolParameters], or [KardanoResult.Err] with a
     *   [ProviderError]. Never throws.
     */
    public suspend fun getProtocolParameters(): KardanoResult<ProtocolParameters, ProviderError>

    /**
     * Returns the current chain tip as a coarse liveness/health signal.
     *
     * @return [KardanoResult.Ok] with the [ChainTip], or [KardanoResult.Err] with a
     *   [ProviderError]. Never throws.
     */
    public suspend fun getTip(): KardanoResult<ChainTip, ProviderError>
}
