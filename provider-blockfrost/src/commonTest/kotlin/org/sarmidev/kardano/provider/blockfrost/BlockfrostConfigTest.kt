package org.sarmidev.kardano.provider.blockfrost

import kotlin.test.Test
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Tests for [BlockfrostConfig], focused on not leaking the project id via [toString],
 * assertion messages, or collection rendering, and on identity (not value) equality.
 */
class BlockfrostConfigTest {

    private companion object {
        const val SECRET: String = "test-project-id-that-must-not-render"
    }

    @Test
    fun toStringRedactsProjectIdButMentionsNetwork() {
        val rendered = BlockfrostConfig(projectId = SECRET, network = BlockfrostNetwork.PREPROD)
            .toString()
        assertFalse(rendered.contains(SECRET), "toString must not expose the project id")
        assertTrue(rendered.contains("redacted"), "toString should mark the key as redacted")
        assertTrue(rendered.contains("PREPROD"), "toString should mention the network")
    }

    @Test
    fun sameFieldValuesAreNotEqualAcrossInstances() {
        val a = BlockfrostConfig(projectId = SECRET, network = BlockfrostNetwork.PREPROD)
        val b = BlockfrostConfig(projectId = SECRET, network = BlockfrostNetwork.PREPROD)
        assertFalse(a == b, "identity equality: distinct instances must not compare equal")
        assertFalse(a.equals(b))
        assertTrue(a == a)
        val set = hashSetOf(a, b)
        assertTrue(set.size == 2, "identity hashing keeps both same-value instances")
        assertTrue(a in set)
        assertFalse(
            BlockfrostConfig(projectId = SECRET, network = BlockfrostNetwork.PREPROD) in set,
            "a new instance with the same fields must not match by value",
        )
    }

    @Test
    fun listSetAndMapRenderingDoesNotExposeProjectId() {
        val config = BlockfrostConfig(projectId = SECRET, network = BlockfrostNetwork.PREVIEW)
        val listRendered = listOf(config).toString()
        val setRendered = setOf(config).toString()
        val mapRendered = mapOf(config to "value").toString()
        assertFalse(listRendered.contains(SECRET), "List.toString leaked the project id: $listRendered")
        assertFalse(setRendered.contains(SECRET), "Set.toString leaked the project id: $setRendered")
        assertFalse(mapRendered.contains(SECRET), "Map.toString leaked the project id: $mapRendered")
        assertTrue(listRendered.contains("redacted"), "List.toString should use the redacted form")
        assertTrue(setRendered.contains("PREVIEW"), "Set.toString should mention the network")
    }

    @Test
    fun assertionFailureMessageDoesNotExposeProjectId() {
        val config = BlockfrostConfig(projectId = SECRET, network = BlockfrostNetwork.MAINNET)
        val failure = assertFails {
            assertTrue(config.toString() == "unrelated-sentinel-that-cannot-match")
        }
        val message = failure.message ?: ""
        assertFalse(message.contains(SECRET), "assertion message leaked the project id: $message")
        val equalsFailure = assertFails {
            kotlin.test.assertEquals<Any>("unrelated-sentinel-that-cannot-match", config)
        }
        val equalsMessage = equalsFailure.message ?: ""
        assertFalse(
            equalsMessage.contains(SECRET),
            "assertEquals message leaked the project id: $equalsMessage",
        )
        assertTrue(
            equalsMessage.contains("redacted") || equalsMessage.contains("BlockfrostConfig"),
            "assertEquals should render the redacted config, got: $equalsMessage",
        )
    }
}
