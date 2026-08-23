package org.sarmidev.kardano.provider.blockfrost

import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.MockRequestHandleScope
import io.ktor.client.engine.mock.respond
import io.ktor.client.request.HttpRequestData
import io.ktor.client.request.HttpResponseData
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import kotlinx.coroutines.test.runTest
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.provider.ProviderError
import kotlin.coroutines.cancellation.CancellationException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Tests for [BlockfrostChainQueryProvider] using a Ktor [MockEngine] and the sanitized
 * [BlockfrostFixtures]. No real network, no keys.
 *
 * Addresses use CIP-19 test vectors (verbatim from the spec): a testnet enterprise address
 * for the preprod-bound provider and a mainnet enterprise address for the network-mismatch
 * case.
 */
class BlockfrostChainQueryProviderTest {

    private companion object {
        // CIP-19 "Test vectors" (verbatim).
        const val TESTNET_ADDRESS =
            "addr_test1vz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerspjrlsz"
        const val MAINNET_ADDRESS =
            "addr1vx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzers66hrl8"
    }

    // ----- getUtxos -----

    @Test
    fun getUtxosMapsSinglePageAndKeepsOnlyLovelace() = runTest {
        val provider = providerReturning(BlockfrostFixtures.UTXOS_SINGLE_PAGE)
        val utxos = ok(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertEquals(2, utxos.size)
        assertEquals(0L, utxos[0].ref.outputIndex)
        assertEquals(5_000_000L, utxos[0].value.coin.value)
        // Lovelace-only entry: hasNativeAssets stays false.
        assertFalse(utxos[0].value.hasNativeAssets, "lovelace-only UTxO must not flag native assets")
        // Second entry carried a native asset; only the lovelace component is summed, but
        // (Block 1.11d) its presence is now flagged rather than silently dropped.
        assertEquals(1L, utxos[1].ref.outputIndex)
        assertEquals(2_000_000L, utxos[1].value.coin.value)
        assertTrue(utxos[1].value.hasNativeAssets, "lovelace + token UTxO must flag native assets")
    }

    @Test
    fun getUtxosLovelaceOnlyEntryHasNativeAssetsFalse() = runTest {
        val provider = providerReturning(BlockfrostFixtures.UTXOS_LOVELACE_ONLY)
        val utxos = ok(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertEquals(1, utxos.size)
        assertEquals(3_000_000L, utxos[0].value.coin.value)
        assertFalse(utxos[0].value.hasNativeAssets)
    }

    @Test
    fun getUtxosLovelacePlusTokenEntryHasNativeAssetsTrue() = runTest {
        val provider = providerReturning(BlockfrostFixtures.UTXOS_LOVELACE_PLUS_MULTIPLE_TOKENS)
        val utxos = ok(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertEquals(1, utxos.size)
        // Only the lovelace component is summed; multiple non-lovelace units still flag once.
        assertEquals(3_000_000L, utxos[0].value.coin.value)
        assertTrue(utxos[0].value.hasNativeAssets)
    }

    @Test
    fun getUtxosPaginatesUntilShortPage() = runTest {
        // Page 1 is a full page (100), page 2 is short (1), so paging stops after page 2.
        val provider = provider { request ->
            when (request.url.parameters["page"]) {
                "1" -> json(BlockfrostFixtures.utxoPage(100))
                "2" -> json(BlockfrostFixtures.utxoPage(1))
                else -> json("[]")
            }
        }
        val utxos = ok(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertEquals(101, utxos.size)
    }

    @Test
    fun getUtxosTreats404AsEmpty() = runTest {
        val provider = provider { json("{\"status_code\":404}", HttpStatusCode.NotFound) }
        val utxos = ok(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertTrue(utxos.isEmpty())
    }

    @Test
    fun getUtxosFailsOnNetworkMismatchWithoutCallingBackend() = runTest {
        var called = false
        val provider = provider {
            called = true
            json("[]")
        }
        val error = err(provider.getUtxos(address(MAINNET_ADDRESS)))
        assertTrue(error is ProviderError.NetworkMismatch)
        assertEquals(false, called)
    }

    @Test
    fun getUtxosMapsBadHashToDeserialization() = runTest {
        val provider = providerReturning(BlockfrostFixtures.UTXOS_BAD_HASH)
        val error = err(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertTrue(error is ProviderError.Deserialization)
    }

    // ----- getProtocolParameters -----

    @Test
    fun getProtocolParametersMapsFields() = runTest {
        val provider = providerReturning(BlockfrostFixtures.EPOCH_PARAMETERS)
        val params = ok(provider.getProtocolParameters())
        assertEquals(44L, params.minFeeCoefficient)
        assertEquals(155_381L, params.minFeeConstant)
        assertEquals(2_000_000L, params.keyDeposit)
        assertEquals(500_000_000L, params.poolDeposit)
        assertEquals(16_384L, params.maxTxSize)
        assertEquals(4_310L, params.coinsPerUtxoByte)
    }

    @Test
    fun getProtocolParametersMapsMalformedNumberToDeserialization() = runTest {
        val provider = providerReturning(BlockfrostFixtures.EPOCH_PARAMETERS_MALFORMED)
        val error = err(provider.getProtocolParameters())
        assertTrue(error is ProviderError.Deserialization)
    }

    @Test
    fun getProtocolParametersMapsInvalidJsonToDeserialization() = runTest {
        val provider = providerReturning("not json at all")
        val error = err(provider.getProtocolParameters())
        assertTrue(error is ProviderError.Deserialization)
    }

    // ----- getTip -----

    @Test
    fun getTipMapsBlock() = runTest {
        val provider = providerReturning(BlockfrostFixtures.BLOCK_LATEST)
        val tip = ok(provider.getTip())
        assertEquals(50_000_000L, tip.slot)
        assertEquals(2_000_000L, tip.blockHeight)
    }

    @Test
    fun getTipMaps404ToNotFound() = runTest {
        val provider = provider { json("{}", HttpStatusCode.NotFound) }
        val error = err(provider.getTip())
        assertTrue(error is ProviderError.NotFound)
    }

    // ----- error mapping -----

    @Test
    fun maps429ToRateLimited() = runTest {
        val provider = provider { json("{}", HttpStatusCode.TooManyRequests) }
        val error = err(provider.getTip())
        assertTrue(error is ProviderError.RateLimited)
    }

    @Test
    fun mapsForbiddenToRemoteStatusWithParsedDetail() = runTest {
        val provider = provider { json(BlockfrostFixtures.FORBIDDEN_BODY, HttpStatusCode.Forbidden) }
        val error = err(provider.getProtocolParameters())
        assertTrue(error is ProviderError.RemoteStatus)
        assertEquals(403, error.code)
        assertTrue(error.detail?.contains("sanitized", ignoreCase = true) == true)
        assertFalse(
            error.detail?.contains("test-project-id") == true,
            "detail must not contain the project id: ${error.detail}",
        )
    }

    @Test
    fun maps500ToRemoteStatusWithParsedDetail() = runTest {
        val provider = provider {
            json(BlockfrostFixtures.SERVER_ERROR_BODY, HttpStatusCode.InternalServerError)
        }
        val error = err(provider.getTip())
        assertTrue(error is ProviderError.RemoteStatus)
        assertEquals(500, error.code)
        assertTrue(error.detail?.contains("sanitized", ignoreCase = true) == true)
        assertFalse(
            error.toString().contains("test-project-id"),
            "error rendering must not contain the project id: $error",
        )
    }

    @Test
    fun mapsMalformedErrorBodyToRemoteStatusWithRawDetail() = runTest {
        val provider = provider {
            json(BlockfrostFixtures.MALFORMED_ERROR_BODY, HttpStatusCode.Forbidden)
        }
        val error = err(provider.getTip())
        assertTrue(error is ProviderError.RemoteStatus)
        assertEquals(403, error.code)
        assertEquals(BlockfrostFixtures.MALFORMED_ERROR_BODY, error.detail)
    }

    @Test
    fun mapsBlankErrorBodyToRemoteStatusWithNullDetail() = runTest {
        val provider = provider { json("   ", HttpStatusCode.InternalServerError) }
        val error = err(provider.getTip())
        assertTrue(error is ProviderError.RemoteStatus)
        assertEquals(500, error.code)
        assertNull(error.detail)
    }

    @Test
    fun getUtxosRejectsOversizedPageBeforeAccumulation() = runTest {
        var mappedFollowUp = false
        val pagination = UtxoPaginationPolicy(pageCount = 2, maxPages = 2)
        val provider = provider(pagination = pagination) { request ->
            when (request.url.parameters["page"]) {
                "1" -> json(BlockfrostFixtures.utxoPage(3))
                else -> {
                    mappedFollowUp = true
                    json(BlockfrostFixtures.utxoPage(2))
                }
            }
        }
        val error = err(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertTrue(error is ProviderError.Deserialization, "expected Deserialization, got: $error")
        assertTrue(error.detail.contains("3"), "got: ${error.detail}")
        assertTrue(error.detail.contains("2"), "got: ${error.detail}")
        assertFalse(mappedFollowUp, "oversized first page must not continue pagination")
    }

    @Test
    fun getUtxosExactCapWithEmptyProbeReturnsOk() = runTest {
        var probeCount: String? = null
        var probePage: String? = null
        val pagination = UtxoPaginationPolicy(pageCount = 2, maxPages = 2)
        val provider = provider(pagination = pagination) { request ->
            when (request.url.parameters["page"]) {
                "1" -> json(BlockfrostFixtures.utxoPage(2))
                "2" -> json(BlockfrostFixtures.utxoPage(2))
                else -> {
                    probePage = request.url.parameters["page"]
                    probeCount = request.url.parameters["count"]
                    json("[]")
                }
            }
        }
        val utxos = ok(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertEquals(4, utxos.size)
        assertEquals("3", probePage)
        assertEquals("1", probeCount, "probe must request one item, not a full extra page")
    }

    @Test
    fun getUtxosExactCapWithNonEmptyProbeReturnsResultTruncated() = runTest {
        var probeCount: String? = null
        val pagination = UtxoPaginationPolicy(pageCount = 2, maxPages = 2)
        val provider = provider(pagination = pagination) { request ->
            when (request.url.parameters["page"]) {
                "1" -> json(BlockfrostFixtures.utxoPage(2))
                "2" -> json(BlockfrostFixtures.utxoPage(2))
                else -> {
                    probeCount = request.url.parameters["count"]
                    json(BlockfrostFixtures.utxoPage(1))
                }
            }
        }
        val error = err(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertTrue(error is ProviderError.ResultTruncated, "expected ResultTruncated, got: $error")
        assertEquals(4, error.fetchedCount)
        assertEquals(4, error.cap)
        assertEquals("1", probeCount)
    }

    @Test
    fun getUtxosExactCapProbeHttpFailureKeepsTypedError() = runTest {
        val pagination = UtxoPaginationPolicy(pageCount = 2, maxPages = 2)
        val provider = provider(pagination = pagination) { request ->
            when (request.url.parameters["page"]) {
                "1" -> json(BlockfrostFixtures.utxoPage(2))
                "2" -> json(BlockfrostFixtures.utxoPage(2))
                else -> json(BlockfrostFixtures.SERVER_ERROR_BODY, HttpStatusCode.InternalServerError)
            }
        }
        val error = err(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertTrue(error is ProviderError.RemoteStatus, "expected RemoteStatus, got: $error")
        assertEquals(500, error.code)
    }

    @Test
    fun getUtxosReturnsOkWhenFinalPermittedPageIsShort() = runTest {
        val pagination = UtxoPaginationPolicy(pageCount = 2, maxPages = 2)
        val provider = provider(pagination = pagination) { request ->
            when (request.url.parameters["page"]) {
                "1" -> json(BlockfrostFixtures.utxoPage(2))
                "2" -> json(BlockfrostFixtures.utxoPage(1))
                else -> json("[]")
            }
        }
        val utxos = ok(provider.getUtxos(address(TESTNET_ADDRESS)))
        assertEquals(3, utxos.size)
    }

    @Test
    fun getTipRethrowsCancellationInsteadOfSwallowingIt() = runTest {
        val provider = provider { throw CancellationException("cancelled") }
        assertFailsWith<CancellationException> {
            provider.getTip()
        }
    }

    @Test
    fun getUtxosRethrowsCancellationInsteadOfSwallowingIt() = runTest {
        val provider = provider { throw CancellationException("cancelled") }
        assertFailsWith<CancellationException> {
            provider.getUtxos(address(TESTNET_ADDRESS))
        }
    }

    // ----- helpers -----

    private fun address(bech32: String): Address {
        val result = Address.parse(bech32)
        assertTrue(result is KardanoResult.Ok, "test address vector must parse: $bech32")
        return result.value
    }

    private fun MockRequestHandleScope.json(
        body: String,
        status: HttpStatusCode = HttpStatusCode.OK,
    ): HttpResponseData =
        respond(body, status, headersOf(HttpHeaders.ContentType, "application/json"))

    private fun provider(
        network: BlockfrostNetwork = BlockfrostNetwork.PREPROD,
        pagination: UtxoPaginationPolicy = UtxoPaginationPolicy.Default,
        handler: suspend MockRequestHandleScope.(HttpRequestData) -> HttpResponseData,
    ): BlockfrostChainQueryProvider {
        val config = BlockfrostConfig(projectId = "test-project-id", network = network)
        val client = HttpClient(MockEngine) {
            configureBlockfrost(config)
            engine { addHandler(handler) }
        }
        return BlockfrostChainQueryProvider(config, client, pagination)
    }

    private fun providerReturning(
        body: String,
        status: HttpStatusCode = HttpStatusCode.OK,
    ): BlockfrostChainQueryProvider = provider { json(body, status) }

    private fun <T> ok(result: KardanoResult<T, ProviderError>): T {
        assertTrue(result is KardanoResult.Ok, "expected Ok but was $result")
        return result.value
    }

    private fun err(result: KardanoResult<*, ProviderError>): ProviderError {
        assertTrue(result is KardanoResult.Err, "expected Err but was $result")
        return result.error
    }
}
