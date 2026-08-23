package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.crypto.signing.SigningError
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import org.sarmidev.kardano.tx.TxBuildError
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.tx.TransactionDraftScope
import org.sarmidev.kardano.wallet.SigningScopeViolationReason
import org.sarmidev.kardano.wallet.WalletError
import org.sarmidev.kardano.wallet.WalletSignedTransaction
import kotlin.test.Test
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Native-free unit tests for [PlaygroundPresenter]'s signed-transaction checkpoint (Block
 * 1.10c) error-mapping path.
 *
 * [PlaygroundPresenter.mapSignedTransactionResult] and [PlaygroundPresenter.presentSigningError]
 * are both non-suspend and native-free: they format an already-constructed [WalletError]
 * directly, without restoring a mnemonic (which reaches `:crypto`'s native derivation/signing
 * backend) or querying a provider. That means these cases run on every target, including
 * `:shared:testAndroidHostTest` — mirroring [PlaygroundTransactionDraftPresenterTest]'s KDoc for
 * the same native-backend constraint.
 *
 * [mapSignedTransactionResult]'s `Ok` branch needs a real [WalletSignedTransaction], whose
 * constructor is `:wallet`-internal and only reachable by actually signing (native code) —
 * that end-to-end success path is covered instead by
 * [PlaygroundSignedTransactionDesktopTest] (`jvmTest`-only), the same split
 * [PlaygroundTransactionDraftDesktopTest] already uses for the unsigned draft checkpoint.
 */
class PlaygroundSignedTransactionPresenterTest {

    // --- mapSignedTransactionResult: Err (wallet error presentation) ---

    @Test
    fun signingError_producesFailureMentioningSigning() {
        val result: KardanoResult<WalletSignedTransaction, WalletError> =
            KardanoResult.Err(WalletError.Signing(SigningError.BackendFailed("boom")))

        val presentation = PlaygroundPresenter.mapSignedTransactionResult(result)

        val failure = assertIs<SignedTransactionPresentation.Failure>(presentation)
        assertTrue(failure.message.contains("Signing failed", ignoreCase = true), "got: ${failure.message}")
        assertTrue(failure.message.contains("boom"), "got: ${failure.message}")
    }

    @Test
    fun transactionAssemblyError_producesFailureMentioningAssembly() {
        val result: KardanoResult<WalletSignedTransaction, WalletError> =
            KardanoResult.Err(WalletError.TransactionAssembly(TxBuildError.EmptyWitnessSet))

        val presentation = PlaygroundPresenter.mapSignedTransactionResult(result)

        val failure = assertIs<SignedTransactionPresentation.Failure>(presentation)
        assertTrue(failure.message.contains("assembly", ignoreCase = true), "got: ${failure.message}")
    }

    // --- presentSigningError: every variant maps to a distinguishable, non-leaking message ---

    @Test
    fun presentSigningError_invalidBodyHashLength_containsExpectedAndActual() {
        val msg = PlaygroundPresenter.presentSigningError(
            SigningError.InvalidBodyHashLength(expectedBytes = 32, actualBytes = 16),
        )
        assertTrue(msg.contains("32"), "got: $msg")
        assertTrue(msg.contains("16"), "got: $msg")
    }

    @Test
    fun presentSigningError_invalidKeyMaterial_containsExpectedAndActual() {
        val msg = PlaygroundPresenter.presentSigningError(
            SigningError.InvalidKeyMaterial(expectedBytes = 96, actualBytes = 32),
        )
        assertTrue(msg.contains("96"), "got: $msg")
        assertTrue(msg.contains("32"), "got: $msg")
    }

    @Test
    fun presentSigningError_backendFailed_containsMessage() {
        val msg = PlaygroundPresenter.presentSigningError(SigningError.BackendFailed("native failure"))
        assertTrue(msg.contains("native failure"), "got: $msg")
    }

    @Test
    fun presentSigningError_signingUnavailable_hasDescription() {
        val msg = PlaygroundPresenter.presentSigningError(SigningError.SigningUnavailable)
        assertTrue(msg.contains("not available", ignoreCase = true), "got: $msg")
    }

    // --- presentWalletError: TransactionAssembly delegates to presentTxBuildError ---

    @Test
    fun presentWalletError_transactionAssembly_delegatesToTxBuildErrorMessage() {
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { 9 }).getOrNull())
        val ref = requireNotNull(UtxoRef.of(txHash, 0L).getOrNull())

        val msg = PlaygroundPresenter.presentWalletError(
            WalletError.TransactionAssembly(TxBuildError.DuplicateInput(ref)),
        )
        assertTrue(msg.contains("Duplicate", ignoreCase = true), "got: $msg")
    }

    @Test
    fun presentWalletError_signingScopeViolation_unsupportedDraftNetwork_namesNetwork() {
        val msg = PlaygroundPresenter.presentWalletError(
            WalletError.SigningScopeViolation(
                SigningScopeViolationReason.UnsupportedDraftNetwork(Network.MAINNET),
            ),
        )
        assertTrue(msg.contains("MAINNET"), "got: $msg")
        assertTrue(msg.contains("testnet", ignoreCase = true), "got: $msg")
    }

    @Test
    fun presentWalletError_signingScopeViolation_declaredNetworkMismatch_namesBoth() {
        val msg = PlaygroundPresenter.presentWalletError(
            WalletError.SigningScopeViolation(
                SigningScopeViolationReason.DeclaredNetworkMismatch(
                    declared = Network.MAINNET,
                    draftNetwork = Network.TESTNET,
                ),
            ),
        )
        assertTrue(msg.contains("MAINNET"), "got: $msg")
        assertTrue(msg.contains("TESTNET"), "got: $msg")
    }

    @Test
    fun presentWalletError_signingScopeViolation_unsupportedScope_mentionsPhase1() {
        val msg = PlaygroundPresenter.presentWalletError(
            WalletError.SigningScopeViolation(
                SigningScopeViolationReason.UnsupportedDraftScope(
                    TransactionDraftScope.Phase1AdaOnlySinglePayment,
                ),
            ),
        )
        assertTrue(msg.contains("Phase 1"), "got: $msg")
    }

    @Test
    fun presentWalletError_signingScopeViolation_unsupportedShape_includesDetail() {
        val msg = PlaygroundPresenter.presentWalletError(
            WalletError.SigningScopeViolation(
                SigningScopeViolationReason.UnsupportedDraftShape("inputs=0 outputs=3"),
            ),
        )
        assertTrue(msg.contains("inputs=0 outputs=3"), "got: $msg")
    }

    @Test
    fun presentWalletError_signingScopeViolation_unrecognizedFixture_mentionsFixture() {
        val msg = PlaygroundPresenter.presentWalletError(
            WalletError.SigningScopeViolation(
                SigningScopeViolationReason.UnrecognizedFixtureIdentity,
            ),
        )
        assertTrue(msg.contains("fixture", ignoreCase = true), "got: $msg")
    }
}
