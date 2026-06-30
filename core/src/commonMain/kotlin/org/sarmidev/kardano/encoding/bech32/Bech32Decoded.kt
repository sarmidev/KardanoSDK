package org.sarmidev.kardano

/**
 * The result of decoding a Bech32 or Bech32m string with [Bech32.decode].
 *
 * This carries the lower-cased human-readable part, the decoded data part as **5-bit
 * group values** (each element is in `0..31`, the raw Bech32 alphabet indices with the
 * six checksum symbols removed), and the detected [variant]. It performs no 5-bit/8-bit
 * conversion and applies no address semantics: callers that need 8-bit bytes convert the
 * data themselves. This is a structural codec result only — it does not prove that any
 * encoded value refers to a real, owned, or spendable on-chain entity.
 *
 * The wrapped data is copied on construction and on every read, so the internal array is
 * never shared or mutable.
 *
 * @property hrp the human-readable part, always lower-case.
 * @property variant the checksum variant the decoded string used.
 */
public class Bech32Decoded internal constructor(
    public val hrp: String,
    data: ByteArray,
    public val variant: Bech32Variant,
) {

    private val data: ByteArray = data.copyOf()

    /**
     * Returns a copy of the decoded data part as 5-bit group values.
     *
     * Each element is in `0..31`. These are raw Bech32 data symbols, not 8-bit bytes; use
     * a separate 5-bit-to-8-bit conversion if 8-bit output is required.
     *
     * @return a fresh [ByteArray] of 5-bit values; mutating it does not affect this
     *   [Bech32Decoded].
     */
    public fun toData5BitArray(): ByteArray = data.copyOf()

    /** Value equality based on [hrp], the 5-bit data content, and [variant]. */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is Bech32Decoded) return false
        return hrp == other.hrp &&
            variant == other.variant &&
            data.contentEquals(other.data)
    }

    /** Hash code derived from [hrp], the 5-bit data content, and [variant]. */
    override fun hashCode(): Int {
        var result = hrp.hashCode()
        result = 31 * result + variant.hashCode()
        result = 31 * result + data.contentHashCode()
        return result
    }

    /** Structural description that does not render the decoded data values. */
    override fun toString(): String =
        "Bech32Decoded(hrp=$hrp, dataValues=${data.size}, variant=$variant)"
}
