package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

class LovelaceTest {

    @Test
    fun ofAcceptsZero() {
        val lovelace = assertIs<KardanoResult.Ok<Lovelace>>(Lovelace.of(0L))
        assertEquals(0L, lovelace.value.value)
    }

    @Test
    fun ofAcceptsPositiveValue() {
        val lovelace = assertIs<KardanoResult.Ok<Lovelace>>(Lovelace.of(1_000_000L))
        assertEquals(1_000_000L, lovelace.value.value)
    }

    @Test
    fun ofAcceptsMaxSupportedValue() {
        val lovelace = assertIs<KardanoResult.Ok<Lovelace>>(Lovelace.of(Long.MAX_VALUE))
        assertEquals(Long.MAX_VALUE, lovelace.value.value)
    }

    @Test
    fun ofRejectsNegativeValues() {
        for (value in listOf(-1L, Long.MIN_VALUE)) {
            val err = assertIs<KardanoResult.Err<LovelaceError>>(Lovelace.of(value))
            val negative = assertIs<LovelaceError.Negative>(err.error)
            assertEquals(value, negative.value)
        }
    }

    @Test
    fun zeroConstantHasZeroValue() {
        assertEquals(0L, Lovelace.ZERO.value)
    }

    @Test
    fun sameAmountsAreEqual() {
        val a = assertIs<KardanoResult.Ok<Lovelace>>(Lovelace.of(42L)).value
        val b = assertIs<KardanoResult.Ok<Lovelace>>(Lovelace.of(42L)).value
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }
}
