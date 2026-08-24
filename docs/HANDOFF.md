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
| 7 | `fix/native-build-and-platform-evidence` | Gate 3 Windows | Linux Gate 2 promotion GO at `58f82a2`. Windows x86-64 JVM is candidate-only (JNA `win32-x86-64/`). Phase C promotion not started. |

`origin/main` is behind this stack. Do not merge from this session.

## Recent Sessions

### Last Session Summary

Date: 2026-08-24

- **Gate 3 Windows x86-64 JVM (candidate-only) on
  `fix/native-build-and-platform-evidence`.** Linux promotion GO at
  `58f82a2`. JNA 5.19.1 resource is
  `win32-x86-64/kardano_ed25519_bip32_signing.dll`. Fail-closed PE32+
  verifier + `dumpbin` corroboration. Two independent `windows-2022`
  jobs; CHECKSUMS stays 9 rows. Phase B equality from run
  `32715104620` at `04c52dc`: A==B SHA-256
  `d0f36f6110f1662bb0c9998afb5598bebc4dc35c6abdc41865ab0fc4d7d905cc`
  (263680 bytes). Artifacts A `9515642236`, B `9515642439`, report
  `9515785476`, expire 2026-09-07. `:crypto-signing-backend:jvmTest`
  passed on the candidate. `:crypto:jvmTest` / `:wallet:jvmTest` failed
  because `bip32-ed25519` 1.8.8 ships no `win32-x86-64` derivation
  wrapper. Phase C promotion is NO-GO pending independent review.
  Do not merge/tag or start the legal packet.

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
  Device runtime remains historical (W5-2). Do not start Windows or
  merge/tag.
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
the branch (ninth CHECKSUMS row). Independent promotion re-review is
the next gate. Do not start Windows. Residual owner work:
authenticated GitHub artifact download, secret-scanning / Dependabot,
the manual accessibility walkthrough, and a post-replacement Android
device `connectedAndroidDeviceTest`. Do not merge from an automated
session.

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
