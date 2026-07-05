package org.sarmidev.kardano.provider.blockfrost

import kotlinx.coroutines.runBlocking
import org.sarmidev.kardano.KardanoResult
import kotlin.test.Test
import kotlin.test.assertTrue

/**
 * Opt-in integration test that hits the real Blockfrost preprod API.
 *
 * It is **skipped by default**: it runs only when a `BLOCKFROST_PROJECT_ID` environment
 * variable is present, so the normal unit suite never touches the network and never needs a
 * key. Supply your own preprod project id to run it locally:
 *
 * ```
 * BLOCKFROST_PROJECT_ID=preprod... ./gradlew :provider-blockfrost:jvmTest
 * ```
 *
 * The key is read from the environment only; it is never committed.
 */
class BlockfrostLiveIntegrationTest {

    @Test
    fun getTipAgainstLivePreprod() = runBlocking {
        val projectId = System.getenv(PROJECT_ID_ENV)
        if (projectId.isNullOrBlank()) {
            println("Skipping live Blockfrost test: $PROJECT_ID_ENV not set")
            return@runBlocking
        }
        val provider = BlockfrostChainQueryProvider.create(BlockfrostConfig(projectId))
        val result = provider.getTip()
        assertTrue(result is KardanoResult.Ok, "live getTip failed: $result")
    }

    private companion object {
        const val PROJECT_ID_ENV = "BLOCKFROST_PROJECT_ID"
    }
}
