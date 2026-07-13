package org.sarmidev.kardano.playground.data

import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.provider.InMemoryTxSubmitProvider
import org.sarmidev.kardano.provider.TxSubmitProvider
import org.sarmidev.kardano.provider.blockfrost.BlockfrostChainQueryProvider
import org.sarmidev.kardano.provider.blockfrost.BlockfrostConfig
import org.sarmidev.kardano.provider.blockfrost.BlockfrostTxSubmitProvider

/**
 * Selects the active [ChainQueryProvider]/[TxSubmitProvider] pair for the Playground, moved out
 * of the Compose layer so [org.sarmidev.kardano.playground.mvi.PlaygroundViewModel] can build
 * providers from [org.sarmidev.kardano.playground.mvi.PlaygroundState] without a `remember`
 * block. Behavior is unchanged from the pre-1.12-pre-a screen: the default is the in-memory
 * mock ([InMemoryChainQueryProvider]/[InMemoryTxSubmitProvider], fake/test-only, no network);
 * passing `useLive = true` with a non-blank `projectId` switches both to live Blockfrost preprod
 * ([BlockfrostChainQueryProvider]/[BlockfrostTxSubmitProvider]) built from the same
 * `project_id`. A blank `projectId` falls back to the mock even when `useLive` is `true`, same
 * as before.
 *
 * The live providers are rebuilt only when `projectId` actually changes (simple
 * last-value cache), mirroring the previous `remember(projectId) { ... }` memoization. The
 * `project_id` string itself is never stored, saved, or logged by this class — it is only held
 * long enough to construct a [BlockfrostConfig].
 *
 * This is sample/diagnostic wiring in `:shared`, not part of the SDK public API.
 */
internal class PlaygroundProviderFactory {

    private val mockQueryProvider: ChainQueryProvider = InMemoryChainQueryProvider()
    private val mockSubmitProvider: TxSubmitProvider = InMemoryTxSubmitProvider()

    private var cachedProjectId: String? = null
    private var cachedLiveQueryProvider: ChainQueryProvider? = null
    private var cachedLiveSubmitProvider: TxSubmitProvider? = null

    /** The active query provider: mock unless [useLive] is `true` and [projectId] is non-blank. */
    fun queryProvider(useLive: Boolean, projectId: String): ChainQueryProvider {
        if (!useLive) return mockQueryProvider
        refreshLiveProvidersIfNeeded(projectId)
        return cachedLiveQueryProvider ?: mockQueryProvider
    }

    /** The active submit provider: mock unless [useLive] is `true` and [projectId] is non-blank. */
    fun submitProvider(useLive: Boolean, projectId: String): TxSubmitProvider {
        if (!useLive) return mockSubmitProvider
        refreshLiveProvidersIfNeeded(projectId)
        return cachedLiveSubmitProvider ?: mockSubmitProvider
    }

    private fun refreshLiveProvidersIfNeeded(projectId: String) {
        val trimmed = projectId.trim()
        if (trimmed == cachedProjectId) return
        cachedProjectId = trimmed
        if (trimmed.isBlank()) {
            cachedLiveQueryProvider = null
            cachedLiveSubmitProvider = null
            return
        }
        val config = BlockfrostConfig(projectId = trimmed)
        cachedLiveQueryProvider = BlockfrostChainQueryProvider.create(config)
        cachedLiveSubmitProvider = BlockfrostTxSubmitProvider.create(config)
    }
}
