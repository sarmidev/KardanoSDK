package org.sarmidev.kardano

/**
 * The Cardano Bech32 human-readable parts (HRPs) that [CardanoBech32] accepts.
 *
 * This is the Phase 0 HRP allowlist mandated by
 * [ADR-0001](../../../../../../docs/DECISIONS/0001-cbor-and-parser-policy.md): the
 * Cardano-facing Bech32 wrappers restrict encoding/decoding to exactly these prefixes and
 * reject every other HRP. The enum carries the on-the-wire lowercase [value] only.
 *
 * This type conveys no address semantics. The presence of a Cardano HRP does not imply
 * that an encoded value parses as a CIP-19 address, refers to a real on-chain entity, or
 * is owned or spendable; it only names which prefixes the wrapper allows.
 *
 * @property value the lowercase HRP string as it appears in the encoded form.
 */
public enum class CardanoHrp(public val value: String) {

    /** The mainnet payment-address prefix, `addr`. */
    ADDR("addr"),

    /** The testnet payment-address prefix, `addr_test`. */
    ADDR_TEST("addr_test"),

    /** The mainnet stake-address prefix, `stake`. */
    STAKE("stake"),

    /** The testnet stake-address prefix, `stake_test`. */
    STAKE_TEST("stake_test");

    internal companion object {

        /**
         * Resolves a [CardanoHrp] from its lowercase [value], or `null` if [hrp] is not on
         * the allowlist.
         *
         * Matching is exact and case-sensitive against the lowercase [value]; the Bech32
         * engine already lower-cases the HRP and rejects mixed case before this is called.
         */
        internal fun fromValue(hrp: String): CardanoHrp? =
            entries.firstOrNull { it.value == hrp }
    }
}
