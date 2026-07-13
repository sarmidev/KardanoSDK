package org.sarmidev.kardano.tx

import kotlin.test.Test
import kotlin.test.assertTrue

/**
 * Smoke test that verifies the `:tx` common test source set is wired and runs.
 *
 * This is test-infrastructure coverage only (Phase 1 Block 1.9b-1). It exercises no SDK
 * behavior; [TransactionBodySerializer] behavior is tested in
 * [TransactionBodySerializerTest].
 */
class TxModuleWiringTest {

    @Test
    fun commonTestSourceSetRuns() {
        assertTrue(true)
    }
}
