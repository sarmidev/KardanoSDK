package org.sarmidev.kardano.tx

import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.provider.ProtocolParameters
import org.sarmidev.kardano.provider.Utxo

/**
 * A request to [TransactionBuilder.build] a minimal, single-payment ADA transaction from
 * candidate UTxOs (ADR-0014 §6-7).
 *
 * Unlike [TransactionBodyRequest] (the lower-level, already-fully-decided serialization
 * request), this leaves coin selection, fee estimation, and change to
 * [TransactionBuilder.build]: it only says what to pay and where change should go, not which
 * inputs, what fee, or how much change.
 *
 * @property network the network every address here (and every [candidateInputs] entry's
 *   owning address, implicitly) is expected to belong to. [payment]'s and [changeAddress]'s
 *   network are checked against it and rejected with [TxBuildError.NetworkMismatch] on
 *   mismatch; [TransactionBuilder] never infers or defaults a network.
 * @property candidateInputs the ADA-only UTxOs [TransactionBuilder.build] may spend from,
 *   selected largest-first by [org.sarmidev.kardano.provider.Value.coin] (ADR-0014 §6).
 *   Order does not matter. Must be non-empty ([TxBuildError.NoInputs]).
 * @property payment the single required payment output: the destination address and ADA
 *   amount to send. Rejected if its amount is below the computed minimum-ADA
 *   ([TxBuildError.InvalidOutputAmount]).
 * @property changeAddress the address any leftover ADA is returned to. Ignored entirely when
 *   the selected inputs total exactly [payment]'s amount plus the estimated fee (ADR-0014 §7).
 * @property protocolParameters the fee coefficients, minimum-UTxO cost, and maximum
 *   transaction size to build against.
 * @property ttl the optional `invalid_hereafter` slot, forwarded verbatim to
 *   [TransactionBodyRequest.ttl].
 */
public data class TransactionBuildRequest(
    public val network: Network,
    public val candidateInputs: List<Utxo>,
    public val payment: TransactionOutput,
    public val changeAddress: Address,
    public val protocolParameters: ProtocolParameters,
    public val ttl: Long? = null,
)
