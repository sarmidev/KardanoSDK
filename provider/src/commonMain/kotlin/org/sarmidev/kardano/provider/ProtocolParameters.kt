package org.sarmidev.kardano.provider

/**
 * The minimal set of Cardano protocol parameters a [ChainQueryProvider] exposes for future
 * fee and transaction-build logic.
 *
 * This is a provider-neutral read model: field names describe the protocol concept, not any
 * specific provider's JSON response shape. The set is intentionally small and covers only
 * what the Phase 1 ADA-only fee/build path is expected to need; it may grow when the
 * transaction builder lands (Block 1.9). All amounts are in lovelace unless noted.
 *
 * @property minFeeCoefficient the per-byte fee coefficient (the protocol's `minFeeA`).
 * @property minFeeConstant the constant fee term (the protocol's `minFeeB`), in lovelace.
 * @property keyDeposit the deposit required to register a stake key, in lovelace.
 * @property poolDeposit the deposit required to register a stake pool, in lovelace.
 * @property maxTxSize the maximum transaction size, in bytes.
 * @property coinsPerUtxoByte the minimum-UTxO cost per byte, in lovelace.
 */
public data class ProtocolParameters(
    public val minFeeCoefficient: Long,
    public val minFeeConstant: Long,
    public val keyDeposit: Long,
    public val poolDeposit: Long,
    public val maxTxSize: Long,
    public val coinsPerUtxoByte: Long,
)
