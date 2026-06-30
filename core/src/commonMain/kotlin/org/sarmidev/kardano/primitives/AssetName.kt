package org.sarmidev.kardano

/**
 * A structural container for a Cardano asset name of [MIN_SIZE]..[MAX_SIZE] bytes.
 *
 * An empty asset name (zero bytes) is valid. This is a structural byte container only: it
 * does not verify that the asset exists, its association with any policy, any display text,
 * and it does not parse or render any hex representation (hex is a later Phase 0 concern).
 *
 * The constructor is private; create instances with [of]. The wrapped bytes are copied on
 * construction and on every read, so the internal array is never shared or mutable.
 */
public class AssetName private constructor(bytes: ByteArray) {

    private val bytes: ByteArray = bytes.copyOf()

    /**
     * Returns a copy of the wrapped bytes.
     *
     * @return a fresh [ByteArray] whose length is in [MIN_SIZE]..[MAX_SIZE]; mutating it
     *   does not affect this [AssetName].
     */
    public fun toByteArray(): ByteArray = bytes.copyOf()

    /** Value equality based on byte content. */
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is AssetName) return false
        return bytes.contentEquals(other.bytes)
    }

    /** Hash code derived from byte content. */
    override fun hashCode(): Int = bytes.contentHashCode()

    /** Structural description that does not render the wrapped bytes. */
    override fun toString(): String = "AssetName(size=${bytes.size})"

    public companion object {

        /** The smallest allowed asset-name length, in bytes (inclusive). */
        public const val MIN_SIZE: Int = 0

        /** The largest allowed asset-name length, in bytes (inclusive). */
        public const val MAX_SIZE: Int = 32

        /**
         * Creates an [AssetName] from [bytes].
         *
         * @param bytes the candidate asset-name bytes; the length must be in
         *   [MIN_SIZE]..[MAX_SIZE] inclusive (an empty array is valid). The array is copied
         *   defensively, so later mutations of the caller's array do not affect the
         *   returned [AssetName].
         * @return [KardanoResult.Ok] with the [AssetName] when the length is in range, or
         *   [KardanoResult.Err] with [ByteSizeError.Range] otherwise. Never throws.
         */
        public fun of(bytes: ByteArray): KardanoResult<AssetName, ByteSizeError> =
            if (bytes.size !in MIN_SIZE..MAX_SIZE) {
                KardanoResult.Err(ByteSizeError.Range(MIN_SIZE, MAX_SIZE, bytes.size))
            } else {
                KardanoResult.Ok(AssetName(bytes))
            }
    }
}
