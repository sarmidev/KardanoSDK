package org.sarmidev.kardano

/**
 * The two checksum variants of the Bech32 family of encodings.
 *
 * The variants differ only by the constant XORed into the checksum polymod:
 *
 * - [BECH32] uses the original BIP-173 constant.
 * - [BECH32M] uses the BIP-350 constant.
 *
 * Otherwise the human-readable part, separator, character set, and checksum length are
 * identical. [Bech32.decode] auto-detects which variant a string uses; [Bech32.encode]
 * takes the variant explicitly.
 *
 * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki">BIP-173</a>
 * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0350.mediawiki">BIP-350</a>
 */
public enum class Bech32Variant {

    /** The original BIP-173 Bech32 checksum (polymod constant `1`). */
    BECH32,

    /** The BIP-350 Bech32m checksum (polymod constant `0x2bc830a3`). */
    BECH32M;

    /** The constant XORed into the checksum for this variant. Internal detail. */
    internal val checksumConstant: Int
        get() = when (this) {
            BECH32 -> 1
            BECH32M -> 0x2bc830a3
        }
}
