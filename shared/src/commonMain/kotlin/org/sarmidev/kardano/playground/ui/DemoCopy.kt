package org.sarmidev.kardano.playground.ui

import org.sarmidev.kardano.playground.mvi.PlaygroundStep

/**
 * All plain-language copy for the guided Playground demo (Block 1.12-pre-e), gathered into one
 * data-driven table so the exact wording is reviewable in a single file and assertable by
 * `DemoCopyTest` — rather than scattered across composables.
 *
 * Every string reachable from [welcome], [chrome] (excluding [Chrome.advanced]), [steps], and
 * [summary] is **primary-facing**: written for a first-time viewer with no Cardano knowledge, and
 * deliberately free of protocol jargon (no "UTxO", "CBOR", "witness", "lovelace", "Bech32",
 * "Blockfrost", or "mainnet" — see [primaryFacingStrings] and `DemoCopyTest`). Jargon is
 * confined to [Chrome.advanced] (the collapsed "Advanced: connect to a test network" disclosure)
 * and to the per-step "Technical details" content built directly in the UI layer from
 * [org.sarmidev.kardano.playground.PlaygroundPresenter]'s existing `LabeledRow`s, which this
 * object does not hold.
 *
 * This file carries no SDK semantics: it is pure display text, matched against `*Presentation`
 * outcomes and [org.sarmidev.kardano.playground.mvi.PlaygroundDemoFlow] results only in the UI
 * layer.
 */
internal object DemoCopy {

    // -----------------------------------------------------------------------
    // Welcome screen
    // -----------------------------------------------------------------------

    object Welcome {
        const val BADGE: String = "Offline demo"
        const val TITLE: String = "Kardano SDK"
        const val SUBTITLE: String = "A guided demo of what this Cardano toolkit does for your app."
        const val INTRO: String = "This demo runs a complete payment from start to finish, using " +
            "a built-in test wallet and test money. Nothing here touches real funds, and by " +
            "default nothing leaves this device."
        const val PREVIEW_HEADING: String = "What you'll see"
        val PREVIEW_STEPS: List<String> = listOf(
            "Create a test wallet — the app makes a wallet and works out its address.",
            "Check its test money — we look up what that wallet holds.",
            "Prepare a test payment — the app puts a small payment together.",
            "Approve it on this device — the payment is approved locally, still unsent.",
            "Try to send it — we attempt delivery and tell you exactly what happened.",
        )
        const val REASSURANCE: String = "You don't need any Cardano knowledge to follow along. " +
            "Each step explains itself, and the technical detail is one tap away if you want it."
        const val START_BUTTON: String = "Start the demo"
        const val ABOUT_LINK: String = "What is Kardano SDK?"
        const val ROADMAP_LINK: String = "Roadmap"

        /** `"Running in demo mode — offline, with built-in test data. Running on {platformLabel}."` */
        fun footer(platformLabel: String): String =
            "Running in demo mode — offline, with built-in test data. Running on $platformLabel."
    }

    // -----------------------------------------------------------------------
    // Demo screen chrome (progress, recap strip, buttons, Advanced disclosure)
    // -----------------------------------------------------------------------

    object Chrome {
        /** `"Step {n} of 5"`. */
        fun progress(stepNumber: Int, stepCount: Int): String = "Step $stepNumber of $stepCount"

        /** `"{n}. {doneLabel}"` for one entry in the finished-steps recap strip. */
        fun recapEntry(stepNumber: Int, doneLabel: String): String = "$stepNumber. $doneLabel"

        const val BACK_BUTTON: String = "Back"
        const val START_OVER_BUTTON: String = "Start over"
        const val CONTINUE_BUTTON: String = "Continue"
        const val CONTINUE_LAST_STEP_BUTTON: String = "See the summary"

        object Advanced {
            const val DISCLOSURE_LABEL: String = "Advanced: connect to a test network"
            const val DISCLOSURE_LABEL_EXPANDED: String = "Hide advanced options"
            const val BODY: String = "By default this demo runs offline with built-in test " +
                "data. You can instead point it at Cardano's public preprod test network using " +
                "your own Blockfrost preprod project id. Test funds only — this demo never " +
                "uses mainnet."
            const val SWITCH_LABEL: String = "Use the preprod test network"
            const val FIELD_LABEL: String = "Blockfrost preprod project id"
            const val FIELD_HELPER: String = "Kept in memory for this session only. Never " +
                "shown, saved, or logged."
            const val CONFIGURATION_REQUIRED: String =
                "Test network not connected — enter a project id. Demo mode is still active."
            const val ACTIVE_LIVE: String = "Live test network — real requests, test funds only."
            const val ACTIVE_MOCK: String = "Demo mode — offline, built-in test data, nothing is sent."
        }
    }

    // -----------------------------------------------------------------------
    // Per-step copy
    // -----------------------------------------------------------------------

    /**
     * The static (non-templated) copy for one guided-demo step. Templated result text (the
     * headline/detail that depends on a runtime value, such as a shortened address or an ADA
     * amount) lives in the `*headline`/`*detail` functions below instead, grouped by step.
     */
    data class StepCopy(
        val title: String,
        val why: String,
        val actionLabel: String,
        val workingLabel: String,
        val statusNotStarted: String,
        val statusWorking: String,
        val statusDone: String,
        val statusInfo: String,
        val statusError: String,
        val doneHeadline: String,
        val errorHeadline: String,
        val guidance: String,
    )

    val steps: Map<PlaygroundStep, StepCopy> = mapOf(
        PlaygroundStep.WALLET to StepCopy(
            title = "Create a test wallet",
            why = "Every payment starts with a wallet. The SDK builds one from a built-in test " +
                "phrase and works out the address it can receive at.",
            actionLabel = "Create the test wallet",
            workingLabel = "Creating the wallet…",
            statusNotStarted = "Not started",
            statusWorking = "Creating…",
            statusDone = "Ready",
            statusInfo = "Ready",
            statusError = "Didn't work",
            doneHeadline = "Test wallet ready",
            errorHeadline = "The test wallet couldn't be created.",
            guidance = "Next, we'll check what this test wallet holds.",
        ),
        PlaygroundStep.FUNDS to StepCopy(
            title = "Check its test money",
            why = "Before sending anything, the SDK asks where the wallet's money is. In demo " +
                "mode that answer comes from built-in test data, with no network request.",
            actionLabel = "Check the balance",
            workingLabel = "Checking the balance…",
            statusNotStarted = "Not started",
            statusWorking = "Checking…",
            statusDone = "Found",
            statusInfo = "Found",
            statusError = "Didn't work",
            doneHeadline = "", // templated — see fundsDoneHeadline
            errorHeadline = "The balance couldn't be read.",
            guidance = "Next, we'll put a small test payment together.",
        ),
        PlaygroundStep.BUILD to StepCopy(
            title = "Prepare a test payment",
            why = "The SDK assembles the payment: which of the wallet's money to spend, where " +
                "it goes, what the network charges, and what comes back as change. Nothing is " +
                "approved or sent yet.",
            actionLabel = "Prepare the payment",
            workingLabel = "Preparing the payment…",
            statusNotStarted = "Not started",
            statusWorking = "Preparing…",
            statusDone = "Ready",
            statusInfo = "Ready",
            statusError = "Didn't work",
            doneHeadline = "", // templated — see buildDoneHeadline
            errorHeadline = "The payment couldn't be prepared.",
            guidance = "Next, you'll approve this payment on the device.",
        ),
        PlaygroundStep.SIGN to StepCopy(
            title = "Approve it on this device",
            why = "The wallet approves the payment with its own key, right here on the device. " +
                "The approval never leaves the device, and the payment still hasn't been sent.",
            actionLabel = "Approve the payment",
            workingLabel = "Approving…",
            statusNotStarted = "Not started",
            statusWorking = "Approving…",
            statusDone = "Approved",
            statusInfo = "Approved",
            statusError = "Didn't work",
            doneHeadline = "Payment approved on this device.",
            errorHeadline = "The payment couldn't be approved.",
            guidance = "Next, we'll try to send it.",
        ),
        PlaygroundStep.SUBMIT to StepCopy(
            title = "Try to send it",
            why = "The last step hands the approved payment to a network service. In demo mode " +
                "there is no network involved, so the SDK will say it can't send — instead of " +
                "pretending it did.",
            actionLabel = "Send the payment",
            workingLabel = "Sending…",
            statusNotStarted = "Not started",
            statusWorking = "Sending…",
            statusDone = "Sent",
            statusInfo = "Stopped on purpose",
            statusError = "Didn't work",
            doneHeadline = "", // templated — see submitLiveSuccessHeadline / submitMockHeadline
            errorHeadline = "The network didn't accept the payment.",
            guidance = "That's the whole flow — let's recap what the SDK did.",
        ),
    )

    // --- Templated result text ---

    /** `"Test address: {shortAddress} — press and hold to copy."` */
    fun walletDoneDetail(shortAddress: String): String =
        "Test address: $shortAddress — press and hold to copy."

    /** `"This wallet holds {ada} of test money."` */
    fun fundsDoneHeadline(ada: String): String = "This wallet holds $ada of test money."

    fun fundsDoneDetail(hasFunds: Boolean): String = if (hasFunds) {
        "That's enough for the demo payment."
    } else {
        "There's nothing to spend yet."
    }

    const val FUNDS_ZERO_BALANCE_GUIDANCE_LIVE: String =
        "Send test ADA to the address above from a public preprod faucet, then check again."

    /** `"Payment prepared: {paymentAda} to a test address."` */
    fun buildDoneHeadline(paymentAda: String): String = "Payment prepared: $paymentAda to a test address."

    /** `"Network cost {feeAda} · {changeAda} comes back to this wallet."` */
    fun buildDoneDetail(feeAda: String, changeAda: String?): String = if (changeAda != null) {
        "Network cost $feeAda · $changeAda comes back to this wallet."
    } else {
        "Network cost $feeAda."
    }

    const val SIGN_DONE_DETAIL: String =
        "It now has a reference id and is ready to send. Nothing has been sent yet."

    const val SUBMIT_MOCK_HEADLINE: String = "Nothing was sent — and that's the honest answer."
    const val SUBMIT_MOCK_DETAIL: String = "This demo runs offline, so there is no network to " +
        "send to. The SDK reported that its demo provider does not submit payments, rather " +
        "than faking a success. Everything up to this point really happened on this device."
    const val SUBMIT_LIVE_SUCCESS_HEADLINE: String = "Sent to Cardano's preprod test network."

    /** `"Reference id {shortId} — press and hold to copy. Test network and test funds only."` */
    fun submitLiveSuccessDetail(shortId: String): String =
        "Reference id $shortId — press and hold to copy. Test network and test funds only."

    // -----------------------------------------------------------------------
    // Summary screen
    // -----------------------------------------------------------------------

    object Summary {
        const val TITLE: String = "That's the whole flow"
        const val INTRO: String = "In five steps, the SDK did all of this from one shared " +
            "Kotlin codebase:"
        val RECAP_LINES_BASE: List<String> = listOf(
            "Created a test wallet and worked out its address.",
            "Looked up what that wallet holds.",
            "Prepared a test payment, including the network cost and the change.",
            "Approved the payment on this device, with the key never leaving it.",
        )
        const val RECAP_LINE_SUBMIT_MOCK: String =
            "Stopped before sending, because the offline demo has no network to send to."
        const val RECAP_LINE_SUBMIT_LIVE: String = "Sent it to the preprod test network."

        /** The five recap lines, the last one chosen for [wasLiveSubmission]. */
        fun recapLines(wasLiveSubmission: Boolean): List<String> = RECAP_LINES_BASE + listOf(
            if (wasLiveSubmission) RECAP_LINE_SUBMIT_LIVE else RECAP_LINE_SUBMIT_MOCK,
        )

        // Deliberately narrower and more technical than the rest of this screen: a scope
        // disclaimer needs to name the exact boundaries (including "mainnet") to be honest
        // about them, the same way Chrome.Advanced is allowed to name "Blockfrost" — see
        // DemoCopyTest and primaryFacingStrings()'s KDoc.
        const val SCOPE_HEADING: String = "What this demo is not"
        val SCOPE_LINES: List<String> = listOf(
            "Test money only — never real funds.",
            "One built-in test wallet — you can't bring your own.",
            "ADA payments only — no tokens, no smart contracts.",
            "Test networks only — this demo never touches mainnet.",
            "Phase 1, experimental, pre-alpha.",
        )
        const val RUN_AGAIN_BUTTON: String = "Run the demo again"
        const val ABOUT_LINK: String = "What can the SDK do?"
        const val ROADMAP_LINK: String = "Roadmap"
    }

    // -----------------------------------------------------------------------
    // About screen (re-copied capabilities)
    // -----------------------------------------------------------------------

    object About {
        data class Capability(val title: String, val description: String)

        val CAPABILITIES: List<Capability> = listOf(
            Capability(
                "Read and check addresses",
                "Confirm a Cardano address is well-formed before your app uses it.",
            ),
            Capability(
                "Create a test wallet",
                "Build a wallet from a recovery phrase and derive its addresses.",
            ),
            Capability(
                "Look up balances",
                "Ask a provider what an address holds, through one interface.",
            ),
            Capability(
                "Prepare ADA payments",
                "Assemble a payment with the amount, the network cost, and the change.",
            ),
            Capability(
                "Approve and send",
                "Approve on the device, then hand it to a network service.",
            ),
        )
        const val BACK_TO_DEMO: String = "Back to the demo"
    }

    // -----------------------------------------------------------------------
    // For DemoCopyTest: every primary-facing (non-Advanced, non-technical) string
    // -----------------------------------------------------------------------

    /**
     * Every string a first-time viewer sees outside the collapsed Advanced disclosure, the
     * per-step Technical details, and the Summary's scope-boundary disclaimer
     * ([Summary.SCOPE_LINES]) — used by `DemoCopyTest` to assert none of it leaks protocol
     * jargon or a banned word. [Chrome.Advanced] and [Summary.SCOPE_LINES] are both excluded on
     * the same basis: each is a deliberately narrower, more technical disclaimer that must name
     * its exact boundary (a live test network's "Blockfrost" project id; the scope list's
     * "mainnet") to stay honest, not a jargon slip in the demo's main narrative.
     */
    fun primaryFacingStrings(): List<String> = buildList {
        add(Welcome.BADGE)
        add(Welcome.TITLE)
        add(Welcome.SUBTITLE)
        add(Welcome.INTRO)
        add(Welcome.PREVIEW_HEADING)
        addAll(Welcome.PREVIEW_STEPS)
        add(Welcome.REASSURANCE)
        add(Welcome.START_BUTTON)
        add(Welcome.ABOUT_LINK)
        add(Welcome.ROADMAP_LINK)
        add(Welcome.footer("Android"))

        add(Chrome.BACK_BUTTON)
        add(Chrome.START_OVER_BUTTON)
        add(Chrome.CONTINUE_BUTTON)
        add(Chrome.CONTINUE_LAST_STEP_BUTTON)

        steps.values.forEach { copy ->
            add(copy.title)
            add(copy.why)
            add(copy.actionLabel)
            add(copy.workingLabel)
            add(copy.statusNotStarted)
            add(copy.statusWorking)
            add(copy.statusDone)
            add(copy.statusInfo)
            add(copy.statusError)
            if (copy.doneHeadline.isNotEmpty()) add(copy.doneHeadline)
            add(copy.errorHeadline)
            add(copy.guidance)
        }
        add(walletDoneDetail("addr_test1qxy…s68faae"))
        add(fundsDoneHeadline("5 ADA"))
        add(fundsDoneDetail(hasFunds = true))
        add(fundsDoneDetail(hasFunds = false))
        add(FUNDS_ZERO_BALANCE_GUIDANCE_LIVE)
        add(buildDoneHeadline("2 ADA"))
        add(buildDoneDetail("0.17 ADA", "10.83 ADA"))
        add(buildDoneDetail("0.17 ADA", null))
        add(SIGN_DONE_DETAIL)
        add(SUBMIT_MOCK_HEADLINE)
        add(SUBMIT_MOCK_DETAIL)
        add(SUBMIT_LIVE_SUCCESS_HEADLINE)
        add(submitLiveSuccessDetail("331a79e…42416"))

        add(Summary.TITLE)
        add(Summary.INTRO)
        addAll(Summary.recapLines(wasLiveSubmission = true))
        addAll(Summary.recapLines(wasLiveSubmission = false))
        add(Summary.SCOPE_HEADING)
        add(Summary.RUN_AGAIN_BUTTON)
        add(Summary.ABOUT_LINK)
        add(Summary.ROADMAP_LINK)

        About.CAPABILITIES.forEach {
            add(it.title)
            add(it.description)
        }
        add(About.BACK_TO_DEMO)
    }
}
