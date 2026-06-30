package org.sarmidev.kardano.encoding.bech32

import org.sarmidev.kardano.KardanoResult

/**
 * A bounded, UI-free generic Bech32 and Bech32m codec.
 *
 * This is the generic encoding layer described by BIP-173 and BIP-350: it validates and
 * converts a human-readable part (HRP), a separator (`1`), a data part drawn from the
 * 32-symbol Bech32 alphabet, and a six-symbol checksum. It operates on the **5-bit data
 * part** (each data value is in `0..31`); it does not perform 5-bit/8-bit conversion in its
 * public API and applies no address semantics. [decode] auto-detects the [Bech32Variant];
 * [encode] takes it explicitly.
 *
 * This performs structural checksum and character-set validation only. It does not prove
 * that any encoded value refers to a real, owned, or spendable on-chain entity, and it does
 * not parse Cardano addresses (that is a later Phase 0 concern). Malformed, over-limit, or
 * checksum-invalid input is rejected via a typed [Bech32Error]; nothing is normalized or
 * truncated. Neither [encode] nor [decode] throws.
 *
 * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki">BIP-173</a>
 * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0350.mediawiki">BIP-350</a>
 */
public object Bech32 {

    /**
     * The maximum length, in characters, of an encoded string that [decode] accepts and
     * that [encode] produces.
     *
     * This is an SDK-owned Phase 0 limit (revisable by a future ADR), not BIP-173's general
     * 90-character cap: CIP-19 Cardano addresses can exceed 90 characters, so this bound is
     * intentionally larger. It is checked before any output buffer is allocated.
     */
    public const val MAX_INPUT_CHARS: Int = 1023

    /**
     * The maximum length, in characters, of the human-readable part.
     *
     * SDK-owned Phase 0 limit (revisable by a future ADR), enforced before allocation.
     */
    public const val MAX_HRP_CHARS: Int = 83

    /**
     * The maximum number of 5-bit data values [encode] accepts (the data part excluding the
     * six checksum symbols).
     *
     * This bounds the 5-bit layer. SDK-owned Phase 0 limit (revisable by a future ADR),
     * checked before any output is built.
     */
    public const val MAX_DATA_VALUES: Int = 1016

    /**
     * The maximum number of 8-bit bytes a 5-bit-to-8-bit conversion may produce.
     *
     * This bounds the 8-bit output of the internal bit-conversion helper only; it does not
     * apply to the 5-bit data part handled by [encode]/[decode]. SDK-owned Phase 0 limit
     * (revisable by a future ADR), checked before allocation.
     */
    public const val MAX_DATA_BYTES: Int = 640

    private const val CHECKSUM_LENGTH: Int = 6

    private const val MIN_HRP_CHAR_CODE: Int = 33
    private const val MAX_HRP_CHAR_CODE: Int = 126

    /** The 32-symbol Bech32 data alphabet. Excludes `1`, `b`, `i`, and `o`. */
    private const val CHARSET: String = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

    private val GENERATOR: IntArray =
        intArrayOf(0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)

    /**
     * Encodes a human-readable part and 5-bit data values into a Bech32/Bech32m string.
     *
     * The human-readable part is emitted in lower case and the data symbols are always lower
     * case, so the output is canonical lower case. Every value in [data] must be a 5-bit
     * value in `0..31`.
     *
     * @param hrp the human-readable part; must be non-empty, at most [MAX_HRP_CHARS] long,
     *   and contain only printable US-ASCII characters (codes `33`..`126`).
     * @param data the 5-bit data values (each in `0..31`), excluding the checksum, which is
     *   appended automatically. Not modified.
     * @param variant the checksum variant to apply.
     * @return [KardanoResult.Ok] with the encoded string, or [KardanoResult.Err] with a
     *   [Bech32Error] when the HRP, the data values, or the resulting length are invalid.
     *   Never throws.
     */
    public fun encode(
        hrp: String,
        data: ByteArray,
        variant: Bech32Variant,
    ): KardanoResult<String, Bech32Error> {
        if (hrp.isEmpty()) return KardanoResult.Err(Bech32Error.EmptyHrp)
        if (hrp.length > MAX_HRP_CHARS) {
            return KardanoResult.Err(Bech32Error.HrpTooLong(MAX_HRP_CHARS, hrp.length))
        }
        for (i in hrp.indices) {
            val code = hrp[i].code
            if (code < MIN_HRP_CHAR_CODE || code > MAX_HRP_CHAR_CODE) {
                return KardanoResult.Err(Bech32Error.HrpCharOutOfRange(i, hrp[i]))
            }
        }
        if (data.size > MAX_DATA_VALUES) {
            return KardanoResult.Err(Bech32Error.DataValuesTooLong(MAX_DATA_VALUES, data.size))
        }
        for (i in data.indices) {
            val value = data[i].toInt()
            if (value < 0 || value > 31) {
                return KardanoResult.Err(Bech32Error.DataValueOutOfRange(i, value))
            }
        }
        val totalLength = hrp.length + 1 + data.size + CHECKSUM_LENGTH
        if (totalLength > MAX_INPUT_CHARS) {
            return KardanoResult.Err(Bech32Error.InputTooLong(MAX_INPUT_CHARS, totalLength))
        }

        val lowerHrp = hrp.lowercase()
        val values = IntArray(data.size) { data[it].toInt() }
        val checksum = createChecksum(lowerHrp, values, variant)
        val out = StringBuilder(totalLength)
        out.append(lowerHrp)
        out.append('1')
        for (value in values) out.append(CHARSET[value])
        for (value in checksum) out.append(CHARSET[value])
        return KardanoResult.Ok(out.toString())
    }

    /**
     * Decodes a Bech32 or Bech32m string into its human-readable part and 5-bit data values.
     *
     * Performs structural validation only: it checks the length limit, rejects mixed-case
     * input, locates the last `1` separator, validates the HRP characters and length, the
     * data character set and minimum length, and the variant-specific checksum. The
     * returned data is the 5-bit data part with the six checksum symbols removed; it is not
     * converted to 8-bit bytes and is not interpreted as an address. Input is fully
     * validated before the result buffer is allocated; malformed input is rejected, never
     * normalized or truncated.
     *
     * @param input the candidate Bech32/Bech32m string.
     * @return [KardanoResult.Ok] with a [Bech32Decoded] (including the detected
     *   [Bech32Variant]) on success, or [KardanoResult.Err] with a [Bech32Error] when the
     *   length, case, separator, HRP, character set, or checksum is invalid. Never throws.
     */
    public fun decode(input: String): KardanoResult<Bech32Decoded, Bech32Error> {
        if (input.length > MAX_INPUT_CHARS) {
            return KardanoResult.Err(Bech32Error.InputTooLong(MAX_INPUT_CHARS, input.length))
        }

        var hasUpper = false
        var hasLower = false
        for (c in input) {
            if (c in 'a'..'z') hasLower = true
            if (c in 'A'..'Z') hasUpper = true
        }
        if (hasUpper && hasLower) return KardanoResult.Err(Bech32Error.MixedCase)

        val lower = if (hasUpper) input.lowercase() else input
        val sepPos = lower.lastIndexOf('1')
        if (sepPos < 0) return KardanoResult.Err(Bech32Error.MissingSeparator)
        if (sepPos == 0) return KardanoResult.Err(Bech32Error.EmptyHrp)

        val hrp = lower.substring(0, sepPos)
        if (hrp.length > MAX_HRP_CHARS) {
            return KardanoResult.Err(Bech32Error.HrpTooLong(MAX_HRP_CHARS, hrp.length))
        }
        for (i in hrp.indices) {
            val code = hrp[i].code
            if (code < MIN_HRP_CHAR_CODE || code > MAX_HRP_CHAR_CODE) {
                return KardanoResult.Err(Bech32Error.HrpCharOutOfRange(i, hrp[i]))
            }
        }

        val dataPart = lower.substring(sepPos + 1)
        if (dataPart.length < CHECKSUM_LENGTH) {
            return KardanoResult.Err(Bech32Error.DataPartTooShort(dataPart.length))
        }
        val values = IntArray(dataPart.length)
        for (i in dataPart.indices) {
            val index = CHARSET.indexOf(dataPart[i])
            if (index < 0) {
                return KardanoResult.Err(
                    Bech32Error.InvalidDataCharacter(sepPos + 1 + i, dataPart[i]),
                )
            }
            values[i] = index
        }

        val variant = verifyChecksum(hrp, values)
            ?: return KardanoResult.Err(Bech32Error.InvalidChecksum)

        val dataValues = ByteArray(values.size - CHECKSUM_LENGTH)
        for (i in dataValues.indices) dataValues[i] = values[i].toByte()
        return KardanoResult.Ok(Bech32Decoded(hrp, dataValues, variant))
    }

    /**
     * Converts between bit-group sizes, as used to move between 8-bit bytes and 5-bit Bech32
     * data values.
     *
     * Each element of [data] is treated as an unsigned [fromBits]-bit value; values with
     * bits set beyond [fromBits] are rejected. When [pad] is `true`, a final partial group
     * is zero-padded; when `false`, any leftover bits must be fewer than [fromBits] and zero,
     * otherwise the conversion is rejected. When [toBits] is `8`, the output length is
     * bounded by [MAX_DATA_BYTES] and the bound is checked before allocation.
     *
     * @return [KardanoResult.Ok] with the converted values, or [KardanoResult.Err] with
     *   [Bech32Error.InvalidPadding] or [Bech32Error.DataTooLong]. Never throws.
     */
    internal fun convertBits(
        data: ByteArray,
        fromBits: Int,
        toBits: Int,
        pad: Boolean,
    ): KardanoResult<ByteArray, Bech32Error> {
        val maxv = (1 shl toBits) - 1
        val totalBits = data.size * fromBits
        val fullGroups = totalBits / toBits
        val remainder = totalBits % toBits
        val outSize = if (pad) fullGroups + (if (remainder != 0) 1 else 0) else fullGroups
        if (toBits == 8 && outSize > MAX_DATA_BYTES) {
            return KardanoResult.Err(Bech32Error.DataTooLong(MAX_DATA_BYTES, outSize))
        }

        val inputMask = (1 shl fromBits) - 1
        val maxAcc = (1 shl (fromBits + toBits - 1)) - 1
        val out = ByteArray(outSize)
        var acc = 0
        var bits = 0
        var oi = 0
        for (b in data) {
            val value = b.toInt() and 0xFF
            if ((value and inputMask.inv()) != 0) {
                return KardanoResult.Err(Bech32Error.InvalidPadding)
            }
            acc = ((acc shl fromBits) or value) and maxAcc
            bits += fromBits
            while (bits >= toBits) {
                bits -= toBits
                out[oi++] = ((acc ushr bits) and maxv).toByte()
            }
        }
        if (pad) {
            if (bits != 0) out[oi++] = ((acc shl (toBits - bits)) and maxv).toByte()
        } else if (bits >= fromBits || ((acc shl (toBits - bits)) and maxv) != 0) {
            return KardanoResult.Err(Bech32Error.InvalidPadding)
        }
        return KardanoResult.Ok(out)
    }

    private fun createChecksum(
        hrp: String,
        data: IntArray,
        variant: Bech32Variant,
    ): IntArray {
        val expanded = hrpExpand(hrp)
        val values = IntArray(expanded.size + data.size + CHECKSUM_LENGTH)
        expanded.copyInto(values, 0)
        data.copyInto(values, expanded.size)
        val mod = polymod(values) xor variant.checksumConstant
        val checksum = IntArray(CHECKSUM_LENGTH)
        for (i in 0 until CHECKSUM_LENGTH) {
            checksum[i] = (mod ushr (5 * (5 - i))) and 31
        }
        return checksum
    }

    private fun verifyChecksum(hrp: String, data: IntArray): Bech32Variant? {
        val expanded = hrpExpand(hrp)
        val values = IntArray(expanded.size + data.size)
        expanded.copyInto(values, 0)
        data.copyInto(values, expanded.size)
        return when (polymod(values)) {
            Bech32Variant.BECH32.checksumConstant -> Bech32Variant.BECH32
            Bech32Variant.BECH32M.checksumConstant -> Bech32Variant.BECH32M
            else -> null
        }
    }

    private fun hrpExpand(hrp: String): IntArray {
        val out = IntArray(hrp.length * 2 + 1)
        for (i in hrp.indices) {
            out[i] = hrp[i].code ushr 5
            out[hrp.length + 1 + i] = hrp[i].code and 31
        }
        out[hrp.length] = 0
        return out
    }

    private fun polymod(values: IntArray): Int {
        var chk = 1
        for (v in values) {
            val top = chk ushr 25
            chk = ((chk and 0x1ffffff) shl 5) xor v
            for (i in 0 until 5) {
                if (((top ushr i) and 1) != 0) chk = chk xor GENERATOR[i]
            }
        }
        return chk
    }
}
