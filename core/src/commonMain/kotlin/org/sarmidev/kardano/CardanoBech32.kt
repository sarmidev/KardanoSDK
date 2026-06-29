package org.sarmidev.kardano

/**
 * A bounded, UI-free Cardano-facing wrapper over the generic [Bech32] codec.
 *
 * This restricts the generic engine in exactly two ways required by
 * [ADR-0001](../../../../../../docs/DECISIONS/0001-cbor-and-parser-policy.md): it accepts
 * only the Cardano HRP allowlist ([CardanoHrp]: `addr`, `addr_test`, `stake`,
 * `stake_test`) and only the [Bech32Variant.BECH32] variant (Cardano addresses and stake
 * keys use Bech32, not Bech32m). All checksum, character-set, length, and padding work is
 * delegated to [Bech32]; failures are surfaced through [CardanoBech32Error.Underlying].
 *
 * This is **HRP allowlist plus Bech32 checksum/character-set validation only — not CIP-19
 * structural address validation**. It operates on the 5-bit data layer and does not parse
 * address payloads, inspect header bytes, or read the network id. It does not prove that an
 * encoded value is a well-formed address, refers to a real on-chain entity, or is owned or
 * spendable. Neither [encode] nor [decode] throws.
 *
 * @see Bech32
 * @see <a href="https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki">BIP-173</a>
 */
public object CardanoBech32 {

    /**
     * Encodes 5-bit data values under an allowlisted Cardano [hrp] using the Bech32 variant.
     *
     * The variant is fixed to [Bech32Variant.BECH32]; Bech32m is intentionally not offered
     * by this wrapper. Because [hrp] is a [CardanoHrp], an unsupported HRP cannot be
     * supplied here. All other validation (5-bit range, lengths) is performed by [Bech32].
     *
     * @param hrp the allowlisted Cardano human-readable part to emit.
     * @param data5Bit the 5-bit data values (each in `0..31`), excluding the checksum. Not
     *   modified, and not interpreted as an address payload.
     * @return [KardanoResult.Ok] with the canonical lowercase encoding, or
     *   [KardanoResult.Err] with [CardanoBech32Error.Underlying] when [Bech32] rejects the
     *   data values or the resulting length. Never throws.
     */
    public fun encode(
        hrp: CardanoHrp,
        data5Bit: ByteArray,
    ): KardanoResult<String, CardanoBech32Error> =
        when (val result = Bech32.encode(hrp.value, data5Bit, Bech32Variant.BECH32)) {
            is KardanoResult.Ok -> KardanoResult.Ok(result.value)
            is KardanoResult.Err -> KardanoResult.Err(CardanoBech32Error.Underlying(result.error))
        }

    /**
     * Decodes a Bech32 string and accepts it only if its HRP is allowlisted and its variant
     * is [Bech32Variant.BECH32].
     *
     * The input is first decoded by the generic [Bech32] engine (checksum, character set,
     * separator, length, and mixed-case rules). On success, two Cardano-specific checks are
     * applied in this intentional order: the HRP allowlist is checked first, then the
     * variant. As a result, a valid Bech32m string with an unsupported HRP is reported as
     * [CardanoBech32Error.UnsupportedHrp] (the more domain-specific failure), while a valid
     * Bech32m string with an allowlisted HRP is reported as
     * [CardanoBech32Error.UnsupportedVariant].
     *
     * This performs HRP-allowlist plus Bech32 checksum/character-set validation only. It
     * does not parse the address payload, inspect header bytes, or read the network id, and
     * it does not prove that the value is a well-formed, real, owned, or spendable address.
     *
     * @param input the candidate Bech32 string (for example `addr_test1...`).
     * @return [KardanoResult.Ok] with the [Bech32Decoded] data on success, or
     *   [KardanoResult.Err] with a [CardanoBech32Error]: [CardanoBech32Error.Underlying] for
     *   a generic decode failure, [CardanoBech32Error.UnsupportedHrp] for a non-allowlisted
     *   HRP, or [CardanoBech32Error.UnsupportedVariant] for a Bech32m string. Never throws.
     */
    public fun decode(input: String): KardanoResult<Bech32Decoded, CardanoBech32Error> {
        val decoded = when (val result = Bech32.decode(input)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err ->
                return KardanoResult.Err(CardanoBech32Error.Underlying(result.error))
        }
        if (CardanoHrp.fromValue(decoded.hrp) == null) {
            return KardanoResult.Err(CardanoBech32Error.UnsupportedHrp(decoded.hrp))
        }
        if (decoded.variant != Bech32Variant.BECH32) {
            return KardanoResult.Err(CardanoBech32Error.UnsupportedVariant(decoded.variant))
        }
        return KardanoResult.Ok(decoded)
    }
}
