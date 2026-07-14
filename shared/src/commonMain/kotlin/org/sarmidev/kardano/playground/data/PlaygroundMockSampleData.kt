package org.sarmidev.kardano.playground.data

import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.playground.TestWalletFixture
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.provider.Value
import org.sarmidev.kardano.wallet.ReadOnlyWallet

/**
 * Sample/mock seed data for the Playground's default in-memory provider (Block 1.12-pre-c-3).
 *
 * This is Playground/sample wiring in `:shared` only — **not** chain data, **not** the SDK public
 * API, and **not** part of `:provider`'s own [InMemoryChainQueryProvider.defaultSeed]. Everything
 * here is fake, offline, and test-only: no real UTxOs, no network, no funds, no secrets.
 *
 * The guided flow restores the cited test-only
 * [org.sarmidev.kardano.playground.TestWalletFixture] mnemonic and queries the active provider for
 * *that wallet's own* self-generated testnet address. `:provider`'s default seed has no UTxOs for
 * that address, so before this block the mock flow stopped at "no UTxOs" before the Build/Sign
 * steps. To let the default mock mode demonstrate the full Wallet -> Funds -> Build -> Sign flow
 * offline, [buildMockQueryProvider] seeds exactly that restored address with deterministic fake
 * ADA-only UTxOs, on top of `:provider`'s existing default seed.
 *
 * Submission is intentionally left honest: the mock
 * [org.sarmidev.kardano.provider.InMemoryTxSubmitProvider] still always reports "submission not
 * supported" and is not changed here — mock mode never fakes a network submission.
 */
internal object PlaygroundMockSampleData {

    /**
     * Builds the Playground's default mock [ChainQueryProvider]: `:provider`'s
     * [InMemoryChainQueryProvider.defaultSeed] (which keeps
     * [InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS] funded and
     * [InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY] empty for the Provider explorer), plus fake
     * ADA-only UTxOs for the demo wallet's own restored address so mock mode can run the guided
     * flow.
     *
     * Restores [TestWalletFixture] via [ReadOnlyWallet.restore] (always [Network.TESTNET]) purely
     * to obtain that address. If the restore fails, the demo-wallet entry is simply omitted and
     * the bare default seed is used, so this never throws — mock mode then degrades to the earlier
     * honest "no UTxOs" behavior rather than crashing.
     */
    fun buildMockQueryProvider(): ChainQueryProvider {
        val seed = LinkedHashMap<Address, List<Utxo>>()
        seed.putAll(InMemoryChainQueryProvider.defaultSeed())
        demoWalletAddress()?.let { walletAddress ->
            seed[walletAddress] = demoWalletFakeUtxos()
        }
        return InMemoryChainQueryProvider(utxosByAddress = seed)
    }

    /** The fixture wallet's own self-generated testnet address, or `null` if restore fails. */
    private fun demoWalletAddress(): Address? =
        ReadOnlyWallet.restore(TestWalletFixture.words, Network.TESTNET).getOrNull()?.address

    /**
     * Two deterministic, fake, ADA-only UTxOs (`hasNativeAssets = false`) for the demo wallet
     * address: 5 ADA + 8 ADA = 13 ADA, comfortably above the fixed 2 ADA demo payment plus its
     * fee and change output. Fake/test-only sample data — not real on-chain outputs, and the
     * transaction hashes are fixed sentinel bytes, not real transaction ids.
     */
    private fun demoWalletFakeUtxos(): List<Utxo> = listOf(
        fakeAdaOnlyUtxo(seedByte = 0xA1, outputIndex = 0L, lovelace = 5_000_000L),
        fakeAdaOnlyUtxo(seedByte = 0xB2, outputIndex = 1L, lovelace = 8_000_000L),
    )

    /**
     * Builds one fake ADA-only [Utxo] from hardcoded, known-valid inputs: a 32-byte transaction
     * hash filled with [seedByte], the given [outputIndex], and an ADA [lovelace] amount. The
     * inputs are constants chosen to be in range, so the underlying factories always succeed; a
     * failure would be a programming error in this sample data rather than runtime input handling.
     */
    private fun fakeAdaOnlyUtxo(seedByte: Int, outputIndex: Long, lovelace: Long): Utxo {
        val txHash = requireNotNull(
            TxHash.of(ByteArray(TxHash.SIZE) { seedByte.toByte() }).getOrNull(),
        ) { "fake demo TxHash bytes are hardcoded to a valid length" }
        val ref = requireNotNull(UtxoRef.of(txHash, outputIndex).getOrNull()) {
            "fake demo output index is hardcoded non-negative"
        }
        val coin = requireNotNull(Lovelace.of(lovelace).getOrNull()) {
            "fake demo lovelace amount is hardcoded non-negative"
        }
        return Utxo(ref, Value(coin))
    }
}
