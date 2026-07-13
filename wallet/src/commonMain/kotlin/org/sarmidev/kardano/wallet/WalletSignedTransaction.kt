package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.tx.SignedTransaction

/**
 * The result of [ReadOnlyWallet.signTransaction]: the `:tx` [signedTransaction] artifact paired
 * with the [transactionId] `:wallet` computed while signing it (ADR-0015 §3).
 *
 * [transactionId] is `Blake2b-256(TransactionDraft.bodyCbor())` — the same body bytes embedded
 * verbatim as field `0` of [signedTransaction], so [transactionId] is exactly the hash of the
 * body that was signed, not a recomputation from [signedTransaction]'s encoded bytes (`:tx`
 * stays crypto-free and never hashes on its own).
 *
 * This is a **signed, unsubmitted** structural artifact only (ADR-0015 §3/§7): submitting it is
 * out of scope for Block 1.10 (Block 1.11, ADR-0006).
 *
 * @property signedTransaction the full signed `transaction` CBOR bytes and witness set.
 * @property transactionId the 32-byte transaction id / signed body hash.
 */
public class WalletSignedTransaction internal constructor(
    public val signedTransaction: SignedTransaction,
    public val transactionId: TxHash,
) {

    /** The number of Shelley key witnesses [signedTransaction] carries. */
    public val witnessCount: Int get() = signedTransaction.witnessCount

    /** Structural description that renders no CBOR or hash bytes. */
    override fun toString(): String =
        "WalletSignedTransaction(transactionId=$transactionId, witnessCount=$witnessCount)"
}
