package org.sarmidev.kardano.provider

import org.sarmidev.kardano.primitives.UtxoRef

/**
 * An unspent transaction output returned by a [ChainQueryProvider]: a structural output
 * reference ([ref]) plus the [value] it holds.
 *
 * This is a read model returned by a provider. It does not prove the output is currently
 * unspent, spendable, or owned by any address; those are chain-state and wallet concerns
 * outside the provider read boundary.
 *
 * @property ref the structural reference (transaction hash + output index) to the output.
 * @property value the value held by the output (ADA-only in the first MVP; see [Value]).
 */
public data class Utxo(
    public val ref: UtxoRef,
    public val value: Value,
)
