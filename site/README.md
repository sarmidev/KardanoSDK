# Kardano SDK public landing page

This directory holds a self-contained, dependency-free static site. It is outside every Kotlin
Gradle module — no framework, package manager, backend, analytics, or new runtime dependency. It
exists to give a short, honest public entrance to the repository; the technical documentation
under [`../docs/`](../docs/) stays the source of truth, and this page links to it rather than
duplicating it.

## Local preview

Serve the directory with any static HTTP server and open it in a browser. For example, from the
repository root:

```bash
cd site
python3 -m http.server 8123
# then open http://127.0.0.1:8123/index.html
```

Any other static file server works the same way (`npx serve`, `ruby -run -e httpd . -p 8123`,
etc.) — none is required or added as a project dependency.

To review both appearances, toggle your OS/browser color scheme (`prefers-color-scheme`) and
resize the window, or use your browser's device toolbar for the mobile layout. The page has no
JavaScript-driven theme switcher; it follows the system setting only.

## Content-source rules

Every public claim on this page must trace back to one of these repository documents, not to new
wording invented for the site:

- [`../README.md`](../README.md)
- [`../docs/PROJECT_BRIEF.md`](../docs/PROJECT_BRIEF.md)
- [`../docs/QUICKSTART.md`](../docs/QUICKSTART.md)
- [`../docs/PHASE_2_PLAN.md`](../docs/PHASE_2_PLAN.md)
- [`../docs/FUNDING_AND_PILOT_PLAYBOOK.md`](../docs/FUNDING_AND_PILOT_PLAYBOOK.md)
- [`../docs/SECURITY.md`](../docs/SECURITY.md)
- [`../docs/ROADMAP.md`](../docs/ROADMAP.md)

Before editing copy, re-read the "Current limits" section of `../README.md` and the "Public-content
guardrails" in the landing-page plan. Do not state or imply: mainnet support, published Maven
artifacts, arbitrary wallet support, user-supplied signing, native-asset transaction support, iOS
runtime validation, independent review, or Phase 2 delivery dates. The Phase 2 loyalty/ticketing
native-asset direction is planned work, not a commitment.

## Asset provenance

`assets/brand/kardano-mark-light.png` and `assets/brand/kardano-mark-dark.png` are website-local
copies of the project's existing first-party icon mark
(`shared/src/commonMain/composeResources/drawable/kardano_mark_light.png` /
`kardano_mark_dark.png`), already recorded as first-party artwork in
[`../docs/THIRD_PARTY_NOTICES.md`](../docs/THIRD_PARTY_NOTICES.md). `favicon-32.png`,
`favicon-64.png`, and `apple-touch-icon.png` are resized derivatives of the light mark;
`og-image.png` is the light mark resized and padded onto the light brand background color for
social-preview cards. No new artwork, Cardano/Kotlin logo, stock illustration, or generated image
was added — every image under `assets/brand/` is a resize/pad/composite of the two existing source
PNGs, the same process already used for the app's launcher icons (see `docs/ROADMAP.md`,
Block 1.12-pre-d).

## Screenshots

The plan for this page called for 2–3 real screenshots of the Playground running in Mock mode. The
automated environment that built this page has no attached display (`screencapture` and headless
browser attempts both confirmed no display session is available), so no real screenshot could be
captured here. **No screenshot was invented or generated to fill this gap.** The hero section
instead shows a clean, Compose-independent, branded summary of the guided flow (wallet → funds →
build → sign → submit) and explicitly says it is not a screenshot.

To replace it with a real screenshot once you have a desktop with a display:

1. Run the Playground: `./gradlew :desktopApp:run` from the repository root.
2. Leave the provider in **Mock** mode (the default) — never capture a screenshot while a live
   Blockfrost project id is entered, and never capture the Android/iOS app screens if a real
   device/emulator is signed into anything other than the test fixture.
3. Open the guided flow ("Try SDK") and capture 2–3 screenshots: the overview/landing screen and
   one or two guided-flow steps (for example "Prepare a transaction" and "Sign it locally").
   Capture both light and dark appearance if useful.
4. Before adding a captured image to `assets/screenshots/`, check it contains no Blockfrost
   project id, no real wallet/mnemonic/private-key material, no personal data, and no network
   credentials — the Mock-mode fixture data needs no further redaction before use.
5. Save the image(s) under `assets/screenshots/` with a descriptive name (for example
   `playground-overview-light.png`), then update `index.html`'s hero panel to reference the image
   with a meaningful `alt` description instead of the branded flow-step list, and update this
   section once real screenshots exist.

## GitHub Pages deployment

[`../.github/workflows/deploy-site.yml`](../.github/workflows/deploy-site.yml) deploys this
directory to GitHub Pages on every push to `main` that changes `site/**` or the workflow itself,
plus manual dispatch (`workflow_dispatch`). It is independent from the SDK `Verify` workflow: it
adds no Gradle, Kotlin, or npm step, and uses only the official `actions/configure-pages`,
`actions/upload-pages-artifact`, and `actions/deploy-pages` actions with the minimum
`pages: write` / `id-token: write` permissions.

**One-time repository setting required** (not something a workflow file can do): in the GitHub
repository's **Settings → Pages**, set **Source** to **GitHub Actions**. Until that setting is
made, pushes to `main` will run the workflow, but GitHub will not serve the deployed result at the
Pages URL. The repository must also be public (or on a GitHub plan that allows Pages for private
repositories) for the published URL to be publicly reachable.

Once enabled, the expected published URL is:

```
https://sarmidev.github.io/KardanoSDK/
```

(the standard project-page URL pattern for the `sarmidev/KardanoSDK` repository — GitHub assigns
the final URL after the first successful deployment; confirm it under Settings → Pages).
