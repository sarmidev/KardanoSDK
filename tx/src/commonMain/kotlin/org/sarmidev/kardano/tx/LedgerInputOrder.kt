package org.sarmidev.kardano.tx

import org.sarmidev.kardano.primitives.UtxoRef

/**
 * The ledger `(transaction_id, index)` ordering (ADR-0014 §4): `transaction_id` bytes compared
 * unsigned-bytewise ascending, then `index` numeric ascending.
 *
 * Shared by [TransactionBodySerializer] (which sorts the encoded input array into this order)
 * and [TransactionBuilder] (which uses the same order as its largest-first coin-selection
 * tie-breaker, per ADR-0014 §6), so the two never disagree on what "ledger order" means.
 */
internal object LedgerInputOrder : Comparator<UtxoRef> {

    override fun compare(a: UtxoRef, b: UtxoRef): Int {
        val hashComparison = compareBytesUnsigned(a.txHash.toByteArray(), b.txHash.toByteArray())
        return if (hashComparison != 0) hashComparison else a.outputIndex.compareTo(b.outputIndex)
    }

    /** Unsigned bytewise lexicographic comparison, shorter array first when one is a prefix. */
    private fun compareBytesUnsigned(a: ByteArray, b: ByteArray): Int {
        val shared = minOf(a.size, b.size)
        for (i in 0 until shared) {
            val ai = a[i].toInt() and 0xFF
            val bi = b[i].toInt() and 0xFF
            if (ai != bi) return ai - bi
        }
        return a.size - b.size
    }
}
