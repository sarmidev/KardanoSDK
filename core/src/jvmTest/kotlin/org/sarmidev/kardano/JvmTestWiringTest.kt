package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertTrue

/**
 * Smoke test that verifies the `:core` JVM test source set is wired and runs.
 *
 * This is test-infrastructure coverage only (Phase 0 Block 0.3). It exercises no SDK
 * behavior; protocol logic is tested in `commonTest` once it exists.
 */
class JvmTestWiringTest {

    @Test
    fun jvmTestSourceSetRuns() {
        assertTrue(true)
    }
}
