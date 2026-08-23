package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.crypto.mnemonic.MnemonicError
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
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.fail

/**
 * Native-free tests for [ReadOnlyWallet.signTestnetFixtureTransaction]'s mnemonic-rejection
 * paths.
 *
 * [org.sarmidev.kardano.crypto.mnemonic.Mnemonic.parse] rejects invalid input before
 * [ReadOnlyWallet.signTestnetFixtureTransaction] ever calls into `:crypto`'s native derivation/
 * signing backends, so these cases run under both `:wallet:jvmTest` and
 * `:wallet:testAndroidHostTest`, mirroring [ReadOnlyWalletRestoreMnemonicTest]. See
 * [ReadOnlyWalletSignTestnetFixtureTransactionDesktopTest] for the JVM-only end-to-end success
 * path that does reach native code.
 *
 * The [TransactionDraft] fixture reuses the CIP-19 "Test vectors" testnet base (type-00)
 * address already cited verbatim in `:core`'s `AddressTest`, mirroring
 * `TransactionBodySerializerTest`. Building it needs no native cryptography (`:tx` is
 * crypto-free).
 *
 * Class-level [OptIn] for [ExperimentalKardanoSigningScope] (ADR-0018): every call here already
 * declares [Network.TESTNET] explicitly, per the Phase 1 call-site discipline the entry point's
 * own KDoc requires.
 */
@OptIn(ExperimentalKardanoSigningScope::class)
class ReadOnlyWalletSignTestnetFixtureTransactionMnemonicTest {

    private companion object {
        const val TESTNET_TYPE_00 =
            "addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae"
        const val MAINNET_TYPE_00 =
            "addr1qx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgse35a3x"

        val unusedWords = listOf("not", "a", "mnemonic")
    }

    private fun fixtureDraft(network: Network = Network.TESTNET): TransactionDraft {
        val bech32 = if (network == Network.TESTNET) TESTNET_TYPE_00 else MAINNET_TYPE_00
        val address = requireNotNull(Address.parse(bech32).getOrNull())
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { 1 }).getOrNull())
        val utxoRef = requireNotNull(UtxoRef.of(txHash, 0L).getOrNull())
        val fee = requireNotNull(Lovelace.of(170_000L).getOrNull())
        val output = TransactionOutput(address, requireNotNull(Lovelace.of(2_000_000L).getOrNull()))
        val request = TransactionBodyRequest(
            network = network,
            inputs = listOf(utxoRef),
            outputs = listOf(output),
            fee = fee,
        )
        return when (val result = TransactionBodySerializer.serialize(request)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> fail("expected a valid fixture draft but got Err(${result.error})")
        }
    }

    @Test
    fun signTestnetFixtureTransaction_withInvalidWordCount_returnsMnemonicErrorWithoutReachingNativeCode() {
        val result = ReadOnlyWallet.signTestnetFixtureTransaction(
            listOf("test", "walk", "nut", "penalty"),
            Network.TESTNET,
            fixtureDraft(),
        )

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val mnemonicError = assertIs<WalletError.Mnemonic>(err.error)
        assertIs<MnemonicError.InvalidWordCount>(mnemonicError.error)
    }

    @Test
    fun signTestnetFixtureTransaction_withWordNotInWordlist_returnsMnemonicErrorWithoutReachingNativeCode() {
        val words = listOf(
            "test", "walk", "nut", "penalty", "hip", "pave",
            "soap", "entry", "language", "right", "filter", "notaword",
        )

        val result = ReadOnlyWallet.signTestnetFixtureTransaction(words, Network.TESTNET, fixtureDraft())

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val mnemonicError = assertIs<WalletError.Mnemonic>(err.error)
        assertIs<MnemonicError.WordNotInWordlist>(mnemonicError.error)
    }

    @Test
    fun signTestnetFixtureTransaction_mainnetDraftDeclaredTestnet_isSigningScopeViolationBeforeMnemonicParse() {
        val result = ReadOnlyWallet.signTestnetFixtureTransaction(
            unusedWords,
            Network.TESTNET,
            fixtureDraft(Network.MAINNET),
        )

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val violation = assertIs<WalletError.SigningScopeViolation>(err.error)
        val reason = assertIs<SigningScopeViolationReason.UnsupportedDraftNetwork>(violation.reason)
        assertEquals(Network.MAINNET, reason.draftNetwork)
    }

    @Test
    fun signTestnetFixtureTransaction_testnetDraftDeclaredMainnet_isSigningScopeViolationBeforeMnemonicParse() {
        val result = ReadOnlyWallet.signTestnetFixtureTransaction(
            unusedWords,
            Network.MAINNET,
            fixtureDraft(Network.TESTNET),
        )

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val violation = assertIs<WalletError.SigningScopeViolation>(err.error)
        val reason = assertIs<SigningScopeViolationReason.DeclaredNetworkMismatch>(violation.reason)
        assertEquals(Network.MAINNET, reason.declared)
        assertEquals(Network.TESTNET, reason.draftNetwork)
    }

    @Test
    fun signTestnetFixtureTransaction_unsupportedScope_isSigningScopeViolationBeforeMnemonicParse() {
        val result = ReadOnlyWallet.signTestnetFixtureTransaction(
            unusedWords,
            Network.TESTNET,
            fixtureDraft().withUnsupportedScopeForPolicyTest(),
        )

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val violation = assertIs<WalletError.SigningScopeViolation>(err.error)
        assertIs<SigningScopeViolationReason.UnsupportedDraftScope>(violation.reason)
    }

    @Test
    fun signTestnetFixtureTransaction_incompatibleShape_isSigningScopeViolationBeforeMnemonicParse() {
        val result = ReadOnlyWallet.signTestnetFixtureTransaction(
            unusedWords,
            Network.TESTNET,
            fixtureDraft().withIncompatibleShapeForPolicyTest(),
        )

        val err = assertIs<KardanoResult.Err<WalletError>>(result)
        val violation = assertIs<WalletError.SigningScopeViolation>(err.error)
        assertIs<SigningScopeViolationReason.UnsupportedDraftShape>(violation.reason)
    }
}
