# Kardano SDK — Final Pre-Release Audit

Date: 2026-08-23
Auditor: AI coding agent (Cursor), per user request, as part of the
`fix/pre-release-core-contracts` remediation batch.

> This audit does not certify the absence of defects, and it is not a certification of any
> kind. It records reproducible evidence, reconciles the prior audit's 32 findings against the
> remediation work that has since landed, records new findings this pass identified, and states
> residual risk plainly. A passing test is evidence for the specific behavior it exercises,
> never evidence that no other issue exists in the surrounding code.

---

## 1. Baseline

| Item | Value |
|---|---|
| Baseline branch/commit | `origin/main` at `f43ad944` (`f43ad94` in short form; the merge of PR #10, `feat/signing-scope-opt-in`) |
| Baseline tree | `adf25bd` (`git rev-parse origin/main^{tree}` = `adf25bd906c1dee7f5e83b7a67b68095587466ce`) |
| Working branch for this batch | `fix/pre-release-core-contracts`, created from `origin/main` at the commit above |
| Prior audit | `docs/AUDIT/2026-08-22-pre-release-audit.md` (32 findings, plus its own §8 addendum) |
| Working tree at start of this pass | Clean (`git status --porcelain` empty, confirmed before branching) |

This document reconciles the prior audit's 32 findings against the eleven remediation commits
that landed on `main` between the prior audit's `8a6339f` addendum baseline and this batch's
`f43ad944` baseline (§2), then records the new findings and verification evidence produced by
this batch's own five commits (§3–§5).

---

## 2. Reconciliation of the 32 original findings

The prior audit's §7.1 findings index is the source of truth for severity/title; this table
adds a status column. "Commit" cites the `main`-branch commit that resolved the finding, where
one exists, verified via `git log --oneline 8a6339f..f43ad944` and the finding's own
before/after code.

| ID | Severity | Title | Status |
|---|---|---|---|
| W1-1 | Low | Uncommitted typo in `:core` KDoc mixed into a working tree | **Resolved, no code change needed** — the typo was never committed (`git show 094ec8c:...CborValue.kt` already read correctly); the stray edit was discarded. Recorded in the prior audit's own §8.2. |
| W1-2 | Informational | `docs/HANDOFF.md` is a large, growing internal log in the public tree | **Resolved on `fix/release-docs-and-scanners`** — historical content moved verbatim to `docs/archive/handoff/`; living handoff is the current resume. See §7. |
| W3-1 | Informational | Benign "Expression is unused" warnings in generated UniFFI bindings | **Confirmed still present, expected** — reproduced verbatim in this batch's own fresh builds (§4); no remediation needed per the original finding's own text. |
| W3-2 | Informational | Audit-methodology note (cache-hit correction) | **N/A** — a note about the prior audit's own method, not a code finding. |
| W3-3 | Low | CI runs no lint step despite AGP providing one for free | **Open** — `verify.yml` still does not invoke `androidApp:lint`; this batch ran it manually (§4) but did not wire it into CI. Not in this batch's authorized scope. |
| W4-1 | Medium | ADR-0015 §9 stale "Block 1.10c remains open" | **Resolved** — commit `f5289d8` ("Reconcile stale ADR-0015/ADR-0017 status claims (W4-1, W4-2)"). |
| W4-2 | Medium | ADR-0017 stale "no Blockfrost implementation… yet" | **Resolved** — commit `f5289d8` (same commit as W4-1). |
| W4-3 | Low | `PROJECT_BRIEF.md` delivery-record pointer one hop removed | **Open** — no remediation commit found; not in this batch's scope. |
| W4-4 | Low | Inconsistent "Not audited." disclaimer across module READMEs | **Open** — no remediation commit found; not in this batch's scope. |
| W4-5 | Medium | `docs/RELEASING.md` manual, no tag-triggered CI | **Open** — no tag-triggered workflow exists; not in this batch's scope. |
| W4-6 | Low | `CborValue.kt` diff had no changelog entry | **Resolved, no code change needed** — see W1-1; the diff was never committed, so there was nothing to log. |
| W5-1 | High | Three dependencies' license status unresolved | **Resolved** — commit `19fc89a` ("Resolve third-party notices for W5-1, add W5-3's missing hash rows"). |
| W5-2 | High | No checksum/provenance manifest for native binaries | **Resolved** — commit `40ab80c` ("Add SHA-256 checksum manifest for signing-backend binaries"); independently re-verified in this batch (§4: 8/8 checksums match). |
| W5-3 | Medium | KotlinCrypto hash deps missing from `THIRD_PARTY_NOTICES.md` | **Resolved** — commit `19fc89a` (same commit as W5-1). |
| W5-4 | Medium/Low | Six pinned dependencies are pre-1.0/alpha/beta | **Open, by design** — pinning (not upgrading) was the original remediation; the dependencies remain pre-1.0 upstream. No pin is dynamic (`git grep` for `+` versions in `gradle/libs.versions.toml` confirms none). Not actionable without an upstream release. |
| W5-5 | Low | `BlockfrostConfig`'s generated `equals`/`hashCode` retain the raw project id | **Open** — no remediation commit found; not in this batch's scope. |
| W6-1 | Medium | `Hashing.blake2b224`/`256` enforce no input-size bound | **Resolved in this batch** — Commit 3 below. |
| W6-2 | Medium | `Cbor.encode` has no total-output-size cap | **Resolved in this batch** — Commit 2 below. |
| W6-3 | Low | `Bech32.convertBits` bounds only one direction | **Resolved in this batch** — Commit 4 below. |
| W6-4 | Low | "Zero `@Throws` repository-wide" claim imprecise | **Open** — a documentation-wording fix, not in this batch's scope. |
| W7-1 | High (release)/by-design (dev) | `signTransaction`'s unused `network`, no fixture check | **Resolved** — commits `ec6d8a7` (ADR-0018) and `b7a08b9` (rename to `signTestnetFixtureTransaction`, opt-in annotation). The underlying scope-enforcement gap this finding described is unchanged by design (ADR-0015 §2a/ADR-0018 both explicitly keep it a compiler/IDE-visible **intent signal**, not a runtime network/fixture check) — see §6 residual risk. |
| W8-1 | Medium | No direct test for the value-conservation identity | **Resolved** — commit `d003618` ("Add value-conservation identity tests and InsufficientFunds fields"). |
| W8-2 | Medium | Native-asset filtering silent; no error field distinguishes cause | **Resolved** — commit `d003618` (same commit as W8-1; added `excludedNativeAssetUtxoCount`/`excludedNativeAssetLovelace` to `TxBuildError.InsufficientFunds`). |
| W8-3 | Low | No HTTP timeout/retry policy | **Open** — no remediation commit found; not in this batch's scope. |
| W8-4 | Low | Broad exception catches lose type fidelity; `RemoteStatus` asymmetry | **Open** — no remediation commit found; not in this batch's scope. |
| W9-1 | High | Live/mock UI honesty gap; Submit-step misclassification | **Resolved before the prior audit's own addendum** — landed at commit `61c852a`, one commit ahead of the prior audit's stated baseline; confirmed in that audit's own §8.2. The manual Android/Desktop accessibility walkthrough this finding also named is still outstanding (see the new "stale Playground operations" finding, §3, which supersedes tracking this specific residual item under W9-1). |
| W9-2 | Medium | CI actions pinned by floating tag, not commit SHA | **Resolved** — commit `89e6c2d` ("Pin CI GitHub Actions to commit SHAs (W9-2)"); this batch found one gap the original remediation missed — see the new "transitive Action pin" finding, §3. |
| W9-3 | Medium | No lint/format/banned-word/secret-scan CI step | **Resolved** — commit `36c92ff` ("Add a CI banned-word/claim-language scan (W9-3)"); this batch found the scanner itself has false-negative gaps — see the new finding, §3. |
| W9-4 | Medium | Native signing-path tests run only on the macOS CI job | **Open, by platform constraint** — no Linux JVM signing-backend artifact exists yet (confirmed unchanged in `docs/THIRD_PARTY_NOTICES.md`); not actionable without one. |
| W9-5 | Medium | Landing-page "expected URL once enabled" wording may be stale | **Resolved** — commit `2b3bb33` ("Confirm the landing page is live, not pending (W9-5)"). |
| W9-6 | Medium | Landing-page skip-link missing `tabindex="-1"` | **Resolved** — commit `d8c14a5` ("Move skip-link focus to main content (W9-6)"). |
| W9-7 | Low | `LovelaceDisplay.ada` negative-input formatting defect | **Resolved before the prior audit's own addendum** — landed at commit `8a6339f`; confirmed in that audit's own §8.2. |

**Reconciliation summary:** of 32 original findings, 19 are resolved (3 of those with no code
change needed, because the underlying diff was never committed), 12 remain open (all either
by explicit design/platform constraint, or genuinely out of this batch's authorized scope), and
1 (W3-2) does not apply (a methodology note, not a code finding). No finding was silently
dropped; every ID above traces to either a commit hash or an explicit "still open, out of
scope" statement.

---

## 3. New findings (this pass)

**NF-1 (Medium) — `Cbor.encode` had no cumulative output bound (the same code path as W6-2,
now resolved by this batch's Commit 2).** Recorded here as the finding that motivated Commit 2;
see §5 Commit 2 for the fix and §2's W6-2 row for its resolution status. Not a new open issue.

**NF-2 (Low) — The Playground's guided-demo copy references operations this batch did not
re-verify end to end on a real device.** The prior audit's W9-1 resolution (commit `61c852a`)
and its own residual-risk note both name a manual Android/Desktop walkthrough (light/dark mode,
narrow window, 200% font scaling, TalkBack/VoiceOver, error-recovery paths) as owner-required
and not yet performed. This remains true as of this batch: no device/emulator with a display was
available in this environment, so the Playground's operational claims (e.g. "Run the demo
again" recovering cleanly) are exercised only by the Kotlin unit-test suite that already covers
`PlaygroundReducer`/`PlaygroundDemoFlow`/`PlaygroundViewModel`, not by a real UI session. *Not
a defect this pass found* — it is the same disclosed residual risk carried forward, now
recorded under its own finding ID so it is tracked independently of W9-1 (which is otherwise
fully resolved).

**NF-3 (Low) — The landing page's accessibility semantics were spot-checked, not repeated as a
full accessibility pass.** This batch re-confirmed the specific W9-6 fix (`tabindex="-1"` on `#main-content`, still
present) but did not repeat the prior audit's full `aria-labelledby`/heading-order/alt-text pass
across `site/index.html`. No regression was found in the spots checked; a full re-audit was out
of this batch's scope (no `site/**` files were touched by any of this batch's five commits).

**NF-4 (Low) — One CI Action dependency is pinned by SHA directly, but that Action's own
transitive Actions are not verified by this repository.** W9-2's remediation (commit `89e6c2d`)
pins all `uses:` lines in `verify.yml`/`deploy-site.yml` to full commit SHAs. This batch spot
-checked one of those pinned Actions (`gradle/actions/setup-gradle`) and confirmed it is
pinned by SHA in this repo's own workflow file, but composite Actions frequently invoke further
Actions internally at whatever ref the pinned commit's own `action.yml` specifies — this
repository's pin controls only the top-level reference, not that Action's own internal
supply chain. This is a standard, industry-wide limitation of SHA-pinning composite Actions
(not specific to a misconfiguration here), but it means "every `uses:` line is pinned to a SHA"
(the literal W9-2 remediation claim) is a narrower guarantee than "this workflow's entire Action
supply chain is pinned." Recorded so the distinction is explicit rather than assumed.

**NF-5 (Low) — The restricted-claim (banned-word) scanner has real, reproducible false
negatives at word-boundary edges, discovered by this batch's own writing.** While drafting this
batch's CHANGELOG/KDoc, two restricted-claim occurrences were caught only by manually
re-running the exact scan script from `verify.yml` locally (§5, Verification) — the scanner
itself is sound (it did fire and both occurrences were fixed before this commit), but this
exercise surfaced two structural gaps in the scan's design, not in its execution:
1. The scan only runs in CI on `pull_request`/`push:main`, so a wording slip introduced and
   then reworded within the same local session (as happened here) is never actually recorded as
   a caught CI failure — only a local pre-commit run catches it. There is no pre-commit hook
   wired to this same script today.
2. The `NEGATION_QUALIFIER`/`HYPHEN_QUALIFIER` exemptions are narrow enough that a
   grammatically valid but still-restricted claim (e.g. "keeps X reliably free of the class of
   bug Y" rephrasing a restricted claim without the literal word) would not be caught at all — this
   is a fundamental limitation of a fixed word-list scan, not a bug in this instance's pattern,
   but it means the scan is a floor, not a ceiling, on claim-language discipline.

*Impact:* Low — no restricted claim shipped in this batch (both occurrences were caught and
reworded before commit), and the scan did work as designed for literal banned-word matches.
*Remediation (not performed in this batch, out of its authorized scope):* consider a
pre-commit/pre-push hook running the same script locally, and treat the fixed word list as a
supplement to human review of claim language, not a substitute for it.

**NF-6 (Low) — `ReadOnlyWallet.signTestnetFixtureTransaction`'s scope-enforcement gap (W7-1)
is unchanged in kind, only in its compiler/IDE-visible signaling.** ADR-0018's own text (and
this batch's independent reading of `ReadOnlyWallet.kt`) confirms: `network` is still an
unread, `@Suppress("UNUSED_PARAMETER")`-annotated parameter; `Network.MAINNET` and
`BlockfrostNetwork.MAINNET` remain public, unguarded values; and no runtime check rejects a
non-fixture mnemonic or a non-testnet network declaration. The rename and
`@ExperimentalKardanoSigningScope` opt-in (ADR-0018) are a real, verified improvement — a
third-party consumer must now take a deliberate, visible action (`@OptIn`) to call this
function at all, and the function's own name states its scope — but neither is a runtime
guarantee. This is the same residual risk the prior audit's W7-1 finding text already
identified as "release-readiness" severity and explicitly by-design for internal development
scope; this batch's own reading of the current code confirms nothing has changed in the
underlying enforcement, only in the calling discipline the type system now nudges toward.

---

## 4. Verification evidence (this batch, freshly executed on this host)

Host: macOS (Darwin 25.2.0, arm64), Gradle wrapper 9.1.0, `./gradlew --no-daemon`. Every command
below was run with `--rerun-tasks` where the task supports it, so results reflect genuine
re-execution on this host during this session, not a cached/`UP-TO-DATE` result reported as if
it were fresh evidence (the same discipline the prior audit's W3-2 finding established).

| # | Command | Result |
|---|---|---|
| V1 | `./gradlew --no-daemon --rerun-tasks :core:jvmTest :crypto:jvmTest :wallet:jvmTest :tx:jvmTest :shared:jvmTest :provider:jvmTest :provider-blockfrost:jvmTest :crypto-signing-backend:jvmTest` | `BUILD SUCCESSFUL`, 54/54 tasks freshly executed. **661 tests, 0 failures, 0 errors, 0 skipped** (core 264, crypto 78, wallet 23, tx 62, shared 186, provider 14, provider-blockfrost 30, crypto-signing-backend 4) |
| V2 | `./gradlew --no-daemon --rerun-tasks :core:testAndroidHostTest :crypto:testAndroidHostTest :provider:testAndroidHostTest :provider-blockfrost:testAndroidHostTest :wallet:testAndroidHostTest :tx:testAndroidHostTest :shared:testAndroidHostTest` | `BUILD SUCCESSFUL`, 108/108 tasks freshly executed. **611 tests, 0 failures, 0 errors, 0 skipped** (core 263, crypto 67, wallet 19, tx 62, shared 157, provider 14, provider-blockfrost 29) |
| V3 | `./gradlew --no-daemon --rerun-tasks :core:compileKotlinIosArm64 :crypto:compileKotlinIosArm64 :wallet:compileKotlinIosArm64 :tx:compileKotlinIosArm64 :shared:compileKotlinIosArm64 :crypto-signing-backend:compileKotlinIosArm64 :provider:compileKotlinIosArm64 :provider-blockfrost:compileKotlinIosArm64` | `BUILD SUCCESSFUL`, 40/40 tasks freshly executed. **All 8 modules compile clean for `iosArm64`**, including the `crypto-signing-backend` cinterop step against the committed native `.a` binary. Same benign "Expression is unused" UniFFI-binding warning as the prior audit's W3-1 (unchanged). |
| V4 | `./gradlew --no-daemon :androidApp:assembleDebug` | `BUILD SUCCESSFUL` |
| V5 | `./gradlew --no-daemon :desktopApp:assemble` | `BUILD SUCCESSFUL` |
| V6 | `./gradlew --no-daemon :androidApp:lintDebug` | `BUILD SUCCESSFUL`. **0 errors, 36 warnings** (`androidApp/build/reports/lint-results-debug.txt`) — all 36 are pre-existing hygiene items (dependency-version-freshness notices, launcher-icon shape/monochrome-tag suggestions, one densityless-drawable note), none touch this batch's changed files. |
| V7 | `cd crypto-signing-backend && shasum -a 256 -c CHECKSUMS.sha256` | **8/8 OK** — every committed native signing-backend binary's SHA-256 matches the manifest from W5-2's remediation, unchanged by this batch. |
| V8 | `git diff --check` | Exit `0`, no output — no whitespace errors in this batch's diff. |
| V9 | Restricted-claim (banned-word) scan — the exact script from `.github/workflows/verify.yml`'s `restricted-claim-scan` job, run locally against this batch's changed tracked files | Initially **caught 2 real restricted-claim occurrences** in this batch's own draft `Bech32.kt` KDoc and `CHANGELOG.md` wording (see NF-5); both reworded to factual language ("enforce this bound structurally" instead of a construction-time restricted claim) and the scan passes clean on the corrected text. |

**Not exercised by this batch** (unchanged residual risk from the prior audit's §6, restated
here rather than re-derived): a live GitHub Actions run of `Verify`/`deploy-site` (this
environment has no network access to trigger or observe one — the "successful GitHub Verify and
Pages workflows" evidence this batch was asked to record reflects the state as of the
`f43ad944` baseline this branch started from, not a run this pass independently triggered);
iOS Simulator/device runtime execution (still no installed Simulator runtime on this host);
physical Android device/emulator manual walkthroughs (see NF-2); a Linux/Windows JVM host; an
independent reproducible-build verification of the native binaries; a counsel license review;
an independent cryptographic protocol review.

---

## 5. This batch's five commits

Full per-commit file lists, exact test names, and API-change details are in this batch's commit
messages and in `CHANGELOG.md`'s Unreleased section; summarized here for the audit record:

1. **Record the final audit baseline** — this document.
2. **CBOR cumulative output bound (W6-2)** — `CborError.OutputTooLong`; `Cbor.encode` sums
   assembled output size with `Long` arithmetic and rejects before the final allocation/concat
   once it would exceed `CBOR_MAX_INPUT_BYTES`. Tests: an encode-output-over-limit case using
   17×64 KiB byte strings (~1.09 MiB, not a multi-gigabyte fixture), an at-limit success case,
   and the previously-missing decode `InputTooLong` test.
3. **Hash input bound (W6-1)** — `Hashing.MAX_INPUT_BYTES` (1 MiB), `CryptoError.InputTooLong`;
   `Blake2bHashing` rejects an oversized input before its defensive copy. Tests: both Blake2b
   variants at the limit (success) and limit+1 (rejection). Playground error presentation
   updated for the new variant.
4. **Bech32 and Hex bounds (W6-3 plus a new Hex encode bound)** — `Bech32.convertBits`'s 8→5
   direction is now bounded by `MAX_DATA_VALUES`, mirroring its 5→8 direction's existing
   `MAX_DATA_BYTES` bound. `Hex.encode` gained `MAX_ENCODE_INPUT_BYTES` (512 KiB, half of
   `Hex.MAX_INPUT_CHARS`) and now returns `KardanoResult<String, HexError>` instead of a bare
   `String` — a pre-alpha, breaking API change, recorded in `CHANGELOG.md`, with every call site
   in `:core`, `:wallet`, `:provider-blockfrost`, and `:shared` updated in the same commit.
5. **Wallet never-throw invariant** — removed the two `error(...)` calls reachable from
   `ReadOnlyWallet`'s public operations (`restore`'s balance-overflow-adjacent Lovelace check
   inside `sumBalance`, and `signTestnetFixtureTransaction`'s `TxHash.of` body-hash-length
   check), replacing both with the new `WalletError.InvariantViolation` variant. The one
   remaining `error(...)` call in the file (`fixedPathOrThrow`) backs only the `internal`,
   test-support `ReadOnlyWallet.of` factory's default parameters — not reachable from any public
   wallet operation — and `restore`/`signTestnetFixtureTransaction` now compute their own fixed
   CIP-1852 path via a typed `KardanoResult` instead of referencing that throwing constant.

---

## 6. Residual risk after this batch

- **W7-1's underlying scope-enforcement gap is unchanged** (NF-6): `signTestnetFixtureTransaction`
  still takes any structurally-valid mnemonic and any `Network` without a runtime check. ADR-0018
  frames this as accepted for the project's current phase; it is not resolved at the type level,
  only signaled more strongly than before.
- **The manual Android/Desktop accessibility walkthrough remains outstanding** (NF-2), unchanged
  from the prior audit's own residual-risk list.
- **Twelve of the original 32 findings remain open**, all either by explicit design/platform
  constraint or genuinely outside this batch's five-commit authorized scope (§2).
- **This batch's own new findings (NF-3, NF-4, NF-5) are all Low severity** and none block this
  batch's own changes from being reviewed and merged; they are recorded so a future pass has a
  concrete starting point rather than an implicit assumption that everything not mentioned was
  checked.

**This audit does not certify the SDK defect-free, and neither this document nor the batch it
describes should be read as a certification of any kind.** It is a record of what was checked,
what was found, and what remains open, as of `fix/pre-release-core-contracts`'s branch point
from `origin/main@f43ad944`.

---

## 7. Later stacked-remediation status (2026-08-23)

Sections 1–6 remain the Prompt 1 batch record. This section only updates **current**
status pointers for findings later remediations addressed. It does not rewrite the
original evidence or reopen resolved-as-of-Prompt-1 items.

| ID | Status as of `fix/release-docs-and-scanners` (docs-reconciliation commit) |
|---|---|
| W4-1 | **Further reconciled** — ADR-0015's header now matches the completed 1.10c §9 result note (the Prompt 1-era `f5289d8` note had updated §9; the header still said 1.10c remained open). |
| W4-2 | **Further reconciled** — ADR-0017's header and Non-goals now point at the shipped 1.11b/1.11c result note; the original 1.11a-only decision text is unchanged. |
| W4-3 | **Resolved** — `docs/PROJECT_BRIEF.md` now links the full delivery record to `docs/DELIVERY_RECORD.md`. `docs/ROADMAP.md` remains the overview. |
| W4-4 | **Resolved** — module README status lines now use the accepted factual wording ("Not independently reviewed") already used by the root README / `docs/SECURITY.md` / `docs/PROJECT_BRIEF.md`. Provider READMEs keep the testnet/preprod qualifier. |
| W5-5 | **Resolved** on stacked `fix/provider-boundaries-and-timeouts` — `BlockfrostConfig` is no longer a `data class`; equality is referential and `toString` stays redacted. |
| W8-3 | **Resolved** on stacked `fix/provider-boundaries-and-timeouts` — explicit Ktor `HttpTimeout` bounds and no Ktor request retry. |
| W1-2 | **Resolved** — historical HANDOFF content is preserved verbatim under `docs/archive/handoff/`; the living `docs/HANDOFF.md` is the current resume. `scripts/check_handoff_archive.py` restores the six documented link rewrites at the byte level and hashes the original bytes. `.gitattributes` scopes `whitespace=-blank-at-eof` to that archive file only. |
| NF-5 | **Further remediated** — match-by-match scanner with `path:line:column`, longest phrase first, sentence-bounded negation, and Markdown-emphasis normalization. Hyphen compounds are not exempt. Evolving ADRs and the append-only Phase 1 log are scanned; unavoidable historical wording is allowlisted per occurrence (path + 1-based physical line + line SHA-256 + phrase + occurrence index; inserting a line before an allowlisted hit is fail-closed). Whole-file exclusions remain only for immutable archived snapshots and circular policy/test data. Suffix matching is case-insensitive. Tracked files come from `git ls-files -z`. CI runs the unit tests before the scan. |
| W9-3 (secret-scan half) | **Resolved** — Gitleaks CLI `v8.30.1` is installed from the official checksums file and scans full history with redacted output. Allowlists are match-level AND entries: the cited CIP-19 hex **and** a root-anchored `^…$` path, including `scripts/gitleaks_allowlist.py` so the helper's own historical assignment is not a finding. A local full-history run on 2026-08-23 reported `no leaks found` (96 commits, 0 findings). CI runs the helper/installer/allowlist tests before install and scan. |
| W9-2 | **Further remediated** on stacked `fix/build-and-ci-reproducibility` — pins re-resolved live on 2026-08-23 and upgraded to Node 24 releases. The previous pins were exact patch releases (`checkout` `v4.3.1` `34e114876b0b11c390a56381ad16ebd13914f8d5`, not the moving `@v4` tag, which is `v4.4.0` as of that resolution). `scripts/check_action_pins.py` now rejects any external `uses:` that is not a 40-character lowercase SHA recorded in `scripts/action_pin_inventory.py`. |
| NF-4 | **Further remediated** on the same branch — `actions/upload-pages-artifact` moved from v3.0.1 (`uses: actions/upload-artifact@v4`) to v5.0.0, whose `action.yml` pins `actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` (v7.0.0). The checker inspects that recorded composite metadata. `gradle/actions` v6.3.0 is not adopted (commercial cache / Terms of Use). |
| W3-3 / toolchain freshness | **Closed on the official envelope** — review-fix pins Kotlin 2.4.10, Gradle 9.5.0, AGP 9.1.0, compile/target SDK 36, lifecycle 2.10.0 (ADR-0021). The earlier 9.7.1 / 9.3.1 / API 37 pair is historical. |
| W5-4 | **Formally accepted** on the same branch (ADR-0020) — remaining 0.x pins are reviewed with current versions, KAT evidence, monitoring triggers, and replacement criteria. Castle 1.85.2 and JNA 5.19.1 were upgraded. Upstream maturity is unchanged. |
| W3-3 / lock + verification | **Further remediated** on `fix/build-and-ci-reproducibility` — STRICT lockfiles, SHA-256 metadata, Cargo `--locked`. Verify `32654915900` failed on four cold-cache Maven Central metadata files; publisher-hashed rows were added. Verify `32655202142` (https://github.com/sarmidev/KardanoSDK/actions/runs/32655202142) is green on all six jobs. |
| W3-3 / lint CI | **Closed** — Debug and Release lint run in `verify.yml` with `warningsAsErrors`. Freshness detectors and `OldTargetApi` (ADR-0021) are the only disables. Monochrome adaptive layer and nodpi splash remain. Legacy square launchers use a generated rounded-rect silhouette, not a 1px inset. |

---

## 8. Prompt 7 native rematch (2026-08-23, stacked)

**Historical (W5-2, commit `40ab80c`).** That CHECKSUMS file described the
original eight host-path-tied binaries. It was a tamper check, not proof
of cross-host rebuild identity or of source provenance.

**Current (replacement commit `5582637`).** CHECKSUMS now describes the
UUID-normalized eight-artifact set matched by clean `macos-26` run
`32662613270` at `f62205e`. Those rows are not the W5-2 host-path hashes.

On `fix/native-build-and-platform-evidence`:

- Link remapping and a stable `@rpath` install name make Darwin *unsigned*
  code/data match across local `26.2` and `macos-26` `26.5.2`.
- `ld`'s `LC_UUID` does not. Apple TN3178 states there is no Apple command
  that sets `LC_UUID` after link. `-no_uuid` matches hashes and is refused
  by macos-26 `dyld`.
- The post-link normalizer derives an RFC 9562 version-8 UUID from
  `hashlib.sha256` of a documented canonical image (zero `LC_UUID`; exclude
  validated `LC_CODE_SIGNATURE` command/blob and restore
  `ncmds`/`sizeofcmds`/`__LINKEDIT` filesize/vmsize). A verifying ad-hoc
  signature with the exact identifier is not sufficient unless `LC_UUID`
  equals that digest. Signature bytes are a separate fact from the UUID
  and from CHECKSUMS.
- Android and iOS candidates already matched a clean runner (6/8).
  Run `32662613270` then matched Darwin UUID + arm64 signature as well
  (8/8). Those candidate bytes replaced `src/` and CHECKSUMS in `5582637`.
  The follow-up harness still accepts those Darwin bytes, so they were
  not rewritten. A later re-review required every Apple dylib dependency
  command (`LC_LOAD_DYLIB` `0xc`, `LC_LOAD_WEAK_DYLIB` `0x18|LC_REQ_DYLD`,
  `LC_REEXPORT_DYLIB` `0x1f|LC_REQ_DYLD`, `LC_LAZY_LOAD_DYLIB` `0x20`,
  `LC_LOAD_UPWARD_DYLIB` `0x23|LC_REQ_DYLD`, from Xcode 26.6 `loader.h`)
  to be parsed and allowlisted; only one `LC_LOAD_DYLIB` of
  `/usr/lib/libSystem.B.dylib` is accepted. Verify now runs
  `:crypto-signing-backend:linkDebugTestIosSimulatorArm64` and
  `:androidApp:assembleDebug`/`assembleRelease` in addition to the
  existing iOS compiles and Android lint. Device runtime remains an
  open owner/manual gate bound to W5-2 checksums. Gate 1 is GO at
  `d09db44`. Gate 2 Linux x86-64 JVM is a native `ubuntu-22.04` candidate
  path (`linux-x86-64/libkardano_ed25519_bip32_signing.so`, glibc 2.35
  baseline measured at runtime) with a fail-closed ELF64 verifier
  (full-string `GLIBC_*` tuples, Verneed bound to one `SHT_GNU_verneed`,
  exact `.dynamic`/`PT_DYNAMIC` and `DT_STRTAB`/`DT_VERSYM` relations,
  raw-byte plus slash-byte path scan; invalid UTF-8 fails on a
  forbidden root or an unapproved absolute-looking path; `/proc` is a
  runtime prefix) and two-build identity; it is not
  in CHECKSUMS until Phase A/B re-review is GO and a promotion commit
  lands. Versym indices resolve to unique `vna_other`/`vd_ndx`;
  ELF64 add/mul is `UINT64_MAX`-checked; raw known roots require a
  following `/`, path stop, or EOF. Runs `32673275963` and
  `32673752819` are superseded.
  Linux ARM, musl, older glibc, and Windows remain out of scope.
