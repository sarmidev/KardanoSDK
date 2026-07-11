package org.sarmidev.kardano.crypto

import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.convert
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.usePinned
import org.sarmidev.kardano.crypto.pbkdf2raw.kardano_ccpbkdf2_hmac_sha512

/**
 * iOS `actual`: Apple CommonCrypto `CCKeyDerivationPBKDF` (PBKDF2, HMAC-SHA-512), reached through
 * the `kardano_ccpbkdf2_hmac_sha512` interop shim.
 *
 * Uses the custom `pbkdf2raw` cinterop binding (see `src/nativeInterop/cinterop/pbkdf2raw.def`)
 * rather than the shipped `platform.CoreCrypto` binding or a plain `noStringConversion` rebind of
 * `CCKeyDerivationPBKDF` itself: the C header declares `password` as `const char *`, which
 * Kotlin/Native's default cinterop heuristic maps to a Kotlin `String` (per the Kotlin/Native
 * C-interop documentation) — lossy for a raw, possibly non-UTF-8 passphrase (embedded NUL bytes
 * truncate at the interop boundary). A direct `noStringConversion` rebind of `CCKeyDerivationPBKDF`
 * via `modules = CommonCrypto` was tried first but produced a klib with zero declarations in this
 * build environment (confirmed with `klib dump-metadata`). The `.def`'s inline C shim,
 * `kardano_ccpbkdf2_hmac_sha512`, is a signature adapter only: it declares `password` as
 * `const uint8_t *` and casts it to `const char *` solely at the call boundary to
 * `CCKeyDerivationPBKDF`, which performs the actual derivation — no PBKDF2 logic is implemented in
 * the shim or here. [password] and [salt] are pinned and passed as raw pointers, matching the
 * shared `expect` contract and the JVM/Android `actual`s (no target decodes the passphrase to or
 * from a `String`).
 *
 * Duplicated verbatim in `iosArm64Main` and `iosSimulatorArm64Main` (per-target cinterop klibs
 * are not visible from the shared `iosMain` source set without enabling the incubating
 * `kotlin.mpp.enableCInteropCommonization` Gradle property) — the same approach this module
 * already uses to share the BouncyCastle actual between `jvmMain` and `androidMain`.
 */
@OptIn(ExperimentalForeignApi::class)
internal actual fun pbkdf2HmacSha512(
    password: ByteArray,
    salt: ByteArray,
    iterations: Int,
    outputBytes: Int,
): ByteArray {
    val derivedKey = ByteArray(outputBytes)
    // CCKeyDerivationPBKDF requires a non-null password pointer even when passwordLen is 0 (an
    // empty passphrase, as in CIP-3 Icarus vector 1); an empty ByteArray has no element to
    // pin/address, so a 1-byte scratch buffer supplies a valid pointer. passwordLen (not the
    // buffer's actual size) tells CommonCrypto how many bytes to read, so the derivation is
    // unaffected by the scratch buffer's extra byte.
    val passwordBuffer = if (password.isEmpty()) ByteArray(1) else password

    val status = passwordBuffer.usePinned { passwordPinned ->
        salt.usePinned { saltPinned ->
            derivedKey.usePinned { derivedKeyPinned ->
                kardano_ccpbkdf2_hmac_sha512(
                    password = passwordPinned.addressOf(0).reinterpret(),
                    password_len = password.size.convert(),
                    salt = saltPinned.addressOf(0).reinterpret(),
                    salt_len = salt.size.convert(),
                    rounds = iterations.convert(),
                    derived_key = derivedKeyPinned.addressOf(0).reinterpret(),
                    derived_key_len = derivedKey.size.convert(),
                )
            }
        }
    }
    // CCKeyDerivationPBKDF (delegated to by the shim) returns 0 (kCCSuccess) on success and a
    // negative status otherwise.
    check(status == 0) { "PBKDF2 derivation failed" }
    return derivedKey
}
