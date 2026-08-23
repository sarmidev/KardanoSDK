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
- A SHA-256 checksum manifest (`crypto-signing-backend/CHECKSUMS.sha256`) for the 8 committed
  native signing-backend binaries, plus a "Verifying the committed binaries" section in
  `crypto-signing-backend/README.md` explaining what it does and does not prove (W5-2). It is a
  tamper/transfer-integrity check tied to a specific commit, not proof that the binaries were
  built from the visible Rust source; independent reproducible-build verification remains an open
  residual risk.
- `TxBuildError.InsufficientFunds` gained two additive fields, `excludedNativeAssetUtxoCount` and
  `excludedNativeAssetLovelace` (default `0`/`0L`, source-compatible with existing call sites), so
  a caller can distinguish "genuinely insufficient ADA" from "value exists but is locked in
  excluded native-asset UTxOs" (W8-2). Direct tests now assert the transaction value-conservation
  identity (`sum(selected inputs) == sum(outputs) + fee`) across the exact-payment/no-change,
  change-emitted, multiple-input, and native-asset-filtered branches, plus that the
  insufficient-funds and fee-overflow paths never produce a draft at all (W8-1).
- `CborError.OutputTooLong`: `Cbor.encode` now sums its assembled output size with `Long`
  arithmetic and rejects before allocating or concatenating the final buffer once the total would
  exceed `Cbor.CBOR_MAX_INPUT_BYTES` — closing a gap where a within-per-element-limits tree (for
  example a flat array of many near-64KiB byte strings) could otherwise assemble into an output
  far larger than any single limit (W6-2).
- `CryptoError.InputTooLong` and `Hashing.MAX_INPUT_BYTES` (1 MiB): `Hashing.blake2b224`/
  `blake2b256` now reject an oversized `input` before the defensive copy that previously ran
  unconditionally, closing a gap where the SDK's other parser primitives (`Cbor`, `Bech32`, `Hex`)
  already enforced a named input bound but hashing did not (W6-1).
- `HexError.EncodeInputTooLong` and `Hex.MAX_ENCODE_INPUT_BYTES` (512 KiB, half of
  `Hex.MAX_INPUT_CHARS`, so encoded output always stays within what `Hex.decode` accepts as
  input): `Hex.encode` now rejects an oversized `bytes` array before allocating the doubled-length
  output buffer.
- `Bech32.convertBits`'s internal 8-bit-to-5-bit direction is now bounded by `Bech32.MAX_DATA_VALUES`
  before allocating its output buffer, mirroring the bound its 5-bit-to-8-bit direction already
  enforced (`Bech32.MAX_DATA_BYTES`), so both directions enforce this bound structurally instead
  of relying on every current caller happening to pre-bound its own input (W6-3).
- `WalletError.InvariantViolation`: replaces two `error(...)` calls inside `ReadOnlyWallet`
  (`TxHash.of`'s and the balance summation's defensive "this cannot happen with valid input"
  branches) that previously threw `IllegalStateException` from a public wallet operation. Neither
  branch is reachable with valid input today; they now return a typed error instead of throwing,
  closing the gap between that guarantee and this module's own never-throw policy.

### Changed

- **Breaking:** `TransactionDraft` now carries `network: Network` and
  `scope: TransactionDraftScope` (ADR-0019). Both are stamped internally by
  `TransactionBodySerializer` / `TransactionBuilder` and participate in equality, hash code,
  and `toString`. Mainnet draft construction remains available.
- **Breaking:** `ReadOnlyWallet.signTestnetFixtureTransaction` reads the bound draft and the
  declared `network` argument. It rejects a non-testnet draft, a declared-network mismatch, an
  unsupported scope, or an incompatible Phase 1 shape *before* parsing the mnemonic, and
  rejects any mnemonic that does not derive to `Phase1FixtureIdentity`'s cited payment-
  credential fingerprint *before* `Signing.sign`. Failures are
  `WalletError.SigningScopeViolation` with a typed `SigningScopeViolationReason`. The unused-
  parameter suppression is gone. The ADR-0018 `@ExperimentalKardanoSigningScope` opt-in is
  retained as a Kotlin-compiler signal; it still does not appear as a Swift compile-time
  gate. The new runtime checks do run for Swift callers of the compiled framework.
- **Breaking:** `:crypto` `Signing` requires `@OptIn(ExperimentalKardanoRawSigning::class)`.
  It remains a raw byte-signing primitive and cannot authorize transaction scope.
- The public landing page's skip-link target (`<main id="main-content">`) now has
  `tabindex="-1"`, so activating "Skip to main content" moves keyboard focus there in every
  browser, not just ones that already move focus to non-interactive scroll targets (W9-6,
  2026-08-22 pre-release audit).
- `README.md` and `site/README.md` no longer describe the GitHub Pages URL as "expected once
  enabled" — it was already live, confirmed via a direct fetch, so the wording now states the
  site is live and points readers who want certainty at Settings → Pages (W9-5).
- `docs/DECISIONS/0015-transaction-signing.md` §9's own result note no longer says Block 1.10c
  "remains open"; it now points at `docs/PHASE_1_PLAN.md`'s 1.10c entry, which every other
  document already described as complete (W4-1). `docs/DECISIONS/0017-transaction-submission-boundary.md`
  gained a dated result note recording that its deferred Blockfrost-submission/`:shared`-checkpoint
  work has since shipped, mirroring ADR-0015 §9's own pattern (W4-2). Both ADRs' original
  at-the-time-of-writing text is otherwise left unchanged.
- CI (`verify.yml`, `deploy-site.yml`) now pins every third-party GitHub Action `uses:` line to a
  full commit SHA with a version comment instead of a floating major-version tag, so a
  compromised or re-tagged upstream release can no longer silently change CI behavior (W9-2).
- `verify.yml` gained a `restricted-claim-scan` job: a plain grep/bash step (no new Action or
  dependency) that fails the build if a tracked doc/markdown/source file contains a banned word
  outside a short, individually-justified exclusion list (frozen historical records, the policy
  definitions themselves, and four narrow non-claim occurrences). This is a claim-language scan
  only, not secret/credential scanning (W9-3).
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
- `LovelaceDisplay.ada` (Playground-only display helper) now takes a `Lovelace` instead of a raw
  `Long`, so a negative amount is rejected at `Lovelace.of` construction time rather than being
  representable at all (W9-7, 2026-08-22 pre-release audit). No caller passed a raw negative value
  before this change; this closes the gap at the type level instead of leaving it as an untested
  assumption.
- **Breaking:** `ReadOnlyWallet.signTransaction` is renamed to
  `ReadOnlyWallet.signTestnetFixtureTransaction` and now requires an explicit
  `@OptIn(ExperimentalKardanoSigningScope::class)` at every call site (W7-1, ADR-0018). The name
  and the opt-in are a compiler/IDE-visible **intent signal that this entry point is scoped to
  the Phase 1 testnet/test-fixture demonstration flow, not general-purpose wallet signing** — see
  the new `ExperimentalKardanoSigningScope` annotation's own KDoc for exactly what this does and
  does not achieve. It is not a runtime check: it does not verify the mnemonic is the fixture,
  that the network is testnet, or that the supplied `TransactionDraft` was built for the declared
  network, and the opt-in requirement does not carry over as a Swift/iOS compile-time gate.
  ADR-0019 (same Unreleased window; see the `TransactionDraft` binding bullets above) later
  added those runtime checks without removing the opt-in. No
  compatibility typealias or deprecated wrapper is provided under the old name (pre-alpha). No
  cryptographic, transaction-building, provider, or signing behavior changed; `Network.MAINNET`/
  `BlockfrostNetwork.MAINNET` are unaffected.
- **Breaking:** `Hex.encode(bytes: ByteArray)` now returns `KardanoResult<String, HexError>`
  instead of a bare, unbounded, non-failable `String`, so it can reject an oversized `bytes` array
  (`HexError.EncodeInputTooLong`) the same way every other codec in this SDK
  (`Bech32.encode`/`decode`, `Cbor.encode`/`decode`, `Hex.decode`) already does, instead of being
  the one codec in the SDK with no upper bound on its input. Every internal call site (`:core`
  tests, `:wallet`, `:provider-blockfrost` tests, `:shared`'s Playground presenter) is updated in
  this same change. No compatibility overload is provided under the old signature (pre-alpha).

### Known limits

- Mainnet, imported wallets, general-purpose signing, and native-asset transaction construction are
  not implemented.
- iOS and JVM/Desktop share the codebase; Android is the Phase 1 runtime validation target.
- JVM signing artifacts are currently packaged for macOS hosts only.
