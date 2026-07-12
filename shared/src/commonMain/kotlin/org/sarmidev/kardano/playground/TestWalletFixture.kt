package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.derivation.Cip1852Path
import org.sarmidev.kardano.crypto.derivation.Cip1852Role

/**
 * A **test-only** fixture wallet for the Playground's derivation and address-generation
 * checkpoints (Block 1.6d, extended by Block 1.7b).
 *
 * [words] is the public BIP-39 mnemonic cited by `IntersectMBO/cardano-addresses`'s golden
 * test vectors (also used by `:crypto`'s `KeyDerivationVectorsTest` and
 * `PublicKeyProjectionDeviceTest`) — **not** a real mnemonic, and never associated with real
 * funds. [paymentPath] and [stakePath] are the two CIP-1852 paths this checkpoint derives:
 * `m/1852'/1815'/0'/0/0` (payment) and `m/1852'/1815'/0'/2/0` (stake). This object holds no
 * key material of its own; it only names the cited public inputs the presenter passes to
 * `:crypto` and `:core`.
 */
internal object TestWalletFixture {

    /**
     * The cited test-only BIP-39 English mnemonic (12 words), copied verbatim from the
     * `IntersectMBO/cardano-addresses` golden vectors already pinned in `:crypto`. Test-only:
     * never a real mnemonic, never used for real funds.
     */
    val words: List<String> = listOf(
        "test", "walk", "nut", "penalty", "hip", "pave",
        "soap", "entry", "language", "right", "filter", "choice",
    )

    /** The payment (external) CIP-1852 path this checkpoint derives: `m/1852'/1815'/0'/0/0`. */
    val paymentPath: Cip1852Path = requireValidPath(Cip1852Role.EXTERNAL)

    /** The stake (staking) CIP-1852 path this checkpoint derives: `m/1852'/1815'/0'/2/0`. */
    val stakePath: Cip1852Path = requireValidPath(Cip1852Role.STAKING)

    /**
     * The cited golden Blake2b-224 fingerprint (CIP-19 payment credential) for [paymentPath]
     * derived from [words], matching the `addr_xvk0` / payment-credential vectors already
     * cited in `:crypto`'s `HashingVectorsTest` and `PublicKeyProjectionDeviceTest`.
     *
     * There is no equivalent externally cited golden for [stakePath] or for a full generated
     * `addr_test` address: those are computed by the Playground checkpoint itself at runtime
     * (Block 1.7b) and are structural/self-generated fixture output, not an external vector —
     * they are never pinned here as if they were one.
     */
    const val GOLDEN_FINGERPRINT_HEX: String =
        "9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e"

    private fun requireValidPath(role: Cip1852Role): Cip1852Path =
        when (val result = Cip1852Path.of(account = 0, role = role, index = 0)) {
            is KardanoResult.Ok -> result.value
            // Unreachable: 0/<role>/0 is always in range. A hard failure here would be a
            // programming error in this fixture, not a runtime condition to handle gracefully.
            is KardanoResult.Err -> error("TestWalletFixture path is invalid: ${result.error}")
        }
}
