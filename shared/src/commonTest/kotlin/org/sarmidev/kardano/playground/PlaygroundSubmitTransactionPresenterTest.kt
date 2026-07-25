package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.provider.SubmitError
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Native-free unit tests for [PlaygroundPresenter]'s submit-transaction checkpoint (Block
 * 1.11c) result-mapping path.
 *
 * [PlaygroundPresenter.mapSubmitTransactionResult] and [PlaygroundPresenter.presentSubmitError]
 * are both non-suspend and native-free. Unlike [PlaygroundPresenter.mapSignedTransactionResult]
 * (whose `Ok` branch needs a real `WalletSignedTransaction`, unreachable without native
 * signing), [mapSubmitTransactionResult] takes a plain [TxHash] for the locally-signed id — a
 * `:core` value constructible from any 32 bytes via [TxHash.of], no native call needed — so
 * both its `Ok` (accepted-id) and `Err` (every [SubmitError] variant) branches are fully
 * covered here, on every target including `:shared:testAndroidHostTest`.
 *
 * The draft-building and signing failures [PlaygroundPresenter.presentSubmitTransaction] can
 * also report are the exact same [org.sarmidev.kardano.tx.TxBuildError]/
 * [org.sarmidev.kardano.wallet.WalletError] variants [PlaygroundTransactionDraftPresenterTest]
 * and [PlaygroundSignedTransactionPresenterTest] already cover through the shared
 * `presentTxBuildError`/`presentWalletError` mappers — not duplicated here.
 *
 * The end-to-end success path (an actual accepted submission) can only come from a live
 * Blockfrost preprod call, which is out of scope for automated tests; the honest "mock never
 * fakes success" end-to-end path is covered instead by
 * [PlaygroundSubmitTransactionDesktopTest] (`jvmTest`-only).
 */
class PlaygroundSubmitTransactionPresenterTest {

    private fun txHash(byte: Int): TxHash =
        requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { byte.toByte() }).getOrNull())

    // --- mapSubmitTransactionResult: Ok (native-free, TxHash needs no native call) ---

    @Test
    fun mapSubmitTransactionResult_matchingIds_reportsMatchAndSubmittedLabel() {
        val localId = txHash(0x11)
        val acceptedId = txHash(0x11)

        val presentation = PlaygroundPresenter.mapSubmitTransactionResult(
            localId,
            KardanoResult.Ok(acceptedId),
        )

        val success = assertIs<SubmitTransactionPresentation.Success>(presentation)
        val rowByLabel = success.rows.associate { it.label to it.value }
        assertEquals("yes", rowByLabel["Ids match"])
        assertEquals(
            "submitted to preprod — testnet-only, test fixture, no real funds",
            rowByLabel["Status"],
        )
        assertTrue(!rowByLabel.containsKey("Note"), "no mismatch note expected when ids match")
    }

    @Test
    fun mapSubmitTransactionResult_differingIds_reportsMismatchNote() {
        val localId = txHash(0x11)
        val acceptedId = txHash(0x22)

        val presentation = PlaygroundPresenter.mapSubmitTransactionResult(
            localId,
            KardanoResult.Ok(acceptedId),
        )

        val success = assertIs<SubmitTransactionPresentation.Success>(presentation)
        val rowByLabel = success.rows.associate { it.label to it.value }
        assertEquals("no", rowByLabel["Ids match"])
        assertTrue(rowByLabel.containsKey("Note"), "expected a mismatch note row")
    }

    @Test
    fun mapSubmitTransactionResult_err_delegatesToPresentSubmitError() {
        val presentation = PlaygroundPresenter.mapSubmitTransactionResult(
            txHash(0x11),
            KardanoResult.Err(SubmitError.RateLimited),
        )

        val failure = assertIs<SubmitTransactionPresentation.Failure>(presentation)
        assertTrue(failure.message.contains("rate", ignoreCase = true), "got: ${failure.message}")
    }

    // --- presentSubmitError: every SubmitError variant maps to a distinguishable message ---

    @Test
    fun presentSubmitError_submissionNotSupported_mentionsMockAndLiveOption() {
        val msg = PlaygroundPresenter.presentSubmitError(SubmitError.SubmissionNotSupported)
        assertTrue(msg.contains("not support", ignoreCase = true), "got: $msg")
        assertTrue(msg.contains("Blockfrost"), "got: $msg")
    }

    @Test
    fun presentSubmitError_emptyTransaction_mentionsEmpty() {
        val msg = PlaygroundPresenter.presentSubmitError(SubmitError.EmptyTransaction)
        assertTrue(msg.contains("empty", ignoreCase = true), "got: $msg")
    }

    @Test
    fun presentSubmitError_rejected_containsCodeAndDetail() {
        val msg = PlaygroundPresenter.presentSubmitError(SubmitError.Rejected(400, "bad body"))
        assertTrue(msg.contains("400"), "got: $msg")
        assertTrue(msg.contains("bad body"), "got: $msg")
    }

    @Test
    fun presentSubmitError_transport_containsMessage() {
        val msg = PlaygroundPresenter.presentSubmitError(SubmitError.Transport("connection reset"))
        assertTrue(msg.contains("connection reset"), "got: $msg")
    }

    @Test
    fun presentSubmitError_remoteStatusWithDetail_containsCodeAndDetail() {
        val msg = PlaygroundPresenter.presentSubmitError(SubmitError.RemoteStatus(403, "forbidden"))
        assertTrue(msg.contains("403"), "got: $msg")
        assertTrue(msg.contains("forbidden"), "got: $msg")
    }

    @Test
    fun presentSubmitError_remoteStatusWithoutDetail_containsCodeOnly() {
        val msg = PlaygroundPresenter.presentSubmitError(SubmitError.RemoteStatus(500, null))
        assertTrue(msg.contains("500"), "got: $msg")
    }

    @Test
    fun presentSubmitError_rateLimited_hasDescription() {
        val msg = PlaygroundPresenter.presentSubmitError(SubmitError.RateLimited)
        assertTrue(msg.contains("rate", ignoreCase = true), "got: $msg")
    }

    @Test
    fun presentSubmitError_deserialization_containsDetail() {
        val msg = PlaygroundPresenter.presentSubmitError(SubmitError.Deserialization("bad hex"))
        assertTrue(msg.contains("bad hex"), "got: $msg")
    }

    @Test
    fun presentSubmitError_unknown_hasDescription() {
        val msg = PlaygroundPresenter.presentSubmitError(SubmitError.Unknown)
        assertTrue(msg.contains("unknown", ignoreCase = true), "got: $msg")
    }
}
