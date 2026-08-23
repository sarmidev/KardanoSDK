package org.sarmidev.kardano.playground.data

import org.sarmidev.kardano.playground.PlaygroundProviderMode
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
 * as before. [mode] reports that effective choice as [PlaygroundProviderMode].
 *
 * Live providers are cached by the last non-blank project id so a repeated live request can
 * reuse the same Blockfrost client. That in-memory cache is dropped when the project id
 * changes **or** live mode is disabled (toggle off, or a blank id). The cache key is a second
 * in-memory copy of the id — [org.sarmidev.kardano.playground.mvi.PlaygroundState.projectId] is
 * not the only place the session holds it. The id is never persisted or logged: this class has
 * no logger, no disk write, and no string interpolation of the id into messages.
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

    /**
     * Effective provider mode: [PlaygroundProviderMode.LivePreprod] only when [useLive] is `true`
     * and [projectId] is non-blank after trim; otherwise [PlaygroundProviderMode.Mock].
     */
    fun mode(useLive: Boolean, projectId: String): PlaygroundProviderMode =
        if (useLive && projectId.trim().isNotBlank()) {
            PlaygroundProviderMode.LivePreprod
        } else {
            PlaygroundProviderMode.Mock
        }

    /** The active query provider: mock unless [useLive] is `true` and [projectId] is non-blank. */
    fun queryProvider(useLive: Boolean, projectId: String): ChainQueryProvider {
        if (mode(useLive, projectId) != PlaygroundProviderMode.LivePreprod) {
            invalidateLiveCache()
            return mockQueryProvider
        }
        refreshLiveProvidersIfNeeded(projectId)
        return cachedLiveQueryProvider ?: mockQueryProvider
    }

    /** The active submit provider: mock unless [useLive] is `true` and [projectId] is non-blank. */
    fun submitProvider(useLive: Boolean, projectId: String): TxSubmitProvider {
        if (mode(useLive, projectId) != PlaygroundProviderMode.LivePreprod) {
            invalidateLiveCache()
            return mockSubmitProvider
        }
        refreshLiveProvidersIfNeeded(projectId)
        return cachedLiveSubmitProvider ?: mockSubmitProvider
    }

    private fun refreshLiveProvidersIfNeeded(projectId: String) {
        val trimmed = projectId.trim()
        if (trimmed == cachedProjectId && cachedLiveQueryProvider != null) return
        cachedProjectId = trimmed
        val config = BlockfrostConfig(projectId = trimmed)
        cachedLiveQueryProvider = BlockfrostChainQueryProvider.create(config)
        cachedLiveSubmitProvider = BlockfrostTxSubmitProvider.create(config)
    }

    private fun invalidateLiveCache() {
        cachedProjectId = null
        cachedLiveQueryProvider = null
        cachedLiveSubmitProvider = null
    }
}
