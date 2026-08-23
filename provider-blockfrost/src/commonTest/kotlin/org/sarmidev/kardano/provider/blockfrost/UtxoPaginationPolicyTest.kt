package org.sarmidev.kardano.provider.blockfrost

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertTrue

/**
 * Construction-time invariants for the internal [UtxoPaginationPolicy] seam.
 * Cases use extreme `Int` bounds only — they do not allocate large pages.
 */
class UtxoPaginationPolicyTest {

    @Test
    fun defaultCapIsTenThousand() {
        assertEquals(100, UtxoPaginationPolicy.Default.pageCount)
        assertEquals(100, UtxoPaginationPolicy.Default.maxPages)
        assertEquals(10_000, UtxoPaginationPolicy.Default.cap)
    }

    @Test
    fun rejectsNonPositivePageCount() {
        val zero = assertFails { UtxoPaginationPolicy(pageCount = 0, maxPages = 1) }
        assertTrue(zero is IllegalArgumentException)
        assertEquals("pageCount must be positive", zero.message)
        val negative = assertFails { UtxoPaginationPolicy(pageCount = -1, maxPages = 1) }
        assertEquals("pageCount must be positive", negative.message)
    }

    @Test
    fun rejectsNonPositiveMaxPages() {
        val zero = assertFails { UtxoPaginationPolicy(pageCount = 1, maxPages = 0) }
        assertTrue(zero is IllegalArgumentException)
        assertEquals("maxPages must be positive", zero.message)
        val negative = assertFails { UtxoPaginationPolicy(pageCount = 1, maxPages = -1) }
        assertEquals("maxPages must be positive", negative.message)
    }

    @Test
    fun rejectsMaxPagesAtIntMaxSoPlusOneCannotOverflow() {
        val failure = assertFails {
            UtxoPaginationPolicy(pageCount = 1, maxPages = Int.MAX_VALUE)
        }
        assertTrue(failure is IllegalArgumentException)
        assertEquals(
            "maxPages must be less than Int.MAX_VALUE so maxPages + 1 cannot overflow",
            failure.message,
        )
    }

    @Test
    fun rejectsPageCountTimesMaxPagesOverflowingInt() {
        val failure = assertFails {
            UtxoPaginationPolicy(pageCount = Int.MAX_VALUE, maxPages = 2)
        }
        assertTrue(failure is IllegalArgumentException)
        assertEquals("pageCount * maxPages overflows Int", failure.message)
    }

    @Test
    fun acceptsMaxPagesJustBelowIntMaxWithPageCountOne() {
        val policy = UtxoPaginationPolicy(pageCount = 1, maxPages = Int.MAX_VALUE - 1)
        assertEquals(Int.MAX_VALUE - 1, policy.cap)
        assertEquals(Int.MAX_VALUE, policy.maxPages + 1)
    }
}
