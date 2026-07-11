package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult

/**
 * The three CIP-1852 role components of a derivation path, at the level directly below the
 * account.
 *
 * @property value the derivation index for this role (a soft index, never prime).
 */
public enum class Cip1852Role(public val value: Int) {

    /** External (receiving) chain, role `0`. */
    EXTERNAL(0),

    /** Internal (change) chain, role `1`. */
    INTERNAL(1),

    /** Staking chain, role `2`. */
    STAKING(2),
}

/**
 * A validated CIP-1852 derivation path `m/1852'/1815'/account'/role/index`.
 *
 * This is an SDK-owned value type: it validates and holds path components, and performs no
 * cryptographic operation. `account` is always prime-derived — this repository's terminology
 * for a BIP-32 index at or above [PRIME_INDEX_OFFSET] (ADR-0009 §Terminology); `role` and
 * `index` are always soft-derived. All three components are public path metadata, not key
 * material, so they are not treated as secret and are rendered in [toString].
 *
 * Instances are created exclusively through [of], which validates `account` and `index` before
 * construction.
 *
 * @property account the account component (soft value; prime derivation is applied internally).
 * @property role the role component.
 * @property index the index component within [role].
 * @see <a href="https://github.com/cardano-foundation/CIPs/tree/master/CIP-1852">CIP-1852</a>
 */
public class Cip1852Path private constructor(
    public val account: Int,
    public val role: Cip1852Role,
    public val index: Int,
) {

    /**
     * The ordered, full CIP-1852 derivation indices for this path, as the uint32-compatible
     * `Long` form the derivation seam narrows to the backend's index type at the point of use:
     * `[1852' , 1815' , account' , role, index]`, where `'` denotes a prime index (this
     * component's value plus [PRIME_INDEX_OFFSET]).
     */
    internal fun fullDerivationIndices(): List<Long> = listOf(
        PURPOSE + PRIME_INDEX_OFFSET,
        COIN_TYPE + PRIME_INDEX_OFFSET,
        account.toLong() + PRIME_INDEX_OFFSET,
        role.value.toLong(),
        index.toLong(),
    )

    /** The path string `m/1852'/1815'/<account>'/<role>/<index>`. Public metadata, no key bytes. */
    override fun toString(): String = "m/$PURPOSE'/$COIN_TYPE'/$account'/${role.value}/$index"

    public companion object {

        /** CIP-1852's fixed purpose component. */
        public const val PURPOSE: Long = 1852L

        /** CIP-1852's fixed coin-type component for Cardano (registered in SLIP-44). */
        public const val COIN_TYPE: Long = 1815L

        /**
         * The offset added to a soft index to make it a prime index: BIP-32's `2^31` (see
         * ADR-0009 §Terminology for this repository's naming choice).
         */
        public const val PRIME_INDEX_OFFSET: Long = 0x8000_0000L

        /** The largest value a soft (non-prime) `account` or `index` may take: `2^31 - 1`. */
        public const val SOFT_INDEX_MAX: Long = 0x7FFF_FFFFL

        /**
         * Validates and creates a [Cip1852Path].
         *
         * `account` and `index` are accepted as `Long` specifically so that out-of-range values
         * above [Int.MAX_VALUE] are representable and rejectable, rather than silently
         * overflowing or wrapping a signed `Int`. Both are stored internally as `Int` only after
         * this range check confirms they fit `0..`[SOFT_INDEX_MAX].
         *
         * @param account the account component; must be in `0..`[SOFT_INDEX_MAX].
         * @param role the role component.
         * @param index the index component within [role]; must be in `0..`[SOFT_INDEX_MAX].
         * @return [KardanoResult.Ok] with the validated [Cip1852Path], or [KardanoResult.Err]
         *   with [KeyDerivationError.IndexOutOfRange] naming the first out-of-range value found
         *   (account checked before index). Never throws.
         */
        public fun of(
            account: Long,
            role: Cip1852Role,
            index: Long,
        ): KardanoResult<Cip1852Path, KeyDerivationError> {
            if (account < 0 || account > SOFT_INDEX_MAX) {
                return KardanoResult.Err(KeyDerivationError.IndexOutOfRange(account))
            }
            if (index < 0 || index > SOFT_INDEX_MAX) {
                return KardanoResult.Err(KeyDerivationError.IndexOutOfRange(index))
            }
            return KardanoResult.Ok(Cip1852Path(account.toInt(), role, index.toInt()))
        }
    }
}
