package org.sarmidev.kardano.address

import org.sarmidev.kardano.KardanoResult

/**
 * Whether an [AddressCredential] hashes a verification key or a script.
 *
 * The distinction comes from the CIP-19 header type bits: even header types use a key hash
 * and odd header types use a script hash. This is structural classification only; it does
 * not prove the hash corresponds to a real key or script.
 *
 * @see <a href="https://cips.cardano.org/cip/CIP-19">CIP-19</a>
 */
public enum class CredentialKind {

    /** The credential is a `blake2b-224` hash of a verification key. */
    KEY,

    /** The credential is a `blake2b-224` hash of a script. */
    SCRIPT,
}

/**
 * A structural Cardano address credential: a [kind] plus its exactly [HASH_SIZE]-byte hash.
 *
 * A credential is the 28-byte payload of a Shelley address part, classified as a key hash
 * or a script hash by [kind]. This is a structural byte container only: it does not verify
 * that the bytes are a correct `blake2b-224` digest, that any corresponding key or script
 * exists, or that funds at an address using it are owned or spendable.
 *
 * The constructor is private; instances are created internally by [Address.parse] through
 * an internal length-validated factory, so a credential can never hold a hash of the wrong
 * length. The wrapped bytes are copied on construction and on every read, so the internal
 * array is never shared or mutable.
 *
 * @property kind whether the hash is a key hash or a script hash.
 * @see <a href="https://cips.cardano.org/cip/CIP-19">CIP-19</a>
 */
public class AddressCredential private constructor(
    public val kind: CredentialKind,
    hash: ByteArray,
) {

    private val hash: ByteArray = hash.copyOf()

    /**
     * Returns a copy of the wrapped credential hash.
     *
     * @return a fresh [ByteArray] of length [HASH_SIZE]; mutating it does not affect this
     *   [AddressCredential].
     */
    public fun hashBytes(): ByteArray = hash.copyOf()

    /** Value equality based on [kind] and the hash content. */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is AddressCredential) return false
        return kind == other.kind && hash.contentEquals(other.hash)
    }

    /** Hash code derived from [kind] and the hash content. */
    override fun hashCode(): Int = 31 * kind.hashCode() + hash.contentHashCode()

    /** Structural description that does not render the wrapped hash. */
    override fun toString(): String = "AddressCredential(kind=$kind, hashSize=${hash.size})"

    internal companion object {

        /** The exact number of bytes a credential hash holds (a `blake2b-224` digest). */
        internal const val HASH_SIZE: Int = 28

        /**
         * Creates an [AddressCredential] from [hash], validating its length.
         *
         * This is the only construction path for [AddressCredential]; it is internal and
         * used by [Address.parse] after a credential slice has been taken from a validated
         * payload. It returns a [KardanoResult] so an invalid length cannot produce a
         * credential.
         *
         * @param kind whether [hash] is a key hash or a script hash.
         * @param hash the candidate credential bytes; must be exactly [HASH_SIZE] bytes. The
         *   array is copied defensively.
         * @return [KardanoResult.Ok] with the credential when [hash] has length [HASH_SIZE],
         *   or [KardanoResult.Err] with [AddressError.InvalidCredentialLength] otherwise.
         */
        internal fun of(
            kind: CredentialKind,
            hash: ByteArray,
        ): KardanoResult<AddressCredential, AddressError> =
            if (hash.size != HASH_SIZE) {
                KardanoResult.Err(AddressError.InvalidCredentialLength(HASH_SIZE, hash.size))
            } else {
                KardanoResult.Ok(AddressCredential(kind, hash))
            }
    }
}
