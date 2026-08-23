package org.sarmidev.kardano.wallet

/**
 * Opt-in marker for `:wallet`'s current signing-orchestration entry point
 * ([ReadOnlyWallet.signTestnetFixtureTransaction]).
 *
 * Requiring [OptIn] here is an **intent signal, not a runtime enforcement mechanism** (ADR-0018).
 * Opting in tells the compiler and every IDE showing this declaration "I have read and accept
 * that this entry point is scoped to the Phase 1 testnet/test-fixture demonstration flow" — it
 * does not, and cannot, verify that the caller actually is that flow. Nothing about this
 * annotation:
 *
 * - Checks the `network` argument passed to [ReadOnlyWallet.signTestnetFixtureTransaction]
 *   against anything.
 * - Checks that the supplied mnemonic is the Phase 1 fixture rather than an arbitrary,
 *   real one.
 * - Binds a [org.sarmidev.kardano.tx.TransactionDraft] to the network it was built for
 *   (`TransactionDraft` carries no `network` field at all — see ADR-0018 §Context). A caller
 *   that opts in can still sign a mainnet-built draft with a real mnemonic; nothing here stops
 *   that.
 * - Restricts `Network.MAINNET` or `BlockfrostNetwork.MAINNET`, which remain ordinary, unguarded,
 *   general-purpose SDK constants used correctly elsewhere (address parsing, provider
 *   configuration) — this annotation is not applied to them (ADR-0018 explicitly rejected doing
 *   so as part of this task's scope).
 *
 * **This is a Kotlin-compiler-only mechanism.** `@RequiresOptIn` enforcement does not cross the
 * Kotlin/Native → Swift boundary: when `:wallet` is consumed through the compiled `:shared`/
 * framework boundary from Swift, a Swift caller sees an ordinary function with no enforced
 * opt-in — the compiler gate below benefits Kotlin/JVM/Android consumers only. For iOS/Swift
 * consumers, the entry point's scope-explicit name and its own KDoc are the only effective
 * signal.
 *
 * Any open-source consumer can also simply delete this annotation from a patched copy of the
 * source; this does not, and is not intended to, prevent a determined bad actor from misusing
 * the code. Its purpose is to give a good-faith integrator a hard-to-miss signal, not to enforce
 * anything against a hostile one.
 *
 * See [ADR-0018](../../../../../../docs/DECISIONS/0018-signing-scope-enforcement-and-publication.md)
 * for the full decision record and comparison of alternatives.
 */
@RequiresOptIn(
    level = RequiresOptIn.Level.ERROR,
    message = "This signing entry point is scoped to the Phase 1 testnet/test-fixture " +
        "demonstration flow (ADR-0015 §2a), not general-purpose wallet signing. Opting in is an " +
        "intent signal, not a runtime enforcement check (ADR-0018) — see this annotation's own " +
        "KDoc before opting in.",
)
@Retention(AnnotationRetention.BINARY)
@Target(AnnotationTarget.FUNCTION)
public annotation class ExperimentalKardanoSigningScope
