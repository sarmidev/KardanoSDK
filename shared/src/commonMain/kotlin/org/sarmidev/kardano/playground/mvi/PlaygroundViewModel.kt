package org.sarmidev.kardano.playground.mvi

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.playground.PlaygroundPresenter
import org.sarmidev.kardano.playground.PlaygroundProviderMode
import org.sarmidev.kardano.playground.data.PlaygroundProviderFactory
import org.sarmidev.kardano.playground.withProvenance
import org.sarmidev.kardano.playground.domain.BuildTransactionDraftUseCase
import org.sarmidev.kardano.playground.domain.LoadProviderParamsUseCase
import org.sarmidev.kardano.playground.domain.LoadProviderUtxosUseCase
import org.sarmidev.kardano.playground.domain.QueryWalletFundsUseCase
import org.sarmidev.kardano.playground.domain.RestoreWalletUseCase
import org.sarmidev.kardano.playground.domain.SignTransactionUseCase
import org.sarmidev.kardano.playground.domain.SubmitTransactionUseCase
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.TxSubmitProvider

/**
 * Owns [PlaygroundState] and handles every [PlaygroundIntent] dispatched by
 * [org.sarmidev.kardano.playground.PlaygroundScreen] (Block 1.12-pre-a).
 *
 * Intents that need no SDK/provider call (provider-selection toggles, text-field edits, seed
 * fill, technical-details toggling, [PlaygroundIntent.ResetFlow]) are folded synchronously
 * through [PlaygroundReducer.reduce]. Intents that call an SDK API go through the injected
 * use cases (guided-flow steps: [restoreWallet], [queryWalletFunds], [buildTransactionDraft],
 * [signTransaction], [submitTransaction]; diagnostics: [loadProviderUtxos],
 * [loadProviderParams]) or directly through [PlaygroundPresenter] (address/hex/CBOR), then fold
 * their result back into state through the matching `applyX`/`startXLoading` helper. This class
 * contains no derivation, hashing, address-generation, balance, coin-selection, fee/change,
 * signing, or submission logic of its own — every one of those still lives in
 * `:core`/`:crypto`/`:wallet`/`:tx`/`:provider`, reached only through the use cases and
 * [PlaygroundPresenter].
 *
 * [providerFactory] selects the active [ChainQueryProvider]/[TxSubmitProvider] pair from the
 * current [PlaygroundState.useLiveBlockfrost]/[PlaygroundState.projectId] for every provider-
 * dependent operation — the same mock-by-default / live-Blockfrost-preprod-when-configured
 * behavior the pre-1.12-pre-a screen had.
 *
 * Provider-backed operations capture [PlaygroundState.flowGeneration] and the matching
 * per-operation request token at start and fold the result back only when both still match.
 * Starting Funds/Build/Sign also cancels downstream guided Jobs and, in the same reducer
 * transition, clears those presentations and increments their tokens.
 * Diagnostic UTxO/params loads also capture a request token (and the explorer address for
 * UTxOs). A result that still completes after [Job] cancellation is folded under
 * [NonCancellable] so the identity check — not cooperative cancellation — is what discards
 * it. [PlaygroundIntent.ResetFlow] and actual provider-configuration changes cancel in-flight
 * [Job]s and increment the generation and the relevant request tokens in the reducer (the
 * reducer itself remains a pure function). Actual project-id changes and disabling live mode
 * also call the internal [PlaygroundProviderFactory.invalidateLiveCache] immediately. This is
 * sample/diagnostic code in `:shared`; it is not part of the SDK public API.
 */
internal class PlaygroundViewModel(
    private val restoreWallet: RestoreWalletUseCase = RestoreWalletUseCase.Default,
    private val queryWalletFunds: QueryWalletFundsUseCase = QueryWalletFundsUseCase.Default,
    private val buildTransactionDraft: BuildTransactionDraftUseCase = BuildTransactionDraftUseCase.Default,
    private val signTransaction: SignTransactionUseCase = SignTransactionUseCase.Default,
    private val submitTransaction: SubmitTransactionUseCase = SubmitTransactionUseCase.Default,
    private val loadProviderUtxos: LoadProviderUtxosUseCase = LoadProviderUtxosUseCase.Default,
    private val loadProviderParams: LoadProviderParamsUseCase = LoadProviderParamsUseCase.Default,
    private val providerFactory: PlaygroundProviderFactory = PlaygroundProviderFactory(),
) : ViewModel() {

    private val mutableState = MutableStateFlow(PlaygroundState.initial())

    private var fundsJob: Job? = null
    private var draftJob: Job? = null
    private var signedJob: Job? = null
    private var submitJob: Job? = null
    private var providerUtxosJob: Job? = null
    private var providerParamsJob: Job? = null

    /** The current [PlaygroundState], observed by [org.sarmidev.kardano.playground.PlaygroundScreen]. */
    val state: StateFlow<PlaygroundState> = mutableState.asStateFlow()

    /** Handles [intent]. See class KDoc for the sync-reducer vs. use-case/presenter split. */
    fun dispatch(intent: PlaygroundIntent) {
        when (intent) {
            is PlaygroundIntent.RestoreWallet -> onRestoreWallet()
            is PlaygroundIntent.QueryFunds -> onQueryFunds()
            is PlaygroundIntent.BuildDraft -> onBuildDraft()
            is PlaygroundIntent.SignTransaction -> onSignTransaction()
            is PlaygroundIntent.SubmitTransaction -> onSubmitTransaction()
            is PlaygroundIntent.ParseAddress -> onParseAddress()
            is PlaygroundIntent.DecodeHex -> onDecodeHex()
            is PlaygroundIntent.DecodeCbor -> onDecodeCbor()
            is PlaygroundIntent.LoadProviderUtxos -> onLoadProviderUtxos()
            is PlaygroundIntent.LoadProviderParams -> onLoadProviderParams()
            is PlaygroundIntent.ResetFlow -> {
                cancelInFlightOperations()
                mutableState.update { PlaygroundReducer.reduce(it, intent) }
            }
            is PlaygroundIntent.ToggleLiveBlockfrost -> {
                if (intent.enabled != mutableState.value.useLiveBlockfrost) {
                    cancelInFlightOperations()
                    if (!intent.enabled) {
                        providerFactory.invalidateLiveCache()
                    }
                }
                mutableState.update { PlaygroundReducer.reduce(it, intent) }
            }
            is PlaygroundIntent.UpdateProjectId -> {
                if (intent.value != mutableState.value.projectId) {
                    cancelInFlightOperations()
                    providerFactory.invalidateLiveCache()
                }
                mutableState.update { PlaygroundReducer.reduce(it, intent) }
            }
            is PlaygroundIntent.UpdateProviderAddressInput,
            is PlaygroundIntent.FillSeedAddress,
            -> {
                val previousAddress = mutableState.value.providerAddressInput
                mutableState.update { PlaygroundReducer.reduce(it, intent) }
                if (mutableState.value.providerAddressInput != previousAddress) {
                    providerUtxosJob?.cancel()
                    providerUtxosJob = null
                }
            }
            else -> mutableState.update { PlaygroundReducer.reduce(it, intent) }
        }
    }

    private fun cancelInFlightOperations() {
        fundsJob?.cancel()
        fundsJob = null
        draftJob?.cancel()
        draftJob = null
        signedJob?.cancel()
        signedJob = null
        submitJob?.cancel()
        submitJob = null
        providerUtxosJob?.cancel()
        providerUtxosJob = null
        providerParamsJob?.cancel()
        providerParamsJob = null
    }

    private fun activeQueryProvider(): ChainQueryProvider = providerFactory.queryProvider(
        useLive = mutableState.value.useLiveBlockfrost,
        projectId = mutableState.value.projectId,
    )

    private fun activeSubmitProvider(): TxSubmitProvider = providerFactory.submitProvider(
        useLive = mutableState.value.useLiveBlockfrost,
        projectId = mutableState.value.projectId,
    )

    private fun activeProviderMode(): PlaygroundProviderMode = providerFactory.mode(
        useLive = mutableState.value.useLiveBlockfrost,
        projectId = mutableState.value.projectId,
    )

    // --- Guided flow: Wallet -> Funds -> Build -> Sign -> Submit ---

    // Restoring the fixture wallet is synchronous (no provider call, no suspend boundary), the
    // same as the pre-1.12-pre-a screen's plain button onClick — no coroutine is needed.
    private fun onRestoreWallet() {
        mutableState.update(PlaygroundReducer::startWalletLoading)
        val result = restoreWallet()
        mutableState.update { PlaygroundReducer.applyWalletResult(it, result) }
    }

    private fun onQueryFunds() {
        fundsJob?.cancel()
        draftJob?.cancel()
        draftJob = null
        signedJob?.cancel()
        signedJob = null
        submitJob?.cancel()
        submitJob = null
        val mode = activeProviderMode()
        mutableState.update(PlaygroundReducer::startFundsLoading)
        val generation = mutableState.value.flowGeneration
        val requestToken = mutableState.value.fundsRequestToken
        val provider = activeQueryProvider()
        fundsJob = viewModelScope.launch {
            val result = queryWalletFunds(provider).withProvenance(mode, generation)
            withContext(NonCancellable) {
                mutableState.update {
                    PlaygroundReducer.applyFundsResult(it, result, generation, requestToken)
                }
            }
        }
    }

    private fun onBuildDraft() {
        draftJob?.cancel()
        signedJob?.cancel()
        signedJob = null
        submitJob?.cancel()
        submitJob = null
        val mode = activeProviderMode()
        mutableState.update(PlaygroundReducer::startDraftLoading)
        val generation = mutableState.value.flowGeneration
        val requestToken = mutableState.value.draftRequestToken
        val provider = activeQueryProvider()
        draftJob = viewModelScope.launch {
            val result = buildTransactionDraft(provider).withProvenance(mode, generation)
            withContext(NonCancellable) {
                mutableState.update {
                    PlaygroundReducer.applyDraftResult(it, result, generation, requestToken)
                }
            }
        }
    }

    private fun onSignTransaction() {
        signedJob?.cancel()
        submitJob?.cancel()
        submitJob = null
        val mode = activeProviderMode()
        mutableState.update(PlaygroundReducer::startSignedLoading)
        val generation = mutableState.value.flowGeneration
        val requestToken = mutableState.value.signedRequestToken
        val provider = activeQueryProvider()
        signedJob = viewModelScope.launch {
            val result = signTransaction(provider).withProvenance(mode, generation)
            withContext(NonCancellable) {
                mutableState.update {
                    PlaygroundReducer.applySignedResult(it, result, generation, requestToken)
                }
            }
        }
    }

    private fun onSubmitTransaction() {
        submitJob?.cancel()
        val mode = activeProviderMode()
        mutableState.update(PlaygroundReducer::startSubmitLoading)
        val generation = mutableState.value.flowGeneration
        val requestToken = mutableState.value.submitRequestToken
        val queryProvider = activeQueryProvider()
        val submitProvider = activeSubmitProvider()
        submitJob = viewModelScope.launch {
            val result = submitTransaction(queryProvider, submitProvider).withProvenance(mode, generation)
            withContext(NonCancellable) {
                mutableState.update {
                    PlaygroundReducer.applySubmitResult(it, result, generation, requestToken)
                }
            }
        }
    }

    // --- Diagnostics: Address Parser, Hex Decoder, CBOR Decoder, Provider explorer ---

    // Address/hex/CBOR decoding are synchronous (no provider call), same as their pre-1.12-pre-a
    // plain button onClicks.
    private fun onParseAddress() {
        val result = PlaygroundPresenter.presentAddress(Address.parse(mutableState.value.addressInput.trim()))
        mutableState.update { PlaygroundReducer.applyAddressResult(it, result) }
    }

    private fun onDecodeHex() {
        val result = PlaygroundPresenter.presentHexDecode(mutableState.value.hexInput)
        mutableState.update { PlaygroundReducer.applyHexResult(it, result) }
    }

    private fun onDecodeCbor() {
        val result = PlaygroundPresenter.presentCbor(mutableState.value.cborInput)
        mutableState.update { PlaygroundReducer.applyCborResult(it, result) }
    }

    private fun onLoadProviderUtxos() {
        providerUtxosJob?.cancel()
        val mode = activeProviderMode()
        mutableState.update(PlaygroundReducer::startProviderUtxosLoading)
        val generation = mutableState.value.flowGeneration
        val requestToken = mutableState.value.providerUtxosRequestToken
        val addressInput = mutableState.value.providerAddressInput
        val provider = activeQueryProvider()
        providerUtxosJob = viewModelScope.launch {
            val result = loadProviderUtxos(provider, addressInput).withProvenance(mode, generation)
            withContext(NonCancellable) {
                mutableState.update {
                    PlaygroundReducer.applyProviderUtxosResult(
                        it,
                        result,
                        generation,
                        requestToken,
                        addressInput,
                    )
                }
            }
        }
    }

    private fun onLoadProviderParams() {
        providerParamsJob?.cancel()
        val mode = activeProviderMode()
        mutableState.update(PlaygroundReducer::startProviderParamsLoading)
        val generation = mutableState.value.flowGeneration
        val requestToken = mutableState.value.providerParamsRequestToken
        val provider = activeQueryProvider()
        providerParamsJob = viewModelScope.launch {
            val result = loadProviderParams(provider).withProvenance(mode, generation)
            withContext(NonCancellable) {
                mutableState.update {
                    PlaygroundReducer.applyProviderParamsResult(it, result, generation, requestToken)
                }
            }
        }
    }
}
