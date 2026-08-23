package org.sarmidev.kardano.playground.ui

import org.sarmidev.kardano.playground.mvi.PlaygroundStep
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Unit tests for [DemoCopy] (Block 1.12-pre-e). */
class DemoCopyTest {

    private val jargonDenyList = listOf(
        "UTxO", "CBOR", "witness", "lovelace", "Bech32", "Blockfrost", "mainnet",
    )

    private val bannedWords = listOf(
        "secure", "safe", "hardened", "audited", "production-ready", "guaranteed",
        "cryptographically safe",
    )

    @Test
    fun everyPlaygroundStep_hasACompleteCopyEntry() {
        for (step in PlaygroundStep.entries) {
            val copy = DemoCopy.steps[step]
            requireNotNull(copy) { "missing DemoCopy.steps entry for $step" }
            assertTrue(copy.title.isNotBlank(), "$step: blank title")
            assertTrue(copy.why.isNotBlank(), "$step: blank why")
            assertTrue(copy.actionLabel.isNotBlank(), "$step: blank actionLabel")
            assertTrue(copy.workingLabel.isNotBlank(), "$step: blank workingLabel")
            assertTrue(copy.statusNotStarted.isNotBlank(), "$step: blank statusNotStarted")
            assertTrue(copy.statusWorking.isNotBlank(), "$step: blank statusWorking")
            assertTrue(copy.statusDone.isNotBlank(), "$step: blank statusDone")
            assertTrue(copy.statusInfo.isNotBlank(), "$step: blank statusInfo")
            assertTrue(copy.statusError.isNotBlank(), "$step: blank statusError")
            assertTrue(copy.errorHeadline.isNotBlank(), "$step: blank errorHeadline")
            assertTrue(copy.guidance.isNotBlank(), "$step: blank guidance")
        }
    }

    @Test
    fun everyButtonLabel_isNonBlank() {
        val buttons = listOf(
            DemoCopy.Welcome.START_BUTTON,
            DemoCopy.Welcome.ABOUT_LINK,
            DemoCopy.Welcome.ROADMAP_LINK,
            DemoCopy.Chrome.BACK_BUTTON,
            DemoCopy.Chrome.START_OVER_BUTTON,
            DemoCopy.Chrome.CONTINUE_BUTTON,
            DemoCopy.Chrome.CONTINUE_LAST_STEP_BUTTON,
            DemoCopy.Summary.RUN_AGAIN_BUTTON,
            DemoCopy.Summary.ABOUT_LINK,
            DemoCopy.Summary.ROADMAP_LINK,
            DemoCopy.About.BACK_TO_DEMO,
        )
        buttons.forEach { assertTrue(it.isNotBlank(), "found a blank button label") }
        DemoCopy.steps.values.forEach { assertTrue(it.actionLabel.isNotBlank()) }
    }

    @Test
    fun summary_hasExactlyFiveRecapLines() {
        assertEquals(5, DemoCopy.Summary.recapLines(wasLiveSubmission = true).size)
        assertEquals(5, DemoCopy.Summary.recapLines(wasLiveSubmission = false).size)
    }

    @Test
    fun summary_recapLastLine_dependsOnSubmissionMode() {
        val mock = DemoCopy.Summary.recapLines(wasLiveSubmission = false)
        val live = DemoCopy.Summary.recapLines(wasLiveSubmission = true)

        assertEquals(DemoCopy.Summary.RECAP_LINE_SUBMIT_MOCK, mock.last())
        assertEquals(DemoCopy.Summary.RECAP_LINE_SUBMIT_LIVE, live.last())
        assertEquals(mock.dropLast(1), live.dropLast(1), "the first four recap lines don't depend on the mode")
    }

    @Test
    fun primaryFacingStrings_containNoJargonFromTheDenyList() {
        DemoCopy.primaryFacingStrings().forEach { text ->
            jargonDenyList.forEach { term ->
                assertFalse(
                    text.contains(term, ignoreCase = true),
                    "primary-facing copy contains jargon term \"$term\": \"$text\"",
                )
            }
        }
    }

    @Test
    fun primaryFacingStrings_containNoBannedWords() {
        DemoCopy.primaryFacingStrings().forEach { text ->
            bannedWords.forEach { word ->
                assertFalse(
                    text.contains(word, ignoreCase = true),
                    "primary-facing copy contains a banned word \"$word\": \"$text\"",
                )
            }
        }
    }

    @Test
    fun advancedDisclosure_isAllowedToNameBlockfrostAndMainnet() {
        // The Advanced disclosure and the Summary scope disclaimer are the two documented
        // exceptions (see DemoCopy.primaryFacingStrings KDoc) — this pins that they still say
        // what they need to say.
        assertTrue(DemoCopy.Chrome.Advanced.BODY.contains("Blockfrost"))
        assertTrue(DemoCopy.Chrome.Advanced.BODY.contains("mainnet"))
        assertTrue(DemoCopy.Summary.SCOPE_LINES.any { it.contains("mainnet") })
    }
}
