package org.sarmidev.kardano.crypto.signing

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.derivation.ExtendedPrivateKey
import org.sarmidev.kardano.crypto.derivation.KeyDerivationError
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.fail

/**
 * Native-free tests for [Signing.sign]'s `bodyHash` length rejection.
 *
 * [Signing.sign] rejects a wrong-length `bodyHash` before it ever reaches the native
 * `:crypto-signing-backend`, so these cases run under both `:crypto:jvmTest` and
 * `:crypto:testAndroidHostTest`, mirroring `ReadOnlyWalletRestoreMnemonicTest`'s native-free
 * mnemonic-rejection pattern. See `Ed25519Bip32SigningKatTest` for the JVM-only tests that do
 * reach the real backend with a correctly-sized 32-byte hash.
 */
class SigningLengthValidationTest {

    // Synthetic fixture bytes only; not derived from any mnemonic or real key material. This
    // key's shape (96 bytes total) is what matters here, not its value: the backend is never
    // reached for these wrong-length-`bodyHash` cases.
    private val fixtureKey = okKey(
        ExtendedPrivateKey.of(
            xsk = ByteArray(64) { (it + 1).toByte() },
            chainCode = ByteArray(32) { (it + 100).toByte() },
        ),
    )

    @Test
    fun sign_emptyHash_isInvalidBodyHashLength() {
        val result = Signing.default().sign(ByteArray(0), fixtureKey)

        assertEquals(
            KardanoResult.Err(SigningError.InvalidBodyHashLength(expectedBytes = 32, actualBytes = 0)),
            result,
        )
    }

    @Test
    fun sign_hashOneByteShort_isInvalidBodyHashLength() {
        val result = Signing.default().sign(ByteArray(31), fixtureKey)

        assertEquals(
            KardanoResult.Err(SigningError.InvalidBodyHashLength(expectedBytes = 32, actualBytes = 31)),
            result,
        )
    }

    @Test
    fun sign_hashOneByteLong_isInvalidBodyHashLength() {
        val result = Signing.default().sign(ByteArray(33), fixtureKey)

        assertEquals(
            KardanoResult.Err(SigningError.InvalidBodyHashLength(expectedBytes = 32, actualBytes = 33)),
            result,
        )
    }

    @Test
    fun sign_rawBodyCborLengthInsteadOfHash_isInvalidBodyHashLength() {
        // A body hash check must reject raw body-CBOR-sized input outright: signing raw body
        // bytes (rather than their 32-byte Blake2b-256 hash) would produce an invalid witness
        // (ADR-0015 §3). This is a structural guard, not a claim about any real body's size.
        val result = Signing.default().sign(ByteArray(64), fixtureKey)

        assertEquals(
            KardanoResult.Err(SigningError.InvalidBodyHashLength(expectedBytes = 32, actualBytes = 64)),
            result,
        )
    }

    private fun okKey(
        result: KardanoResult<ExtendedPrivateKey, KeyDerivationError>,
    ): ExtendedPrivateKey = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }
}
