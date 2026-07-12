package org.sarmidev.kardano.crypto

import com.ionspin.kotlin.crypto.LibsodiumInitializer
import com.ionspin.kotlin.crypto.ed25519.Ed25519LowLevel
import kotlinx.coroutines.runBlocking
import org.sarmidev.kardano.KardanoResult

/**
 * iOS actual (1.6c-follow-up gate result, ADR-0010): delegates to libsodium's
 * `crypto_scalarmult_ed25519_base_noclamp` via the Ionspin bindings' statically-linked native
 * build. No handwritten Ed25519 math. Compile+link verified; on-device runtime execution is
 * recorded as future work, same posture as the 1.6b/1.6c iOS checkpoints.
 *
 * `kL.toUByteArray()` and the native call's `UByteArray` result are both copies distinct from
 * `kL` and from the `ByteArray` this function returns; both are wiped here (ADR-0004 §5 /
 * ADR-0009 §7) rather than left for the runtime, matching the caller's own
 * `leftScalar.fill(0)` on `kL` itself ([Bip32Ed25519KeyDerivation.publicKey]).
 *
 * Duplicated in `iosSimulatorArm64Main` (this project has no shared `iosMain` source set — see
 * `crypto/build.gradle.kts`'s per-target `pbkdf2raw` cinterop for the same pattern).
 */
@OptIn(ExperimentalUnsignedTypes::class)
internal actual fun projectPublicKey(kL: ByteArray): KardanoResult<ByteArray, KeyDerivationError> {
    if (!LibsodiumInitializer.isInitialized()) {
        runBlocking { LibsodiumInitializer.initialize() }
    }
    val scalar = kL.toUByteArray()
    return try {
        val projected = Ed25519LowLevel.scalarMultiplicationBaseNoClamp(scalar)
        val result = projected.toByteArray()
        projected.fill(0u)
        KardanoResult.Ok(result)
    } catch (t: Throwable) {
        KardanoResult.Err(KeyDerivationError.DerivationFailed("public-key projection failed"))
    } finally {
        scalar.fill(0u)
    }
}
