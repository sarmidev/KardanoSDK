package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult

/**
 * An opaque handle over a CIP-3 (Icarus) 96-byte root extended key.
 *
 * Instances are created exclusively through [fromMnemonic], which derives the key from a
 * validated [Mnemonic] and an optional passphrase. Per ADR-0009 §2, the 96-byte result is the
 * root extended key directly: a 64-byte extended private key followed by a 32-byte chain code.
 * There is no separate "root from seed" step, and this SDK does not expose the plain BIP-39
 * seed function (Cardano's Icarus path does not use it).
 *
 * There is no public accessor for the key bytes (ADR-0009 §7): this block does not need one,
 * and private-key byte access is deferred to whichever later block explicitly designs it.
 *
 * @see <a href="https://github.com/cardano-foundation/CIPs/blob/master/CIP-0003/Icarus.md">CIP-3 (Icarus)</a>
 */
public class IcarusMasterKey private constructor(rootKey: ByteArray) {

    private var rootKey: ByteArray = rootKey.copyOf()

    /**
     * Returns a defensive copy of the 96-byte root key.
     *
     * Module-internal test-only accessor: there is no public byte accessor for the root key
     * (ADR-0009 §7). Used only by this module's known-answer tests to compare against the cited
     * CIP-3 vectors.
     *
     * @return a fresh copy of the root-key bytes.
     */
    internal fun rootKeyBytesForTesting(): ByteArray = rootKey.copyOf()

    /**
     * Best-effort wipe of the retained root-key bytes.
     *
     * This zeroes this instance's backing array, but gives no guarantee about compiler,
     * runtime, or garbage-collector behavior (ADR-0004 §5).
     */
    public fun clear() {
        rootKey.fill(0)
    }

    /** Structural description that renders no key bytes. */
    override fun toString(): String = "IcarusMasterKey()"

    public companion object {

        /** PBKDF2 iteration count fixed by CIP-3 for the Icarus master-key derivation. */
        private const val PBKDF2_ITERATIONS: Int = 4096

        /** PBKDF2 output length in bytes fixed by CIP-3: a 64-byte key plus a 32-byte chain code. */
        private const val ROOT_KEY_BYTES: Int = 96

        /** Number of leading bytes of the PBKDF2 output the CIP-3 bit tweaks apply to. */
        private const val TWEAK_REGION_BYTES: Int = 64

        /**
         * Derives the CIP-3 (Icarus) root extended key from [mnemonic] and an optional
         * [passphrase].
         *
         * Computes PBKDF2-HMAC-SHA-512(password = [passphrase] bytes, salt = the mnemonic's
         * BIP-39 entropy bytes, iterations = 4096, output = 96 bytes), then applies the CIP-3
         * bit tweaks to the first 64 bytes of the result
         * (`data[0] &= 0b1111_1000; data[31] &= 0b0001_1111; data[31] |= 0b0100_0000`). The
         * PBKDF2-HMAC-SHA-512 step is delegated to a platform backend (never hand-written); the
         * bit tweaks are SDK-owned data handling per ADR-0009 §3.1.
         *
         * @param mnemonic a validated [Mnemonic] (see [Mnemonic.parse]).
         * @param passphrase the Icarus passphrase bytes. Defaults to empty (no passphrase). Not
         *   modified, and not decoded to or from a `String` on any target.
         * @return [KardanoResult.Ok] with the derived [IcarusMasterKey], or [KardanoResult.Err]
         *   with a [KeyDerivationError] if the underlying PBKDF2 backend fails. Never throws.
         */
        public fun fromMnemonic(
            mnemonic: Mnemonic,
            passphrase: ByteArray = ByteArray(0),
        ): KardanoResult<IcarusMasterKey, KeyDerivationError> {
            val entropy = mnemonic.entropyBytes()
            // Defensive copy so the derivation backend never receives (and cannot retain a
            // reference to) the caller's own passphrase array; wiped in `finally` on every path
            // (success, backend failure) without affecting the caller's array.
            val password = passphrase.copyOf()
            val derived: ByteArray
            try {
                derived = pbkdf2HmacSha512(
                    password = password,
                    salt = entropy,
                    iterations = PBKDF2_ITERATIONS,
                    outputBytes = ROOT_KEY_BYTES,
                )
            } catch (t: Throwable) {
                entropy.fill(0)
                return KardanoResult.Err(KeyDerivationError.DerivationFailed("PBKDF2 derivation failed"))
            } finally {
                password.fill(0)
            }
            entropy.fill(0)

            if (derived.size != ROOT_KEY_BYTES) {
                derived.fill(0)
                return KardanoResult.Err(
                    KeyDerivationError.InvalidKeyMaterial(
                        expectedBytes = ROOT_KEY_BYTES,
                        actualBytes = derived.size,
                    ),
                )
            }

            tweakBits(derived)
            val masterKey = IcarusMasterKey(derived)
            derived.fill(0)
            return KardanoResult.Ok(masterKey)
        }

        /**
         * Applies the CIP-3 bit tweaks to the first [TWEAK_REGION_BYTES] bytes of [data],
         * in place: clears the low 3 bits of byte 0, clears the top 3 bits of byte 31, and sets
         * bit 6 of byte 31. Spec-defined bit masking around a delegated PBKDF2 primitive
         * (ADR-0009 §3.1), not a cryptographic algorithm in itself.
         */
        private fun tweakBits(data: ByteArray) {
            data[0] = (data[0].toInt() and 0b1111_1000).toByte()
            data[31] = (data[31].toInt() and 0b0001_1111).toByte()
            data[31] = (data[31].toInt() or 0b0100_0000).toByte()
        }
    }
}
