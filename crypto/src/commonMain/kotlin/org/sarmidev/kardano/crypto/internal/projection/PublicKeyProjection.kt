package org.sarmidev.kardano.crypto.internal.projection

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.derivation.Bip32Ed25519KeyDerivation
import org.sarmidev.kardano.crypto.derivation.KeyDerivationError

/**
 * Platform-seam Ed25519 public-key projection, module-internal to [Bip32Ed25519KeyDerivation]:
 * `A = [kL] * B` (base-point scalar multiplication, **noclamp**) from an extended private key's
 * left 32-byte scalar.
 *
 * 1.6c-follow-up / 1.6c-follow-up-2 gate results (ADR-0010): unlike [Bip32Ed25519KeyDerivation]'s
 * derivation wrapper (directly callable from `commonMain` on every target), this needs a genuine
 * per-platform seam, because JVM/iOS and Android use two different libsodium builds. JVM and iOS
 * delegate to Ionspin's bindings, whose Android native library is missing
 * `crypto_scalarmult_ed25519_*`/`crypto_core_ed25519_*` entirely (confirmed by
 * `UnsatisfiedLinkError` on real Android runtime and by static symbol inspection, across every
 * published version checked). Android instead delegates to `com.goterl:lazysodium-android`,
 * whose AAR bundles a full libsodium `.so` that does export the symbol on all four ABIs. JVM and
 * Android reproduce the cited `addr_xvk` golden vectors at runtime (Android: real device/emulator
 * execution, API 24, 35, 36). iOS is verified for compile+link only; iOS runtime execution of
 * these vectors remains future work, same posture as the 1.6b/1.6c iOS checkpoints.
 *
 * @param kL the 32-byte left scalar of an extended private key. Not cleared by this function;
 *   the caller owns the lifetime of this array.
 * @return [KardanoResult.Ok] with the 32-byte projected public key, or [KardanoResult.Err] with
 *   [KeyDerivationError.PublicKeyProjectionUnavailable] if projection is not available on this
 *   platform, or another [KeyDerivationError] if the backend fails. Never throws.
 */
internal expect fun projectPublicKey(kL: ByteArray): KardanoResult<ByteArray, KeyDerivationError>
