package org.sarmidev.kardano.playground

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import org.sarmidev.kardano.Greeting
import org.sarmidev.kardano.playground.mvi.PlaygroundIntent
import org.sarmidev.kardano.playground.mvi.PlaygroundSection
import org.sarmidev.kardano.playground.mvi.PlaygroundViewModel
import org.sarmidev.kardano.playground.ui.DemoStepSection
import org.sarmidev.kardano.playground.ui.KardanoPlaygroundTheme
import org.sarmidev.kardano.playground.ui.PlaygroundLanding
import org.sarmidev.kardano.playground.ui.RoadmapScreen
import org.sarmidev.kardano.playground.ui.SummarySection
import org.sarmidev.kardano.playground.ui.WelcomeSection

/**
 * The SDK Playground screen: a small developer-facing demo of the Kardano SDK MVP, restructured
 * into an MVI architecture in Block 1.12-pre-a, given its guided visual/UX presentation in Block
 * 1.12-pre-b, fronted by a landing/overview area in Block 1.12-pre-c, and rebuilt into a linear,
 * single-step-at-a-time guided story in Block 1.12-pre-e.
 *
 * This composable is a pure renderer: it reads [PlaygroundState] from [PlaygroundViewModel] and
 * dispatches [PlaygroundIntent]s for every user action — it computes nothing itself. All
 * SDK-calling logic lives in [PlaygroundViewModel], its use cases (`playground/domain`), and its
 * provider factory (`playground/data`), which call [PlaygroundPresenter]; the UI package
 * (`playground/ui`) holds only presentation-shell composables (hero, step card, demo chrome,
 * badges, diagnostics), none of which reach an SDK API.
 *
 * ### The guided journey (Block 1.12-pre-e)
 *
 * [PlaygroundState.section] drives a **linear** journey, not a tab row: [PlaygroundSection.WELCOME]
 * (the default landing screen — what the demo will do, a five-step preview, one *Start the demo*
 * call to action) leads into [PlaygroundSection.DEMO] ([DemoStepSection] — one guided step at a
 * time, driven by [PlaygroundState.demoStep] and gated by
 * [org.sarmidev.kardano.playground.mvi.PlaygroundDemoFlow]), which ends at
 * [PlaygroundSection.SUMMARY] ([SummarySection] — a plain-language recap plus an honest scope
 * list). [PlaygroundSection.ABOUT] ([PlaygroundLanding] — capabilities, code examples, and the
 * relocated [org.sarmidev.kardano.playground.ui.DiagnosticsSection] developer tools) and
 * [PlaygroundSection.ROADMAP] ([RoadmapScreen]) are secondary screens reachable from Welcome and
 * Summary, each with a control back into the demo.
 *
 * The five guided steps themselves — **Wallet → Funds → Build → Sign → Submit** — exercise
 * [TestWalletFixture]'s cited test-only mnemonic (never a real mnemonic, never real funds)
 * against whichever provider is active (an in-memory mock by default, or live Blockfrost preprod
 * once configured via the Demo screen's collapsed "Advanced" disclosure), building a minimal
 * unsigned ADA-only transaction draft, signing it, and finally attempting to submit it. Testnet/
 * preprod only, everywhere; no mainnet, no real mnemonic/private-key display, and no full
 * (untruncated) CBOR display — see [PlaygroundState] and [PlaygroundPresenter] for the exact
 * display rules each `*Presentation` type follows.
 *
 * The root container (Block 1.12-pre-b polish) paints a subtle theme-derived gradient — from
 * [MaterialTheme.colorScheme]'s `surface` into its `background`, continuing the tone the hero
 * card's own gradient ends on — instead of the platform's default (white) window background, and
 * applies [Modifier.safeDrawingPadding] so content never starts under the status bar and the
 * controls at the bottom are never hidden behind the navigation bar. [Modifier.safeDrawingPadding]
 * is a Compose-Multiplatform-common API (`expect`/`actual` per target); no Android-specific inset
 * code was added here.
 *
 * This is sample/diagnostic code in `:shared`. It is not part of the SDK public API.
 */
@Composable
internal fun PlaygroundScreen() {
    val platformLabel = remember { Greeting().greet() }
    val viewModel = viewModel { PlaygroundViewModel() }
    val state by viewModel.state.collectAsStateWithLifecycle()
    val dispatch: (PlaygroundIntent) -> Unit = viewModel::dispatch

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(MaterialTheme.colorScheme.surface, MaterialTheme.colorScheme.background),
                ),
            )
            .safeDrawingPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        when (state.section) {
            PlaygroundSection.WELCOME -> WelcomeSection(
                platformLabel = platformLabel,
                onStartDemo = { dispatch(PlaygroundIntent.NavigateToDemo) },
                onOpenAbout = { dispatch(PlaygroundIntent.NavigateToAbout) },
                onOpenRoadmap = { dispatch(PlaygroundIntent.NavigateToRoadmap) },
            )

            PlaygroundSection.DEMO -> DemoStepSection(state, dispatch)

            PlaygroundSection.SUMMARY -> SummarySection(
                state = state,
                onRunAgain = { dispatch(PlaygroundIntent.ResetFlow) },
                onOpenAbout = { dispatch(PlaygroundIntent.NavigateToAbout) },
                onOpenRoadmap = { dispatch(PlaygroundIntent.NavigateToRoadmap) },
            )

            PlaygroundSection.ABOUT -> PlaygroundLanding(
                state = state,
                codeExamplesExpanded = state.codeExamplesExpanded,
                onToggleCodeExamples = { dispatch(PlaygroundIntent.ToggleCodeExamples) },
                onOpenRoadmap = { dispatch(PlaygroundIntent.NavigateToRoadmap) },
                onBackToDemo = { dispatch(PlaygroundIntent.NavigateToDemo) },
                dispatch = dispatch,
            )

            PlaygroundSection.ROADMAP -> RoadmapScreen(
                selected = state.selectedRoadmapPhase,
                onSelect = { dispatch(PlaygroundIntent.SelectRoadmapPhase(it)) },
                onBack = { dispatch(PlaygroundIntent.NavigateToDemo) },
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Preview
// ---------------------------------------------------------------------------

@Preview
@Composable
private fun PlaygroundScreenPreview() {
    KardanoPlaygroundTheme {
        PlaygroundScreen()
    }
}
