package org.sarmidev.kardano.crypto.signing.backend

import org.sarmidev.kardano.crypto.signing.backend.internal.deriveXpub
import org.sarmidev.kardano.crypto.signing.backend.internal.sign
import org.sarmidev.kardano.crypto.signing.backend.internal.verify
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertTrue

/**
 * Block 1.10b backend adoption — iOS compile/link check (ADR-0016 §7c/§9f).
 *
 * The primary purpose of this test is to force `linkDebugTestIosSimulatorArm64` to actually link
 * the committed `src/nativeInterop/libs/iosSimulatorArm64/libkardano_ed25519_bip32_signing.a`: by
 * referencing the cinterop-backed `sign`/`verify`/`deriveXpub` bindings, the Kotlin/Native linker
 * must resolve the UniFFI C symbols from that static library, so a green link is real evidence the
 * committed `.a` + cinterop wiring is correct. On-simulator *execution* of these assertions is
 * honest future work (matching the repo's iOS posture and ADR-0016 §8); this leg is compile+link.
 *
 * Vector source: `ed25519-bip32` crate 0.4.2, `src/tests.rs`, `xprv_sign` / `verify_signature`
 * (`D1_H0`), cited by CIP-3 and pinned in ADR-0016 §3. Copied verbatim, not invented.
 */
class SigningBackendIosLinkTest {
    private fun hexToBytes(hex: String): ByteArray =
        ByteArray(hex.length / 2) { i -> hex.substring(i * 2, i * 2 + 2).toInt(16).toByte() }

    private val xprv
        get() = hexToBytes(
            "60d399da83ef80d8d4f8d223239efdc2b8fef387e1b5219137ffb4e8fbdea15adc9366b7d003af37c11396de9a83734e30e05e851efa32745c9cd7b42712c890" +
                "608763770eddf77248ab652984b21b849760d1da74a6f5bd633ce41adceef07a",
        )
    private val message = "Hello World".encodeToByteArray()
    private val expectedSignature =
        "90194d57cde4fdadd01eb7cf161780c277e129fc7135b97779a3268837e4cd2e9444b9bb91c0e84d23bba870df3c4bda91a110ef735638fa7a34ea2046d4be04"

    @Test
    fun reproducesAdr0016D1H0PrimaryKat() {
        val signature = sign(xprv, message)
        assertContentEquals(hexToBytes(expectedSignature), signature, "D1_H0_SIGNATURE mismatch")

        val xpub = deriveXpub(xprv)
        assertTrue(verify(xpub, message, signature))
    }
}
