package org.sarmidev.kardano.playground

import org.sarmidev.kardano.crypto.derivation.KeyDerivationError
import org.sarmidev.kardano.crypto.hashing.CryptoError
import org.sarmidev.kardano.crypto.mnemonic.MnemonicError
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Unit tests for [PlaygroundPresenter]'s test-wallet derivation checkpoint (Block 1.6d).
 *
 * This test runs on **every** target, including `:shared:testAndroidHostTest` — the host JVM
 * under the Android target, where `:crypto`'s native derivation/projection backend cannot load
 * (`UnsatisfiedLinkError`, same finding as Block 1.6c). It therefore covers only paths that
 * never reach a native call: error-message mapping (variants constructed directly), CIP-1852
 * path formatting, and mnemonic parsing failures that are rejected before
 * `IcarusMasterKey.fromMnemonic`/derivation. The end-to-end fingerprint golden check (which does
 * reach the native backend) lives only in `shared/jvmTest`.
 */
class PlaygroundWalletPresenterTest {

    // --- TestWalletFixture: path formatting, no native call ---

    @Test
    fun fixturePath_formatsAsExpectedCip1852Path() {
        assertEquals("m/1852'/1815'/0'/0/0", TestWalletFixture.path.toString())
    }

    @Test
    fun fixtureWords_hasTwelveWords() {
        assertEquals(12, TestWalletFixture.words.size)
    }

    // --- presentMnemonicError: directly-constructed variants ---

    @Test
    fun invalidWordCount_containsCount() {
        val msg = PlaygroundPresenter.presentMnemonicError(MnemonicError.InvalidWordCount(4))
        assertTrue(msg.contains("4"), "got: $msg")
    }

    @Test
    fun wordNotInWordlist_containsPosition() {
        val msg = PlaygroundPresenter.presentMnemonicError(MnemonicError.WordNotInWordlist(2))
        assertTrue(msg.contains("2"), "got: $msg")
    }

    @Test
    fun checksumMismatch_containsDescription() {
        val msg = PlaygroundPresenter.presentMnemonicError(MnemonicError.ChecksumMismatch)
        assertTrue(msg.contains("checksum", ignoreCase = true), "got: $msg")
    }

    @Test
    fun invalidCharacters_containsPosition() {
        val msg = PlaygroundPresenter.presentMnemonicError(MnemonicError.InvalidCharacters(1))
        assertTrue(msg.contains("1"), "got: $msg")
    }

    @Test
    fun inputTooLong_containsMaxAndActual() {
        val msg = PlaygroundPresenter.presentMnemonicError(MnemonicError.InputTooLong(256, 300))
        assertTrue(msg.contains("256"), "got: $msg")
        assertTrue(msg.contains("300"), "got: $msg")
    }

    // --- presentKeyDerivationError: directly-constructed variants ---

    @Test
    fun invalidKeyMaterial_containsExpectedAndActual() {
        val msg = PlaygroundPresenter.presentKeyDerivationError(
            KeyDerivationError.InvalidKeyMaterial(expectedBytes = 96, actualBytes = 64),
        )
        assertTrue(msg.contains("96"), "got: $msg")
        assertTrue(msg.contains("64"), "got: $msg")
    }

    @Test
    fun indexOutOfRange_containsValue() {
        val msg = PlaygroundPresenter.presentKeyDerivationError(
            KeyDerivationError.IndexOutOfRange(9_999_999_999L),
        )
        assertTrue(msg.contains("9999999999"), "got: $msg")
    }

    @Test
    fun softDerivationRequired_containsDescription() {
        val msg = PlaygroundPresenter.presentKeyDerivationError(KeyDerivationError.SoftDerivationRequired)
        assertTrue(msg.contains("soft", ignoreCase = true), "got: $msg")
    }

    @Test
    fun derivationFailed_containsMessage() {
        val msg = PlaygroundPresenter.presentKeyDerivationError(
            KeyDerivationError.DerivationFailed("backend failed"),
        )
        assertTrue(msg.contains("backend failed"), "got: $msg")
    }

    @Test
    fun publicKeyProjectionUnavailable_containsDescription() {
        val msg = PlaygroundPresenter.presentKeyDerivationError(
            KeyDerivationError.PublicKeyProjectionUnavailable,
        )
        assertTrue(msg.contains("projection", ignoreCase = true), "got: $msg")
    }

    // --- presentCryptoError: directly-constructed variants ---

    @Test
    fun hashingFailed_containsMessage() {
        val msg = PlaygroundPresenter.presentCryptoError(CryptoError.HashingFailed("digest failed"))
        assertTrue(msg.contains("digest failed"), "got: $msg")
    }

    @Test
    fun invalidDigestLength_containsExpectedAndActual() {
        val msg = PlaygroundPresenter.presentCryptoError(
            CryptoError.InvalidDigestLength(expected = 28, actual = 32),
        )
        assertTrue(msg.contains("28"), "got: $msg")
        assertTrue(msg.contains("32"), "got: $msg")
    }

    // --- presentTestWalletWithWords: invalid input, rejected before any native call ---

    @Test
    fun invalidWordCount_producesFailure_withoutReachingNativeCode() {
        // Rejected by Mnemonic.parse (word count) before IcarusMasterKey.fromMnemonic or any
        // derivation call — safe to run under testAndroidHostTest.
        val presentation = PlaygroundPresenter.presentTestWalletWithWords(
            listOf("not", "a", "valid", "mnemonic"),
        )
        assertIs<WalletPresentation.Failure>(presentation)
        assertTrue(presentation.message.isNotBlank(), "message should not be blank")
    }

    @Test
    fun wordNotInEnglishWordlist_producesFailure_withoutReachingNativeCode() {
        // Twelve words (valid count) but not from the BIP-39 English wordlist — rejected by
        // Mnemonic.parse before any native call.
        val presentation = PlaygroundPresenter.presentTestWalletWithWords(
            List(12) { "notarealbip39word" },
        )
        assertIs<WalletPresentation.Failure>(presentation)
        assertTrue(presentation.message.isNotBlank(), "message should not be blank")
    }
}
