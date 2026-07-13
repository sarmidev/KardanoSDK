package org.sarmidev.kardano.tx

import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.primitives.Lovelace

/**
 * A single Cardano transaction output: an [address] to pay and the ADA [amount] it carries.
 *
 * ADA-only for the Block 1.9 MVP (ADR-0014 §2): no multi-asset value, no datum, no script
 * reference. [TransactionBodySerializer] encodes this using the legacy/Alonzo array form
 * `[address, coin]` (ADR-0014 §5), not the post-Alonzo map form.
 *
 * @property address the destination address (payment or change). Its raw bytes
 *   ([Address.toByteArray], header included) are encoded directly, with no datum hash.
 * @property amount the ADA amount the output carries.
 * @see <a href="https://github.com/IntersectMBO/cardano-ledger">Cardano ledger CDDL,
 *   `legacy_transaction_output`</a>
 */
public data class TransactionOutput(
    public val address: Address,
    public val amount: Lovelace,
)
