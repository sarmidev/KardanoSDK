package org.sarmidev.kardano.crypto.derivation

import org.sarmidev.kardano.KardanoResult

/**
 * A minimal, backend-neutral interface for Ed25519-BIP32 (CIP-1852) private-key derivation.
 *
 * This interface names no cryptographic library: the concrete implementation is a swappable
 * adapter behind it, so consumers depend only on this SDK's types. It derives only along the
 * private (prime-and-soft) path from an [IcarusMasterKey] root to a full CIP-1852
 * `m/1852'/1815'/account'/role/index` leaf, and projects a derived private key to its public
 * counterpart; it does not sign or generate addresses.
 *
 * Operations return [KardanoResult] and never throw, which keeps the API compatible with
 * Swift/ObjC interop (a thrown exception would crash iOS consumers).
 *
 * 1.6c-follow-up-2 gate result (ADR-0010): [publicKey] is verified on JVM, iOS, and Android
 * (real-runtime execution on API 24, 35, and 36). [derivePrivate] is likewise verified on every
 * target including Android (1.6c-follow-up). [KeyDerivationError.PublicKeyProjectionUnavailable]
 * remains a declared error for platforms without a projection backend, but no current target
 * returns it.
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

    /**
     * Projects [key] to its [ExtendedPublicKey] counterpart.
     *
     * Computes `A = [kL] * B` (Ed25519 base-point scalar multiplication, noclamp, on the
     * extended private key's left 32-byte scalar) and pairs it with the unchanged chain code.
     *
     * @param key the extended private key to project (see [derivePrivate]).
     * @return [KardanoResult.Ok] with the projected [ExtendedPublicKey], or [KardanoResult.Err]
     *   with [KeyDerivationError.PublicKeyProjectionUnavailable] if projection is not available
     *   on this platform, or another [KeyDerivationError] if the backend fails. Never throws.
     */
    public fun publicKey(key: ExtendedPrivateKey): KardanoResult<ExtendedPublicKey, KeyDerivationError>

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
