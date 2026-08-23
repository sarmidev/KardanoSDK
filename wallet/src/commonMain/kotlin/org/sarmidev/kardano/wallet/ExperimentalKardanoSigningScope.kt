package org.sarmidev.kardano.wallet

/**
 * Opt-in marker for `:wallet`'s current signing-orchestration entry point
 * ([ReadOnlyWallet.signTestnetFixtureTransaction]).
 *
 * Requiring [OptIn] here is an **intent signal** (ADR-0018). Opting in tells the compiler and
 * every IDE showing this declaration that this entry point is scoped to the Phase 1
 * testnet/test-fixture demonstration flow. It does not, by itself, verify the caller.
 *
 * **Runtime checks now exist alongside this signal (ADR-0019).**
 * [ReadOnlyWallet.signTestnetFixtureTransaction] rejects a draft whose bound network is not
 * [org.sarmidev.kardano.primitives.Network.TESTNET], whose declared network disagrees with
 * that bound network, whose [org.sarmidev.kardano.tx.TransactionDraftScope] is not the Phase 1
 * ADA-only marker, or whose input/output shape is not the Phase 1 single-payment flow — all
 * before the mnemonic is parsed. Those checks are independent of this annotation.
 *
 * This annotation still does not:
 *
 * - Restrict `Network.MAINNET` or `BlockfrostNetwork.MAINNET`, which remain ordinary,
 *   unguarded, general-purpose SDK constants used correctly elsewhere (address parsing,
 *   provider configuration).
 * - Carry over as a Swift/iOS compile-time gate. `@RequiresOptIn` is Kotlin-compiler-only;
 *   the runtime [WalletError.SigningScopeViolation] checks do execute for Swift callers
 *   because they run in shared Kotlin code (ADR-0019).
 *
 * Any open-source consumer can delete this annotation — or the runtime checks — from a
 * patched copy of the source. This is an honest signal plus a working rejection for a
 * good-faith integrator of the compiled artifact, not a claim about unmodified source.
 *
 * See [ADR-0018](../../../../../../docs/DECISIONS/0018-signing-scope-enforcement-and-publication.md)
 * and [ADR-0019](../../../../../../docs/DECISIONS/0019-transaction-draft-scope-binding.md).
 */
@RequiresOptIn(
    level = RequiresOptIn.Level.ERROR,
    message = "This signing entry point is scoped to the Phase 1 testnet/test-fixture " +
        "demonstration flow (ADR-0015 §2a / ADR-0019), not general-purpose wallet signing. " +
        "Opting in is a Kotlin-compiler intent signal (ADR-0018); runtime draft " +
        "network/scope checks are separate (ADR-0019).",
)
@Retention(AnnotationRetention.BINARY)
@Target(AnnotationTarget.FUNCTION)
public annotation class ExperimentalKardanoSigningScope
