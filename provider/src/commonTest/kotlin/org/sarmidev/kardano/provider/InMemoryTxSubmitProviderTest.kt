package org.sarmidev.kardano.provider

import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.primitives.Network
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

/**
 * Contract tests for [InMemoryTxSubmitProvider], exercising the [TxSubmitProvider] surface
 * through the mock. It never submits anything; there is no fake success path to test for.
 */
class InMemoryTxSubmitProviderTest {

    @Test
    fun submitAlwaysReturnsSubmissionNotSupported() = runTest {
        val provider = InMemoryTxSubmitProvider()
        val transactionCbor = ByteArray(64) { it.toByte() }

        val result = provider.submit(transactionCbor)

        val err = assertIs<KardanoResult.Err<SubmitError>>(result)
        assertEquals(SubmitError.SubmissionNotSupported, err.error)
    }

    @Test
    fun submitWithEmptyBytesAlsoReturnsSubmissionNotSupported() = runTest {
        val provider = InMemoryTxSubmitProvider()

        val result = provider.submit(ByteArray(0))

        val err = assertIs<KardanoResult.Err<SubmitError>>(result)
        assertEquals(SubmitError.SubmissionNotSupported, err.error)
    }

    @Test
    fun defaultNetworkIsTestnet() {
        val provider = InMemoryTxSubmitProvider()

        assertEquals(Network.TESTNET, provider.network)
    }

    @Test
    fun networkIsConfigurable() {
        val provider = InMemoryTxSubmitProvider(network = Network.MAINNET)

        assertEquals(Network.MAINNET, provider.network)
    }
}
