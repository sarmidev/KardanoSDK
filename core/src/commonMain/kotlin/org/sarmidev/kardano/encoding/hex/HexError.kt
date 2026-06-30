package org.sarmidev.kardano.encoding.hex

import org.sarmidev.kardano.KardanoResult

/**
 * A typed error produced when [Hex.decode] rejects a candidate hex string.
 *
 * Decoding never throws on malformed input; it returns one of these variants inside a
 * [KardanoResult.Err]. Malformed input is rejected, not normalized.
 */
public sealed interface HexError {

    /**
     * The input length exceeded the decoder's named limit.
     *
     * The limit is checked before any output buffer is allocated.
     *
     * @property max the maximum number of input characters allowed ([Hex.MAX_INPUT_CHARS]).
     * @property actual the number of input characters that were provided.
     */
    public data class InputTooLong(public val max: Int, public val actual: Int) : HexError

    /**
     * The input had an odd number of characters, so it cannot map to whole bytes.
     *
     * @property length the number of input characters that were provided.
     */
    public data class OddLength(public val length: Int) : HexError

    /**
     * The input contained a character outside the hex alphabet (`0-9`, `a-f`, `A-F`).
     *
     * @property index the zero-based index of the first invalid character.
     * @property char the first invalid character encountered.
     */
    public data class InvalidCharacter(public val index: Int, public val char: Char) : HexError
}
