package org.sarmidev.kardano.tx

import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.UtxoRef

/**
 * An already fully specified request to serialize an unsigned Cardano `transaction_body`
 * (ADR-0014 §2).
 *
 * This is the lower-level request shape: [inputs], [outputs], [fee], and [ttl] are already
 * decided by the caller. It intentionally does **not** perform coin selection or fee
 * computation from a wallet's candidate UTxOs and
 * [org.sarmidev.kardano.provider.ProtocolParameters] — callers that want the SDK's coin
 * selection, fee estimation, and change handling should use [TransactionBuilder.build] with a
 * [TransactionBuildRequest] instead. [TransactionBodySerializer.serialize] only orders,
 * validates, and encodes what is supplied here.
 *
 * @property network the network every output address is expected to belong to; a mismatch is
 *   rejected with [TxBuildError.NetworkMismatch] rather than silently accepted.
 * @property inputs the transaction inputs to spend. Order does not matter: they are re-sorted
 *   into the ledger `(transaction_id, index)` order (ADR-0014 §4). Duplicate
 *   `(transaction_id, index)` pairs are rejected.
 * @property outputs the transaction outputs, in the order they should appear in the body (for
 *   example payment then change); each is encoded in the legacy `[address, coin]` form
 *   (ADR-0014 §5).
 * @property fee the transaction fee to encode. This request does not compute it; the caller
 *   supplies an already-decided value (for example a fee estimated by [TransactionBuilder.build],
 *   or a fixed value in a test).
 * @property ttl the optional `invalid_hereafter` slot (body field `3`). Included in the body
 *   only when non-null (ADR-0014 §2); a negative value is rejected with
 *   [TxBuildError.Serialization] (an unsigned CBOR field cannot hold it).
 */
public data class TransactionBodyRequest(
    public val network: Network,
    public val inputs: List<UtxoRef>,
    public val outputs: List<TransactionOutput>,
    public val fee: Lovelace,
    public val ttl: Long? = null,
)
