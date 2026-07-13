package org.sarmidev.kardano.tx

import org.sarmidev.kardano.KardanoResult

/**
 * A Cardano `transaction_witness_set` restricted to Shelley key witnesses: the CDDL shape
 * `{ 0 : [ [ vkey /* 32 bytes */, signature /* 64 bytes */ ], ... ] }`.
 *
 * Only field `0` (`vkeywitness` set) is represented, matching the single-key ADA-only MVP
 * scope Block 1.10b supports (ADR-0015 §2): no native or Plutus scripts (field `1`/`3`/`6`), no
 * bootstrap/Byron witnesses (field `2`), and no Plutus data/redeemers (field `4`/`5`). Adding
 * any of those requires its own later, explicit block/ADR.
 *
 * @property verificationKeyWitnesses the Shelley key witnesses this set carries, in the order
 *   supplied to [of].
 */
public class TransactionWitnessSet private constructor(
    verificationKeyWitnesses: List<VerificationKeyWitness>,
) {

    public val verificationKeyWitnesses: List<VerificationKeyWitness> =
        verificationKeyWitnesses.toList()

    /** Structural description that renders no witness bytes. */
    override fun toString(): String =
        "TransactionWitnessSet(verificationKeyWitnesses=${verificationKeyWitnesses.size})"

    public companion object {

        /**
         * Creates a [TransactionWitnessSet] from [verificationKeyWitnesses].
         *
         * @param verificationKeyWitnesses the Shelley key witnesses to carry, in order. Must be
         *   non-empty: this MVP's flow always signs with at least the one payment key
         *   (ADR-0015 §2), so a witness set with none is rejected rather than representing an
         *   ambiguous "signed with nothing" state.
         * @return [KardanoResult.Ok] with the [TransactionWitnessSet], or [KardanoResult.Err]
         *   with [TxBuildError.EmptyWitnessSet] if [verificationKeyWitnesses] is empty. Never
         *   throws.
         */
        public fun of(
            verificationKeyWitnesses: List<VerificationKeyWitness>,
        ): KardanoResult<TransactionWitnessSet, TxBuildError> {
            if (verificationKeyWitnesses.isEmpty()) {
                return KardanoResult.Err(TxBuildError.EmptyWitnessSet)
            }
            return KardanoResult.Ok(TransactionWitnessSet(verificationKeyWitnesses))
        }
    }
}
