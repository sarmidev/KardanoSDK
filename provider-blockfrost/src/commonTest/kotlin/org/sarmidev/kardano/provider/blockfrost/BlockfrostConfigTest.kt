package org.sarmidev.kardano.provider.blockfrost

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Tests for [BlockfrostConfig], focused on not leaking the project id via [toString]. */
class BlockfrostConfigTest {

    @Test
    fun toStringRedactsProjectIdButMentionsNetwork() {
        val secret = "test-project-id-that-must-not-render"
        val rendered = BlockfrostConfig(projectId = secret, network = BlockfrostNetwork.PREPROD)
            .toString()
        assertFalse(rendered.contains(secret), "toString must not expose the project id")
        assertTrue(rendered.contains("redacted"), "toString should mark the key as redacted")
        assertTrue(rendered.contains("PREPROD"), "toString should mention the network")
    }
}
