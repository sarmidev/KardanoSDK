package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.hex.Hex

/**
 * The cited public payment-credential fingerprint that
 * [ReadOnlyWallet.signTestnetFixtureTransaction] uses to recognize the Phase 1 test fixture
 * (ADR-0019 §3).
 *
 * This is **not** a mnemonic, seed, or private key. It is the 28-byte Blake2b-224
 * (CIP-19 payment credential) of the account-0 external public key at
 * `m/1852'/1815'/0'/0/0` derived from the published IntersectMBO `cardano-addresses`
 * Shelley golden mnemonic. The phrase itself is not stored in this module's production
 * code; `:wallet` also does not depend on `:shared`'s `TestWalletFixture`.
 *
 * **Why this identity is test-only.** The fingerprint identifies a *published test vector*,
 * not a funded wallet. Source (Apache-2.0), already pinned by `:crypto`'s
 * `KeyDerivationVectorsTest` / `HashingVectorsTest` and by `ReadOnlyWallet.restore`:
 *
 * - Repository: `IntersectMBO/cardano-addresses`
 * - Path: `test/golden/addresses_5574d91d/golden`
 * - Pinned commit: `46d01319015275941f96126b2496453693f89538`
 * - The same 28-byte value is the CIP-19 type-00 payment credential cited in
 *   `HashingVectorsTest` (`9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e`).
 *
 * @see <a href="https://github.com/IntersectMBO/cardano-addresses/tree/46d01319015275941f96126b2496453693f89538/test/golden/addresses_5574d91d">IntersectMBO/cardano-addresses golden</a>
 * @see <a href="https://cips.cardano.org/cip/CIP-19">CIP-19</a>
 */
public object Phase1FixtureIdentity {

    /**
     * Canonical lowercase hex of the 28-byte Blake2b-224 payment credential. Copied verbatim
     * from the cited sources above; not computed here.
     */
    public const val PAYMENT_CREDENTIAL_FINGERPRINT_HEX: String =
        "9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e"

    /**
     * Whether [paymentCredentialHash] equals the cited fingerprint, compared as raw bytes.
     *
     * @param paymentCredentialHash a candidate 28-byte Blake2b-224 digest. Not retained.
     */
    internal fun matchesPaymentCredential(paymentCredentialHash: ByteArray): Boolean {
        val expected = when (val result = Hex.decode(PAYMENT_CREDENTIAL_FINGERPRINT_HEX)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> return false
        }
        return paymentCredentialHash.contentEquals(expected)
    }
}
