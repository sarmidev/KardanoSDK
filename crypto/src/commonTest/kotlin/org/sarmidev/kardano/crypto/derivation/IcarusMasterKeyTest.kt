package org.sarmidev.kardano.crypto.derivation

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.mnemonic.Mnemonic
import org.sarmidev.kardano.crypto.mnemonic.MnemonicError
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Structural tests for [IcarusMasterKey], exercising key-material handling rules (ADR-0009 §7)
 * rather than the derived byte values themselves (covered by [IcarusMasterKeyVectorsTest]).
 */
class IcarusMasterKeyTest {

    // The cited 12-word, all-zero-entropy vector (see MnemonicVectorsTest).
    private val validWords = listOf(
        "abandon", "abandon", "abandon", "abandon", "abandon", "abandon",
        "abandon", "abandon", "abandon", "abandon", "abandon", "about",
    )

    @Test
    fun fromMnemonic_emptyPassphrase_isOk() {
        val mnemonic = okMnemonic(Mnemonic.parse(validWords))

        val result = IcarusMasterKey.fromMnemonic(mnemonic)

        assertTrue(result is KardanoResult.Ok)
    }

    @Test
    fun toString_isStructuralAndDoesNotRenderKeyBytes() {
        val mnemonic = okMnemonic(Mnemonic.parse(validWords))
        val master = okMaster(IcarusMasterKey.fromMnemonic(mnemonic))

        assertEquals("IcarusMasterKey()", master.toString())
    }

    @Test
    fun clear_wipesRootKeyOnThisInstanceOnly() {
        val mnemonic = okMnemonic(Mnemonic.parse(validWords))
        val master = okMaster(IcarusMasterKey.fromMnemonic(mnemonic))
        val beforeClear = master.rootKeyBytesForTesting()
        assertFalse(beforeClear.all { it == 0.toByte() }, "derived key must not already be all zero")

        master.clear()

        assertTrue(
            master.rootKeyBytesForTesting().all { it == 0.toByte() },
            "clear() must zero the retained root key",
        )
    }

    @Test
    fun rootKeyBytesForTesting_returnsIndependentCopy() {
        val mnemonic = okMnemonic(Mnemonic.parse(validWords))
        val master = okMaster(IcarusMasterKey.fromMnemonic(mnemonic))

        val first = master.rootKeyBytesForTesting()
        first[0] = 0x7F

        assertFalse(
            master.rootKeyBytesForTesting()[0] == 0x7F.toByte(),
            "mutating a returned copy must not affect the IcarusMasterKey's internal root key",
        )
    }

    @Test
    fun fromMnemonic_differentPassphrasesProduceDifferentKeys() {
        val mnemonic = okMnemonic(Mnemonic.parse(validWords))

        val withoutPassphrase = okMaster(IcarusMasterKey.fromMnemonic(mnemonic, ByteArray(0)))
        val withPassphrase =
            okMaster(IcarusMasterKey.fromMnemonic(mnemonic, "foo".encodeToByteArray()))

        assertFalse(
            withoutPassphrase.rootKeyBytesForTesting()
                .contentEquals(withPassphrase.rootKeyBytesForTesting()),
            "different passphrases must derive different master keys",
        )
    }

    private fun okMnemonic(result: KardanoResult<Mnemonic, MnemonicError>): Mnemonic =
        when (result) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }

    private fun okMaster(
        result: KardanoResult<IcarusMasterKey, KeyDerivationError>,
    ): IcarusMasterKey =
        when (result) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }
}
