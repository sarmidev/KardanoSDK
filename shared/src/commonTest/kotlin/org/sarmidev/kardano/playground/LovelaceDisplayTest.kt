package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.LovelaceError
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

/** Unit tests for [LovelaceDisplay] (Block 1.12-pre-e). */
class LovelaceDisplayTest {

    private fun lovelace(value: Long): Lovelace = assertIs<KardanoResult.Ok<Lovelace>>(Lovelace.of(value)).value

    @Test
    fun ada_zero_isZeroAda() {
        assertEquals("0 ADA", LovelaceDisplay.ada(lovelace(0L)))
    }

    @Test
    fun ada_oneLovelace_showsTinyFraction() {
        assertEquals("0.000001 ADA", LovelaceDisplay.ada(lovelace(1L)))
    }

    @Test
    fun ada_justUnderOneAda_showsFullFraction() {
        assertEquals("0.999999 ADA", LovelaceDisplay.ada(lovelace(999_999L)))
    }

    @Test
    fun ada_exactlyOneAda_hasNoFraction() {
        assertEquals("1 ADA", LovelaceDisplay.ada(lovelace(1_000_000L)))
    }

    @Test
    fun ada_oneAndAHalf_trimsTrailingZeros() {
        assertEquals("1.5 ADA", LovelaceDisplay.ada(lovelace(1_500_000L)))
    }

    @Test
    fun ada_thirteenAda_hasNoFraction() {
        assertEquals("13 ADA", LovelaceDisplay.ada(lovelace(13_000_000L)))
    }

    @Test
    fun ada_maxLong_doesNotThrow() {
        val result = LovelaceDisplay.ada(lovelace(Long.MAX_VALUE))
        assertEquals(true, result.endsWith("ADA"))
    }

    /**
     * W9-7 (2026-08-22 pre-release audit): a raw negative `Long` can no longer reach [LovelaceDisplay.ada]
     * at all — [Lovelace.of] rejects it first, at construction time, before any display formatting
     * is attempted. This pins that rejection as the actual, tested contract rather than an
     * un-asserted assumption every current caller happened to satisfy.
     */
    @Test
    fun negativeLovelace_isRejectedAtConstructionBeforeItCanReachAda() {
        val error = assertIs<KardanoResult.Err<LovelaceError>>(Lovelace.of(-1L))
        assertEquals(LovelaceError.Negative(-1L), error.error)
    }
}
