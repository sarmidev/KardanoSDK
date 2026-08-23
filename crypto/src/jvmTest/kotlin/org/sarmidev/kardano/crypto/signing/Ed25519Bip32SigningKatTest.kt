package org.sarmidev.kardano.crypto.signing

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.derivation.ExtendedPrivateKey
import org.sarmidev.kardano.crypto.derivation.KeyDerivationError
import org.sarmidev.kardano.crypto.hashing.CryptoError
import org.sarmidev.kardano.crypto.hashing.HashDigest
import org.sarmidev.kardano.crypto.hashing.Hashing
import org.sarmidev.kardano.crypto.signing.backend.internal.deriveXpub
import org.sarmidev.kardano.crypto.signing.backend.internal.sign as backendSign
import org.sarmidev.kardano.crypto.signing.backend.internal.verify as backendVerify
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * JVM tests that exercise [Signing] against the real, adopted `:crypto-signing-backend` module
 * (ADR-0016 §9i) — the dependency this test file proves is correctly wired from `:crypto`.
 *
 * JVM host-run by design, not a style choice, mirroring `KeyDerivationVectorsTest`:
 * `:crypto:testAndroidHostTest` runs on the host JVM, not Android, so it cannot prove the
 * native-backed signing backend works on real Android runtime. That proof is
 * `:crypto-signing-backend:connectedAndroidDeviceTest` (ADR-0016 §9f, already verified for the
 * backend module itself); this file additionally proves `:crypto`'s own dependency wiring and
 * public [Signing] API reach that same backend correctly on the host JVM.
 *
 * Vector source (D1_H0 reproduction): `ed25519-bip32` crate 0.4.2, `src/tests.rs`, `xprv_sign`
 * (cited by CIP-3, pinned in ADR-0016 §3). Copied verbatim, not invented.
 */
@OptIn(ExperimentalKardanoRawSigning::class)
class Ed25519Bip32SigningKatTest {

    // D1_H0, copied verbatim from ADR-0016 §3 (see class doc for source).
    private val d1h0ExtendedScalar =
        "60d399da83ef80d8d4f8d223239efdc2b8fef387e1b5219137ffb4e8fbdea15adc9366b7d003af37c11396" +
            "de9a83734e30e05e851efa32745c9cd7b42712c890"
    private val d1h0ChainCode =
        "608763770eddf77248ab652984b21b849760d1da74a6f5bd633ce41adceef07a"
    private val d1h0Message = "Hello World".toByteArray(Charsets.US_ASCII)
    private val d1h0ExpectedSignature =
        "90194d57cde4fdadd01eb7cf161780c277e129fc7135b97779a3268837e4cd2e9444b9bb91c0e84d23bba87" +
            "0df3c4bda91a110ef735638fa7a34ea2046d4be04"
    private val d1h0Xprv get() = hexToBytes(d1h0ExtendedScalar + d1h0ChainCode)

    @Test
    fun cryptoDependencyWiring_reproducesAdr0016D1H0ThroughTheBackendItDependsOn() {
        // Proves the crypto -> crypto-signing-backend dependency (added by this block) reaches
        // the same real backend the module's own SigningBackendKatTest already verified.
        val signature = backendSign(d1h0Xprv, d1h0Message)

        assertContentEquals(hexToBytes(d1h0ExpectedSignature), signature, "D1_H0_SIGNATURE mismatch")
    }

    @Test
    fun sign_withD1H0KeyAndA32ByteBodyHash_producesASignatureThatVerifiesAgainstTheDerivedXpub() {
        // Self-consistency check (ADR-0015 §6), not an external golden: D1_H0's own message is
        // 11 bytes, not the 32-byte body hash Signing.sign requires, so this signs a real
        // Blake2b-256 digest (computed by this module's own already-vector-tested Hashing, not
        // invented) and checks the signature verifies against the backend-derived public key.
        val key = okKey(
            ExtendedPrivateKey.of(
                xsk = d1h0Xprv.copyOfRange(0, 64),
                chainCode = d1h0Xprv.copyOfRange(64, 96),
            ),
        )
        val bodyHash = okDigest(Hashing.default().blake2b256(d1h0Message)).toByteArray()

        val result = Signing.default().sign(bodyHash, key)

        val signature = when (result) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }
        assertTrue(signature.size == Signing.SIGNATURE_BYTES)
        val xpub = deriveXpub(d1h0Xprv)
        assertTrue(
            backendVerify(xpub, bodyHash, signature),
            "signature produced by Signing.sign must verify against the derived xpub",
        )
    }

    private fun hexToBytes(hex: String): ByteArray =
        ByteArray(hex.length / 2) { i -> hex.substring(i * 2, i * 2 + 2).toInt(16).toByte() }

    private fun okKey(
        result: KardanoResult<ExtendedPrivateKey, KeyDerivationError>,
    ): ExtendedPrivateKey = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }

    private fun okDigest(
        result: KardanoResult<HashDigest, CryptoError>,
    ): HashDigest = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }
}
