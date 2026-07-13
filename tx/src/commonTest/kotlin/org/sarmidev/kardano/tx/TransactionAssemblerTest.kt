package org.sarmidev.kardano.tx

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.encoding.cbor.CborValue
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.fail

/**
 * Structural tests for [TransactionAssembler] (ADR-0015 §1/§3/§6, Block 1.10b): assembled CBOR
 * is decoded back through `:core` [Cbor.decode] and inspected against the CDDL shape
 * `[transaction_body, transaction_witness_set, true, null]`. `:tx` is crypto-free (ADR-0015
 * §1), so [fixtureVkey]/[fixtureSignature] are synthetic fixture bytes only — not a real key or
 * signature, and no cryptographic correctness is asserted here.
 *
 * Addresses reuse the CIP-19 "Test vectors" testnet base (type-00) address already cited
 * verbatim in `:core`'s `AddressTest`, mirroring `TransactionBodySerializerTest`.
 */
class TransactionAssemblerTest {

    private companion object {
        const val TESTNET_TYPE_00 =
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"
        const val DEFAULT_FEE = 170_000L
    }

    // Synthetic fixture bytes only; not a real verification key or signature.
    private val fixtureVkey = ByteArray(32) { (it + 1).toByte() }
    private val fixtureSignature = ByteArray(64) { (it + 100).toByte() }

    private fun address(bech32: String): Address =
        requireNotNull(Address.parse(bech32).getOrNull()) { "expected a valid test address" }

    private fun txHash(fill: Byte): TxHash =
        requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { fill }).getOrNull())

    private fun utxoRef(hashFill: Byte, index: Long): UtxoRef =
        requireNotNull(UtxoRef.of(txHash(hashFill), index).getOrNull())

    private fun lovelace(value: Long): Lovelace = requireNotNull(Lovelace.of(value).getOrNull())

    private fun paymentOutput(): TransactionOutput =
        TransactionOutput(address(TESTNET_TYPE_00), lovelace(2_000_000L))

    private fun draft(): TransactionDraft {
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = listOf(paymentOutput()),
            fee = lovelace(DEFAULT_FEE),
        )
        return okDraft(TransactionBodySerializer.serialize(request))
    }

    private fun oneWitnessSet(): TransactionWitnessSet =
        okSet(
            TransactionWitnessSet.of(
                listOf(okWitness(VerificationKeyWitness.of(fixtureVkey, fixtureSignature))),
            ),
        )

    @Test
    fun assemble_producesFullTransactionArrayOfExactlyFourElements() {
        val signed = okSigned(TransactionAssembler.assemble(draft(), oneWitnessSet()))

        val decoded = decodedTransaction(signed)
        assertEquals(4, decoded.items().size)
    }

    @Test
    fun assemble_fieldZeroIsTheExactBodyCborDraftProduced() {
        val d = draft()
        val signed = okSigned(TransactionAssembler.assemble(d, oneWitnessSet()))

        val decodedBody = decodedTransaction(signed).items()[0]
        val reEncodedBody = assertIs<KardanoResult.Ok<ByteArray>>(Cbor.encode(decodedBody)).value

        assertContentEquals(d.bodyCbor(), reEncodedBody, "field 0 must be the draft's body, unchanged")
    }

    @Test
    fun assemble_fieldTwoIsTrueAndFieldThreeIsNull() {
        val signed = okSigned(TransactionAssembler.assemble(draft(), oneWitnessSet()))

        val items = decodedTransaction(signed).items()
        assertEquals(CborValue.CborBool(true), items[2])
        assertEquals(CborValue.CborNull, items[3])
    }

    @Test
    fun assemble_witnessSetHasExactlyKeyZeroWithOneVkeyWitness() {
        val signed = okSigned(TransactionAssembler.assemble(draft(), oneWitnessSet()))

        val witnessSetMap = assertIs<CborValue.CborMap>(decodedTransaction(signed).items()[1])
        assertEquals(1, witnessSetMap.entries().size, "only field 0 (vkeywitness set) is populated")
        val entry = witnessSetMap.entries()[0]
        assertEquals(0L, assertIs<CborValue.CborUnsigned>(entry.key).value)

        val witnesses = assertIs<CborValue.CborArray>(entry.value)
        assertEquals(1, witnesses.items().size)
        val witness = assertIs<CborValue.CborArray>(witnesses.items()[0])
        assertEquals(2, witness.items().size, "a vkeywitness is exactly [vkey, signature]")
        val vkeyBytes = assertIs<CborValue.CborByteString>(witness.items()[0]).toByteArray()
        val sigBytes = assertIs<CborValue.CborByteString>(witness.items()[1]).toByteArray()
        assertContentEquals(fixtureVkey, vkeyBytes)
        assertContentEquals(fixtureSignature, sigBytes)
    }

    @Test
    fun assemble_withTwoWitnesses_encodesBothInSuppliedOrder() {
        val secondVkey = ByteArray(32) { (it + 50).toByte() }
        val secondSignature = ByteArray(64) { (it + 150).toByte() }
        val witnessSet = okSet(
            TransactionWitnessSet.of(
                listOf(
                    okWitness(VerificationKeyWitness.of(fixtureVkey, fixtureSignature)),
                    okWitness(VerificationKeyWitness.of(secondVkey, secondSignature)),
                ),
            ),
        )

        val signed = okSigned(TransactionAssembler.assemble(draft(), witnessSet))

        val witnessSetMap = assertIs<CborValue.CborMap>(decodedTransaction(signed).items()[1])
        val witnesses = assertIs<CborValue.CborArray>(witnessSetMap.entries()[0].value)
        assertEquals(2, witnesses.items().size)
        assertEquals(2, signed.witnessCount)
    }

    @Test
    fun assemble_doesNotMutateDraftBodyOrFee() {
        val d = draft()
        val originalBody = d.bodyCbor()
        val originalFee = d.fee

        TransactionAssembler.assemble(d, oneWitnessSet())

        assertContentEquals(originalBody, d.bodyCbor(), "assembling must not rebuild or alter the body")
        assertEquals(originalFee, d.fee, "assembling must not alter the fee")
    }

    @Test
    fun cbor_returnsIndependentCopy() {
        val signed = okSigned(TransactionAssembler.assemble(draft(), oneWitnessSet()))
        val originalFirstByte = signed.cbor()[0]

        val exposed = signed.cbor()
        exposed[0] = (originalFirstByte + 1).toByte()

        assertEquals(
            originalFirstByte,
            signed.cbor()[0],
            "mutating a returned copy must not affect the SignedTransaction's internal bytes",
        )
    }

    // Structural guard: the witness/assembly API provides no way to represent a script witness,
    // native asset, metadata, or auxiliary data — VerificationKeyWitness.of only ever validates
    // vkey/signature byte lengths, and TransactionAssembler.assemble only ever emits field 0 of
    // the witness set and a fixed `null` auxiliary_data. These are not silently accepted; there
    // is no parameter through which they could be supplied at all.
    @Test
    fun witnessSet_hasNoScriptOrOtherWitnessFields() {
        val signed = okSigned(TransactionAssembler.assemble(draft(), oneWitnessSet()))

        val witnessSetMap = assertIs<CborValue.CborMap>(decodedTransaction(signed).items()[1])
        val keys = witnessSetMap.entries().map { assertIs<CborValue.CborUnsigned>(it.key).value }
        assertEquals(listOf(0L), keys, "no script (1/3/6), bootstrap (2), or Plutus (4/5) witness fields")
    }

    private fun decodedTransaction(signed: SignedTransaction): CborValue.CborArray {
        val decoded = assertIs<KardanoResult.Ok<CborValue>>(Cbor.decode(signed.cbor()))
        return assertIs<CborValue.CborArray>(decoded.value)
    }

    private fun okDraft(
        result: KardanoResult<TransactionDraft, TxBuildError>,
    ): TransactionDraft = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }

    private fun okWitness(
        result: KardanoResult<VerificationKeyWitness, TxBuildError>,
    ): VerificationKeyWitness = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }

    private fun okSet(
        result: KardanoResult<TransactionWitnessSet, TxBuildError>,
    ): TransactionWitnessSet = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }

    private fun okSigned(
        result: KardanoResult<SignedTransaction, TxBuildError>,
    ): SignedTransaction = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }
}
