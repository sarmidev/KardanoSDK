package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.address.AddressError
import org.sarmidev.kardano.crypto.derivation.KeyDerivationError
import org.sarmidev.kardano.crypto.hashing.CryptoError
import org.sarmidev.kardano.crypto.mnemonic.MnemonicError
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.provider.ProviderError
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Direct construction/equality tests proving each [WalletError] variant wraps its upstream
 * typed error without losing information, per ADR-0013 §6. [ReadOnlyWalletRestoreDesktopTest]
 * and [ReadOnlyWalletBalanceTest] cover the reachable-in-practice wrapping paths
 * ([WalletError.Mnemonic], [WalletError.Provider], [WalletError.BalanceOverflow]); the
 * variants here ([WalletError.Derivation], [WalletError.Hashing], [WalletError.AddressBuild])
 * are only reachable once native derivation succeeds and a later step fails, which this
 * native-free suite cannot force deterministically, so they are covered by direct
 * construction instead.
 */
class WalletErrorTest {

    @Test
    fun mnemonicVariant_wrapsUnderlyingMnemonicError() {
        val error = WalletError.Mnemonic(MnemonicError.InvalidWordCount(4))

        assertEquals(MnemonicError.InvalidWordCount(4), error.error)
    }

    @Test
    fun derivationVariant_wrapsUnderlyingKeyDerivationError() {
        val error = WalletError.Derivation(KeyDerivationError.IndexOutOfRange(-1L))

        assertEquals(KeyDerivationError.IndexOutOfRange(-1L), error.error)
    }

    @Test
    fun hashingVariant_wrapsUnderlyingCryptoError() {
        val error = WalletError.Hashing(CryptoError.InvalidDigestLength(expected = 28, actual = 20))

        assertEquals(CryptoError.InvalidDigestLength(expected = 28, actual = 20), error.error)
    }

    @Test
    fun addressBuildVariant_wrapsUnderlyingAddressError() {
        val error = WalletError.AddressBuild(AddressError.InvalidCredentialLength(expected = 28, actual = 10))

        assertEquals(AddressError.InvalidCredentialLength(expected = 28, actual = 10), error.error)
    }

    @Test
    fun providerVariant_wrapsUnderlyingProviderError() {
        val error = WalletError.Provider(
            ProviderError.NetworkMismatch(expected = Network.TESTNET, actual = Network.MAINNET),
        )

        assertEquals(
            ProviderError.NetworkMismatch(expected = Network.TESTNET, actual = Network.MAINNET),
            error.error,
        )
    }

    @Test
    fun balanceOverflowVariant_carriesPartialCount() {
        val error = WalletError.BalanceOverflow(partialCount = 3)

        assertEquals(3, error.partialCount)
    }

    @Test
    fun distinctVariants_areNotEqual() {
        val mnemonicError: WalletError = WalletError.Mnemonic(MnemonicError.ChecksumMismatch)
        val overflowError: WalletError = WalletError.BalanceOverflow(partialCount = 0)

        assertEquals(false, mnemonicError == overflowError)
    }
}
