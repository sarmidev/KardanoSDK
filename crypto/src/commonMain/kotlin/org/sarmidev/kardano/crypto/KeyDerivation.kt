package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult

/**
 * A minimal, backend-neutral interface for Ed25519-BIP32 (CIP-1852) private-key derivation.
 *
 * This interface names no cryptographic library: the concrete implementation is a swappable
 * adapter behind it, so consumers depend only on this SDK's types. It derives only along the
 * private (prime-and-soft) path from an [IcarusMasterKey] root to a full CIP-1852
 * `m/1852'/1815'/account'/role/index` leaf; it does not sign, generate addresses, or project a
 * private key to its public counterpart (ADR-0009 §4's Block 1.6c gate result: the pinned
 * `dev.allain:bip32-ed25519` backend has no such primitive — public-key derivation is deferred
 * to a follow-up block).
 *
 * Operations return [KardanoResult] and never throw, which keeps the API compatible with
 * Swift/ObjC interop (a thrown exception would crash iOS consumers).
 *
 * @see <a href="https://github.com/cardano-foundation/CIPs/tree/master/CIP-1852">CIP-1852</a>
 */
public interface KeyDerivation {

    /**
     * Derives the [ExtendedPrivateKey] at [path], starting from [master].
     *
     * Applies five successive derivation steps: `1852'`, `1815'`, `account'` (all prime), then
     * `role` and `index` (both soft) — see [Cip1852Path.fullDerivationIndices].
     *
     * @param master the root extended key to derive from (see [IcarusMasterKey.fromMnemonic]).
     * @param path the validated CIP-1852 path to derive (see [Cip1852Path.of]).
     * @return [KardanoResult.Ok] with the derived [ExtendedPrivateKey], or [KardanoResult.Err]
     *   with a [KeyDerivationError] if the backend fails or produces unexpected key material.
     *   Never throws.
     */
    public fun derivePrivate(
        master: IcarusMasterKey,
        path: Cip1852Path,
    ): KardanoResult<ExtendedPrivateKey, KeyDerivationError>

    public companion object {

        /**
         * Returns the default [KeyDerivation] implementation.
         *
         * The concrete backend is an internal implementation detail and is not part of the
         * public API.
         *
         * @return a ready-to-use [KeyDerivation] instance.
         */
        public fun default(): KeyDerivation = Bip32Ed25519KeyDerivation()
    }
}
