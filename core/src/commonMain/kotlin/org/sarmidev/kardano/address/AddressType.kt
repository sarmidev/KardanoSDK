package org.sarmidev.kardano.address

/**
 * The subset of CIP-19 Shelley address types that [Address.parse] can produce.
 *
 * This enum is the **settled Block 0.7 scope**: the Shelley CIP-19 Bech32 address families —
 * the single-credential, fixed-length types ([ENTERPRISE], [REWARD]), the two-credential
 * [BASE] type, and the [POINTER] type (a payment credential plus a variable-length chain
 * pointer). Legacy Byron (bootstrap) addresses (header type 8) are **not** modeled; they are
 * deferred beyond Block 0.7 to a future block (Base58-encoded and Byron-specific). Header
 * types that are not in this scope are rejected by [Address.parse] with
 * [AddressError.UnsupportedAddressType], which carries the raw header type nibble, rather
 * than being represented by a placeholder constant here.
 *
 * This type conveys structural classification only. It does not imply that an address
 * exists on-chain, is owned, is controllable, or is spendable.
 *
 * @see <a href="https://cips.cardano.org/cip/CIP-19">CIP-19</a>
 */
public enum class AddressType {

    /**
     * A base address (CIP-19 header types 0-3): a payment credential plus a
     * delegation/stake credential. Each part is a key hash or a script hash, selected by
     * the header type bits — type 0: payment key + stake key; type 1: payment script +
     * stake key; type 2: payment key + stake script; type 3: payment script + stake
     * script. An [Address] of this type exposes both [Address.paymentCredential] and
     * [Address.stakeCredential] as non-null.
     */
    BASE,

    /**
     * An enterprise address (CIP-19 header types 6 and 7): a payment credential with no
     * delegation part. The payment credential is a key hash (type 6) or a script hash
     * (type 7). An [Address] of this type exposes [Address.paymentCredential] as non-null
     * and [Address.stakeCredential] as null.
     */
    ENTERPRISE,

    /**
     * A reward (stake) address (CIP-19 header types 14 and 15): a single stake credential.
     * The credential is a stake key hash (type 14) or a script hash (type 15). An [Address]
     * of this type exposes [Address.stakeCredential] as non-null and
     * [Address.paymentCredential] as null.
     */
    REWARD,

    /**
     * A pointer address (CIP-19 header types 4 and 5): a payment credential plus a chain
     * pointer to an on-chain stake key registration certificate, instead of an inline
     * delegation credential. The payment credential is a key hash (type 4) or a script hash
     * (type 5). An [Address] of this type exposes [Address.paymentCredential] and
     * [Address.pointer] as non-null and [Address.stakeCredential] as null.
     *
     * The pointer is the three variable-length coordinates `(slot, transactionIndex,
     * certificateIndex)`; see [AddressPointer]. This is structural classification only: it
     * does not check that the pointer refers to an existing certificate on-chain. CIP-19
     * notes that from the Conway ledger era new pointer addresses can no longer be added to
     * mainnet; parsing an existing pointer address remains structurally valid and is
     * era-agnostic.
     */
    POINTER,
}
