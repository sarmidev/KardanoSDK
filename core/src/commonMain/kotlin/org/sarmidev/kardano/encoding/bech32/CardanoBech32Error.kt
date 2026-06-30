package org.sarmidev.kardano.encoding.bech32

import org.sarmidev.kardano.KardanoResult

/**
 * A typed error produced when [CardanoBech32.encode] or [CardanoBech32.decode] rejects its
 * input.
 *
 * The Cardano-facing wrappers never throw; they return one of these variants inside a
 * [KardanoResult.Err]. They add only HRP-allowlist and variant restrictions on top of the
 * generic [Bech32] codec — all checksum, character-set, length, and padding failures are
 * surfaced unchanged through [Underlying]. These errors carry no address semantics.
 *
 * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki">BIP-173</a>
 */
public sealed interface CardanoBech32Error {

    /**
     * The generic [Bech32] codec rejected the input.
     *
     * This wraps the underlying [Bech32Error] verbatim (for example an invalid checksum,
     * an out-of-charset character, or an over-limit length) so callers can inspect the
     * exact engine-level failure.
     *
     * @property error the underlying generic Bech32 error.
     */
    public data class Underlying(public val error: Bech32Error) : CardanoBech32Error

    /**
     * The decoded human-readable part is not on the Cardano HRP allowlist ([CardanoHrp]).
     *
     * The string was a structurally valid Bech32/Bech32m encoding, but its HRP is not one
     * the Cardano-facing wrappers accept in Phase 0.
     *
     * @property hrp the decoded human-readable part that was rejected.
     */
    public data class UnsupportedHrp(public val hrp: String) : CardanoBech32Error

    /**
     * The decoded string used a Bech32 variant the Cardano-facing wrappers do not accept.
     *
     * The wrappers accept [Bech32Variant.BECH32] only; a valid [Bech32Variant.BECH32M]
     * string for an allowlisted HRP is rejected with this error.
     *
     * @property variant the variant that was detected and rejected.
     */
    public data class UnsupportedVariant(public val variant: Bech32Variant) : CardanoBech32Error
}
