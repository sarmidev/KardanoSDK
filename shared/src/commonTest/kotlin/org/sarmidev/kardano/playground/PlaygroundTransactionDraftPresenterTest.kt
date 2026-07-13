package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.encoding.cbor.CborError
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.provider.ProtocolParameters
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.provider.Value
import org.sarmidev.kardano.tx.TransactionBuildRequest
import org.sarmidev.kardano.tx.TransactionBuilder
import org.sarmidev.kardano.tx.TransactionOutput
import org.sarmidev.kardano.tx.TxBuildError
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Unit tests for [PlaygroundPresenter]'s unsigned transaction-draft checkpoint (Block 1.9c).
 *
 * [PlaygroundPresenter.mapTransactionDraftResult] and [PlaygroundPresenter.presentTxBuildError]
 * are both non-suspend and native-free: they format an already-built `:tx`
 * [org.sarmidev.kardano.tx.TransactionDraft]/[TxBuildError] constructed directly (via
 * [TransactionBuilder.build] with fake UTxOs, exactly as `:tx`'s own `TransactionBuilderTest`
 * does), without restoring a mnemonic (which reaches `:crypto`'s native derivation backend) or
 * querying a real provider. That means this test can run on every target, including
 * `:shared:testAndroidHostTest` — see [PlaygroundWalletPresenterTest]'s KDoc for the same
 * native-backend constraint, and [PlaygroundTransactionDraftDesktopTest] for the end-to-end
 * ([PlaygroundPresenter.presentTransactionDraft]) coverage that does reach it.
 *
 * Addresses reuse the CIP-19 "Test vectors" testnet base/enterprise (type-00/type-01) addresses
 * already cited verbatim in `:core`'s `AddressTest` and reused by `:tx`'s
 * `TransactionBuilderTest` — not invented for this test.
 * https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md
 */
class PlaygroundTransactionDraftPresenterTest {

    private companion object {
        const val TESTNET_TYPE_00 =
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"
        const val TESTNET_TYPE_01 =
            "addr_test1zrphkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gten0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgsxj90mg"
    }

    private fun address(bech32: String): Address =
        requireNotNull(Address.parse(bech32).getOrNull()) { "expected a valid test address" }

    private fun lovelace(value: Long): Lovelace = requireNotNull(Lovelace.of(value).getOrNull())

    private fun fakeUtxo(fill: Byte, index: Long, amount: Long): Utxo {
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { fill }).getOrNull())
        val ref = requireNotNull(UtxoRef.of(txHash, index).getOrNull())
        return Utxo(ref, Value(lovelace(amount)))
    }

    /** Realistic, illustrative protocol parameters (same values as the `:provider` fixture). */
    private fun realisticParams(): ProtocolParameters = InMemoryChainQueryProvider.DEFAULT_PROTOCOL_PARAMETERS

    private fun buildRequest(
        candidateInputs: List<Utxo>,
        paymentAmount: Long = 5_000_000L,
        protocolParameters: ProtocolParameters = realisticParams(),
    ): TransactionBuildRequest = TransactionBuildRequest(
        network = Network.TESTNET,
        candidateInputs = candidateInputs,
        payment = TransactionOutput(address(TESTNET_TYPE_00), lovelace(paymentAmount)),
        changeAddress = address(TESTNET_TYPE_01),
        protocolParameters = protocolParameters,
        ttl = null,
    )

    // --- mapTransactionDraftResult: Ok (successful draft presentation) ---

    @Test
    fun okDraft_producesSuccessRowsWithCountsFeeAndBodyPreview() {
        val candidateInputs = listOf(
            fakeUtxo(0x11, 0L, 7_000_000L),
            fakeUtxo(0x22, 1L, 3_500_000L),
        )
        val draftResult = TransactionBuilder.build(buildRequest(candidateInputs))
        val draft = assertIs<KardanoResult.Ok<org.sarmidev.kardano.tx.TransactionDraft>>(draftResult).value

        val presentation = PlaygroundPresenter.mapTransactionDraftResult(draftResult)

        val success = assertIs<TransactionDraftPresentation.Success>(presentation)
        val rowByLabel = success.rows.associate { it.label to it.value }
        assertEquals(draft.selectedInputs.size.toString(), rowByLabel["Selected inputs"])
        assertEquals(draft.outputs.size.toString(), rowByLabel["Outputs"])
        assertEquals("${draft.fee.value} lovelace", rowByLabel["Fee"])
        assertEquals("${draft.bodyCbor().size} bytes", rowByLabel["Body size"])
        assertTrue(rowByLabel.containsKey("Body CBOR (preview)"), "expected a body CBOR preview row")
        assertEquals("Unsigned draft — not signed, not submitted", rowByLabel["Status"])
    }

    @Test
    fun okDraft_withChange_includesChangeRow() {
        val candidateInputs = listOf(fakeUtxo(0x33, 0L, 20_000_000L))
        val draftResult = TransactionBuilder.build(buildRequest(candidateInputs))
        val draft = assertIs<KardanoResult.Ok<org.sarmidev.kardano.tx.TransactionDraft>>(draftResult).value
        assertEquals(2, draft.outputs.size, "expected a payment output plus a change output")

        val presentation = PlaygroundPresenter.mapTransactionDraftResult(draftResult)

        val success = assertIs<TransactionDraftPresentation.Success>(presentation)
        val rowByLabel = success.rows.associate { it.label to it.value }
        assertEquals("${draft.outputs[1].amount.value} lovelace", rowByLabel["Change"])
    }

    // --- mapTransactionDraftResult: Err (insufficient funds / builder error presentation) ---

    @Test
    fun insufficientFundsError_producesFailureWithRequiredAndAvailable() {
        val candidateInputs = listOf(fakeUtxo(0x44, 0L, 1_000_000L))
        val draftResult = TransactionBuilder.build(buildRequest(candidateInputs, paymentAmount = 5_000_000L))
        val err = assertIs<KardanoResult.Err<TxBuildError>>(draftResult)
        assertIs<TxBuildError.InsufficientFunds>(err.error)

        val presentation = PlaygroundPresenter.mapTransactionDraftResult(draftResult)

        val failure = assertIs<TransactionDraftPresentation.Failure>(presentation)
        assertTrue(failure.message.contains("Insufficient funds"), "got: ${failure.message}")
    }

    @Test
    fun emptyCandidateInputs_producesFailure_distinguishableAsNoUtxos() {
        val draftResult = TransactionBuilder.build(buildRequest(candidateInputs = emptyList()))
        val err = assertIs<KardanoResult.Err<TxBuildError>>(draftResult)
        assertIs<TxBuildError.NoInputs>(err.error)

        val presentation = PlaygroundPresenter.mapTransactionDraftResult(draftResult)

        val failure = assertIs<TransactionDraftPresentation.Failure>(presentation)
        assertTrue(failure.message.contains("UTxOs"), "got: ${failure.message}")
    }

    // --- presentTxBuildError: every variant maps to a distinguishable message ---

    @Test
    fun presentTxBuildError_noInputs_mentionsUtxos() {
        val msg = PlaygroundPresenter.presentTxBuildError(TxBuildError.NoInputs)
        assertTrue(msg.contains("UTxOs"), "got: $msg")
    }

    @Test
    fun presentTxBuildError_noOutputs_isDistinctMessage() {
        val msg = PlaygroundPresenter.presentTxBuildError(TxBuildError.NoOutputs)
        assertTrue(msg.contains("output", ignoreCase = true), "got: $msg")
    }

    @Test
    fun presentTxBuildError_invalidProtocolParameters_containsFieldAndValue() {
        val msg = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.InvalidProtocolParameters("coinsPerUtxoByte", -1L),
        )
        assertTrue(msg.contains("coinsPerUtxoByte"), "got: $msg")
        assertTrue(msg.contains("-1"), "got: $msg")
    }

    @Test
    fun presentTxBuildError_feeEstimateDidNotConverge_containsBothFees() {
        val msg = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.FeeEstimateDidNotConverge(encodedFee = 200_000L, recomputedFee = 200_500L),
        )
        assertTrue(msg.contains("200000"), "got: $msg")
        assertTrue(msg.contains("200500"), "got: $msg")
    }

    @Test
    fun presentTxBuildError_insufficientFunds_containsRequiredAndAvailable() {
        val msg = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.InsufficientFunds(required = 5_000_000L, available = 1_000_000L),
        )
        assertTrue(msg.contains("5000000"), "got: $msg")
        assertTrue(msg.contains("1000000"), "got: $msg")
    }

    @Test
    fun presentTxBuildError_invalidOutputAmount_containsAmountAndMinRequired() {
        val msg = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.InvalidOutputAmount(amount = 100L, minRequired = 969_750L),
        )
        assertTrue(msg.contains("100"), "got: $msg")
        assertTrue(msg.contains("969750"), "got: $msg")
    }

    @Test
    fun presentTxBuildError_changeBelowMinimum_containsChangeAndMinRequired() {
        val msg = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.ChangeBelowMinimum(change = 100L, minRequired = 969_750L),
        )
        assertTrue(msg.contains("100"), "got: $msg")
        assertTrue(msg.contains("969750"), "got: $msg")
    }

    @Test
    fun presentTxBuildError_exceedsMaxTxSize_containsSizeAndMax() {
        val msg = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.ExceedsMaxTxSize(size = 20_000L, max = 16_384L),
        )
        assertTrue(msg.contains("20000"), "got: $msg")
        assertTrue(msg.contains("16384"), "got: $msg")
    }

    @Test
    fun presentTxBuildError_feeCalculationOverflow_hasDescription() {
        val msg = PlaygroundPresenter.presentTxBuildError(TxBuildError.FeeCalculationOverflow)
        assertTrue(msg.contains("overflow", ignoreCase = true), "got: $msg")
    }

    @Test
    fun presentTxBuildError_serialization_delegatesToCborError() {
        val msg = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.Serialization(CborError.InputTooLong(max = 1, actual = 2)),
        )
        assertTrue(msg.contains("Serialization error"), "got: $msg")
    }

    @Test
    fun presentTxBuildError_networkMismatch_containsExpectedAndActual() {
        val msg = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.NetworkMismatch(Network.MAINNET, Network.TESTNET),
        )
        assertTrue(msg.contains("MAINNET"), "got: $msg")
        assertTrue(msg.contains("TESTNET"), "got: $msg")
    }

    @Test
    fun presentTxBuildError_unsupportedFeature_containsDetail() {
        val msg = PlaygroundPresenter.presentTxBuildError(
            TxBuildError.UnsupportedFeature("multi-asset value"),
        )
        assertTrue(msg.contains("multi-asset value"), "got: $msg")
    }

    @Test
    fun presentTxBuildError_duplicateInput_hasDescription() {
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { 0x55 }).getOrNull())
        val ref = requireNotNull(UtxoRef.of(txHash, 0L).getOrNull())
        val msg = PlaygroundPresenter.presentTxBuildError(TxBuildError.DuplicateInput(ref))
        assertTrue(msg.contains("Duplicate", ignoreCase = true), "got: $msg")
    }
}
