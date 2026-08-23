# Kardano SDK — Pre-Release Repository Audit

Date: 2026-08-22
Auditor: AI coding agent (Cursor), read-only repository audit per user request.

> This audit does not certify the absence of defects. It records reproducible evidence,
> classified findings, and residual risks as of the commit and working-tree state below. A
> passing test is recorded as evidence for the specific behavior it exercises, never as evidence
> that no other issue exists in the surrounding code.

---

## 1. Executive summary

This audit examined the Kardano SDK working tree (committed history plus the uncommitted
Playground redesign, ~1,755 lines across 30 files) across nine workstreams: git/tree hygiene,
public claims versus implemented behavior, secrets/fixtures/dependencies/licenses, parser and
ByteArray safety, crypto-backend delegation and signing-scope enforcement, transaction/provider
integrity, and Playground/CI/landing-page behavior. It produced 32 findings (2 High, 15 Medium, 10
Low, 5 Informational — one finding, W7-1, carries a dual rating explained below) plus 30
inline no-finding confirmations and 10 residual risks this audit could not close itself. 1,232
individual test executions were forced to genuinely re-run on this host (not read from cache) with
zero failures, and all 8 Kotlin Multiplatform iOS-compile targets were freshly recompiled clean.

**This audit does not certify the SDK defect-free.** It found no evidence of a real secret,
credential, or funded wallet anywhere in the current tree or across all 59 commits; it found no
handwritten cryptographic primitive anywhere the guardrail prohibits one; and it found that every
test it executed passed. None of that proves the absence of an undiscovered defect — it is the
specific, reproducible evidence this pass gathered, no more.

**The two findings that most matter before a public release:**

- **W9-1 (High) — a real, reachable honesty gap in the Playground itself.** With the live-network
  toggle on and the project-id field left blank, the UI claims "Live test network — real requests"
  while every request is actually served by the offline mock, and the demo's own intentional,
  honest mock-stop is then misclassified as a hard error. This is the opposite of what the
  redesign's own stated goal — "tell the user exactly what happened" — is for, and it is trivially
  reachable by any visitor who toggles the switch before pasting a key.
- **W7-1 (High for public-release readiness; assessed as by-design and acceptable for the
  project's current internal development scope) — the SDK's signing entry point enforces none of
  ADR-0015's seven scope constraints in code.** `ReadOnlyWallet.signTransaction` takes a `network`
  parameter it is annotated `@Suppress("UNUSED_PARAMETER")` and never reads, and validates only that
  a supplied mnemonic is structurally valid BIP-39 — not that it is the Phase-1 fixture.
  `Network.MAINNET` and `BlockfrostNetwork.MAINNET` are both public, unguarded values. Reading
  ADR-0015 in full confirms this is a deliberate, documented architectural choice — the guardrail
  governs what the project's own contributors are authorized to *build*, not a requirement that the
  library itself refuse mainnet/arbitrary-wallet input — and every in-repo Playground call site
  correctly hardcodes testnet/the fixture. That reasoning holds for an internal, single-consumer
  repository. It stops holding the moment this becomes a public, installable artifact: nothing in
  the compiled library signals to a third-party integrator that "testnet/fixture only" is anything
  more than a KDoc comment.

**Two High-severity findings from the dependency/provenance audit also warrant attention before any
binary release:** three third-party dependencies' license terms are explicitly marked unresolved in
the project's own notices file (W5-1), and the ~39.9MB of committed native signing-backend binaries
have no checksum manifest a third party could use to verify them against the visible Rust source
without trusting the repository owner (W5-2).

**Everything else is Medium/Low/Informational** — stale ADR status lines that contradict the
project's own more-current documentation (W4-1, W4-2), several parser/hashing primitives that lack
a safety bound their sibling primitives already enforce but that no current code path can actually
reach with unbounded input (W6-1, W6-2, W6-3), missing test coverage for the single most
safety-critical property a transaction-building SDK has — value conservation — despite the
implementation itself holding that property exactly in every branch traced (W8-1), a native-asset
UTxO filtering behavior that is silent rather than transparent to the caller (W8-2), and a handful
of CI/supply-chain hygiene gaps (floating-tag action pins, no lint/secret-scan step, no
tag-triggered release workflow, native signing-path tests running on only one of two CI jobs).

**What this audit did not and could not establish**, recorded in full in §6: iOS Simulator/device
runtime execution (this host has Xcode but zero installed Simulator runtimes — confirmed by
directly attempting it, not assumed), the physical-device manual UI walkthroughs the project's own
`docs/HANDOFF.md` already flags as owner-required and outstanding, a live Blockfrost network path,
whether GitHub Pages/Discussions are actually live, a Linux/Windows JVM host, an independent
reproducible-build verification of the native binaries, a counsel license review, an independent
cryptographic protocol review, and pixel-level brand-artwork comparison.

---

## 2. Scope, baseline, method

### 2.1 Baseline identity

| Item | Value |
|---|---|
| Repository | `/Users/sarmidev/StudioProjects/KardanoSDK` |
| Current branch | `feat/public-landing-page` |
| `git rev-parse HEAD` | `094ec8c410ddec344e04d37f538df7b5a5cdc8d6` |
| `origin/feat/public-landing-page` | `094ec8c` (in sync with local branch tip) |
| `origin/main` | `01d672e` — merge of PR #6, which merged `feat/public-landing-page` into `main` |
| Local `main` | `e5b6a58` — 4 commits behind `origin/main` |
| Working tree | Dirty: 22 tracked files modified, 8 untracked files (7 files + 1 new test directory) |
| Tracked file count | 353 (`git ls-files \| wc -l`) |
| Total commits (all refs) | 59 (`git log --all --oneline \| wc -l`) |

This audit evaluates the **working tree as it stands**, per the confirmed audit baseline decision:
committed history plus the uncommitted Playground redesign, since that is what would ship if
committed now. Where a finding is specific to the uncommitted delta rather than to already-merged
`main`, this is stated explicitly in the finding.

### 2.2 Host environment (for W3 execution evidence)

| Item | Value |
|---|---|
| OS | macOS 26.2 (BuildVersion 25C56), Darwin 25.2.0, arm64 (Apple Silicon) |
| JDK | Temurin/Homebrew OpenJDK 21.0.11 |
| Xcode | 26.6 (Build 17F113) |
| Swift | present at `/usr/bin/swift` |
| Gradle | wrapper-pinned 9.1.0 (`gradle/wrapper/gradle-wrapper.properties`), invoked via `./gradlew --no-daemon` |

This host can execute every job in `.github/workflows/verify.yml` (both the `ubuntu-latest`
portable/Android-host job and the `macos-latest` signing/iOS-compile job), because it is macOS
with Xcode installed. Evidence gathered here is at least as strong as CI for those two jobs; it
does **not** cover a Linux or Windows JVM host, a real Android device/emulator, or a real iOS
simulator/device run — those are recorded as residual risks in §6.

### 2.3 Excluded from this pass

- No file is modified, no dependency is upgraded, no test is weakened or added, no finding is
  remediated. This is a read-only audit.
- No live network call to Blockfrost, GitHub Pages, or any external service is made.
- No physical Android/iOS device is used (none is available in this environment).
- No legal license review is performed; §6 flags where one is required before release.

### 2.4 Method

Nine workstreams (W1–W9) per the approved plan, each producing path:line-cited evidence, feeding
one consolidated, severity-classified findings list in §4. Passing/failing command output is
captured verbatim into `/tmp/kardano-audit/*.log` during the audit session; the decisive lines are
quoted in §3 and in individual findings. Severity rubric is fixed in §4.0.

---

## 3. Evidence and commands

Each row is a command actually executed during this audit, its exit code, and where full output
lives (session-local log files; contents are excerpted into this report where relevant, and the
underlying commands are all reproducible directly from the repository root).

| # | Workstream | Command | Exit | Notes |
|---|---|---|---|---|
| E1 | W1 | `git rev-parse HEAD` | 0 | `094ec8c4…` |
| E2 | W1 | `git status --porcelain` / `--porcelain=2` | 0 | 22 modified, 8 untracked |
| E3 | W1 | `git log --oneline --graph --all -30` | 0 | confirms branch topology in §2.1 |
| E4 | W1 | `git branch -vv --all` | 0 | confirms local `main` is 4 behind `origin/main` |
| E5 | W1 | `git ls-files \| wc -l` | 0 | 353 |
| E6 | W1 | `git diff --stat` | 0 | 22 files, +766/-681 |
| E7 | W1 | `git diff -- core/.../CborValue.kt` | 0 | see Finding W1-1 |
| E8 | W1 | `git check-ignore -v local.properties .idea .DS_Store .gradle .kotlin build` | 0 | all six match `.gitignore` rules |
| E9 | W1 | `git ls-files -z \| xargs -0 ls -l` sorted by size | 0 | see §5 (dependency/binary inventory) |
| E10 | W1 | `git rev-list --objects --all \| git cat-file --batch-check` sorted by blob size | 0 | confirms no accidental large-object history beyond the intentional native binaries |
| E11 | W5 | `git log --all --pretty=format: --name-only --diff-filter=A \| sort -u \| rg -i "local\.properties\|\.env\|secret\|credential\|\.pem\|\.p12\|\.jks\|keystore\|service-account\|id_rsa\|\.key$"` | 0 (no match) | see Finding "no-finding" §5 |
| E12 | W5 | `git log --all -p -S "preprod" --pickaxe-regex \| rg -o "(mainnet\|preprod\|preview\|testnet)[A-Za-z0-9]{28,36}"` | 0 (no match) | see §5 |
| E13 | W3 | `./gradlew --no-daemon --rerun-tasks :core:jvmTest :provider:jvmTest :provider-blockfrost:jvmTest :tx:jvmTest` | 0 | portable JVM (CI job 1, step 1). 21/21 tasks freshly executed (not cached), 5.7s. **356 tests, 0 failures, 0 errors, 0 skipped** (core 258, provider 14, provider-blockfrost 30, tx 54) |
| E14 | W3 | `./gradlew --no-daemon --rerun-tasks :core:testAndroidHostTest :crypto:testAndroidHostTest :provider:testAndroidHostTest :provider-blockfrost:testAndroidHostTest :wallet:testAndroidHostTest :tx:testAndroidHostTest` | 0 | Android host (CI job 1, step 2). 54/54 tasks executed, 9.6s. **435 tests, 0 failures, 0 errors, 0 skipped** (core 257, provider 14, provider-blockfrost 29, tx 54, wallet 18, crypto 63). One compiler note: two "Expression is unused" warnings in generated UniFFI Android bindings (see Finding W3-1) |
| E15 | W3 | `./gradlew --no-daemon --rerun-tasks :crypto:jvmTest :crypto-signing-backend:jvmTest :wallet:jvmTest :shared:jvmTest` | 0 | macOS signing path (CI job 2, step 1). 45/45 tasks executed, 11.7s. **285 tests, 0 failures, 0 errors, 0 skipped** (crypto 74, crypto-signing-backend 4, wallet 22, shared 185). This is the first real signing-backend JVM KAT execution performed *during this audit* on this host — corroborates ADR-0016's macOS-JVM-verified claim |
| E16 | W3 | `./gradlew --no-daemon --rerun-tasks :shared:testAndroidHostTest` | 0 | CI job 2, step 2. 89/89 tasks executed, 10.8s. **156 tests, 0 failures, 0 errors, 0 skipped**. Note: 156 < the 185 tests seen under `:shared:jvmTest` in E15 — some JVM-only tests are absent from the Android-host source set (consistent with `shared/README.md:588`'s claim that the native signing backend cannot load under the Android host-JVM target); this was not independently confirmed to be *why* the counts differ, only that they differ in the direction the docs predict |
| E17 | W3 | `./gradlew --no-daemon --rerun-tasks` × 8 `compileKotlinIosArm64` tasks | 0 | CI job 2, step 3. 40/40 tasks freshly executed (forced past an initial cache hit — see Finding W3-2 methodology note), 10.7s. All eight modules (`core`, `crypto`, `crypto-signing-backend`, `provider`, `provider-blockfrost`, `wallet`, `tx`, `shared`) compiled clean for `iosArm64`, including the `crypto-signing-backend` cinterop step linking against the committed 18MB `libkardano_ed25519_bip32_signing.a`. One compiler note: "Expression is unused" in generated UniFFI native bindings (`kardano_ed25519_bip32_signing.native.kt:1626`) |
| E18 | W3 | `./gradlew --no-daemon --rerun-tasks :shared:iosSimulatorArm64Test` | **1 (FAILED)** | Beyond CI — tests the claim at `shared/README.md:658`. Compile and link succeeded (`linkDebugTestIosSimulatorArm64`), but execution failed: `Xcode does not support simulator tests for ios_simulator_arm64. Check that requested SDK is installed.` `xcrun simctl list devices available` confirms **zero iOS Simulator runtimes/devices installed** on this host despite Xcode 26.6 being present. This corroborates — does not contradict — `docs/HANDOFF.md:1370-1372`'s claim that iOS runtime execution is environment-gated; it is a host-environment limitation, not a code defect. Recorded as a residual risk in §6, not a finding against the SDK |
| E19 | W3 | `./gradlew --no-daemon --rerun-tasks :crypto-signing-backend:iosSimulatorArm64Test` | **1 (FAILED)** | Beyond CI. Identical failure mode to E18 (link succeeds, `Xcode does not support simulator tests…`) — same host-environment cause, not a code defect |
| E20 | W3 | `./gradlew --no-daemon tasks --all` | 0 | Full task enumeration (2,068 lines), 5.6s. Confirms: **zero** `ktlint`/`detekt`/`spotless` tasks anywhere in the task graph; AGP's built-in `androidApp:lint` / `*:compileLint` / `*:lintAnalyzeAndroidHostTest` tasks **do exist** (provided automatically by the Android Gradle Plugin) but are not invoked by either `.github/workflows/verify.yml` job — see Finding W3-3 |
| E21 | W3 | `xcrun simctl list devices available` | 0 | `== Devices ==` with no entries — confirms E18/E19's root cause independently |
| E22 | W3 | JUnit XML aggregation: `rg -o 'tests="[0-9]+" skipped="[0-9]+" failures="[0-9]+" errors="[0-9]+"' <module>/build/test-results/<task>/*.xml` per module | 0 | Used to produce the exact counts quoted in E13–E16 |

**Host environment used for E13–E21:** macOS 26.2 (Darwin 25.2.0, arm64), Xcode 26.6, Temurin JDK
21.0.11, Gradle wrapper 9.1.0 — see §2.2. Every `--rerun-tasks` invocation forced genuine
re-execution rather than reporting a Gradle `UP-TO-DATE`/configuration-cache hit as if it were
fresh evidence (an initial, uncorrected first pass of E17 returned in 5s entirely `UP-TO-DATE` from
a prior developer session and was discarded — see Finding W3-2).

_(Table continues to be populated as W4–W9 verification work completes; additional rows are
appended per workstream rather than renumbered, to keep citations in individual findings stable.)_

---

## 4. Findings

### 4.0 Severity rubric

- **Critical** — could cause loss of real funds, expose a real credential, or make a materially
  false public claim about safety or scope.
- **High** — scope-enforcement gap, honesty gap in user-facing output, or unbounded/unvalidated
  input reachable from a public API.
- **Medium** — missing enforcement currently compensated by call-site discipline, missing test
  coverage for a claimed behavior, or a doc/code contradiction a reader could act on.
- **Low** — inconsistency, omission, or robustness gap with no current exploit path.
- **Informational** — observation, hygiene item, or a decision to record before release.

_Findings are grouped by workstream below, sorted by severity within each group. This section is
built incrementally; entries are added as each workstream's verification completes._

### 4.1 W1 — Git state, branch, diff boundaries, stray files

**W1-1 (Low) — Uncommitted, unrelated one-character typo in a `:core` public-API KDoc, mixed into
the Playground-redesign working tree.**

`git diff -- core/src/commonMain/kotlin/org/sarmidev/kardano/encoding/cbor/CborValue.kt` shows the
only non-Playground, non-doc source change in the working tree:

```27:27:core/src/commonMain/kotlin/org/sarmidev/kardano/encoding/cbor/CborValue.kt
     * The valid range is `0..Long.MAX_VALUE`. [Cbor.decode] only ev er produces in-range
```

"only ever produces" was changed to "only ev er produces" — a stray space inserted mid-word,
almost certainly an accidental keystroke. This is a documentation-only change (no behavior
change; confirmed by reading the full 2-line diff hunk), but it is a real typo that would ship in
public KDoc for `:core` if committed as-is.

The repository's own `docs/HANDOFF.md` (working-tree diff, lines ~601-607) is self-aware of this
edit, explicitly noting it as a "pre-existing, unrelated working-tree edit… left untouched
throughout" the Block 1.12-pre-e session — so the redesign session did not introduce it and
deliberately avoided touching it further, but it is still sitting uncommitted at the time of this
audit, several sessions later.

*Impact:* Cosmetic only — no functional or security impact. If committed together with the
Playground redesign (which `CHANGELOG.md:24-31` and `docs/HANDOFF.md` describe as strictly
"presentation-only, no SDK public API… change"), it would violate that same commit's own stated
scope and introduce a KDoc typo into `:core`.

*Evidence:* `git diff -- core/src/commonMain/kotlin/org/sarmidev/kardano/encoding/cbor/CborValue.kt`
(E7); `git diff -- docs/HANDOFF.md` (quoted above).

*Remediation:* Fix the typo ("ev er" → "ever") in its own small, separately-scoped commit before
or after the Playground-redesign commit, rather than folding it into a diff whose own commit
message claims zero `:core` changes.

**W1-2 (Informational) — `docs/HANDOFF.md` is a large, continuously-growing internal session log
committed to the public repository.**

`git rev-list --objects --all` shows five distinct historical blob sizes for `docs/HANDOFF.md`
ranging up to 333KB (E10), and the current working-tree version is 333,070 bytes (`ls -l`). It is
tracked at a public repository path with no `.gitignore` exclusion.

*Impact:* Not a secret-exposure issue (§5 confirms no credential-shaped content), but a
public-facing pre-alpha repository carrying an ever-growing internal "session resume ledger" (its
own self-description, per the W4/reconnaissance file inventory) as the single largest tracked
document in the repo is a release-readiness/curation question the project may want to decide on
deliberately (keep as transparency, move out of the public tree, or trim before tagging a
release) rather than by default.

*Evidence:* `git rev-list --objects --all | git cat-file --batch-check` (E10); `ls -l
docs/HANDOFF.md`.

*Remediation:* Decide and document (e.g. in `docs/RELEASING.md`) whether `docs/HANDOFF.md` is
intended to remain in the public tree pre- and post-1.0, or whether it should be pruned/archived
at release time; no code change implied either way.

**No findings for:** stray build artifacts, `.DS_Store`, IDE files, or `local.properties` in the
tracked tree (all confirmed absent and correctly `.gitignore`-covered — see §5.1); accidental large
binary bloat in git history beyond the intentionally-committed native signing-backend artifacts
(see §5.4); branch-divergence risk (local `main` being 4 commits behind `origin/main` is a
local-clone staleness issue, not a repository defect — the current branch's tip is already merged
into `origin/main` via PR #6, confirmed identical commit hash `094ec8c`).

### 4.2 W3 — Build, test, lint matrix, reproducibility

**W3-1 (Informational) — Two "Expression is unused" compiler warnings in generated UniFFI
bindings.**

Both the Android host-test build (E14) and the iOS compile (E17) emit:

```
w: file:///…/crypto-signing-backend/src/androidMain/kotlin/.../kardano_ed25519_bip32_signing.android.kt:1024:9 Expression is unused.
w: file:///…/crypto-signing-backend/src/androidMain/kotlin/.../kardano_ed25519_bip32_signing.android.kt:1318:5 Expression is unused.
w: file:///…/crypto-signing-backend/src/nativeMain/kotlin/.../kardano_ed25519_bip32_signing.native.kt:1626:5 Expression is unused.
```

*Impact:* None observed — build succeeds, tests pass. These are UniFFI-generated files (not
hand-maintained; see §5.4/§7 provenance), so this is not actionable SDK code to edit, but it is
worth the project recording that these warnings are expected/benign so a future contributor does
not mistake them for a regression when they reappear on a UniFFI-binding regeneration.

*Evidence:* E14, E17 compiler output.

*Remediation:* None required; optionally suppress via the UniFFI/Gobley generator configuration
if the warning noise becomes a problem, or note it in `crypto-signing-backend/README.md`.

**W3-2 (Informational, methodology) — An initial iOS-compile evidence pass silently reported a
stale cache hit as if it were fresh evidence.**

The first attempt to execute the CI-mirroring `compileKotlinIosArm64` matrix (without
`--rerun-tasks`) returned `BUILD SUCCESSFUL in 5s / 40 actionable tasks: 9 executed, 31 up-to-date`
— i.e. nearly the entire task graph was satisfied by a Kotlin/Native build cache left over from a
prior, unrelated developer session, not by work performed during this audit. This was caught and
corrected by re-running with `--rerun-tasks` (E17), which genuinely re-executed all 40 tasks.

*Impact:* None on the SDK itself — this is a note about audit methodology, recorded per this
audit's own rule that "passing tests are recorded as evidence of a specific behavior, never as
evidence of absence of defects," extended here to "a cached result is not fresh evidence." It is
included so a reader can trust that E13–E17's pass results reflect genuine execution on this host
during this session, not inherited cache state.

*Evidence:* discarded log (not retained; superseded by E17); E17 itself shows `40 actionable
tasks: 40 executed` with no `UP-TO-DATE` lines.

*Remediation:* None — informational only.

**W3-3 (Low) — CI runs zero lint/static-analysis/format-check step despite AGP providing one for
free.**

`./gradlew tasks --all` (E20) confirms: no `ktlint`, `detekt`, or `spotless` task exists anywhere
in the 2,068-line task graph (Kotlin-specific lint/format tooling is simply not wired into the
build at all — this is a from-scratch absence, not a misconfiguration). However, the **Android
Gradle Plugin automatically provides** `androidApp:lint`, `*:compileLint`, and
`*:lintAnalyzeAndroidHostTest` tasks for every Android-enabled module (`core`, `crypto`,
`crypto-signing-backend`, `provider`, `provider-blockfrost`, `shared`, `tx`, `wallet`,
`androidApp`) — these tasks exist and are runnable today, but neither
`.github/workflows/verify.yml` job (E20 cross-checked against the workflow file) invokes any of
them.

*Impact:* No lint/format regression would currently be caught by CI before merge. This is a gap
relative to what scope item 18 ("build/test/lint matrix") expects to find enforced, though the
project's guardrail rules (manual "banned word" `rg` scans, documented in `docs/AI_WORKING_AGREEMENT.md`)
partially substitute for automated tooling today.

*Evidence:* E20; `.github/workflows/verify.yml` (full contents read — no `lint` step in either
job).

*Remediation:* Add an `androidApp:lint`/`*:lintDebug` step to the `verify.yml` `ubuntu-latest` job
(cheap, already available with no new dependency) as a first step toward automated static
analysis; consider `ktlint`/`detekt` as a separate, larger decision given the project's
"no dependency without a documented rationale" rule.

**No findings for:** test failures, errors, or skips of any kind across 356 + 435 + 285 + 156 =
**1,232 individual test executions** verified during this audit (E13–E16, all 0 failures/0
errors/0 skipped); Gradle wrapper integrity (`distributionSha256Sum` is pinned in
`gradle/wrapper/gradle-wrapper.properties` against Gradle 9.1.0, matching the wrapper's own
`distributionUrl` — no unpinned/floating wrapper version); iOS **compile** claims (all 8 modules
genuinely compile clean for `iosArm64` — confirmed by forced fresh re-execution, not cache, per
E17).

### 4.3 W4 — Public claims versus implemented behavior

**W4-1 (Medium) — `docs/DECISIONS/0015-transaction-signing.md` §9 states Block 1.10c "remains
open"; every other document, including `docs/PHASE_1_PLAN.md`, says it is complete.**

`docs/DECISIONS/0015-transaction-signing.md:383` (inside the ADR's own Block 1.10b result note,
`Updated: 2026-07-13`): "No submission, mainnet path, or general-purpose wallet signing API was
introduced. Block 1.10c (the `:shared` Playground checkpoint, §7) **remains open**." Contradicted
by `docs/PHASE_1_PLAN.md:1075-1094`: "`1.10c` … — **Status: complete, including manual Android
runtime checkpoint**," with a full checkpoint record (transaction id, witness count, CBOR
preview). `shared/README.md`, `CHANGELOG.md`, and ADR-0017 (`docs/DECISIONS/0017-transaction-submission-boundary.md:21-22`,
"Local signing (Block 1.10, ADR-0015/ADR-0016) is now complete") all agree 1.10c shipped — only
ADR-0015's own §9 sentence was never updated afterward.

*Impact:* ADR-0015 is the canonical decision record for signing scope — a security-conscious
reader consulting it first would incorrectly conclude the Playground signing checkpoint is still
outstanding, understating delivered verification evidence at exactly the module they'd check
first.

*Remediation:* Update the stale sentence in ADR-0015 §9 to reflect 1.10c's completion, or replace
it with a pointer to `docs/PHASE_1_PLAN.md`'s 1.10c entry.

**W4-2 (Medium) — `docs/DECISIONS/0017-transaction-submission-boundary.md` header says "no
Blockfrost implementation… yet"; `BlockfrostTxSubmitProvider` (185 lines) is fully implemented and
shipped.**

`docs/DECISIONS/0017-transaction-submission-boundary.md:5`: "Records only the `:provider`
submission interface, error type, and in-memory double; no Blockfrost implementation and no
`:shared` checkpoint yet (§7)." §7 and the Non-goals section repeat this, marking Blockfrost
submission and the `:shared` checkpoint "deferred." But
`provider-blockfrost/src/commonMain/kotlin/org/sarmidev/kardano/provider/blockfrost/BlockfrostTxSubmitProvider.kt`
is a complete, tested `TxSubmitProvider` implementation (full status-code mapping, `POST
{baseUrl}/tx/submit`), and `CHANGELOG.md:14`, `docs/ROADMAP.md:16-19`, `README.md:9-15`, and
`shared/README.md` all describe submission as delivered. Unlike ADR-0015 and ADR-0016, ADR-0017
has no appended post-hoc "result note" documenting that its own deferred work later shipped.

*Impact:* Same class of risk as W4-1 — a reader treating ADRs as the authoritative record of
"what has been authorized/built so far" would materially understate delivered scope for the
submission boundary specifically.

*Remediation:* Append a Block 1.11b/1.11c result note to ADR-0017 (mirroring ADR-0015 §9's
pattern), and correct the stale header/§7/non-goals language or explicitly date-stamp it as
historical-at-time-of-writing.

**W4-3 (Low) — `docs/PROJECT_BRIEF.md:16` points to `docs/ROADMAP.md` for "the full delivery
record"; `docs/ROADMAP.md` itself delegates that role to `docs/DELIVERY_RECORD.md`.**

`docs/PROJECT_BRIEF.md:16`: "The full delivery record is in `docs/ROADMAP.md`." But
`docs/ROADMAP.md:4-6` says: "This document answers what is delivered… For completed
implementation detail, use the [delivery record](DELIVERY_RECORD.md)." A reader following
`PROJECT_BRIEF.md`'s pointer is told by the destination document to go elsewhere.

*Impact:* Low — a broken-signpost experience during due diligence, no safety/scope claim at risk.

*Remediation:* Point `docs/PROJECT_BRIEF.md:16` directly at `docs/DELIVERY_RECORD.md` (or at both,
matching `docs/ROADMAP.md`'s own "Detailed Records" list).

**W4-4 (Low) — Inconsistent "Not audited." disclaimer across module READMEs; `:provider` also
drifts in wording.**

| Module | Path:line | Exact opening disclaimer |
|---|---|---|
| `:core` | `core/README.md:8` | "Phase 0 — pre-alpha, experimental. **Not audited.** Not for real funds." |
| `:crypto` | `crypto/README.md:11` | "Phase 1 — pre-alpha, experimental. **Not audited.** Not for real funds." |
| `:shared` | `shared/README.md:8` | "Phase 1 — pre-alpha, experimental. Not for real funds." |
| `:wallet` | `wallet/README.md:8` | "Phase 1 — pre-alpha, experimental. Not for real funds." |
| `:tx` | `tx/README.md:9` | "Phase 1 — pre-alpha, experimental. Not for real funds." |
| `:provider` | `provider/README.md:7` | "Phase 1 — pre-alpha, experimental. Testnet/preprod only. **No real funds.**" |

Not a false claim (no module claims to *be* audited), but `:wallet` and `:tx` — arguably
higher-stakes than `:core`, since they now perform signing orchestration and CBOR construction —
omit "Not audited." that `:core`/`:crypto` carry, and `:provider` uses yet a third phrasing ("No
real funds" vs. "Not for real funds").

*Impact:* A reader comparing module READMEs could reasonably infer a different audit posture
between modules than actually exists.

*Remediation:* Standardize one canonical disclaimer sentence (including "Not audited.") referenced
by all six module READMEs rather than repeated and drifting six times.

**W4-5 (Medium) — `docs/RELEASING.md` is entirely manual, unenforced prose; no CI workflow is
triggered by a tag or release event.**

`docs/RELEASING.md`'s two checklists (12 items total) are all imperative prose ("Confirm…",
"Verify…", "Run…") with no script, Gradle task, or CI job gating tag creation on any of them.
Confirmed via full read of both `.github/workflows/*.yml`: neither has a `tags:` or `release:`
trigger (also independently confirmed in W9 Lead 7e). A tag could be pushed today with zero CI
involvement.

*Impact:* The release process is discipline-based, not enforced — acceptable for a personal
pre-alpha workflow, but a real gap if `RELEASING.md` is meant to function as a safety gate before
a public release.

*Remediation:* Add a tag-triggered workflow that re-runs the verify matrix (and ideally a
banned-word/claim scan) against the tagged commit, or explicitly relabel `RELEASING.md` as "manual
checklist, not CI-enforced."

**W4-6 (Low) — The one-line `CborValue.kt` diff has no `CHANGELOG.md` entry.**

Cross-referenced with W1-1: the working tree's only non-Playground, non-doc source diff has no
corresponding "Unreleased" changelog line. This is not a silent omission — `docs/HANDOFF.md`
explicitly self-documents it as a known, deliberately-untouched pre-existing edit — but the
changelog and working tree do not fully reconcile as of this snapshot.

*Impact:* Low — see W1-1 for the underlying typo; this entry only notes the changelog-coverage
gap specifically.

*Remediation:* Same as W1-1 — resolve (fix-and-log, or revert) before a release commit.

**No findings for:** the `crypto-signing-backend/README.md:77` Gradle-version line (states 9.1.0,
matching the pinned wrapper exactly — no mismatch); Phase 2/3 non-commitment language across
`docs/ROADMAP.md:34-43,77-98` and `site/index.html:238-245` (every passage checked carries explicit
disclaiming language — "planned direction," "not a delivery schedule," "no delivery date(s)
implied"); a 3-item spot-check of README "What works" claims against `:wallet`/`:provider`/`:tx`
code (Icarus/CIP-3 restoration, in-memory + Blockfrost providers, ADA-only build/sign/submit all
verified as implemented, matching the claims).

**Incidental observations (outside the 9 assigned leads, recorded for completeness):**
`provider/README.md:7`'s "No real funds" vs. the other five modules' "Not for real funds" is the
same wording-drift family as W4-4. ADR-0017 is the only one of the three signing-related ADRs
(0015/0016/0017) with no appended post-hoc result note — the same root cause as W4-2.

### 4.4 W5 — Secrets, fixtures, dependencies, licenses

**W5-1 (High) — Three dependencies' license status is explicitly unresolved by the project's own
documentation, and would block an honest release-time notice.**

`docs/THIRD_PARTY_NOTICES.md:16-18` states, verbatim, for `bip32-ed25519`, IonSpin libsodium
bindings, and LazySodium Android: "Verify release artefact notice before distribution." This is
not a placeholder oversight — it is the document's own admission that these three components'
license terms have not yet been confirmed against their actual distributed artifacts (as opposed
to the Maven Central listing), which matters because some may carry embedded `NOTICE`/attribution
obligations not yet captured.

*Impact:* Shipping a binary/Maven artifact before resolving these three rows risks distributing a
component under license terms the SDK's own notices file does not yet accurately reflect.

*Remediation:* Before any public/binary release, pull each artifact's actual embedded
notice/license file and replace the "Verify" placeholder with confirmed license text, per
`docs/THIRD_PARTY_NOTICES.md`'s own release-time checklist §1/§3.

**W5-2 (High) — No checksum or provenance manifest exists for the ~39.9MB of committed
signing-backend native binaries; a third party cannot verify they match the visible Rust source
without trusting the repository owner.**

The 8 committed native binaries (two 18MB iOS `.a`, four Android `.so`, two macOS `.dylib`) have no
`.sha256`/`SHASUMS`/provenance file anywhere in the repository. `crypto-signing-backend/Cargo.lock`
checksums verify only the Rust *dependency source* downloads, not the compiled output artifacts.
`crypto-signing-backend/README.md` documents a symbol-presence proof (`nm -gU`/`llvm-nm -D`
confirming the expected export exists) and a fully pinned-toolchain manual-rebuild recipe (`rustc
1.97.0`, `cargo-ndk 4.1.2`, NDK `27.2.12479018`), and confirms "there is no CI in this repo" for
these artifacts — meaning even the maintainer's own build is not automatically re-verified. The
in-repo verification is therefore limited to (a) known-answer signing tests proving the shipped
binary *behaves* correctly against one test vector at runtime, and (b) a recipe a sufficiently
motivated third party could manually follow and diff against.

*Impact:* This is a supply-chain provenance gap for binaries that implement the actual sign/verify
cryptographic operation. A compromised or substituted binary that didn't match the visible
`lib.rs` would only be caught by someone manually reproducing the build — nothing in the repository
automates or nudges a consumer toward doing so.

*Remediation:* Publish a checksum manifest (e.g. `crypto-signing-backend/CHECKSUMS.sha256`)
alongside each commit touching these binaries, generated by the same documented regeneration
script; at minimum, record each of the 8 files' SHA-256 in the README so a manual rebuild has a
concrete value to diff against. A reproducible-build verification step is a residual risk requiring
external CI (see §6).

**W5-3 (Medium) — `org.kotlincrypto.hash:blake2` and `:sha2` — the SDK's actual hashing
backends — are missing from `docs/THIRD_PARTY_NOTICES.md`.**

Cross-checking every `[libraries]` entry in `gradle/libs.versions.toml` against
`docs/THIRD_PARTY_NOTICES.md`'s table: both KotlinCrypto hash dependencies (confirmed
actively used in `crypto/build.gradle.kts`) have no corresponding row. `junit` and
`androidx.test:runner` are minor, test-scope-only gaps by comparison.

*Impact:* A release-time license audit trusting `THIRD_PARTY_NOTICES.md` as complete would miss
reviewing/attributing the two dependencies that back the SDK's real hashing path.

*Remediation:* Add explicit rows for `org.kotlincrypto.hash:blake2`/`:sha2` before the release-time
checklist is executed; optionally add `junit`/`androidx.test:runner`.

**W5-4 (Medium for the two 0.x cryptographic-hash dependencies; Low for the UI-only alpha/beta
entries) — Six pinned dependencies are pre-1.0/alpha/beta.**

All confirmed pinned (no `+`/dynamic versions anywhere in `gradle/libs.versions.toml`). Pre-release
versions in use: `org.kotlincrypto.hash:blake2`/`:sha2` (`0.8.0` each — load-bearing crypto-hash
backends), `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings` (`0.9.5`),
`org.jetbrains.kotlinx:atomicfu` (`0.26.1`), `androidx.lifecycle:lifecycle-viewmodel-compose`/`-runtime-compose`
(`2.11.0-beta01`), `org.jetbrains.compose.material3:material3` (`1.11.0-alpha07`).

*Impact:* A 0.x/alpha/beta dependency can introduce breaking changes without semver guarantees on
the next bump; pinning mitigates immediate risk but the project inherits upstream pre-1.0 churn.
The two hash-backend dependencies sit on a security-relevant path (though delegated-not-handwritten
per the project's own guardrail); the UI dependencies affect only the non-SDK Playground app.

*Remediation:* Track upstream 1.0 milestones for the KotlinCrypto hash libraries and
`atomicfu`/`ionspin-libsodium`; re-review before any version bump; flag as pre-1.0 transitive trust
boundaries in release notes.

**W5-5 (Low) — `BlockfrostConfig`'s auto-generated `equals`/`hashCode` retain the raw, unredacted
`projectId`, unlike its deliberately-redacted `toString()`.**

`provider-blockfrost/src/commonMain/kotlin/org/sarmidev/kardano/provider/blockfrost/BlockfrostConfig.kt:15-21`
is a `data class` whose `toString()` is manually overridden to redact `projectId`, but
`equals`/`hashCode` are compiler-generated and therefore still operate on the raw key value. A
25-hit repository-wide grep for `BlockfrostConfig` confirms no current call site logs, prints, or
places a `BlockfrostConfig` in an exception message, and none currently compares/hashes two
configs in a way that would surface the raw value — this is a latent, not currently exploited, gap.

*Impact:* A future `Set<BlockfrostConfig>` dedup, or a test/logging framework that renders
assertion failures via `equals`-based diffing, could leak the raw project id where none is expected
today.

*Remediation:* Override `equals`/`hashCode` manually (or wrap `projectId` in a value type with its
own redacted representation) so no auto-generated member can round-trip the raw key.

**No findings for:** secret/credential filenames ever committed across all 59 commits and 365
distinct file paths in history (`git log --all --diff-filter=A --name-only` cross-checked against
`local\.properties|\.env|secret|credential|\.pem|\.p12|\.jks|keystore|service-account|id_rsa|apikey|token|password`
— the sole hit, `AddressCredential.kt`, is a legitimate CIP-19 domain type, not a secret); Blockfrost-style
project-id patterns in current tree or full history (`git log --all -p` and current-tree regex
scan for `(mainnet|preprod|preview|testnet)[A-Za-z0-9]{28,40}` — zero matches in either); private-key
literals (`xprv1`/`root_xsk1`/`ed25519_sk`) outside allowed test source sets (both hits confined to
`jvmTest`/`androidDeviceTest`); fixture citation integrity (`TestWalletFixture.kt`, BIP-39
Trezor vectors, CIP-3 Icarus vectors all carry explicit source/commit citations); mainnet address
literals ever paired with a private key or mnemonic in any fixture (none found — all mainnet
`addr1…` literals are standalone CIP-19 spec structural-parsing vectors); `PlaygroundState.projectId`
persistence (confirmed never written to `DataStore`/`SharedPreferences`/`UserDefaults`/any file or
serializer); `project_id` leakage into `BlockfrostConfig` call-site logging (none found — see also
W8 Lead 5, which independently confirms no leakage into HTTP error paths).

### 4.5 W6 — Parsers, ByteArray discipline, error policy, Swift/ObjC boundary

**W6-1 (Medium) — `Hashing.blake2b224`/`blake2b256` enforce no input-size bound before hashing;
the primitive itself lacks the safety property `Cbor`/`Bech32` both enforce.**

`crypto/src/commonMain/kotlin/org/sarmidev/kardano/crypto/hashing/Blake2bHashing.kt:28-39` passes
`input.copyOf()` directly to `BLAKE2b(bitStrength).digest(...)` with no `MAX_INPUT_BYTES`-style
guard, unlike `Cbor`'s `CBOR_MAX_INPUT_BYTES` or `Bech32`'s `MAX_INPUT_CHARS`. Every current
caller (`AddressCredential`, `ReadOnlyWallet.restore`/`sign`) passes small, internally-bounded
byte arrays (32 bytes or a small transaction body), so there is no live SDK flow that pipes
unbounded, caller-controlled length into it today — but `Hashing` is a public interface, so a
consumer *can* call it directly with an arbitrarily large array they built themselves. In that
case the defensive copy at the call's own entry allocates a second multi-GB buffer before hashing
even starts, so on a memory-constrained mobile device the OOM would occur on the copy, not inside
the delegated hash routine.

*Impact:* A latent gap in the primitive itself rather than an externally-triggerable DoS through
any documented SDK flow today; still a real inconsistency with the project's own parser-safety
guardrail ("Enforce named constants: MAX_INPUT_BYTES…") applied everywhere else in `:core`.

*Remediation:* Add a named `MAX_HASH_INPUT_BYTES` constant and reject oversized input with a typed
`CryptoError` before the defensive copy.

**W6-2 (Medium) — `Cbor.encode` enforces per-element bounds but no total-output-size cap; a
within-limits tree can still produce output far exceeding `CBOR_MAX_INPUT_BYTES`.**

`CBOR_MAX_INPUT_BYTES` (1 MiB) is checked only in `decode` (`core/.../cbor/Cbor.kt:156-158`).
`encode` enforces per-element bounds (`CBOR_MAX_BYTESTRING_BYTES`, `CBOR_MAX_STRING_BYTES`,
`CBOR_MAX_COLLECTION_ELEMENTS`, nesting depth) but never sums the running output size. On paper: a
flat `CborArray` of `CBOR_MAX_COLLECTION_ELEMENTS` (65,536) byte-strings each at
`CBOR_MAX_BYTESTRING_BYTES` (65,536 bytes) passes every individual check yet `encode` returns a
~4GiB output — 4,000× over the decoder's own input limit, with no rejection. The resulting bytes
would then be rejected by this SDK's own `decode`, an asymmetry the KDoc does not disclose. Today's
only production callers (`TransactionBodySerializer`, `TransactionAssembler`, `TransactionBuilder`)
build small, ADA-only single-payment trees, so this is not exploitable through any current SDK
flow, but the gap would silently inherit into any future feature building larger trees.

*Impact:* Structural gap in a security-sensitive parser primitive; not currently reachable, but
would become reachable the moment a future feature (multi-asset outputs, metadata) builds larger
`CborValue` trees from less-bounded input.

*Remediation:* Track a running total during `encodeArray`/`encodeMap`/`concat` and reject with a
new `CborError` variant once the assembled byte count would exceed `CBOR_MAX_INPUT_BYTES`.

**W6-3 (Low) — `Bech32.convertBits` enforces `MAX_DATA_BYTES` only in the 5→8 bit direction, not
the 8→5 direction; not exploitable today because both current callers pre-bound their input, but
the function is not safe-by-construction.**

Confirmed as suspected: the `toBits == 5` (encode) direction has no equivalent bound. `convertBits`
is `internal`, not part of the public API — its only two call sites
(`Address.encodeCanonical`/`parsePointer`) both pass small, internally-bounded payloads (a fixed
57-byte address payload, or a payload already bounded by Bech32's own 1023-character input limit).

*Impact:* Latent trap for any future caller (or a visibility widening) that doesn't realize the
asymmetry — currently unreachable with unbounded input.

*Remediation:* Add a symmetrical bound check for the `toBits == 5` branch so the function is safe
by construction rather than safe only because every current caller happens to pre-bound its input.

**W6-4 (Low) — The internal documentation claim of "zero `@Throws` repository-wide" is false as
literally stated; correctly scoped, it is true only for `:core`/`:crypto`'s own public surface.**

A repository-wide `@Throws` grep returns 12 hits, all inside `:crypto-signing-backend`'s generated
UniFFI FFI bindings — a deliberate, ADR-0016-carved-out exception for a generated FFI boundary,
fully wrapped by try/catch adapters (`Ed25519Bip32Signing.sign`, `Bip32Ed25519KeyDerivation.derivePrivate`)
before reaching any public `:crypto` API. No uncaught-throw path exists in `:core`/`:crypto`'s own
public surface — every internal thrower (BouncyCastle PBKDF2 calls, KotlinCrypto SHA256) is caught
before crossing a public boundary.

*Impact:* Documentation-accuracy issue only, not a live defect — the actual guarantee (`:core`/`:crypto`
never throw) holds; only its literal repository-wide phrasing is imprecise.

*Remediation:* Rephrase the internal claim to scope it explicitly to `:core`/`:crypto`'s own public
API, to avoid a future contributor being surprised by the correct, intentional `@Throws` usage in
`:crypto-signing-backend`.

**No findings for:** the CBOR uint64-overflow rejection (`Cbor.kt:596-604`, an exact sign-bit test
against `Long.MIN_VALUE`/`MAX_VALUE`, no defeating input constructed) and the `Address` pointer-field
overflow guard (`Address.kt:521-528`, a standard overflow-safe accumulator whose byte-count cap
and arithmetic cap agree exactly at 63 bits) — both confirmed sound with no truncation path; all
twelve `ByteArray`-holding container classes in `:core`/`:crypto` (defensive copy on construct and
accessor, `contentEquals`/`contentHashCode` or deliberate reference-identity equality, no
byte-leaking `toString()` anywhere) — the four key-material classes' deliberate omission of
`equals`/`hashCode` is assessed as the *safer* design choice (prevents collection-based comparison/
dedup of secret material and removes any temptation toward a structural `toString()`), not a
defect; the `:shared` iOS framework surface (no `export(...)` configured, every SDK-touching class
in `playground.*` is `internal`, so the actual Swift-visible surface today is limited to a bare
`UIViewController` factory — `KardanoResult`'s Swift-interop ergonomics risk, discussed in the
finding text as a design note, applies only if a future feature exposes it directly, which none
does today).

### 4.6 W7 — Crypto boundaries and signing scope

**W7-1 (High for public-release readiness; assessed as by-design and acceptable for the current
internal development scope) — `ReadOnlyWallet.signTransaction`'s `network` parameter is
compiler-confirmed unused, and no fixture check exists; nothing in the shipped SDK artifact stops
a third-party consumer from signing an arbitrary mainnet transaction with an arbitrary mnemonic.**

```254:259:wallet/src/commonMain/kotlin/org/sarmidev/kardano/wallet/ReadOnlyWallet.kt
    @Suppress("UNUSED_PARAMETER")
    public fun signTransaction(
        words: List<String>,
        network: Network,
        draft: TransactionDraft,
    ): KardanoResult<WalletSignedTransaction, WalletError> {
```

The `@Suppress("UNUSED_PARAMETER")` is itself the tell — `network` appears nowhere in the function
body; the KDoc says so explicitly ("`network` is intentionally not read by this function's
implementation… kept as an explicit parameter… purely so this entry point's signature mirrors
`restore`'s shape"). Both `restore` and `signTransaction` validate only that the supplied mnemonic
is *structurally* valid BIP-39 (`Mnemonic.parse`) — any 12/15/18/21/24-word mnemonic passes, not
specifically the Phase-1 fixture; the KDoc again says so directly ("has no way to verify that
`words` is the Phase 1 fixture or that `network` is testnet; that guarantee is a call-site/checkpoint
discipline, not a runtime check this function performs"). Separately, `Network.MAINNET`
(`core/.../Network.kt:20-26`) and `BlockfrostNetwork.MAINNET` (`provider-blockfrost/.../BlockfrostNetwork.kt:16-25`,
resolving to a real, working `cardano-mainnet.blockfrost.io` base URL) are both public,
unrestricted enum constants with no runtime block anywhere in `:wallet`/`:tx`/`:provider`/`:provider-blockfrost` —
the only checks present (`TransactionBuilder.kt:94-101`) verify *self-consistency* (declared
network matches address network), never *which* network was declared.

Reading ADR-0015 §2a in full confirms this is the documented, deliberate design: the guardrail
text ("Transaction signing is allowed only inside the explicitly authorized Block 1.10 scope…")
governs what the project's own AI/contributors are authorized to *build* during this development
phase, not a requirement that the shipped library itself runtime-reject non-fixture/mainnet input.
The ADR explicitly considered and rejected baking fixture-awareness into `:wallet`, reasoning that
doing so would invert the `:wallet` (SDK) → `:shared` (app) dependency direction. Every actual
Playground call site is confirmed hardcoded to `Network.TESTNET` and the fixture mnemonic
(`PlaygroundPresenter.kt:440,608,738,751,893,976`); `PlaygroundProviderFactory` never overrides the
Blockfrost network away from its `PREPROD` default. **Within that frame, the current design is not
a defect** — it is a legitimate SDK-composition pattern where a narrow app enforces policy over a
general-purpose library, and the in-repo Playground never violates the intended scope.

Six of ADR-0015's seven scope constraints (testnet/preprod, fixture wallet, single payment, no
metadata, no scripts, no multisig) are enforced only by (a) the shape of the public API having no
field to express the disallowed thing, or by Playground call-site discipline — never by a
`:wallet`/`:tx` runtime check. The one positive exception found: `TransactionDraft`'s constructor
is `internal`, so metadata/script/multisig exclusion is in fact a real, compiler-checked Kotlin
module-visibility guarantee, not merely "shape discipline" as ADR-0015's own text implies — this is
*stronger* than the ADR states and should be documented as such. The lone runtime-enforced
constraint is ADA-only filtering (`TransactionBuilder.kt:111-120`).

*Impact — reframed for a public release:* the distinction that makes this acceptable as internal
development policy stops applying the moment `:wallet`/`:tx` become an installable, third-party-
consumable artifact. A third-party developer importing this SDK has no visibility into ADR-0015 or
the guardrail file unless they read the KDoc carefully, and nothing in the *type system* stops them
from calling `ReadOnlyWallet.signTransaction(theirRealMnemonic, Network.MAINNET, theirDraft)` and
receiving back a validly signed, submittable mainnet transaction. This is a materially different
risk profile than "the Playground doesn't misuse it" — it is "nothing in the shipped artifact stops
anyone from doing exactly what the project's own guardrails say must not happen yet."

*Remediation:* Before a public release, either (a) add the minimal runtime check ADR-0015 §2a
deliberately omitted — reject `network != Network.TESTNET` with a typed `WalletError` — and treat
future mainnet/general-wallet support as the explicit, later ADR the current one already
anticipates, or (b) narrow `signTransaction`'s visibility/annotate it as clearly experimental/
scope-limited so external consumers get a compiler- or IDE-level signal, not just KDoc prose.

**No findings for:** every actual cryptographic transform in `:crypto` (hashing, PBKDF2, key
derivation, public-key projection, signing) — all eight call sites confirmed to delegate to a named
external backend (KotlinCrypto BLAKE2b, BouncyCastle/Apple CommonCrypto PBKDF2, Hyperledger Identus
UniFFI `bip32-ed25519`, Ionspin/lazysodium libsodium, the pinned `:crypto-signing-backend` Rust
crate), with no local reimplementation of any S-box, round function, curve-point modular
arithmetic, or HMAC construction found in any of them; the four candidate "handwritten crypto?"
sites (`Bech32.polymod`/`convertBits`, `Mnemonic.packElevenBitGroups`, `IcarusMasterKey.tweakBits`)
are all confirmed to be non-cryptographic glue code (a checksum, a bit-regrouping utility, BIP-39
bit-packing, and CIP-3 spec-literal constant bit-masking applied to already-delegated PBKDF2
output) correctly sitting outside the no-handwritten-crypto rule's intent, which names
confidentiality/integrity primitives specifically.

### 4.7 W8 — Provider behavior and transaction integrity

**W8-1 (Medium) — No test asserts the transaction value-conservation identity
(`sum(inputs) == sum(outputs) + fee`) directly; existing tests check each side separately.**

Manual algebraic trace of every branch in `TransactionBuilder.evaluateAttempt` confirms conservation
holds exactly by construction (`change = selectedSum − payment − fee`, using `CheckedMath`'s
overflow-checked, never-truncating arithmetic) — this is a **no-finding** on the implementation
itself. However, `TransactionBuilderTest.kt`'s tests (`exactZeroChangeOmitsChangeOutput`,
`changeAtOrAboveMinAdaEmitsChangeOutput`, `finalFeeMatchesFeeEncodedInBodyField2`) each assert one
side of the identity (fee alone, or change alone, or the encoded fee alone) rather than tying
inputs, outputs, and fee together in one assertion.

*Impact:* For a wallet SDK, this is the single most safety-critical property, and testing each side
separately is strictly weaker than testing the identity — a future refactor that shifted lovelace
between fee and change while keeping each side "individually plausible" could pass every existing
test while breaking conservation.

*Remediation:* Add at least one test per branch that sums the selected candidates' lovelace and
asserts it equals `sum(outputs) + fee` in a single assertion.

**W8-2 (Medium) — Native-asset UTxO filtering is silent, and no `TxBuildError` variant lets a
caller distinguish "excluded for carrying native assets" from "genuinely insufficient ADA."**

`TransactionBuilder.kt:107-120` filters out native-asset-carrying UTxOs before selection, discarding
their count and lovelace value; the resulting `InsufficientFunds(required, available)` variant
(reachable when the ADA-only remainder is non-empty but too small) has no field distinguishing "you
have too little ADA" from "you have plenty of value locked in excluded token-bearing UTxOs." The
only variant that mentions native assets at all (`UnsupportedFeature`) fires exclusively when *all*
candidates are excluded — exactly the one case where the distinction is no longer the interesting
fact.

*Impact:* A wallet developer debugging "why does this say insufficient funds when the explorer
shows plenty of ADA" gets no signal from the typed error pointing at the real cause; in a wallet UI
this could surface as a generic, potentially confusing message to an end user who does hold
sufficient ADA, just inaccessible to this ADA-only builder.

*Remediation:* Add an `excludedNativeAssetUtxoCount`/total-value field to `InsufficientFunds` (or a
separate advisory alongside a build attempt) so a caller can distinguish the two cases.

**W8-3 (Low) — No `HttpTimeout`/`HttpRequestRetry` plugin is installed; effective timeout behavior
is an unintentional, inconsistent byproduct of each platform's Ktor engine defaults, and no
UI-level timeout wraps any Playground provider call.**

`provider-blockfrost/src/commonMain/kotlin/org/sarmidev/kardano/provider/blockfrost/HttpClientFactory.kt:30-37`
installs only `ContentNegotiation` and the `project_id` default header. Without an explicit
`HttpTimeout` plugin, JVM (CIO) falls back to a ~15s engine default, Android (OkHttp) to 10s
connect/read/write with **no overall call-timeout cap**, and iOS (Darwin/`NSURLSession`) to a 60s
idle / 7-day total-transfer ceiling — three different, undocumented, un-unified bounds arising by
accident of engine choice rather than SDK policy. `PlaygroundViewModel`'s provider calls
(`onQueryFunds`, `onBuildDraft`, `onSignTransaction`, `onSubmitTransaction`, etc.) are all plain
`viewModelScope.launch { … }` with no `withTimeout`/`withTimeoutOrNull` wrapper.

*Impact:* Not a funds-safety issue (failures are still mapped to typed errors normally), but a
real UX/robustness gap — on a flaky mobile network a user could see a loading state for anywhere
from ~10s to 60s+ depending on platform, with no SDK-guaranteed bound and no cancel affordance.

*Remediation:* Install `HttpTimeout` with explicit, platform-uniform values; consider
`HttpRequestRetry` for idempotent read-path calls only (never `submit`); wrap Playground provider
calls in `withTimeoutOrNull` for a documented UI-level bound independent of engine defaults.

**W8-4 (Low) — Broad `catch (e: Exception)` blocks in the Blockfrost providers discard exception
type information (one discards the exception entirely), and `ProviderError.RemoteStatus` cannot
carry response-body detail while `SubmitError.RemoteStatus` can.**

Seven `catch (e: Exception)` blocks preserve `e.message` but not the exception type, collapsing
timeout/DNS/TLS/generic-IO failures into the same `Transport(String)` shape a caller can only
distinguish by fragile string-matching. One catch
(`BlockfrostTxSubmitProvider.kt` error-body read, inside `statusError`) discards the secondary
exception entirely, falling back to an empty body string — low impact since the primary HTTP
status code is still captured. Separately, `ProviderError.RemoteStatus` (`provider/.../ProviderError.kt:32`)
has no `detail` field at all, while `SubmitError.RemoteStatus` (`provider/.../SubmitError.kt:58-59`)
does — a genuine type-level asymmetry, not just an implementation gap in one file, meaning the
read-path error UX is strictly less informative than the write-path for the same failure class.
Status-code-to-variant mapping itself is confirmed exhaustive in both providers (every branch ends
in a named variant or an `else`; `Unknown` is never actually constructed by either).

*Impact:* Forces calling apps to parse free-text messages for differentiated handling (retry vs.
"check your network" vs. "contact support"); minor but real inconsistency in a public error-type
API surface.

*Remediation:* Add a `detail: String?` field to `ProviderError.RemoteStatus` for parity; consider
tagging transport-exception variants with a coarse category alongside the preserved message.

**No findings for:** `project_id` leakage into any forwarded HTTP error text (confirmed — every
error-text-producing code path in both Blockfrost providers reads only `response.bodyAsText()`,
never anything from the outgoing request/headers; no `response.request`/`.call.request` access
exists anywhere in `provider-blockfrost`); value conservation itself, which holds exactly in every
reachable branch (see W8-1's implementation half); the dust-change-rejected and insufficient-funds
branches, which correctly emit no draft rather than a non-conserving one.

### 4.8 W9 — Playground, CI, landing page

**W9-1 (High) — Confirmed: with the live toggle on and a blank project id, the UI displays "Live
test network — real requests, test funds only" while every request is actually served by the
offline mock, and the demo's own intentionally-honest mock-stop is then misclassified as a hard
error instead of the neutral "stopped on purpose" outcome.**

```45:57:shared/src/commonMain/kotlin/org/sarmidev/kardano/playground/data/PlaygroundProviderFactory.kt
    fun queryProvider(useLive: Boolean, projectId: String): ChainQueryProvider {
        if (!useLive) return mockQueryProvider
        refreshLiveProvidersIfNeeded(projectId)
        return cachedLiveQueryProvider ?: mockQueryProvider
    }
```

With `useLive == true` and a blank/whitespace-only `projectId`, `refreshLiveProvidersIfNeeded`
leaves `cachedLiveQueryProvider`/`cachedLiveSubmitProvider` as `null` (lines 59-67), so `?:
mockQueryProvider` silently returns the mock — no HTTP call, no 401/403, no error surfaced anywhere.
Yet the label condition in `DemoStepSection.kt:471-479` is `state.useLiveBlockfrost` **alone** — not
`useLiveBlockfrost && projectId.isNotBlank()` — so the toggle position, not the actual active
provider, drives the "Live test network" claim. The Funds-step guidance and the Summary recap line
share the identical toggle-only condition, so a run in this exact state would also claim "Sent it to
the preprod test network" in the final recap for a session that never left the device.

Compounding this: `PlaygroundDemoFlow.outcome()` classifies the Submit step's mock failure as the
neutral `StepOutcome.INFO` only `if (!state.useLiveBlockfrost && submit.message ==
MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE)`. Since the toggle is on, `!state.useLiveBlockfrost` is
`false` even though the mock actually served the request, so this falls through to
`StepOutcome.ERROR` and the user sees "The network didn't accept the payment" — the code's own
KDoc comment directly above this logic names this exact combination as a case that "should not
happen but is not asserted away here."

*Impact:* A first-time visitor who toggles "live" without pasting a project id gets a false "real
network" claim, then sees the demo's intentionally-honest mock stop rendered as a red failure — the
opposite of the demo's stated purpose of telling the user exactly what happened. This is precisely
the kind of "Mock honesty" failure the audit scope was designed to catch.

*Remediation:* Gate the live/mock label, the funds guidance, the summary recap line, and the Submit
`INFO` classification on `useLiveBlockfrost && projectId.isNotBlank()` (mirroring the factory's
actual selection logic), or thread the factory's actual-provider decision into state so the UI
never has to re-derive it from the toggle alone.

**W9-2 (Medium) — CI pins every third-party GitHub Action by a floating major-version tag
(`@v4`/`@v5`), not a commit SHA.**

Confirmed for all 7 `uses:` lines across both workflows (`actions/checkout@v4`,
`actions/setup-java@v4`, `gradle/actions/setup-gradle@v4`, `actions/configure-pages@v5`,
`actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4`) — none pinned to a full commit SHA.

*Impact:* A compromised or re-tagged upstream action release could silently change CI behavior on
any push/PR, including the `pages: write`/`id-token: write` deploy job.

*Remediation:* Pin every `uses:` to a full commit SHA with a version comment.

**W9-3 (Medium) — Neither CI workflow runs any lint, format, static-analysis, banned-word, or
secret-scanning step.**

Confirmed absent from both `verify.yml` and `deploy-site.yml` — every step is checkout/setup/a
Gradle test-or-compile invocation, or a Pages action. `docs/RELEASING.md` step 3 explicitly calls
for "the project's restricted-claim scan," but nothing in CI performs one; the only current
enforcement is the `DemoCopyTest` unit test covering the Playground's own copy specifically (see
Lead 6, no finding), not the rest of the repository (docs, other READMEs).

*Impact:* No automated net catches a banned-word regression, a claim-language slip, or a leaked
secret before merge, anywhere outside the Playground's own copy file.

*Remediation:* Add a CI step (or pre-commit hook) that greps tracked text/markdown for the
project's banned-word list and fails the build; cross-reference W3-3's note on the unused AGP
`lint` tasks as a low-cost first step.

**W9-4 (Medium) — `:crypto:jvmTest`/`:shared:jvmTest` run only on the `macos-latest` CI job; a
Linux-only contributor's PR never exercises the native signing/derivation backend.**

Confirmed from the workflow text directly: the Ubuntu job runs `:core:testAndroidHostTest`,
`:crypto:testAndroidHostTest`, etc. (Android-host-JVM, structural/rule tests only per the project's
own testing convention — never a call into the native backend); only the macOS job runs
`:crypto:jvmTest`/`:shared:jvmTest`, which do exercise the real native derivation/signing path. This
is a real platform-artifact gap, not a workflow oversight — no Linux signing-backend native artifact
currently exists (`docs/THIRD_PARTY_NOTICES.md` itself notes Linux/Windows JVM signing artifacts
are future work).

*Impact:* A contributor whose PR only triggers/reviews the Ubuntu job's output never sees the
signing/derivation KAT evidence — they'd need to separately check the macOS job.

*Remediation:* Once a Linux JVM signing-backend artifact exists, mirror these test invocations into
the Ubuntu job; until then, state the platform-coverage asymmetry explicitly in `docs/TESTING.md`.

**W9-5 (Medium) — `README.md:38-44`'s "Expected URL once enabled" wording is honestly hedged in
isolation, but `site/**` is already merged into `origin/main`, so the Pages-deploy trigger has
almost certainly already fired at least once — the site may already be live.**

`origin/main`'s tip (`01d672e`, merge of PR #6) already contains the full `site/` tree with zero
diff against the current working tree, and `deploy-site.yml` triggers on any push to `main` that
touches `site/**` — a condition that merge already satisfied. Whether the deployment actually
published depends on whether the one-time repository Pages setting was enabled at that time, which
cannot be verified without a live network fetch (out of scope per this audit's constraints — see
§6).

*Impact:* A reader could infer from "once enabled" that Pages is a still-pending future step, when
the triggering push may have already happened and the page could already be publicly reachable.

*Remediation:* Verify Pages deployment status in repository settings (or by visiting the URL)
before/at release time, and update the wording to either confirm the live URL or state a concrete
as-of-date if Pages genuinely has not been enabled yet.

**W9-6 (Medium) — The landing page's skip-link target (`<main id="main-content">`) has no
`tabindex="-1"`, so in Safari and older Firefox, activating "Skip to main content" scrolls the
viewport without actually moving keyboard focus there.**

*Impact:* Partial, browser-dependent failure of the one explicit accessibility affordance on the
page for keyboard-only users.

*Remediation:* Add `tabindex="-1"` to `<main id="main-content">`.

**W9-7 (Low) — `LovelaceDisplay.ada(-1L)` produces a garbled string (`"0.0000-1 ADA"`), confirmed
by manual trace of Kotlin's negative-remainder `%` semantics; not reachable today because every
production call site passes an already-validated `Lovelace.value`, whose constructor rejects
negative input, but the function's own signature (`Long`) does not enforce this.**

*Impact:* Latent, not currently reachable — but the four production call sites in
`PlaygroundPresenter.kt` all pass `.value` off a `Lovelace`, not a raw `Long`, and the existing
`LovelaceDisplayTest.kt` tests `Long.MAX_VALUE` but never a negative input.

*Remediation:* Narrow `ada`'s parameter type to `Lovelace` (compile-time enforcement of the
existing invariant) or add an explicit non-negative precondition, plus a test asserting the
negative case is rejected or handled, rather than leaving it untested given the type-widening risk.

**No findings for:** `PlaygroundReducer` purity (184 lines read in full — zero `suspend`, zero
coroutine launches, zero direct SDK imports beyond two `public const val` seed-address string
references); the Playground `ui/*.kt` package import boundary (all 11 files import only from
`playground.*`, none import `:core`/`:crypto`/`:wallet`/`:tx`/`:provider` directly); logging/`println`
calls anywhere in `shared/`, `androidApp/`, or `desktopApp/` (zero matches); mnemonic/private-key
clearing discipline in `PlaygroundPresenter.kt:375-470` (all key-material `var`s cleared
unconditionally in a `finally` block on every return path); `DemoCopyTest`'s coverage of both the
project's banned-word list and a separate protocol-jargon deny list (both lists are distinct,
correctly matched to their respective concerns, and both are exercised against a real, populated
`primaryFacingStrings()` aggregation); iOS-runtime-testing absence from CI (confirmed, but matches
the project's own disclosed limitation, not a hidden gap); the absence of a tag/release-triggered
workflow (confirmed, consistent with `docs/RELEASING.md`'s manual-checklist framing — cross-referenced
with W4-5); every landing-page `aria-labelledby` pair (9/9 valid), heading order (single `h1`,
non-skipping levels), brand-image `alt` text, and every repo-relative link target (all confirmed to
exist in the working tree); first-party artwork provenance (all 8 referenced files exist; the two
Compose source PNGs and their `site/assets/brand/` copies are byte-size-identical, consistent with
the claimed direct-copy relationship — pixel-level confirmation remains a residual risk per §6).

---

## 5. No-finding sections

Each workstream's detailed no-finding items are recorded inline at the end of its findings
subsection in §4 (§4.1–§4.8), immediately after that workstream's numbered findings, each naming
the exact check and command/evidence used. This section is a consolidated index so a reader does
not have to search §4 to confirm an area was checked rather than skipped.

| Area checked | Result | Where documented |
|---|---|---|
| Stray build artifacts / `.DS_Store` / IDE files / `local.properties` in tracked tree | Absent, correctly `.gitignore`-covered | §4.1 |
| Accidental large-object history bloat beyond intentional native binaries | None found | §4.1 |
| Branch-divergence risk (local `main` behind `origin/main`) | Local-clone staleness only; current branch tip already merged | §4.1 |
| Test failures/errors/skips across 1,232 executed tests (JVM + Android host, portable + macOS signing path) | 0 failures, 0 errors, 0 skipped everywhere | §4.2 |
| Gradle wrapper integrity | Pinned `distributionSha256Sum` matches pinned `9.1.0` | §4.2 |
| iOS compile (8 modules, `iosArm64`) | Genuinely compiles clean (forced fresh re-execution) | §4.2 |
| `crypto-signing-backend/README.md` Gradle-version claim vs. pinned wrapper | Matches exactly (9.1.0) | §4.3 |
| Phase 2/3 non-commitment language | Every checked passage properly hedged | §4.3 |
| 3-item spot-check of README "What works" claims | All verified implemented | §4.3 |
| Secret/credential filenames across all 59 commits, 365 distinct paths | None found (one benign false-positive filename match) | §4.4 |
| Blockfrost-style project-id patterns in tree + full history | None found | §4.4 |
| Private-key literals (`xprv1`/`root_xsk1`/`ed25519_sk`) outside allowed test source sets | None found | §4.4 |
| Fixture citation integrity (mnemonic, BIP-39, CIP-3 vectors) | All carry explicit source/commit citations | §4.4 |
| Mainnet address ever paired with a private key/mnemonic in a fixture | None found | §4.4 |
| `PlaygroundState.projectId` persistence | Confirmed never persisted/serialized | §4.4 |
| `project_id` leakage into logs/exceptions | None found | §4.4, §4.7 |
| CBOR uint64-overflow and Address pointer-overflow guards | Both sound; no defeating input constructed | §4.5 |
| ByteArray defensive-copy / equality discipline (12 classes) | All correct; key-material no-equals is by-design | §4.5 |
| `:shared` iOS framework Swift-visible surface | Limited to a bare `UIViewController` factory today | §4.5 |
| Crypto backend delegation (hashing, PBKDF2, derivation, projection, signing) | All 8 call sites delegate to a named external backend | §4.6 |
| "Handwritten crypto?" classification of 4 candidate glue-code sites | All confirmed non-cryptographic | §4.6 |
| Value-conservation identity in `TransactionBuilder` (implementation, not test coverage) | Holds exactly in every branch | §4.7 |
| `project_id` leakage into HTTP error-forwarding paths | None found | §4.7 |
| `PlaygroundReducer` purity | Confirmed pure | §4.8 |
| Playground `ui/*.kt` import boundary | No SDK imports outside `playground.*` | §4.8 |
| Logging/`println` anywhere in `shared/`, `androidApp/`, `desktopApp/` | None found | §4.8 |
| Mnemonic/private-key clearing discipline | Confirmed cleared on every return path | §4.8 |
| `DemoCopyTest` banned-word + jargon coverage | Both lists correctly distinct and exercised | §4.8 |
| iOS-runtime-testing absence from CI | Confirmed, matches disclosed limitation | §4.8 |
| Absence of tag/release-triggered CI workflow | Confirmed, consistent with manual-checklist framing | §4.3, §4.8 |
| Landing-page `aria-labelledby` pairs, heading order, alt text, repo-relative links | All valid/resolve | §4.8 |
| First-party artwork file existence | All 8 referenced files exist | §4.8 |

---

## 6. Residual risks and out-of-scope verification

These checks could not be completed within this audit's constraints (read-only, no live network
calls, this specific host's hardware/software) and require a physical device, an external service,
a different host OS, or an independent specialist. None of them are findings against the SDK —
they are gaps in *this audit's own coverage* that a release decision should account for.

1. **iOS Simulator/device runtime execution.** Confirmed during W3 (E18/E19): this host has Xcode
   26.6 installed but **zero iOS Simulator runtimes** (`xcrun simctl list devices available`
   returns none). `:shared:iosSimulatorArm64Test` and `:crypto-signing-backend:iosSimulatorArm64Test`
   both compiled and linked successfully but failed at execution with "Xcode does not support
   simulator tests for ios_simulator_arm64. Check that requested SDK is installed." This
   independently corroborates — does not contradict — the project's own documented claim
   (`docs/HANDOFF.md:1370-1372`) that iOS runtime execution is environment-gated. **Required:** a
   macOS host with an iOS Simulator runtime installed (or a physical iOS device) to obtain the
   iOS-runtime evidence this audit could not gather itself.

2. **Physical Android device/emulator manual walkthroughs.** The repository's own
   `docs/HANDOFF.md` (2026-08-22 session entry, part of the uncommitted Playground-redesign diff)
   explicitly names these as **owner-required and not yet performed**: light/dark mode, a narrow
   (~360dp) window/device, 200% system font scaling, TalkBack/VoiceOver across the
   Welcome→Demo→Summary journey, and the error-recovery/"Start over"/"Run the demo again" paths.
   This audit did not perform them either (no attached display in this environment, matching the
   same constraint the project's own session hit). **Required:** a physical Android device or
   emulator with a display, driven manually.

3. **Live Blockfrost preprod key / live network path.** This audit did not obtain or use a
   Blockfrost project id and made no live network call to Blockfrost, GitHub, or GitHub Pages, per
   its own read-only/no-live-network-call constraint. The live query/submit path (as opposed to the
   mock path, which was verified via code and unit tests) was not exercised end-to-end.
   **Required:** a live Blockfrost preprod project id and a network-connected run.

4. **GitHub Pages live-deployment status.** W9-5 identified that `site/**` is already merged into
   `origin/main`, which should have satisfied `deploy-site.yml`'s trigger condition — but whether
   the one-time repository Pages setting was enabled at that time, and therefore whether
   `sarmidev.github.io/KardanoSDK` is already publicly live, cannot be determined without visiting
   the URL or the repository's Settings → Pages screen. **Required:** a live check of the
   repository's Pages configuration and/or the URL itself.

5. **GitHub Discussions enablement.** `site/index.html` and `README.md` link to
   `github.com/sarmidev/KardanoSDK/discussions` in three places; whether Discussions is actually
   enabled on the repository (as opposed to 404ing) was not checked, per the same no-live-fetch
   constraint. **Required:** a live check of the repository's Discussions tab.

6. **Linux and Windows JVM hosts.** All build/test evidence in §3/§4.2 was gathered on macOS
   (arm64). The portable-JVM and Android-host-test tasks are expected to behave identically on
   Linux/Windows per `.github/workflows/verify.yml`'s own `ubuntu-latest` job, but this audit did
   not independently verify on either OS, and the signing-backend native artifacts explicitly do
   not yet exist for Linux/Windows JVM at all (per `docs/THIRD_PARTY_NOTICES.md`), so
   `:crypto:jvmTest`/`:crypto-signing-backend:jvmTest`/`:shared:jvmTest` cannot currently be
   executed on either OS by anyone, not just this audit. **Required:** a Linux and/or Windows JVM
   host for the platform-agnostic subset, and a future signing-backend artifact for the
   native-backed subset.

7. **Reproducible-build verification of the ~39.9MB of committed native signing-backend
   binaries.** W5-2 established that no checksum manifest exists and that the repository's own
   README states "there is no CI in this repo" for these artifacts. This audit read the documented
   rebuild recipe and confirmed a functional (behavioral) proof exists via known-answer tests, but
   did not attempt to independently execute the pinned-toolchain Rust/cargo-ndk rebuild and diff the
   result against the committed binaries — doing so requires the exact pinned toolchain versions
   (`rustc 1.97.0`, `cargo-ndk 4.1.2`, NDK `27.2.12479018`) and is a substantial, separate
   undertaking. **Required:** an independent rebuild-and-diff exercise, ideally automated in CI.

8. **Third-party license review by counsel.** W5-1 identified three dependencies whose license
   status is explicitly marked unresolved in the project's own `docs/THIRD_PARTY_NOTICES.md`. This
   audit is not a substitute for a qualified legal review of any dependency's actual license terms,
   including the JNA Apache-2.0/LGPL-2.1 dual-license election. **Required:** legal counsel review
   before a binary/commercial release, per `docs/THIRD_PARTY_NOTICES.md`'s own disclaimer.

9. **Independent cryptographic review.** This audit confirmed that every cryptographic primitive
   delegates to a named, verifiable external backend and that no local reimplementation of a hash/
   PBKDF2/signature primitive exists — but this audit is not a cryptographic protocol review (e.g.
   of CIP-1852/CIP-3 derivation correctness against the Cardano ecosystem's broader interoperability
   expectations, or of the `ed25519-bip32` Rust crate's own implementation). **Required:** a
   specialist independent of this project.

10. **Pixel-level brand-artwork provenance.** W9 Lead 9 confirmed all referenced first-party image
    files exist and that the Compose-source and `site/assets/brand/` copies are byte-size-identical
    (consistent with, but not proof of, being pixel-identical copies). No image-diffing tool was
    available in this environment. **Required:** a manual visual/pixel comparison before relying on
    the provenance claim for a specific derivative (e.g. the resized favicons/og-image).

---

## 7. Appendix

### 7.1 Findings index (all severities, in order found within each workstream)

| ID | Severity | Title |
|---|---|---|
| W1-1 | Low | Uncommitted, unrelated typo in `:core` KDoc mixed into the Playground-redesign diff |
| W1-2 | Informational | `docs/HANDOFF.md` is a large, continuously-growing internal log in the public tree |
| W3-1 | Informational | Two benign "Expression is unused" warnings in generated UniFFI bindings |
| W3-2 | Informational | Audit-methodology note: an initial cache hit was caught and corrected |
| W3-3 | Low | CI runs no lint step despite AGP providing one for free |
| W4-1 | Medium | ADR-0015 §9 stale "Block 1.10c remains open" vs. actual completion |
| W4-2 | Medium | ADR-0017 stale "no Blockfrost implementation… yet" vs. shipped provider |
| W4-3 | Low | `PROJECT_BRIEF.md` delivery-record pointer is one hop removed from the real target |
| W4-4 | Low | Inconsistent "Not audited." disclaimer across module READMEs |
| W4-5 | Medium | `docs/RELEASING.md` is entirely manual/unenforced; no tag-triggered CI |
| W4-6 | Low | `CborValue.kt` diff has no changelog entry |
| W5-1 | High | Three dependencies' license status explicitly unresolved |
| W5-2 | High | No checksum/provenance manifest for committed signing-backend binaries |
| W5-3 | Medium | KotlinCrypto hash dependencies missing from `THIRD_PARTY_NOTICES.md` |
| W5-4 | Medium/Low | Six pinned dependencies are pre-1.0/alpha/beta |
| W5-5 | Low | `BlockfrostConfig`'s generated `equals`/`hashCode` retain the raw project id |
| W6-1 | Medium | `Hashing.blake2b224`/`256` enforce no input-size bound |
| W6-2 | Medium | `Cbor.encode` has no total-output-size cap |
| W6-3 | Low | `Bech32.convertBits` bounds only one direction |
| W6-4 | Low | "Zero `@Throws` repository-wide" claim is imprecise as literally stated |
| W7-1 | High (release-readiness) / by-design (dev-scope) | `signTransaction`'s unused `network` param and no fixture check; mainnet reachable |
| W8-1 | Medium | No direct test for the value-conservation identity |
| W8-2 | Medium | Native-asset filtering is silent; no error field distinguishes cause |
| W8-3 | Low | No HTTP timeout/retry policy; inconsistent per-platform defaults |
| W8-4 | Low | Broad exception catches lose type fidelity; `RemoteStatus` field asymmetry |
| W9-1 | High | Live/mock UI honesty gap plus Submit-step error misclassification |
| W9-2 | Medium | CI actions pinned by floating tag, not commit SHA |
| W9-3 | Medium | No lint/format/banned-word/secret-scan CI step |
| W9-4 | Medium | Native signing-path tests run only on the macOS CI job |
| W9-5 | Medium | Landing-page "expected URL once enabled" wording may already be stale |
| W9-6 | Medium | Landing-page skip-link missing `tabindex="-1"` |
| W9-7 | Low | `LovelaceDisplay.ada` negative-input formatting defect (unreachable today) |

### 7.2 Reconnaissance inventories

Full file-by-file inventories, capability/status claim tables (with path:line citations for every
claim in `README.md`, `docs/ROADMAP.md`, `CHANGELOG.md`, `docs/QUICKSTART.md`, `shared/README.md`,
`site/index.html`), the banned-word scan, and per-module test/source-set breakdowns were produced
during this audit's reconnaissance phase and are not reproduced in full here to keep this document
navigable; they are available in the session transcript and were the basis for the claim
cross-checks in §4.3. The dependency and native-binary inventories referenced in §4.4/§4.6 are
summarized inline in those findings.

---

## 8. Addendum (2026-08-23): severity-count correction and post-audit remediation status

**This addendum corrects factual errors in this report's own executive summary and records what
has changed in the repository since this report was written. It does not re-run the underlying
audit, does not add or remove findings, and does not certify anything — it is a factual
correction plus a status update, produced during the first remediation pass that followed this
report.**

### 8.1 Severity-count correction

§1's opening paragraph states "32 findings (2 High, 15 Medium, 10 Low, 5 Informational)". §7.1's
own findings-index table — which this correction takes as authoritative, since each row's
severity is individually justified in its own finding text in §4 — does not support that
breakdown. Counting every row in §7.1 exactly as labeled:

| Severity (as labeled in §7.1) | IDs | Count |
|---|---|---|
| High (unconditional) | W5-1, W5-2, W9-1 | 3 |
| High (release-readiness) / by-design (dev-scope) — dual | W7-1 | 1 |
| Medium (unconditional) | W4-1, W4-2, W4-5, W5-3, W6-1, W6-2, W8-1, W8-2, W9-2, W9-3, W9-4, W9-5, W9-6 | 13 |
| Medium/Low — dual | W5-4 | 1 |
| Low (unconditional) | W1-1, W3-3, W4-3, W4-4, W4-6, W5-5, W6-3, W6-4, W8-3, W8-4, W9-7 | 11 |
| Informational | W1-2, W3-1, W3-2 | 3 |
| **Total** | | **32** |

The total (32) matches the original claim; the per-severity breakdown does not: High was
undercounted (2 claimed vs. 3 unconditional), Medium was overcounted (15 claimed vs. 13
unconditional), Low was undercounted (10 claimed vs. 11 unconditional), and Informational was
overcounted (5 claimed vs. 3 actual). The errors net to zero, consistent with an arithmetic/
bucketing slip in the executive summary's rolled-up sentence rather than a deliberate alternate
classification — no individual finding's own severity label in §4/§7.1 is being changed by this
correction, and no finding is reclassified here.

**W7-1's dual rating is preserved, not collapsed.** W7-1 evaluates the same code
(`ReadOnlyWallet.signTransaction`'s unused `network` parameter, no fixture check, public
`Network.MAINNET`) under two frames, both stated in the finding's own text (§4.6): by-design and
acceptable for the project's current internal development scope, versus High once the SDK becomes
a public, installable artifact. Depending on which frame a reader applies:

- Internal-development-scope frame: **3** unconditional High findings (W5-1, W5-2, W9-1); W7-1 is
  not counted as High under this frame.
- Public-release-readiness frame (the frame that matters for a first public release): **4**
  release-relevant High findings (W5-1, W5-2, W9-1, W7-1).

Similarly, W5-4 is Medium for its two 0.x cryptographic-hash dependencies and Low for its
UI-only alpha/beta entries — both halves are already stated explicitly in the finding's own text
(§4.4) and are not merged into a single number here.

**This audit is not a certification.** As stated in §1's own epigraph, "this audit does not
certify the absence of defects." This addendum does not change that; it corrects only the
executive summary's arithmetic. It remains true, as originally stated, that every findings-index
severity label (§7.1) is individually argued in §4 and should be read there, not from the
top-line sentence alone.

### 8.2 Post-audit remediation status: W9-1 and W9-7 already resolved

This audit's stated baseline (§2.1) was commit `094ec8c` plus an uncommitted, ~1,755-line
Playground-redesign working tree. That exact working tree has since been **committed** as
`61c852a` ("Redesign Playground as a guided demo", 2026-08-23), one commit ahead of this report's
baseline. That commit already contains a complete, tested fix for **W9-1**:

- `PlaygroundState.isLivePreprodActive` (`useLiveBlockfrost && projectId.isNotBlank()`) is now the
  single derived flag every UI/classification site uses instead of the raw toggle.
- `PlaygroundDemoFlow.outcome()` classifies the mock Submit stop as `INFO` using
  `!state.isLivePreprodActive`, not `!state.useLiveBlockfrost` — the exact defect this finding
  cited.
- The Advanced-panel label (`DemoStepSection.kt`) now branches
  `isLivePreprodActive -> "Live test network..."`, `useLiveBlockfrost (only) -> "...not
  connected..."`, `else -> "Demo mode..."` — three explicit provider states instead of one
  toggle-derived claim.
- The Summary recap line (`SummarySection.kt`) keys off the actually-observed
  `state.submit is Success`, stricter than the toggle-derived flag.
- New/extended tests assert this directly:
  `PlaygroundDemoFlowTest.outcome_submit_mockNotSupportedFailure_isInfoUntilLivePreprodIsActuallyConfigured`,
  plus updated `PlaygroundReducerTest`, `DemoCopyTest`, `PlaygroundMockFlowDesktopTest`, and
  `PlaygroundViewModelTest`.

**W9-1's own residual risk is not closed.** The manual Android/Desktop walkthrough
(light/dark mode, a narrow ~360dp window, 200% font scaling, TalkBack/VoiceOver, and the
error-recovery/"Start over"/"Run the demo again" paths) that this report's §6 item 2 and the
project's own `docs/HANDOFF.md` name as owner-required has **still not been performed** as of this
addendum — no device/emulator with a display has been available in any session to date. This
remains open and must be completed, and its outcome recorded, before the guided demo is used to
record the public release video (see the final re-audit gate in the remediation plan this
addendum accompanies).

**W9-7** (`LovelaceDisplay.ada(-1L)` producing a garbled string) is also resolved, at commit
`8a6339f`: `LovelaceDisplay.ada` now takes a `Lovelace` instead of a raw `Long`, so a negative
amount is rejected at `Lovelace.of` construction time before it can reach the formatter at all,
with a test (`LovelaceDisplayTest.negativeLovelace_isRejectedAtConstructionBeforeItCanReachAda`)
pinning the rejection.

**W1-1/W4-6 required no code change.** Re-investigating during this remediation pass found that
the one-character `CborValue.kt` KDoc typo this report described was **never committed to git
history** — `git show 094ec8c:core/.../CborValue.kt` (this report's own baseline commit) already
reads "only ever produces"; the typo existed only as an uncommitted, ephemeral working-tree edit
at the time this report was written. Discarding that stray edit (restoring the working tree to
match already-committed, already-correct text) fully resolves both findings; no `CHANGELOG.md`
entry was added, since no committed or released behavior was ever affected.

### 8.3 New baseline

As of this addendum, `git rev-parse HEAD` is `8a6339f` (working tree clean apart from this
report's own `docs/AUDIT/` addition). This is the commit subsequent remediation work and the
final re-audit gate should be measured against, superseding `094ec8c` as the reference point for
"what has changed since the original audit."
