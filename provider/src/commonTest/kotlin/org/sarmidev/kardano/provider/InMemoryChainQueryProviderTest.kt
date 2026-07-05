package org.sarmidev.kardano.provider

import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Network
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Contract tests for [InMemoryChainQueryProvider], exercising the [ChainQueryProvider]
 * surface through the mock. No real network, no funds; all data is the mock's fake seed.
 */
class InMemoryChainQueryProviderTest {

    private fun parse(address: String): Address =
        requireNotNull(Address.parse(address).getOrNull()) { "expected a valid test address" }

    @Test
    fun seededAddressReturnsFakeUtxos() = runTest {
        val provider = InMemoryChainQueryProvider()
        val address = parse(InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS)

        val result = provider.getUtxos(address)

        val ok = assertIs<KardanoResult.Ok<List<Utxo>>>(result)
        assertEquals(2, ok.value.size)
        assertTrue(ok.value.all { it.value.coin.value > 0L })
    }

    @Test
    fun emptySeedAddressReturnsEmptyListNotError() = runTest {
        val provider = InMemoryChainQueryProvider()
        val address = parse(InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY)

        val result = provider.getUtxos(address)

        val ok = assertIs<KardanoResult.Ok<List<Utxo>>>(result)
        assertTrue(ok.value.isEmpty())
    }

    @Test
    fun mismatchedNetworkReturnsNetworkMismatch() = runTest {
        // Provider bound to MAINNET, queried with a testnet address.
        val provider = InMemoryChainQueryProvider(network = Network.MAINNET)
        val address = parse(InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS)

        val result = provider.getUtxos(address)

        val err = assertIs<KardanoResult.Err<ProviderError>>(result)
        val mismatch = assertIs<ProviderError.NetworkMismatch>(err.error)
        assertEquals(Network.MAINNET, mismatch.expected)
        assertEquals(Network.TESTNET, mismatch.actual)
    }

    @Test
    fun protocolParametersReturnsSeededValues() = runTest {
        val provider = InMemoryChainQueryProvider()

        val result = provider.getProtocolParameters()

        val ok = assertIs<KardanoResult.Ok<ProtocolParameters>>(result)
        assertEquals(InMemoryChainQueryProvider.DEFAULT_PROTOCOL_PARAMETERS, ok.value)
    }

    @Test
    fun tipReturnsSeededValue() = runTest {
        val provider = InMemoryChainQueryProvider()

        val result = provider.getTip()

        val ok = assertIs<KardanoResult.Ok<ChainTip>>(result)
        assertEquals(InMemoryChainQueryProvider.DEFAULT_TIP, ok.value)
    }
}
