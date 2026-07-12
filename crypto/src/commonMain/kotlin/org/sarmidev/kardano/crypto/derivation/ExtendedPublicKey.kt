package org.sarmidev.kardano.crypto.derivation

import org.sarmidev.kardano.KardanoResult

/**
 * An opaque handle over a derived Ed25519-BIP32 extended public key: a 32-byte public key
 * followed by a 32-byte chain code, matching the CIP-5 `xvk` (extended verification key) layout.
 *
 * Instances are created exclusively through [KeyDerivation.publicKey]. Unlike
 * [ExtendedPrivateKey], a public key is not secret, so [publicKeyBytes] is a public accessor —
 * this does not widen ADR-0009 §7's "no public private-key byte accessor" rule, which applies
 * only to private-key material.
 *
 * 1.6c-follow-up-2 gate result (ADR-0010): projection is verified on JVM, iOS, and Android
 * (real-runtime execution on API 24, 35, and 36).
 */
public class ExtendedPublicKey private constructor(publicKey: ByteArray, chainCode: ByteArray) {

    private val publicKey: ByteArray = publicKey.copyOf()
    private val chainCode: ByteArray = chainCode.copyOf()

    /**
     * Returns a defensive copy of the 32-byte public key.
     *
     * @return a fresh 32-byte copy of the public key.
     */
    public fun publicKeyBytes(): ByteArray = publicKey.copyOf()

    /**
     * Returns a defensive copy of the 32-byte public key followed by the 32-byte chain code
     * (64 bytes total), matching the CIP-5 `xvk` layout.
     *
     * Module-internal test-only accessor, mirroring [ExtendedPrivateKey.xskBytesForTesting].
     * Used only by this module's known-answer tests to compare against the cited CIP-1852
     * golden `addr_xvk` vectors.
     *
     * @return a fresh 64-byte copy of public key || chain code.
     */
    internal fun xvkBytesForTesting(): ByteArray = publicKey.copyOf() + chainCode.copyOf()

    /**
     * Best-effort wipe of the retained key bytes.
     *
     * This zeroes this instance's backing arrays, but gives no guarantee about compiler,
     * runtime, or garbage-collector behavior (ADR-0004 §5).
     */
    public fun clear() {
        publicKey.fill(0)
        chainCode.fill(0)
    }

    /** Structural description that renders no key bytes. */
    override fun toString(): String = "ExtendedPublicKey()"

    public companion object {

        /** The byte length of the public key component. */
        internal const val PUBLIC_KEY_BYTES: Int = 32

        /** The byte length of the chain code component. */
        internal const val CHAIN_CODE_BYTES: Int = 32

        /**
         * Creates an [ExtendedPublicKey], validating the length of both components.
         *
         * Internal to the module: the only caller is the [KeyDerivation] backend adapter,
         * which passes it bytes a backend produced.
         *
         * @param publicKey the 32-byte public key. Copied defensively.
         * @param chainCode the 32-byte chain code. Copied defensively.
         * @return [KardanoResult.Ok] with the [ExtendedPublicKey], or [KardanoResult.Err] with
         *   [KeyDerivationError.InvalidKeyMaterial] if either length is wrong. Never throws.
         */
        internal fun of(
            publicKey: ByteArray,
            chainCode: ByteArray,
        ): KardanoResult<ExtendedPublicKey, KeyDerivationError> {
            if (publicKey.size != PUBLIC_KEY_BYTES) {
                return KardanoResult.Err(
                    KeyDerivationError.InvalidKeyMaterial(
                        expectedBytes = PUBLIC_KEY_BYTES,
                        actualBytes = publicKey.size,
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
            return KardanoResult.Ok(ExtendedPublicKey(publicKey, chainCode))
        }
    }
}
