package org.sarmidev.kardano.crypto.signing

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.derivation.ExtendedPrivateKey

/**
 * A minimal, backend-neutral interface for signing a Cardano **transaction body hash** with an
 * extended Ed25519-BIP32 private key (ADR-0015 §3).
 *
 * [sign] signs exactly one thing: the 32-byte Blake2b-256 hash of a `transaction_body`
 * (`bodyHash = Blake2b-256(TransactionDraft.bodyCbor())`, which is also the Cardano transaction
 * id) — never the raw body bytes, and never an arbitrary-length message. This is the message
 * shape a Cardano vkey witness signs; signing the raw body bytes would produce an invalid
 * witness. This interface performs no wallet operation of its own (no derivation, no address
 * construction, no transaction assembly) — those remain the responsibility of
 * [org.sarmidev.kardano.crypto.derivation.KeyDerivation], `:tx`, and `:wallet`, respectively.
 *
 * This interface names no cryptographic library: the concrete implementation is a swappable
 * adapter behind it (mirroring the existing [org.sarmidev.kardano.crypto.hashing.Hashing] /
 * [org.sarmidev.kardano.crypto.derivation.KeyDerivation] seam pattern), backed by the adopted
 * `:crypto-signing-backend` module (ADR-0016 §9i), which wraps the reference `ed25519-bip32`
 * Rust crate's `XPrv::sign` — no handwritten signing algorithm (ADR-0004 §3.1).
 *
 * **This layer signs bytes and cannot authorize transaction scope** (ADR-0019 §4). It does
 * not inspect a `TransactionDraft`, a [org.sarmidev.kardano.primitives.Network], or a fixture
 * identity. Phase 1 transaction signing goes through
 * `ReadOnlyWallet.signTestnetFixtureTransaction`, which performs those checks before calling
 * here. The [ExperimentalKardanoRawSigning] opt-in marks this surface as a primitive, not
 * ordinary integration API. That opt-in is Kotlin-compiler-only; it does not appear as a
 * Swift compile-time gate (ADR-0019).
 *
 * Operations return [KardanoResult] and never throw, which keeps the API compatible with
 * Swift/ObjC interop (a thrown exception would crash iOS consumers).
 *
 * @see <a href="https://github.com/cardano-foundation/CIPs/tree/master/CIP-1852">CIP-1852</a>
 */
@ExperimentalKardanoRawSigning
public interface Signing {

    /**
     * Signs the 32-byte Cardano transaction body hash [bodyHash] with [key], returning the raw
     * 64-byte Ed25519 signature.
     *
     * [bodyHash] must be exactly [BODY_HASH_BYTES] bytes — the Blake2b-256 digest of
     * [org.sarmidev.kardano.tx.TransactionDraft.bodyCbor] (computed by the caller through
     * [org.sarmidev.kardano.crypto.hashing.Hashing.blake2b256]), which is also the transaction
     * id. This function does not hash, build, or validate a transaction itself; it only signs
     * the 32-byte hash it is given.
     *
     * [key]'s full 96-byte extended private-key material is read once for this call and cleared
     * immediately afterward; this function never retains it and never exposes it.
     *
     * @param bodyHash the 32-byte transaction body hash to sign. Not modified.
     * @param key the extended private key to sign with. Not modified or retained.
     * @return [KardanoResult.Ok] with the raw 64-byte signature, or [KardanoResult.Err] with a
     *   [SigningError] describing the failure. Never throws.
     */
    @ExperimentalKardanoRawSigning
    public fun sign(bodyHash: ByteArray, key: ExtendedPrivateKey): KardanoResult<ByteArray, SigningError>

    public companion object {

        /** The exact byte length [sign] requires for [sign]'s `bodyHash` parameter. */
        public const val BODY_HASH_BYTES: Int = 32

        /** The exact byte length of the raw signature [sign] returns on success. */
        public const val SIGNATURE_BYTES: Int = 64

        /**
         * Returns the default [Signing] implementation.
         *
         * The concrete backend is an internal implementation detail and is not part of the
         * public API.
         *
         * @return a ready-to-use [Signing] instance.
         */
        @ExperimentalKardanoRawSigning
        public fun default(): Signing = Ed25519Bip32Signing()
    }
}
