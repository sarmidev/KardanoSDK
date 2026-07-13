package org.sarmidev.kardano.crypto.signing.backend

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith
import org.sarmidev.kardano.crypto.signing.backend.internal.deriveXpub
import org.sarmidev.kardano.crypto.signing.backend.internal.sign
import org.sarmidev.kardano.crypto.signing.backend.internal.verify
import kotlin.test.assertContentEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Block 1.10b backend adoption — Android real-runtime KAT (ADR-0016 §7d/§9f) against the real,
 * permanent `:crypto-signing-backend` module.
 *
 * Runs on a real Android runtime (emulator/physical device), not just the host JVM, exercising the
 * pre-generated `src/androidMain/kotlin/.../internal/kardano_ed25519_bip32_signing.{common,android}.kt`
 * UniFFI/JNA bindings against the `.so`s cross-compiled into `src/androidMain/jniLibs/` — i.e.
 * through the packaged wrapper.
 *
 * Vector source: `ed25519-bip32` crate 0.4.2, `src/tests.rs`, `xprv_sign` / `verify_signature`
 * (`D1_H0`), cited by CIP-3 and pinned in ADR-0016 §3. Copied verbatim, not invented.
 */
@RunWith(AndroidJUnit4::class)
class SigningBackendAndroidKatTest {
    private fun hexToBytes(hex: String): ByteArray =
        ByteArray(hex.length / 2) { i -> hex.substring(i * 2, i * 2 + 2).toInt(16).toByte() }

    private val extendedScalar =
        "60d399da83ef80d8d4f8d223239efdc2b8fef387e1b5219137ffb4e8fbdea15adc9366b7d003af37c11396de9a83734e30e05e851efa32745c9cd7b42712c890"
    private val chainCode =
        "608763770eddf77248ab652984b21b849760d1da74a6f5bd633ce41adceef07a"
    private val message = "Hello World".toByteArray(Charsets.US_ASCII)
    private val expectedSignature =
        "90194d57cde4fdadd01eb7cf161780c277e129fc7135b97779a3268837e4cd2e9444b9bb91c0e84d23bba870df3c4bda91a110ef735638fa7a34ea2046d4be04"
    private val xprv get() = hexToBytes(extendedScalar + chainCode)

    @Test
    fun reproducesAdr0016D1H0PrimaryKat_onDeviceRuntime() {
        assertTrue(xprv.size == 96)

        val signature = sign(xprv, message)

        assertContentEquals(hexToBytes(expectedSignature), signature, "D1_H0_SIGNATURE mismatch")
    }

    @Test
    fun signThenVerify_selfConsistencyUsingTheDerivedXpub_onDeviceRuntime() {
        val signature = sign(xprv, message)
        val xpub = deriveXpub(xprv)

        assertTrue(verify(xpub, message, signature), "signature must verify against the derived xpub")
    }

    @Test
    fun verify_rejectsATamperedSignature_onDeviceRuntime() {
        val signature = sign(xprv, message)
        signature[0] = (signature[0].toInt() xor 0xFF).toByte()
        val xpub = deriveXpub(xprv)

        assertFalse(verify(xpub, message, signature))
    }

    @Test
    fun sign_rejectsWrongLengthExtendedPrivateKey_onDeviceRuntime() {
        val badXprv = ByteArray(10)

        var threw = false
        try {
            sign(badXprv, message)
        } catch (_: Exception) {
            threw = true
        }
        assertTrue(threw, "expected sign() to reject a 10-byte xprv")
    }
}
