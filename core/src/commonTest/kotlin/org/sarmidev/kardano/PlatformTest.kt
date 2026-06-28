package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertTrue

class PlatformTest {

    @Test
    fun platformNameIsNotBlank() {
        assertTrue(getPlatform().name.isNotBlank())
    }
}
