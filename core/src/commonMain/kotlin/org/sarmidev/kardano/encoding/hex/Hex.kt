package org.sarmidev.kardano.encoding.hex

import org.sarmidev.kardano.KardanoResult

/**
 * A bounded, UI-free hexadecimal (base-16) encoder and decoder.
 *
 * This is a generic byte/string codec, not a Cardano-specific helper: it neither inspects
 * nor interprets the bytes it converts. Encoding produces canonical lowercase output;
 * decoding accepts lowercase, uppercase, and mixed case because hex carries no checksum, so
 * letter case is unambiguous to decode. Malformed input is rejected via a typed [HexError]
 * rather than normalized or truncated.
 */
public object Hex {

    /**
     * The maximum number of characters [decode] will accept.
     *
     * This is an SDK-owned Phase 0 limit (revisable by a future ADR), not a value mandated
     * by any spec. It bounds work and allocation: the limit is checked before any output
     * buffer is allocated. The value (1,048,576 characters) decodes to at most 512 KiB.
     */
    public const val MAX_INPUT_CHARS: Int = 1 shl 20

    private const val LOWER_DIGITS: String = "0123456789abcdef"

    /**
     * Encodes [bytes] into a canonical lowercase hex string.
     *
     * Each byte becomes exactly two lowercase hex characters (`0-9`, `a-f`), most
     * significant nibble first. An empty array encodes to an empty string.
     *
     * @param bytes the bytes to encode. Not modified.
     * @return the canonical lowercase hex representation of [bytes]. Never throws.
     */
    public fun encode(bytes: ByteArray): String {
        if (bytes.isEmpty()) return ""
        val out = CharArray(bytes.size * 2)
        var i = 0
        for (b in bytes) {
            val v = b.toInt() and 0xFF
            out[i++] = LOWER_DIGITS[v ushr 4]
            out[i++] = LOWER_DIGITS[v and 0x0F]
        }
        return out.concatToString()
    }

    /**
     * Decodes a hex string into the bytes it represents.
     *
     * Accepts lowercase, uppercase, and mixed case. The input is fully validated before any
     * output buffer is allocated: the length limit is checked, then the length parity, then
     * every character. Malformed input is rejected, never normalized or truncated.
     *
     * @param input the candidate hex string. An empty string decodes to an empty array.
     * @return [KardanoResult.Ok] with the decoded bytes, or [KardanoResult.Err] with a
     *   [HexError] when [input] exceeds [MAX_INPUT_CHARS] ([HexError.InputTooLong]), has an
     *   odd length ([HexError.OddLength]), or contains a non-hex character
     *   ([HexError.InvalidCharacter]). Never throws.
     */
    public fun decode(input: String): KardanoResult<ByteArray, HexError> {
        if (input.length > MAX_INPUT_CHARS) {
            return KardanoResult.Err(HexError.InputTooLong(MAX_INPUT_CHARS, input.length))
        }
        if (input.length % 2 != 0) {
            return KardanoResult.Err(HexError.OddLength(input.length))
        }
        for (index in input.indices) {
            if (nibble(input[index]) < 0) {
                return KardanoResult.Err(HexError.InvalidCharacter(index, input[index]))
            }
        }
        val out = ByteArray(input.length / 2)
        var i = 0
        var j = 0
        while (i < input.length) {
            val hi = nibble(input[i])
            val lo = nibble(input[i + 1])
            out[j++] = ((hi shl 4) or lo).toByte()
            i += 2
        }
        return KardanoResult.Ok(out)
    }

    /** Returns the 0..15 value of a hex digit, or `-1` if [c] is not a hex digit. */
    private fun nibble(c: Char): Int = when (c) {
        in '0'..'9' -> c - '0'
        in 'a'..'f' -> c - 'a' + 10
        in 'A'..'F' -> c - 'A' + 10
        else -> -1
    }
}
