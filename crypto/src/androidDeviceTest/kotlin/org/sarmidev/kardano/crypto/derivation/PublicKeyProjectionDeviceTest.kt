package org.sarmidev.kardano.crypto.derivation

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.hashing.Hashing
import org.sarmidev.kardano.crypto.mnemonic.Mnemonic
import org.sarmidev.kardano.encoding.bech32.Bech32
import org.sarmidev.kardano.encoding.hex.Hex
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.fail

/**
 * On-device (emulator/physical-device) known-answer test for [KeyDerivation.publicKey].
 *
 * 1.6c-follow-up-2 gate result (ADR-0010): the `androidMain` `projectPublicKey` actual (the
 * `crypto.internal.projection` platform seam) now delegates to `com.goterl:lazysodium-android`,
 * whose AAR exports
 * `crypto_scalarmult_ed25519_base_noclamp` on all four ABIs (verified by `nm -D` and by this
 * test's on-device execution — see the gate probe evidence for the full record). This replaces
 * the earlier `PublicKeyUnavailableDeviceTest`, whose contract (returning
 * [KeyDerivationError.PublicKeyProjectionUnavailable] on Android) no longer holds.
 * [KeyDerivationDeviceTest] proves private derivation is unaffected.
 *
 * Cross-links two independently cited sources: the `addr_xvk` golden from
 * `IntersectMBO/cardano-addresses` (see [KeyDerivationDeviceTest] for the pinned commit) and the
 * CIP-19 payment credential pinned in [HashingVectorsTest], which ADR-0009 §4 records as the
 * same key (`addr_xvk0` == CIP-19 `addr_vk1w0l2sr...`).
 */
@RunWith(AndroidJUnit4::class)
class PublicKeyProjectionDeviceTest {

    private val mnemonic = listOf(
        "test", "walk", "nut", "penalty", "hip", "pave",
        "soap", "entry", "language", "right", "filter", "choice",
    )

    // CIP-5 bech32 `addr_xvk` (extended verification key), copied verbatim from the pinned
    // golden file (see KeyDerivationDeviceTest for the cited source).
    private val addrXvk0 =
        "addr_xvk1w0l2sr2zgfm26ztc6nl9xy8ghsk5sh6ldwemlpmp9xylzy4dtf7a6a0p2ndyz7lva32um5jfxf6" +
            "9gyu0pqs3q2tat6r6kf0pt7k32rcuhjq9l"

    // CIP-19 payment credential for the same key (see HashingVectorsTest for the cited source).
    private val cip19PaymentCredential = "9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e"

    @Test
    fun publicKey_role0Index0_matchesGoldenAddrXvk0_onDeviceRuntime() {
        val master = deriveMaster()
        val path = okPath(Cip1852Path.of(account = 0, role = Cip1852Role.EXTERNAL, index = 0))
        val privateKey = okKey(KeyDerivation.default().derivePrivate(master, path))

        val publicKey = okPublicKey(KeyDerivation.default().publicKey(privateKey))

        assertContentEquals(decodeCip5(addrXvk0), publicKey.xvkBytesForTesting())
    }

    @Test
    fun publicKey_role0Index0_blake2b224MatchesCip19PaymentCredential_onDeviceRuntime() {
        val master = deriveMaster()
        val path = okPath(Cip1852Path.of(account = 0, role = Cip1852Role.EXTERNAL, index = 0))
        val privateKey = okKey(KeyDerivation.default().derivePrivate(master, path))
        val publicKey = okPublicKey(KeyDerivation.default().publicKey(privateKey))

        val digest = when (val result = Hashing.default().blake2b224(publicKey.publicKeyBytes())) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }

        assertContentEquals(hex(cip19PaymentCredential), digest.toByteArray())
    }

    private fun deriveMaster(): IcarusMasterKey {
        val parsed = when (val result = Mnemonic.parse(mnemonic)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }
        return when (val result = IcarusMasterKey.fromMnemonic(parsed)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }
    }

    private fun okPath(
        result: KardanoResult<Cip1852Path, KeyDerivationError>,
    ): Cip1852Path = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }

    private fun okKey(
        result: KardanoResult<ExtendedPrivateKey, KeyDerivationError>,
    ): ExtendedPrivateKey = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }

    private fun okPublicKey(
        result: KardanoResult<ExtendedPublicKey, KeyDerivationError>,
    ): ExtendedPublicKey = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }

    private fun hex(value: String): ByteArray = when (val result = Hex.decode(value)) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("invalid hex in test vector: ${result.error}")
    }

    /** Decodes a CIP-5 bech32 key string to its raw bytes via [Bech32.decode] and [convert5BitTo8Bit]. */
    private fun decodeCip5(bech32: String): ByteArray {
        val decoded = when (val result = Bech32.decode(bech32)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }
        return convert5BitTo8Bit(decoded.toData5BitArray())
    }

    /**
     * Test-only 5-bit-to-8-bit conversion, mirroring BIP-173's `convertbits(data, 5, 8, False)`.
     * Duplicated rather than shared for the same reason cited in [KeyDerivationDeviceTest].
     */
    private fun convert5BitTo8Bit(data: ByteArray): ByteArray {
        require(data.size <= MAX_5BIT_VALUES) { "5-bit input too long for this test helper" }
        val outSize = data.size * 5 / 8
        val out = ByteArray(outSize)
        var acc = 0
        var bits = 0
        var oi = 0
        for (b in data) {
            val value = b.toInt() and 0xFF
            require(value in 0..31) { "not a 5-bit value: $value" }
            acc = ((acc shl 5) or value) and MAX_ACCUMULATOR
            bits += 5
            while (bits >= 8) {
                bits -= 8
                out[oi++] = ((acc ushr bits) and 0xFF).toByte()
            }
        }
        check(bits < 5 && ((acc shl (8 - bits)) and 0xFF) == 0) {
            "leftover bits are non-zero; not a canonical byte-aligned encoding"
        }
        return out
    }

    private companion object {
        private const val MAX_5BIT_VALUES: Int = 256
        private const val MAX_ACCUMULATOR: Int = 0xFFF
    }
}
