package org.sarmidev.kardano.provider

/**
 * A typed, provider-neutral error returned by a [TxSubmitProvider].
 *
 * These variants describe failure categories in transport-agnostic terms so the submission
 * API does not leak the shape or vocabulary of any specific backend (for example Blockfrost).
 * A concrete provider implementation is responsible for mapping its own failures (HTTP status
 * codes, JSON errors, transport exceptions) into these variants. This is a distinct type from
 * [ProviderError]: submission failure categories (for example a node rejecting a malformed or
 * conflicting transaction) are not the same shape as read failures, so submission is not
 * forced to reuse or awkwardly extend the read-only error taxonomy.
 */
public sealed interface SubmitError {

    /**
     * This provider does not support transaction submission at all.
     *
     * Reserved for providers that deliberately do not submit (for example an in-memory test
     * double). A provider must never report success to simulate acceptance when it has not
     * actually submitted anything.
     */
    public data object SubmissionNotSupported : SubmitError

    /** [TxSubmitProvider.submit] was called with empty transaction CBOR bytes. */
    public data object EmptyTransaction : SubmitError

    /**
     * The backend parsed [transactionCbor][TxSubmitProvider.submit] but rejected the
     * transaction itself (for example a malformed body, a missing/invalid witness, an
     * already-spent input, or another node-level validation failure).
     *
     * @property code the backend-reported status code for the rejection.
     * @property detail a short, human-readable description of why the backend rejected the
     *   transaction, when the backend provides one.
     */
    public data class Rejected(public val code: Int, public val detail: String) : SubmitError

    /**
     * The request could not be completed at the transport layer (for example a connection
     * failure or timeout).
     *
     * @property message a short, human-readable description of the transport failure.
     */
    public data class Transport(public val message: String) : SubmitError

    /**
     * The remote backend returned a non-success status code that is not more specifically
     * classified by another variant (for example [Rejected] or [RateLimited]).
     *
     * This is deliberately transport-agnostic and is **not** named `HttpStatus`: the
     * submission boundary does not assume HTTP. A concrete implementation (for example the
     * Blockfrost provider) maps its HTTP status codes into this [code].
     *
     * @property code the backend-reported status code.
     * @property detail a short, human-readable description of the failure, when available.
     */
    public data class RemoteStatus(public val code: Int, public val detail: String? = null) :
        SubmitError

    /** The backend rejected the request because a rate limit was exceeded. */
    public data object RateLimited : SubmitError

    /**
     * The backend's response could not be decoded into the expected accepted-transaction-id
     * shape.
     *
     * @property detail a short description of what failed to decode.
     */
    public data class Deserialization(public val detail: String) : SubmitError

    /** An unclassified failure. Implementations should prefer a more specific variant. */
    public data object Unknown : SubmitError
}
