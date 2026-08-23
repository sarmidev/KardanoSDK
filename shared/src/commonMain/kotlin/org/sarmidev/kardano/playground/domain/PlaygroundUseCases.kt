package org.sarmidev.kardano.playground.domain

import org.sarmidev.kardano.playground.PlaygroundPresenter
import org.sarmidev.kardano.playground.ProviderParamsPresentation
import org.sarmidev.kardano.playground.ProviderUtxosPresentation
import org.sarmidev.kardano.playground.SignedTransactionPresentation
import org.sarmidev.kardano.playground.SubmitTransactionPresentation
import org.sarmidev.kardano.playground.TransactionDraftPresentation
import org.sarmidev.kardano.playground.WalletBalancePresentation
import org.sarmidev.kardano.playground.WalletPresentation
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.TxSubmitProvider

/**
 * Restores the test-only fixture wallet and generates its structural address (Wallet step).
 *
 * Thin wrapper over [PlaygroundPresenter.presentTestWallet] — no derivation, hashing, or
 * address-generation logic of its own. Exists so [org.sarmidev.kardano.playground.mvi.PlaygroundViewModel]
 * depends on a small, fakeable seam instead of the presenter object directly, for testing.
 */
internal fun interface RestoreWalletUseCase {
    operator fun invoke(): WalletPresentation

    companion object {
        val Default = RestoreWalletUseCase { PlaygroundPresenter.presentTestWallet() }
    }
}

/**
 * Queries [provider] for the fixture wallet's balance (Funds step).
 *
 * Thin wrapper over [PlaygroundPresenter.presentWalletBalance] — no restore, query, or
 * balance-summation logic of its own.
 */
internal fun interface QueryWalletFundsUseCase {
    suspend operator fun invoke(provider: ChainQueryProvider): WalletBalancePresentation

    companion object {
        val Default = QueryWalletFundsUseCase { provider ->
            PlaygroundPresenter.presentWalletBalance(provider)
        }
    }
}

/**
 * Builds the unsigned minimal-ADA transaction draft from [provider]'s UTxOs (Build step).
 *
 * Thin wrapper over [PlaygroundPresenter.presentTransactionDraft] — no coin-selection, fee, or
 * change logic of its own.
 */
internal fun interface BuildTransactionDraftUseCase {
    suspend operator fun invoke(provider: ChainQueryProvider): TransactionDraftPresentation

    companion object {
        val Default = BuildTransactionDraftUseCase { provider ->
            PlaygroundPresenter.presentTransactionDraft(provider)
        }
    }
}

/**
 * Builds the same draft and signs it, but does not submit it (Sign step).
 *
 * Thin wrapper over [PlaygroundPresenter.presentSignedTransaction] — no signing or
 * witness/transaction-assembly logic of its own.
 */
internal fun interface SignTransactionUseCase {
    suspend operator fun invoke(provider: ChainQueryProvider): SignedTransactionPresentation

    companion object {
        val Default = SignTransactionUseCase { provider ->
            PlaygroundPresenter.presentSignedTransaction(provider)
        }
    }
}

/**
 * Builds, signs, and submits the draft to [submitProvider] (Submit step).
 *
 * Thin wrapper over [PlaygroundPresenter.presentSubmitTransaction] — no build, sign, or submit
 * logic of its own; the accepted/local id comparison stays in the presenter (ADR-0017).
 */
internal fun interface SubmitTransactionUseCase {
    suspend operator fun invoke(
        queryProvider: ChainQueryProvider,
        submitProvider: TxSubmitProvider,
    ): SubmitTransactionPresentation

    companion object {
        val Default = SubmitTransactionUseCase { queryProvider, submitProvider ->
            PlaygroundPresenter.presentSubmitTransaction(queryProvider, submitProvider)
        }
    }
}

/**
 * Loads UTxOs for the Provider explorer address from [provider].
 *
 * Thin wrapper over [PlaygroundPresenter.presentProviderUtxos] so [PlaygroundViewModel] can be
 * tested with a fake that completes after cancellation ([kotlinx.coroutines.NonCancellable]).
 */
internal fun interface LoadProviderUtxosUseCase {
    suspend operator fun invoke(
        provider: ChainQueryProvider,
        addressInput: String,
    ): ProviderUtxosPresentation

    companion object {
        val Default = LoadProviderUtxosUseCase { provider, addressInput ->
            PlaygroundPresenter.presentProviderUtxos(provider, addressInput)
        }
    }
}

/**
 * Loads protocol parameters for the Provider explorer from [provider].
 *
 * Thin wrapper over [PlaygroundPresenter.presentProviderParams] so repeated non-cooperative
 * loads can be faked in [PlaygroundViewModel] tests.
 */
internal fun interface LoadProviderParamsUseCase {
    suspend operator fun invoke(provider: ChainQueryProvider): ProviderParamsPresentation

    companion object {
        val Default = LoadProviderParamsUseCase { provider ->
            PlaygroundPresenter.presentProviderParams(provider)
        }
    }
}
