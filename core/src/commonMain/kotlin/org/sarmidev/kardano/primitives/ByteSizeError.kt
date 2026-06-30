package org.sarmidev.kardano.primitives

/**
 * A typed error produced when a byte-backed value type rejects an input `ByteArray`
 * because its length is not allowed.
 *
 * Shared by the fixed-length byte primitives ([TxHash], [PolicyId]) and the
 * bounded-length [AssetName]. It reports lengths only; it does not inspect byte content.
 */
public sealed interface ByteSizeError {

    /**
     * The input did not have the single required length.
     *
     * @property expected the exact number of bytes the type requires.
     * @property actual the number of bytes that were provided.
     */
    public data class Fixed(public val expected: Int, public val actual: Int) : ByteSizeError

    /**
     * The input length fell outside the allowed inclusive `[min, max]` range.
     *
     * @property min the smallest allowed number of bytes (inclusive).
     * @property max the largest allowed number of bytes (inclusive).
     * @property actual the number of bytes that were provided.
     */
    public data class Range(
        public val min: Int,
        public val max: Int,
        public val actual: Int,
    ) : ByteSizeError
}
