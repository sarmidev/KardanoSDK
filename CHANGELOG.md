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
  built from the visible Rust source. A staged rebuild harness
  (`crypto-signing-backend/scripts/`) and `native-rebuild-evidence.yml` now rebuild those
  eight targets into a fresh directory and compare them byte-for-byte; a mismatch is a
  failed job, not a reason to rewrite CHECKSUMS. The first harness commit (`6cb6810`)
  is historical review debt (module `target/` default, fail-open inspection). Later
  commits on `fix/native-build-and-platform-evidence` require a staging-owned empty
  `CARGO_TARGET_DIR`, remapped absolute source roots, a link-time
  `@rpath/libkardano_ed25519_bip32_signing.dylib` install name, fail-closed
  `nm`/`lipo`/`file` checks, and a pinned `macos-26` / Xcode 26.6 runner. Gate 1 is
  still NO-GO until local candidate hashes match a clean runner. macos-26 image
  `ANDROID_NDK*` defaults to `27.3.13750724`; the rebuild job now ignores those
  names and fail-closes on any NDK other than `27.2.12479018`. Python zip
  extract now restores NDK clang execute bits and Unix `clang -> clang-18`
  symlinks (CI `Exec format error` / `clang-18: command not found`). Darwin JVM candidates drop `LC_UUID` via
  `-Wl,-no_uuid` / `-Wl,-reproducible`. iOS candidate hashes already matched
  a clean `macos-26` runner on `ea01b12`.
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

- Explicit Blockfrost HTTP timeouts via Ktor `HttpTimeout` (already in `ktor-client-core`;
  no new dependency): connect 10s, request 30s, socket 30s. Timeout failures map to typed
  `Transport` errors. There is no Ktor `HttpRequestRetry` plugin. Android OkHttp is built
  with `engine { config { retryOnConnectionFailure(false) } }` so the effective Ktor
  OkHttp engine client has retry disabled (Ktor 3.5.2 reapplies `true` after a
  preconfigured client; a preconfigured client with retry disabled is kept as defense
  in depth). That is engine-level, distinct from the Ktor plugin. CIO and Darwin do
  not enable an equivalent automatic request replay. Coroutine cancellation is still
  rethrown.
- Blockfrost error `detail` is read from a bounded response-body prefix (500 characters
  publicly; at most 2004 UTF-8 bytes from the channel). A filled byte budget is not parsed
  as JSON; envelope `message`/`error` fields are capped to the same 500-character budget.
- `ProviderError.ResultTruncated(fetchedCount, cap)`: the typed failure when a paged UTxO
  query reaches the provider cap and a one-item probe of the next page is non-empty
  (production cap: 10_000 UTxOs). An empty probe — including HTTP 404, matching ordinary
  UTxO pagination — is a complete `Ok` at exactly the cap.
  A page larger than the requested count is `Deserialization`, not this variant.
- Playground operation lifecycle: a monotonic `flowGeneration` discards stale Funds/Build/Sign/
  Submit/diagnostic results after ResetFlow or an actual provider-configuration change; in-flight
  jobs are cancelled. Provider explorer UTxO and protocol-parameter loads also carry a request
  token (and the explorer address for UTxOs) so a result for address A cannot apply after the
  field shows B, and a repeated load cannot overwrite a newer one. Funds, Build, Sign, and
  Submit each carry their own request token so a repeated same-step request cannot be
  overwritten by a slower first call that still shares `flowGeneration`. Starting Funds
  clears Build/Sign/Submit (completed results included) and increments those tokens;
  starting Build clears Sign/Submit; starting Sign clears Submit — so Continue cannot
  advance on a stale later step after an upstream rerun. Wallet restore is
  synchronous and has no request token. ResetFlow converts in-flight
  diagnostic Loading values to Empty and keeps completed diagnostic results. Provider-backed
  results now carry `PlaygroundProviderMode` (`Mock` / `LivePreprod`) and that generation. The
  live Blockfrost client cache is dropped immediately on an actual project-id change and when
  live mode is disabled (the internal `PlaygroundProviderFactory.invalidateLiveCache`
  method), not only on the next lookup. The project id remains session-only (state plus an
  in-memory cache key) and is never persisted or logged.
- `PlaygroundPresenter.presentTxBuildError` now includes `InsufficientFunds`'s excluded
  native-asset UTxO count and lovelace when those fields are non-zero.
- Playground Compose semantics: headings on section/step titles; polite live regions for
  loading, success, and the honest informational stop; assertive live regions for errors;
  expanded/collapsed state plus expand/collapse actions on Technical details, Advanced,
  roadmap phases, and other disclosures.
- Public landing page hash targets (`#approach`, `#try-the-playground`, and the other section
  ids) reserve space under the sticky header via one `scroll-padding-top` offset
  (`--anchor-scroll-offset`), raised at the 860px and 560px breakpoints when header/nav wrap.

### Changed

- Android lint is now a CI gate (`:androidApp:lintDebug` and
  `lintRelease`, `warningsAsErrors`). Online freshness detectors
  (`GradleDependency`, `NewerVersionAvailable`,
  `AndroidGradlePluginVersion`) are disabled because coordinates are
  catalog-pinned, lockfiled, and SHA-256 verified. Adaptive icons gained
  a monochrome layer from the first-party mark; splash PNGs moved to
  `drawable-nodpi` / `drawable-night-nodpi`. Legacy square launchers
  were regenerated from the approved marks as a rounded-rect silhouette
  with 12.5% transparent padding (`scripts/generate_legacy_launcher_icons.py`).
  Adaptive icon layers were not changed. Owner should still glance at
  the pre-API-26 launcher tiles.
- Dependency locking and verification (2026-08-23): every lockable
  compile/runtime classpath uses `LockMode.STRICT` with per-project
  `gradle.lockfile`s; `gradle/verification-metadata.xml` records
  SHA-256 only. `crypto-signing-backend/rust-toolchain.toml` pins
  Rust `1.97.0`. Cargo directs are `ed25519-bip32 = "=0.4.2"` and
  `uniffi = "=0.29.5"`; documented rebuilds use `--locked`. Lock
  regeneration produced no diff; a tampered `junit` checksum failed
  the build and was restored.
- Crypto/native support review (2026-08-23, ADR-0020): Bouncy Castle
  `bcprov-jdk18on` 1.84 → 1.85.2 and JNA 5.17.0 → 5.19.1 after changelog
  review. `:crypto:jvmTest` (78) after the Castle bump;
  `:crypto-signing-backend:jvmTest` (4), `:crypto:jvmTest` (78), and
  `:wallet:jvmTest` (30) after the JNA bump. KotlinCrypto 0.8.0, IonSpin
  0.9.5, atomicfu 0.26.1, `ed25519-bip32` 0.4.2, UniFFI 0.29.x, and
  Material3 1.11.0-alpha07 stay pinned; ADR-0020 records why, the KAT
  evidence, and replacement criteria. No signing/hashing backend was
  replaced.
- Build-platform compatibility group (2026-08-23 review-fix): moved from
  the locally passing Gradle 9.7.1 / AGP 9.3.1 / API 37 pair to the
  official Kotlin 2.4.10 envelope — Gradle **9.5.0** (distribution
  SHA-256 `553c78f50dafcd54d65b9a444649057857469edf836431389695608536d6b746`),
  AGP **9.1.0**, compile/target SDK **36**, JetBrains lifecycle Compose
  **2.10.0**. API 37 is deferred (ADR-0021). Locks use
  `lockAllConfigurations()`; publisher checksum comparison is in
  `docs/DEPENDENCY_PROVENANCE.md`. Ktor stays 3.5.2. Compose Multiplatform
  stays 1.11.1 and Material3 stays 1.11.0-alpha07.
- Build-platform compatibility group (2026-08-23, historical Prompt 6
  commit 2): Gradle 9.7.1 / AGP 9.3.1 / API 37 / lifecycle 2.11.0. That
  pairing is superseded by the review-fix row above.
- **Breaking (pre-alpha):** `ProviderError.RemoteStatus` is now
  `RemoteStatus(code: Int, detail: String? = null)`. Existing source call sites that pass
  only `code` remain source-compatible because `detail` defaults to `null`. This is still
  a data-class shape change: generated `equals` / `hashCode` / `toString` / `copy` /
  `componentN` include `detail`. No binary compatibility and no exhaustive-`when`
  compatibility are claimed (pre-alpha).
- **Breaking (pre-alpha):** `ProviderError` gained the subtype
  `ResultTruncated(fetchedCount, cap)`. Existing exhaustive `when` expressions over
  `ProviderError` must add a branch. No binary compatibility is claimed (pre-alpha).
- **Breaking (pre-alpha):** `BlockfrostConfig` is no longer a `data class`. Equality is
  referential (identity), `toString` still redacts `projectId`, and `copy` / `componentN`
  are not generated. `equals` / `hashCode` no longer incorporate the project id, so
  collection-key and assertion-diff paths cannot reconstruct the key from those members.
  No current call site compared, hashed, copied, or destructured a config. The public
  `projectId` and `network` accessors are unchanged.
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
  document already described as complete (W4-1). The ADR header now matches that completed
  1.10c result note. `docs/DECISIONS/0017-transaction-submission-boundary.md`
  gained a dated result note recording that its deferred Blockfrost-submission/`:shared`-checkpoint
  work has since shipped, mirroring ADR-0015 §9's own pattern (W4-2). The ADR-0017 header and
  Non-goals now point at that shipped 1.11b/1.11c result note. Both ADRs' original
  at-the-time-of-writing decision text is otherwise left unchanged.
- `docs/PROJECT_BRIEF.md` now links the full delivery record to `docs/DELIVERY_RECORD.md`
  (W4-3). `docs/ROADMAP.md` remains the overview.
- Module README status lines now use the same factual wording as the root README /
  `docs/SECURITY.md` / `docs/PROJECT_BRIEF.md`: "Not independently reviewed" (W4-4). Provider
  READMEs keep the testnet/preprod qualifier.
- `docs/HANDOFF.md` is now the living resume (current context, recent sessions, active
  risks, branch-stack status). The previous full handoff is preserved verbatim at
  `docs/archive/handoff/2026-08-23-pre-curation.md` and checked by
  `scripts/check_handoff_archive.py` (W1-2).
- CI (`verify.yml`, `deploy-site.yml`) now pins every third-party GitHub Action `uses:` line to a
  full commit SHA with a version comment instead of a floating major-version tag, so a
  compromised or re-tagged upstream release can no longer silently change CI behavior (W9-2).
- CI Action pins were re-resolved live on 2026-08-23 and upgraded from the previous exact
  patch pins (checkout `v4.3.1`, setup-java `v4.9.1`, setup-gradle `v4.4.3`, configure-pages
  `v5.0.0`, upload-pages-artifact `v3.0.1`, deploy-pages `v4.0.5`) to maintained Node 24
  releases: checkout `v7.0.1`, setup-java `v5.7.0`, setup-gradle `v5.0.2`, configure-pages
  `v6.0.0`, upload-pages-artifact `v5.0.0`, deploy-pages `v5.0.0`. The previous pins were
  those patch releases, not the moving `v4` major tags named in the 2026-08-22 audit
  (`actions/checkout@v4` is `v4.4.0` as of this resolution). `gradle/actions` v6.3.0 is
  not adopted: v6 defaults to a separate commercial cache component and a Terms of Use
  gate that this commit does not accept. setup-gradle cache inputs are set explicitly to
  the v4.4.3/v5.0.2 defaults. upload-pages-artifact v3.0.1's floating
  `actions/upload-artifact@v4` transitive use is gone; v5.0.0 pins
  `actions/upload-artifact` to `bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` (v7.0.0)
  (W9-2 / NF-4).
- `scripts/check_action_pins.py` (and `scripts.tests.test_check_action_pins`) require every
  external workflow `uses:` to be `owner/name@<40-char lowercase SHA>` matching
  `scripts/action_pin_inventory.py`, and require recorded composite transitives plus those
  SHAs to appear in `docs/DEPENDENCY_REVIEW.md`. `verify.yml` runs the tests and the
  check in a dedicated `action-pin-scan` job.
- `verify.yml` gained a `restricted-claim-scan` job that runs the restricted-claim
  and archive unit tests, the HANDOFF archive byte check, then
  `scripts/check_restricted_claims.py`. The script classifies each phrase match on its
  own (never a whole-line exclusion), reports `path:line:column`, and prefers the
  longest phrase. Whole-file exclusions are limited to immutable archived
  snapshots and circular policy/test data. Historical wording in evolving ADRs
  and append-only logs is allowlisted per occurrence (path, physical line,
  line hash, phrase, and phrase occurrence). This is a claim-language
  scan only, not credential scanning (W9-3 / NF-5).
- `verify.yml` gained a `credential-scan` job that runs the Gitleaks helper /
  installer / allowlist tests, installs the Gitleaks CLI (`v8.30.1`,
  checksum-verified from the official GitHub release checksums file), and scans
  complete git history with redacted output. Allowlists are match-level only
  for the cited CIP-19 payment-credential hex **and** an exact repo-root path,
  including the helper that historically embedded that vector (W9-3).
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
