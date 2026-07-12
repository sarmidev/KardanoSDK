package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult

/**
 * Android actual (1.6c-follow-up gate result, ADR-0010): public-key projection is not available
 * on Android. The verified backend's published Android native library does not export
 * `crypto_scalarmult_ed25519_*`/`crypto_core_ed25519_*` at all — confirmed by
 * `UnsatisfiedLinkError` on real Android emulator runtime and by static symbol inspection of the
 * shipped `.so`, across every published version checked. This actual deliberately never calls
 * that backend (there is no `libsodium` dependency in `androidMain`, see `crypto/build.gradle.kts`):
 * it returns the typed error directly, so [KeyDerivation.publicKey] degrades gracefully on
 * Android instead of crashing. [KeyDerivation.derivePrivate] is unaffected and works on Android.
 */
internal actual fun projectPublicKey(kL: ByteArray): KardanoResult<ByteArray, KeyDerivationError> =
    KardanoResult.Err(KeyDerivationError.PublicKeyProjectionUnavailable)
