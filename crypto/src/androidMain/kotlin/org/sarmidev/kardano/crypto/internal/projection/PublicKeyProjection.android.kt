package org.sarmidev.kardano.crypto.internal.projection

import com.goterl.lazysodium.SodiumAndroid
import com.sun.jna.Library
import com.sun.jna.Native
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.derivation.ExtendedPublicKey
import org.sarmidev.kardano.crypto.derivation.KeyDerivationError

/**
 * Android actual (1.6c-follow-up-2 gate result, ADR-0010): delegates to libsodium's
 * `crypto_scalarmult_ed25519_base_noclamp` via `com.goterl:lazysodium-android`'s bundled native
 * library. No handwritten Ed25519 math.
 *
 * Unlike the minimal libsodium build Ionspin ships for Android (the JVM/iOS backend, see
 * `PublicKeyProjection.jvm.kt`), lazysodium-android's AAR bundles a full libsodium `.so` that
 * exports `crypto_scalarmult_ed25519_base_noclamp` on all four ABIs — verified by `nm -D` symbol
 * inspection and by an on-device probe reproducing the cited `addr_xvk` goldens on API 24, 35,
 * and 36 runtimes (1.6c-follow-up-2 gate). Its own `Sodium`/`SodiumAndroid` JNA interfaces do not
 * declare that function (checked by disassembling the library's `classes.jar`), so [MinimalSodium]
 * declares only the one native symbol this module needs and loads it directly via JNA.
 */
internal actual fun projectPublicKey(kL: ByteArray): KardanoResult<ByteArray, KeyDerivationError> {
    val sodium = try {
        ensureSodiumLoaded()
    } catch (t: Throwable) {
        return KardanoResult.Err(KeyDerivationError.DerivationFailed("public-key projection failed"))
    }

    val q = ByteArray(ExtendedPublicKey.PUBLIC_KEY_BYTES)
    val rc = try {
        sodium.crypto_scalarmult_ed25519_base_noclamp(q, kL)
    } catch (t: Throwable) {
        q.fill(0)
        return KardanoResult.Err(KeyDerivationError.DerivationFailed("public-key projection failed"))
    }
    if (rc != 0) {
        q.fill(0)
        return KardanoResult.Err(KeyDerivationError.DerivationFailed("public-key projection failed"))
    }
    return KardanoResult.Ok(q)
}

/** The one native symbol this module needs, declared directly since lazysodium's own JNA. */
private interface MinimalSodium : Library {
    fun crypto_scalarmult_ed25519_base_noclamp(q: ByteArray, n: ByteArray): Int
}

private val sodiumInitLock = Any()
private var cachedSodium: MinimalSodium? = null

/**
 * Loads [MinimalSodium] once, after triggering lazysodium-android's normal native-load path for
 * the `sodium` library name via [SodiumAndroid].
 */
private fun ensureSodiumLoaded(): MinimalSodium {
    cachedSodium?.let { return it }
    synchronized(sodiumInitLock) {
        cachedSodium?.let { return it }
        SodiumAndroid()
        val loaded = Native.load("sodium", MinimalSodium::class.java)
        cachedSodium = loaded
        return loaded
    }
}
