package org.sarmidev.kardano.crypto

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.bech32.Bech32
import kotlin.test.assertContentEquals
import kotlin.test.fail

/**
 * On-device (emulator/physical-device) known-answer test for [KeyDerivation.derivePrivate].
 *
 * 1.6c-follow-up gate (Outcome A investigation): `:crypto:testAndroidHostTest`
 * (`androidHostTest`) only proves the module *compiles* for Android — it runs on the host JVM,
 * not on Android, so it cannot prove the uniffi/JNA native library actually loads and derives
 * correctly under a real Android runtime. This device test runs under `connectedAndroidTest`
 * / `connectedDebugAndroidTest` on an emulator or device, exercising the exact same call path
 * as [KeyDerivationVectorsTest] against the identical cited golden vectors. Test-only: no
 * product/app code depends on this source set.
 *
 * Source: `IntersectMBO/cardano-addresses` (Apache-2.0), path
 * `test/golden/addresses_5574d91d/golden`, pinned commit
 * `46d01319015275941f96126b2496453693f89538`.
 */
@RunWith(AndroidJUnit4::class)
class KeyDerivationDeviceTest {

    private val mnemonic = listOf(
        "test", "walk", "nut", "penalty", "hip", "pave",
        "soap", "entry", "language", "right", "filter", "choice",
    )

    // CIP-5 bech32, copied verbatim from the pinned golden file (see class doc for source).
    private val rootXsk =
        "root_xsk1vzrzr76vqyqlavclduhawqvtae2pq8lk0424q7t8rzfjyhhp530zxv2fwq5a3pd4vdzqtu6s2zxdjh" +
            "ww8xg4qwcs7y5dqne5k7mz27p6rcaath83rl20nz0v9nwdaga9fkufjuucza8vmny8qpkzwstk5qh7s88m"
    private val addrXsk0 =
        "addr_xsk1hqf6v2lvhfn5mr3fe6g8ac6n8a3z6s0p24mg6kre8jadxulp530y07wjp2ml0zcz8gk0xc7zy96qp2" +
            "xxtr0arjq9038k9dhkw3k3cswawhs4fkjp00kwc4wd6fynyaz5zw8ssggs9974apatyhs4ltg4puw0nn7y"

    @Test
    fun fromMnemonic_rootMatchesGoldenRootXsk_onDeviceRuntime() {
        val master = deriveMaster()

        assertContentEquals(decodeCip5(rootXsk), master.rootKeyBytesForTesting())
    }

    @Test
    fun derivePrivate_role0Index0_matchesGoldenAddrXsk0_onDeviceRuntime() {
        val master = deriveMaster()
        val path = okPath(Cip1852Path.of(account = 0, role = Cip1852Role.EXTERNAL, index = 0))

        val key = okKey(KeyDerivation.default().derivePrivate(master, path))

        assertContentEquals(decodeCip5(addrXsk0), key.xskBytesForTesting())
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
     *
     * Duplicated from [KeyDerivationVectorsTest] rather than shared: `:core`'s equivalent
     * (`Bech32.convertBits`) is `internal` to `:core` and not visible from `:crypto`
     * (ADR-0009 §Block 1.6c gate result), and this device-test source set does not share a
     * source root with `jvmTest`.
     *
     * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki">BIP-173</a>
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
        /** Upper bound on 5-bit values [convert5BitTo8Bit] accepts, checked before allocation. */
        private const val MAX_5BIT_VALUES: Int = 256

        /** Mask matching BIP-173's `(1 << (fromBits + toBits - 1)) - 1` for fromBits=5, toBits=8. */
        private const val MAX_ACCUMULATOR: Int = 0xFFF
    }
}
