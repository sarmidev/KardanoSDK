package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.address.AddressError
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.encoding.cbor.CborError
import org.sarmidev.kardano.encoding.hex.Hex
import org.sarmidev.kardano.encoding.hex.HexError
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.ProtocolParameters
import org.sarmidev.kardano.provider.ProviderError
import org.sarmidev.kardano.provider.Utxo

// ---------------------------------------------------------------------------
// Display models — pure data, no Compose imports
// ---------------------------------------------------------------------------

/** A labeled key-value row for a structured result card. */
internal data class LabeledRow(val label: String, val value: String)

/** Result of presenting an [Address.parse] call. */
internal sealed interface AddressPresentation {
    data object Empty : AddressPresentation
    data class Success(val rows: List<LabeledRow>) : AddressPresentation
    data class Failure(val message: String) : AddressPresentation
}

/** Result of presenting a [Hex] encode or decode operation. */
internal sealed interface HexPresentation {
    data class EncodeSuccess(val hex: String) : HexPresentation
    data class DecodeSuccess(val byteCount: Int, val hex: String) : HexPresentation
    data class Failure(val message: String) : HexPresentation
}

/** Result of presenting a [Cbor] decode + re-encode pair. */
internal sealed interface CborPresentation {
    data class Success(val summary: String, val roundTripOk: Boolean) : CborPresentation
    data class Failure(val message: String) : CborPresentation
}

/** Result of presenting a [ChainQueryProvider.getUtxos] call (mock or live provider). */
internal sealed interface ProviderUtxosPresentation {
    data object Empty : ProviderUtxosPresentation
    data object Loading : ProviderUtxosPresentation
    data class Success(val rows: List<LabeledRow>) : ProviderUtxosPresentation
    data class NoUtxos(val message: String) : ProviderUtxosPresentation
    data class Failure(val message: String) : ProviderUtxosPresentation
}

/** Result of presenting a [ChainQueryProvider.getProtocolParameters] call. */
internal sealed interface ProviderParamsPresentation {
    data object Empty : ProviderParamsPresentation
    data object Loading : ProviderParamsPresentation
    data class Success(val rows: List<LabeledRow>) : ProviderParamsPresentation
    data class Failure(val message: String) : ProviderParamsPresentation
}

// ---------------------------------------------------------------------------
// Presenter — maps :core results to display models; no SDK logic of its own
// ---------------------------------------------------------------------------

/**
 * Maps results from `:core` APIs to [AddressPresentation], [HexPresentation], and
 * [CborPresentation] for display in [PlaygroundScreen].
 *
 * This object only formats and labels results. It never re-parses, re-validates, or
 * reimplements any protocol rule. All structural-validation semantics come from `:core`.
 *
 * This is sample/diagnostic code in `:shared`. It is not part of the SDK public API.
 */
internal object PlaygroundPresenter {

    /** Bytes of a credential hash shown as a short hex prefix in the UI. */
    private const val SHORT_HEX_PREFIX_BYTES: Int = 6

    // --- Address ---

    /**
     * Maps an [Address.parse] result to an [AddressPresentation].
     *
     * Structural validation only — [Address.parse] makes no claim about on-chain existence,
     * ownership, or spendability; this presenter carries the same limitation forward.
     */
    fun presentAddress(result: KardanoResult<Address, AddressError>): AddressPresentation =
        when (result) {
            is KardanoResult.Ok -> buildSuccess(result.value)
            is KardanoResult.Err -> AddressPresentation.Failure(presentAddressError(result.error))
        }

    private fun buildSuccess(address: Address): AddressPresentation.Success {
        val rows = buildList {
            add(LabeledRow("Network", address.network.name))
            add(LabeledRow("Type", address.type.name))
            add(LabeledRow("HRP", address.hrp.value))
            address.paymentCredential?.let { cred ->
                add(LabeledRow("Payment credential", cred.kind.name))
                add(LabeledRow("Payment hash (prefix)", shortHex(cred.hashBytes())))
            }
            address.stakeCredential?.let { cred ->
                add(LabeledRow("Stake credential", cred.kind.name))
                add(LabeledRow("Stake hash (prefix)", shortHex(cred.hashBytes())))
            }
            address.pointer?.let { ptr ->
                add(LabeledRow("Pointer slot", ptr.slot.toString()))
                add(LabeledRow("Pointer tx index", ptr.transactionIndex.toString()))
                add(LabeledRow("Pointer cert index", ptr.certificateIndex.toString()))
            }
        }
        return AddressPresentation.Success(rows)
    }

    /**
     * Maps an [AddressError] to a human-readable single-line message.
     *
     * Internal so tests can exercise all error variants by constructing them directly,
     * without needing a specific input string to trigger each one.
     */
    internal fun presentAddressError(error: AddressError): String = when (error) {
        is AddressError.Bech32 ->
            "Bech32 error: ${error.error}"
        is AddressError.InvalidBitConversion ->
            "Bit conversion error: ${error.error}"
        is AddressError.EmptyPayload ->
            "Empty payload: no header byte to inspect"
        is AddressError.UnsupportedAddressType ->
            "Unsupported address type (header nibble ${error.headerTypeNibble})"
        is AddressError.UnsupportedNetworkId ->
            "Unsupported network id: ${error.error}"
        is AddressError.HrpNetworkMismatch ->
            "HRP/network mismatch: hrp=${error.hrp.value}, header network=${error.headerNetwork.name}"
        is AddressError.HrpFamilyMismatch ->
            "HRP/family mismatch: hrp=${error.hrp.value}, type=${error.type.name}"
        is AddressError.InvalidPayloadLength ->
            "Invalid payload length: expected ${error.expected}, got ${error.actual} (type=${error.type.name})"
        is AddressError.InvalidCredentialLength ->
            "Invalid credential length: expected ${error.expected}, got ${error.actual}"
        is AddressError.TruncatedPointer ->
            "Pointer truncated: payload ended before all pointer fields were read"
        is AddressError.PointerValueOutOfRange ->
            "Pointer value out of range: field=${error.field.name}"
        is AddressError.NonCanonicalPointer ->
            "Non-canonical pointer encoding: field=${error.field.name}"
        is AddressError.TrailingPointerBytes ->
            "Trailing bytes after pointer: consumed ${error.consumed}, total ${error.actual}"
    }

    // --- Hex ---

    /**
     * Attempts to decode [input] as a hex string.
     *
     * Returns [HexPresentation.DecodeSuccess] with the byte count and re-encoded hex on
     * success, or [HexPresentation.Failure] on [HexError].
     */
    fun presentHexDecode(input: String): HexPresentation =
        when (val result = Hex.decode(input.trim())) {
            is KardanoResult.Ok -> {
                val bytes = result.value
                HexPresentation.DecodeSuccess(bytes.size, Hex.encode(bytes))
            }
            is KardanoResult.Err -> HexPresentation.Failure(presentHexError(result.error))
        }

    /**
     * Encodes [bytes] to canonical lowercase hex.
     */
    fun presentHexEncode(bytes: ByteArray): HexPresentation =
        HexPresentation.EncodeSuccess(Hex.encode(bytes))

    private fun presentHexError(error: HexError): String = when (error) {
        is HexError.InputTooLong -> "Input too long: ${error.actual} chars (max ${error.max})"
        is HexError.OddLength -> "Odd length: ${error.length} chars"
        is HexError.InvalidCharacter -> "Invalid character '${error.char}' at index ${error.index}"
    }

    // --- CBOR ---

    /**
     * Decodes [hexInput] as hex, then decodes the resulting bytes as CBOR, and reports
     * whether a canonical re-encode round-trips to the same bytes.
     *
     * Returns [CborPresentation.Failure] on any hex or CBOR decode error.
     */
    fun presentCbor(hexInput: String): CborPresentation {
        val bytes = when (val hexResult = Hex.decode(hexInput.trim())) {
            is KardanoResult.Ok -> hexResult.value
            is KardanoResult.Err ->
                return CborPresentation.Failure("Hex error: ${presentHexError(hexResult.error)}")
        }
        val value = when (val cborResult = Cbor.decode(bytes)) {
            is KardanoResult.Ok -> cborResult.value
            is KardanoResult.Err ->
                return CborPresentation.Failure("CBOR error: ${presentCborError(cborResult.error)}")
        }
        val summary = value.toString()
        val roundTripOk = when (val encResult = Cbor.encode(value)) {
            is KardanoResult.Ok -> encResult.value.contentEquals(bytes)
            is KardanoResult.Err -> false
        }
        return CborPresentation.Success(summary, roundTripOk)
    }

    private fun presentCborError(error: CborError): String = error.toString()

    // --- Provider (read-only; provider-agnostic: mock or live) ---

    /**
     * Parses [addressInput] and queries [provider] for its UTxOs, mapping the result to a
     * [ProviderUtxosPresentation]. A parse failure is reported as
     * [ProviderUtxosPresentation.Failure]; an empty (but valid) result is reported as
     * [ProviderUtxosPresentation.NoUtxos], not an error.
     *
     * This is provider-agnostic: it works with any [ChainQueryProvider]. The caller decides
     * whether [provider] is the in-memory mock (fake/test-only) or a live provider (for example
     * Blockfrost preprod); this presenter does not know or care which.
     */
    suspend fun presentProviderUtxos(
        provider: ChainQueryProvider,
        addressInput: String,
    ): ProviderUtxosPresentation {
        val address = when (val parsed = Address.parse(addressInput.trim())) {
            is KardanoResult.Ok -> parsed.value
            is KardanoResult.Err ->
                return ProviderUtxosPresentation.Failure(presentAddressError(parsed.error))
        }
        return mapUtxosResult(provider.getUtxos(address))
    }

    /**
     * Queries [provider] for protocol parameters and maps the result to a
     * [ProviderParamsPresentation]. Provider-agnostic: the caller decides whether [provider] is
     * the in-memory mock (fake/test-only) or a live provider (for example Blockfrost preprod).
     */
    suspend fun presentProviderParams(
        provider: ChainQueryProvider,
    ): ProviderParamsPresentation = mapParamsResult(provider.getProtocolParameters())

    /**
     * Maps a raw `getUtxos` result to a [ProviderUtxosPresentation]. An empty (but Ok) result
     * is [ProviderUtxosPresentation.NoUtxos], not a failure. Non-suspend and `internal` so it
     * can be unit-tested by constructing results directly.
     */
    internal fun mapUtxosResult(
        result: KardanoResult<List<Utxo>, ProviderError>,
    ): ProviderUtxosPresentation = when (result) {
        is KardanoResult.Ok ->
            if (result.value.isEmpty()) {
                ProviderUtxosPresentation.NoUtxos("No UTxOs for this address.")
            } else {
                ProviderUtxosPresentation.Success(result.value.map(::utxoRow))
            }
        is KardanoResult.Err ->
            ProviderUtxosPresentation.Failure(presentProviderError(result.error))
    }

    /**
     * Maps a raw `getProtocolParameters` result to a [ProviderParamsPresentation]. Non-suspend
     * and `internal` so it can be unit-tested by constructing results directly.
     */
    internal fun mapParamsResult(
        result: KardanoResult<ProtocolParameters, ProviderError>,
    ): ProviderParamsPresentation = when (result) {
        is KardanoResult.Ok -> ProviderParamsPresentation.Success(paramsRows(result.value))
        is KardanoResult.Err ->
            ProviderParamsPresentation.Failure(presentProviderError(result.error))
    }

    private fun utxoRow(utxo: Utxo): LabeledRow {
        val ref = "${shortHex(utxo.ref.txHash.toByteArray())}#${utxo.ref.outputIndex}"
        return LabeledRow(ref, "${utxo.value.coin.value} lovelace")
    }

    private fun paramsRows(params: ProtocolParameters): List<LabeledRow> = listOf(
        LabeledRow("minFeeCoefficient", params.minFeeCoefficient.toString()),
        LabeledRow("minFeeConstant", params.minFeeConstant.toString()),
        LabeledRow("keyDeposit", params.keyDeposit.toString()),
        LabeledRow("poolDeposit", params.poolDeposit.toString()),
        LabeledRow("maxTxSize", params.maxTxSize.toString()),
        LabeledRow("coinsPerUtxoByte", params.coinsPerUtxoByte.toString()),
    )

    /** Maps a [ProviderError] to a human-readable single-line message. */
    internal fun presentProviderError(error: ProviderError): String = when (error) {
        is ProviderError.Transport -> "Transport error: ${error.message}"
        is ProviderError.RemoteStatus -> "Remote status: ${error.code}"
        is ProviderError.NotFound -> "Not found"
        is ProviderError.Deserialization -> "Decode error: ${error.detail}"
        is ProviderError.RateLimited -> "Rate limited"
        is ProviderError.NetworkMismatch ->
            "Network mismatch: provider=${error.expected.name}, address=${error.actual.name}"
        is ProviderError.Unknown -> "Unknown provider error"
    }

    // --- Helpers ---

    private fun shortHex(bytes: ByteArray): String {
        val prefix = bytes.copyOf(minOf(SHORT_HEX_PREFIX_BYTES, bytes.size))
        return "${Hex.encode(prefix)}… (${bytes.size}B, structural only)"
    }
}
