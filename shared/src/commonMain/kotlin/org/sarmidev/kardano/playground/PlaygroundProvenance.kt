package org.sarmidev.kardano.playground

/**
 * Stamps [PlaygroundProviderMode] and the captured [flowGeneration] onto a provider-backed
 * presentation. Loading/Empty variants are left unchanged — they are in-flight or unused, not
 * results. Sample-app only; does not change SDK protocol behavior.
 */
internal fun WalletBalancePresentation.withProvenance(
    mode: PlaygroundProviderMode,
    generation: Long,
): WalletBalancePresentation = when (this) {
    is WalletBalancePresentation.Success -> copy(providerMode = mode, flowGeneration = generation)
    is WalletBalancePresentation.Failure -> copy(providerMode = mode, flowGeneration = generation)
    WalletBalancePresentation.Empty, WalletBalancePresentation.Loading -> this
}

internal fun TransactionDraftPresentation.withProvenance(
    mode: PlaygroundProviderMode,
    generation: Long,
): TransactionDraftPresentation = when (this) {
    is TransactionDraftPresentation.Success -> copy(providerMode = mode, flowGeneration = generation)
    is TransactionDraftPresentation.Failure -> copy(providerMode = mode, flowGeneration = generation)
    TransactionDraftPresentation.Empty, TransactionDraftPresentation.Loading -> this
}

internal fun SignedTransactionPresentation.withProvenance(
    mode: PlaygroundProviderMode,
    generation: Long,
): SignedTransactionPresentation = when (this) {
    is SignedTransactionPresentation.Success -> copy(providerMode = mode, flowGeneration = generation)
    is SignedTransactionPresentation.Failure -> copy(providerMode = mode, flowGeneration = generation)
    SignedTransactionPresentation.Empty, SignedTransactionPresentation.Loading -> this
}

internal fun SubmitTransactionPresentation.withProvenance(
    mode: PlaygroundProviderMode,
    generation: Long,
): SubmitTransactionPresentation = when (this) {
    is SubmitTransactionPresentation.Success -> copy(providerMode = mode, flowGeneration = generation)
    is SubmitTransactionPresentation.Failure -> copy(providerMode = mode, flowGeneration = generation)
    SubmitTransactionPresentation.Empty, SubmitTransactionPresentation.Loading -> this
}

internal fun ProviderUtxosPresentation.withProvenance(
    mode: PlaygroundProviderMode,
    generation: Long,
): ProviderUtxosPresentation = when (this) {
    is ProviderUtxosPresentation.Success -> copy(providerMode = mode, flowGeneration = generation)
    is ProviderUtxosPresentation.NoUtxos -> copy(providerMode = mode, flowGeneration = generation)
    is ProviderUtxosPresentation.Failure -> copy(providerMode = mode, flowGeneration = generation)
    ProviderUtxosPresentation.Empty, ProviderUtxosPresentation.Loading -> this
}

internal fun ProviderParamsPresentation.withProvenance(
    mode: PlaygroundProviderMode,
    generation: Long,
): ProviderParamsPresentation = when (this) {
    is ProviderParamsPresentation.Success -> copy(providerMode = mode, flowGeneration = generation)
    is ProviderParamsPresentation.Failure -> copy(providerMode = mode, flowGeneration = generation)
    ProviderParamsPresentation.Empty, ProviderParamsPresentation.Loading -> this
}
