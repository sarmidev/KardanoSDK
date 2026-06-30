package org.sarmidev.kardano.address

import org.sarmidev.kardano.encoding.bech32.Bech32Error
import org.sarmidev.kardano.encoding.bech32.CardanoBech32Error
import org.sarmidev.kardano.encoding.bech32.CardanoHrp
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.NetworkError

/**
 * A typed error produced when [Address.parse] rejects its input.
 *
 * [Address.parse] never throws; it returns one of these variants inside a
 * [org.sarmidev.kardano.KardanoResult.Err]. These errors describe **structural**
 * validation failures only (Bech32 decoding, bit conversion, header byte, network id,
 * HRP/network and HRP/family agreement, and byte lengths). They make no claim about
 * ownership, on-chain existence, controllability, spendability, or balance.
 *
 * @see <a href="https://cips.cardano.org/cip/CIP-19">CIP-19</a>
 */
public sealed interface AddressError {

    /**
     * The Cardano-facing Bech32 decoder rejected the input string.
     *
     * Wraps the underlying [CardanoBech32Error] verbatim (for example an invalid checksum,
     * an out-of-charset character, a non-allowlisted HRP, or a Bech32m variant).
     *
     * @property error the underlying Cardano Bech32 error.
     */
    public data class Bech32(public val error: CardanoBech32Error) : AddressError

    /**
     * The 5-bit-to-8-bit conversion of the decoded data part failed.
     *
     * This happens when the Bech32 data part does not pack into whole bytes with zero
     * padding (for example non-zero leftover bits). Wraps the underlying [Bech32Error].
     *
     * @property error the underlying bit-conversion error.
     */
    public data class InvalidBitConversion(public val error: Bech32Error) : AddressError

    /** The decoded payload was empty, so it has no header byte to inspect. */
    public data object EmptyPayload : AddressError

    /**
     * The header type nibble is not a type this parser supports.
     *
     * Supported so far: base (0-3), pointer (4, 5), enterprise (6, 7), and reward (14, 15).
     * Byron (8) and reserved type nibbles are rejected here rather than parsed.
     *
     * @property headerTypeNibble the raw header type nibble (`0..15`) that was rejected.
     */
    public data class UnsupportedAddressType(public val headerTypeNibble: Int) : AddressError

    /**
     * The header network nibble is not a network id this SDK recognizes.
     *
     * Wraps the underlying [NetworkError] from [Network.fromId].
     *
     * @property error the underlying network-id error.
     */
    public data class UnsupportedNetworkId(public val error: NetworkError) : AddressError

    /**
     * The HRP and the header network nibble disagree.
     *
     * For example an `addr_test`/`stake_test` string whose header encodes mainnet, or an
     * `addr`/`stake` string whose header encodes a testnet.
     *
     * @property hrp the decoded human-readable part.
     * @property headerNetwork the network resolved from the header network nibble.
     */
    public data class HrpNetworkMismatch(
        public val hrp: CardanoHrp,
        public val headerNetwork: Network,
    ) : AddressError

    /**
     * The HRP family and the header address type disagree.
     *
     * For example a `stake`/`stake_test` HRP wrapping an enterprise (payment) header, or an
     * `addr`/`addr_test` HRP wrapping a reward (stake) header.
     *
     * @property hrp the decoded human-readable part.
     * @property type the address type resolved from the header type nibble.
     */
    public data class HrpFamilyMismatch(
        public val hrp: CardanoHrp,
        public val type: AddressType,
    ) : AddressError

    /**
     * The decoded payload length does not match the fixed length for the parsed type.
     *
     * @property type the address type whose fixed length was expected.
     * @property expected the number of payload bytes the type requires (the header plus its
     *   credential or credentials).
     * @property actual the number of payload bytes that were decoded.
     */
    public data class InvalidPayloadLength(
        public val type: AddressType,
        public val expected: Int,
        public val actual: Int,
    ) : AddressError

    /**
     * A credential hash slice was not the required length.
     *
     * In this step a valid payload always yields a correctly sized credential, so this is
     * unreachable from valid input; it makes the credential length invariant explicit at
     * the credential boundary.
     *
     * @property expected the exact number of bytes a credential hash requires.
     * @property actual the number of bytes that were provided.
     */
    public data class InvalidCredentialLength(
        public val expected: Int,
        public val actual: Int,
    ) : AddressError

    /**
     * A pointer address payload ended before a chain-pointer field terminated.
     *
     * This is a "ran out of bytes" condition: the payload is too short to even hold the
     * payment credential, or one of the three variable-length coordinates has a byte whose
     * continuation bit is set but no following byte is present (so fewer than three complete
     * fields could be read). It is distinct from [PointerValueOutOfRange], which is a
     * fully-present but too-large field.
     */
    public data object TruncatedPointer : AddressError

    /**
     * A chain-pointer coordinate is present in full but is too large.
     *
     * The field is not truncated (it terminates with a byte whose continuation bit is clear),
     * but it either spans more than the allowed number of bytes or its accumulated value would
     * exceed the non-negative `Long` range (`0..Long.MAX_VALUE`). The value is never truncated
     * or wrapped; it is rejected.
     *
     * @property field which coordinate (slot, transaction index, or certificate index) was
     *   out of range.
     */
    public data class PointerValueOutOfRange(public val field: PointerField) : AddressError

    /**
     * A chain-pointer coordinate used a non-canonical (over-long) variable-length encoding.
     *
     * The variable-length integer began with a leading zero group (a first byte of `0x80`)
     * that contributes no value, so the same number could be encoded in fewer bytes. Per the
     * Phase 0 parser policy ("reject malformed, non-canonical, or unsupported input — never
     * normalize it") this is rejected. This is stricter than the historically lenient ledger
     * decoder, which accepts over-long encodings.
     *
     * @property field which coordinate used the non-canonical encoding.
     */
    public data class NonCanonicalPointer(public val field: PointerField) : AddressError

    /**
     * A pointer address payload had extra bytes after the third chain-pointer coordinate.
     *
     * A pointer payload is the header, the 28-byte payment credential, and exactly three
     * variable-length coordinates with nothing after them. Trailing bytes are rejected rather
     * than ignored.
     *
     * @property consumed the number of payload bytes consumed by the header, credential, and
     *   three coordinates.
     * @property actual the total number of payload bytes.
     */
    public data class TrailingPointerBytes(
        public val consumed: Int,
        public val actual: Int,
    ) : AddressError
}
