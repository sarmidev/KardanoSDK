# Kardano SDK - Handoff

## Purpose

This file is the living resume document for the owner, Cursor, ChatGPT, or another
assistant. Keep it current and short. Older implementation notes and session logs
are preserved verbatim under [docs/archive/handoff/](archive/handoff/README.md).

Update the recent-sessions section at the end of each work session. Do not silently
delete historical content; move it into a dated archive snapshot and extend
`scripts/check_handoff_archive.py`. The curation policy lives in
[docs/RELEASING.md](RELEASING.md).

## Current Project Context

Kardano SDK is an open-source Kotlin Multiplatform SDK for native Cardano mobile apps.

- Name: Kardano SDK.
- Package/group: `org.sarmidev.kardano`.
- Main targets: Android, iOS, JVM/Desktop.
- Current status: **Phase 0 and Phase 1 implementation are complete.** Phase 1 is the
  Android-primary, fixture-scoped, ADA-only preprod flow and the shared Playground.
  Active work is Phase 1 closure and funding readiness: public materials, contribution
  and release hygiene, pilot discovery, and Phase 2 architecture planning. No Phase 2
  protocol capability is implemented.
- Current Phase 1 limits: testnet/preprod fixture flow, ADA-only transaction
  construction, Android-primary runtime validation. No mainnet, imported wallets,
  general-purpose signing, or native-asset transaction construction.
- Strategic direction: Phase 2 is a loyalty/ticketing native-asset pilot with provider
  expansion, gated by an ADR, external problem validation, and a preserved-value
  transaction model. See `docs/PHASE_2_PLAN.md` and `docs/FUNDING_AND_PILOT_PLAYBOOK.md`.

Business goal:

> Build the first credible mobile-first KMP SDK for Cardano apps, focused on shared
> Android/iOS Cardano logic.

The full delivery record is [docs/DELIVERY_RECORD.md](DELIVERY_RECORD.md).
[docs/ROADMAP.md](ROADMAP.md) is the overview.

## Important Files

Read these first:

- `docs/PROJECT_BRIEF.md`
- `docs/DELIVERY_RECORD.md`
- `docs/ROADMAP.md`
- `docs/AI_WORKING_AGREEMENT.md`
- `docs/SECURITY.md`
- `docs/RELEASING.md`
- `docs/TESTING.md`
- ADR files under `docs/DECISIONS/`
- Cursor rules under `.cursor/rules/`
- Archived HANDOFF snapshot: `docs/archive/handoff/2026-08-23-pre-curation.md`

## Active Risks And Gates

- Signing-scope residual: a consumer who builds from a patched copy of the source can
  delete the ADR-0019 runtime checks. `Network.MAINNET` remains a public constant for
  address parsing and provider configuration. Preview and preprod are both
  `Network.TESTNET`. `@RequiresOptIn` does not appear as a Swift compile-time gate;
  the runtime `WalletError.SigningScopeViolation` checks do.
- Manual owner device pass still outstanding: TalkBack, VoiceOver, 200% font, 360dp,
  light/dark, in-flight Reset, Mock→Live→Mock, and landing keyboard/hash navigation.
- Live Blockfrost connect/socket timeouts still depend on the platform engine honoring
  `HttpTimeout`. OkHttp replay disablement is asserted on the effective Ktor 3.5.2
  engine client, not by inducing a live connection failure. Opt-in
  `BLOCKFROST_PROJECT_ID` live tests and the manual Android submit checkpoint remain
  the only live-network coverage.
- The Playground factory cache key is a second in-memory copy of the project id. It is
  not persisted or logged.
- iOS runtime execution of CIP-3 / signing vectors is still future verification
  (compile/link only on this host). Linux x86-64 JVM is promoted. Windows
  x86-64 JVM is candidate-only (W9-4).
- Still-open hygiene items outside this stacked batch: tag-triggered
  release CI (W4-5). Android lint Debug/Release is a CI error (W3-3
  closed). Owner should still glance at pre-API-26 launcher tiles.
  Pre-1.0 pins are accepted in ADR-0020 (W5-4).
- `gradle/actions` v6.3.0 is not adopted (proprietary cache component / Terms of
  Use). setup-gradle stays on v5.0.2. See `docs/DEPENDENCY_REVIEW.md`.
- Restricted-claim and full-history Gitleaks scans now run in CI. They are not a
  substitute for an owner-authenticated GitHub secret-scanning pass.

## Branch-Stack Status

Stacked remediations, each additive (no amend / no force-push):

| Prompt | Branch | Tip (short) | Role |
|---|---|---|---|
| 1 | `fix/pre-release-core-contracts` | `43a30e0` | Parser/hash/wallet-throw bounds; audit baseline |
| 2 | `fix/signing-scope-enforcement` | `a632b7d` | ADR-0019 draft binding and fixture-identity checks |
| 3 | `fix/playground-operation-lifecycle` | `a34afdc` | Generation/token lifecycle and accessibility semantics |
| 4 | `fix/provider-boundaries-and-timeouts` | `3936047` | Config identity, remote detail, UTxO cap, HTTP timeouts. Independent review passed; PR-ready. |
| 5 | `fix/release-docs-and-scanners` | `90fe0ee` | Docs, HANDOFF archive, restricted-claim scanner, Gitleaks. Independent review passed; PR-ready. |
| 6 | `fix/build-and-ci-reproducibility` | `2b85ed7` | Independent review passed; PR-ready. Verify run `32656606067` green. |
| 7 | `fix/native-build-and-platform-evidence` | Legal-evidence packet | Linux Gate 2 promotion GO at `58f82a2`. Windows x86-64 JVM is candidate-only (JNA `win32-x86-64/`). PE evidence A/B `32724622118` at `73da4f4`; independent PE technical review is COMPLETE at `c65a20a`. Phase C remains NO-GO solely pending Identus #226 (PE re-review is no longer a blocking gate). Non-counsel legal-evidence packet added at/after `c65a20a` (`NOTICE`, `LICENSES/`, `docs/LEGAL_REVIEW.md`, `docs/evidence/`); counsel review and Identus #226 remain open. |

`origin/main` is behind this stack. Do not merge from this session.

## Recent Sessions

### Last Session Summary

Date: 2026-08-24

- **Legal-evidence packet (non-counsel scope) on
  `fix/native-build-and-platform-evidence`, starting from clean tip
  `c65a20a`.** Added root `NOTICE`; `LICENSES/` (verbatim `Apache-2.0.txt`,
  `MPL-2.0.txt`, `ISC-libsodium.txt` fetched 2026-08-24 from each own
  canonical URL; `BouncyCastle.txt` is a **manual transcription**, not a
  fetched file — see the 2026-08-24 correction below and
  `LICENSES/README.md` for source/SHA-256 detail); `docs/LEGAL_REVIEW.md`
  (an owner/counsel evidence checklist and template, not legal advice or
  approval); and deterministic generated inventories under `docs/evidence/`
  (`scripts/generate_legal_evidence.py`): per-module Gradle
  source/runtime/test-only classification from `*/gradle.lockfile`, a
  `cargo metadata --locked` package graph for the signing backend (then
  superseded by the per-target-triple `cargo tree` inventory below), the 5
  committed UniFFI-generated binding files, an exact 9-row
  `crypto-signing-backend/CHECKSUMS.sha256` cross-check, and a static
  Maven-native-carrier catalog (Identus/IonSpin/LazySodium/libsodium).
  `scripts/check_release_evidence.py` (25 new unit tests plus a live run)
  fails closed on a broken `NOTICE`/`LICENSES/` reference, a
  native-inventory mismatch, stale generated evidence, or a generic
  placeholder in `docs/LEGAL_REVIEW.md`; it passed on this tree.
  `docs/THIRD_PARTY_NOTICES.md` is reconciled: JNA and the
  `ed25519-bip32`/`cryptoxide` dual licenses (`Apache-2.0 OR
  LGPL-2.1`/`MIT OR Apache-2.0`) now record an explicit, but still OPEN and
  unaccepted, proposed Apache-2.0 election;
  the single-license `uniffi` crate's MPL-2.0 file-level obligation (linked
  into all 9 native artifacts) is reviewed the same way as
  `lazysodium-android`; and the page states explicitly that the Windows
  signing-backend candidate DLL and the Identus `apollo` derivation-backend
  Windows native library are **not** distributed. `RELEASING.md`,
  `TESTING.md`, `CHANGELOG.md`, and `docs/AUDIT/2026-08-23-final-pre-release-audit.md`
  §8 point at the new packet without restating or changing any prior
  finding. **This work does not mark Prompt 7, the Windows candidate, or any
  release as GO.** Counsel review and upstream `hyperledger-identus/apollo`
  issue #226 remain open gates, recorded as such (not as "TBD") in
  `docs/LEGAL_REVIEW.md`.
- **Legal-evidence packet NO-GO fixes (same branch, four commits above
  preserved as-is).** An independent review returned NO-GO on the packet
  above for eight factual/fail-closed gaps; all eight are fixed in later
  commits, not by amending the four commits above. (1) The packet's implicit
  "no MIT-only distributed component" framing was wrong — `LICENSES/MIT.txt`
  and `LICENSES/Unicode-3.0.txt` (both fetched verbatim from spdx.org, hash
  in `LICENSES/README.md`) are now committed, and
  `scripts/license_catalog.py` records a per-coordinate election for every
  Gradle runtime dependency, including confirming `org.slf4j:slf4j-api` is
  MIT-only (no dual-license `OR` clause in its POM) and that JNA's
  `Apache-2.0 OR LGPL-2.1` election does not cover it. (2) The old "69
  packages, 63 linked" single-closure heuristic is replaced by
  `cargo tree --locked --target <triple> -e <edges> --prefix none` run
  separately for each of the 9 committed target triples (Darwin 2: macOS
  arm64/x86-64; Android 4: arm64-v8a/armeabi-v7a/x86/x86_64; iOS 2:
  arm64/arm64-simulator; Linux 1: x86-64) in
  `docs/evidence/cargo_dependency_inventory.json`; each triple separately
  reports `linked_into_compiled_artifact` (32 or 33, depending on
  Android-only deps), `proc_macro_and_support_closure` (12, never traversed
  as linked), `host_build_dependency_only` (1), and `dev_dependency_only`
  (0), over 46 distinct package/version/source combinations total, 33 of
  them linked into at least one target; `unicode-ident`'s `(MIT OR Apache-2.0)
  AND Unicode-3.0` compound expression and the three MIT-only linked crates
  (`bytes`, `cargo_metadata`, `zmij`) are called out explicitly rather than
  assumed covered by a blanket dual-license election. (3) Gradle modules are
  now discovered by parsing `settings.gradle.kts` (not a static list); the
  distribution scope statement in `docs/LEGAL_REVIEW.md` §3 is explicit that
  Desktop MSI/DEB/DMG installers are not planned for this release and their
  runtime inventory is not claimed complete; JNA's 25 embedded
  `libjnidispatch` natives, Skiko's per-platform dylibs, and the Identus/
  IonSpin/LazySodium native carriers are recorded with embedded path/hash/
  platform notes in `docs/evidence/maven_native_carriers_inventory.json`, and
  JNA is explicitly documented as "source-plus-embedded-native-carrier", not
  Source. (4) `docs/LEGAL_REVIEW.md` §6/§6b no longer state that embedded
  UniFFI or MPL handling is "satisfied"; both are marked as OPEN counsel
  determinations, the 5 generated binding files are discovered dynamically
  (`discover_uniffi_generated_files()`), and the Identus carrier statement
  shows Apache-2.0-declared plus embedded/MPL uncertainty tied to issue #226
  without claiming an exact source-file mapping. (5)
  `scripts/generate_legal_evidence.py`/`scripts/check_release_evidence.py`
  now reject symlinks among evidence inputs, parse `Cargo.lock`/
  `CHECKSUMS.sha256` byte-strictly (malformed lines, duplicate
  paths/coordinates, and CRLF all fail), recompute every named digest in
  `LEGAL_EVIDENCE_DIGEST.txt` and its exact `licenses_files=`/
  `expected_evidence_files=` file sets, and run in two modes:
  `ci-structural` (default; permits the four named `ALLOWED_OPEN_GATE_MARKERS`
  strings, rejects everything else including lowercase `open`/`pending` and
  an unsupported "approved" claim) and `release` (additionally fails while
  any of those four markers remains — expected to fail today). (6)
  `docs/evidence/scope_binding.json` records the evidence-generation-time
  `subject_commit`/`subject_tree` (the HEAD the packet was generated
  against) separately from whatever commit and tree end up containing this
  file, documented as non-self-referential by construction; `docs/LEGAL_REVIEW.md`
  §14 adds an explicit "OPEN — pending per-election reviewer acceptance" row
  covering the 3 elections and 3 compound expressions individually. (7)
  `LICENSES/README.md` and `docs/evidence/bouncycastle_license_source.json`
  now consistently call `LICENSES/BouncyCastle.txt` a **manual transcription**
  of the licence paragraphs rendered at
  `https://www.bouncycastle.org/licence.html`, not fetched/verbatim bytes;
  the fetched HTML snapshot is separately committed at
  `docs/evidence/license-sources/bouncycastle-licence-2026-08-24.html` and
  both `source_html_sha256` and `transcription_sha256` are recorded, with
  transcription faithfulness left as an explicit OPEN counsel field. (8)
  Every `cargo metadata`/`cargo tree` call hashes
  `crypto-signing-backend/Cargo.lock` immediately before and after and raises
  a fail-closed error if it changed; `docs/LEGAL_REVIEW.md` §13 documents
  which two generators need read-only network/cache access (Gradle POM
  resolution, a dated static Maven-native-carrier table) and which do not.
  New unit tests cover both scripts (conditional target deps, proc-macro
  descendants, duplicate name/version packages, CRLF/symlink/duplicate-key/
  malformed-lock corruption, missing `LICENSES/README.md`, lowercase
  placeholders, blank table cells, and `ci-structural` vs `release` mode
  behavior). This fix round still does not mark Prompt 7, the Windows
  candidate, or any release as GO, and does not start Prompt 8. **A second
  independent review found this round incomplete — see the next bullet.**
- **Legal-evidence packet NO-GO fixes, round 2 (same branch, prior legal
  commits preserved as-is).** A second independent review found the round-1
  fixes above still incomplete on 10 further points; this round addresses
  the concrete engineering gaps: (1) Gradle license resolution no longer
  depends on a pre-populated local cache — `scripts/license_catalog.py`
  (hand-curated) plus a new, mechanically harvested
  `scripts/license_catalog_harvested.py` (`scripts/harvest_gradle_pom_licenses.py`)
  together cover all 298 runtime coordinates with zero unresolved, verified
  by new `ColdGradleCacheTests` that point `GRADLE_USER_HOME` at an empty
  temp directory, and a new CI step does the same in `verify.yml`;
  `gradle_license_inventory()` now raises (fails generation) instead of
  recording a silent unresolved list. (2) Every target-linked Cargo package
  with a non-single-license SPDX expression (27, not the round-1 packet's 3
  — a new `parse_spdx_expression()` also fixed a real bug where `cryptoxide`'s
  legacy `MIT/Apache-2.0` slash syntax was silently treated as single-license)
  now has an explicit, catalog-backed election row
  (`scripts/cargo_election_catalog.py`,
  `cargo_dependency_inventory.json`'s new `license_elections` section); a
  target-linked package missing from that catalog fails generation (no
  blanket election), and `check_release_evidence.py --mode release` fails
  while any row is not `ACCEPTED`. A previously cited `r-efi` compound-license
  entry did not actually exist in this crate's dependency graph and is
  removed. (3) `docs/evidence/` freshness checking is now a full recursive
  walk (`check_evidence_tree_exact()`), rejecting nested extra files and
  symlinked directories, not just a top-level JSON glob. (4)
  `docs/evidence/maven_native_carriers_inventory.json` now records each
  carrier's own `artifact_sha256` and, for every embedded native member, its
  own SHA-256 plus inferred platform/arch (not just path/size), a
  `distribution_status` enum
  (`resolved_runtime_dependency`/`transitively_available`/
  `redistributed_by_kardano`/`not_in_first_release_scope`), and a corrected
  JNA embedded-native count of 27 (a full zip-member enumeration found two
  AIX variants the round-1 catalog missed); Skiko is explicitly
  `not_in_first_release_scope`, not `redistributed_by_kardano`, since no
  Desktop installer ships in this release. (5) `LICENSES/README.md` is now a
  hard-required file for the checker, blank required table cells in
  `docs/LEGAL_REVIEW.md` now fail instead of passing through silently, and
  the new election rows are schema-validated (status must be an exact
  `OPEN`/`ACCEPTED`/`NOT_APPLICABLE` enum; `ACCEPTED` requires a non-empty
  reviewer and an ISO-8601 date). (6) `memchr`'s `Unlicense OR MIT`
  expression gets no proposed election; `LICENSES/Unlicense.txt` is
  committed and cited in `NOTICE` specifically because no MIT election has
  been accepted for it. (7) This audit file's own round-1 addendum
  overclaimed "all are fixed" when a second review found more gaps — see
  its corrected §8.1/§8.2 split. (8) `docs/evidence/scope_binding.json` is
  no longer written in the same commit as the evidence it describes (a
  self-reference that could never independently prove anything — the
  checker regeneration would always trivially "pass" by rewriting the
  binding to whatever `HEAD` is right now). It is now a two-commit seal:
  `generate_legal_evidence.py` (no flag) writes every other evidence file
  against the current, still-uncommitted `HEAD` (the immutable
  subject-source commit); after that is committed,
  `generate_legal_evidence.py --seal` reads back that commit's own hash and
  immediate parent, records a SHA-256 of every evidence file's bytes, and
  writes `scope_binding.json` — committed separately as the seal commit.
  `check_release_evidence.py`'s new `check_scope_binding_seal()` verifies
  this purely from git history (commit/tree existence, exact
  immediate-parent ancestry, `evidence_commit` reachable from `HEAD`) plus
  a byte-for-byte cross-check against both the current worktree and
  `git show <evidence_commit>:<path>` — never by regenerating and
  comparing keys. (9) Cargo network access is now bounded to one explicit
  `cargo fetch --locked` bootstrap step in `verify.yml`; every Cargo
  invocation inside the generator itself now also passes `--offline`
  (`cargo metadata --locked --offline`, `cargo tree --locked --offline`),
  so generation can only read the registry cache that bootstrap step
  already populated, and `CARGO_NET_OFFLINE=true` is set for every step
  that runs the generator or its tests as a second, independent guard.
  `verify.yml` also now diffs the ENTIRE tracked worktree (not just
  `docs/evidence/`) before vs. after the whole legal-evidence job and
  fails on any unexpected mutation outside `docs/evidence/`, on top of the
  existing per-Cargo-invocation `Cargo.lock` hash guard. This round still
  does not mark Prompt 7, the Windows candidate, or any release as GO, and
  does not start Prompt 8.
- **Legal-evidence packet NO-GO fix: fail-closed live bcprov verification
  (same branch, prior legal commits preserved as-is).** A 2026-08-25
  independent review found `java_class_version_evidence.json`'s live
  verifier used the same "cold local Gradle cache is a harmless no-op"
  pattern `maven_native_carriers_inventory()` uses, but this repo's own
  legal-evidence-scan CI job never populates a Gradle cache at all -- so
  the check silently returned success with nothing actually verified on
  the one job it needed to be authoritative in. Fix:
  `cross_check_java_class_version_evidence_against_local_cache()` is
  replaced by `live_verify_java_class_version_evidence()`, which always
  resolves an ACTUAL resolved jar to scan -- an explicit `--bcprov-jar`
  path, the `KARDANO_LEGAL_EVIDENCE_BCPROV_JAR` environment variable, or
  (the default) `fetch_and_verify_bcprov_jar()`'s pinned-host
  (`repo1.maven.org`, refuses any redirect elsewhere),
  SHA-256-and-size-verified download from Maven Central -- no skip branch
  remains. The pinned coordinate/URL/hash/size
  (`org.bouncycastle:bcprov-jdk18on:1.85.2`, 10280518 bytes, sha256
  `986b0fb92ec10e0c66b43e036ce0077e6150cfaecd1db9fb92b56672e157afe5`) is
  independently confirmed against Maven Central's own directory listing
  and published `.jar.sha256` sidecar, matching the value already recorded
  in `docs/DEPENDENCY_PROVENANCE.md` before this fix. `verify.yml`'s
  `legal-evidence-scan` job gains one new bootstrap step (immediately
  after the existing Cargo `fetch --locked` step) that fetches+verifies
  the jar once and exports its path via `KARDANO_LEGAL_EVIDENCE_BCPROV_JAR`
  for every later step in that job to reuse, so it is fetched from the
  network exactly once per job despite the generator and checker each
  running several times. New tests cover a missing explicit/env-var path,
  a wrong sha256/size/redirect-host, a truncated/padded download, sidecar
  agreement and best-effort-ignored sidecar failure, and an explicit
  proof (mocked failing fetch, no explicit path, no env var) that there is
  no silent-skip branch left at either the generator or the checker. This
  fix still does not mark Prompt 7, the Windows candidate, or any release
  as GO, and does not start Prompt 8.
- **Legal-evidence packet: two Medium bcprov-fetch findings (same branch,
  same fetch this round's own fail-closed fix introduced).** A
  2026-08-25 follow-up independent review found the freshly added Maven
  Central fetch itself had two provenance/write gaps. (1) It validated
  only the request/response *hostname*, and its redirect handler
  explicitly allowed a same-host redirect through unchanged -- a URL
  with an unexpected port/query/fragment/userinfo, or a same-host
  redirect to a different path/version, was never checked at all. Fix:
  `_validate_pinned_artifact_url()` requires the request URL AND the
  actual final response URL to be byte-identical to the one pinned
  `https://repo1.maven.org/...` URL (exact scheme, host, HTTPS default
  port only, exact coordinate/version/filename path, no query/fragment/
  userinfo), checked before any network I/O and again on the response;
  `_NoRedirectHandler` (replacing the old host-allowlist handler) refuses
  EVERY HTTP redirect outright, including one to the identical scheme/
  host/port/path, so a redirect loop is moot -- the first hop already
  fails closed. (2) The verified bytes were written with a plain
  `Path.write_bytes()` (`O_CREAT | O_TRUNC`, no `O_EXCL`), which follows
  and overwrites through a pre-existing symlink at the destination path,
  and a separate `is_symlink()` check afterward is a check-then-act
  TOCTOU race, not a fix. Fix: `_create_exclusive_file()` opens the
  destination with `os.open(..., O_CREAT | O_EXCL | O_WRONLY
  [| O_NOFOLLOW])` in one atomic syscall (refuses to create over an
  existing file, symlink to anywhere, or directory, with no separate
  check-then-write window), writes every byte through a new
  `_write_all_to_fd()` retry loop (handles both a partial `write()` and
  `InterruptedError`/EINTR), and removes any partially written file on
  failure. Both fixes run before the SHA-256/size check, so a correct
  hash can never override a provenance failure. New tests cover: every
  redirect variant (HTTP downgrade, different path/version/host/port/
  query/fragment/userinfo, same-URL "loop") on the handler directly, the
  URL validator's own scheme/host/port/path/query/fragment/userinfo
  rules, `_fetch_url_bytes()`'s pre-request rejection and post-response
  URL re-validation (including a response with the exact correct bytes
  but a drifted URL), and `_create_exclusive_file()`/`_write_all_to_fd()`
  against a pre-existing file/symlink/dangling-symlink/directory, a
  simulated race, a write failure with cleanup, and partial/EINTR write
  retries -- confirming the symlink target's own content is left
  byte-for-byte unchanged in every rejected case. This fix still does not
  mark Prompt 7, the Windows candidate, or any release as GO, and does
  not start Prompt 8.
- **Gate 3 Windows x86-64 JVM (candidate-only) on
  `fix/native-build-and-platform-evidence`.** Linux promotion GO at
  `58f82a2`. JNA 5.19.1 resource is
  `win32-x86-64/kardano_ed25519_bip32_signing.dll`. Fail-closed PE32+
  verifier now also requires: import descriptors + all-zero terminator
  strictly inside `DataDirectory[IMPORT]` (zero padding only);
  independent 64-bit ILT/IAT arrays with mandatory terminators and
  identical pre-relocation name/ordinal semantics; IAT array including
  terminator inside `DataDirectory[IAT]`; export header, tables, DLL
  name, and export strings wholly inside `DataDirectory[EXPORT]`
  (function RVAs outside that span; forwarders rejected); debug
  REPRO/POGO payloads parsed against Microsoft PE/COFF Debug Type
  (REPRO empty or `uint32` length + 32-byte hash) and MSVC
  `coffgrp` signatures `ZERO`/`LTCG`/`PGI`/`PGO`/`PGU` (CODEVIEW/PDB
  rejected; run `32724069174` showed candidate POGO `ZERO`);
  resource structural interval registry (exact same-kind
  reuse only; partial overlap and cycles rejected); TLS
  callback array NUL-terminated with executable non-writable targets.
  `windows-2022` jobs select exact MSVC `14.44.35207` /
  `link.exe` `14.44.35228.0` and Windows SDK `10.0.26100.0` (required
  include/lib/bin paths; drift fails). Hosted `ImageVersion` is
  recorded and is not an immutable-image claim. CHECKSUMS stays 9
  rows. Prior PE artifacts (`32719231997` at `7f2cc78`;
  `32720083778` at `bc98c2a`; `32722013030` at `6e5bb97`; failed
  payload-parse run `32724069174` at `f1e44f2`) are superseded and
  must not be reused for re-review. Fresh independent A/B at `73da4f4`
  / run
  [32724622118](https://github.com/sarmidev/KardanoSDK/actions/runs/32724622118):
  A==B SHA-256
  `d0f36f6110f1662bb0c9998afb5598bebc4dc35c6abdc41865ab0fc4d7d905cc`
  (263680 bytes; same candidate bytes as `32715104620`). Artifacts A
  `9519072053`, B `9519114103`, report `9519211566`, expire
  2026-09-07. Sign export RVA `0x42c0` (ordinal 67). Observed
  `IMAGE_DEBUG_DIRECTORY`: type 13 POGO/coffgrp `SizeOfData=772`
  `AddressOfRawData=0x37b7c` `PointerToRawData=0x36f7c`
  payload SHA-256
  `61fa6e6b20425e1cde52d663e5e3a90b534c6faea9a98ea3403506f0142861a4`
  (`ZERO` + 40 entries, head `0000000000100000506202002e746578`);
  type 16 REPRO `SizeOfData=36` `AddressOfRawData=0x37e80`
  `PointerToRawData=0x37280` payload SHA-256
  `9159c153358b044f594e064382c04264a6c4a580a1d8fbda1b7df62c6e6d0a1c`
  (MSVC `uint32` length 32 + 32-byte hash; hash SHA-256
  `f4aba6dd5cae4dee0299896d3d4a1af18f62a3509c25aa499b63137fa009ada2`).
  Selected toolchain on the runner: MSVC `14.44.35207`
  `Hostx64/x64` `link.exe` Version `14.44.35228.0`; Windows SDK
  `10.0.26100.0` (`Include`/`Lib`/`bin` asserted);
  `ImageOS=win22`; `ImageVersion=20260818.277.1`.
  `:crypto-signing-backend:jvmTest` BUILD SUCCESSFUL. Linux
  [32724622312](https://github.com/sarmidev/KardanoSDK/actions/runs/32724622312),
  Native
  [32724622162](https://github.com/sarmidev/KardanoSDK/actions/runs/32724622162),
  Verify
  [32724622109](https://github.com/sarmidev/KardanoSDK/actions/runs/32724622109)
  were green at PE evidence tip `73da4f4`. A later docs-only tip
  records these IDs; reuse the `73da4f4` run for PE re-review, not
  the docs-commit workflows. `:crypto`/`:wallet` JVM tests remain
  blocked by `bip32-ed25519` 1.8.8 missing `win32-x86-64` (Identus
  #226). Identus is not being built. Phase C promotion is NO-GO
  pending independent PE re-review. Do not merge/tag,
  download/promote the DLL, or start the legal packet.
  **Historical/superseded note (added later, not rewriting the entry
  above):** the "pending independent PE re-review" clause reflects this
  session's state only. The independent PE (native-artifact structural)
  technical review is now COMPLETE at `c65a20a` (see row 7 above and
  `docs/LEGAL_REVIEW.md` §14/§15); it is no longer a blocking gate.
  Completion of that technical review is not a legal approval and does
  not promote the Windows candidate or imply any DLL is distributed.
  Phase C / the Windows candidate remain NO-GO solely because of the
  still-open upstream `hyperledger-identus/apollo` issue #226 (Identus
  full build-availability gap), plus counsel review, which are the only
  remaining full-path blockers.

- **Native rebuild evidence on `fix/native-build-and-platform-evidence`.**
  Gate 1 is GO at `d09db44`. Gate 2 Linux x86-64 JVM uses JNA prefix
  `linux-x86-64/` and a fail-closed ELF64 verifier (ET_DYN, EM_X86_64,
  `e_version == EV_CURRENT`, allowlisted `DT_NEEDED`, exact SONAME, no
  RPATH/RUNPATH, no build-id, no `.debug_*` / `.zdebug_*` /
  `.gnu_debuglink`, exact `.dynsym` sign export, full-string `GLIBC_*`
  labels compared as tuples against `(2, 35, 0)`, Verneed/Vernaux bound
  to one `SHT_GNU_verneed` with terminal-zero/overlap/cycle checks,
  canonical section 0, one `.dynamic`/`PT_DYNAMIC` with exact
  offset/vaddr/filesz/memsz/align, `.dynstr.sh_size == DT_STRSZ`,
  `DT_VERSYM` bound to `.gnu.version`). Path policy is a raw-byte
  search for documented build roots at any offset plus a slash-byte
  scan through NUL/control/whitespace/EOF. Invalid UTF-8 candidates
  fail when they contain a forbidden root or look like an unapproved
  absolute path; `/proc` is a runtime prefix. Rebuilds run only on
  pinned `ubuntu-22.04`
  (ImageOS `ubuntu22`) with rustc 1.97.0 / `x86_64-unknown-linux-gnu`.
  Two independent jobs plus JVM KAT must match; promotion waits for
  re-review GO. Versym indices resolve uniquely; arithmetic is
  `UINT64_MAX`-checked; raw known roots use a following-byte boundary.
  Versym 0, canonical dynsym 0, globally unique `vna_other`/`vd_ndx`,
  and `readelf --dyn-syms --wide` sign records coupled to the parsed
  sign Versym. Phase C promotion from run `32678079715` (artifacts
  `9503309381` / `9503308946` / `9503350346`, expire 2026-09-07)
  added the ninth CHECKSUMS row
  `cb4390996d30cb9a6f64ad4cbc1bd301d4400dff0806a41829d574cd1f1b4ed5`.
  Device runtime remains historical (W5-2). Windows x86-64 JVM is
  already in progress as candidate-only Gate 3 work. Do not merge/tag.
- **Merge-ref seal exception tightened to be GitHub-event-bound (same
  branch, after merging `main`/PR #14).** A later independent review
  found the `pull_request` merge-ref exception in
  `check_scope_binding_seal()`/`_effective_seal_tip()` accepted a
  two-parent commit by TREE SHAPE alone (any parent whose own first
  parent was `evidence_commit`, with a matching tree) and only relied on
  `check_full_source_scope_seal()`'s unconditional full-tree diff as a
  backstop -- it could not itself distinguish a genuine GitHub
  merge-ref from an octopus merge, swapped/unrelated parents, or a
  fabricated same-tree candidate. Fix:
  `_github_pull_request_merge_head()` now requires the CURRENT
  `GITHUB_EVENT_NAME == "pull_request"` plus every one of
  `GITHUB_EVENT_PATH`/`GITHUB_SHA`/`GITHUB_REPOSITORY`/`GITHUB_BASE_REF`/
  `GITHUB_HEAD_REF` set; a readable, valid (no duplicate key) event
  payload; `GITHUB_SHA == HEAD`; same-repository `base`/`head` (no fork
  exception); `main` base ref; matching head ref; `pull_request.
  merge_commit_sha` (when present) equal to `HEAD`; `HEAD`'s exact two
  parents matched, in exact GitHub order, against the event's own
  `base.sha`/`head.sha`; and a byte-identical merge tree. Any doubt --
  missing env, unreadable/malformed/duplicate-key event, wrong
  repo/ref/SHA, wrong parent order, or a tree mismatch -- denies the
  exception and falls back to the strict "HEAD's own first parent must
  be `evidence_commit`" path, which a genuine merge commit fails.
  `check_full_source_scope_seal()` is kept as GitHub-event-independent
  defense in depth, documented as not itself binding the exception to
  the event. `scripts.tests.test_check_release_evidence
  .ScopeBindingSealCheckTests` gained the positive GitHub shape plus
  every named adversarial escape (octopus/one-parent, swapped/unrelated
  parents, a genuine tree mismatch, a forged same-tree candidate built
  with `git commit-tree` using the wrong parent order, wrong/stale
  base/head/event SHAs, a stale `GITHUB_SHA`, a wrong repository/ref, a
  fork-repository head, a post-seal commit named as the PR head, and no
  event env at all). This round also merges `main` (PR #14, `34c174b`)
  into this branch with a normal merge commit (no rebase/squash) and
  freshly regenerates+reseals the Prompt 7 evidence packet against the
  merged tree plus the hardening code itself. Still does not mark
  Prompt 7, the Windows candidate, or any release as GO, and does not
  start Prompt 8.
- **Build and CI reproducibility on `fix/build-and-ci-reproducibility` (stacked on
  Prompt 5 `90fe0ee`).** The original five commits remain. Review-fix
  commits move the toolchain to the official Kotlin 2.4.10 envelope
  (Gradle 9.5.0 / AGP 9.1.0 / SDK 36 / lifecycle 2.10.0; API 37 deferred
  in ADR-0021), lock every configuration, record publisher checksums,
  scan merge-parent diffs, parse Action pins with Psych, and permanently
  run Verify on `push` to `fix/**`. Legacy square launchers were
  regenerated as a rounded-rect silhouette. Android lint Debug/Release
  is a CI error (`warningsAsErrors`); that lint-CI finding is **closed**.
  Verify run `32654915900` (head `0786237`) failed on Ubuntu and
  macOS-arm64: four Maven Central parent/BOM metadata files missing
  from `gradle/verification-metadata.xml`. Run `32655202142` (head
  `5201d63`) is **green** (all six jobs):
  https://github.com/sarmidev/KardanoSDK/actions/runs/32655202142
- **Release docs and scanners on `fix/release-docs-and-scanners` (stacked on Prompt 4
  `3936047`) — four original commits complete, plus review-fix commits.**
  - **Commit 1 — documentation reconciliation (`cb7b40d`).** ADR-0015 header now
    matches the completed 1.10c result note. ADR-0017 header and Non-goals point
    at the shipped 1.11b/1.11c result note. `PROJECT_BRIEF` links
    `DELIVERY_RECORD` directly. Module README status lines use "Not independently
    reviewed"; provider READMEs keep the testnet/preprod qualifier. Audit §7
    records the new status pointers.
  - **Commit 2 — HANDOFF curation (`8854146`).** Historical implementation and
    session content preserved verbatim in
    `docs/archive/handoff/2026-08-23-pre-curation.md`. Coverage is checked by
    `scripts/check_handoff_archive.py`.
  - **Commit 3 — restricted-claim scanner (`fe7db78`).**
    `scripts/check_restricted_claims.py` replaces the inline `verify.yml` grep.
    Classification is per match; output is `path:line:column`; longest phrase
    wins.
  - **Commit 4 — full-history Gitleaks (`d62a8ae`).** Checksum-verified CLI
    installer (`v8.30.1`). CI checkout uses `fetch-depth: 0`.
  - **Review-fix 1 — scanner tightening (`641a5c3`).** Root-exact Gitleaks
    allowlist including the helper path; sentence-boundary negation;
    Markdown-emphasis matching; `git ls-files -z`; installer refuses dest
    symlinks and world-writable archive members.
  - **Review-fix 2 — archive, CI, and docs (`76dc040`).** Byte-level archive
    restore/hash; path-scoped `.gitattributes` for the archive trailing blank
    line; CI runs the scanner/archive tests before scans.
  - **Review-fix 3 — occurrence allowlist and installer writes (`857ef82`).**
    Evolving ADRs and the append-only Phase 1 log are scanned; historical
    wording is allowlisted per occurrence. Hyphen compounds are not exempt.
    Suffix matching is case-insensitive. The installer loops `os.write` to
    completion and sets mode `0755` on the open temp descriptor only.
  - **Review-fix 4 — line-numbered occurrence keys (this commit).** The
    allowlist key is path + 1-based physical line + line SHA-256 + phrase +
    phrase occurrence. Duplicating or shifting an allowlisted line fails
    until the allowlist is re-reviewed.

### Session Summary (Provider boundaries and timeouts)

Date: 2026-08-23

Prompt 4 on `fix/provider-boundaries-and-timeouts` (three original commits plus
review-fix commits, stacked on Prompt 3 `a34afdc`). `BlockfrostConfig` uses identity
equality; `RemoteStatus` carries optional body `detail`; an exact-cap non-empty UTxO
probe is `ResultTruncated`; explicit Ktor `HttpTimeout` (10s/30s/30s); no Ktor
`HttpRequestRetry`; Android OkHttp effective `retryOnConnectionFailure` is false.
Full session text: [archived HANDOFF](archive/handoff/2026-08-23-pre-curation.md).

### Session Summary (Playground operation lifecycle)

Date: 2026-08-23

Prompt 3 on `fix/playground-operation-lifecycle`. Operation generations, request
tokens, provider-mode provenance, accessibility semantics, and upstream-rerun
invalidation of downstream guided steps. No SDK protocol behavior changed. Full
session text is in the archive.

### Session Summary (Signing-scope enforcement)

Date: 2026-08-23

Prompt 2 on `fix/signing-scope-enforcement`. ADR-0019 binds `TransactionDraft`
network/scope; `signTestnetFixtureTransaction` enforces testnet + Phase 1 shape +
cited fixture identity before `Mnemonic.parse` / `Signing.sign`. Full session text
is in the archive.

### Session Summary (Pre-release core contracts)

Date: 2026-08-23

Prompt 1 on `fix/pre-release-core-contracts`. CBOR output bound, hash input bound,
Bech32/Hex bounds, wallet never-throw invariant, and
`docs/AUDIT/2026-08-23-final-pre-release-audit.md`. Full session text is in the
archive.

Older Phase 0 / Phase 1 block sessions (1.2 through 1.12, funding, landing page,
brand, release-hygiene) are in the [pre-curation snapshot](archive/handoff/2026-08-23-pre-curation.md),
not restated here.

## What Not To Do Yet

Do not implement:

- Mnemonic generation.
- Raw private-key byte exposure (ADR-0009 §7).
- Transaction signing outside the Block 1.10 scope (ADR-0015 §2 / ADR-0019):
  testnet/preprod only, the cited fixture identity only, ADA-only single-payment
  `TransactionBuilder` drafts only. No mainnet, non-fixture wallet, native assets,
  scripts, metadata, or multisig signing. No general-purpose wallet signing API.
- Real transaction submission beyond preprod test funds. Block 1.11 is complete
  (`TxSubmitProvider`, `BlockfrostTxSubmitProvider`, Playground submit checkpoint,
  1.11d-2 ADA-only filtering). Do not add mainnet submit.
- Real wallet flows, Plutus, staking/delegation, or hardware-wallet behavior.
- Readiness or review-status claims beyond the documented evidence.

Do not use:

- Invented test vectors for protocol behavior.
- Handwritten cryptographic algorithms.
- Lenient parsers that accept malformed input to make tests pass.
- `ByteArray == ByteArray` for content equality.

## Next Recommended Task

Prompt 7 is on `fix/native-build-and-platform-evidence`. Gate 1 is GO at
`d09db44`. Gate 2 Linux Phase C promotion from run `32678079715` is on
the branch (ninth CHECKSUMS row). Gate 3 Windows x86-64 JVM is
candidate-only: independent PE technical review is COMPLETE at `c65a20a`,
but Identus #226 still blocks `:crypto`/`:wallet` JVM tests and promotion
(PE technical-review completion does not promote the candidate or imply
DLL distribution). The non-counsel legal-evidence
packet on this same branch has been through two independent-review
NO-GO rounds (see "Recent Sessions" above); a reviewer should check
whether a third round finds further engineering gaps before treating the
packet itself as engineering-complete — separately, and regardless of
engineering completeness, the packet's owner/counsel/Identus/Windows
open gates in `docs/LEGAL_REVIEW.md` are not something an automated
session can close. Residual owner work: authenticated GitHub artifact
download, secret-scanning / Dependabot, the manual accessibility
walkthrough, and a post-replacement Android device
`connectedAndroidDeviceTest`. Do not merge from an automated session.

## Prompt For Cursor Business/Product Work

Use this prompt in Cursor Ask mode when working on business or product strategy:

```text
Act as a product and business strategy advisor for Kardano SDK.

Use these files as source of truth:
- docs/PROJECT_BRIEF.md
- docs/ROADMAP.md
- docs/DELIVERY_RECORD.md
- docs/HANDOFF.md
- docs/archive/handoff/README.md
- docs/AI_WORKING_AGREEMENT.md
- docs/SECURITY.md
- ADR files under docs/DECISIONS/

Do not edit source code.

Focus only on:
- product positioning
- MVP scope
- roadmap
- adoption strategy
- Cardano ecosystem fit
- grants and funding
- documentation strategy
- developer experience

If you recommend changes, explain why and list the exact docs that should be updated.
```

## Prompt For Cursor Technical Planning

Use this prompt before implementation tasks:

```text
Act as a senior Kotlin Multiplatform engineer and SDK maintainer.

Read:
- docs/PROJECT_BRIEF.md
- docs/ROADMAP.md
- docs/DELIVERY_RECORD.md
- docs/HANDOFF.md
- docs/archive/handoff/README.md
- docs/AI_WORKING_AGREEMENT.md
- docs/SECURITY.md
- ADR files under docs/DECISIONS/

Do not edit files yet.

Plan the next small implementation task.

Return:
- objective
- files likely affected
- tests required
- docs required
- risks
- exact acceptance criteria
- whether this is appropriate for Agent mode
```

## Prompt For Updating This Handoff

Use this at the end of a Cursor session:

```text
Update docs/HANDOFF.md with the latest session state.

Include:
- what changed
- why it changed
- files touched
- tests run
- docs updated
- decisions made
- current risks
- next recommended task

Move older session text into docs/archive/handoff/ rather than deleting it.
Do not modify source code.
```
