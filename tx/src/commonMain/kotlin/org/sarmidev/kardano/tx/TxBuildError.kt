package org.sarmidev.kardano.tx

import org.sarmidev.kardano.encoding.cbor.CborError
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.UtxoRef

/**
 * A typed error produced when building or serializing a Cardano transaction body.
 *
 * Returned via [org.sarmidev.kardano.KardanoResult] (no throwing, per the KMP error policy).
 * This is the full error surface sketched in ADR-0014 §8 for Block 1.9b, plus four additions
 * beyond that sketch: [DuplicateInput] (required by ADR-0014 §4's duplicate-input rejection
 * rule, which §8's illustrative sketch did not name a dedicated variant for), [NoOutputs] (a
 * minimal transaction body, ADR-0014 §2, must have at least one output; discovered while
 * implementing the Block 1.9b-1 serializer), and two Block 1.9b-2 review-fix additions:
 * [InvalidProtocolParameters] ([org.sarmidev.kardano.provider.ProtocolParameters] is a plain
 * data class of `Long` fields with no non-negativity invariant of its own, so
 * [TransactionBuilder.build] cannot assume a caller-supplied instance is well-formed) and
 * [FeeEstimateDidNotConverge] (the fee/change fixed-point loop's final conservative rebuild,
 * ADR-0014 §6, must itself be checked — see that variant's KDoc).
 *
 * **Reachability.** [TransactionBodySerializer.serialize] (Block 1.9b-1) only orders,
 * validates, and encodes an already fully specified [TransactionBodyRequest]; it performs no
 * coin selection and computes no fee, so it alone can only produce [NoInputs], [NoOutputs],
 * [Serialization], [NetworkMismatch], and [DuplicateInput]. [TransactionBuilder.build] (Block
 * 1.9b-2) additionally performs largest-first coin selection and the fee/change fixed-point
 * loop (ADR-0014 §6-7), which is what makes [InsufficientFunds], [InvalidOutputAmount],
 * [ChangeBelowMinimum], [ExceedsMaxTxSize], [FeeCalculationOverflow],
 * [InvalidProtocolParameters], and [FeeEstimateDidNotConverge] reachable. [UnsupportedFeature]
 * (Block 1.11d, narrowed in 1.11d-2) became reachable once
 * [org.sarmidev.kardano.provider.Value] gained the
 * [org.sarmidev.kardano.provider.Value.hasNativeAssets] presence flag: [TransactionBuilder.build]
 * drops every candidate input carrying it before coin selection, and returns
 * [UnsupportedFeature] only if that leaves no candidates at all — not whenever any single input
 * carried native assets, which would otherwise decline a request that a mix of ADA-only and
 * native-asset UTxOs could still satisfy. Each variant's KDoc below states which entry point
 * produces it.
 *
 * Block 1.10b (ADR-0015 §5) extends this same sealed type — rather than adding a sibling
 * sealed type — for witness/full-`transaction` assembly errors: [InvalidVerificationKeyLength],
 * [InvalidSignatureLength], and [EmptyWitnessSet]. `:tx` stays crypto-free (ADR-0015 §1): these
 * validate byte lengths and structure only, never cryptographic correctness.
 */
public sealed interface TxBuildError {

    /**
     * The candidate input list is empty.
     *
     * Reachable today: [TransactionBodySerializer.serialize] rejects an empty
     * [TransactionBodyRequest.inputs] list — the ADR-0014 §2 MVP transaction body requires
     * one or more inputs. Also produced by the coin-selection builder (Block 1.9b-2) when its
     * own candidate list is empty.
     */
    public data object NoInputs : TxBuildError

    /**
     * The outputs list is empty.
     *
     * Reachable today: [TransactionBodySerializer.serialize] rejects an empty
     * [TransactionBodyRequest.outputs] list — a minimal transaction body (ADR-0014 §2) must
     * have at least one output. See the type-level KDoc for why this variant extends the
     * ADR-0014 §8 sketch rather than contradicting it.
     */
    public data object NoOutputs : TxBuildError

    /**
     * A [org.sarmidev.kardano.provider.ProtocolParameters] field [TransactionBuilder] depends
     * on is negative.
     *
     * Reachable today: [TransactionBuilder.build] validates
     * [org.sarmidev.kardano.provider.ProtocolParameters.minFeeCoefficient],
     * [org.sarmidev.kardano.provider.ProtocolParameters.minFeeConstant],
     * [org.sarmidev.kardano.provider.ProtocolParameters.maxTxSize], and
     * [org.sarmidev.kardano.provider.ProtocolParameters.coinsPerUtxoByte] before doing any
     * selection or fee/min-ADA arithmetic with them.
     * [org.sarmidev.kardano.provider.ProtocolParameters] is a plain data class of `Long`
     * fields with no invariant of its own (any provider implementation, including a
     * misconfigured or malicious one, could hand `:tx` a negative value), and a negative
     * `coinsPerUtxoByte` in particular would silently defeat the min-ADA check
     * ([InvalidOutputAmount]/[ChangeBelowMinimum]) rather than fail loudly.
     *
     * @property field the name of the invalid [org.sarmidev.kardano.provider.ProtocolParameters]
     *   property.
     * @property value the rejected (negative) value.
     */
    public data class InvalidProtocolParameters(
        public val field: String,
        public val value: Long,
    ) : TxBuildError

    /**
     * The fee/change fixed-point loop (ADR-0014 §6) did not converge, and even the final
     * conservative rebuild — with `fee = maxOf(lastFee, lastFeeNext)` — turned out to need a
     * higher fee than the one it encoded into the body.
     *
     * This guards a real edge case, not a defensive-only check: [TransactionBuilder]'s
     * conservative rebuild can itself need to select additional inputs to cover the larger
     * trial fee, and each additional input adds another witness to the size estimate — which
     * can push the *next* fee estimate past the very value the rebuilt body encoded. Rather
     * than return a [TransactionDraft] whose encoded fee (body field `2`) is a known
     * under-estimate of what the real estimate demands, [TransactionBuilder.build] reports
     * this instead.
     *
     * Reachable today: see the type-level KDoc.
     *
     * @property encodedFee the fee the final rebuilt [TransactionDraft.bodyCbor] actually
     *   encodes.
     * @property recomputedFee the higher fee re-estimated from that same rebuilt body.
     */
    public data class FeeEstimateDidNotConverge(
        public val encodedFee: Long,
        public val recomputedFee: Long,
    ) : TxBuildError

    /**
     * The selected inputs cannot cover `payment + fee` with no candidates left to add.
     *
     * Reachable today: [TransactionBuilder.build] returns this once its largest-first
     * selection has exhausted [TransactionBuildRequest.candidateInputs] without reaching the
     * required total. Since Block 1.11d-2, any candidate with
     * [org.sarmidev.kardano.provider.Value.hasNativeAssets] set is dropped before selection
     * even starts, so [available] here only ever totals the ADA-only candidates — a
     * native-asset UTxO's lovelace is never counted toward covering the shortfall.
     *
     * @property required the lovelace amount required.
     * @property available the lovelace amount the (ADA-only, native-asset-filtered) candidate
     *   inputs actually total.
     */
    public data class InsufficientFunds(
        public val required: Long,
        public val available: Long,
    ) : TxBuildError

    /**
     * The payment output amount is below its computed minimum-ADA (min-UTxO).
     *
     * Reachable today: [TransactionBuilder.build] checks
     * [TransactionBuildRequest.payment] against its own min-ADA (ADR-0014 §7) before any coin
     * selection.
     *
     * @property amount the rejected output amount.
     * @property minRequired the computed minimum-ADA for that output.
     */
    public data class InvalidOutputAmount(
        public val amount: Long,
        public val minRequired: Long,
    ) : TxBuildError

    /**
     * The computed change is non-zero but below the change output's minimum-ADA (min-UTxO).
     *
     * Reachable today: [TransactionBuilder.build] rejects positive dust change (ADR-0014 §7)
     * rather than silently folding it into the fee.
     *
     * @property change the rejected change amount.
     * @property minRequired the computed minimum-ADA for the change output.
     */
    public data class ChangeBelowMinimum(
        public val change: Long,
        public val minRequired: Long,
    ) : TxBuildError

    /**
     * The estimated transaction size exceeds `ProtocolParameters.maxTxSize`.
     *
     * Reachable today: [TransactionBuilder.build] is the first `:tx` code that estimates
     * whole-transaction size (ADR-0014 §6), and checks it against
     * [org.sarmidev.kardano.provider.ProtocolParameters.maxTxSize] on every fee-loop attempt.
     *
     * @property size the estimated transaction size, in bytes.
     * @property max the maximum transaction size allowed.
     */
    public data class ExceedsMaxTxSize(
        public val size: Long,
        public val max: Long,
    ) : TxBuildError

    /**
     * A `Long` overflow occurred in the fee/change arithmetic.
     *
     * Reachable today: [TransactionBuilder.build] returns this instead of truncating or
     * wrapping whenever its checked coin-selection, fee, size, or min-ADA arithmetic would
     * overflow a signed `Long`.
     */
    public data object FeeCalculationOverflow : TxBuildError

    /**
     * Encoding the `transaction_body` CBOR failed.
     *
     * Reachable today — for example when [TransactionBodyRequest.ttl] is negative (an unsigned
     * CBOR field cannot hold it), or a collection exceeds `:core`'s named limits.
     *
     * @property error the underlying `:core` [CborError].
     */
    public data class Serialization(public val error: CborError) : TxBuildError

    /**
     * An output address's [Network] disagrees with the request's declared network.
     *
     * Reachable today: [TransactionBodySerializer.serialize] checks every output address
     * against [TransactionBodyRequest.network]; [TransactionBuilder.build] separately checks
     * [TransactionBuildRequest.payment]'s and [TransactionBuildRequest.changeAddress]'s network
     * against [TransactionBuildRequest.network] before any coin selection.
     *
     * @property expected the network the request declared.
     * @property actual the network resolved from the offending output's address.
     */
    public data class NetworkMismatch(
        public val expected: Network,
        public val actual: Network,
    ) : TxBuildError

    /**
     * A supplied input or output uses a feature this MVP does not support.
     *
     * Reachable today (Block 1.11d, narrowed in 1.11d-2): [TransactionBuilder.build] first
     * drops every [TransactionBuildRequest.candidateInputs] entry with
     * [org.sarmidev.kardano.provider.Value.hasNativeAssets] set — Phase 1 never spends a
     * native-asset UTxO (ADR-0014 §8) — and only returns this if that filtering leaves **no**
     * candidates at all. A request with a mix of ADA-only and native-asset candidates instead
     * builds from the ADA-only ones (or reports [InsufficientFunds] against just their total,
     * if that total cannot cover `payment + fee`); no ledger-rule engine decides which
     * native-asset inputs to keep, because none of them are ever kept. Quantities, policy ids,
     * and asset names are never inspected — [TransactionBuilder] only reads the boolean
     * presence flag.
     *
     * @property detail a human-readable description of the unsupported feature.
     */
    public data class UnsupportedFeature(public val detail: String) : TxBuildError

    /**
     * Two supplied inputs referred to the same `(transaction_id, index)` pair.
     *
     * Reachable today: [TransactionBodySerializer.serialize] rejects duplicate inputs per
     * ADR-0014 §4. See the type-level KDoc for why this variant extends the ADR-0014 §8
     * sketch rather than contradicting it.
     *
     * @property ref the duplicated input reference.
     */
    public data class DuplicateInput(public val ref: UtxoRef) : TxBuildError

    /**
     * A supplied verification key (`vkey`) was not exactly [VerificationKeyWitness.VKEY_BYTES]
     * bytes.
     *
     * Reachable today: [VerificationKeyWitness.of] (Block 1.10b, ADR-0015 §3/§5) rejects any
     * other length before assembling a witness — `:tx` never hashes, signs, or trims a `vkey`
     * to fit.
     *
     * @property expectedBytes the exact number of bytes expected ([VerificationKeyWitness.VKEY_BYTES]).
     * @property actualBytes the number of bytes actually supplied.
     */
    public data class InvalidVerificationKeyLength(
        public val expectedBytes: Int,
        public val actualBytes: Int,
    ) : TxBuildError

    /**
     * A supplied signature was not exactly [VerificationKeyWitness.SIGNATURE_BYTES] bytes.
     *
     * Reachable today: [VerificationKeyWitness.of] (Block 1.10b, ADR-0015 §3/§5) rejects any
     * other length before assembling a witness.
     *
     * @property expectedBytes the exact number of bytes expected
     *   ([VerificationKeyWitness.SIGNATURE_BYTES]).
     * @property actualBytes the number of bytes actually supplied.
     */
    public data class InvalidSignatureLength(
        public val expectedBytes: Int,
        public val actualBytes: Int,
    ) : TxBuildError

    /**
     * A [TransactionWitnessSet] was assembled with no verification-key witnesses.
     *
     * Reachable today: [TransactionWitnessSet.of] (Block 1.10b) rejects an empty witness list —
     * a "signed" transaction with zero witnesses is not meaningfully signed for this MVP's
     * single-key ADA-only scope (ADR-0015 §2).
     */
    public data object EmptyWitnessSet : TxBuildError
}
