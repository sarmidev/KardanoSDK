package org.sarmidev.kardano.crypto

/**
 * A typed, backend-neutral error returned by a key-derivation operation such as
 * [IcarusMasterKey.fromMnemonic].
 *
 * These variants describe failure categories without naming or leaking the shape of any
 * specific cryptographic backend, and never carry key bytes, entropy, seed, passphrase bytes,
 * or mnemonic words (ADR-0009 §6).
 */
public sealed interface KeyDerivationError {

    /**
     * Key material had an unexpected byte length.
     *
     * @property expectedBytes the exact number of bytes expected.
     * @property actualBytes the number of bytes actually produced or supplied.
     */
    public data class InvalidKeyMaterial(
        public val expectedBytes: Int,
        public val actualBytes: Int,
    ) : KeyDerivationError

    /**
     * A derivation index was outside the permitted range.
     *
     * @property value the out-of-range index value.
     */
    public data class IndexOutOfRange(public val value: Long) : KeyDerivationError

    /**
     * Public-key derivation was requested for an index that requires private-key (prime)
     * derivation.
     */
    public data object SoftDerivationRequired : KeyDerivationError

    /**
     * The underlying derivation backend failed.
     *
     * @property message a short, neutral description of the failure category (for example
     *   `"PBKDF2 derivation failed"`). Never a backend type, key bytes, entropy, passphrase
     *   bytes, or mnemonic words.
     */
    public data class DerivationFailed(public val message: String) : KeyDerivationError
}
