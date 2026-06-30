package org.sarmidev.kardano

/**
 * A typed error produced when [Bech32.encode] or [Bech32.decode] rejects its input.
 *
 * Encoding and decoding never throw on malformed input; they return one of these variants
 * inside a [KardanoResult.Err]. Malformed, over-limit, non-canonical, or checksum-invalid
 * input is rejected, never normalized or truncated.
 *
 * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki">BIP-173</a>
 * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0350.mediawiki">BIP-350</a>
 */
public sealed interface Bech32Error {

    /**
     * The encoded string exceeded the decoder's named character limit.
     *
     * The limit is checked before any output buffer is allocated.
     *
     * @property max the maximum number of input characters allowed
     *   ([Bech32.MAX_INPUT_CHARS]).
     * @property actual the number of input characters that were provided.
     */
    public data class InputTooLong(public val max: Int, public val actual: Int) : Bech32Error

    /**
     * The human-readable part exceeded the named HRP-length limit.
     *
     * @property max the maximum number of HRP characters allowed ([Bech32.MAX_HRP_CHARS]).
     * @property actual the number of HRP characters that were provided.
     */
    public data class HrpTooLong(public val max: Int, public val actual: Int) : Bech32Error

    /**
     * The number of 5-bit data values passed to [Bech32.encode] exceeded the named limit.
     *
     * This bounds the Bech32 data part (excluding the six checksum symbols) and is checked
     * before any output is built.
     *
     * @property max the maximum number of 5-bit data values allowed
     *   ([Bech32.MAX_DATA_VALUES]).
     * @property actual the number of 5-bit data values that were provided.
     */
    public data class DataValuesTooLong(public val max: Int, public val actual: Int) :
        Bech32Error

    /**
     * A 5-bit-to-8-bit conversion would produce more bytes than the named limit allows.
     *
     * The limit is checked before any output buffer is allocated.
     *
     * @property max the maximum number of converted bytes allowed ([Bech32.MAX_DATA_BYTES]).
     * @property actual the number of bytes the conversion would have produced.
     */
    public data class DataTooLong(public val max: Int, public val actual: Int) : Bech32Error

    /** The input had an empty human-readable part (no characters before the separator). */
    public data object EmptyHrp : Bech32Error

    /** The input contained no separator character (`1`). */
    public data object MissingSeparator : Bech32Error

    /**
     * The human-readable part contained a character outside the printable US-ASCII range
     * (`33`..`126`) that Bech32 allows.
     *
     * @property index the zero-based index of the first offending HRP character.
     * @property char the first offending character encountered.
     */
    public data class HrpCharOutOfRange(public val index: Int, public val char: Char) :
        Bech32Error

    /**
     * The input mixed upper-case and lower-case characters, which Bech32 forbids.
     *
     * Uniformly upper-case or uniformly lower-case input is accepted; mixed case is not.
     */
    public data object MixedCase : Bech32Error

    /**
     * The data part was shorter than the six characters required for a checksum.
     *
     * @property length the number of data-part characters that were provided.
     */
    public data class DataPartTooShort(public val length: Int) : Bech32Error

    /**
     * The data part contained a character outside the 32-symbol Bech32 alphabet.
     *
     * @property index the zero-based index of the first offending character within the
     *   whole input string.
     * @property char the first offending character encountered.
     */
    public data class InvalidDataCharacter(public val index: Int, public val char: Char) :
        Bech32Error

    /**
     * A data value passed to [Bech32.encode] fell outside the valid 5-bit range `0..31`.
     *
     * @property index the zero-based index of the first out-of-range value.
     * @property value the first out-of-range value encountered.
     */
    public data class DataValueOutOfRange(public val index: Int, public val value: Int) :
        Bech32Error

    /**
     * The checksum did not match either the Bech32 or the Bech32m constant.
     *
     * The data part is well-formed (valid charset and length) but its trailing six symbols
     * are not a valid checksum for the human-readable part under either variant.
     */
    public data object InvalidChecksum : Bech32Error

    /**
     * A 5-bit/8-bit conversion failed its padding rules: the leftover bits did not fit in
     * fewer than the source group size, or the padding bits were non-zero.
     */
    public data object InvalidPadding : Bech32Error
}
