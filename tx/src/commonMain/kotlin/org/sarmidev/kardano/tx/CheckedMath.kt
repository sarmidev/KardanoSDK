package org.sarmidev.kardano.tx

/**
 * Overflow-checked `Long` arithmetic for the fee/change fixed-point loop (ADR-0014 §6-7).
 *
 * `kotlin.math` has no multiplatform-common overflow-checked operators (the JVM-only
 * `java.lang.Math.addExact`/`multiplyExact` are not available from `commonMain`), so this
 * reimplements the same well-known overflow checks. Each function returns the exact result,
 * or `null` if the true mathematical result does not fit in a signed `Long` — callers map
 * `null` to [TxBuildError.FeeCalculationOverflow]. Never truncates or wraps silently.
 */

/** Returns `a + b`, or `null` if the sum overflows a signed `Long`. */
internal fun addExact(a: Long, b: Long): Long? {
    val result = a + b
    // Overflow iff the operands have the same sign and the result's sign differs from theirs.
    return if (((a xor result) and (b xor result)) < 0L) null else result
}

/** Returns `a - b`, or `null` if the difference overflows a signed `Long`. */
internal fun subtractExact(a: Long, b: Long): Long? {
    val result = a - b
    // Overflow iff the operands have different signs and the result's sign differs from a's.
    return if (((a xor b) and (a xor result)) < 0L) null else result
}

/** Returns `a * b`, or `null` if the product overflows a signed `Long`. */
internal fun multiplyExact(a: Long, b: Long): Long? {
    if (a == 0L || b == 0L) return 0L
    // Long.MIN_VALUE * -1 wraps back to Long.MIN_VALUE, which would otherwise defeat the
    // division check below for either operand order; both orderings are excluded explicitly.
    if ((a == -1L && b == Long.MIN_VALUE) || (b == -1L && a == Long.MIN_VALUE)) return null
    val result = a * b
    return if (result / a == b) result else null
}
