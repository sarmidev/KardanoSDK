package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult

/**
 * Platform-seam Ed25519 public-key projection, module-internal to [Bip32Ed25519KeyDerivation]:
 * `A = [kL] * B` (base-point scalar multiplication, **noclamp**) from an extended private key's
 * left 32-byte scalar.
 *
 * 1.6c-follow-up gate result (ADR-0010): unlike [Bip32Ed25519KeyDerivation]'s derivation wrapper
 * (directly callable from `commonMain` on every target), this needs a genuine per-platform seam.
 * The verified backend (libsodium's `crypto_scalarmult_ed25519_base_noclamp`) reproduces the
 * cited `addr_xvk` golden vectors on JVM, and iOS's bundled static libsodium exports the same
 * symbol (compile+link verified; iOS runtime execution is future work, same posture as the
 * 1.6b/1.6c iOS checkpoints). Its published Android native library does not export
 * `crypto_scalarmult_ed25519_*`/`crypto_core_ed25519_*` at all (confirmed by
 * `UnsatisfiedLinkError` on real Android runtime and by static symbol inspection, across every
 * published version checked) — the Android `actual` therefore returns
 * [KeyDerivationError.PublicKeyProjectionUnavailable] without attempting the call.
 *
 * @param kL the 32-byte left scalar of an extended private key. Not cleared by this function;
 *   the caller owns the lifetime of this array.
 * @return [KardanoResult.Ok] with the 32-byte projected public key, or [KardanoResult.Err] with
 *   [KeyDerivationError.PublicKeyProjectionUnavailable] if projection is not available on this
 *   platform, or another [KeyDerivationError] if the backend fails. Never throws.
 */
internal expect fun projectPublicKey(kL: ByteArray): KardanoResult<ByteArray, KeyDerivationError>
