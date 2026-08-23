# :shared

Currently the sample/UI host module. It carries the Compose Multiplatform sample UI and
builds the iOS `Shared` framework that the Xcode app consumes.

## Status

Phase 1 — pre-alpha, experimental. Not for real funds.

## Role today

- Hosts the SDK Playground (`playground/PlaygroundScreen.kt`, `playground/PlaygroundPresenter.kt`),
  introduced in Block 1.2, as the Android-facing diagnostic surface for existing `:core`/
  `:crypto`/`:wallet`/`:tx`/`:provider` SDK behavior (address parsing, Hex, CBOR, test-wallet
  derivation + address generation, read-only wallet balance, an unsigned transaction-draft
  checkpoint, a signed-but-not-submitted transaction checkpoint, and a submit-transaction
  checkpoint) and, from Block 1.3a, a read-only "Provider" section (mock by default, with an
  optional live-Blockfrost toggle added in Block 1.3b).
- Hosts `App.kt` (theme wrapper that renders `PlaygroundScreen`) and the iOS UI entry point
  (`MainViewController.kt`).
- Retains the sample glue (`Greeting.kt`, `GreetingUtil.kt`) used by `PlaygroundScreen` to
  show the platform name.
- Depends on `:core` for encoding/address SDK logic (`Address.parse`, `Address.baseAddress`,
  `Address.toBech32()`, `AddressCredential`, `Hex`, `Cbor`, `Platform`), on `:crypto` for the
  test-wallet derivation checkpoint (`Mnemonic`, `IcarusMasterKey`, `KeyDerivation`, `Hashing`
  — see "Test Wallet & Address Generation" below), on `:provider` for the read-only query
  boundary (`ChainQueryProvider`) and its in-memory mock, and, from Block 1.11a, the submit
  boundary (`TxSubmitProvider`, `SubmitError`) and its in-memory mock, on `:provider-blockfrost`
  for the live Blockfrost query provider and, from Block 1.11b, the live Blockfrost submit
  provider (`BlockfrostTxSubmitProvider`), on `:wallet` (Block 1.8b) for the read-only
  wallet-balance checkpoint (`ReadOnlyWallet`, `WalletBalance`, `WalletError` — see "Wallet
  Balance" below), and, from Block 1.9c, on `:tx` for the unsigned transaction-draft checkpoint
  (`TransactionBuilder`, `TransactionBuildRequest`, `TransactionDraft`, `TxBuildError` — see
  "Transaction Draft" below). Block 1.10c (signing) and Block 1.11c (submission) reuse these
  same `:wallet`/`:tx`/`:provider` dependencies — `ReadOnlyWallet.signTestnetFixtureTransaction`
  (renamed from `signTransaction`, 2026-08-23, ADR-0018), `WalletSignedTransaction`, and
  `TxSubmitProvider.submit` — with no new Gradle module added (see "Signed Transaction" and
  "Submit Transaction" below).
- Builds the static iOS framework named `Shared` (`baseName = "Shared"`), consumed by
  `iosApp` via `MainViewControllerKt.MainViewController()`. Swift sees ordinary Kotlin
  functions: `@RequiresOptIn` (`ExperimentalKardanoSigningScope`,
  `ExperimentalKardanoRawSigning`) does not appear as a Swift compile-time gate. Exported
  `TransactionDraft.network` / `scope` properties and runtime
  `WalletError.SigningScopeViolation` cases do cross that boundary (ADR-0019).

## Playground architecture (Block 1.12-pre-a)

Block 1.12-pre-a refactored the Playground from a single long Compose screen driving every
checkpoint through `remember`/`LaunchedEffect` state into a lightweight MVI (Model-View-Intent)
architecture, under `playground/mvi/`, `playground/domain/`, and `playground/data/`. This is an
**architecture-only** change to the sample/diagnostic code in `:shared` — it is not part of the
SDK public API, and every SDK-calling behavior each checkpoint below documents (fixture wallet,
mock/live provider selection, ADA-only filtering, error messages, submit id comparison, and so
on) is unchanged. The guided visual/UX presentation built on top of this architecture landed in
**Block 1.12-pre-b** (see "Playground visual flow" below); Block 1.12-pre-a itself kept the
existing Material3 cards/buttons/dividers style, only reordering and regrouping them.

- `playground/mvi/PlaygroundState.kt` — a single immutable `PlaygroundState` data class holding
  provider selection (mock vs. live Blockfrost preprod, the in-memory-only `project_id`), the
  five guided-flow steps' results, per-step loading flags, a `technicalDetailsExpanded` set, and
  the diagnostics tools' inputs/results. It reuses the existing `*Presentation` sealed types from
  `PlaygroundPresenter` directly (`WalletPresentation`, `WalletBalancePresentation`,
  `TransactionDraftPresentation`, `SignedTransactionPresentation`, `SubmitTransactionPresentation`,
  `AddressPresentation`, `HexPresentation`, `CborPresentation`, `ProviderUtxosPresentation`,
  `ProviderParamsPresentation`) rather than introducing a parallel display model — those types
  already carry only public, display-safe metadata (see each type's KDoc), so this state holds no
  new SDK semantics of its own. A `PlaygroundStep` enum (`WALLET`, `FUNDS`, `BUILD`, `SIGN`,
  `SUBMIT`) identifies the five guided-flow steps for the technical-details toggle.
- `playground/mvi/PlaygroundIntent.kt` — a sealed `PlaygroundIntent` covering every user action:
  provider selection (`ToggleLiveBlockfrost`, `UpdateProjectId`), the guided flow
  (`RestoreWallet`, `QueryFunds`, `BuildDraft`, `SignTransaction`, `SubmitTransaction`,
  `ResetFlow`, `ToggleTechnicalDetails`), and the diagnostics tools (address/hex/CBOR
  update-and-run pairs, the provider explorer's address field, seed-address fill, and UTxO/params
  loads).
- `playground/mvi/PlaygroundReducer.kt` — a pure, non-suspend object folding every intent that
  needs no SDK/provider call (toggles, text-field edits, seed fill, technical-details toggling,
  `ResetFlow`) directly into a new `PlaygroundState`, plus small `startXLoading`/`applyXResult`
  helpers `PlaygroundViewModel` uses around each use-case/presenter call. Being pure and
  coroutine-free, it is exercised directly and synchronously by `PlaygroundReducerTest`
  (`commonTest`, native-free — runs on every target including `:shared:testAndroidHostTest`).
  `ResetFlow` clears the five guided-flow step results (and the Wallet step's loading flag);
  provider selection, diagnostics inputs, and *completed* diagnostic results are preserved.
  In-flight diagnostic Loading values become Empty. UTxO/params request tokens increment on
  ResetFlow, each load, and (UTxOs) an actual explorer-address change.
- `playground/mvi/PlaygroundViewModel.kt` — an `androidx.lifecycle.ViewModel` (already a
  `commonMain` dependency via `libs.androidx.lifecycle.viewmodelCompose`/`-runtimeCompose`; no new
  architecture library was added) exposing `state: StateFlow<PlaygroundState>` and
  `dispatch(intent: PlaygroundIntent)`. Sync intents go through `PlaygroundReducer`; intents that
  call an SDK API run the matching use case or diagnostics presenter call — in `viewModelScope`
  where a provider call is involved — and fold the result back into state through the matching
  reducer helper. This class holds no derivation, hashing, address-generation, balance,
  coin-selection, fee/change, signing, or submission logic of its own.
- `playground/domain/PlaygroundUseCases.kt` — seven small `fun interface`s
  (`RestoreWalletUseCase`, `QueryWalletFundsUseCase`, `BuildTransactionDraftUseCase`,
  `SignTransactionUseCase`, `SubmitTransactionUseCase`, `LoadProviderUtxosUseCase`,
  `LoadProviderParamsUseCase`), each a thin, directly-injectable wrapper over the matching
  existing `PlaygroundPresenter` function (`.Default` delegates to it). They exist so
  `PlaygroundViewModel` can be unit-tested with fakes — including `NonCancellable` completions
  after Job cancellation — without reimplementing or duplicating any `:wallet`/`:tx`/`:provider`
  call (see `PlaygroundViewModelTest`, `jvmTest`).
- `playground/data/PlaygroundProviderFactory.kt` — moves the provider-selection logic (mock by
  default; live Blockfrost preprod once the toggle is on and `project_id` is non-blank) out of
  the Compose layer, so `PlaygroundViewModel` can build a `ChainQueryProvider`/`TxSubmitProvider`
  pair from `PlaygroundState` without a `remember`. Live clients are cached by the last non-blank
  id. The internal `invalidateLiveCache()` factory method drops that cache immediately and is
  invoked by `PlaygroundViewModel` on an actual project-id change and when live mode is
  disabled — not only on the next lookup. The session field lives in `PlaygroundState`; the
  factory also keeps an in-memory cache key. Neither copy is persisted or logged.
  Provider-backed results carry `PlaygroundProviderMode` (`Mock` / `LivePreprod`) plus the
  captured `flowGeneration`. Funds/Build/Sign/Submit also carry a per-operation request token
  so a repeated same-step request cannot be overwritten by a slower first call.
- `PlaygroundPresenter.kt` is **retained unchanged as the display-mapping layer** — every use
  case and every diagnostics intent still calls into it, and every existing `PlaygroundPresenter`
  test below (`PlaygroundPresenterTest`, `PlaygroundProviderPresenterTest`,
  `PlaygroundWalletPresenterTest`, `PlaygroundWalletBalancePresenterTest`,
  `PlaygroundTransactionDraftPresenterTest`, `PlaygroundSignedTransactionPresenterTest`,
  `PlaygroundSubmitTransactionPresenterTest`, and their `jvmTest` end-to-end counterparts) still
  applies unmodified.
- `PlaygroundScreen.kt` is now a renderer: it reads `PlaygroundState` from `PlaygroundViewModel`
  (via `collectAsStateWithLifecycle`) and only dispatches `PlaygroundIntent`s — it computes
  nothing itself. The screen reads top to bottom as a guided flow, **Wallet → Funds → Build →
  Sign → Submit** (restore the fixture wallet and generate its address; query its balance from
  the active provider; build a minimal unsigned ADA-only draft; sign it; submit it), each step
  with a short description and a "Details" toggle that expands its result card from a one-line
  summary to the full row list (`PlaygroundIntent.ToggleTechnicalDetails`). Below the guided flow,
  a **Diagnostics** area keeps the standalone Address Parser, Hex Decoder, CBOR Decoder, and the
  generic (arbitrary-address) Provider explorer with its seed-address buttons — tools unrelated
  to the fixture wallet, folded into the same `PlaygroundState`/`PlaygroundIntent` model rather
  than kept as separate ad hoc Compose state.

## Playground visual flow (Block 1.12-pre-b)

Block 1.12-pre-b is a **sample-app visual/UX refresh** built on the Block 1.12-pre-a MVI
foundation — it changes presentation only. It adds no SDK behavior, no SDK public API, no new
dependency, and no `:core`/`:crypto`/`:wallet`/`:tx`/`:provider`/`:provider-blockfrost` change;
`PlaygroundState`, `PlaygroundIntent`, `PlaygroundReducer`, `PlaygroundViewModel`, the use
cases, the provider factory, and `PlaygroundPresenter` are all unchanged. The screen still reads
`PlaygroundState` and dispatches `PlaygroundIntent`s — no SDK orchestration moved into the
composables.

- New `playground/ui/` package holds only presentation-shell composables (none reach an SDK
  API): `PlaygroundTheme.kt` (a Kotlin/KMP-inspired Material 3 color scheme — purple lead, blue
  secondary, orange tertiary, at restrained contrast, following the system light/dark setting),
  `PlaygroundHeader.kt` (a hero header with the "Kardano SDK" title, the "Kotlin Multiplatform
  Cardano transaction flow" subtitle, always-on `TESTNET`/`ADA-only`/provider-mode badges, and a
  `FlowStepper` that highlights completed steps), `StatusBadge.kt` (the `MOCK` / `LIVE PREPROD` /
  `TESTNET` / `ADA-only` / `SIGNED` / `SUBMITTED` badges and per-step status chips),
  `FlowStepCard.kt` (a numbered step card with title, one-line explanation, status chip, primary
  action button with an in-button spinner, key output, and a "Technical details" toggle, plus
  shared `ResultRow`/`LabeledRows`/`ErrorInline`/`LoadingInline` primitives), and
  `DiagnosticsSection.kt` (the Address Parser, Hex Decoder, CBOR Decoder, and Provider explorer
  in a visually secondary, collapsed-by-default area).
- The **hero mark is drawn entirely with Compose shapes** (a rounded-square gradient with two
  white forward chevrons) — it is intentionally not the Kotlin or Cardano logo, and **no
  external image asset is bundled**, so there is no third-party artwork license to track for this
  sample app.
- Each guided-flow step (`PlaygroundScreen.kt`) shows a title, short microcopy, its current
  status, one main action, and its key output (Wallet → generated address; Funds → balance +
  UTxO count; Build → selected inputs, fee, change; Sign → transaction id + witness count;
  Submit → accepted tx id + id-match), with the full `PlaygroundPresenter` row list kept behind
  the per-step "Technical details" toggle (`PlaygroundIntent.ToggleTechnicalDetails`). Loading is
  shown per step (an in-button spinner plus an inline "Working…"), and errors render inline
  directly under the step that produced them, reusing the exact `PlaygroundPresenter` messages.
- Behavior is unchanged: the same fixture wallet, the same mock/live provider selection and
  Blockfrost preprod-only submit boundary, the same ADA-only filtering, the same no-mainnet
  policy, no real mnemonic/private-key display, no arbitrary-mnemonic input, no full CBOR
  display, no polling, and no multi-asset support. `App.kt` now wraps `PlaygroundScreen` in
  `KardanoPlaygroundTheme` instead of the default `MaterialTheme`.

**Background/inset polish (same block).** `PlaygroundScreen`'s root container paints a subtle
theme-derived gradient (`MaterialTheme.colorScheme.surface` into `background` — the same tone
`PlaygroundHeader`'s own gradient ends on) instead of relying on the platform's default (white)
window background, and applies `Modifier.safeDrawingPadding()` so the hero never starts under
the status bar and the reset/diagnostics controls at the bottom are never hidden behind the
navigation bar. `safeDrawingPadding()` is a Compose-Multiplatform-common `expect`/`actual` API
(`androidx.compose.foundation.layout`) — no Android-specific inset code was added; `:androidApp`
already calls `enableEdgeToEdge()` (Block 1.2), which this polish now actually accounts for.

## Playground landing section (Block 1.12-pre-c)

Block 1.12-pre-c is a **sample-app UX/content change** on top of the 1.12-pre-b refresh: it makes
the Playground open like a small developer-facing landing/demo page, then keeps the existing
guided flow below it. It preserves the 1.12-pre-a MVI architecture and all SDK behavior — no SDK
public API, no provider/wallet/tx change, no new dependency, and no
`:core`/`:crypto`/`:wallet`/`:tx`/`:provider`/`:provider-blockfrost` change. `PlaygroundScreen`
still only reads `PlaygroundState` and dispatches `PlaygroundIntent`s.

Top-to-bottom, the screen now reads: **hero → landing overview → the interactive flow →
Diagnostics**.

- **Hero** (`PlaygroundHeader.kt`, reworked): the "Kardano SDK" title, the "Kotlin Multiplatform
  Cardano SDK" subtitle, the value statement *"Build Cardano wallet and transaction flows from
  shared Kotlin code."*, a platform/scope badge row (`KMP` / `Android` / `iOS` / `JVM` / `Preprod`
  / `ADA-only MVP`), the same test-only framing line, and a CTA button (*"Try the transaction flow
  below ↓"*) that smooth-scrolls to the flow. The active provider mode is shown by the flow's
  provider card and per-step badges, so the hero no longer carries it.
- **Landing overview** (`LandingSection.kt` — `PlaygroundLanding`, all presentation, no SDK call):
  - *What the SDK does today* — five compact capability cards (parse/validate addresses, restore a
    test wallet, query UTxOs/balance through the provider boundary, build ADA-only drafts, sign
    locally and submit to preprod).
  - *The transaction flow* — a preview of the five steps with developer-friendly labels ("Create a
    test wallet" … "Send it to preprod") and a note that exact technical detail stays behind the
    per-step toggles below.
  - *Code examples* — three collapsible monospace snippet cards, each tagged `simplified`. These
    are deliberately illustrative pseudo-snippets — **never** a real mnemonic, private key, or full
    signed CBOR. The collapse is driven by `PlaygroundState.codeExamplesExpanded` /
    `PlaygroundIntent.ToggleCodeExamples` (a presentation-only reducer flag, default collapsed).
  - *Roadmap and scope* — Phase 0 / Phase 1 / Next cards plus an honest "Current limitations" list:
    testnet/preprod-focused demo, ADA-only MVP, no multi-asset transactions yet, no mainnet flow,
    and no real wallet import in the Playground (it uses a fixed test-only fixture).
- All landing visuals are **Compose-drawn** (accent dots, numbered dots, the existing hero mark);
  **no external image/logo asset is bundled** — logos/illustrations are deferred until added with
  an explicit source/license.
- The guided steps' titles were softened to the developer-friendly labels above (e.g. Wallet →
  "Create a test wallet"), with a one-line explanation each; the exact hex/fees/witnesses/ids stay
  behind the per-step "Technical details" toggle. The step actions and outputs dispatch the same
  intents and render the same `PlaygroundPresenter` data as before.

## Playground sections and roadmap screen (Block 1.12-pre-c-2)

> **Superseded on navigation only** by Block 1.12-pre-e's guided-demo redesign (see
> "Playground guided demo (Block 1.12-pre-e)" below): the tab row, `PlaygroundSection.OVERVIEW`/
> `TRY_SDK`, and `NavigateToOverview`/`NavigateToTrySdk` described in this section no longer exist.
> The roadmap screen's card content and tap-to-expand behavior described here are unchanged.

Block 1.12-pre-c-2 splits the sample app into three navigable sections and adds a dedicated,
tappable roadmap screen, and softens the Wallet step's main-UX wording. It is **sample-app
UX/content only** — the 1.12-pre-a MVI architecture and all SDK behavior are preserved (no SDK
public API, no provider/wallet/tx change, no new dependency, no non-`:shared` module touched).
`PlaygroundScreen` still only reads `PlaygroundState` and dispatches `PlaygroundIntent`s.

- **Top navigation.** A `SectionNav` row switches between three sections, driven by
  `PlaygroundState.section` (`PlaygroundSection.OVERVIEW` / `TRY_SDK` / `ROADMAP`, default
  `OVERVIEW`): the selected tab is a filled button, the others outlined. Navigation intents
  (`NavigateToOverview` / `NavigateToTrySdk` / `NavigateToRoadmap`) are presentation-only reducer
  transitions.
  - **Overview** — the hero + `PlaygroundLanding` (capabilities, transaction-flow preview, code
    examples, and a compact `RoadmapTeaser`). The hero CTA and the teaser navigate to Try SDK /
    Roadmap (replacing 1.12-pre-c's in-page scroll). The inline roadmap/limitations block moved into
    the dedicated Roadmap screen.
  - **Try SDK** — the unchanged guided **Wallet → Funds → Build → Sign → Submit** flow, the reset
    control, and the visually secondary, collapsed-by-default Diagnostics.
  - **Roadmap** — the new `RoadmapScreen`.
- **Roadmap screen** (`RoadmapScreen.kt`): one clickable card per phase, driven by
  `PlaygroundState.selectedRoadmapPhase` (`RoadmapPhase?`, default `PHASE_1`) and
  `PlaygroundIntent.SelectRoadmapPhase` (tapping the selected phase again collapses it). Each card
  shows a title, a status badge (**Done** / **Current** / **Planned** / **Future**), and a tagline;
  when selected it also shows a highlights list and a scope note. **Phase 0 (Foundation)** and
  **Phase 1 (MVP transaction flow)** describe shipped work; **Phase 2 (wallet/provider expansion)**
  and **Phase 3 (advanced transaction/ecosystem features)** are aspirational **candidate direction,
  explicitly not a commitment and with no dates**. The screen is Compose-drawn (no external asset)
  and is **sample-app presentation, not a committed public API or delivery schedule**.
- **Wallet copy.** The Wallet step now reads **"Create test wallet"** (title + action, status
  "Creating…") with the explanation *"Set up the built-in test-only wallet and generate its testnet
  address."* Its "Technical details" block keeps the precise wording that the demo calls
  `ReadOnlyWallet.restore(...)` with a **cited public test-only mnemonic fixture — never a real
  wallet, mnemonic, or private key, and never real funds**. No arbitrary-mnemonic input and no real
  wallet import were added; the underlying `RestoreWallet` intent and all SDK calls are unchanged.

## Seeded mock UTxOs for the guided flow (Block 1.12-pre-c-3)

Block 1.12-pre-c-3 is a **sample-app/mock-data change only**: it lets the *default mock mode* run
the whole **Wallet → Funds → Build → Sign** flow offline, instead of stopping at "no UTxOs". It
adds **no SDK public API**, does **not** change `:provider`, `:wallet`, or `:tx` behavior, does
**not** change the live Blockfrost path, and does **not** fake a network submission.

- **Why it was needed.** The guided flow restores `TestWalletFixture` and queries the active
  provider for *that wallet's own* self-generated testnet address. `:provider`'s default seed has
  no UTxOs for that address, so under the plain in-memory mock, Build/Sign/Submit failed early with
  "no UTxOs".
- **What changed.** A new `:shared` sample object, `playground/data/PlaygroundMockSampleData.kt`,
  builds the Playground's default mock `ChainQueryProvider`. It starts from
  `InMemoryChainQueryProvider.defaultSeed()` (which keeps `SEED_ADDRESS_WITH_UTXOS` funded and
  `SEED_ADDRESS_EMPTY` empty for the Provider explorer) and **adds two deterministic, fake, ADA-only
  UTxOs for the demo wallet's own restored address** (5 ADA + 8 ADA = 13 ADA — enough for the fixed
  2 ADA demo payment plus fee and change). It restores `TestWalletFixture` only to obtain that
  address; if the restore fails, the entry is omitted and mock mode degrades to the earlier honest
  "no UTxOs" behavior rather than crashing. `PlaygroundProviderFactory` now builds its mock query
  provider from this object (lazily, so the derivation runs once on first mock use). The fake UTxOs
  are **not chain data**: fixed sentinel transaction hashes, no native assets
  (`hasNativeAssets = false`), no network, no funds, no secrets.
- **Submit stays honest.** The mock submit provider is unchanged — `InMemoryTxSubmitProvider`
  always returns `SubmitError.SubmissionNotSupported`. In mock mode the Submit step now *reaches*
  that provider (because Build/Sign succeed) and shows its readable "this provider does not support
  submission (mock)" message, rather than failing earlier for lack of UTxOs.
- **Copy.** The provider card states mock mode uses **"fake local UTxOs, test-only, no network.
  Submit is not supported here."** while live mode keeps **"real network calls, test funds only."**
- **Expected default mock flow.** Create test wallet ✓ · Check available test ADA → non-zero
  (13 ADA, 2 UTxOs) ✓ · Prepare transaction ✓ · Sign locally ✓ · Send to preprod → honest
  "submission not supported". Live preprod mode is unchanged (real calls, faucet-funded address).

## Brand mark and theme (Block 1.12-pre-d)

Block 1.12-pre-d is a **visual/branding change only**: it replaces every placeholder/template icon
and the Kotlin/KMP-inspired sample palette from Block 1.12-pre-b with the project's own,
first-party icon mark and a matching Material 3 theme, ahead of the public landing page. It adds no
SDK behavior, no SDK public API, no new dependency, and no
`:core`/`:crypto`/`:wallet`/`:tx`/`:provider`/`:provider-blockfrost` change; the guided flow, its
MVI state/intents/reducer, and every use case/provider factory call are unchanged.

- **The mark.** A violet-to-blue "K" beside a cyan-tinted, Cardano-style dot cluster — Sarmidev's
  own artwork (see `docs/THIRD_PARTY_NOTICES.md`'s "First-party assets" table), not the Kotlin or
  Cardano logo. It ships as a saturated **light** variant (for light surfaces) and a white/lilac
  **dark** variant (for dark surfaces), both with verified-transparent backgrounds.
- **Theme (`PlaygroundTheme.kt`).** The Kotlin/KMP-inspired purple/blue/orange scheme is replaced
  with a violet/blue/cyan scheme matched to the mark (light primary `#5B3FD1` / secondary
  `#216BB9` / tertiary `#006E88` on a cool `#FAF9FF` background; dark primary `#CDBDFF` / secondary
  `#A6CEFF` / tertiary `#8FE3FF` on a violet-black `#0E0C13` background — neither pure white nor
  pure black, so the mark reads clearly on top). A new `KardanoBrandColors` data class, provided
  through a `LocalKardanoBrand` composition local, centralizes the five decorative accent hues
  (`LandingSection.kt`'s capability/step-number dots) and every chip background/foreground pair
  (`StatusBadge.kt`'s `Badge`/`StepStatus` chips) — each with a distinct dark-mode value, so dark
  mode no longer reuses light-mode chip colors verbatim.
- **Header mark (`PlaygroundHeader.kt`).** The Compose-drawn `KmpMark()` (a gradient rounded square
  with two drawn chevrons) is replaced by `BrandMark()`, an `Image` that renders
  `Res.drawable.kardano_mark_light` or `-dark` depending on `isSystemInDarkTheme()` — the same
  signal `KardanoPlaygroundTheme` uses for its color scheme, so the mark and the surrounding hero
  always agree. The two PNGs live under `composeResources/drawable/`; the unused JetBrains sample
  drawable (`compose-multiplatform.xml`) was removed alongside them.
- **Launchers and shells (outside `:shared`).** `:androidApp`'s adaptive icon, legacy mipmaps, and
  visible app name; `iosApp`'s `AppIcon` dark-appearance slot, `AccentColor`, and display name; and
  `:desktopApp`'s distribution/window icons and window title were all updated to the same mark and
  palette — see this repository's top-level `docs/HANDOFF.md` for the per-platform detail, since
  none of that lives in `:shared`.
- **Not changed.** `PlaygroundScreen.kt`'s root gradient already read
  `MaterialTheme.colorScheme.surface`/`background` rather than a hardcoded color, so it picks up
  the new palette automatically; no edit was needed there.

## Playground guided demo (Block 1.12-pre-e)

Block 1.12-pre-e is a **presentation-only redesign** of the Playground, aimed at a first-time
viewer with no Cardano knowledge watching a short public video: it replaces the Block
1.12-pre-c-2 tab row (Overview / Try SDK / Roadmap) with a **linear, one-step-at-a-time guided
story** — Welcome → Demo (five steps) → Summary — with plain-language copy, one obvious primary
action per step, and every technical term (hashes, fees, CBOR, UTxOs, witnesses) collapsed behind
an optional "Technical details" toggle. It touches only `playground/mvi` + `playground/ui` plus
two additive display rows and one extracted constant in `PlaygroundPresenter.kt` — **no SDK
public API, no provider/wallet/tx/signing/crypto change, no new dependency**, and every existing
test/behavior the earlier Playground blocks documented above still holds.

- **Sections, not tabs.** `PlaygroundSection` is now `WELCOME` / `DEMO` / `SUMMARY` / `ABOUT` /
  `ROADMAP` (default `WELCOME`), superseding 1.12-pre-c-2's `OVERVIEW` / `TRY_SDK` / `ROADMAP` on
  navigation only — `NavigateToOverview`/`NavigateToTrySdk` are renamed to
  `NavigateToAbout`/`NavigateToDemo`, and `NavigateToWelcome`/`NavigateToSummary` are new. Welcome
  is the landing screen (what the demo does, a five-step preview, *Start the demo*); About (the
  former Overview content) and Roadmap are secondary screens reachable from Welcome and Summary,
  each with a "Back to the demo" control back into `DEMO`.
- **One step at a time.** `PlaygroundState.demoStep: PlaygroundStep` (default `WALLET`) is a new
  presentation-only cursor into the same five steps 1.12-pre-c-2 already had —
  **Wallet → Funds → Build → Sign → Submit**, unchanged — rendered one `FlowStepCard` at a time by
  `DemoStepSection.kt` instead of all five stacked. Above the card: `Step N of 5` plus a compact
  recap strip of finished steps; below it (via the card's own secondary-action row): *Back* and
  *Continue* (*See the summary* on the last step); further below: *Start over* and a collapsed
  *"Advanced: connect to a test network"* disclosure holding the Mock/Live switch (moved out of
  the always-visible provider card) and the Blockfrost preprod project-id field, now rendered with
  `PasswordVisualTransformation` (previously plain text — the one existing behavior this block
  changes for sensitivity, not for capability). The switch expresses intent only: until that
  field is non-blank, `PlaygroundState.isLivePreprodActive` remains false, the provider factory
  continues to use Mock, and the panel explicitly reports that live configuration is incomplete.
- **`PlaygroundDemoFlow.kt`** (new, `playground/mvi`): a pure, non-suspend, `commonTest`-covered
  object holding every derived-state rule the UI needs — `outcome(state, step): StepOutcome`
  (`NOT_STARTED` / `WORKING` / `DONE` / `INFO` / `ERROR`), `canContinue(state)` (gates
  `ContinueDemo`), `completedSteps(state)`, `friendlyReason(step, message)` (maps a documented
  subset of existing `PlaygroundPresenter` messages to a plain sentence, falling back to `null` so
  the raw message still shows under Technical details), and `shortenAddress`/`shortenId` (bech32
  address / hex id truncation for headline text). No composable computes this itself.
- **The honest mock-stop, made legible.** The mock Submit step still returns exactly the same
  `SubmitTransactionPresentation.Failure` it always has (`InMemoryTxSubmitProvider` never fakes an
  accepted id, per ADR-0017) — this block does not touch that. What changes is only how it is
  *presented*: `PlaygroundDemoFlow.outcome` classifies that one specific, expected combination
  (the effective provider is Mock **and** the mock's own not-supported message) as a new
  `StepOutcome.INFO` — a neutral "stopped on purpose" state, backed by a new `StepTone.INFO` chip
  tone (mapped to the existing `chipInfoBg`/`chipInfoFg` brand tokens, no new colors) — rather
  than the same red `ERROR` a real failure gets. Effective provider state requires both the live
  switch and a non-blank project id, matching `PlaygroundProviderFactory`'s existing fallback
  behavior. To key off the result message reliably instead of restating it,
  `PlaygroundPresenter.presentSubmitError`'s literal for `SubmitError.SubmissionNotSupported` was
  extracted, byte-identical, into a new `internal const val MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE`.
  Any other Submit failure — including that same combination under live mode, which should not
  happen — still classifies as `ERROR`.
- **`DemoCopy.kt`** (new, `playground/ui`): every primary-facing string for Welcome, the Demo
  chrome, all five steps, and Summary, gathered into one reviewable, data-driven table instead of
  scattered across composables. Its `Chrome.Advanced` group and the Summary's "What this demo is
  not" scope list are the two documented, narrower exceptions allowed to name a live-mode-only
  term ("Blockfrost", "mainnet"); every other string is asserted jargon-free
  (no "UTxO"/"CBOR"/"witness"/"lovelace"/"Bech32"/"mainnet"/"Blockfrost") and banned-word-free by
  `DemoCopyTest`.
- **ADA, not raw lovelace, in the main narrative.** A new `playground/LovelaceDisplay.kt`
  (`fun ada(lovelace: Long): String`, e.g. `2_000_000L -> "2 ADA"`, `1_500_000L -> "1.5 ADA"`)
  backs four new, purely additive `LabeledRow`s in `PlaygroundPresenter.kt` — `Test ADA` on the
  balance result, and `Payment` / `Network cost` / `Change back` on the draft result — used by the
  Demo screen's plain-language headlines. No existing `LabeledRow` label or value changed; the raw
  lovelace rows (`Balance`, `Fee`, `Change`) are still there, under Technical details.
- **Diagnostics moved, not changed.** `DiagnosticsSection.kt` (Address Parser, Hex Decoder, CBOR
  Decoder, Provider explorer) is content-unchanged; it now lives under the About screen's
  "Developer tools" heading (still collapsed by default) instead of beneath the old Try SDK tab,
  since it is unrelated to the guided demo's fixture wallet and was crowding the main story.
- **Summary.** A new `SummarySection.kt` recaps what the SDK did in five plain sentences (the
  fifth honestly branching on whether Submit ran in mock or live mode), an explicit "What this
  demo is not" scope list (test money only, one built-in wallet, ADA-only, test networks only,
  Phase 1/experimental/pre-alpha), and *Run the demo again* (which reuses the existing
  `ResetFlow` intent, extended to also reset `demoStep`/`section` back to the start of the Demo
  screen — the same intent now serves both a mid-demo "Start over" and this "run again").
- **Not changed.** The 1.12-pre-a MVI split (reducer vs. ViewModel), every `RestoreWallet` /
  `QueryFunds` / `BuildDraft` / `SignTransaction` / `SubmitTransaction` call and its provider
  wiring, `TestWalletFixture`, `PlaygroundMockSampleData`'s seeded UTxOs (1.12-pre-c-3),
  `PlaygroundProviderFactory`, the Block 1.12-pre-d brand mark/theme, and every existing
  `*Presentation` display rule (no mnemonic, seed, private key, or untruncated signed CBOR
  anywhere) — this block is additive/relocating UI and copy only.

### Test Wallet & Address Generation section (Block 1.6d, extended by Block 1.7b)

The "Test Wallet & Address Generation" section restores `playground/TestWalletFixture.kt`'s
cited test-only BIP-39 mnemonic (the same public vector `:crypto`'s `KeyDerivationVectorsTest`
and `PublicKeyProjectionDeviceTest` already cite from `IntersectMBO/cardano-addresses`) —
**never a real mnemonic, never associated with real funds** — and derives the two fixed
CIP-1852 paths `paymentPath` (`m/1852'/1815'/0'/0/0`) and `stakePath` (`m/1852'/1815'/0'/2/0`)
via `:crypto`'s `KeyDerivation.derivePrivate`/`publicKey`. Each derived public key's
Blake2b-224 credential hash is computed via `:crypto`'s `Hashing.blake2b224`, wrapped with
`:core`'s `AddressCredential.keyHash(...)`, and passed to
`Address.baseAddress(Network.TESTNET, paymentCredential, stakeCredential)`
(Block 1.7a). The generated address is immediately re-parsed with
`Address.parse(address.toBech32())` for a structural round-trip check. The screen displays
**only** both path strings, both credential-hash hex values (public CIP-19 credentials, not
secret key material), the generated `addr_test1...` address, and the round-trip status —
never the mnemonic, entropy, seed, root/private key bytes, or a raw public key. All
derivation, projection, hashing, credential, and address-encoding logic belongs to
`:crypto`/`:core`; `PlaygroundPresenter` only calls it and formats the result, per this file's
standing rule below. This is structural address generation only: no signing, no transaction
logic, and no claim that the generated address is owned, funded, or registered.

### Provider section

The "Provider" section exercises `:provider`'s read-only `ChainQueryProvider`. It defaults to
`InMemoryChainQueryProvider`, whose data is **fake and test-only** — no real network, no funds,
no secrets, no committed chain fixtures. Two documented seed addresses (both valid public
CIP-19 testnet vectors) drive the mock checkpoint:

- Has UTxOs: `addr_test1vz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerspjrlsz`
  (`InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS`).
- Empty: `addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae`
  (`InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY`). This is a different address from the guided
  flow's demo wallet (which Block 1.12-pre-c-3 seeds with fake UTxOs), so it still shows the empty
  state.

The screen provides one-tap buttons to fill either seed address.

A "Use live Blockfrost (preprod)" toggle (Block 1.3b) switches the same section to a live
`BlockfrostChainQueryProvider` (`:provider-blockfrost`) built from a `project_id` you paste in.
That key is held only in non-persistent Compose state (`remember`, not `rememberSaveable`) — it
is never stored, saved, or logged — and live calls hit the real preprod network (test funds).
No key is committed to the repo. See
[docs/DECISIONS/0006-provider-boundary-and-strategy.md](../docs/DECISIONS/0006-provider-boundary-and-strategy.md)
and [docs/DECISIONS/0007-http-client-and-blockfrost-provider.md](../docs/DECISIONS/0007-http-client-and-blockfrost-provider.md).

### Wallet Balance section (Block 1.8b)

The "Wallet Balance (read-only)" section restores the same `TestWalletFixture` mnemonic as the
Test Wallet section above, but through `:wallet`'s `ReadOnlyWallet.restore(TestWalletFixture.words,
Network.TESTNET)` — always `Network.TESTNET`; that call site, not `ReadOnlyWallet.restore`
itself, is what enforces the Phase 1 no-mainnet boundary here (`ReadOnlyWallet.restore` is
generic over `Network`, see [docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md](../docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md)
§3). It then queries whichever `ChainQueryProvider` is currently selected in the Provider
section above (mock or live) via `wallet.balance(provider)` and displays only the generated
`addr_test1...` address, the UTxO count, and the balance in lovelace — never the mnemonic,
seed, entropy, or any private/raw key bytes. `:shared` reimplements none of mnemonic parsing,
derivation, hashing, address generation, or balance summation; all of that logic belongs to
`:wallet`/`:crypto`/`:core`, and `PlaygroundPresenter.presentWalletBalance` only calls it and
formats the result. A zero balance/UTxO count under `:provider`'s own bare
`InMemoryChainQueryProvider()` default is the honest result (ADR-0013 §7) — that seed has no fake
UTxOs for this generated address — and is displayed as a normal success, not an error. Note that
since Block 1.12-pre-c-3 the *Playground's* default mock provider is built by
`PlaygroundMockSampleData` (not the bare `:provider` default) and **does** seed this address with
fake ADA-only UTxOs so mock mode can run the flow; the bare `:provider` default and the presenter
desktop tests that use it directly are unchanged. A live Blockfrost preprod provider can show a
non-zero balance only after the generated address is funded with test ADA from a preprod faucet.

### Transaction Draft section (Block 1.9c)

The "Transaction Draft (unsigned)" section restores the same `TestWalletFixture` mnemonic as
the Wallet Balance section above (always `Network.TESTNET`, via `ReadOnlyWallet.restore`),
queries whichever `ChainQueryProvider` is currently selected in the Provider section for that
wallet's candidate UTxOs and the current `ProtocolParameters`, and calls `:tx`'s
`TransactionBuilder.build(TransactionBuildRequest)` to build a minimal, single-payment,
**unsigned** ADA transaction: a fixed 2 ADA payment to a reused cited CIP-19 testnet vector
(`InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY`, already used elsewhere in this Playground as a
provider seed address — not invented for this checkpoint), with any change returned to the
restored wallet's own address. `:shared` performs no coin selection, fee estimation, change
decision, or CBOR encoding itself — all of that belongs to `:tx`
(`TransactionBuilder`/`TransactionBodySerializer`), and `PlaygroundPresenter.presentTransactionDraft`
only builds the request and formats the result. On success the screen shows only the selected
input and output counts, the fee and (if present) change amounts in lovelace, the encoded body
size in bytes, and a truncated hex preview of the body bytes — always labeled as an unsigned
draft. On failure (for example no UTxOs, insufficient funds, or an amount below minimum ADA) the
screen shows a message distinguishing the cause, mapped from `:tx`'s typed `TxBuildError`. Under
the raw `InMemoryChainQueryProvider` default, the restored wallet's address has no fake UTxOs
seeded for it — same honest-empty behavior as presenter tests for Wallet Balance (ADR-0013 §7).
The Playground factory mock (`PlaygroundMockSampleData`) seeds fake ADA-only UTxOs for that
address so the guided demo can complete Funds/Build/Sign offline. A live Blockfrost preprod
provider can build a real draft only after that address is funded with test ADA from a preprod
faucet. **No signing, no witness construction, no transaction id hashing, and no submission**
anywhere in this checkpoint — see
[docs/DECISIONS/0014-minimal-ada-transaction-builder.md](../docs/DECISIONS/0014-minimal-ada-transaction-builder.md).

**ADA-only filtering (Block 1.11d, narrowed in 1.11d-2).** A manual Android checkpoint found
that a preprod address funded with mixed (ADA + native-asset) UTxOs let a draft build and sign,
then get rejected by the node at submit time (`ValueNotConservedUTxO`) once the built
transaction implicitly dropped the native assets those inputs carried. `:tx`'s
`TransactionBuilder` now drops every UTxO with `Value.hasNativeAssets` set before selecting
inputs, so a wallet with a mix of ADA-only and native-asset UTxOs still builds normally from
just the ADA-only ones; it only fails (`TxBuildError.UnsupportedFeature`) when that leaves no
candidates at all, and `presentTxBuildError` then shows a dedicated message: "This wallet has
no ADA-only UTxOs to spend — only UTxOs containing native assets/tokens. Phase 1 only builds
ADA-only transactions." This is honest filtering, not multi-asset support: no token quantities,
policy ids, sending, or change-preserving logic were added anywhere in this stack, and a
native-asset UTxO is never selected as an input.

### Signed Transaction (not submitted) section (Block 1.10c)

The "Signed Transaction (not submitted)" section builds the same unsigned draft as the
Transaction Draft section above — through a shared `PlaygroundPresenter.buildTransactionDraft`
helper extracted from that checkpoint so both sections build the identical draft — then signs it
by calling `:wallet`'s `ReadOnlyWallet.signTestnetFixtureTransaction(TestWalletFixture.words,
Network.TESTNET, draft)`, always passing the cited test-only fixture words and `Network.TESTNET`
explicitly. ADR-0019 now also binds `TransactionDraft.network` / `scope` and rejects a
mismatched or mainnet draft, plus any mnemonic that does not derive to
`Phase1FixtureIdentity`, at signing time. The function's scope-explicit name and its required
`ExperimentalKardanoSigningScope` opt-in (ADR-0018) remain a Kotlin-compiler intent signal;
that opt-in does **not** appear as a Swift compile-time gate on the compiled `Shared`
framework. The runtime `WalletError.SigningScopeViolation` checks **do** run for Swift
callers. `:shared` performs no hashing,
signing, or witness/CBOR assembly itself — all of that belongs to `:wallet` (which itself
delegates to `:crypto`'s `Signing` and `:tx`'s `TransactionAssembler`) — and
`PlaygroundPresenter.presentSignedTransaction` only calls it and formats the result. On success
the screen shows only the 32-byte transaction id (hex), the witness count (always `1` for this
single-key checkpoint), a truncated hex preview of the full signed `transaction` CBOR, and an
explicit `signed, not submitted — testnet-only, test fixture, no real funds` label — never the
mnemonic, seed, private/root key bytes, or the full (untruncated) signed CBOR. On failure the
screen shows a message distinguishing the cause, covering both the same draft-building failures
the Transaction Draft section can report and every `WalletError`
`ReadOnlyWallet.signTestnetFixtureTransaction` itself can return (a signing failure or a
witness/transaction-assembly failure). Under the
raw `InMemoryChainQueryProvider` default, the restored wallet's address has no fake UTxOs seeded
for it — same honest-empty behavior as the presenter tests above. The Playground factory mock
seeds that address, so the guided Sign step can complete offline. A live Blockfrost preprod
provider can sign a real draft only after that address is funded with test ADA from a preprod
faucet. **No
submission anywhere in this checkpoint** — submitting a transaction is Block 1.11, see
[docs/DECISIONS/0015-transaction-signing.md](../docs/DECISIONS/0015-transaction-signing.md).

### Submit Transaction (preprod) section (Block 1.11c)

The "Submit Transaction (preprod)" section builds and signs the same fixture transaction as
the Signed Transaction section above — through `PlaygroundPresenter.presentSubmitTransaction`,
which reuses the exact same `buildTransactionDraft` + `ReadOnlyWallet.signTestnetFixtureTransaction`
sequence — then calls `:provider`'s `TxSubmitProvider.submit(signed.signedTransaction.cbor())` directly
on the resulting `WalletSignedTransaction`. **No new `:wallet` orchestration method was added
for this** (ADR-0017 "Non-goals"): the presenter sequences build → sign → submit itself, and
the accepted-id/local-id comparison lives in the presenter, not in `:wallet` or `:provider`.

A new `activeSubmitProvider: TxSubmitProvider` is wired alongside the existing `activeProvider:
ChainQueryProvider`, gated by the same "Use live Blockfrost (preprod)" toggle and `project_id`
field the Provider section already uses (no second key field is added): the default is
`InMemoryTxSubmitProvider()` (fake/test-only — it always returns
`SubmitError.SubmissionNotSupported`, per ADR-0017, never a fake accepted id); enabling the
toggle with a `project_id` switches to a live `BlockfrostTxSubmitProvider.create(BlockfrostConfig(projectId
= key))` (real preprod submission, test funds only, never mainnet). On success the screen
shows only the accepted transaction id, the locally-signed transaction id, whether the two
match (with a readable mismatch note if they do not), and an explicit `submitted to preprod —
testnet-only, test fixture, no real funds` label. On failure the screen shows a message
distinguishing the cause, covering every `SubmitError` variant (including
`SubmissionNotSupported`'s explicit "this provider does not support submission (mock)"
message) and every upstream draft-building/signing failure the Transaction Draft and Signed
Transaction sections can already report. **No automatic polling**: once a submission is
accepted, the screen shows the accepted id once, for a manual preprod-explorer lookup — a
single-shot submit-and-display checkpoint has no justification yet for the added complexity
(see `PlaygroundPresenter.presentSubmitTransaction`'s KDoc). See
[docs/DECISIONS/0017-transaction-submission-boundary.md](../docs/DECISIONS/0017-transaction-submission-boundary.md).

**SDK logic and the protocol/cryptographic test-vector suites belong in `:core`/`:crypto`/
`:wallet`/`:tx`, not here.** `:shared` only calls `:core`/`:crypto`/`:provider`/`:wallet`/`:tx`
APIs and formats/displays results. `PlaygroundPresenter` is a display-only mapping layer with no
protocol or cryptographic rules of its own — it does not reimplement derivation, projection,
hashing, address generation, balance summation, coin selection, fee/change computation, or CBOR
encoding. `:shared` tests use a minimum of cited CIP-19/CIP-1852 vectors to verify presenter
wiring, but do not replicate the `:core`/`:crypto`/`:wallet`/`:tx` test-vector suites.

## Why it still contains UI

The SDK core direction is UI-free and lives in `:core`. `:shared` keeps Compose because the
iOS app needs a Kotlin-produced UI framework. Removing Compose from `:shared` outright would
break the iOS sample app.

## Planned direction

`:shared` is expected to migrate toward a dedicated sample module (a candidate `:sample:*`
name) in a later step. It is intentionally not renamed now to avoid changing the iOS Xcode
project. See [docs/DECISIONS/0002-module-structure.md](../docs/DECISIONS/0002-module-structure.md).

## Consumers

- `:androidApp`, `:desktopApp` depend on `:shared`.
- `iosApp` (Xcode) links the `Shared` framework produced here.

## Testing

`:shared` carries example tests in `commonTest`, `jvmTest`, `androidHostTest`, and `iosTest`
that demonstrate the wiring per target. The protocol/cryptographic test-vector suites and
SDK-logic tests belong in `:core`/`:crypto`/`:wallet`; `:shared` uses only a minimum of cited
CIP-19/CIP-1852 vectors for presenter-wiring verification. The test-wallet + address-generation
checkpoint's `commonTest` coverage (`PlaygroundWalletPresenterTest`) is deliberately
native-free — it covers only error mapping, path formatting, and mnemonic-parsing failures
that are rejected before any native derivation call, because `:crypto`'s native backend
cannot load under the Android host-JVM target (`androidHostTest`); the end-to-end
fingerprint/address golden check (`PlaygroundWalletDerivationDesktopTest`) lives only in
`jvmTest`, where the native backend does load — it asserts the cited golden payment
credential and a structural generate-then-parse round trip, never a self-generated address
pinned as if it were an external vector. The wallet-balance checkpoint follows the same split:
`PlaygroundWalletBalancePresenterTest` (`commonTest`) is native-free, feeding constructed
`WalletBalance`/`WalletError` values and a `Address.parse`-derived address into
`mapWalletBalanceResult`/`presentWalletError` directly; `PlaygroundWalletBalanceDesktopTest`
(`jvmTest`-only) is the only place `presentWalletBalance` and `ReadOnlyWallet.restore` run end
to end together, asserting the honest zero balance under the default mock and that the
checkpoint's own restore call uses `Network.TESTNET`. The transaction-draft checkpoint follows
the same split: `PlaygroundTransactionDraftPresenterTest` (`commonTest`) is native-free, building
real `TransactionDraft`/`TxBuildError` values via `TransactionBuilder.build` against hand-built
fake UTxOs and cited CIP-19 addresses (no mnemonic, no native call) and feeding them into
`mapTransactionDraftResult`/`presentTxBuildError` directly; `PlaygroundTransactionDraftDesktopTest`
(`jvmTest`-only) is the only place `presentTransactionDraft` and `ReadOnlyWallet.restore` run end
to end together, asserting the honest "no UTxOs" result under the default mock and a successful
draft once the mock is seeded with a UTxO for the restored wallet's own address.
`PlaygroundTransactionDraftPresenterTest` also covers the Block 1.11d/1.11d-2 ADA-only
filtering: a hand-built, sole `Utxo` with `Value.hasNativeAssets = true` fed through the real
`TransactionBuilder` is rejected with `TxBuildError.UnsupportedFeature` (message asserted to
mention "native" and "ADA-only"), while a *mixed* candidate list (one native-asset UTxO plus a
sufficient ADA-only one) builds successfully and selects only the ADA-only input;
`PlaygroundTransactionDraftDesktopTest` covers both the sole-native-asset rejection and the
mixed-candidates success end to end, once seeded for the restored wallet's own address, without
a live Blockfrost call. The signed-
transaction checkpoint (Block 1.10c) follows the same split:
`PlaygroundSignedTransactionPresenterTest` (`commonTest`) is native-free, feeding constructed
`WalletError` values (`Signing`, `TransactionAssembly`) into `mapSignedTransactionResult`/
`presentSigningError`/`presentWalletError` directly (no mnemonic, no native call);
`PlaygroundSignedTransactionDesktopTest` (`jvmTest`-only) is the only place
`presentSignedTransaction` and `ReadOnlyWallet.signTestnetFixtureTransaction` run end to end
together, asserting the honest "no UTxOs" result under the default mock, and — once the mock is seeded
with a UTxO for the restored wallet's own address — a successful signed transaction whose rows
carry a well-formed 32-byte hex transaction id, exactly one witness, a truncated CBOR preview,
the exact not-submitted/testnet/fixture label, and none of the fixture's mnemonic words. The
submit-transaction checkpoint (Block 1.11c) follows a related but slightly different split:
`PlaygroundSubmitTransactionPresenterTest` (`commonTest`) is native-free and, unlike the
signed-transaction split, covers **both** branches of its raw-result mapper
(`mapSubmitTransactionResult`) — its accepted-id parameter is a plain `TxHash` (a `:core` value
constructible from any 32 bytes, no native call needed), not a `:wallet`-internal type — so
both the accepted/local-id match-and-mismatch cases and every `SubmitError` variant
(`presentSubmitError`) are exercised directly; `PlaygroundSubmitTransactionDesktopTest`
(`jvmTest`-only) is the only place `presentSubmitTransaction` runs end to end (it reaches
`ReadOnlyWallet.signTestnetFixtureTransaction`'s native backend), asserting the honest "no UTxOs" result
under the default mock and, once the mock query provider is seeded with a UTxO for the
restored wallet's own address, that the mock submit provider still reports its honest
not-supported failure rather than a fake accepted id — there is no automated end-to-end
*success* path, since an actual accepted submission only comes from a live Blockfrost preprod
call, which these tests must not perform.

The MVI layer added in Block 1.12-pre-a follows the same split. `PlaygroundReducerTest`
(`commonTest`) drives `PlaygroundReducer` directly — pure, non-suspend, no coroutine, no native
call — covering the default mock initial state, provider-selection and technical-details
transitions, `ResetFlow`'s keep-vs-clear behavior (completed diagnostics kept; Loading
converted to Empty), diagnostic and guided-operation request-token / address-identity
applies, and every `applyXResult` helper (including the ADA-only/native-asset draft-failure
message from Block 1.11d/1.11d-2 flowing through unchanged). `PlaygroundViewModelTest`
(`jvmTest`-only) drives `PlaygroundViewModel.dispatch` with every guided-flow and
diagnostic-load use case faked (`RestoreWalletUseCase`, `QueryWalletFundsUseCase`,
`BuildTransactionDraftUseCase`, `SignTransactionUseCase`, `SubmitTransactionUseCase`,
`LoadProviderUtxosUseCase`, `LoadProviderParamsUseCase`), covering each step's
success/failure folding (including the submit step's accepted/local-id match and mismatch
cases), the funds step's loading flag while its fake use case is still in flight,
`NonCancellable` stale-result discard for ResetFlow / address edit/fill / repeated Funds,
Build, Sign, Submit, UTxO and params loads / provider-configuration changes, immediate
live-cache invalidation, and that `PlaygroundProviderFactory` selects the same mock-or-live
provider instance the ViewModel passes to a use case. It is `jvmTest`-only because
`androidx.lifecycle.ViewModel.viewModelScope`
needs a `Dispatchers.Main` implementation to dispatch on, which `kotlinx-coroutines-test`
(already a `jvmTest` dependency) supplies via `Dispatchers.setMain`; no native `:crypto`/`:wallet`
call is reached by any fake used here. See [docs/TESTING.md](../docs/TESTING.md) for the testing
strategy and test-vector policy.

- Desktop (JVM) tests: `./gradlew :shared:jvmTest`
- Android host tests: `./gradlew :shared:testAndroidHostTest`
- iOS simulator tests: `./gradlew :shared:iosSimulatorArm64Test`
