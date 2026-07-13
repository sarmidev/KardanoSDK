package org.sarmidev.kardano.crypto.signing

/**
 * A typed, backend-neutral error returned by [Signing.sign].
 *
 * These variants describe failure categories without naming or leaking the shape of any
 * specific cryptographic backend, and never carry key bytes, signature bytes, or message
 * bytes (mirroring [org.sarmidev.kardano.crypto.derivation.KeyDerivationError]).
 */
public sealed interface SigningError {

    /**
     * The message passed to [Signing.sign] was not exactly [Signing.BODY_HASH_BYTES] bytes.
     *
     * [Signing.sign] signs a Cardano transaction body hash, which is always exactly 32 bytes
     * (a Blake2b-256 digest) — never an arbitrary-length message.
     *
     * @property expectedBytes the exact number of bytes expected ([Signing.BODY_HASH_BYTES]).
     * @property actualBytes the number of bytes the caller actually supplied.
     */
    public data class InvalidBodyHashLength(
        public val expectedBytes: Int,
        public val actualBytes: Int,
    ) : SigningError

    /**
     * The [org.sarmidev.kardano.crypto.derivation.ExtendedPrivateKey] material passed to the
     * signing backend had an unexpected byte length.
     *
     * As of Block 1.10b, every [org.sarmidev.kardano.crypto.derivation.ExtendedPrivateKey] is
     * already length-validated on construction, so this is not reachable through the public
     * [Signing] API today; it is declared for backend-reported key-material shape errors
     * (mirroring [org.sarmidev.kardano.crypto.derivation.KeyDerivationError.InvalidKeyMaterial]).
     *
     * @property expectedBytes the exact number of bytes expected.
     * @property actualBytes the number of bytes actually supplied to the backend.
     */
    public data class InvalidKeyMaterial(
        public val expectedBytes: Int,
        public val actualBytes: Int,
    ) : SigningError

    /**
     * The underlying signing backend failed.
     *
     * @property message a short, neutral description of the failure category. Never a backend
     *   type, key bytes, signature bytes, or message bytes.
     */
    public data class BackendFailed(public val message: String) : SigningError

    /**
     * Extended Ed25519-BIP32 signing is not available on the current platform.
     *
     * As of the Block 1.10b-pre gate result (ADR-0016 §9i), every current target (JVM, iOS,
     * Android) has a verified signing backend (`:crypto-signing-backend`), so no target
     * currently returns this. It remains declared for a platform without one added in the
     * future (mirroring
     * [org.sarmidev.kardano.crypto.derivation.KeyDerivationError.PublicKeyProjectionUnavailable]).
     */
    public data object SigningUnavailable : SigningError
}
