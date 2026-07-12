package org.sarmidev.kardano.crypto.mnemonic

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

/**
 * Structural tests for [Bip39EnglishWordlist]: shape and lookup invariants only. The word
 * content itself is verified against the cited source by the round-trip vectors in
 * [MnemonicVectorsTest] (entropy decoded through this wordlist must match cited entropy).
 */
class Bip39EnglishWordlistTest {

    @Test
    fun words_hasExactlySize2048EntriesAllUnique() {
        assertEquals(Bip39EnglishWordlist.SIZE, Bip39EnglishWordlist.words.size)
        assertEquals(Bip39EnglishWordlist.SIZE, Bip39EnglishWordlist.words.toSet().size)
    }

    @Test
    fun indexOf_isConsistentWithWordsOrder() {
        assertEquals(0, Bip39EnglishWordlist.indexOf("abandon"))
        assertEquals(Bip39EnglishWordlist.SIZE - 1, Bip39EnglishWordlist.indexOf("zoo"))
        for ((index, word) in Bip39EnglishWordlist.words.withIndex()) {
            assertEquals(index, Bip39EnglishWordlist.indexOf(word), "mismatch for word '$word'")
        }
    }

    @Test
    fun indexOf_returnsNullForUnknownWord() {
        assertNull(Bip39EnglishWordlist.indexOf("notabip39word"))
        assertNull(Bip39EnglishWordlist.indexOf("ABANDON"))
    }
}
