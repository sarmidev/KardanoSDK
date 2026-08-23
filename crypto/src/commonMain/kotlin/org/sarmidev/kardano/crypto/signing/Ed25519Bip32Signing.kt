package org.sarmidev.kardano.crypto.signing

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.derivation.ExtendedPrivateKey
import org.sarmidev.kardano.crypto.signing.backend.internal.SigningBackendException
import org.sarmidev.kardano.crypto.signing.backend.internal.sign as backendSign

/**
 * The default [Signing] implementation, backed by the adopted `:crypto-signing-backend` module
 * (ADR-0016 §9i), which wraps the reference `ed25519-bip32` Rust crate's `XPrv::sign` — Cardano
 * extended Ed25519-BIP32 signing, not plain RFC 8032 seed-based Ed25519.
 *
 * This adapter is `internal`: the backend module's generated wrapper types never appear in the
 * public API. It is directly callable from `commonMain` on every target (JVM, Android, iOS) —
 * no additional `expect`/`actual` seam needed here, mirroring how [Signing.default] over the
 * `bip32-ed25519:1.8.8` derivation wrapper needs none either (ADR-0009 §4).
 */
@OptIn(ExperimentalKardanoRawSigning::class)
internal class Ed25519Bip32Signing : Signing {

    override fun sign(
        bodyHash: ByteArray,
        key: ExtendedPrivateKey,
    ): KardanoResult<ByteArray, SigningError> {
        if (bodyHash.size != Signing.BODY_HASH_BYTES) {
            return KardanoResult.Err(
                SigningError.InvalidBodyHashLength(
                    expectedBytes = Signing.BODY_HASH_BYTES,
                    actualBytes = bodyHash.size,
                ),
            )
        }

        val xprv = key.extendedPrivateKeyBytesForSigning()
        try {
            val signature = backendSign(xprv, bodyHash.copyOf())
            return if (signature.size != Signing.SIGNATURE_BYTES) {
                // Defensive: the backend contract guarantees a 64-byte signature (verified by
                // the ADR-0016 §9i KAT); this is not reachable through normal operation.
                signature.fill(0)
                KardanoResult.Err(SigningError.BackendFailed("unexpected signature length"))
            } else {
                KardanoResult.Ok(signature)
            }
        } catch (t: Throwable) {
            return KardanoResult.Err(mapThrowable(t, xprv.size))
        } finally {
            xprv.fill(0)
        }
    }

    internal companion object {

        /**
         * Maps a [Throwable] from the backend to a typed, backend-neutral [SigningError].
         *
         * Factored out from [sign] so the mapping itself is directly unit-testable with
         * synthetic exceptions, without invoking the native backend (mirroring
         * `Bip32Ed25519KeyDerivation.mapThrowable`).
         *
         * @param t the caught throwable. Never rethrown; no key, signature, or message bytes
         *   are retained from it.
         * @param xprvBytes the length of the `xprv` bytes that were passed to the backend, used
         *   only to report [SigningError.InvalidKeyMaterial]'s `actualBytes`.
         * @return [SigningError.InvalidKeyMaterial] for
         *   [SigningBackendException.InvalidExtendedPrivateKey], or [SigningError.BackendFailed]
         *   with a short, backend-neutral category for anything else.
         */
        internal fun mapThrowable(t: Throwable, xprvBytes: Int): SigningError = when (t) {
            is SigningBackendException.InvalidExtendedPrivateKey ->
                SigningError.InvalidKeyMaterial(expectedBytes = 96, actualBytes = xprvBytes)
            else -> SigningError.BackendFailed("signing failed")
        }
    }
}
