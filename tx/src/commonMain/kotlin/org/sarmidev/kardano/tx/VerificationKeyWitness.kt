package org.sarmidev.kardano.tx

import org.sarmidev.kardano.KardanoResult

/**
 * A Cardano Shelley `vkeywitness`: a 32-byte Ed25519 verification key (`vkey`) paired with the
 * 64-byte signature it produced over a transaction body hash.
 *
 * This is a structural byte container only (ADR-0015 §1/§3): `:tx` never derives, hashes, or
 * signs — the caller (`:wallet`, via `:crypto`'s `Signing`) already computed both [vkeyBytes]
 * and [signatureBytes] before constructing this. Only the byte lengths are validated here; the
 * cryptographic correctness of the signature is not (and cannot be, without a `:crypto`
 * dependency `:tx` deliberately does not have).
 *
 * @see <a href="https://github.com/cardano-foundation/CIPs/tree/master/CIP-1852">CIP-1852</a>
 */
public class VerificationKeyWitness private constructor(vkey: ByteArray, signature: ByteArray) {

    private val vkey: ByteArray = vkey.copyOf()
    private val signature: ByteArray = signature.copyOf()

    /**
     * Returns a defensive copy of the 32-byte verification key.
     *
     * @return a fresh [VKEY_BYTES]-byte copy.
     */
    public fun vkeyBytes(): ByteArray = vkey.copyOf()

    /**
     * Returns a defensive copy of the 64-byte signature.
     *
     * @return a fresh [SIGNATURE_BYTES]-byte copy.
     */
    public fun signatureBytes(): ByteArray = signature.copyOf()

    /** Value equality based on byte content. */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is VerificationKeyWitness) return false
        return vkey.contentEquals(other.vkey) && signature.contentEquals(other.signature)
    }

    /** Hash code derived from byte content. */
    override fun hashCode(): Int = 31 * vkey.contentHashCode() + signature.contentHashCode()

    /** Structural description that renders no key or signature bytes. */
    override fun toString(): String = "VerificationKeyWitness()"

    public companion object {

        /** The exact byte length of a verification key (`vkey`). */
        public const val VKEY_BYTES: Int = 32

        /** The exact byte length of a signature. */
        public const val SIGNATURE_BYTES: Int = 64

        /**
         * Creates a [VerificationKeyWitness], validating the length of both [vkey] and
         * [signature].
         *
         * @param vkey the 32-byte Ed25519 verification key. Copied defensively.
         * @param signature the 64-byte signature [vkey]'s private key produced over a
         *   transaction body hash. Copied defensively.
         * @return [KardanoResult.Ok] with the [VerificationKeyWitness], or
         *   [KardanoResult.Err] with [org.sarmidev.kardano.tx.TxBuildError.InvalidVerificationKeyLength]
         *   or [org.sarmidev.kardano.tx.TxBuildError.InvalidSignatureLength] if either length is
         *   wrong. Never throws.
         */
        public fun of(
            vkey: ByteArray,
            signature: ByteArray,
        ): KardanoResult<VerificationKeyWitness, TxBuildError> {
            if (vkey.size != VKEY_BYTES) {
                return KardanoResult.Err(
                    TxBuildError.InvalidVerificationKeyLength(
                        expectedBytes = VKEY_BYTES,
                        actualBytes = vkey.size,
                    ),
                )
            }
            if (signature.size != SIGNATURE_BYTES) {
                return KardanoResult.Err(
                    TxBuildError.InvalidSignatureLength(
                        expectedBytes = SIGNATURE_BYTES,
                        actualBytes = signature.size,
                    ),
                )
            }
            return KardanoResult.Ok(VerificationKeyWitness(vkey, signature))
        }
    }
}
