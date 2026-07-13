package org.sarmidev.kardano.provider

import org.sarmidev.kardano.primitives.Lovelace

/**
 * The value carried by a transaction output.
 *
 * For the Phase 1 first MVP this is ADA-only: it holds a single [coin] amount in
 * [Lovelace]. Native (multi-asset) values are out of the first MVP (see ADR-0005). This
 * type is intentionally minimal and is designed to leave room for future multiasset support
 * (for example an additional asset map); no binary or source compatibility is promised for
 * that future addition.
 *
 * [hasNativeAssets] (Block 1.11d) is the minimal step toward that future support this MVP
 * takes now: it records *whether* the underlying output carried one or more native-asset
 * amounts, without representing their quantities, policy ids, or asset names. A concrete
 * [ChainQueryProvider] implementation (for example `:provider-blockfrost`) sets it to `true`
 * when it detects native assets in the backend's response, so a caller (for example `:tx`'s
 * `TransactionBuilder`) can honestly reject a UTxO it cannot fully represent instead of
 * silently building a transaction that would drop the caller's tokens.
 *
 * @property coin the ADA component of the value, in lovelace.
 * @property hasNativeAssets `true` if the output this [Value] was read from also carried one
 *   or more native-asset amounts alongside its [coin]; `false` if it was lovelace-only. Default
 *   `false` preserves the ADA-only behavior of every existing call site.
 */
public data class Value(
    public val coin: Lovelace,
    public val hasNativeAssets: Boolean = false,
)
