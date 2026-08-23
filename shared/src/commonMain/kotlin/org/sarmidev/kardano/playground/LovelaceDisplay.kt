package org.sarmidev.kardano.playground

import org.sarmidev.kardano.primitives.Lovelace

/**
 * Formats a lovelace amount as a plain-language ADA string (for example `2.5 ADA`) for the
 * guided demo's headline/detail copy (Block 1.12-pre-e).
 *
 * This is a display-only helper: it does not validate, clamp, or otherwise interpret the
 * amount as a protocol value — every amount shown by the demo still comes from a real
 * `:core`/`:tx`/`:wallet` value ([org.sarmidev.kardano.primitives.Lovelace],
 * [org.sarmidev.kardano.wallet.WalletBalance], [org.sarmidev.kardano.tx.TransactionDraft]).
 * 1 ADA is fixed at 1,000,000 lovelace; this performs no other unit conversion. Trailing zero
 * fractional digits are trimmed (`"2.000000"` -> `"2"`, `"2.500000"` -> `"2.5"`) so whole-ADA
 * amounts read cleanly.
 *
 * [ada] takes a [Lovelace] rather than a raw [Long] so a negative amount is rejected at
 * [Lovelace.of] construction time, before it ever reaches this formatter — compile-time
 * enforcement of the non-negative invariant every current call site already relied on, rather
 * than a gap only every current caller happens to avoid (W9-7, 2026-08-22 pre-release audit).
 */
internal object LovelaceDisplay {

    private const val LOVELACE_PER_ADA: Long = 1_000_000L

    /** Formats [lovelace] as `"<amount> ADA"`, for example `ada(Lovelace.of(2_000_000L))` -> `"2 ADA"`. */
    fun ada(lovelace: Lovelace): String {
        val value = lovelace.value
        val whole = value / LOVELACE_PER_ADA
        val remainder = value % LOVELACE_PER_ADA
        if (remainder == 0L) return "$whole ADA"
        val fractionDigits = remainder.toString().padStart(6, '0').trimEnd('0')
        return "$whole.$fractionDigits ADA"
    }
}
