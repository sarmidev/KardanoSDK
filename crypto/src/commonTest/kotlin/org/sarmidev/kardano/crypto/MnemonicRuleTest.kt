package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Rule tests for [Mnemonic.parse]'s validation and structural behavior.
 *
 * The invalid-input cases are derived by mutating the cited 12-word all-zero-entropy vector
 * from `trezor/python-mnemonic` `vectors.json` (see [MnemonicVectorsTest]) so that each case
 * changes exactly one property under test, per `docs/DECISIONS/0009-mnemonic-seed-and-key-
 * derivation.md` §4's "derived rule test" allowance. No case is a cited known-answer vector in
 * its own right.
 */
class MnemonicRuleTest {

    // The cited 12-word, all-zero-entropy vector (see MnemonicVectorsTest), used as the base
    // for every mutation below.
    private val validWords = listOf(
        "abandon", "abandon", "abandon", "abandon", "abandon", "abandon",
        "abandon", "abandon", "abandon", "abandon", "abandon", "about",
    )

    @Test
    fun parse_validVector_isOk() {
        assertTrue(Mnemonic.parse(validWords) is KardanoResult.Ok)
    }

    @Test
    fun parse_wrongWordCount_isRejected() {
        val tooFew = validWords.dropLast(1)

        val result = Mnemonic.parse(tooFew)

        assertEquals(
            KardanoResult.Err(MnemonicError.InvalidWordCount(tooFew.size)),
            result,
        )
    }

    @Test
    fun parse_wordNotInWordlist_isRejected() {
        val words = validWords.toMutableList()
        words[11] = "zzznotaword"

        val result = Mnemonic.parse(words)

        assertEquals(KardanoResult.Err(MnemonicError.WordNotInWordlist(11)), result)
    }

    @Test
    fun parse_uppercaseCharacters_isRejectedAsInvalidCharacters() {
        val words = validWords.toMutableList()
        words[0] = "ABANDON"

        val result = Mnemonic.parse(words)

        assertEquals(KardanoResult.Err(MnemonicError.InvalidCharacters(0)), result)
    }

    @Test
    fun parse_nonAsciiDigitCharacter_isRejectedAsInvalidCharacters() {
        val words = validWords.toMutableList()
        words[3] = "aband0n"

        val result = Mnemonic.parse(words)

        assertEquals(KardanoResult.Err(MnemonicError.InvalidCharacters(3)), result)
    }

    @Test
    fun parse_wrongChecksum_isRejected() {
        // Same 12 valid dictionary words as the cited vector, but the last word ("zoo" instead
        // of "about") no longer matches the checksum computed over the resulting entropy.
        val words = validWords.dropLast(1) + "zoo"

        val result = Mnemonic.parse(words)

        assertEquals(KardanoResult.Err(MnemonicError.ChecksumMismatch), result)
    }

    @Test
    fun parse_phraseTooLong_isRejectedBeforeSplitting() {
        val overlong = "a".repeat(Mnemonic.MAX_PHRASE_CHARS + 1)

        val result = Mnemonic.parse(overlong)

        assertEquals(
            KardanoResult.Err(MnemonicError.InputTooLong(Mnemonic.MAX_PHRASE_CHARS, overlong.length)),
            result,
        )
    }

    @Test
    fun parse_emptyPhrase_isRejectedAsInvalidWordCount() {
        val result = Mnemonic.parse("")

        assertEquals(KardanoResult.Err(MnemonicError.InvalidWordCount(0)), result)
    }

    @Test
    fun parse_doubleSpaceSeparator_isRejectedRatherThanNormalized() {
        // A double space produces an empty-string "word" at the split point, which must be
        // rejected outright (ADR-0009 §2: reject, never normalize whitespace).
        val phrase = validWords.joinToString(" ").replaceFirst("abandon abandon", "abandon  abandon")

        val result = Mnemonic.parse(phrase)

        assertTrue(result is KardanoResult.Err)
    }

    @Test
    fun clear_wipesEntropyOnThisInstanceOnly() {
        // Uses a non-zero-entropy cited vector (see MnemonicVectorsTest): the base validWords
        // vector's entropy is all-zero by design, which would make the "not already zero"
        // precondition below meaningless.
        val nonZeroEntropyWords = listOf(
            "ozone", "drill", "grab", "fiber", "curtain", "grace",
            "pudding", "thank", "cruise", "elder", "eight", "picnic",
        )
        val mnemonic = okMnemonic(Mnemonic.parse(nonZeroEntropyWords))
        val beforeClear = mnemonic.entropyBytes()
        assertFalse(beforeClear.all { it == 0.toByte() }, "vector entropy must not already be all zero")

        mnemonic.clear()

        assertTrue(mnemonic.entropyBytes().all { it == 0.toByte() }, "clear() must zero the retained entropy")
    }

    @Test
    fun entropyBytes_returnsIndependentCopy() {
        val mnemonic = okMnemonic(Mnemonic.parse(validWords))

        val first = mnemonic.entropyBytes()
        first[0] = 0x7F

        assertFalse(
            mnemonic.entropyBytes()[0] == 0x7F.toByte(),
            "mutating a returned copy must not affect the Mnemonic's internal entropy",
        )
    }

    @Test
    fun toString_isStructuralAndDoesNotRenderWordsOrEntropy() {
        val mnemonic = okMnemonic(Mnemonic.parse(validWords))

        val text = mnemonic.toString()

        assertEquals("Mnemonic(wordCount=12)", text)
        assertFalse(text.contains("abandon"), "toString must not render the mnemonic words")
    }

    private fun okMnemonic(result: KardanoResult<Mnemonic, MnemonicError>): Mnemonic =
        when (result) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }
}
