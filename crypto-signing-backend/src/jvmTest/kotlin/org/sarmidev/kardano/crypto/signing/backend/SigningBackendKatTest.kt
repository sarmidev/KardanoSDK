package org.sarmidev.kardano.crypto.signing.backend

import org.sarmidev.kardano.crypto.signing.backend.internal.deriveXpub
import org.sarmidev.kardano.crypto.signing.backend.internal.sign
import org.sarmidev.kardano.crypto.signing.backend.internal.verify
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Block 1.10b backend adoption — JVM KAT (ADR-0016 §9f) against the real, permanent
 * `:crypto-signing-backend` module (not the disposable spike). Exercises the committed
 * `src/jvmMain/resources/darwin-<arch>/libkardano_ed25519_bip32_signing.dylib` through the
 * pre-generated JNA-backed UniFFI bindings.
 *
 * Vector source: `ed25519-bip32` crate 0.4.2, `src/tests.rs`, `xprv_sign` / `verify_signature`
 * (`D1_H0`), cited by CIP-3 and pinned in ADR-0016 §3. Copied verbatim, not invented.
 */
class SigningBackendKatTest {
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
    fun `reproduces ADR-0016 D1_H0 primary KAT`() {
        assertTrue(xprv.size == 96)

        val signature = sign(xprv, message)

        assertContentEquals(hexToBytes(expectedSignature), signature, "D1_H0_SIGNATURE mismatch")
    }

    @Test
    fun `sign-then-verify self-consistency using the derived xpub`() {
        val signature = sign(xprv, message)
        val xpub = deriveXpub(xprv)

        assertTrue(verify(xpub, message, signature), "signature must verify against the derived xpub")
    }

    @Test
    fun `verify rejects a tampered signature`() {
        val signature = sign(xprv, message)
        signature[0] = (signature[0].toInt() xor 0xFF).toByte()
        val xpub = deriveXpub(xprv)

        assertFalse(verify(xpub, message, signature))
    }

    @Test
    fun `rejects wrong-length extended private key`() {
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
