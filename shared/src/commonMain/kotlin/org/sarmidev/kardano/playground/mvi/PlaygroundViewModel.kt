package org.sarmidev.kardano.playground.mvi

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.playground.PlaygroundPresenter
import org.sarmidev.kardano.playground.data.PlaygroundProviderFactory
import org.sarmidev.kardano.playground.domain.BuildTransactionDraftUseCase
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
 * [signTransaction], [submitTransaction]) or directly through [PlaygroundPresenter] (the
 * diagnostics tools: address/hex/CBOR, generic provider explorer), then fold their result back
 * into state through the matching `applyX`/`startXLoading` helper. This class contains no
 * derivation, hashing, address-generation, balance, coin-selection, fee/change, signing, or
 * submission logic of its own — every one of those still lives in `:core`/`:crypto`/`:wallet`/
 * `:tx`/`:provider`, reached only through the use cases and [PlaygroundPresenter].
 *
 * [providerFactory] selects the active [ChainQueryProvider]/[TxSubmitProvider] pair from the
 * current [PlaygroundState.useLiveBlockfrost]/[PlaygroundState.projectId] for every provider-
 * dependent operation — the same mock-by-default / live-Blockfrost-preprod-when-configured
 * behavior the pre-1.12-pre-a screen had.
 *
 * Provider-backed operations capture [PlaygroundState.flowGeneration] at start and fold the
 * result back only when that generation is still current. [PlaygroundIntent.ResetFlow] and
 * actual provider-configuration changes cancel in-flight [Job]s and increment the generation
 * in the reducer (the reducer itself remains a pure function). This is sample/diagnostic code
 * in `:shared`; it is not part of the SDK public API.
 */
internal class PlaygroundViewModel(
    private val restoreWallet: RestoreWalletUseCase = RestoreWalletUseCase.Default,
    private val queryWalletFunds: QueryWalletFundsUseCase = QueryWalletFundsUseCase.Default,
    private val buildTransactionDraft: BuildTransactionDraftUseCase = BuildTransactionDraftUseCase.Default,
    private val signTransaction: SignTransactionUseCase = SignTransactionUseCase.Default,
    private val submitTransaction: SubmitTransactionUseCase = SubmitTransactionUseCase.Default,
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
                }
                mutableState.update { PlaygroundReducer.reduce(it, intent) }
            }
            is PlaygroundIntent.UpdateProjectId -> {
                if (intent.value != mutableState.value.projectId) {
                    cancelInFlightOperations()
                }
                mutableState.update { PlaygroundReducer.reduce(it, intent) }
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
        val generation = mutableState.value.flowGeneration
        mutableState.update(PlaygroundReducer::startFundsLoading)
        val provider = activeQueryProvider()
        fundsJob = viewModelScope.launch {
            val result = queryWalletFunds(provider)
            mutableState.update { PlaygroundReducer.applyFundsResult(it, result, generation) }
        }
    }

    private fun onBuildDraft() {
        draftJob?.cancel()
        val generation = mutableState.value.flowGeneration
        mutableState.update(PlaygroundReducer::startDraftLoading)
        val provider = activeQueryProvider()
        draftJob = viewModelScope.launch {
            val result = buildTransactionDraft(provider)
            mutableState.update { PlaygroundReducer.applyDraftResult(it, result, generation) }
        }
    }

    private fun onSignTransaction() {
        signedJob?.cancel()
        val generation = mutableState.value.flowGeneration
        mutableState.update(PlaygroundReducer::startSignedLoading)
        val provider = activeQueryProvider()
        signedJob = viewModelScope.launch {
            val result = signTransaction(provider)
            mutableState.update { PlaygroundReducer.applySignedResult(it, result, generation) }
        }
    }

    private fun onSubmitTransaction() {
        submitJob?.cancel()
        val generation = mutableState.value.flowGeneration
        mutableState.update(PlaygroundReducer::startSubmitLoading)
        val queryProvider = activeQueryProvider()
        val submitProvider = activeSubmitProvider()
        submitJob = viewModelScope.launch {
            val result = submitTransaction(queryProvider, submitProvider)
            mutableState.update { PlaygroundReducer.applySubmitResult(it, result, generation) }
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
        val generation = mutableState.value.flowGeneration
        mutableState.update(PlaygroundReducer::startProviderUtxosLoading)
        val provider = activeQueryProvider()
        val addressInput = mutableState.value.providerAddressInput
        providerUtxosJob = viewModelScope.launch {
            val result = PlaygroundPresenter.presentProviderUtxos(provider, addressInput)
            mutableState.update { PlaygroundReducer.applyProviderUtxosResult(it, result, generation) }
        }
    }

    private fun onLoadProviderParams() {
        providerParamsJob?.cancel()
        val generation = mutableState.value.flowGeneration
        mutableState.update(PlaygroundReducer::startProviderParamsLoading)
        val provider = activeQueryProvider()
        providerParamsJob = viewModelScope.launch {
            val result = PlaygroundPresenter.presentProviderParams(provider)
            mutableState.update { PlaygroundReducer.applyProviderParamsResult(it, result, generation) }
        }
    }
}
