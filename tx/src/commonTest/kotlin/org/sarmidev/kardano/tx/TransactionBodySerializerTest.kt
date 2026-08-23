package org.sarmidev.kardano.tx

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.encoding.cbor.CborError
import org.sarmidev.kardano.encoding.cbor.CborValue
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Structural tests for [TransactionBodySerializer], per ADR-0014 §9: the encoded body is
 * decoded back through `:core` [Cbor.decode] and inspected against the CDDL shape. No
 * `transaction_body` golden bytes are invented (ADR-0014 §9 records that no citable minimal
 * ADA-only vector was found).
 *
 * Addresses reuse the CIP-19 "Test vectors" mainnet/testnet base (type-00) addresses already
 * cited verbatim in `:core`'s `AddressTest`
 * (`core/src/commonTest/kotlin/org/sarmidev/kardano/address/AddressTest.kt`) — not invented
 * for this test.
 * https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md
 */
class TransactionBodySerializerTest {

    private companion object {
        // CIP-19 "Test vectors" (verbatim), copied from AddressTest's own citation.
        const val TESTNET_TYPE_00 =
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"
        const val MAINNET_TYPE_00 =
            "addr1qx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgse35a3x"

        const val DEFAULT_FEE = 170_000L
    }

    private fun address(bech32: String): Address =
        requireNotNull(Address.parse(bech32).getOrNull()) { "expected a valid test address" }

    private fun txHash(fill: Byte): TxHash =
        requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { fill }).getOrNull())

    private fun utxoRef(hashFill: Byte, index: Long): UtxoRef =
        requireNotNull(UtxoRef.of(txHash(hashFill), index).getOrNull())

    private fun lovelace(value: Long): Lovelace = requireNotNull(Lovelace.of(value).getOrNull())

    private fun paymentOutput(): TransactionOutput =
        TransactionOutput(address(TESTNET_TYPE_00), lovelace(2_000_000L))

    private fun decodedMap(draft: TransactionDraft): CborValue.CborMap {
        val decoded = assertIs<KardanoResult.Ok<CborValue>>(Cbor.decode(draft.bodyCbor()))
        return assertIs<CborValue.CborMap>(decoded.value)
    }

    private fun keysOf(map: CborValue.CborMap): List<Long> =
        map.entries().map { assertIs<CborValue.CborUnsigned>(it.key).value }

    @Test
    fun bodyMapHasKeysZeroOneTwoInOrderWhenTtlOmitted() {
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = listOf(paymentOutput()),
            fee = lovelace(DEFAULT_FEE),
        )

        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(request),
        ).value

        assertEquals(listOf(0L, 1L, 2L), keysOf(decodedMap(draft)))
    }

    @Test
    fun bodyMapHasKeysZeroOneTwoThreeInOrderWhenTtlSupplied() {
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = listOf(paymentOutput()),
            fee = lovelace(DEFAULT_FEE),
            ttl = 12_345_678L,
        )

        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(request),
        ).value
        val body = decodedMap(draft)

        assertEquals(listOf(0L, 1L, 2L, 3L), keysOf(body))
        val ttlValue = assertIs<CborValue.CborUnsigned>(body.entries().last().value)
        assertEquals(12_345_678L, ttlValue.value)
    }

    @Test
    fun inputsAreSortedRegardlessOfSuppliedOrder() {
        val lowerHash = utxoRef(1, 5L)
        val higherHash = utxoRef(2, 0L)
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(higherHash, lowerHash), // supplied out of ledger order
            outputs = listOf(paymentOutput()),
            fee = lovelace(DEFAULT_FEE),
        )

        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(request),
        ).value
        assertEquals(listOf(lowerHash, higherHash), draft.selectedInputs)

        val inputsArray = assertIs<CborValue.CborArray>(decodedMap(draft).entries()[0].value)
        val firstEncoded = assertIs<CborValue.CborArray>(inputsArray.items()[0])
        val firstIndex = assertIs<CborValue.CborUnsigned>(firstEncoded.items()[1])
        assertEquals(5L, firstIndex.value)
    }

    @Test
    fun duplicateInputsAreRejected() {
        val ref = utxoRef(3, 2L)
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(ref, utxoRef(3, 2L)),
            outputs = listOf(paymentOutput()),
            fee = lovelace(DEFAULT_FEE),
        )

        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBodySerializer.serialize(request),
        )
        val duplicate = assertIs<TxBuildError.DuplicateInput>(err.error)
        assertEquals(ref, duplicate.ref)
    }

    @Test
    fun outputsUseLegacyAddressCoinArrayForm() {
        val output = paymentOutput()
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = listOf(output),
            fee = lovelace(DEFAULT_FEE),
        )

        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(request),
        ).value
        val outputsArray = assertIs<CborValue.CborArray>(decodedMap(draft).entries()[1].value)
        val encodedOutput = assertIs<CborValue.CborArray>(outputsArray.items()[0])

        assertEquals(2, encodedOutput.items().size)
        val encodedAddress = assertIs<CborValue.CborByteString>(encodedOutput.items()[0])
        assertEquals(
            output.address.toByteArray().toList(),
            encodedAddress.toByteArray().toList(),
        )
        val encodedCoin = assertIs<CborValue.CborUnsigned>(encodedOutput.items()[1])
        assertEquals(output.amount.value, encodedCoin.value)
    }

    @Test
    fun bodyCborReturnsDefensiveCopy() {
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = listOf(paymentOutput()),
            fee = lovelace(DEFAULT_FEE),
        )
        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(request),
        ).value

        val original = draft.bodyCbor()
        val mutable = draft.bodyCbor()
        mutable[0] = (mutable[0] + 1).toByte()

        assertEquals(original.toList(), draft.bodyCbor().toList())
        assertTrue(!mutable.contentEquals(draft.bodyCbor()))
    }

    @Test
    fun mismatchedOutputNetworkIsRejected() {
        val mainnetOutput = TransactionOutput(address(MAINNET_TYPE_00), lovelace(2_000_000L))
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = listOf(mainnetOutput),
            fee = lovelace(DEFAULT_FEE),
        )

        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBodySerializer.serialize(request),
        )
        val mismatch = assertIs<TxBuildError.NetworkMismatch>(err.error)
        assertEquals(Network.TESTNET, mismatch.expected)
        assertEquals(Network.MAINNET, mismatch.actual)
    }

    @Test
    fun emptyInputsIsRejectedWithNoInputs() {
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = emptyList(),
            outputs = listOf(paymentOutput()),
            fee = lovelace(DEFAULT_FEE),
        )

        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBodySerializer.serialize(request),
        )
        assertIs<TxBuildError.NoInputs>(err.error)
    }

    @Test
    fun emptyOutputsIsRejectedWithNoOutputs() {
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = emptyList(),
            fee = lovelace(DEFAULT_FEE),
        )

        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBodySerializer.serialize(request),
        )
        assertIs<TxBuildError.NoOutputs>(err.error)
    }

    @Test
    fun serialize_testnetDraft_carriesTestnetNetworkAndPhase1Scope() {
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = listOf(paymentOutput()),
            fee = lovelace(DEFAULT_FEE),
        )

        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(request),
        ).value

        assertEquals(Network.TESTNET, draft.network)
        assertEquals(TransactionDraftScope.Phase1AdaOnlySinglePayment, draft.scope)
    }

    @Test
    fun serialize_mainnetDraft_carriesMainnetNetworkAndPhase1Scope() {
        val mainnetOutput = TransactionOutput(address(MAINNET_TYPE_00), lovelace(2_000_000L))
        val request = TransactionBodyRequest(
            network = Network.MAINNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = listOf(mainnetOutput),
            fee = lovelace(DEFAULT_FEE),
        )

        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(request),
        ).value

        assertEquals(Network.MAINNET, draft.network)
        assertEquals(TransactionDraftScope.Phase1AdaOnlySinglePayment, draft.scope)
    }

    @Test
    fun draftEqualsAndHashCode_includeNetworkAndScope() {
        val testnetRequest = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = listOf(paymentOutput()),
            fee = lovelace(DEFAULT_FEE),
        )
        val first = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(testnetRequest),
        ).value
        val second = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(testnetRequest),
        ).value
        val mainnetDraft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(
                TransactionBodyRequest(
                    network = Network.MAINNET,
                    inputs = listOf(utxoRef(1, 0L)),
                    outputs = listOf(TransactionOutput(address(MAINNET_TYPE_00), lovelace(2_000_000L))),
                    fee = lovelace(DEFAULT_FEE),
                ),
            ),
        ).value

        assertEquals(first, second)
        assertEquals(first.hashCode(), second.hashCode())
        assertTrue(first != mainnetDraft, "drafts built for different networks must not be equal")
        assertTrue(
            first.toString().contains("network=TESTNET"),
            "toString should name the bound network, got: $first",
        )
        assertTrue(
            first.toString().contains("scope="),
            "toString should name the bound scope, got: $first",
        )
    }

    @Test
    fun withUnsupportedScopeForPolicyTest_replacesScopeOnly() {
        val draft = assertIs<KardanoResult.Ok<TransactionDraft>>(
            TransactionBodySerializer.serialize(
                TransactionBodyRequest(
                    network = Network.TESTNET,
                    inputs = listOf(utxoRef(1, 0L)),
                    outputs = listOf(paymentOutput()),
                    fee = lovelace(DEFAULT_FEE),
                ),
            ),
        ).value

        val rewritten = draft.withUnsupportedScopeForPolicyTest()

        assertEquals(UnsupportedTransactionDraftScope, rewritten.scope)
        assertEquals(draft.network, rewritten.network)
        assertEquals(draft.selectedInputs, rewritten.selectedInputs)
        assertEquals(draft.outputs, rewritten.outputs)
        assertEquals(draft.fee, rewritten.fee)
        assertEquals(draft.ttl, rewritten.ttl)
        assertEquals(draft.bodyCbor().toList(), rewritten.bodyCbor().toList())
        assertTrue(draft != rewritten)
    }

    @Test
    fun negativeTtlIsRejectedAsSerializationError() {
        val request = TransactionBodyRequest(
            network = Network.TESTNET,
            inputs = listOf(utxoRef(1, 0L)),
            outputs = listOf(paymentOutput()),
            fee = lovelace(DEFAULT_FEE),
            ttl = -1L,
        )

        val err = assertIs<KardanoResult.Err<TxBuildError>>(
            TransactionBodySerializer.serialize(request),
        )
        val serialization = assertIs<TxBuildError.Serialization>(err.error)
        assertIs<CborError.UnsignedValueNegative>(serialization.error)
    }
}
