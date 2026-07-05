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
 * @property coin the ADA component of the value, in lovelace.
 */
public data class Value(public val coin: Lovelace)
