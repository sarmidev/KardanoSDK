package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.crypto.derivation.Cip1852Path
import org.sarmidev.kardano.crypto.derivation.Cip1852Role
import org.sarmidev.kardano.crypto.derivation.IcarusMasterKey
import org.sarmidev.kardano.crypto.derivation.KeyDerivation
import org.sarmidev.kardano.crypto.hashing.Hashing
import org.sarmidev.kardano.crypto.mnemonic.Mnemonic
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.encoding.cbor.CborValue
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.tx.TransactionBodyRequest
import org.sarmidev.kardano.tx.TransactionBodySerializer
import org.sarmidev.kardano.tx.TransactionDraft
import org.sarmidev.kardano.tx.TransactionOutput
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.fail

/**
 * JVM-only end-to-end test for [ReadOnlyWallet.signTestnetFixtureTransaction].
 *
 * Reaches `:crypto`'s native derivation and signing backends, which cannot load under
 * `:wallet:testAndroidHostTest` (host JVM, Android target) — mirroring the same
 * native-vs-host-JVM split [ReadOnlyWalletRestoreDesktopTest] already established. This is a
 * **self-consistency** check (ADR-0015 §6), not an external golden: no full signed-transaction
 * vector exists to cite (mirroring `TransactionBodySerializerTest`'s unsigned-body policy), so
 * this independently re-derives the payment key and re-hashes the body with the same already
 * cited `IntersectMBO/cardano-addresses` test mnemonic used by
 * [ReadOnlyWalletRestoreDesktopTest], and checks
 * [ReadOnlyWallet.signTestnetFixtureTransaction]'s output against that independent computation.
 *
 * Class-level [OptIn] for [ExperimentalKardanoSigningScope] (ADR-0018): this test exercises the
 * Phase 1 testnet/test-fixture flow the entry point is scoped to, using the cited fixture
 * mnemonic and [Network.TESTNET] explicitly at every call, exactly as every in-repository call
 * site must.
 */
@OptIn(ExperimentalKardanoSigningScope::class)
class ReadOnlyWalletSignTestnetFixtureTransactionDesktopTest {

    private companion object {
        const val TESTNET_TYPE_00 =
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"

        val mnemonic = listOf(
            "test", "walk", "nut", "penalty", "hip", "pave",
            "soap", "entry", "language", "right", "filter", "choice",
        )
    }

    private fun fixtureDraft(): TransactionDraft {
        val address = requireNotNull(Address.parse(TESTNET_TYPE_00).getOrNull())
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { 7 }).getOrNull())
        val utxoRef = requireNotNull(UtxoRef.of(txHash, 0L).getOrNull())
        val fee = requireNotNull(Lovelace.of(170_000L).getOrNull())
        val output = TransactionOutput(address, requireNotNull(Lovelace.of(2_000_000L).getOrNull()))
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef),
            outputs = listOf(output),
            fee = fee,
        )
        return when (val result = TransactionBodySerializer.serialize(request)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected a valid fixture draft but got Err(${result.error})")
        }
    }

    /** Independently derives the same account-0 payment public key [ReadOnlyWallet] would. */
    private fun expectedPaymentPublicKeyBytes(): ByteArray {
        val parsedMnemonic = when (val result = Mnemonic.parse(mnemonic)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected a valid mnemonic but got Err(${result.error})")
        }
        try {
            val master = when (val result = IcarusMasterKey.fromMnemonic(parsedMnemonic)) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> fail("expected master key but got Err(${result.error})")
            }
            try {
                val path = when (val result = Cip1852Path.of(account = 0, role = Cip1852Role.EXTERNAL, index = 0)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> fail("expected a valid path but got Err(${result.error})")
                }
                val derivation = KeyDerivation.default()
                val privateKey = when (val result = derivation.derivePrivate(master, path)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> fail("expected a private key but got Err(${result.error})")
                }
                try {
                    val publicKey = when (val result = derivation.publicKey(privateKey)) {
                        is KardanoResult.Ok -> result.value
                        is KardanoResult.Err -> fail("expected a public key but got Err(${result.error})")
                    }
                    return publicKey.publicKeyBytes()
                } finally {
                    privateKey.clear()
                }
            } finally {
                master.clear()
            }
        } finally {
            parsedMnemonic.clear()
        }
    }

    @Test
    fun signTestnetFixtureTransaction_producesOneWitnessWithTheDerivedPaymentVkeyAndCorrectTransactionId() {
        val draft = fixtureDraft()
        val expectedBodyHash = when (val result = Hashing.default().blake2b256(draft.bodyCbor())) {
            is KardanoResult.Ok -> result.value.toByteArray()
            is KardanoResult.Err -> fail("expected a body hash but got Err(${result.error})")
        }
        val expectedVkey = expectedPaymentPublicKeyBytes()

        val signed = when (
            val result = ReadOnlyWallet.signTestnetFixtureTransaction(mnemonic, Network.TESTNET, draft)
        ) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }

        assertEquals(1, signed.witnessCount)
        assertContentEquals(expectedBodyHash, signed.transactionId.toByteArray())

        val witness = signed.signedTransaction.witnessSet.verificationKeyWitnesses.single()
        assertContentEquals(expectedVkey, witness.vkeyBytes())
        assertEquals(64, witness.signatureBytes().size)
    }

    @Test
    fun signTestnetFixtureTransaction_embedsTheDraftBodyUnchangedAsFieldZero() {
        val draft = fixtureDraft()

        val signed = when (
            val result = ReadOnlyWallet.signTestnetFixtureTransaction(mnemonic, Network.TESTNET, draft)
        ) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
        }

        val decoded = assertIs<KardanoResult.Ok<CborValue>>(Cbor.decode(signed.signedTransaction.cbor()))
        val transaction = assertIs<CborValue.CborArray>(decoded.value)
        val decodedBody = transaction.items()[0]
        val reEncodedBody = assertIs<KardanoResult.Ok<ByteArray>>(Cbor.encode(decodedBody)).value

        assertContentEquals(draft.bodyCbor(), reEncodedBody)
    }

    @Test
    fun signTestnetFixtureTransaction_doesNotMutateDraftBodyOrFee() {
        val draft = fixtureDraft()
        val originalBody = draft.bodyCbor()
        val originalFee = draft.fee

        ReadOnlyWallet.signTestnetFixtureTransaction(mnemonic, Network.TESTNET, draft)

        assertContentEquals(originalBody, draft.bodyCbor())
        assertEquals(originalFee, draft.fee)
    }
}
