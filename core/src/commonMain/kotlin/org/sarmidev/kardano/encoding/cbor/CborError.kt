package org.sarmidev.kardano.encoding.cbor

import org.sarmidev.kardano.KardanoResult

/**
 * A typed error produced when [Cbor.decode] or [Cbor.encode] rejects its input.
 *
 * Decoding and encoding never throw on malformed or unsupported input; they return one of
 * these variants inside a [KardanoResult.Err]. Malformed, non-canonical, out-of-range,
 * over-limit, or unsupported input is rejected, never normalized or truncated.
 *
 * The Phase 0 subset supports only definite-length unsigned integers, negative integers,
 * byte strings, and text strings within the signed [Long] range, plus definite-length arrays
 * and maps within the named nesting and element-count limits; everything else maps to a
 * variant here.
 *
 * @see <a href="https://www.rfc-editor.org/rfc/rfc8949">RFC 8949 (CBOR)</a>
 */
public sealed interface CborError {

    /**
     * The input exceeded the named total-input limit before any item was decoded.
     *
     * The limit is checked before any work is done.
     *
     * @property max the maximum number of input bytes allowed ([Cbor.CBOR_MAX_INPUT_BYTES]).
     * @property actual the number of input bytes that were provided.
     */
    public data class InputTooLong(public val max: Int, public val actual: Int) : CborError

    /** The input was empty; a CBOR value requires at least one byte. */
    public data object EmptyInput : CborError

    /**
     * The input ended before a value (its head, argument, or payload) was fully read.
     *
     * @property offset the index at which more bytes were required.
     * @property needed the number of bytes required at [offset].
     * @property available the number of bytes actually remaining from [offset].
     */
    public data class UnexpectedEndOfInput(
        public val offset: Int,
        public val needed: Int,
        public val available: Int,
    ) : CborError

    /**
     * Bytes remained after one complete top-level value was decoded.
     *
     * The Phase 0 decoder accepts exactly one top-level item and rejects any trailing data.
     *
     * @property consumed the number of bytes the single value consumed.
     * @property total the total number of input bytes.
     */
    public data class TrailingBytes(public val consumed: Int, public val total: Int) : CborError

    /**
     * The head byte used a reserved additional-info value (`28`, `29`, or `30`), which
     * RFC 8949 does not assign.
     *
     * @property majorType the major type (`0`..`7`) of the head byte.
     * @property additionalInfo the reserved additional-info value (`28`..`30`).
     */
    public data class ReservedAdditionalInfo(
        public val majorType: Int,
        public val additionalInfo: Int,
    ) : CborError

    /**
     * The head byte requested an indefinite-length encoding (additional info `31`). The
     * Phase 0 subset accepts definite-length encodings only.
     *
     * @property majorType the major type (`0`..`7`) of the head byte.
     */
    public data class IndefiniteLengthNotSupported(public val majorType: Int) : CborError

    /**
     * An integer argument (major type 0 or 1) was not encoded in its shortest canonical
     * form, for example `24` encoded as a `uint8` whose value is below `24`.
     *
     * @property additionalInfo the additional-info value used (`24`..`27`).
     * @property value the decoded numeric argument that a shorter encoding could represent.
     */
    public data class NonCanonicalInteger(
        public val additionalInfo: Int,
        public val value: Long,
    ) : CborError

    /**
     * A length or element-count prefix was not encoded in its shortest canonical form. This
     * applies to byte- and text-string length prefixes (major types 2 and 3) as well as
     * array and map element-count prefixes (major types 4 and 5), for example a count of `0`
     * encoded as a `uint8` instead of in the head byte.
     *
     * @property additionalInfo the additional-info value used (`24`..`27`).
     * @property value the decoded length or count that a shorter encoding could represent.
     */
    public data class NonCanonicalLength(
        public val additionalInfo: Int,
        public val value: Long,
    ) : CborError

    /**
     * An integer argument fell outside the supported signed [Long] range. This happens for a
     * `uint64` argument (additional info `27`) whose value sets bit 63: for major type 0 it
     * exceeds `Long.MAX_VALUE`, and for major type 1 the resulting negative value would be
     * below `Long.MIN_VALUE`. The value is rejected, never truncated.
     *
     * @property majorType the major type (`0` or `1`) of the offending integer.
     */
    public data class IntegerOutOfRange(public val majorType: Int) : CborError

    /**
     * A CBOR tag (major type 6) was encountered. Tags, including bignum tags 2 and 3, are
     * out of scope for the Phase 0 subset and are rejected.
     */
    public data object TagsNotSupported : CborError

    /**
     * A CBOR float or simple value (major type 7), including `false`, `true`, `null`, and
     * `undefined`, was encountered. These are out of scope for the Phase 0 subset and are
     * rejected.
     *
     * @property additionalInfo the additional-info value of the major-type-7 head byte.
     */
    public data class FloatOrSimpleNotSupported(public val additionalInfo: Int) : CborError

    /**
     * A byte string's declared length exceeded the named limit. The limit is checked before
     * any buffer is allocated.
     *
     * @property max the maximum byte-string length allowed ([Cbor.CBOR_MAX_BYTESTRING_BYTES]).
     * @property actual the declared (decode) or actual (encode) byte-string length.
     */
    public data class ByteStringTooLong(public val max: Int, public val actual: Long) : CborError

    /**
     * A text string's declared length exceeded the named limit. The limit is checked before
     * any buffer is allocated.
     *
     * @property max the maximum text-string length in bytes ([Cbor.CBOR_MAX_STRING_BYTES]).
     * @property actual the declared (decode) or actual (encode) UTF-8 byte length.
     */
    public data class TextStringTooLong(public val max: Int, public val actual: Long) : CborError

    /**
     * A byte- or text-string declared a length larger than the bytes remaining in the input.
     * The declared length is validated against the remaining input before any buffer is
     * allocated, so an attacker-controlled length cannot force a large allocation.
     *
     * @property declaredLength the length the head declared.
     * @property remaining the number of payload bytes actually available.
     */
    public data class DeclaredLengthExceedsInput(
        public val declaredLength: Long,
        public val remaining: Int,
    ) : CborError

    /**
     * A length or element-count prefix was a `uint64` argument outside the supported signed
     * [Long] range (its bit 63 was set, i.e. the declared value was at least `2^63`). The
     * value is rejected rather than reinterpreted as a negative value or truncated.
     *
     * This is distinct from [IntegerOutOfRange], which applies to integer values (major types
     * 0 and 1); this variant applies to the length prefix of a string (major types 2 and 3)
     * or the element-count prefix of an array or map (major types 4 and 5).
     *
     * @property majorType the major type of the offending item (`2` for byte strings, `3` for
     *   text strings, `4` for arrays, `5` for maps).
     */
    public data class LengthOutOfRange(public val majorType: Int) : CborError

    /**
     * A text string's payload (decode) or a [CborValue.CborTextString]'s value (encode) was
     * not valid UTF-8. Malformed UTF-8 is rejected, never replaced with substitute
     * characters.
     */
    public data object InvalidUtf8 : CborError

    /**
     * [Cbor.encode] was given a [CborValue.CborUnsigned] whose value is negative, which is
     * outside the `0..Long.MAX_VALUE` range an unsigned integer may hold.
     *
     * @property value the rejected negative value.
     */
    public data class UnsignedValueNegative(public val value: Long) : CborError

    /**
     * [Cbor.encode] was given a [CborValue.CborNegative] whose value is non-negative, which
     * is outside the `Long.MIN_VALUE..-1` range a negative integer may hold.
     *
     * @property value the rejected non-negative value.
     */
    public data class NegativeValueNonNegative(public val value: Long) : CborError

    /**
     * An array or map nested more deeply than the named limit
     * ([Cbor.CBOR_MAX_NESTING_DEPTH]). The limit is checked when a collection head is reached,
     * before its children are read (decode) or written (encode), so deeply nested input
     * cannot drive unbounded recursion.
     *
     * @property max the maximum nesting depth allowed ([Cbor.CBOR_MAX_NESTING_DEPTH]).
     * @property depth the depth at which the limit was exceeded.
     */
    public data class MaxNestingDepthExceeded(public val max: Int, public val depth: Int) :
        CborError

    /**
     * An array's element count or a map's entry count exceeded the named limit
     * ([Cbor.CBOR_MAX_COLLECTION_ELEMENTS]). On decode the declared count is checked before
     * any element is read, so an over-large declared count cannot drive work or allocation;
     * on encode the actual element/entry count is checked before emitting.
     *
     * @property max the maximum element/entry count allowed
     *   ([Cbor.CBOR_MAX_COLLECTION_ELEMENTS]).
     * @property actual the declared (decode) or actual (encode) element/entry count.
     */
    public data class CollectionTooLarge(public val max: Int, public val actual: Long) :
        CborError

    /**
     * A map's keys were not in the strictly ascending canonical order the Phase 0
     * deterministic rule requires (per ADR-0001, RFC 8949 §4.2.1: keys ordered by the bytewise
     * comparison of their canonical encoded representation). The offending key is neither
     * sorted nor normalized; the map is rejected.
     *
     * @property index the index of the entry whose key is not greater than the previous key.
     */
    public data class NonCanonicalMapKeyOrder(public val index: Int) : CborError

    /**
     * A map contained two entries with the same key. Duplicate keys are rejected
     * unconditionally and never collapsed.
     *
     * @property index the index of the entry whose key repeats an earlier key.
     */
    public data class DuplicateMapKey(public val index: Int) : CborError
}
