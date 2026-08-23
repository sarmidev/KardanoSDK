package org.sarmidev.kardano.crypto.signing

/**
 * Opt-in marker for `:crypto`'s raw byte-signing primitive ([Signing]).
 *
 * [Signing.sign] signs a 32-byte hash with an [org.sarmidev.kardano.crypto.derivation.ExtendedPrivateKey].
 * It cannot authorize a transaction's network, draft scope, or fixture identity — those
 * checks live in `:wallet` (ADR-0019). This annotation keeps that byte-signing surface from
 * reading as ordinary integration API.
 *
 * **This is a Kotlin-compiler-only mechanism.** `@RequiresOptIn` does not cross the
 * Kotlin/Native → Swift boundary. A Swift caller of the compiled framework sees an ordinary
 * function; the runtime transaction-scope checks in
 * `ReadOnlyWallet.signTestnetFixtureTransaction` still run in shared Kotlin code
 * (ADR-0019).
 *
 * This module does not depend on `:wallet` or `:tx`. Applying this annotation here adds no
 * new module edge.
 *
 * See [ADR-0019](../../../../../../../docs/DECISIONS/0019-transaction-draft-scope-binding.md) §4.
 */
@RequiresOptIn(
    level = RequiresOptIn.Level.ERROR,
    message = "Signing.sign is a raw byte-signing primitive. It cannot authorize transaction " +
        "network, draft scope, or fixture identity (ADR-0019). Prefer " +
        "ReadOnlyWallet.signTestnetFixtureTransaction for Phase 1 transaction signing.",
)
@Retention(AnnotationRetention.BINARY)
@Target(AnnotationTarget.CLASS, AnnotationTarget.FUNCTION)
public annotation class ExperimentalKardanoRawSigning
