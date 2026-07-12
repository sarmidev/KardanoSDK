package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.derivation.Cip1852Path
import org.sarmidev.kardano.crypto.derivation.Cip1852Role

/**
 * A **test-only** fixture wallet for the Playground's derivation checkpoint (Block 1.6d).
 *
 * [words] is the public BIP-39 mnemonic cited by `IntersectMBO/cardano-addresses`'s golden
 * test vectors (also used by `:crypto`'s `KeyDerivationVectorsTest` and
 * `PublicKeyProjectionDeviceTest`) — **not** a real mnemonic, and never associated with real
 * funds. [path] is the single CIP-1852 path this checkpoint derives:
 * `m/1852'/1815'/0'/0/0`. This object holds no key material of its own; it only names the
 * cited public inputs the presenter passes to `:crypto`.
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

    /** The single CIP-1852 path this checkpoint derives: `m/1852'/1815'/0'/0/0`. */
    val path: Cip1852Path = requireValidPath()

    /**
     * The cited golden Blake2b-224 fingerprint (CIP-19 payment credential) for [path] derived
     * from [words], matching the `addr_xvk0` / payment-credential vectors already cited in
     * `:crypto`'s `HashingVectorsTest` and `PublicKeyProjectionDeviceTest`.
     */
    const val GOLDEN_FINGERPRINT_HEX: String =
        "9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e"

    private fun requireValidPath(): Cip1852Path =
        when (val result = Cip1852Path.of(account = 0, role = Cip1852Role.EXTERNAL, index = 0)) {
            is KardanoResult.Ok -> result.value
            // Unreachable: 0/EXTERNAL/0 is always in range. A hard failure here would be a
            // programming error in this fixture, not a runtime condition to handle gracefully.
            is KardanoResult.Err -> error("TestWalletFixture path is invalid: ${result.error}")
        }
}
