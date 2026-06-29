package org.sarmidev.kardano

/**
 * A typed success-or-failure result for failable Kardano SDK APIs.
 *
 * Public APIs that can fail return a [KardanoResult] instead of throwing, because
 * exceptions thrown across the Swift/ObjC boundary crash iOS consumers. A value is either
 * [Ok] with a result of type [T] or [Err] with a typed error of type [E].
 *
 * @param T the success value type.
 * @param E the typed error type, usually a sealed error.
 */
public sealed interface KardanoResult<out T, out E> {

    /**
     * A successful [KardanoResult] carrying a [value].
     *
     * @param T the success value type.
     * @property value the success value.
     */
    public data class Ok<out T>(public val value: T) : KardanoResult<T, Nothing>

    /**
     * A failed [KardanoResult] carrying a typed [error].
     *
     * @param E the typed error type.
     * @property error the failure value describing why the operation failed.
     */
    public data class Err<out E>(public val error: E) : KardanoResult<Nothing, E>
}

/**
 * Returns the success value if this is a [KardanoResult.Ok], or `null` if it is a
 * [KardanoResult.Err].
 *
 * @return the [KardanoResult.Ok.value], or `null` on failure. Never throws.
 */
public fun <T, E> KardanoResult<T, E>.getOrNull(): T? = when (this) {
    is KardanoResult.Ok -> value
    is KardanoResult.Err -> null
}

/**
 * Returns the typed error if this is a [KardanoResult.Err], or `null` if it is a
 * [KardanoResult.Ok].
 *
 * @return the [KardanoResult.Err.error], or `null` on success. Never throws.
 */
public fun <T, E> KardanoResult<T, E>.errorOrNull(): E? = when (this) {
    is KardanoResult.Ok -> null
    is KardanoResult.Err -> error
}
