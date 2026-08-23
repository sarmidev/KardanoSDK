package org.sarmidev.kardano.tx

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.provider.ProtocolParameters
import org.sarmidev.kardano.provider.Utxo

/**
 * Builds a minimal, unsigned, single-payment ADA transaction from candidate UTxOs (ADR-0014
 * §6-7): selects inputs, estimates the fee, decides change, and delegates the actual
 * `transaction_body` encoding to [TransactionBodySerializer].
 *
 * **Fee is an estimate, not a final value.** [computeFee] follows the linear
 * `minFeeCoefficient * txSize + minFeeConstant` formula (ADR-0014 §6) against a *sized, not
 * yet built*, witness set — [estimateTxSize] accounts for one Ed25519 vkey witness per
 * selected input without ever constructing one, because signing does not exist in `:tx` yet.
 * The returned [TransactionDraft.fee] is exactly what was encoded into the body, but it is
 * only correct if the eventual real witness set has one vkey witness per input and no other
 * witnesses (no scripts, no multi-sig) — true for the Block 1.9 MVP, but this estimate must be
 * revisited once real signing lands (Phase 1 Block 1.10).
 *
 * **Non-goals** (ADR-0014 §2, restated): no signing, no witness construction, no transaction
 * id hashing, no submission. [TransactionDraft] is a structural artifact only.
 */
public object TransactionBuilder {

    /**
     * Bounded fixed-point iteration cap for the fee/size loop (ADR-0014 §6: "e.g. ≤ 8"). If
     * the loop has not converged after this many attempts, [build] takes the conservative
     * (larger) of the last two fee estimates and rebuilds once more with it — see [build].
     */
    private const val MAX_FEE_ITERATIONS: Int = 8

    /**
     * The Babbage/Conway min-UTxO constant overhead, in bytes (ADR-0014 §7): `minADA =
     * (160 + serializedOutputSizeInBytes) * coinsPerUtxoByte`.
     */
    private const val MIN_UTXO_CONSTANT_OVERHEAD: Long = 160L

    /** Fixed transaction wrapper element count: `[body, witness_set, bool, aux_data]`. */
    private const val WRAPPER_ELEMENT_COUNT: Long = 4L

    /**
     * Encoded size of one `vkeywitness = [vkey, signature]`: array(2) header (1 byte) + a
     * 32-byte bytestring (2-byte head + 32 payload) + a 64-byte bytestring (2-byte head + 64
     * payload) = 1 + 34 + 66 = 101 bytes.
     */
    private const val VKEY_WITNESS_SIZE: Long = 101L

    /** Witness-set map overhead: a 1-entry map header (1 byte) + key `0` (1 byte). */
    private const val WITNESS_SET_MAP_OVERHEAD: Long = 2L

    /** CBOR `bool` (the transaction's validity flag) is always exactly 1 byte. */
    private const val VALIDITY_FLAG_SIZE: Long = 1L

    /** CBOR `null` (the auxiliary-data placeholder) is always exactly 1 byte. */
    private const val AUXILIARY_DATA_SIZE: Long = 1L

    /**
     * Builds a [TransactionDraft] for [request].
     *
     * Order of checks (ADR-0014 §6-7, extended by Block 1.11d/1.11d-2): [TxBuildError.InvalidProtocolParameters]
     * if [TransactionBuildRequest.protocolParameters] has a negative
     * `minFeeCoefficient`/`minFeeConstant`/`maxTxSize`/`coinsPerUtxoByte`, then network
     * validation, then [TxBuildError.NoInputs] if
     * [TransactionBuildRequest.candidateInputs] is empty. [TransactionBuildRequest.candidateInputs]
     * is then filtered to drop every candidate with
     * [org.sarmidev.kardano.provider.Value.hasNativeAssets] set (Phase 1 stays ADA-only and never
     * spends a native-asset UTxO), and [TxBuildError.UnsupportedFeature] is returned if that
     * filtering leaves no candidates at all — only then, not whenever *any* input carried native
     * assets. Otherwise building proceeds normally from the filtered, ADA-only candidates, so a
     * wallet with a mix of ADA-only and native-asset UTxOs can still build/sign/submit using just
     * the ADA-only ones; if the ADA-only ones alone cannot cover `payment + fee`, the usual
     * [TxBuildError.InsufficientFunds] is returned (its `available` total reflects only the
     * ADA-only candidates, since the native-asset ones were never counted — their count and
     * total are instead reported separately via `excludedNativeAssetUtxoCount`/
     * `excludedNativeAssetLovelace`, W8-2). Next,
     * [TxBuildError.InvalidOutputAmount] if the payment itself is below its min-ADA. It then
     * runs the largest-first coin-selection / fee fixed-point loop (see the type-level KDoc) —
     * which can itself fail with [TxBuildError.FeeEstimateDidNotConverge] if even the final
     * conservative rebuild under-estimates the fee it encodes — and finally applies the change
     * policy: omit change when it is exactly zero, emit it when it is at or above its own
     * min-ADA, or reject with [TxBuildError.ChangeBelowMinimum] when it is positive dust.
     * [TxBuildError.DuplicateInput] and [TxBuildError.Serialization] are passed through
     * verbatim from [TransactionBodySerializer.serialize] if it ever reports them (in practice
     * unreachable here: [request]'s candidates cannot form a duplicate pair unless the
     * caller's own [TransactionBuildRequest.candidateInputs] already contained one).
     *
     * @return [KardanoResult.Ok] with the built [TransactionDraft], or [KardanoResult.Err] with
     *   the first applicable [TxBuildError]. Never throws.
     */
    public fun build(request: TransactionBuildRequest): KardanoResult<TransactionDraft, TxBuildError> {
        validateProtocolParameters(request.protocolParameters)?.let { return KardanoResult.Err(it) }

        val paymentNetwork = request.payment.address.network
        if (paymentNetwork != request.network) {
            return KardanoResult.Err(TxBuildError.NetworkMismatch(request.network, paymentNetwork))
        }
        val changeNetwork = request.changeAddress.network
        if (changeNetwork != request.network) {
            return KardanoResult.Err(TxBuildError.NetworkMismatch(request.network, changeNetwork))
        }

        if (request.candidateInputs.isEmpty()) {
            return KardanoResult.Err(TxBuildError.NoInputs)
        }

        // Phase 1 never spends a native-asset UTxO (ADR-0014 §8, Block 1.11d), but a wallet with
        // a mix of ADA-only and native-asset UTxOs must still be able to build from the ADA-only
        // ones (Block 1.11d-2) rather than have the whole request declined because one candidate
        // happened to carry a token.
        val adaOnlyCandidates = request.candidateInputs.filterNot { it.value.hasNativeAssets }
        val nativeAssetCandidates = request.candidateInputs.filter { it.value.hasNativeAssets }
        if (adaOnlyCandidates.isEmpty()) {
            return KardanoResult.Err(
                TxBuildError.UnsupportedFeature(
                    "all ${request.candidateInputs.size} candidate UTxO(s) carry native " +
                        "assets/tokens; Phase 1 requires at least one ADA-only UTxO to build a " +
                        "transaction",
                ),
            )
        }

        val paymentMinAda = when (
            val r = minAdaFor(request.payment, request.protocolParameters.coinsPerUtxoByte)
        ) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err -> return r
        }
        if (request.payment.amount.value < paymentMinAda) {
            return KardanoResult.Err(
                TxBuildError.InvalidOutputAmount(request.payment.amount.value, paymentMinAda),
            )
        }

        val selection = InputSelection(adaOnlyCandidates, nativeAssetCandidates)

        var fee = request.protocolParameters.minFeeConstant
        var attempt = when (val r = evaluateAttempt(request, selection, fee)) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err -> return r
        }
        var iterations = 1
        while (attempt.feeNext != fee && iterations < MAX_FEE_ITERATIONS) {
            fee = attempt.feeNext
            attempt = when (val r = evaluateAttempt(request, selection, fee)) {
                is KardanoResult.Ok -> r.value
                is KardanoResult.Err -> return r
            }
            iterations++
        }
        if (attempt.feeNext != fee) {
            // Did not converge within MAX_FEE_ITERATIONS. Per ADR-0014 §6, take the
            // conservative (larger) of the last two estimates and rebuild exactly once more
            // with it — never loop unbounded chasing an oscillating fixed point.
            val conservativeFee = maxOf(fee, attempt.feeNext)
            attempt = when (val r = evaluateAttempt(request, selection, conservativeFee)) {
                is KardanoResult.Ok -> r.value
                is KardanoResult.Err -> return r
            }
            // The rebuild itself can need to select additional inputs to cover
            // conservativeFee, and each additional input adds another witness to the size
            // estimate — which can push this re-estimate past conservativeFee again. Never
            // return a draft whose encoded fee is a known under-estimate.
            if (attempt.feeNext > conservativeFee) {
                return KardanoResult.Err(
                    TxBuildError.FeeEstimateDidNotConverge(conservativeFee, attempt.feeNext),
                )
            }
        }

        if (attempt.change > 0L) {
            val changeLovelace = when (val r = Lovelace.of(attempt.change)) {
                is KardanoResult.Ok -> r.value
                is KardanoResult.Err -> return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)
            }
            val changeOutput = TransactionOutput(request.changeAddress, changeLovelace)
            val changeMinAda = when (
                val r = minAdaFor(changeOutput, request.protocolParameters.coinsPerUtxoByte)
            ) {
                is KardanoResult.Ok -> r.value
                is KardanoResult.Err -> return r
            }
            if (attempt.change < changeMinAda) {
                return KardanoResult.Err(TxBuildError.ChangeBelowMinimum(attempt.change, changeMinAda))
            }
        }

        return KardanoResult.Ok(attempt.draft)
    }

    /**
     * Validates the [org.sarmidev.kardano.provider.ProtocolParameters] fields [build] relies
     * on for fee, size, and min-ADA arithmetic, returning the first
     * [TxBuildError.InvalidProtocolParameters] found, or `null` if all are non-negative.
     *
     * [org.sarmidev.kardano.provider.ProtocolParameters] is a plain data class of `Long`
     * fields with no non-negativity invariant of its own; a negative `coinsPerUtxoByte` in
     * particular would silently defeat the min-ADA check rather than fail loudly, so this must
     * run before any of that arithmetic.
     */
    private fun validateProtocolParameters(params: ProtocolParameters): TxBuildError? {
        if (params.minFeeCoefficient < 0L) {
            return TxBuildError.InvalidProtocolParameters("minFeeCoefficient", params.minFeeCoefficient)
        }
        if (params.minFeeConstant < 0L) {
            return TxBuildError.InvalidProtocolParameters("minFeeConstant", params.minFeeConstant)
        }
        if (params.maxTxSize < 0L) {
            return TxBuildError.InvalidProtocolParameters("maxTxSize", params.maxTxSize)
        }
        if (params.coinsPerUtxoByte < 0L) {
            return TxBuildError.InvalidProtocolParameters("coinsPerUtxoByte", params.coinsPerUtxoByte)
        }
        return null
    }

    /** The outcome of building and sizing a body at one candidate [fee][feeNext]-seeking fee. */
    private class FeeAttempt(
        val draft: TransactionDraft,
        val feeNext: Long,
        val change: Long,
    )

    /**
     * Builds a candidate [TransactionDraft] at a specific trial [fee], growing [selection] with
     * more largest-first inputs if [fee] is not yet covered, and returns both that draft and
     * the next fee estimate computed from its actual encoded size.
     *
     * This does **not** reject dust change (ADR-0014 §7) — that policy is applied once, in
     * [build], against the final accepted attempt, not against every intermediate trial (an
     * intermediate trial's change is not final: it can still shrink or grow as [fee] itself is
     * still converging).
     */
    private fun evaluateAttempt(
        request: TransactionBuildRequest,
        selection: InputSelection,
        fee: Long,
    ): KardanoResult<FeeAttempt, TxBuildError> {
        val required = addExact(request.payment.amount.value, fee)
            ?: return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)
        when (val r = selection.ensureCovers(required)) {
            is KardanoResult.Err -> return r
            is KardanoResult.Ok -> Unit
        }

        val spentBeforeFee = subtractExact(selection.selectedSum, request.payment.amount.value)
            ?: return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)
        val change = subtractExact(spentBeforeFee, fee)
            ?: return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)

        val outputs = if (change == 0L) {
            listOf(request.payment)
        } else {
            val changeLovelace = when (val r = Lovelace.of(change)) {
                is KardanoResult.Ok -> r.value
                is KardanoResult.Err -> return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)
            }
            listOf(request.payment, TransactionOutput(request.changeAddress, changeLovelace))
        }

        val feeLovelace = when (val r = Lovelace.of(fee)) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err -> return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)
        }

        val bodyRequest = TransactionBodyRequest(
            network = request.network,
            inputs = selection.refs(),
            outputs = outputs,
            fee = feeLovelace,
            ttl = request.ttl,
        )
        val draft = when (val r = TransactionBodySerializer.serialize(bodyRequest)) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err -> return r
        }

        val txSize = estimateTxSize(draft.bodyCbor().size, selection.inputCount)
            ?: return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)
        if (txSize > request.protocolParameters.maxTxSize) {
            return KardanoResult.Err(
                TxBuildError.ExceedsMaxTxSize(txSize, request.protocolParameters.maxTxSize),
            )
        }

        val feeNext = computeFee(
            request.protocolParameters.minFeeCoefficient,
            txSize,
            request.protocolParameters.minFeeConstant,
        ) ?: return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)

        return KardanoResult.Ok(FeeAttempt(draft, feeNext, change))
    }

    /**
     * Grows a largest-first, ledger-order-tie-broken selection from [candidates] on demand
     * (ADR-0014 §6): each call to [ensureCovers] adds just enough of the remaining candidates,
     * in that fixed order, to reach the requested total, never re-ordering or dropping a
     * previously selected input.
     *
     * [excludedNativeAssetCandidates] (W8-2) are never selected from — they are carried only so
     * [ensureCovers] can attach their count/total to [TxBuildError.InsufficientFunds] if
     * selection exhausts [candidates] without reaching the required total, so a caller can
     * distinguish "genuinely insufficient ADA" from "value exists but is locked in excluded
     * native-asset UTxOs."
     */
    private class InputSelection(
        candidates: List<Utxo>,
        private val excludedNativeAssetCandidates: List<Utxo> = emptyList(),
    ) {
        private val sortedCandidates: List<Utxo> = candidates.sortedWith(candidateOrder)
        private val selected: MutableList<Utxo> = mutableListOf()

        var selectedSum: Long = 0L
            private set

        val inputCount: Int
            get() = selected.size

        /** Adds candidates, largest-first, until [selectedSum] is at least [required]. */
        fun ensureCovers(required: Long): KardanoResult<Unit, TxBuildError> {
            while (selectedSum < required) {
                if (selected.size >= sortedCandidates.size) {
                    return KardanoResult.Err(
                        TxBuildError.InsufficientFunds(
                            required = required,
                            available = selectedSum,
                            excludedNativeAssetUtxoCount = excludedNativeAssetCandidates.size,
                            excludedNativeAssetLovelace = excludedNativeAssetCandidates.fold(0L) { sum, utxo ->
                                addExact(sum, utxo.value.coin.value) ?: Long.MAX_VALUE
                            },
                        ),
                    )
                }
                val next = sortedCandidates[selected.size]
                val newSum = addExact(selectedSum, next.value.coin.value)
                    ?: return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)
                selected.add(next)
                selectedSum = newSum
            }
            return KardanoResult.Ok(Unit)
        }

        fun refs() = selected.map { it.ref }

        private companion object {
            /** Largest-first by amount; ties broken by [LedgerInputOrder] (ADR-0014 §6). */
            val candidateOrder: Comparator<Utxo> =
                compareByDescending<Utxo> { it.value.coin.value }
                    .then(compareBy(LedgerInputOrder) { it.ref })
        }
    }

    /**
     * `minADA = (160 + serializedOutputSizeInBytes) * coinsPerUtxoByte` (ADR-0014 §7), where
     * `serializedOutputSizeInBytes` is [output]'s exact encoded size via
     * [TxCborSupport.encodeOutput] — the same encoding [TransactionBodySerializer] uses.
     */
    private fun minAdaFor(
        output: TransactionOutput,
        coinsPerUtxoByte: Long,
    ): KardanoResult<Long, TxBuildError> {
        val encoded = when (val r = Cbor.encode(TxCborSupport.encodeOutput(output))) {
            is KardanoResult.Ok -> r.value
            is KardanoResult.Err -> return KardanoResult.Err(TxBuildError.Serialization(r.error))
        }
        val overhead = addExact(MIN_UTXO_CONSTANT_OVERHEAD, encoded.size.toLong())
            ?: return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)
        val minAda = multiplyExact(overhead, coinsPerUtxoByte)
            ?: return KardanoResult.Err(TxBuildError.FeeCalculationOverflow)
        return KardanoResult.Ok(minAda)
    }

    /**
     * `fee = minFeeCoefficient * txSize + minFeeConstant` (ADR-0014 §6), or `null` on overflow.
     */
    private fun computeFee(minFeeCoefficient: Long, txSize: Long, minFeeConstant: Long): Long? {
        val variableFee = multiplyExact(minFeeCoefficient, txSize) ?: return null
        return addExact(variableFee, minFeeConstant)
    }

    /**
     * Estimates the full `transaction` wrapper size (ADR-0014 §6) from an actual [bodySize]
     * (the real `transaction_body` CBOR byte count) plus the sized-but-unbuilt witness set for
     * [inputCount] vkey witnesses, a wrapper array header, a validity-flag byte, and an
     * auxiliary-data-null byte. Returns `null` on overflow.
     */
    private fun estimateTxSize(bodySize: Int, inputCount: Int): Long? {
        val wrapperHeader = headSize(WRAPPER_ELEMENT_COUNT)
        val witnessSet = witnessSetSize(inputCount.toLong()) ?: return null
        val withBody = addExact(wrapperHeader, bodySize.toLong()) ?: return null
        val withWitness = addExact(withBody, witnessSet) ?: return null
        val withValidity = addExact(withWitness, VALIDITY_FLAG_SIZE) ?: return null
        return addExact(withValidity, AUXILIARY_DATA_SIZE)
    }

    /**
     * `witness_set = {0: [vkeywitness, ...]}` sized for [inputCount] vkey witnesses (one per
     * selected input, ADR-0014 §6): map overhead + the inner array's own header (computed
     * generically via [headSize], not hardcoded for `inputCount < 24`) + `inputCount` fixed-size
     * witnesses. Returns `null` on overflow.
     */
    private fun witnessSetSize(inputCount: Long): Long? {
        val witnessesTotal = multiplyExact(VKEY_WITNESS_SIZE, inputCount) ?: return null
        val withHeadSize = addExact(headSize(inputCount), witnessesTotal) ?: return null
        return addExact(WITNESS_SET_MAP_OVERHEAD, withHeadSize)
    }

    /**
     * The canonical CBOR shortest-form array/map head size for an element/entry count [n]
     * (ADR-0014 §6): the same rule `:core`'s own encoder implements (1 byte for `n < 24`, 2 for
     * `24..255`, 3 for `256..65_535`, 5 for `65_536..4_294_967_295`, 9 beyond). `:core`'s `Cbor`
     * does not expose this sizing rule directly, so it is reimplemented here; this function
     * never encodes anything itself, it only sizes a header `:core` would produce for the same
     * count.
     */
    private fun headSize(n: Long): Long = when {
        n < 24L -> 1L
        n <= 0xFFL -> 2L
        n <= 0xFFFFL -> 3L
        n <= 0xFFFF_FFFFL -> 5L
        else -> 9L
    }
}
