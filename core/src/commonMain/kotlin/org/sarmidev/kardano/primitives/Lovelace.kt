package org.sarmidev.kardano.primitives

import org.sarmidev.kardano.KardanoResult
import kotlin.jvm.JvmInline

/**
 * A non-negative amount of lovelace, the smallest indivisible unit of ADA (1 ADA =
 * 1,000,000 lovelace).
 *
 * The allowed range is `0..Long.MAX_VALUE`. Negative amounts are rejected by [of], and
 * values are never silently truncated. This type does not enforce the Cardano maximum ADA
 * supply: enforcing a supply cap is a protocol-level concern and is deferred, so a valid
 * [Lovelace] does not claim the amount is reachable on any network.
 *
 * Instances are created through [of]; the constructor is private to keep the non-negative
 * invariant in one place.
 *
 * @property value the amount in lovelace, always in `0..Long.MAX_VALUE`.
 */
@JvmInline
public value class Lovelace private constructor(public val value: Long) {

    public companion object {

        /** A [Lovelace] amount of zero, the lower bound of the allowed range. */
        public val ZERO: Lovelace = Lovelace(0L)

        /**
         * Creates a [Lovelace] from a raw lovelace [value].
         *
         * @param value the amount in lovelace; must be in `0..Long.MAX_VALUE`.
         * @return [KardanoResult.Ok] with the [Lovelace] for a non-negative [value], or
         *   [KardanoResult.Err] with [LovelaceError.Negative] if [value] is negative.
         *   Never throws and never truncates.
         */
        public fun of(value: Long): KardanoResult<Lovelace, LovelaceError> =
            if (value < 0L) {
                KardanoResult.Err(LovelaceError.Negative(value))
            } else {
                KardanoResult.Ok(Lovelace(value))
            }
    }
}

/**
 * A typed error produced when creating a [Lovelace] amount.
 */
public sealed interface LovelaceError {

    /**
     * The provided [value] was negative, which is outside the allowed `0..Long.MAX_VALUE`
     * range.
     *
     * @property value the rejected negative amount.
     */
    public data class Negative(public val value: Long) : LovelaceError
}
