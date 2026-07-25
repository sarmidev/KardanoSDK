package org.sarmidev.kardano.crypto.mnemonic

/**
 * A typed, backend-neutral error returned by [Mnemonic.parse].
 *
 * Every variant carries only structural information (a word count or a 0-based word position)
 * needed to explain why parsing was rejected. No variant carries a mnemonic word, entropy, or
 * any other secret material. Per ADR-0009 §2, non-conforming input is rejected, never
 * normalized: this SDK accepts only lowercase ASCII words from the English wordlist.
 *
 * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki">BIP-39</a>
 */
public sealed interface MnemonicError {

    /**
     * The number of words did not match one of the BIP-39-defined word counts for the English
     * wordlist (12, 15, 18, 21, or 24).
     *
     * @property count the number of words actually supplied.
     */
    public data class InvalidWordCount(public val count: Int) : MnemonicError

    /**
     * The word at [position] used only lowercase ASCII letters but was not present in the
     * BIP-39 English wordlist.
     *
     * @property position the 0-based position of the offending word.
     */
    public data class WordNotInWordlist(public val position: Int) : MnemonicError

    /**
     * The checksum bits extracted from the words did not match the SHA-256 checksum of the
     * decoded entropy.
     */
    public data object ChecksumMismatch : MnemonicError

    /**
     * The word at [position] contained a character outside lowercase ASCII letters (for
     * example uppercase, digits, punctuation, or non-ASCII characters), or the position was
     * empty due to malformed word separation (for example a double space). Per ADR-0009 §2,
     * this input is rejected outright rather than normalized.
     *
     * @property position the 0-based position of the offending word.
     */
    public data class InvalidCharacters(public val position: Int) : MnemonicError

    /**
     * The candidate phrase passed to [Mnemonic.parse] exceeded [Mnemonic.MAX_PHRASE_CHARS].
     * Rejected before any word-splitting, so an untrusted-length input never drives an
     * unbounded allocation (parser-safety policy shared with [org.sarmidev.kardano.encoding]).
     *
     * @property max the maximum number of characters allowed ([Mnemonic.MAX_PHRASE_CHARS]).
     * @property actual the number of characters the candidate phrase had.
     */
    public data class InputTooLong(public val max: Int, public val actual: Int) : MnemonicError
}
