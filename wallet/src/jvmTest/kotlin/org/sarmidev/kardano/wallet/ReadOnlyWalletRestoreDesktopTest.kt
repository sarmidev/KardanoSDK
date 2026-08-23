package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.address.AddressType
import org.sarmidev.kardano.encoding.hex.Hex
import org.sarmidev.kardano.primitives.Network
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * JVM-only end-to-end test for [ReadOnlyWallet.restore].
 *
 * Reaches `:crypto`'s native derivation and public-key-projection backends, which cannot load
 * under `:wallet:testAndroidHostTest` (host JVM, Android target) — the module's other
 * `commonTest` suites cover the native-free paths that do run there. This mirrors the same
 * native-vs-host-JVM split already established for `:crypto`'s `KeyDerivationVectorsTest` and
 * `:shared`'s `PlaygroundWalletDerivationDesktopTest`.
 *
 * The cited mnemonic and golden payment-credential fingerprint are the same
 * `IntersectMBO/cardano-addresses` (Apache-2.0) Shelley golden vector already pinned in
 * `:crypto`'s `HashingVectorsTest`/`KeyDerivationVectorsTest` and reproduced end to end by
 * `PublicKeyProjectionDeviceTest`, for `m/1852'/1815'/0'/0/0` — this module's fixed payment
 * path. There is no externally cited golden for the stake credential or for a full generated
 * `addr_test` string, so this test asserts only the cited payment credential plus a structural
 * generate-then-parse round trip, never a self-generated address as if it were an external
 * vector (per this project's test-vector policy).
 */
class ReadOnlyWalletRestoreDesktopTest {

    private val mnemonic = listOf(
        "test", "walk", "nut", "penalty", "hip", "pave",
        "soap", "entry", "language", "right", "filter", "choice",
    )

    private val cip19PaymentCredential = "9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e"

    @Test
    fun restore_matchesGoldenPathsAndFingerprint_andGeneratesRoundtrippingAddress() {
        val wallet = when (val result = ReadOnlyWallet.restore(mnemonic, Network.TESTNET)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }

        assertEquals(Network.TESTNET, wallet.network)
        assertEquals("m/1852'/1815'/0'/0/0", wallet.paymentPath.toString())
        assertEquals("m/1852'/1815'/0'/2/0", wallet.stakePath.toString())

        val generatedBech32 = wallet.address.toBech32()
        assertTrue(
            generatedBech32.startsWith("addr_test1"),
            "expected a testnet base address, got: $generatedBech32",
        )

        val parsed = when (val result = Address.parse(generatedBech32)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("generated address should re-parse, got: ${result.error}")
        }
        assertEquals(Network.TESTNET, parsed.network)
        assertEquals(AddressType.BASE, parsed.type)
        assertEquals(wallet.address, parsed)

        val paymentCredential = requireNotNull(parsed.paymentCredential) {
            "a base address should have a payment credential"
        }
        val encodedPaymentCredential = when (val result = Hex.encode(paymentCredential.hashBytes())) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }
        assertEquals(cip19PaymentCredential, encodedPaymentCredential)
    }
}
