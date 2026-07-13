package org.sarmidev.kardano.tx

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.encoding.cbor.CborValue
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.provider.ProtocolParameters
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.provider.Value
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Structural tests for [TransactionBuilder], per ADR-0014 §9: results are inspected via the
 * public [TransactionDraft] API and, where the CDDL shape matters, decoded back through
 * `:core` [Cbor.decode]. No `transaction_body` golden bytes are invented.
 *
 * A few tests use a [ProtocolParameters] with `minFeeCoefficient = 0` (see [flatFeeParams]).
 * This is not a claim about real Cardano fees — it isolates the change/min-ADA decision
 * (ADR-0014 §7) from the size-dependent fee formula (ADR-0014 §6) so a test can require an
 * *exact* change amount without needing to duplicate `:core`'s CBOR byte-size accounting by
 * hand. Tests that only need "clearly enough"/"clearly too little" headroom instead use
 * [InMemoryChainQueryProvider.DEFAULT_PROTOCOL_PARAMETERS], exercising the real formula.
 *
 * Addresses reuse the CIP-19 "Test vectors" mainnet/testnet base (type-00/type-01) addresses
 * already cited verbatim in `:core`'s `AddressTest`
 * (`core/src/commonTest/kotlin/org/sarmidev/kardano/address/AddressTest.kt`) — not invented for
 * this test. https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md
 */
class TransactionBuilderTest {

    private companion object {
        const val TESTNET_TYPE_00 =
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"
        const val TESTNET_TYPE_01 =
            "addr_test1zrphkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gten0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgsxj90mg"
        const val MAINNET_TYPE_00 =
            "addr1qx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgse35a3x"

        const val DEFAULT_PAYMENT_AMOUNT = 5_000_000L
    }

    private fun address(bech32: String): Address =
        requireNotNull(Address.parse(bech32).getOrNull()) { "expected a valid test address" }

    private fun paymentAddress(): Address = address(TESTNET_TYPE_00)

    private fun changeAddress(): Address = address(TESTNET_TYPE_01)

    private fun txHash(fill: Byte): TxHash =
        requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { fill }).getOrNull())

    private fun utxoRef(fill: Byte, index: Long): UtxoRef =
        requireNotNull(UtxoRef.of(txHash(fill), index).getOrNull())

    private fun lovelace(value: Long): Lovelace = requireNotNull(Lovelace.of(value).getOrNull())

    private fun fakeUtxo(fill: Byte, index: Long, amount: Long): Utxo =
        Utxo(utxoRef(fill, index), Value(lovelace(amount)))

    /** A structural fixture UTxO flagged as carrying native assets (Block 1.11d). */
    private fun fakeNativeAssetUtxo(fill: Byte, index: Long, amount: Long): Utxo =
        Utxo(utxoRef(fill, index), Value(lovelace(amount), hasNativeAssets = true))

    private fun paymentOutput(amount: Long = DEFAULT_PAYMENT_AMOUNT): TransactionOutput =
        TransactionOutput(paymentAddress(), lovelace(amount))

    /** Realistic, illustrative protocol parameters (same values as the `:provider` fixture). */
    private fun realisticParams(): ProtocolParameters =
        InMemoryChainQueryProvider.DEFAULT_PROTOCOL_PARAMETERS

    /**
     * A `minFeeCoefficient = 0` variant of [realisticParams]: the fee is always exactly
     * [fee], regardless of transaction size, so a test can target an exact change amount
     * without duplicating `:core`'s CBOR byte-size accounting. See the class-level KDoc.
     */
    private fun flatFeeParams(fee: Long, coinsPerUtxoByte: Long = realisticParams().coinsPerUtxoByte): ProtocolParameters =
        realisticParams().copy(minFeeCoefficient = 0L, minFeeConstant = fee, coinsPerUtxoByte = coinsPerUtxoByte)

    private fun request(
        candidateInputs: List<Utxo>,
        payment: TransactionOutput = paymentOutput(),
        changeAddress: Address = changeAddress(),
        protocolParameters: ProtocolParameters = realisticParams(),
        network: Network = Network.TESTNET,
        ttl: Long? = null,
    ): TransactionBuildRequest = TransactionBuildRequest(
        network = network,
        candidateInputs = candidateInputs,
        payment = payment,
        changeAddress = changeAddress,
        protocolParameters = protocolParameters,
        ttl = ttl,
    )

    private fun decodedMap(draft: TransactionDraft): CborValue.CborMap {
        val decoded = assertIs<KardanoResult.Ok<CborValue>>(Cbor.decode(draft.bodyCbor()))
        return assertIs<CborValue.CborMap>(decoded.value)
    }

    @Test
    fun emptyCandidateInputsReturnsNoInputs() {
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(request(candidateInputs = emptyList())),
        )
        assertIs<TxBuildError.NoInputs>(err.error)
    }

    // --- ADA-only enforcement (Block 1.11d): candidate inputs carrying native assets ---

    @Test
    fun soleCandidateWithNativeAssetsReturnsUnsupportedFeature() {
        val nativeAssetUtxo = fakeNativeAssetUtxo(1, 0L, 50_000_000L)
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(request(candidateInputs = listOf(nativeAssetUtxo))),
        )
        val unsupported = assertIs<TxBuildError.UnsupportedFeature>(err.error)
        assertTrue(
            unsupported.detail.contains("native assets", ignoreCase = true),
            "got: ${unsupported.detail}",
        )
    }

    @Test
    fun mixedCandidateListWithOneNativeAssetUtxoIsRejectedEntirely() {
        // The architecture choice (ADR-0014 §8, Block 1.11d) is to reject the whole candidate
        // list, not to silently filter out just the flagged input(s): even though the
        // ADA-only fakeUtxo(2, ...) below could alone cover payment + fee, this proves the
        // native-asset input is not simply skipped from selection.
        val adaOnly = fakeUtxo(2, 0L, 50_000_000L)
        val nativeAssetUtxo = fakeNativeAssetUtxo(1, 0L, 50_000_000L)
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(request(candidateInputs = listOf(adaOnly, nativeAssetUtxo))),
        )
        assertIs<TxBuildError.UnsupportedFeature>(err.error)
    }

    @Test
    fun adaOnlyCandidatesStillBuildNormallyAlongsideNativeAssetCheck() {
        // Regression: the new check must not affect the existing ADA-only success path.
        val payment = paymentOutput()
        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBuilder.build(
                request(candidateInputs = listOf(fakeUtxo(1, 0L, payment.amount.value + 20_000_000L))),
            ),
        ).value
        assertEquals(1, draft.selectedInputs.size)
    }

    @Test
    fun negativeMinFeeCoefficientReturnsInvalidProtocolParameters() {
        val params = realisticParams().copy(minFeeCoefficient = -1L)
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(candidateInputs = listOf(fakeUtxo(1, 0L, 50_000_000L)), protocolParameters = params),
            ),
        )
        val invalid = assertIs<TxBuildError.InvalidProtocolParameters>(err.error)
        assertEquals("minFeeCoefficient", invalid.field)
        assertEquals(-1L, invalid.value)
    }

    @Test
    fun negativeMinFeeConstantReturnsInvalidProtocolParameters() {
        val params = realisticParams().copy(minFeeConstant = -1L)
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(candidateInputs = listOf(fakeUtxo(1, 0L, 50_000_000L)), protocolParameters = params),
            ),
        )
        val invalid = assertIs<TxBuildError.InvalidProtocolParameters>(err.error)
        assertEquals("minFeeConstant", invalid.field)
        assertEquals(-1L, invalid.value)
    }

    @Test
    fun negativeMaxTxSizeReturnsInvalidProtocolParameters() {
        val params = realisticParams().copy(maxTxSize = -1L)
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(candidateInputs = listOf(fakeUtxo(1, 0L, 50_000_000L)), protocolParameters = params),
            ),
        )
        val invalid = assertIs<TxBuildError.InvalidProtocolParameters>(err.error)
        assertEquals("maxTxSize", invalid.field)
        assertEquals(-1L, invalid.value)
    }

    @Test
    fun negativeCoinsPerUtxoByteCannotBypassMinAdaCheck() {
        // Before this check existed, a negative coinsPerUtxoByte made the computed min-ADA
        // negative, so even a 1,000 lovelace payment (obviously not a real min-ADA-covering
        // amount) would have passed `amount < minAda`. This proves that path is closed: the
        // request is rejected up front, before the min-ADA arithmetic ever runs.
        val tinyPayment = paymentOutput(amount = 1_000L)
        val params = realisticParams().copy(coinsPerUtxoByte = -1L)
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(fakeUtxo(1, 0L, 50_000_000L)),
                    payment = tinyPayment,
                    protocolParameters = params,
                ),
            ),
        )
        val invalid = assertIs<TxBuildError.InvalidProtocolParameters>(err.error)
        assertEquals("coinsPerUtxoByte", invalid.field)
        assertEquals(-1L, invalid.value)
    }

    @Test
    fun paymentBelowMinAdaReturnsInvalidOutputAmount() {
        val tinyPayment = paymentOutput(amount = 1_000L)
        val params = realisticParams().copy(coinsPerUtxoByte = 10_000_000L)
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(fakeUtxo(1, 0L, 50_000_000L)),
                    payment = tinyPayment,
                    protocolParameters = params,
                ),
            ),
        )
        val invalid = assertIs<TxBuildError.InvalidOutputAmount>(err.error)
        assertEquals(1_000L, invalid.amount)
        assertTrue(invalid.minRequired > 1_000L)
    }

    @Test
    fun insufficientFundsAfterFeeReturnsInsufficientFunds() {
        val payment = paymentOutput()
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(candidateInputs = listOf(fakeUtxo(1, 0L, payment.amount.value + 1L)), payment = payment),
            ),
        )
        assertIs<TxBuildError.InsufficientFunds>(err.error)
    }

    @Test
    fun largestFirstSelectionUsesDeterministicTieBreaker() {
        val preferred = utxoRef(3, 0L) // smaller ledger-order hash -> tie-break winner
        val other = utxoRef(5, 0L)
        // 7,000,000 leaves change comfortably above min-ADA once fee is deducted, so this
        // test fails only if the tie-break itself is wrong, not on an unrelated dust rejection.
        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(
                        Utxo(other, Value(lovelace(7_000_000L))),
                        Utxo(preferred, Value(lovelace(7_000_000L))),
                    ),
                ),
            ),
        ).value
        assertEquals(listOf(preferred), draft.selectedInputs)
    }

    @Test
    fun exactZeroChangeOmitsChangeOutput() {
        val payment = paymentOutput()
        val fee = 200_000L
        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(fakeUtxo(1, 0L, payment.amount.value + fee)),
                    payment = payment,
                    protocolParameters = flatFeeParams(fee),
                ),
            ),
        ).value
        assertEquals(fee, draft.fee.value)
        assertEquals(listOf(payment), draft.outputs)
    }

    @Test
    fun changeAtOrAboveMinAdaEmitsChangeOutput() {
        val payment = paymentOutput()
        val change = changeAddress()
        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(fakeUtxo(1, 0L, payment.amount.value + 20_000_000L)),
                    payment = payment,
                    changeAddress = change,
                ),
            ),
        ).value
        assertEquals(2, draft.outputs.size)
        assertEquals(payment, draft.outputs[0])
        assertEquals(change, draft.outputs[1].address)
        assertTrue(draft.outputs[1].amount.value > 0L)
    }

    @Test
    fun dustChangeBelowMinAdaReturnsChangeBelowMinimum() {
        val payment = paymentOutput()
        val fee = 200_000L
        val dust = 1_000L
        // The default coinsPerUtxoByte's min-ADA (~970K) comfortably exceeds this 1,000
        // lovelace of dust while staying well below the 5,000,000 lovelace payment, so only
        // the change output — not the payment output — is rejected.
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(fakeUtxo(1, 0L, payment.amount.value + fee + dust)),
                    payment = payment,
                    protocolParameters = flatFeeParams(fee),
                ),
            ),
        )
        val belowMin = assertIs<TxBuildError.ChangeBelowMinimum>(err.error)
        assertEquals(dust, belowMin.change)
        assertTrue(belowMin.minRequired > dust)
    }

    @Test
    fun maxTxSizeExceededReturnsExceedsMaxTxSize() {
        val payment = paymentOutput()
        val params = realisticParams().copy(maxTxSize = 10L)
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(fakeUtxo(1, 0L, payment.amount.value + 10_000_000L)),
                    payment = payment,
                    protocolParameters = params,
                ),
            ),
        )
        val exceeds = assertIs<TxBuildError.ExceedsMaxTxSize>(err.error)
        assertEquals(10L, exceeds.max)
        assertTrue(exceeds.size > 10L)
    }

    @Test
    fun feeOverflowReturnsFeeCalculationOverflow() {
        val payment = paymentOutput()
        val params = realisticParams().copy(minFeeCoefficient = 1L, minFeeConstant = Long.MAX_VALUE)
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(fakeUtxo(1, 0L, Long.MAX_VALUE)),
                    payment = payment,
                    protocolParameters = params,
                ),
            ),
        )
        assertIs<TxBuildError.FeeCalculationOverflow>(err.error)
    }

    @Test
    fun feeLoopNonConvergenceReturnsFeeEstimateDidNotConverge() {
        // A large minFeeCoefficient makes each additional selected input's witness expensive
        // relative to a filler UTxO's own value. Many equal, moderately small fillers are
        // needed to cover payment + fee, and each fresh batch pulled in during the fee loop
        // (and even during the ADR-0014 §6 final conservative rebuild itself) adds enough
        // witness weight to push the next fee estimate past what was just encoded — a genuine
        // non-convergence discovered by construction, not an invented golden byte sequence.
        val payment = paymentOutput()
        val fillers = (0 until 30).map { i -> fakeUtxo(i.toByte(), 0L, 900_000L) }
        val params = realisticParams().copy(minFeeCoefficient = 5_000L)
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(candidateInputs = fillers, payment = payment, protocolParameters = params),
            ),
        )
        val notConverged = assertIs<TxBuildError.FeeEstimateDidNotConverge>(err.error)
        assertTrue(notConverged.recomputedFee > notConverged.encodedFee)
    }

    @Test
    fun networkMismatchForPaymentAddressReturnsNetworkMismatch() {
        val mainnetPayment = TransactionOutput(address(MAINNET_TYPE_00), lovelace(DEFAULT_PAYMENT_AMOUNT))
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(fakeUtxo(1, 0L, 50_000_000L)),
                    payment = mainnetPayment,
                ),
            ),
        )
        val mismatch = assertIs<TxBuildError.NetworkMismatch>(err.error)
        assertEquals(Network.TESTNET, mismatch.expected)
        assertEquals(Network.MAINNET, mismatch.actual)
    }

    @Test
    fun networkMismatchForChangeAddressReturnsNetworkMismatch() {
        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(fakeUtxo(1, 0L, 50_000_000L)),
                    changeAddress = address(MAINNET_TYPE_00),
                ),
            ),
        )
        val mismatch = assertIs<TxBuildError.NetworkMismatch>(err.error)
        assertEquals(Network.TESTNET, mismatch.expected)
        assertEquals(Network.MAINNET, mismatch.actual)
    }

    @Test
    fun finalDraftBodyDecodesStructurallyThroughCoreDecode() {
        val payment = paymentOutput()
        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBuilder.build(
                request(candidateInputs = listOf(fakeUtxo(1, 0L, payment.amount.value + 20_000_000L)), payment = payment),
            ),
        ).value
        val keys = decodedMap(draft).entries().map { assertIs<CborValue.CborUnsigned>(it.key).value }
        assertEquals(listOf(0L, 1L, 2L), keys)
    }

    @Test
    fun finalFeeMatchesFeeEncodedInBodyField2() {
        val payment = paymentOutput()
        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBuilder.build(
                request(candidateInputs = listOf(fakeUtxo(1, 0L, payment.amount.value + 20_000_000L)), payment = payment),
            ),
        ).value
        val feeEntry = decodedMap(draft).entries()
            .first { (it.key as CborValue.CborUnsigned).value == 2L }
        val feeValue = assertIs<CborValue.CborUnsigned>(feeEntry.value)
        assertEquals(draft.fee.value, feeValue.value)
    }

    @Test
    fun selectedInputsInDraftAreLedgerOrdered() {
        val payment = paymentOutput()
        val a = utxoRef(9, 0L)
        val b = utxoRef(1, 0L)
        // Neither alone covers payment + fee, so both must be selected (and their combined
        // total leaves change comfortably above min-ADA); supplied out of ledger order to
        // prove the draft re-sorts them.
        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBuilder.build(
                request(
                    candidateInputs = listOf(
                        Utxo(a, Value(lovelace(3_500_000L))),
                        Utxo(b, Value(lovelace(3_500_000L))),
                    ),
                    payment = payment,
                ),
            ),
        ).value
        assertEquals(listOf(b, a), draft.selectedInputs)
    }

    @Test
    fun bodyCborRemainsDefensiveCopy() {
        val payment = paymentOutput()
        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBuilder.build(
                request(candidateInputs = listOf(fakeUtxo(1, 0L, payment.amount.value + 20_000_000L)), payment = payment),
            ),
        ).value

        val original = draft.bodyCbor()
        val mutable = draft.bodyCbor()
        mutable[0] = (mutable[0] + 1).toByte()

        assertEquals(original.toList(), draft.bodyCbor().toList())
        assertTrue(!mutable.contentEquals(draft.bodyCbor()))
    }
}
