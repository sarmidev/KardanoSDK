package org.sarmidev.kardano.provider

import org.sarmidev.kardano.primitives.Network

/**
 * A typed, provider-neutral error returned by a [ChainQueryProvider].
 *
 * These variants describe failure categories in transport-agnostic terms so the provider
 * API does not leak the shape or vocabulary of any specific backend (for example Blockfrost).
 * A concrete provider implementation is responsible for mapping its own failures (HTTP status
 * codes, JSON errors, transport exceptions) into these variants.
 */
public sealed interface ProviderError {

    /**
     * The request could not be completed at the transport layer (for example a connection
     * failure or timeout).
     *
     * @property message a short, human-readable description of the transport failure.
     */
    public data class Transport(public val message: String) : ProviderError

    /**
     * The remote backend returned a non-success status code.
     *
     * This is deliberately transport-agnostic and is **not** named `HttpStatus`: the read
     * boundary does not assume HTTP. A concrete implementation (for example the Blockfrost
     * provider) maps its HTTP status codes into this [code]. [detail] is optional parsed
     * response text when the backend provides one; it must never include request headers or
     * request configuration.
     *
     * @property code the backend-reported status code.
     * @property detail a short, human-readable description of the failure, when available.
     */
    public data class RemoteStatus(
        public val code: Int,
        public val detail: String? = null,
    ) : ProviderError

    /**
     * A paged query reached this provider's accumulation cap and a one-item probe of the
     * next page showed that at least one further item exists.
     *
     * A full last permitted page is not enough to claim truncation: an empty probe means
     * the result is complete at exactly [cap]. Callers must treat this variant as a
     * failure, not as a complete result.
     *
     * This is not used when a single page contains more entries than were requested —
     * that is an invalid remote payload, not ordinary truncation.
     *
     * @property fetchedCount how many items were accumulated before the cap was reached.
     * @property cap the maximum number of items this provider will accumulate.
     */
    public data class ResultTruncated(
        public val fetchedCount: Int,
        public val cap: Int,
    ) : ProviderError

    /** The requested resource was not found by the backend. */
    public data object NotFound : ProviderError

    /**
     * The backend response could not be decoded into the expected model.
     *
     * @property detail a short description of what failed to decode.
     */
    public data class Deserialization(public val detail: String) : ProviderError

    /** The backend rejected the request because a rate limit was exceeded. */
    public data object RateLimited : ProviderError

    /**
     * The queried resource belongs to a different [Network] than the one this provider is
     * bound to.
     *
     * @property expected the network the provider is bound to.
     * @property actual the network of the queried resource (for example an address's network).
     */
    public data class NetworkMismatch(
        public val expected: Network,
        public val actual: Network,
    ) : ProviderError

    /** An unclassified failure. Implementations should prefer a more specific variant. */
    public data object Unknown : ProviderError
}
