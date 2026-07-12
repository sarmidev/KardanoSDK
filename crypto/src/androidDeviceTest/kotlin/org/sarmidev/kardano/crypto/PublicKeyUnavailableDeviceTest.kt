package org.sarmidev.kardano.crypto

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith
import org.sarmidev.kardano.KardanoResult
import kotlin.test.assertEquals
import kotlin.test.fail

/**
 * On-device (emulator/physical-device) proof that [KeyDerivation.publicKey] degrades
 * gracefully on Android — returning [KeyDerivationError.PublicKeyProjectionUnavailable] —
 * instead of throwing, per the KMP error policy's "no throwing" rule.
 *
 * 1.6c-follow-up gate result (ADR-0010): the verified projection backend's published Android
 * native library does not export the required symbols, so [KeyDerivation.publicKey] must not
 * attempt to call it on Android at all (see the `androidMain` [PublicKeyProjection] actual).
 * This test proves that contract holds under a real Android runtime, not just in host-JVM
 * compilation. [KeyDerivationDeviceTest] proves private derivation is unaffected.
 */
@RunWith(AndroidJUnit4::class)
class PublicKeyUnavailableDeviceTest {

    private val mnemonic = listOf(
        "test", "walk", "nut", "penalty", "hip", "pave",
        "soap", "entry", "language", "right", "filter", "choice",
    )

    @Test
    fun publicKey_returnsUnavailableError_onDeviceRuntime() {
        val master = deriveMaster()
        val path = okPath(Cip1852Path.of(account = 0, role = Cip1852Role.EXTERNAL, index = 0))
        val privateKey = okKey(KeyDerivation.default().derivePrivate(master, path))

        val result = KeyDerivation.default().publicKey(privateKey)

        val error = when (result) {
            is KardanoResult.Ok -> fail("expected Err but got Ok(${result.value})")
            is KardanoResult.Err -> result.error
        }
        assertEquals(KeyDerivationError.PublicKeyProjectionUnavailable, error)
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
}
