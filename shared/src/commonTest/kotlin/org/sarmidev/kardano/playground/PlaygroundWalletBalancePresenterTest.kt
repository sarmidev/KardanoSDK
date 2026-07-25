package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.address.AddressError
import org.sarmidev.kardano.crypto.derivation.KeyDerivationError
import org.sarmidev.kardano.crypto.hashing.CryptoError
import org.sarmidev.kardano.crypto.mnemonic.MnemonicError
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.provider.ProviderError
import org.sarmidev.kardano.wallet.WalletBalance
import org.sarmidev.kardano.wallet.WalletError
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Unit tests for [PlaygroundPresenter]'s read-only wallet-balance checkpoint (Block 1.8b).
 *
 * [PlaygroundPresenter.mapWalletBalanceResult] and [PlaygroundPresenter.presentWalletError] are
 * both non-suspend and native-free: they format an already-restored [Address] plus a
 * [KardanoResult] built directly, without calling `:wallet`'s `ReadOnlyWallet.restore` (which
 * reaches `:crypto`'s native derivation backend). That means this test can run on every
 * target, including `:shared:testAndroidHostTest` — see [PlaygroundWalletPresenterTest]'s KDoc
 * for the same native-backend constraint.
 *
 * The [Address] used below is [InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS], a cited
 * CIP-19 testnet vector already used by the provider-section checkpoint — not the fixture's own
 * self-generated address, since building that would require the native backend.
 */
class PlaygroundWalletBalancePresenterTest {

    private val address: Address = requireNotNull(
        Address.parse(InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS).getOrNull(),
    )

    // --- mapWalletBalanceResult: Ok ---

    @Test
    fun okWithUtxos_producesSuccessRowsWithAddressCountAndLovelace() {
        val balance = WalletBalance(coin = requireNotNull(Lovelace.of(5_000_000L).getOrNull()), utxoCount = 2)
        val presentation = PlaygroundPresenter.mapWalletBalanceResult(address, KardanoResult.Ok(balance))

        val success = assertIs<WalletBalancePresentation.Success>(presentation)
        val rowByLabel = success.rows.associate { it.label to it.value }
        assertEquals(address.toBech32(), rowByLabel["Address"])
        assertEquals("2", rowByLabel["UTxO count"])
        assertEquals("5000000 lovelace", rowByLabel["Balance"])
    }

    @Test
    fun okWithZeroBalance_producesSuccessNotFailure() {
        // Honest zero-balance behavior (ADR-0013 §7): the default in-memory mock has no fake
        // UTxOs seeded for a generated wallet address, and that is a normal Ok result, not an
        // error this presenter should surface as a failure.
        val balance = WalletBalance(coin = Lovelace.ZERO, utxoCount = 0)
        val presentation = PlaygroundPresenter.mapWalletBalanceResult(address, KardanoResult.Ok(balance))

        val success = assertIs<WalletBalancePresentation.Success>(presentation)
        val rowByLabel = success.rows.associate { it.label to it.value }
        assertEquals("0", rowByLabel["UTxO count"])
        assertEquals("0 lovelace", rowByLabel["Balance"])
    }

    // --- mapWalletBalanceResult: Err ---

    @Test
    fun errProviderNetworkMismatch_producesFailure() {
        val error = WalletError.Provider(ProviderError.NetworkMismatch(Network.MAINNET, Network.TESTNET))
        val presentation = PlaygroundPresenter.mapWalletBalanceResult(address, KardanoResult.Err(error))

        val failure = assertIs<WalletBalancePresentation.Failure>(presentation)
        assertTrue(failure.message.contains("Network mismatch"), "got: ${failure.message}")
    }

    // --- presentWalletError: every variant delegates to the matching existing presenter ---

    @Test
    fun presentWalletError_mnemonic_delegatesToPresentMnemonicError() {
        val msg = PlaygroundPresenter.presentWalletError(
            WalletError.Mnemonic(MnemonicError.InvalidWordCount(4)),
        )
        assertTrue(msg.contains("4"), "got: $msg")
    }

    @Test
    fun presentWalletError_derivation_delegatesToPresentKeyDerivationError() {
        val msg = PlaygroundPresenter.presentWalletError(
            WalletError.Derivation(KeyDerivationError.SoftDerivationRequired),
        )
        assertTrue(msg.contains("soft", ignoreCase = true), "got: $msg")
    }

    @Test
    fun presentWalletError_hashing_delegatesToPresentCryptoError() {
        val msg = PlaygroundPresenter.presentWalletError(
            WalletError.Hashing(CryptoError.HashingFailed("digest failed")),
        )
        assertTrue(msg.contains("digest failed"), "got: $msg")
    }

    @Test
    fun presentWalletError_addressBuild_delegatesToPresentAddressError() {
        val msg = PlaygroundPresenter.presentWalletError(
            WalletError.AddressBuild(AddressError.EmptyPayload),
        )
        assertTrue(msg.contains("Empty payload", ignoreCase = true), "got: $msg")
    }

    @Test
    fun presentWalletError_provider_delegatesToPresentProviderError() {
        val msg = PlaygroundPresenter.presentWalletError(WalletError.Provider(ProviderError.NotFound))
        assertTrue(msg.contains("Not found", ignoreCase = true), "got: $msg")
    }

    @Test
    fun presentWalletError_balanceOverflow_containsPartialCount() {
        val msg = PlaygroundPresenter.presentWalletError(WalletError.BalanceOverflow(partialCount = 3))
        assertTrue(msg.contains("3"), "got: $msg")
    }
}
