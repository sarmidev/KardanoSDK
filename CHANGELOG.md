# Changelog

All notable user-facing changes are recorded here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) concepts. Releases
are not published yet; entries remain under **Unreleased** until a tagged release exists.

## Unreleased

### Added

- Kotlin Multiplatform Cardano SDK modules for primitives, encoding, structural addresses,
  key derivation, providers, wallet orchestration, transaction building, and the signing backend.
- ADA-only, fixture-scoped transaction build/sign/submit demonstration for Blockfrost preprod.
- Android-first Playground with mock data, live preprod opt-in, guided transaction flow, and
  roadmap/overview screens.
- Apache-2.0 project license, contribution guide, quickstart, and Phase 2 funding/pilot planning.
- A dependency-free public landing page under `site/`, deployed to GitHub Pages from `main` via
  a dedicated `deploy-site` workflow (independent from `Verify`). The page links back to the
  repository documentation rather than duplicating it; see `site/README.md`.

### Changed

- The Playground demo is now a linear, guided story (Welcome → five-step Demo → Summary) with
  plain-language copy, one primary action per step, and technical detail (hashes, fees, CBOR,
  UTxOs, witnesses) collapsed behind an optional "Technical details" toggle, replacing the earlier
  Overview/Try SDK/Roadmap tab row. Mock mode stays the default and recommended path; the mock
  submission step is presented as an honest "nothing was sent" outcome rather than an error or a
  faked success. Live Blockfrost preprod mode moved into a collapsed "Advanced" control, and its
  project-id field is now masked. Turning on the switch without entering a project id explicitly
  reports that configuration is incomplete and keeps identifying the active provider as the
  offline mock; the UI only claims live requests once both inputs are present. This is a
  presentation-only change — no SDK public API, provider, wallet, signing, or
  transaction-construction behavior changed.
- Native-asset UTxOs are filtered out of the ADA-only Phase 1 transaction flow rather than causing
  the whole candidate set to fail when ADA-only UTxOs remain available.
- The public landing page's Roadmap section (`site/index.html#roadmap`) now presents Phase 1
  delivered evidence, an explicit invitation for developers and the Cardano community to run the
  mock Playground and share feedback, and the Phase 2 loyalty/ticketing direction as three
  distinct steps, with concrete links to the Quickstart, the technical roadmap, GitHub issues,
  and the Phase 2 plan.

### Changed

- `LovelaceDisplay.ada` (Playground-only display helper) now takes a `Lovelace` instead of a raw
  `Long`, so a negative amount is rejected at `Lovelace.of` construction time rather than being
  representable at all (W9-7, 2026-08-22 pre-release audit). No caller passed a raw negative value
  before this change; this closes the gap at the type level instead of leaving it as an untested
  assumption.

### Known limits

- Mainnet, imported wallets, general-purpose signing, and native-asset transaction construction are
  not implemented.
- iOS and JVM/Desktop share the codebase; Android is the Phase 1 runtime validation target.
- JVM signing artifacts are currently packaged for macOS hosts only.
