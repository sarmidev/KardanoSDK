package org.sarmidev.kardano.crypto.signing

import org.sarmidev.kardano.crypto.signing.backend.internal.SigningBackendException
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Unit tests for [Ed25519Bip32Signing]'s `mapThrowable`, the boundary that turns a backend
 * exception into a typed [SigningError].
 *
 * These construct backend exception values directly (no native call, no signing is performed)
 * so the mapping logic is exercised without invoking the native library, mirroring
 * `Bip32Ed25519KeyDerivationRuleTest`. [SigningBackendException] and its subtypes are plain
 * Kotlin exception classes defined in `:crypto-signing-backend`'s common source, so
 * constructing them here does not touch any platform-specific native binary.
 */
class Ed25519Bip32SigningRuleTest {

    @Test
    fun mapThrowable_invalidExtendedPrivateKey_isInvalidKeyMaterial() {
        val error = Ed25519Bip32Signing.mapThrowable(
            SigningBackendException.InvalidExtendedPrivateKey(),
            xprvBytes = 10,
        )

        assertEquals(SigningError.InvalidKeyMaterial(expectedBytes = 96, actualBytes = 10), error)
    }

    @Test
    fun mapThrowable_unrelatedThrowable_isBackendFailedWithNoBackendDetail() {
        val error = Ed25519Bip32Signing.mapThrowable(RuntimeException("boom"), xprvBytes = 96)

        assertEquals(SigningError.BackendFailed("signing failed"), error)
    }
}
