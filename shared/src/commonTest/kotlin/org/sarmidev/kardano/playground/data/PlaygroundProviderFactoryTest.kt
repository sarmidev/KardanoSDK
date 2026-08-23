package org.sarmidev.kardano.playground.data

import org.sarmidev.kardano.playground.PlaygroundProviderMode
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Unit tests for [PlaygroundProviderFactory] cache invalidation and [PlaygroundProviderMode]
 * reporting. Dummy project-id strings used here are not credentials and must never appear in
 * assertion messages or logs.
 */
class PlaygroundProviderFactoryTest {

    @Test
    fun mode_blankOrToggleOff_isMock() {
        val factory = PlaygroundProviderFactory()

        assertEquals(PlaygroundProviderMode.Mock, factory.mode(useLive = false, projectId = ""))
        assertEquals(PlaygroundProviderMode.Mock, factory.mode(useLive = true, projectId = ""))
        assertEquals(PlaygroundProviderMode.Mock, factory.mode(useLive = true, projectId = "   "))
    }

    @Test
    fun mode_liveToggleWithNonBlankId_isLivePreprod() {
        val factory = PlaygroundProviderFactory()

        assertEquals(
            PlaygroundProviderMode.LivePreprod,
            factory.mode(useLive = true, projectId = "session-id"),
        )
    }

    @Test
    fun liveCache_reusesInstanceForTheSameId() {
        val factory = PlaygroundProviderFactory()
        val first = factory.queryProvider(useLive = true, projectId = "session-id")
        val second = factory.queryProvider(useLive = true, projectId = "session-id")

        assertTrue(first === second)
        assertEquals(PlaygroundProviderMode.LivePreprod, factory.mode(true, "session-id"))
    }

    @Test
    fun liveCache_isRebuiltWhenTheIdChanges() {
        val factory = PlaygroundProviderFactory()
        val first = factory.queryProvider(useLive = true, projectId = "session-id-a")
        val second = factory.queryProvider(useLive = true, projectId = "session-id-b")

        assertTrue(first !== second)
    }

    @Test
    fun liveCache_isDroppedWhenLiveModeIsDisabled() {
        val factory = PlaygroundProviderFactory()
        val live = factory.queryProvider(useLive = true, projectId = "session-id")
        val mock = factory.queryProvider(useLive = false, projectId = "session-id")
        val liveAgain = factory.queryProvider(useLive = true, projectId = "session-id")

        assertTrue(live !== mock)
        assertTrue(live !== liveAgain, "disabling live mode must drop the cached live provider")
        assertEquals(PlaygroundProviderMode.Mock, factory.mode(false, "session-id"))
    }
}
