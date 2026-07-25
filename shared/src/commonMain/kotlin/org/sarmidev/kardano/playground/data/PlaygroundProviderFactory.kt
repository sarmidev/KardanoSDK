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
 * block. The default is the in-memory mock ([InMemoryChainQueryProvider]/[InMemoryTxSubmitProvider],
 * fake/test-only, no network). Since Block 1.12-pre-c-3 the mock query provider is built by
 * [PlaygroundMockSampleData.buildMockQueryProvider], which seeds fake ADA-only UTxOs for the demo
 * wallet address so mock mode can run the whole Wallet -> Funds -> Build -> Sign flow offline; the
 * mock submit provider is unchanged and still honestly reports "submission not supported".
 * Passing `useLive = true` with a non-blank `projectId` switches both to live Blockfrost preprod
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

    // Built lazily: buildMockQueryProvider restores the fixture wallet (native derivation) once,
    // on first mock use, rather than at every ViewModel construction. Stable instance thereafter.
    private val mockQueryProvider: ChainQueryProvider by lazy {
        PlaygroundMockSampleData.buildMockQueryProvider()
    }
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
