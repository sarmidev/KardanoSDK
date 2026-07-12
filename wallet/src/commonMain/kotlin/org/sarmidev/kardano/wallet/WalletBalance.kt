package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.primitives.Lovelace

/**
 * A [ReadOnlyWallet]'s ADA balance, summed from the UTxOs a [org.sarmidev.kardano.provider.ChainQueryProvider]
 * query returned for its address.
 *
 * Provider-neutral and ADA-only, matching [org.sarmidev.kardano.provider.Value]'s ADA-only
 * scope for the first MVP (ADR-0005 §1): native (multi-asset) amounts are not represented and
 * are not summed. An address with no UTxOs has [coin] equal to [Lovelace.ZERO] and [utxoCount]
 * equal to `0` — this is a normal successful result
 * ([org.sarmidev.kardano.KardanoResult.Ok]), not an error, mirroring
 * [org.sarmidev.kardano.provider.ChainQueryProvider.getUtxos]'s own "empty is not an error"
 * contract.
 *
 * This is structural only: it does not prove the summed UTxOs are still unspent on-chain at
 * the moment of use, and it makes no claim about the address's ownership or spendability.
 *
 * @property coin the total ADA amount, in lovelace, summed across the queried UTxOs.
 * @property utxoCount the number of UTxOs the sum was computed from.
 */
public data class WalletBalance(
    public val coin: Lovelace,
    public val utxoCount: Int,
)
