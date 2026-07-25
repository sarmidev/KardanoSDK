package org.sarmidev.kardano.tx

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.encoding.cbor.CborValue

/**
 * Assembles a full, signed Cardano `transaction` from an existing [TransactionDraft] and an
 * already-computed [TransactionWitnessSet] (ADR-0015 §1/§3, Block 1.10b).
 *
 * This object is crypto-free, per ADR-0015 §1: it never hashes, signs, or verifies anything —
 * [assemble] only encodes bytes and [VerificationKeyWitness] values the caller already
 * produced (typically `:wallet`, via `:crypto`'s `Signing`) into the CDDL shape
 * `[transaction_body, transaction_witness_set, true, null]`. It never rebuilds or alters
 * [draft]'s body or fee (ADR-0015 §3): [TransactionDraft.bodyCbor] is embedded verbatim as
 * field `0` of the assembled array.
 */
public object TransactionAssembler {

    /** The `transaction_witness_set` map key for the Shelley `vkeywitness` set. */
    private const val FIELD_VKEY_WITNESSES: Long = 0

    /**
     * Assembles the full signed `transaction` for [draft] and [witnessSet].
     *
     * @param draft the unsigned draft to sign. Its [TransactionDraft.bodyCbor] is embedded
     *   unchanged as field `0` of the assembled `transaction`; this function does not rebuild
     *   or re-derive the body or fee.
     * @param witnessSet the already-computed witness set to embed as field `1`.
     * @return [KardanoResult.Ok] with the assembled [SignedTransaction], or
     *   [KardanoResult.Err] with [TxBuildError.Serialization] if encoding [draft]'s body bytes
     *   back into a [CborValue] or encoding the assembled `transaction` fails. Never throws.
     */
    public fun assemble(
        draft: TransactionDraft,
        witnessSet: TransactionWitnessSet,
    ): KardanoResult<SignedTransaction, TxBuildError> {
        val bodyValue = when (val result = Cbor.decode(draft.bodyCbor())) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> return KardanoResult.Err(TxBuildError.Serialization(result.error))
        }

        val transaction = CborValue.CborArray(
            listOf(
                bodyValue,
                encodeWitnessSet(witnessSet),
                CborValue.CborBool(true),
                CborValue.CborNull,
            ),
        )

        val cborBytes = when (val result = Cbor.encode(transaction)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> return KardanoResult.Err(TxBuildError.Serialization(result.error))
        }

        return KardanoResult.Ok(SignedTransaction(witnessSet, cborBytes))
    }

    /**
     * Builds the `transaction_witness_set` CBOR map `{ 0 : [ [vkey, signature], ... ] }` for
     * [witnessSet]. Building this tree cannot itself fail (encoding it can, if the witness
     * count somehow exceeded `:core`'s named collection limit — [assemble] surfaces that
     * through [Cbor.encode]'s result).
     */
    private fun encodeWitnessSet(witnessSet: TransactionWitnessSet): CborValue.CborMap {
        val witnesses = witnessSet.verificationKeyWitnesses.map { witness ->
            CborValue.CborArray(
                listOf(
                    CborValue.CborByteString(witness.vkeyBytes()),
                    CborValue.CborByteString(witness.signatureBytes()),
                ),
            )
        }
        return CborValue.CborMap(
            listOf(
                CborValue.CborEntry(
                    CborValue.CborUnsigned(FIELD_VKEY_WITNESSES),
                    CborValue.CborArray(witnesses),
                ),
            ),
        )
    }
}
