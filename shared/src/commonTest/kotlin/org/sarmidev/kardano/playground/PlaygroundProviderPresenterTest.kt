package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.provider.ProtocolParameters
import org.sarmidev.kardano.provider.ProviderError
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.provider.Value
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Unit tests for the provider-section mapping in [PlaygroundPresenter].
 *
 * The suspend entry points delegate to the non-suspend `mapUtxosResult` / `mapParamsResult`
 * and `presentProviderError`, so these tests construct [KardanoResult] / [ProviderError]
 * values directly and stay free of coroutines, matching the direct-variant style of
 * [PlaygroundPresenterTest].
 */
class PlaygroundProviderPresenterTest {

    private fun fakeUtxo(): Utxo {
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { 0x11 }).getOrNull())
        val ref = requireNotNull(UtxoRef.of(txHash, 0L).getOrNull())
        val coin = requireNotNull(Lovelace.of(1_000_000L).getOrNull())
        return Utxo(ref, Value(coin))
    }

    @Test
    fun mapUtxosResultSuccessProducesRows() {
        val presentation = PlaygroundPresenter.mapUtxosResult(
            KardanoResult.Ok(listOf(fakeUtxo())),
        )
        val success = assertIs<ProviderUtxosPresentation.Success>(presentation)
        assertEquals(1, success.rows.size)
        assertTrue(success.rows.first().value.contains("lovelace"))
    }

    @Test
    fun mapUtxosResultEmptyProducesNoUtxosNotFailure() {
        val presentation = PlaygroundPresenter.mapUtxosResult(
            KardanoResult.Ok(emptyList()),
        )
        assertIs<ProviderUtxosPresentation.NoUtxos>(presentation)
    }

    @Test
    fun mapUtxosResultErrorProducesFailure() {
        val presentation = PlaygroundPresenter.mapUtxosResult(
            KardanoResult.Err(
                ProviderError.NetworkMismatch(Network.MAINNET, Network.TESTNET),
            ),
        )
        val failure = assertIs<ProviderUtxosPresentation.Failure>(presentation)
        assertTrue(failure.message.contains("Network mismatch"))
    }

    @Test
    fun mapParamsResultSuccessProducesRows() {
        val params = ProtocolParameters(
            minFeeCoefficient = 44L,
            minFeeConstant = 155_381L,
            keyDeposit = 2_000_000L,
            poolDeposit = 500_000_000L,
            maxTxSize = 16_384L,
            coinsPerUtxoByte = 4_310L,
        )
        val presentation = PlaygroundPresenter.mapParamsResult(KardanoResult.Ok(params))
        val success = assertIs<ProviderParamsPresentation.Success>(presentation)
        assertEquals(6, success.rows.size)
    }

    @Test
    fun presentProviderErrorCoversAllVariants() {
        val messages = listOf(
            ProviderError.Transport("boom"),
            ProviderError.RemoteStatus(500),
            ProviderError.RemoteStatus(403, "forbidden"),
            ProviderError.NotFound,
            ProviderError.Deserialization("bad json"),
            ProviderError.RateLimited,
            ProviderError.NetworkMismatch(Network.TESTNET, Network.MAINNET),
            ProviderError.ResultTruncated(fetchedCount = 4, cap = 4),
            ProviderError.Unknown,
        ).map { PlaygroundPresenter.presentProviderError(it) }

        assertEquals(9, messages.size)
        assertTrue(messages.all { it.isNotBlank() })
    }

    @Test
    fun presentProviderErrorRemoteStatusWithDetailContainsCodeAndDetail() {
        val msg = PlaygroundPresenter.presentProviderError(
            ProviderError.RemoteStatus(403, "forbidden"),
        )
        assertTrue(msg.contains("403"), "got: $msg")
        assertTrue(msg.contains("forbidden"), "got: $msg")
    }

    @Test
    fun presentProviderErrorRemoteStatusWithoutDetailContainsCodeOnly() {
        val msg = PlaygroundPresenter.presentProviderError(ProviderError.RemoteStatus(500, null))
        assertTrue(msg.contains("500"), "got: $msg")
        assertFalse(msg.contains("("), "got: $msg")
    }

    @Test
    fun presentProviderErrorResultTruncatedMentionsCapAndFetchedCount() {
        val msg = PlaygroundPresenter.presentProviderError(
            ProviderError.ResultTruncated(fetchedCount = 4, cap = 4),
        )
        assertTrue(msg.contains("4"), "got: $msg")
        assertTrue(msg.contains("further output"), "got: $msg")
        assertTrue(msg.contains("not returned"), "got: $msg")
    }
}
