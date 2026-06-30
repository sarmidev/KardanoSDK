package org.sarmidev.kardano.address

import org.sarmidev.kardano.KardanoResult

/**
 * Which of an [AddressPointer]'s three coordinates a pointer-decoding error refers to.
 *
 * The coordinates are decoded in this order from the pointer payload: [SLOT], then
 * [TRANSACTION_INDEX], then [CERTIFICATE_INDEX]. Used by [AddressError] variants to say
 * which field was malformed, over-long, or out of range.
 *
 * @see <a href="https://cips.cardano.org/cip/CIP-19">CIP-19</a>
 */
public enum class PointerField {

    /** The absolute slot number coordinate. */
    SLOT,

    /** The transaction index (within the slot) coordinate. */
    TRANSACTION_INDEX,

    /** The (delegation) certificate index (within the transaction) coordinate. */
    CERTIFICATE_INDEX,
}

/**
 * A structural Cardano chain pointer: the three coordinates of a pointer address (CIP-19
 * header types 4 and 5).
 *
 * A chain pointer refers to a point of the chain containing a stake key registration
 * certificate, identified by an absolute [slot] number, a [transactionIndex] within that
 * slot, and a [certificateIndex] within that transaction. In a pointer address these are
 * serialized after the payment credential as three variable-length unsigned integers (see
 * [Address.parse]).
 *
 * Each coordinate is a non-negative [Long] in the range `0..Long.MAX_VALUE`. This is a
 * structural container only: it does not prove the pointer refers to a certificate that
 * exists on-chain, nor that any address using it is owned, controllable, or spendable. The
 * coordinates are public on-chain references, not secrets, so [toString] renders them.
 *
 * The constructor is private; instances are created internally by [Address.parse] through
 * an internal range-validated factory, so a pointer can never hold a negative coordinate.
 *
 * @property slot the absolute slot number.
 * @property transactionIndex the transaction index within the slot.
 * @property certificateIndex the certificate index within the transaction.
 * @see <a href="https://cips.cardano.org/cip/CIP-19">CIP-19</a>
 */
public class AddressPointer private constructor(
    public val slot: Long,
    public val transactionIndex: Long,
    public val certificateIndex: Long,
) {

    /** Value equality based on the three coordinates. */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is AddressPointer) return false
        return slot == other.slot &&
            transactionIndex == other.transactionIndex &&
            certificateIndex == other.certificateIndex
    }

    /** Hash code derived from the three coordinates. */
    override fun hashCode(): Int {
        var result = slot.hashCode()
        result = 31 * result + transactionIndex.hashCode()
        result = 31 * result + certificateIndex.hashCode()
        return result
    }

    /** Structural description rendering the three (public) coordinates. */
    override fun toString(): String =
        "AddressPointer(slot=$slot, transactionIndex=$transactionIndex, " +
            "certificateIndex=$certificateIndex)"

    internal companion object {

        /**
         * Creates an [AddressPointer] from its three coordinates, validating non-negativity.
         *
         * This is the only construction path for [AddressPointer]; it is internal and used by
         * [Address.parse] after the three variable-length fields have been decoded. The
         * decoder only produces non-negative values, so this factory makes the invariant
         * explicit at the boundary; a negative coordinate yields a typed error rather than a
         * pointer.
         *
         * @param slot the absolute slot number; must be `0..Long.MAX_VALUE`.
         * @param transactionIndex the transaction index; must be `0..Long.MAX_VALUE`.
         * @param certificateIndex the certificate index; must be `0..Long.MAX_VALUE`.
         * @return [KardanoResult.Ok] with the pointer when all coordinates are non-negative,
         *   or [KardanoResult.Err] with [AddressError.PointerValueOutOfRange] naming the first
         *   offending field otherwise.
         */
        internal fun of(
            slot: Long,
            transactionIndex: Long,
            certificateIndex: Long,
        ): KardanoResult<AddressPointer, AddressError> {
            if (slot < 0) {
                return KardanoResult.Err(AddressError.PointerValueOutOfRange(PointerField.SLOT))
            }
            if (transactionIndex < 0) {
                return KardanoResult.Err(
                    AddressError.PointerValueOutOfRange(PointerField.TRANSACTION_INDEX),
                )
            }
            if (certificateIndex < 0) {
                return KardanoResult.Err(
                    AddressError.PointerValueOutOfRange(PointerField.CERTIFICATE_INDEX),
                )
            }
            return KardanoResult.Ok(
                AddressPointer(slot, transactionIndex, certificateIndex),
            )
        }
    }
}
