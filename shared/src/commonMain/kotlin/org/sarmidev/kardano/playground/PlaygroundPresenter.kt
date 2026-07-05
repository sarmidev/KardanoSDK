package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.address.AddressError
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.encoding.cbor.CborError
import org.sarmidev.kardano.encoding.hex.Hex
import org.sarmidev.kardano.encoding.hex.HexError

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

    // --- Helpers ---

    private fun shortHex(bytes: ByteArray): String {
        val prefix = bytes.copyOf(minOf(SHORT_HEX_PREFIX_BYTES, bytes.size))
        return "${Hex.encode(prefix)}… (${bytes.size}B, structural only)"
    }
}
