package org.sarmidev.kardano

import org.sarmidev.kardano.CborError.ByteStringTooLong
import org.sarmidev.kardano.CborError.CollectionTooLarge
import org.sarmidev.kardano.CborError.DeclaredLengthExceedsInput
import org.sarmidev.kardano.CborError.DuplicateMapKey
import org.sarmidev.kardano.CborError.EmptyInput
import org.sarmidev.kardano.CborError.FloatOrSimpleNotSupported
import org.sarmidev.kardano.CborError.IndefiniteLengthNotSupported
import org.sarmidev.kardano.CborError.InputTooLong
import org.sarmidev.kardano.CborError.IntegerOutOfRange
import org.sarmidev.kardano.CborError.InvalidUtf8
import org.sarmidev.kardano.CborError.LengthOutOfRange
import org.sarmidev.kardano.CborError.MaxNestingDepthExceeded
import org.sarmidev.kardano.CborError.NegativeValueNonNegative
import org.sarmidev.kardano.CborError.NonCanonicalInteger
import org.sarmidev.kardano.CborError.NonCanonicalLength
import org.sarmidev.kardano.CborError.NonCanonicalMapKeyOrder
import org.sarmidev.kardano.CborError.ReservedAdditionalInfo
import org.sarmidev.kardano.CborError.TagsNotSupported
import org.sarmidev.kardano.CborError.TextStringTooLong
import org.sarmidev.kardano.CborError.TrailingBytes
import org.sarmidev.kardano.CborError.UnexpectedEndOfInput
import org.sarmidev.kardano.CborError.UnsignedValueNegative
import org.sarmidev.kardano.CborValue.CborArray
import org.sarmidev.kardano.CborValue.CborByteString
import org.sarmidev.kardano.CborValue.CborEntry
import org.sarmidev.kardano.CborValue.CborMap
import org.sarmidev.kardano.CborValue.CborNegative
import org.sarmidev.kardano.CborValue.CborTextString
import org.sarmidev.kardano.CborValue.CborUnsigned

/**
 * A bounded decoder and encoder for the Phase 0 definite-length CBOR subset (RFC 8949).
 *
 * Supported types are: unsigned integers (major type 0) and negative integers (major type 1)
 * within the signed [Long] range, definite-length byte strings (major type 2), definite-length
 * text strings (major type 3, valid UTF-8 only), definite-length arrays (major type 4), and
 * definite-length maps (major type 5). Everything else is rejected with a typed [CborError]
 * and never normalized:
 *
 * - tags (major type 6, including bignum tags 2 and 3) are out of scope;
 * - floats and simple values (major type 7), including `false`/`true`/`null`/`undefined`,
 *   are out of scope;
 * - indefinite-length encodings, reserved additional-info values, non-canonical integer,
 *   length, or count encodings, out-of-range integers, malformed UTF-8, over-limit input,
 *   collections past the named element-count or nesting-depth limits, and trailing bytes
 *   after one complete top-level value are all rejected.
 *
 * Maps follow the Phase 0 deterministic rule (per ADR-0001, RFC 8949 §4.2.1): keys must be in
 * strictly ascending order by the bytewise comparison of their canonical encoded
 * representation, with no duplicates. The decoder rejects maps that violate this; the encoder
 * requires the caller to supply entries already in that order and rejects otherwise — it does
 * not reorder. This Phase 0 deterministic rule is not asserted to be final Cardano
 * transaction-serialization compatibility.
 *
 * The encoder emits canonical (shortest-form, definite-length) encodings for the supported
 * types only. Decoding and encoding return a [KardanoResult] and never throw on malformed
 * input. No buffer is ever allocated from an untrusted declared length or element count: a
 * declared length is validated against the total input limit, then against the remaining
 * bytes, then against the named size limit, before any payload is copied; a declared element
 * count is validated against the named element-count limit before any element is read.
 *
 * @see <a href="https://www.rfc-editor.org/rfc/rfc8949">RFC 8949 (CBOR)</a>
 * @see <a href="https://www.rfc-editor.org/rfc/rfc8949#appendix-A">RFC 8949 Appendix A</a>
 */
public object Cbor {

    /**
     * The maximum total input size [decode] will accept, in bytes.
     *
     * SDK-owned Phase 0 limit (revisable by a future ADR), not a value mandated by any spec.
     * It bounds work and allocation and is checked before any item is decoded.
     */
    public const val CBOR_MAX_INPUT_BYTES: Int = 1 shl 20

    /**
     * The maximum length of a single byte string, in bytes.
     *
     * SDK-owned Phase 0 limit (revisable by a future ADR). It is deliberately smaller than
     * [CBOR_MAX_INPUT_BYTES] so that a byte string is bounded independently of the overall
     * input size. The declared length is validated against this limit before any buffer is
     * allocated.
     */
    public const val CBOR_MAX_BYTESTRING_BYTES: Int = 1 shl 16

    /**
     * The maximum length of a single text string, in UTF-8 bytes.
     *
     * SDK-owned Phase 0 limit (revisable by a future ADR). It is deliberately smaller than
     * [CBOR_MAX_INPUT_BYTES] so that a text string is bounded independently of the overall
     * input size. The declared length is validated against this limit before any buffer is
     * allocated.
     *
     */
    public const val CBOR_MAX_STRING_BYTES: Int = 1 shl 16

    /**
     * The maximum nesting depth of arrays and maps [decode] and [encode] will accept.
     *
     * SDK-owned Phase 0 limit (revisable by a future ADR). A top-level array or map is depth
     * `1`, its collection children depth `2`, and so on. The limit is checked when a collection
     * head is reached, before its children are read or written, so deeply nested input cannot
     * drive unbounded recursion. The value comfortably exceeds realistic Cardano structures.
     */
    public const val CBOR_MAX_NESTING_DEPTH: Int = 64

    /**
     * The maximum number of elements in a single array or entries in a single map [decode] and
     * [encode] will accept.
     *
     * SDK-owned Phase 0 limit (revisable by a future ADR). On decode the declared count is
     * validated against this limit before any element is read, so an over-large declared count
     * cannot drive work or allocation. It is a denial-of-service backstop set well above
     * realistic Phase 0 structures.
     */
    public const val CBOR_MAX_COLLECTION_ELEMENTS: Int = 1 shl 16

    private const val MAJOR_UNSIGNED: Int = 0
    private const val MAJOR_NEGATIVE: Int = 1
    private const val MAJOR_BYTE_STRING: Int = 2
    private const val MAJOR_TEXT_STRING: Int = 3
    private const val MAJOR_ARRAY: Int = 4
    private const val MAJOR_MAP: Int = 5

    /**
     * Decodes a single top-level CBOR value from [input].
     *
     * The whole input is validated as it is read: the total-input limit is checked first,
     * empty input is rejected, exactly one definite-length value from the supported subset is
     * decoded, and any trailing bytes are rejected. Unsupported, malformed, non-canonical,
     * out-of-range, or over-limit input is rejected with a typed [CborError]; nothing is
     * normalized.
     *
     * @param input the candidate CBOR bytes. Not modified.
     * @return [KardanoResult.Ok] with the decoded [CborValue], or [KardanoResult.Err] with a
     *   [CborError] describing why the input was rejected. Never throws.
     * @see <a href="https://www.rfc-editor.org/rfc/rfc8949">RFC 8949 (CBOR)</a>
     */
    public fun decode(input: ByteArray): KardanoResult<CborValue, CborError> {
        if (input.size > CBOR_MAX_INPUT_BYTES) {
            return KardanoResult.Err(InputTooLong(CBOR_MAX_INPUT_BYTES, input.size))
        }
        if (input.isEmpty()) {
            return KardanoResult.Err(EmptyInput)
        }
        return when (val outcome = readItem(input, 0, depth = 0)) {
            is ReadOutcome.Fail -> KardanoResult.Err(outcome.error)
            is ReadOutcome.Ok ->
                if (outcome.nextOffset != input.size) {
                    KardanoResult.Err(TrailingBytes(outcome.nextOffset, input.size))
                } else {
                    KardanoResult.Ok(outcome.value)
                }
        }
    }

    /**
     * Encodes [value] into canonical, definite-length CBOR for the supported subset.
     *
     * Integers are emitted in their shortest canonical form. A [CborValue.CborUnsigned] must
     * be in `0..Long.MAX_VALUE` and a [CborValue.CborNegative] must be in
     * `Long.MIN_VALUE..-1`; values outside those ranges, a text string that is not valid
     * UTF-8, or a string longer than its named limit are rejected with a typed [CborError].
     *
     * Arrays and maps are emitted in definite-length form, subject to the named element-count
     * ([CBOR_MAX_COLLECTION_ELEMENTS]) and nesting-depth ([CBOR_MAX_NESTING_DEPTH]) limits. For
     * a [CborValue.CborMap] the caller must supply entries already in the Phase 0 deterministic
     * key order (per ADR-0001, RFC 8949 §4.2.1: strictly ascending by the bytewise comparison
     * of each key's canonical encoding) with no duplicate keys. The encoder does **not** sort
     * or deduplicate: a map whose keys are out of order is rejected with
     * [CborError.NonCanonicalMapKeyOrder] and one with a repeated key with
     * [CborError.DuplicateMapKey].
     *
     * @param value the value to encode.
     * @return [KardanoResult.Ok] with the canonical CBOR bytes, or [KardanoResult.Err] with a
     *   [CborError] if [value] cannot be encoded. Never throws.
     * @see <a href="https://www.rfc-editor.org/rfc/rfc8949">RFC 8949 (CBOR)</a>
     */
    public fun encode(value: CborValue): KardanoResult<ByteArray, CborError> =
        encodeValue(value, depth = 0)

    /**
     * Encodes [value] at nesting [depth] (`0` at the top level). A collection encoded here
     * sits at depth `depth + 1`, checked against [CBOR_MAX_NESTING_DEPTH] before its children
     * are emitted.
     */
    private fun encodeValue(value: CborValue, depth: Int): KardanoResult<ByteArray, CborError> =
        when (value) {
            is CborUnsigned ->
                if (value.value < 0L) {
                    KardanoResult.Err(UnsignedValueNegative(value.value))
                } else {
                    KardanoResult.Ok(encodeHead(MAJOR_UNSIGNED, value.value))
                }

            is CborNegative ->
                if (value.value >= 0L) {
                    KardanoResult.Err(NegativeValueNonNegative(value.value))
                } else {
                    KardanoResult.Ok(encodeHead(MAJOR_NEGATIVE, -1L - value.value))
                }

            is CborByteString -> {
                val bytes = value.toByteArray()
                if (bytes.size > CBOR_MAX_BYTESTRING_BYTES) {
                    KardanoResult.Err(
                        ByteStringTooLong(CBOR_MAX_BYTESTRING_BYTES, bytes.size.toLong()),
                    )
                } else {
                    KardanoResult.Ok(encodeHead(MAJOR_BYTE_STRING, bytes.size.toLong()) + bytes)
                }
            }

            is CborTextString -> {
                val bytes = try {
                    value.value.encodeToByteArray(throwOnInvalidSequence = true)
                } catch (_: CharacterCodingException) {
                    return KardanoResult.Err(InvalidUtf8)
                }
                if (bytes.size > CBOR_MAX_STRING_BYTES) {
                    KardanoResult.Err(TextStringTooLong(CBOR_MAX_STRING_BYTES, bytes.size.toLong()))
                } else {
                    KardanoResult.Ok(encodeHead(MAJOR_TEXT_STRING, bytes.size.toLong()) + bytes)
                }
            }

            is CborArray -> encodeArray(value, depth)
            is CborMap -> encodeMap(value, depth)
        }

    private fun encodeArray(value: CborArray, depth: Int): KardanoResult<ByteArray, CborError> {
        val level = depth + 1
        if (level > CBOR_MAX_NESTING_DEPTH) {
            return KardanoResult.Err(MaxNestingDepthExceeded(CBOR_MAX_NESTING_DEPTH, level))
        }
        val items = value.items()
        if (items.size > CBOR_MAX_COLLECTION_ELEMENTS) {
            return KardanoResult.Err(
                CollectionTooLarge(CBOR_MAX_COLLECTION_ELEMENTS, items.size.toLong()),
            )
        }
        val parts = ArrayList<ByteArray>(items.size + 1)
        parts.add(encodeHead(MAJOR_ARRAY, items.size.toLong()))
        for (item in items) {
            when (val r = encodeValue(item, level)) {
                is KardanoResult.Err -> return r
                is KardanoResult.Ok -> parts.add(r.value)
            }
        }
        return KardanoResult.Ok(concat(parts))
    }

    private fun encodeMap(value: CborMap, depth: Int): KardanoResult<ByteArray, CborError> {
        val level = depth + 1
        if (level > CBOR_MAX_NESTING_DEPTH) {
            return KardanoResult.Err(MaxNestingDepthExceeded(CBOR_MAX_NESTING_DEPTH, level))
        }
        val entries = value.entries()
        if (entries.size > CBOR_MAX_COLLECTION_ELEMENTS) {
            return KardanoResult.Err(
                CollectionTooLarge(CBOR_MAX_COLLECTION_ELEMENTS, entries.size.toLong()),
            )
        }
        val parts = ArrayList<ByteArray>(entries.size * 2 + 1)
        parts.add(encodeHead(MAJOR_MAP, entries.size.toLong()))
        var previousKey: ByteArray? = null
        for ((index, entry) in entries.withIndex()) {
            val keyBytes = when (val r = encodeValue(entry.key, level)) {
                is KardanoResult.Err -> return r
                is KardanoResult.Ok -> r.value
            }
            // The encoder requires already-canonical, duplicate-free key order; it rejects
            // rather than reordering, keeping behavior identical to the decoder.
            val prev = previousKey
            if (prev != null) {
                val cmp = compareBytesUnsigned(prev, keyBytes)
                if (cmp > 0) return KardanoResult.Err(NonCanonicalMapKeyOrder(index))
                if (cmp == 0) return KardanoResult.Err(DuplicateMapKey(index))
            }
            val valueBytes = when (val r = encodeValue(entry.value, level)) {
                is KardanoResult.Err -> return r
                is KardanoResult.Ok -> r.value
            }
            parts.add(keyBytes)
            parts.add(valueBytes)
            previousKey = keyBytes
        }
        return KardanoResult.Ok(concat(parts))
    }

    /** Concatenates [parts] into a single [ByteArray] in order. */
    private fun concat(parts: List<ByteArray>): ByteArray {
        var total = 0
        for (part in parts) total += part.size
        val out = ByteArray(total)
        var position = 0
        for (part in parts) {
            part.copyInto(out, position)
            position += part.size
        }
        return out
    }

    /**
     * Reads one item starting at [offset]. [depth] is the number of arrays/maps already open
     * above this item (`0` at the top level); a collection read here sits at depth `depth + 1`.
     */
    private fun readItem(input: ByteArray, offset: Int, depth: Int): ReadOutcome {
        if (offset >= input.size) {
            return ReadOutcome.Fail(UnexpectedEndOfInput(offset, 1, 0))
        }
        val head = input[offset].toInt() and 0xFF
        val major = head ushr 5
        val additionalInfo = head and 0x1F
        if (additionalInfo in 28..30) {
            return ReadOutcome.Fail(ReservedAdditionalInfo(major, additionalInfo))
        }
        if (additionalInfo == 31) {
            return ReadOutcome.Fail(IndefiniteLengthNotSupported(major))
        }
        return when (major) {
            MAJOR_UNSIGNED -> readUnsigned(input, offset, additionalInfo)
            MAJOR_NEGATIVE -> readNegative(input, offset, additionalInfo)
            MAJOR_BYTE_STRING -> readByteString(input, offset, additionalInfo)
            MAJOR_TEXT_STRING -> readTextString(input, offset, additionalInfo)
            MAJOR_ARRAY -> readArray(input, offset, additionalInfo, depth)
            MAJOR_MAP -> readMap(input, offset, additionalInfo, depth)
            6 -> ReadOutcome.Fail(TagsNotSupported)
            else -> ReadOutcome.Fail(FloatOrSimpleNotSupported(additionalInfo)) // major == 7
        }
    }

    private fun readUnsigned(input: ByteArray, offset: Int, additionalInfo: Int): ReadOutcome {
        val argument = when (val r = readArgument(input, offset, additionalInfo)) {
            is KardanoResult.Err -> return ReadOutcome.Fail(r.error)
            is KardanoResult.Ok -> r.value
        }
        if (!isCanonicalArgument(additionalInfo, argument.value, argument.outOfSignedRange)) {
            return ReadOutcome.Fail(NonCanonicalInteger(additionalInfo, argument.value))
        }
        if (argument.outOfSignedRange) {
            return ReadOutcome.Fail(IntegerOutOfRange(MAJOR_UNSIGNED))
        }
        return ReadOutcome.Ok(CborUnsigned(argument.value), argument.nextOffset)
    }

    private fun readNegative(input: ByteArray, offset: Int, additionalInfo: Int): ReadOutcome {
        val argument = when (val r = readArgument(input, offset, additionalInfo)) {
            is KardanoResult.Err -> return ReadOutcome.Fail(r.error)
            is KardanoResult.Ok -> r.value
        }
        if (!isCanonicalArgument(additionalInfo, argument.value, argument.outOfSignedRange)) {
            return ReadOutcome.Fail(NonCanonicalInteger(additionalInfo, argument.value))
        }
        if (argument.outOfSignedRange) {
            return ReadOutcome.Fail(IntegerOutOfRange(MAJOR_NEGATIVE))
        }
        // CBOR encodes a negative integer as the argument n = -1 - value; here value = -1 - n.
        // n is in 0..Long.MAX_VALUE, so the result is in Long.MIN_VALUE..-1 without overflow.
        return ReadOutcome.Ok(CborNegative(-1L - argument.value), argument.nextOffset)
    }

    private fun readByteString(input: ByteArray, offset: Int, additionalInfo: Int): ReadOutcome {
        val argument = when (val r = readArgument(input, offset, additionalInfo)) {
            is KardanoResult.Err -> return ReadOutcome.Fail(r.error)
            is KardanoResult.Ok -> r.value
        }
        if (!isCanonicalArgument(additionalInfo, argument.value, argument.outOfSignedRange)) {
            return ReadOutcome.Fail(NonCanonicalLength(additionalInfo, argument.value))
        }
        if (argument.outOfSignedRange) {
            return ReadOutcome.Fail(LengthOutOfRange(MAJOR_BYTE_STRING))
        }
        val payloadStart = argument.nextOffset
        val remaining = input.size - payloadStart
        // Anti-DoS ordering: the length is now a non-negative value in the signed Long range;
        // validate it against the remaining bytes, then the named limit, before allocating.
        if (argument.value > remaining.toLong()) {
            return ReadOutcome.Fail(DeclaredLengthExceedsInput(argument.value, remaining))
        }
        val length = argument.value.toInt()
        if (length > CBOR_MAX_BYTESTRING_BYTES) {
            return ReadOutcome.Fail(ByteStringTooLong(CBOR_MAX_BYTESTRING_BYTES, argument.value))
        }
        val payload = input.copyOfRange(payloadStart, payloadStart + length)
        return ReadOutcome.Ok(CborByteString(payload), payloadStart + length)
    }

    private fun readTextString(input: ByteArray, offset: Int, additionalInfo: Int): ReadOutcome {
        val argument = when (val r = readArgument(input, offset, additionalInfo)) {
            is KardanoResult.Err -> return ReadOutcome.Fail(r.error)
            is KardanoResult.Ok -> r.value
        }
        if (!isCanonicalArgument(additionalInfo, argument.value, argument.outOfSignedRange)) {
            return ReadOutcome.Fail(NonCanonicalLength(additionalInfo, argument.value))
        }
        if (argument.outOfSignedRange) {
            return ReadOutcome.Fail(LengthOutOfRange(MAJOR_TEXT_STRING))
        }
        val payloadStart = argument.nextOffset
        val remaining = input.size - payloadStart
        // Anti-DoS ordering: the length is now a non-negative value in the signed Long range;
        // validate it against the remaining bytes, then the named limit, before allocating.
        if (argument.value > remaining.toLong()) {
            return ReadOutcome.Fail(DeclaredLengthExceedsInput(argument.value, remaining))
        }
        val length = argument.value.toInt()
        if (length > CBOR_MAX_STRING_BYTES) {
            return ReadOutcome.Fail(TextStringTooLong(CBOR_MAX_STRING_BYTES, argument.value))
        }
        val text = try {
            input.decodeToString(payloadStart, payloadStart + length, throwOnInvalidSequence = true)
        } catch (_: CharacterCodingException) {
            return ReadOutcome.Fail(InvalidUtf8)
        }
        return ReadOutcome.Ok(CborTextString(text), payloadStart + length)
    }

    private fun readArray(
        input: ByteArray,
        offset: Int,
        additionalInfo: Int,
        depth: Int,
    ): ReadOutcome {
        val level = depth + 1
        val head = when (
            val r = readCollectionHead(input, offset, additionalInfo, MAJOR_ARRAY, level)
        ) {
            is KardanoResult.Err -> return ReadOutcome.Fail(r.error)
            is KardanoResult.Ok -> r.value
        }
        // The count is already bounded by CBOR_MAX_COLLECTION_ELEMENTS; the list is not
        // pre-sized from it, and an over-claimed count simply runs out of input below.
        val items = ArrayList<CborValue>()
        var cursor = head.nextOffset
        repeat(head.count) {
            when (val outcome = readItem(input, cursor, level)) {
                is ReadOutcome.Fail -> return outcome
                is ReadOutcome.Ok -> {
                    items.add(outcome.value)
                    cursor = outcome.nextOffset
                }
            }
        }
        return ReadOutcome.Ok(CborArray(items), cursor)
    }

    private fun readMap(
        input: ByteArray,
        offset: Int,
        additionalInfo: Int,
        depth: Int,
    ): ReadOutcome {
        val level = depth + 1
        val head = when (
            val r = readCollectionHead(input, offset, additionalInfo, MAJOR_MAP, level)
        ) {
            is KardanoResult.Err -> return ReadOutcome.Fail(r.error)
            is KardanoResult.Ok -> r.value
        }
        val entries = ArrayList<CborEntry>()
        var cursor = head.nextOffset
        var previousKey: ByteArray? = null
        repeat(head.count) { index ->
            val keyStart = cursor
            val (key, keyEnd) = when (val r = readItem(input, keyStart, level)) {
                is ReadOutcome.Fail -> return r
                is ReadOutcome.Ok -> r.value to r.nextOffset
            }
            // The key was decoded under the same canonical rules, so its encoded bytes are
            // canonical; comparing successive keys' encoded bytes enforces RFC 8949 §4.2.1
            // ordering and rejects duplicates without re-encoding.
            val keyBytes = input.copyOfRange(keyStart, keyEnd)
            val prev = previousKey
            if (prev != null) {
                val cmp = compareBytesUnsigned(prev, keyBytes)
                if (cmp > 0) return ReadOutcome.Fail(NonCanonicalMapKeyOrder(index))
                if (cmp == 0) return ReadOutcome.Fail(DuplicateMapKey(index))
            }
            val (value, valueEnd) = when (val r = readItem(input, keyEnd, level)) {
                is ReadOutcome.Fail -> return r
                is ReadOutcome.Ok -> r.value to r.nextOffset
            }
            entries.add(CborEntry(key, value))
            cursor = valueEnd
            previousKey = keyBytes
        }
        return ReadOutcome.Ok(CborMap(entries), cursor)
    }

    /**
     * Reads and validates an array/map element-count prefix and checks the nesting depth.
     * On success the returned count is within both the signed [Int] range and the named
     * element-count limit, and [CollectionHead.nextOffset] points just past the prefix.
     */
    private fun readCollectionHead(
        input: ByteArray,
        offset: Int,
        additionalInfo: Int,
        majorType: Int,
        level: Int,
    ): KardanoResult<CollectionHead, CborError> {
        if (level > CBOR_MAX_NESTING_DEPTH) {
            return KardanoResult.Err(MaxNestingDepthExceeded(CBOR_MAX_NESTING_DEPTH, level))
        }
        val argument = when (val r = readArgument(input, offset, additionalInfo)) {
            is KardanoResult.Err -> return KardanoResult.Err(r.error)
            is KardanoResult.Ok -> r.value
        }
        if (!isCanonicalArgument(additionalInfo, argument.value, argument.outOfSignedRange)) {
            return KardanoResult.Err(NonCanonicalLength(additionalInfo, argument.value))
        }
        if (argument.outOfSignedRange) {
            return KardanoResult.Err(LengthOutOfRange(majorType))
        }
        if (argument.value > CBOR_MAX_COLLECTION_ELEMENTS.toLong()) {
            return KardanoResult.Err(
                CollectionTooLarge(CBOR_MAX_COLLECTION_ELEMENTS, argument.value),
            )
        }
        return KardanoResult.Ok(CollectionHead(argument.value.toInt(), argument.nextOffset))
    }

    /** Unsigned bytewise lexicographic comparison, shorter array first when one is a prefix. */
    private fun compareBytesUnsigned(a: ByteArray, b: ByteArray): Int {
        val shared = minOf(a.size, b.size)
        for (i in 0 until shared) {
            val ai = a[i].toInt() and 0xFF
            val bi = b[i].toInt() and 0xFF
            if (ai != bi) return ai - bi
        }
        return a.size - b.size
    }

    /**
     * Reads the head byte's argument starting at [headOffset]. Caller has already rejected
     * reserved (`28`..`30`) and indefinite (`31`) additional-info values.
     */
    private fun readArgument(
        input: ByteArray,
        headOffset: Int,
        additionalInfo: Int,
    ): KardanoResult<Argument, CborError> {
        if (additionalInfo < 24) {
            return KardanoResult.Ok(Argument(additionalInfo.toLong(), headOffset + 1, false))
        }
        val byteCount = when (additionalInfo) {
            24 -> 1
            25 -> 2
            26 -> 4
            else -> 8 // additionalInfo == 27
        }
        val argStart = headOffset + 1
        val available = input.size - argStart
        if (available < byteCount) {
            val present = if (available < 0) 0 else available
            return KardanoResult.Err(UnexpectedEndOfInput(argStart, byteCount, present))
        }
        var raw = 0L
        for (i in 0 until byteCount) {
            raw = (raw shl 8) or (input[argStart + i].toLong() and 0xFFL)
        }
        // For an 8-byte argument, a set bit 63 means the unsigned value is >= 2^63, which does
        // not fit the signed Long range.
        val outOfSignedRange = byteCount == 8 && raw < 0L
        return KardanoResult.Ok(Argument(raw, argStart + byteCount, outOfSignedRange))
    }

    /**
     * Returns whether the argument was encoded in its shortest canonical form for the given
     * [additionalInfo]. Out-of-signed-range `uint64` arguments are canonical (they genuinely
     * require eight bytes).
     */
    private fun isCanonicalArgument(
        additionalInfo: Int,
        value: Long,
        outOfSignedRange: Boolean,
    ): Boolean = when (additionalInfo) {
        24 -> value >= 24L
        25 -> value >= 256L
        26 -> value >= 65_536L
        27 -> outOfSignedRange || value >= 0x1_0000_0000L
        else -> true // additionalInfo < 24: value is the head byte itself, no shorter form
    }

    /** Encodes a major type and a non-negative argument in shortest canonical form. */
    private fun encodeHead(major: Int, argument: Long): ByteArray {
        val majorBits = major shl 5
        return when {
            argument < 24L -> byteArrayOf((majorBits or argument.toInt()).toByte())
            argument <= 0xFFL -> byteArrayOf((majorBits or 24).toByte(), argument.toByte())
            argument <= 0xFFFFL -> byteArrayOf(
                (majorBits or 25).toByte(),
                (argument ushr 8).toByte(),
                argument.toByte(),
            )
            argument <= 0xFFFFFFFFL -> byteArrayOf(
                (majorBits or 26).toByte(),
                (argument ushr 24).toByte(),
                (argument ushr 16).toByte(),
                (argument ushr 8).toByte(),
                argument.toByte(),
            )
            else -> byteArrayOf(
                (majorBits or 27).toByte(),
                (argument ushr 56).toByte(),
                (argument ushr 48).toByte(),
                (argument ushr 40).toByte(),
                (argument ushr 32).toByte(),
                (argument ushr 24).toByte(),
                (argument ushr 16).toByte(),
                (argument ushr 8).toByte(),
                argument.toByte(),
            )
        }
    }

    /** A decoded head argument: its numeric [value], the [nextOffset], and a range flag. */
    private class Argument(
        val value: Long,
        val nextOffset: Int,
        val outOfSignedRange: Boolean,
    )

    /** A validated array/map element-count prefix and the offset just past it. */
    private class CollectionHead(val count: Int, val nextOffset: Int)

    /** The outcome of reading one item: a decoded value with its end offset, or an error. */
    private sealed interface ReadOutcome {
        data class Ok(val value: CborValue, val nextOffset: Int) : ReadOutcome
        data class Fail(val error: CborError) : ReadOutcome
    }
}
