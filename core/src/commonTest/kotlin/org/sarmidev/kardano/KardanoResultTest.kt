package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class KardanoResultTest {

    @Test
    fun okExposesValueAndNullError() {
        val result: KardanoResult<Int, String> = KardanoResult.Ok(42)
        assertEquals(42, result.getOrNull())
        assertNull(result.errorOrNull())
    }

    @Test
    fun errExposesErrorAndNullValue() {
        val result: KardanoResult<Int, String> = KardanoResult.Err("e")
        assertNull(result.getOrNull())
        assertEquals("e", result.errorOrNull())
    }
}
