package org.sarmidev.kardano.playground

import kotlin.test.Test
import kotlin.test.assertEquals

/** Unit tests for [LovelaceDisplay] (Block 1.12-pre-e). */
class LovelaceDisplayTest {

    @Test
    fun ada_zero_isZeroAda() {
        assertEquals("0 ADA", LovelaceDisplay.ada(0L))
    }

    @Test
    fun ada_oneLovelace_showsTinyFraction() {
        assertEquals("0.000001 ADA", LovelaceDisplay.ada(1L))
    }

    @Test
    fun ada_justUnderOneAda_showsFullFraction() {
        assertEquals("0.999999 ADA", LovelaceDisplay.ada(999_999L))
    }

    @Test
    fun ada_exactlyOneAda_hasNoFraction() {
        assertEquals("1 ADA", LovelaceDisplay.ada(1_000_000L))
    }

    @Test
    fun ada_oneAndAHalf_trimsTrailingZeros() {
        assertEquals("1.5 ADA", LovelaceDisplay.ada(1_500_000L))
    }

    @Test
    fun ada_thirteenAda_hasNoFraction() {
        assertEquals("13 ADA", LovelaceDisplay.ada(13_000_000L))
    }

    @Test
    fun ada_maxLong_doesNotThrow() {
        val result = LovelaceDisplay.ada(Long.MAX_VALUE)
        assertEquals(true, result.endsWith("ADA"))
    }
}
