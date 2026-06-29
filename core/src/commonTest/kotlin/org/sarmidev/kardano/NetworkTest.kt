package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

class NetworkTest {

    @Test
    fun fromIdResolvesTestnet() {
        val result = Network.fromId(0)
        assertEquals(KardanoResult.Ok(Network.TESTNET), result)
    }

    @Test
    fun fromIdResolvesMainnet() {
        val result = Network.fromId(1)
        assertEquals(KardanoResult.Ok(Network.MAINNET), result)
    }

    @Test
    fun networkIdsMatchProtocolValues() {
        assertEquals(0, Network.TESTNET.id)
        assertEquals(1, Network.MAINNET.id)
    }

    @Test
    fun enumNamesArePresent() {
        assertEquals("TESTNET", Network.TESTNET.name)
        assertEquals("MAINNET", Network.MAINNET.name)
    }

    @Test
    fun fromIdRejectsUnsupportedIds() {
        for (id in listOf(-1, 2, 15, Int.MAX_VALUE, Int.MIN_VALUE)) {
            val result = Network.fromId(id)
            val err = assertIs<KardanoResult.Err<NetworkError>>(result)
            val unsupported = assertIs<NetworkError.UnsupportedNetworkId>(err.error)
            assertEquals(id, unsupported.id)
        }
    }
}
