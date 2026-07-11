package org.sarmidev.kardano.crypto

import uniffi.ed25519_bip32_wrapper.DerivationException
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Unit tests for [Bip32Ed25519KeyDerivation]'s `mapThrowable`, the boundary that turns a backend
 * exception into a typed [KeyDerivationError].
 *
 * These construct backend exception values directly (no native call, no derivation is
 * performed) so the mapping logic is exercised without invoking the native library — this
 * module's Android host-test environment cannot load it (ADR-0009 §4's Block 1.6c gate result).
 * [uniffi.ed25519_bip32_wrapper.DerivationException] and its subtypes are plain Kotlin exception
 * classes defined in the wrapper's common source, so constructing them here does not touch any
 * platform-specific native binary.
 */
class Bip32Ed25519KeyDerivationRuleTest {

    @Test
    fun mapThrowable_expectedSoftDerivation_isSoftDerivationRequired() {
        val error = Bip32Ed25519KeyDerivation.mapThrowable(
            DerivationException.ExpectedSoftDerivation("soft derivation expected"),
        )

        assertEquals(KeyDerivationError.SoftDerivationRequired, error)
    }

    @Test
    fun mapThrowable_invalidAddition_isDerivationFailedWithNoBackendDetail() {
        val error = Bip32Ed25519KeyDerivation.mapThrowable(
            DerivationException.InvalidAddition("invalid addition"),
        )

        assertEquals(KeyDerivationError.DerivationFailed("invalid derivation addition"), error)
    }

    @Test
    fun mapThrowable_unrelatedThrowable_isDerivationFailedWithNoBackendDetail() {
        val error = Bip32Ed25519KeyDerivation.mapThrowable(RuntimeException("boom"))

        assertEquals(KeyDerivationError.DerivationFailed("key derivation failed"), error)
    }
}
