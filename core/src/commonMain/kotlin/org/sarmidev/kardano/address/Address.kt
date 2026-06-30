package org.sarmidev.kardano.address

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.bech32.Bech32
import org.sarmidev.kardano.encoding.bech32.CardanoBech32
import org.sarmidev.kardano.encoding.bech32.CardanoBech32Error
import org.sarmidev.kardano.encoding.bech32.CardanoHrp
import org.sarmidev.kardano.primitives.Network

/**
 * A structurally validated Cardano address.
 *
 * This Block 0.7 type covers the Shelley CIP-19 Bech32 address families: base addresses
 * (`addr` / `addr_test`, CIP-19 header types 0-3), pointer addresses (`addr` / `addr_test`,
 * header types 4 and 5), enterprise addresses (`addr` / `addr_test`, header types 6 and 7),
 * and reward/stake addresses (`stake` / `stake_test`, header types 14 and 15). Byron
 * (bootstrap) addresses are not supported; they are deferred beyond Block 0.7 to a future
 * block (see [AddressType]).
 *
 * The address carries up to two credentials, exposed as the explicit, nullable
 * [paymentCredential] and [stakeCredential] properties, plus an optional chain [pointer].
 * Which are non-null depends on [type]:
 * - [AddressType.ENTERPRISE]: [paymentCredential] non-null; [stakeCredential] and [pointer] null.
 * - [AddressType.REWARD]: [stakeCredential] non-null; [paymentCredential] and [pointer] null.
 * - [AddressType.BASE]: [paymentCredential] and [stakeCredential] non-null; [pointer] null.
 * - [AddressType.POINTER]: [paymentCredential] and [pointer] non-null; [stakeCredential] null.
 *
 * **Structural validation only.** [parse] verifies the Bech32 checksum and character set
 * (via [CardanoBech32]), the 5-bit-to-8-bit conversion, the header byte (address type and
 * network nibble), agreement between the HRP and the header network and family, the
 * credential kinds, and the payload byte length (fixed for base/enterprise/reward, and for a
 * pointer address the variable-length chain pointer with no trailing bytes, each coordinate
 * canonical and within the non-negative `Long` range). It does **not** prove that the address
 * exists on-chain, is owned, is controllable, is spendable, or holds any balance, it does not
 * verify that the 28-byte credentials are real key or script hashes, and it does not check
 * that a [pointer] refers to a certificate that exists on-chain.
 *
 * The network id is taken from the header and preserved in [network]; it is never
 * discarded. Note that [network] cannot distinguish preview from preprod, because both use
 * network id `0` (see [Network]).
 *
 * The full address bytes (including the header) are copied on construction and on every
 * read, so the internal array is never shared or mutable.
 *
 * @property network the network resolved from the header network nibble.
 * @property type the structural address type.
 * @property hrp the human-readable part the address was encoded with.
 * @property paymentCredential the payment credential (CIP-19 payment part), or null for a
 *   reward/stake address. Non-null for base, pointer, and enterprise addresses.
 * @property stakeCredential the stake credential (CIP-19 delegation part), or null for an
 *   enterprise or pointer address. Non-null for base and reward/stake addresses. For a base
 *   address this is the delegation credential and may itself be a script hash (header types
 *   2/3). A pointer address has no inline delegation credential; it carries a [pointer]
 *   instead.
 * @property pointer the chain pointer (CIP-19 delegation part for a pointer address), or null
 *   for every other type. Non-null only for [AddressType.POINTER].
 * @see <a href="https://cips.cardano.org/cip/CIP-19">CIP-19</a>
 */
public class Address private constructor(
    public val network: Network,
    public val type: AddressType,
    public val hrp: CardanoHrp,
    public val paymentCredential: AddressCredential?,
    public val stakeCredential: AddressCredential?,
    public val pointer: AddressPointer?,
    rawBytes: ByteArray,
) {

    private val rawBytes: ByteArray = rawBytes.copyOf()

    /**
     * Returns a copy of the full address bytes, including the header byte.
     *
     * @return a fresh [ByteArray]; mutating it does not affect this [Address].
     */
    public fun toByteArray(): ByteArray = rawBytes.copyOf()

    /**
     * Value equality based on [network], [type], [hrp], [paymentCredential],
     * [stakeCredential], [pointer], and the byte content.
     */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is Address) return false
        return network == other.network &&
            type == other.type &&
            hrp == other.hrp &&
            paymentCredential == other.paymentCredential &&
            stakeCredential == other.stakeCredential &&
            pointer == other.pointer &&
            rawBytes.contentEquals(other.rawBytes)
    }

    /**
     * Hash code derived from [network], [type], [hrp], [paymentCredential],
     * [stakeCredential], [pointer], and the byte content.
     */
    override fun hashCode(): Int {
        var result = network.hashCode()
        result = 31 * result + type.hashCode()
        result = 31 * result + hrp.hashCode()
        result = 31 * result + paymentCredential.hashCode()
        result = 31 * result + stakeCredential.hashCode()
        result = 31 * result + pointer.hashCode()
        result = 31 * result + rawBytes.contentHashCode()
        return result
    }

    /** Structural description that does not render the address bytes. */
    override fun toString(): String =
        "Address(network=$network, type=$type, hrp=$hrp, bytes=${rawBytes.size})"

    public companion object {

        /** The fixed payload length of a single-credential address: header + credential. */
        private const val SINGLE_CREDENTIAL_PAYLOAD_SIZE: Int =
            1 + AddressCredential.HASH_SIZE

        /**
         * The fixed payload length of a base address: header + payment credential + stake
         * (delegation) credential.
         */
        private const val BASE_PAYLOAD_SIZE: Int =
            1 + 2 * AddressCredential.HASH_SIZE

        /**
         * The smallest valid pointer address payload: header + payment credential + three
         * one-byte (minimum) variable-length pointer coordinates.
         */
        private const val MIN_POINTER_PAYLOAD_SIZE: Int =
            1 + AddressCredential.HASH_SIZE + 3

        /**
         * The maximum number of bytes a single variable-length pointer coordinate may span.
         * Nine 7-bit groups carry 63 bits, exactly the non-negative `Long` range; a tenth
         * continuation byte is rejected as out of range.
         */
        private const val MAX_POINTER_FIELD_BYTES: Int = 9

        /** Continuation bit of a variable-length pointer byte: set means more bytes follow. */
        private const val CONTINUATION_BIT: Int = 0x80

        /** The 7 value-carrying low bits of a variable-length pointer byte. */
        private const val GROUP_MASK: Int = 0x7F

        /** Number of value bits carried by one variable-length pointer byte. */
        private const val GROUP_BITS: Int = 7

        private const val NIBBLE_MASK: Int = 0xF

        /** Header type bit selecting a script (vs key) payment part on a base address. */
        private const val PAYMENT_SCRIPT_BIT: Int = 0x1

        /** Header type bit selecting a script (vs key) delegation part on a base address. */
        private const val DELEGATION_SCRIPT_BIT: Int = 0x2

        /**
         * Parses and structurally validates a Bech32-encoded Cardano address.
         *
         * Performs **structural validation only** (see the [Address] class documentation):
         * it checks the Bech32 checksum/charset, the bit conversion, the header byte, the
         * network id, HRP/network and HRP/family agreement, the credential kind, and the
         * payload length. It does not prove that the address exists, is owned, or is
         * spendable. Malformed input is rejected with a typed [AddressError]; nothing is
         * normalized.
         *
         * @param bech32 the candidate address string (for example `addr_test1...` or
         *   `stake1...`).
         * @return [KardanoResult.Ok] with the validated [Address], or [KardanoResult.Err]
         *   with an [AddressError]. Never throws.
         * @see <a href="https://cips.cardano.org/cip/CIP-19">CIP-19</a>
         */
        public fun parse(bech32: String): KardanoResult<Address, AddressError> {
            val decoded = when (val result = CardanoBech32.decode(bech32)) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> return KardanoResult.Err(AddressError.Bech32(result.error))
            }

            val payload = when (
                val result = Bech32.convertBits(decoded.toData5BitArray(), 5, 8, pad = false)
            ) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err ->
                    return KardanoResult.Err(AddressError.InvalidBitConversion(result.error))
            }
            if (payload.isEmpty()) return KardanoResult.Err(AddressError.EmptyPayload)

            val header = payload[0].toInt() and 0xFF
            val typeNibble = (header ushr 4) and NIBBLE_MASK
            val networkNibble = header and NIBBLE_MASK

            // For base addresses the payment and delegation parts can each be a key or a
            // script hash, selected independently by the two low bits of the type nibble.
            val (type, paymentKind, stakeKind) = when (typeNibble) {
                BASE_KEY_KEY, BASE_SCRIPT_KEY, BASE_KEY_SCRIPT, BASE_SCRIPT_SCRIPT ->
                    Triple(
                        AddressType.BASE,
                        if (typeNibble and PAYMENT_SCRIPT_BIT != 0) {
                            CredentialKind.SCRIPT
                        } else {
                            CredentialKind.KEY
                        },
                        if (typeNibble and DELEGATION_SCRIPT_BIT != 0) {
                            CredentialKind.SCRIPT
                        } else {
                            CredentialKind.KEY
                        },
                    )
                POINTER_KEY_TYPE -> Triple(AddressType.POINTER, CredentialKind.KEY, null)
                POINTER_SCRIPT_TYPE -> Triple(AddressType.POINTER, CredentialKind.SCRIPT, null)
                ENTERPRISE_KEY_TYPE -> Triple(AddressType.ENTERPRISE, CredentialKind.KEY, null)
                ENTERPRISE_SCRIPT_TYPE ->
                    Triple(AddressType.ENTERPRISE, CredentialKind.SCRIPT, null)
                REWARD_KEY_TYPE -> Triple(AddressType.REWARD, null, CredentialKind.KEY)
                REWARD_SCRIPT_TYPE -> Triple(AddressType.REWARD, null, CredentialKind.SCRIPT)
                else -> return KardanoResult.Err(AddressError.UnsupportedAddressType(typeNibble))
            }

            val network = when (val result = Network.fromId(networkNibble)) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err ->
                    return KardanoResult.Err(AddressError.UnsupportedNetworkId(result.error))
            }

            // CardanoBech32.decode already enforced the HRP allowlist, so this is non-null
            // for any value that reached here; the null branch keeps parse total.
            val hrp = CardanoHrp.fromValue(decoded.hrp)
                ?: return KardanoResult.Err(
                    AddressError.Bech32(CardanoBech32Error.UnsupportedHrp(decoded.hrp)),
                )

            val expectedNetwork = when (hrp) {
                CardanoHrp.ADDR, CardanoHrp.STAKE -> Network.MAINNET
                CardanoHrp.ADDR_TEST, CardanoHrp.STAKE_TEST -> Network.TESTNET
            }
            if (network != expectedNetwork) {
                return KardanoResult.Err(AddressError.HrpNetworkMismatch(hrp, network))
            }

            val familyMatches = when (hrp) {
                CardanoHrp.ADDR, CardanoHrp.ADDR_TEST ->
                    type == AddressType.BASE ||
                        type == AddressType.POINTER ||
                        type == AddressType.ENTERPRISE
                CardanoHrp.STAKE, CardanoHrp.STAKE_TEST -> type == AddressType.REWARD
            }
            if (!familyMatches) {
                return KardanoResult.Err(AddressError.HrpFamilyMismatch(hrp, type))
            }

            // Pointer addresses are variable length (a fixed payment credential plus a
            // variable-length chain pointer), so they use a dedicated path instead of the
            // fixed-size check below. paymentKind is non-null (KEY or SCRIPT) for pointer.
            if (type == AddressType.POINTER && paymentKind != null) {
                return parsePointer(network, hrp, paymentKind, payload)
            }

            val expectedSize =
                if (type == AddressType.BASE) BASE_PAYLOAD_SIZE else SINGLE_CREDENTIAL_PAYLOAD_SIZE
            if (payload.size != expectedSize) {
                return KardanoResult.Err(
                    AddressError.InvalidPayloadLength(type, expectedSize, payload.size),
                )
            }

            // Enterprise/base carry the payment credential in the first 28-byte slot after
            // the header; reward addresses carry their single stake credential there.
            val paymentCredential = if (paymentKind != null) {
                when (
                    val result = AddressCredential.of(
                        paymentKind,
                        payload.copyOfRange(1, 1 + AddressCredential.HASH_SIZE),
                    )
                ) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(result.error)
                }
            } else {
                null
            }

            val stakeCredential = if (stakeKind != null) {
                val stakeStart =
                    if (type == AddressType.BASE) 1 + AddressCredential.HASH_SIZE else 1
                when (
                    val result = AddressCredential.of(
                        stakeKind,
                        payload.copyOfRange(stakeStart, stakeStart + AddressCredential.HASH_SIZE),
                    )
                ) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(result.error)
                }
            } else {
                null
            }

            return KardanoResult.Ok(
                Address(network, type, hrp, paymentCredential, stakeCredential, null, payload),
            )
        }

        /**
         * Parses the variable-length payload of a pointer address (CIP-19 header types 4 and
         * 5): a 28-byte payment credential followed by the three variable-length chain-pointer
         * coordinates, with no trailing bytes.
         */
        private fun parsePointer(
            network: Network,
            hrp: CardanoHrp,
            paymentKind: CredentialKind,
            payload: ByteArray,
        ): KardanoResult<Address, AddressError> {
            if (payload.size < MIN_POINTER_PAYLOAD_SIZE) {
                return KardanoResult.Err(AddressError.TruncatedPointer)
            }

            val paymentCredential = when (
                val result = AddressCredential.of(
                    paymentKind,
                    payload.copyOfRange(1, 1 + AddressCredential.HASH_SIZE),
                )
            ) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> return KardanoResult.Err(result.error)
            }

            var offset = 1 + AddressCredential.HASH_SIZE
            val slot = when (
                val result = decodePointerField(payload, offset, PointerField.SLOT)
            ) {
                is KardanoResult.Ok -> {
                    offset = result.value.nextOffset
                    result.value.value
                }
                is KardanoResult.Err -> return KardanoResult.Err(result.error)
            }
            val transactionIndex = when (
                val result = decodePointerField(payload, offset, PointerField.TRANSACTION_INDEX)
            ) {
                is KardanoResult.Ok -> {
                    offset = result.value.nextOffset
                    result.value.value
                }
                is KardanoResult.Err -> return KardanoResult.Err(result.error)
            }
            val certificateIndex = when (
                val result = decodePointerField(payload, offset, PointerField.CERTIFICATE_INDEX)
            ) {
                is KardanoResult.Ok -> {
                    offset = result.value.nextOffset
                    result.value.value
                }
                is KardanoResult.Err -> return KardanoResult.Err(result.error)
            }

            if (offset != payload.size) {
                return KardanoResult.Err(
                    AddressError.TrailingPointerBytes(offset, payload.size),
                )
            }

            val pointer = when (
                val result = AddressPointer.of(slot, transactionIndex, certificateIndex)
            ) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> return KardanoResult.Err(result.error)
            }

            return KardanoResult.Ok(
                Address(
                    network,
                    AddressType.POINTER,
                    hrp,
                    paymentCredential,
                    null,
                    pointer,
                    payload,
                ),
            )
        }

        /**
         * Decodes one variable-length unsigned pointer coordinate (CIP-19 big-endian base-128
         * "Word7" encoding) starting at [start] in [payload].
         *
         * Each byte contributes 7 low bits, most-significant group first; the continuation bit
         * ([CONTINUATION_BIT]) signals more bytes. Rejects (never normalizes): a field that
         * runs past the end of the payload ([AddressError.TruncatedPointer]); a non-canonical
         * leading zero group ([AddressError.NonCanonicalPointer]); and a field that spans more
         * than [MAX_POINTER_FIELD_BYTES] bytes or whose value would exceed `Long.MAX_VALUE`
         * ([AddressError.PointerValueOutOfRange]). The overflow check is performed before each
         * shift, so the accumulator never relies on signed `Long` wraparound.
         */
        private fun decodePointerField(
            payload: ByteArray,
            start: Int,
            field: PointerField,
        ): KardanoResult<PointerFieldDecode, AddressError> {
            var acc = 0L
            var offset = start
            var bytesRead = 0
            while (true) {
                if (offset >= payload.size) {
                    return KardanoResult.Err(AddressError.TruncatedPointer)
                }
                val b = payload[offset].toInt() and 0xFF
                // A leading 0x80 is a zero high group with the continuation bit set: the same
                // value could be encoded in fewer bytes, so the encoding is non-canonical.
                if (bytesRead == 0 && b == CONTINUATION_BIT) {
                    return KardanoResult.Err(AddressError.NonCanonicalPointer(field))
                }
                bytesRead++
                if (bytesRead > MAX_POINTER_FIELD_BYTES) {
                    return KardanoResult.Err(AddressError.PointerValueOutOfRange(field))
                }
                val group = (b and GROUP_MASK).toLong()
                // Reject before shifting so the signed Long is never allowed to overflow.
                if (acc > (Long.MAX_VALUE ushr GROUP_BITS)) {
                    return KardanoResult.Err(AddressError.PointerValueOutOfRange(field))
                }
                val shifted = acc shl GROUP_BITS
                if (group > Long.MAX_VALUE - shifted) {
                    return KardanoResult.Err(AddressError.PointerValueOutOfRange(field))
                }
                acc = shifted or group
                offset++
                if (b and CONTINUATION_BIT == 0) {
                    return KardanoResult.Ok(PointerFieldDecode(acc, offset))
                }
            }
        }

        private const val BASE_KEY_KEY: Int = 0
        private const val BASE_SCRIPT_KEY: Int = 1
        private const val BASE_KEY_SCRIPT: Int = 2
        private const val BASE_SCRIPT_SCRIPT: Int = 3
        private const val POINTER_KEY_TYPE: Int = 4
        private const val POINTER_SCRIPT_TYPE: Int = 5
        private const val ENTERPRISE_KEY_TYPE: Int = 6
        private const val ENTERPRISE_SCRIPT_TYPE: Int = 7
        private const val REWARD_KEY_TYPE: Int = 14
        private const val REWARD_SCRIPT_TYPE: Int = 15

        /** Internal carrier for one decoded pointer coordinate and the offset just past it. */
        private class PointerFieldDecode(val value: Long, val nextOffset: Int)
    }
}
