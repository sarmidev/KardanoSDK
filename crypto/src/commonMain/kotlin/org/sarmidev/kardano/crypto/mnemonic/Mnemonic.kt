package org.sarmidev.kardano.crypto.mnemonic

import org.kotlincrypto.hash.sha2.SHA256
import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.derivation.IcarusMasterKey

/**
 * An opaque, validated BIP-39 English mnemonic, holding only the entropy it decodes to.
 *
 * Instances are created exclusively through [parse], which validates word count, English
 * wordlist membership, and the BIP-39 checksum, and immediately converts the words to entropy
 * bytes. The words themselves are not retained: this type is an input-only parse result, per
 * ADR-0009 §7. There is no accessor for the words or the entropy; [entropyBytes] is
 * module-internal, used only by [IcarusMasterKey] and this module's tests.
 *
 * Restore-only: this SDK does not generate new mnemonics (ADR-0009 §8). English wordlist only;
 * non-conforming input (wrong length, unknown word, bad checksum, non-ASCII/uppercase
 * characters) is rejected with a typed [MnemonicError], never normalized.
 *
 * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki">BIP-39</a>
 */
public class Mnemonic private constructor(
    entropy: ByteArray,
    wordCount: Int,
) {

    private var entropy: ByteArray = entropy.copyOf()

    /** The number of words the parsed mnemonic had (12, 15, 18, 21, or 24). */
    public val wordCount: Int = wordCount

    /**
     * Returns a defensive copy of the decoded entropy bytes.
     *
     * Module-internal: the only callers are [IcarusMasterKey.fromMnemonic] (which uses the
     * entropy as the Icarus PBKDF2 salt, per ADR-0009 §2) and this module's tests. There is no
     * public accessor for the entropy.
     *
     * @return a fresh copy of the entropy bytes.
     */
    internal fun entropyBytes(): ByteArray = entropy.copyOf()

    /**
     * Best-effort wipe of the retained entropy bytes.
     *
     * This zeroes this instance's backing array, but gives no guarantee about compiler,
     * runtime, or garbage-collector behavior, and does not affect any copy already returned by
     * [entropyBytes] (ADR-0004 §5 / ADR-0009 §7).
     */
    public fun clear() {
        entropy.fill(0)
    }

    /** Structural description that renders no words, no entropy, and no other secret bytes. */
    override fun toString(): String = "Mnemonic(wordCount=$wordCount)"

    public companion object {

        private val VALID_WORD_COUNTS: Set<Int> = setOf(12, 15, 18, 21, 24)

        /**
         * A generous per-word length bound used only to reject pathological input early (the
         * BIP-39 English wordlist's longest word is 8 characters).
         */
        private const val MAX_WORD_LENGTH: Int = 16

        /**
         * The maximum number of characters [parse] accepts for a phrase, well above the longest
         * possible valid phrase (24 words of at most 8 characters plus 23 separators = 215).
         * Enforced before any word-splitting, so an untrusted-length phrase never drives an
         * allocation sized by that length (parser-safety policy per the Phase 0 encoders).
         */
        public const val MAX_PHRASE_CHARS: Int = 256

        /**
         * Parses [phrase] as a space-separated BIP-39 English mnemonic.
         *
         * Splits on a single ASCII space (`' '`) only. Malformed separation (a double space, or
         * leading/trailing space) is rejected as an invalid word position, never normalized:
         * per ADR-0009 §2, this SDK rejects rather than trims or collapses whitespace.
         *
         * @param phrase the candidate mnemonic phrase.
         * @return [KardanoResult.Ok] with a [Mnemonic] on success, or [KardanoResult.Err] with a
         *   [MnemonicError] if [phrase] is not a valid BIP-39 English mnemonic. Never throws.
         */
        public fun parse(phrase: String): KardanoResult<Mnemonic, MnemonicError> {
            if (phrase.length > MAX_PHRASE_CHARS) {
                return KardanoResult.Err(MnemonicError.InputTooLong(MAX_PHRASE_CHARS, phrase.length))
            }
            if (phrase.isEmpty()) {
                return KardanoResult.Err(MnemonicError.InvalidWordCount(0))
            }
            return parse(phrase.split(" "))
        }

        /**
         * Parses [words] as a BIP-39 English mnemonic.
         *
         * Validates, in order: word count (must be 12, 15, 18, 21, or 24), that every word uses
         * only lowercase ASCII letters and is present in the English wordlist, and that the
         * BIP-39 checksum bits match the SHA-256 checksum of the decoded entropy. Non-conforming
         * input is rejected with a typed [MnemonicError], never normalized.
         *
         * @param words the candidate mnemonic words, in order.
         * @return [KardanoResult.Ok] with a [Mnemonic] on success, or [KardanoResult.Err] with a
         *   [MnemonicError] describing the first validation failure. Never throws.
         */
        public fun parse(words: List<String>): KardanoResult<Mnemonic, MnemonicError> {
            if (words.size !in VALID_WORD_COUNTS) {
                return KardanoResult.Err(MnemonicError.InvalidWordCount(words.size))
            }

            val indices = IntArray(words.size)
            for ((position, word) in words.withIndex()) {
                if (!isLowercaseAsciiWord(word)) {
                    return KardanoResult.Err(MnemonicError.InvalidCharacters(position))
                }
                val index = Bip39EnglishWordlist.indexOf(word)
                    ?: return KardanoResult.Err(MnemonicError.WordNotInWordlist(position))
                indices[position] = index
            }

            val totalBits = words.size * 11
            // BIP-39: CS = ENT / 32 and MS * 11 = ENT + CS, so ENT = totalBits * 32 / 33.
            val entropyBits = totalBits * 32 / 33
            val checksumBits = totalBits - entropyBits
            val packed = packElevenBitGroups(indices, totalBits)

            val entropyByteCount = entropyBits / 8
            val entropy = packed.copyOf(entropyByteCount)

            val checksumDigest = SHA256().digest(entropy)
            val expectedChecksumBits = (checksumDigest[0].toInt() and 0xFF) ushr (8 - checksumBits)
            val actualChecksumBits = (packed[entropyByteCount].toInt() and 0xFF) ushr (8 - checksumBits)
            if (expectedChecksumBits != actualChecksumBits) {
                return KardanoResult.Err(MnemonicError.ChecksumMismatch)
            }

            return KardanoResult.Ok(Mnemonic(entropy, words.size))
        }

        /** `true` only if [word] is non-empty and every character is a lowercase ASCII letter. */
        private fun isLowercaseAsciiWord(word: String): Boolean {
            if (word.isEmpty() || word.length > MAX_WORD_LENGTH) return false
            for (c in word) {
                if (c < 'a' || c > 'z') return false
            }
            return true
        }

        /**
         * Packs [indices] (each a BIP-39 11-bit wordlist index) into a big-endian bit stream of
         * exactly [totalBits] meaningful bits, MSB-first within each byte, zero-padded to a
         * whole number of bytes.
         */
        private fun packElevenBitGroups(indices: IntArray, totalBits: Int): ByteArray {
            val buffer = ByteArray((totalBits + 7) / 8)
            var bitPos = 0
            for (index in indices) {
                for (bit in 10 downTo 0) {
                    if ((index ushr bit) and 1 == 1) {
                        val byteIndex = bitPos / 8
                        val bitInByte = 7 - (bitPos % 8)
                        buffer[byteIndex] = (buffer[byteIndex].toInt() or (1 shl bitInByte)).toByte()
                    }
                    bitPos++
                }
            }
            return buffer
        }
    }
}
