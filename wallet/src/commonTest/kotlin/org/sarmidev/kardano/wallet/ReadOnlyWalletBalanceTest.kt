package org.sarmidev.kardano.wallet

import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.address.AddressCredential
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.provider.ProviderError
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.provider.Value
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

/**
 * Native-free tests for [ReadOnlyWallet.balance], using the module-internal [ReadOnlyWallet.of]
 * to assemble a wallet handle around an already-parsed/built [Address] rather than restoring a
 * mnemonic — so this suite runs under both `:wallet:jvmTest` and `:wallet:testAndroidHostTest`
 * without reaching `:crypto`'s native derivation backend. See
 * [ReadOnlyWalletRestoreDesktopTest] for the JVM-only end-to-end coverage that does restore a
 * real mnemonic.
 *
 * The seeded-address cases deliberately assemble a wallet around
 * [InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS] / `SEED_ADDRESS_EMPTY` to assert the
 * balance-summation path against known fake data; this does not imply a *restored* wallet's own
 * generated address is seeded (ADR-0013 §7 — it is not, and stays zero-balance under the
 * default mock).
 */
class ReadOnlyWalletBalanceTest {

    private fun parse(address: String): Address =
        requireNotNull(Address.parse(address).getOrNull()) { "expected a valid test address" }

    /** A structurally valid base address distinct from either of the mock's seeded addresses. */
    private fun distinctUnseededAddress(): Address {
        val payment = requireNotNull(
            AddressCredential.keyHash(ByteArray(28) { 0xAA.toByte() }).getOrNull(),
        )
        val stake = requireNotNull(
            AddressCredential.keyHash(ByteArray(28) { 0xBB.toByte() }).getOrNull(),
        )
        return requireNotNull(Address.baseAddress(Network.TESTNET, payment, stake).getOrNull())
    }

    private fun utxo(seedByte: Int, outputIndex: Long, lovelace: Long): Utxo {
        val hashBytes = ByteArray(TxHash.SIZE) { seedByte.toByte() }
        val txHash = requireNotNull(TxHash.of(hashBytes).getOrNull())
        val ref = requireNotNull(UtxoRef.of(txHash, outputIndex).getOrNull())
        val coin = requireNotNull(Lovelace.of(lovelace).getOrNull())
        return Utxo(ref, Value(coin))
    }

    @Test
    fun balance_seededWithUtxosAddress_sumsSeededAmounts() = runTest {
        val address = parse(InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS)
        val wallet = ReadOnlyWallet.of(Network.TESTNET, address)

        val result = wallet.balance(InMemoryChainQueryProvider())

        val ok = assertIs<KardanoResult.Ok<WalletBalance>>(result)
        assertEquals(2, ok.value.utxoCount)
        assertEquals(17_500_000L, ok.value.coin.value)
    }

    @Test
    fun balance_seededEmptyAddress_returnsZero() = runTest {
        val address = parse(InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY)
        val wallet = ReadOnlyWallet.of(Network.TESTNET, address)

        val result = wallet.balance(InMemoryChainQueryProvider())

        val ok = assertIs<KardanoResult.Ok<WalletBalance>>(result)
        assertEquals(0, ok.value.utxoCount)
        assertEquals(Lovelace.ZERO, ok.value.coin)
    }

    @Test
    fun balance_unseededAddress_returnsZeroNotError() = runTest {
        val wallet = ReadOnlyWallet.of(Network.TESTNET, distinctUnseededAddress())

        val result = wallet.balance(InMemoryChainQueryProvider())

        val ok = assertIs<KardanoResult.Ok<WalletBalance>>(result)
        assertEquals(0, ok.value.utxoCount)
        assertEquals(Lovelace.ZERO, ok.value.coin)
    }

    @Test
    fun balance_providerNetworkMismatch_returnsWalletErrorProvider() = runTest {
        val address = parse(InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS)
        val wallet = ReadOnlyWallet.of(Network.TESTNET, address)
        val mainnetBoundProvider = InMemoryChainQueryProvider(network = Network.MAINNET)

        val result = wallet.balance(mainnetBoundProvider)

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val providerError = assertIs<WalletError.Provider>(err.error)
        val mismatch = assertIs<ProviderError.NetworkMismatch>(providerError.error)
        assertEquals(Network.MAINNET, mismatch.expected)
        assertEquals(Network.TESTNET, mismatch.actual)
    }

    @Test
    fun balance_overflowingUtxoSum_returnsBalanceOverflowWithoutTruncating() = runTest {
        val address = distinctUnseededAddress()
        val wallet = ReadOnlyWallet.of(Network.TESTNET, address)
        val overflowingUtxos = listOf(
            utxo(seedByte = 0x01, outputIndex = 0L, lovelace = Long.MAX_VALUE),
            utxo(seedByte = 0x02, outputIndex = 1L, lovelace = 1L),
        )
        val provider = InMemoryChainQueryProvider(utxosByAddress = mapOf(address to overflowingUtxos))

        val result = wallet.balance(provider)

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val overflow = assertIs<WalletError.BalanceOverflow>(err.error)
        assertEquals(1, overflow.partialCount)
    }
}
