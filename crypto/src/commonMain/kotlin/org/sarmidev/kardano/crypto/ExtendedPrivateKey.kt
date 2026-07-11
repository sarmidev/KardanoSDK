package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult

/**
 * An opaque handle over a derived Ed25519-BIP32 extended private key: a 64-byte extended
 * private key (xsk) followed by a 32-byte chain code, in the same 96-byte layout as
 * [IcarusMasterKey].
 *
 * Instances are created exclusively through [KeyDerivation.derivePrivate]. There is no public
 * accessor for the key bytes (ADR-0009 §7): this block does not project this key to its public
 * counterpart or use it for anything beyond structural handling, and private-key byte access is
 * deferred to whichever later block explicitly designs it (Block 1.10 for signing).
 */
public class ExtendedPrivateKey private constructor(xsk: ByteArray, chainCode: ByteArray) {

    private val xsk: ByteArray = xsk.copyOf()
    private val chainCode: ByteArray = chainCode.copyOf()

    /**
     * Returns a defensive copy of the 64-byte extended private key followed by the 32-byte
     * chain code (96 bytes total).
     *
     * Module-internal test-only accessor: there is no public byte accessor for this key
     * (ADR-0009 §7). Used only by this module's known-answer tests to compare against the cited
     * CIP-1852 golden vectors.
     *
     * @return a fresh 96-byte copy of xsk || chain code.
     */
    internal fun xskBytesForTesting(): ByteArray = xsk.copyOf() + chainCode.copyOf()

    /**
     * Best-effort wipe of the retained key bytes.
     *
     * This zeroes this instance's backing arrays, but gives no guarantee about compiler,
     * runtime, or garbage-collector behavior (ADR-0004 §5).
     */
    public fun clear() {
        xsk.fill(0)
        chainCode.fill(0)
    }

    /** Structural description that renders no key bytes. */
    override fun toString(): String = "ExtendedPrivateKey()"

    public companion object {

        /** The byte length of the extended private key component. */
        internal const val XSK_BYTES: Int = 64

        /** The byte length of the chain code component. */
        internal const val CHAIN_CODE_BYTES: Int = 32

        /**
         * Creates an [ExtendedPrivateKey], validating the length of both components.
         *
         * Internal to the module: the only caller is the [KeyDerivation] backend adapter,
         * which passes it bytes a backend produced.
         *
         * @param xsk the 64-byte extended private key. Copied defensively.
         * @param chainCode the 32-byte chain code. Copied defensively.
         * @return [KardanoResult.Ok] with the [ExtendedPrivateKey], or [KardanoResult.Err] with
         *   [KeyDerivationError.InvalidKeyMaterial] if either length is wrong. Never throws.
         */
        internal fun of(
            xsk: ByteArray,
            chainCode: ByteArray,
        ): KardanoResult<ExtendedPrivateKey, KeyDerivationError> {
            if (xsk.size != XSK_BYTES) {
                return KardanoResult.Err(
                    KeyDerivationError.InvalidKeyMaterial(
                        expectedBytes = XSK_BYTES,
                        actualBytes = xsk.size,
                    ),
                )
            }
            if (chainCode.size != CHAIN_CODE_BYTES) {
                return KardanoResult.Err(
                    KeyDerivationError.InvalidKeyMaterial(
                        expectedBytes = CHAIN_CODE_BYTES,
                        actualBytes = chainCode.size,
                    ),
                )
            }
            return KardanoResult.Ok(ExtendedPrivateKey(xsk, chainCode))
        }
    }
}
