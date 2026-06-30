package org.sarmidev.kardano.encoding.cbor

/**
 * A decoded or to-be-encoded CBOR value from the Phase 0 definite-length subset.
 *
 * This subset (RFC 8949) covers four primitive types — unsigned integers ([CborUnsigned]),
 * negative integers ([CborNegative]), byte strings ([CborByteString]), and text strings
 * ([CborTextString]) — plus two definite-length collection types: arrays ([CborArray]) and
 * maps ([CborMap]). Tags, floats, simple values, `null`/`undefined`, and indefinite-length
 * encodings are intentionally outside this type and are rejected by [Cbor.decode] with a
 * typed [CborError]; they are not represented here.
 *
 * Integers are restricted to the signed [Long] range so that no value is silently
 * truncated. See [Cbor] for the decode/encode entry points and the named nesting and
 * element-count limits that bound collections.
 *
 * @see <a href="https://www.rfc-editor.org/rfc/rfc8949">RFC 8949 (CBOR)</a>
 */
public sealed interface CborValue {

    /**
     * A CBOR unsigned integer (major type 0).
     *
     * The valid range is `0..Long.MAX_VALUE`. [Cbor.decode] only ever produces in-range
     * instances; if a [CborUnsigned] with a negative [value] is passed to [Cbor.encode] it
     * is rejected with [CborError.UnsignedValueNegative] rather than encoded.
     *
     * @property value the non-negative integer, in `0..Long.MAX_VALUE`.
     */
    public data class CborUnsigned(public val value: Long) : CborValue

    /**
     * A CBOR negative integer (major type 1).
     *
     * The valid range is `Long.MIN_VALUE..-1`. In CBOR a negative integer is encoded as the
     * unsigned argument `n = -1 - value`, so the most negative representable value is
     * `Long.MIN_VALUE` (`n = Long.MAX_VALUE`). [Cbor.decode] only ever produces in-range
     * instances; if a [CborNegative] with a non-negative [value] is passed to [Cbor.encode]
     * it is rejected with [CborError.NegativeValueNonNegative] rather than encoded.
     *
     * @property value the negative integer, in `Long.MIN_VALUE..-1`.
     */
    public data class CborNegative(public val value: Long) : CborValue

    /**
     * A CBOR byte string (major type 2), holding raw bytes of definite length.
     *
     * This is a structural container only: it does not interpret the bytes it holds. The
     * wrapped bytes are copied on construction and on every read, so the internal array is
     * never shared or mutable.
     *
     * @param bytes the byte-string contents; copied defensively.
     */
    public class CborByteString(bytes: ByteArray) : CborValue {

        private val bytes: ByteArray = bytes.copyOf()

        /**
         * Returns a copy of the wrapped bytes.
         *
         * @return a fresh [ByteArray]; mutating it does not affect this [CborByteString].
         */
        public fun toByteArray(): ByteArray = bytes.copyOf()

        /** Value equality based on byte content. */
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is CborByteString) return false
            return bytes.contentEquals(other.bytes)
        }

        /** Hash code derived from byte content. */
        override fun hashCode(): Int = bytes.contentHashCode()

        /** Structural description that does not render the wrapped bytes. */
        override fun toString(): String = "CborByteString(size=${bytes.size})"
    }

    /**
     * A CBOR text string (major type 3), holding a UTF-8 string of definite length.
     *
     * [Cbor.decode] only produces a [CborTextString] when the encoded bytes are valid
     * UTF-8; otherwise it returns [CborError.InvalidUtf8].
     *
     * @property value the decoded text. May be empty.
     */
    public data class CborTextString(public val value: String) : CborValue

    /**
     * A CBOR array (major type 4): an ordered, definite-length sequence of [CborValue]s.
     *
     * The elements are copied into an immutable snapshot on construction, so the list this
     * holds is never shared or mutated. [Cbor.decode] enforces the named element-count limit
     * ([Cbor.CBOR_MAX_COLLECTION_ELEMENTS]) and nesting-depth limit
     * ([Cbor.CBOR_MAX_NESTING_DEPTH]); [Cbor.encode] enforces the same limits before emitting.
     *
     * @param items the array elements, in order; copied defensively.
     */
    public class CborArray(items: List<CborValue>) : CborValue {

        private val items: List<CborValue> = items.toList()

        /**
         * Returns the array elements, in order.
         *
         * @return a fresh list; mutating it (even via a cast) does not affect this
         *   [CborArray]'s internal storage.
         */
        public fun items(): List<CborValue> = items.toList()

        /** Value equality based on the ordered element list. */
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is CborArray) return false
            return items == other.items
        }

        /** Hash code derived from the ordered element list. */
        override fun hashCode(): Int = items.hashCode()

        /** Structural description that does not render the elements. */
        override fun toString(): String = "CborArray(size=${items.size})"
    }

    /**
     * A single CBOR map entry: a [key] and its [value].
     *
     * Both are arbitrary [CborValue]s from this subset. [CborMap] holds entries in canonical
     * key order; see [CborMap] and [Cbor] for the ordering and duplicate-key rules.
     *
     * @property key the entry key.
     * @property value the entry value.
     */
    public data class CborEntry(public val key: CborValue, public val value: CborValue)

    /**
     * A CBOR map (major type 5): a definite-length sequence of key/value [CborEntry] pairs.
     *
     * Entries are held as an ordered, immutable list (not a [Map]) so the deterministic key
     * order is a first-class, explicit property rather than relying on a platform map's
     * iteration order. The entries are copied into a snapshot on construction.
     *
     * For the Phase 0 deterministic rule (per ADR-0001, RFC 8949 §4.2.1), keys must be in
     * strictly ascending order by the bytewise (unsigned) comparison of their canonical
     * encoded representation, with no duplicates. [Cbor.decode] only ever produces maps that
     * satisfy this. [Cbor.encode] **requires** the caller to supply entries already in that
     * order with no duplicate keys and rejects otherwise with
     * [CborError.NonCanonicalMapKeyOrder] or [CborError.DuplicateMapKey]; it does not reorder
     * entries. This Phase 0 deterministic rule is not asserted to be final Cardano
     * transaction-serialization compatibility.
     *
     * @param entries the map entries, in canonical key order; copied defensively.
     */
    public class CborMap(entries: List<CborEntry>) : CborValue {

        private val entries: List<CborEntry> = entries.toList()

        /**
         * Returns the map entries, in order.
         *
         * @return a fresh list; mutating it (even via a cast) does not affect this
         *   [CborMap]'s internal storage.
         */
        public fun entries(): List<CborEntry> = entries.toList()

        /** Value equality based on the ordered entry list. */
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is CborMap) return false
            return entries == other.entries
        }

        /** Hash code derived from the ordered entry list. */
        override fun hashCode(): Int = entries.hashCode()

        /** Structural description that does not render the entries. */
        override fun toString(): String = "CborMap(size=${entries.size})"
    }
}
