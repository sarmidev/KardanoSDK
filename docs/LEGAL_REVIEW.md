# Legal Review — Distribution Evidence Checklist

**This is an evidence checklist and template for owner/counsel review. It is
not legal advice, not a legal opinion, and not counsel approval. Nothing in
this file, `NOTICE`, `LICENSES/`, `docs/THIRD_PARTY_NOTICES.md`, or
`docs/evidence/` states that Kardano SDK is cleared to release, and nothing
in it should be read that way.**

Every factual field below is machine-checked by
`scripts/check_release_evidence.py` (run in CI by `verify.yml`,
job `legal-evidence-scan`, in its default `ci-structural` mode) and is
regenerated deterministically by `scripts/generate_legal_evidence.py`. Open
review fields use one of the literal markers in that script's
`ALLOWED_OPEN_GATE_MARKERS`; any other unresolved filler text fails the
checker, and `--mode release` additionally fails while ANY such marker is
still present anywhere in this file (see §14).

**2026-08-24, independent-review correction.** An earlier version of this
packet made several claims an independent review found to be false,
overreaching, or insufficiently fail-closed: it claimed no MIT-only
distributed component existed (false — see §4/§5), it drew legal conclusions
about MPL-2.0/UniFFI obligations being "satisfied" (removed — see §6/§6b),
it used one merged 69/63-package Cargo closure instead of a separate graph
per committed target triple (replaced — see §9), it called
`LICENSES/BouncyCastle.txt` "fetched" rather than manually transcribed
(corrected — see §7), and its generator/checker had several structural gaps
(dynamic scope discovery, symlink rejection, strict byte parsing, exact
digest-file recomputation — all addressed in the same change that added this
paragraph). This paragraph is a factual changelog entry, not a claim that
every gap is now closed to counsel's satisfaction.

## 1. Candidate commit / tag scope

| Field | Value |
|---|---|
| Candidate commit | `c65a20acf485bf842b90655fcc6967ade4474671` (start of this packet's work; see §12 for why this is not the same as "the commit that carries this file") |
| Candidate tag | None. No tag exists yet; this packet is prepared for a future tagged review, not for one commit alone. |
| Branch | `fix/native-build-and-platform-evidence` (stacked; Prompt 7) |
| Scope statement | ADA-only, testnet/preprod, Phase 1 fixture-scoped signing (ADR-0015/ADR-0019). No mainnet. Windows x86-64 JVM signing backend is candidate-only and excluded from this scope (see §11). |

## 1a. Distribution scope: modules, sample apps, installers

The 10 Gradle modules below are discovered dynamically from
`settings.gradle.kts` (`scripts/generate_legal_evidence.py`
`discover_gradle_modules()`), not read off a static list that could drift
from the actual project. §5/§8's Gradle-runtime inventory covers exactly
these 10 modules' resolved runtime dependency graph; there is no unlisted
Gradle module in this repository.

| Category | Modules | Distribution status |
|---|---|---|
| SDK library modules | `core`, `crypto`, `provider`, `provider-blockfrost`, `tx`, `wallet`, `crypto-signing-backend` | The redistributable Kotlin Multiplatform SDK surface; source is distributed on this tag/branch, and their resolved runtime/native dependencies are the subject of §5/§8/§9/§10 |
| Sample-app / demo modules | `androidApp`, `desktopApp`, `shared` | Demonstration code only (the Playground), not published as a library artifact; `shared` is the cross-platform Playground UI/presenter layer consumed by the sample apps, not part of the SDK's own public API |
| Non-Gradle sample app | `iosApp` (Xcode project, not in `settings.gradle.kts`; out of scope for the Gradle-lockfile-based inventory below) | Demonstration code only |

**Desktop MSI/DEB/DMG installers are not planned for this release and this
packet does not claim their native-payload runtime inventory is complete.**
`desktopApp/build.gradle.kts` configures Compose Multiplatform
`nativeDistributions { targetFormats(TargetFormat.Dmg, TargetFormat.Msi,
TargetFormat.Deb) }` — the packaging capability exists in the build script —
but no workflow under `.github/workflows/` invokes `packageDmg`, `packageMsi`,
`packageDeb`, or any other `jetbrains.compose.desktop` packaging task; Ubuntu
`Verify` does not even compile `:desktopApp` (`docs/DEPENDENCY_REVIEW.md`),
and no released, downloadable installer artifact exists anywhere in this
repository's CI or release process. `:desktopApp:run` (a plain JVM run, not a
packaged installer) is the only way `desktopApp` is currently exercised. If
a future release does package and distribute one of these installer
formats, this section, `docs/evidence/maven_native_carriers_inventory.json`,
and a per-OS embedded-native inventory generated on an actual Windows/Linux/
macOS runner (not guessed) must be added before that release is evidenced as
GO — this packet does not attempt to guess what such a build would embed.

## 2. Reviewer / counsel / date

| Field | Value |
|---|---|
| Preparer | Automated evidence-generation session (this repository's AI working agreement, `docs/AI_WORKING_AGREEMENT.md`) |
| Preparation date | 2026-08-24 |
| Counsel reviewer | OPEN — pending owner/counsel review |
| Counsel review date | OPEN — pending owner/counsel review |
| Counsel determination | OPEN — pending owner/counsel review |

## 3. Digests (from `docs/evidence/LEGAL_EVIDENCE_DIGEST.txt`)

Regenerate with `python3 scripts/generate_legal_evidence.py`; every digest
below is independently recomputed byte-for-byte by
`scripts/check_release_evidence.py`'s `check_digest_file_exact`, which also
confirms the `licenses_files=`/`expected_evidence_files=` lines list exactly
the files present on disk (no extra, no missing).

| Field | SHA-256 |
|---|---|
| Gradle lock digest (all Gradle modules discovered from `settings.gradle.kts`, concatenated in sorted module-name order) | `4339a9ed4fb19ba4aae22eb4dae1abc8334d557ba4a2f3c2278acc6b92ad007e` |
| Cargo.lock digest (`crypto-signing-backend/Cargo.lock`) | `855373baa265413f3929a85bb90aa83f137674fe58c6324b5d4de3cce2f93d8e` |
| Native CHECKSUMS digest (`crypto-signing-backend/CHECKSUMS.sha256`) | `55c3b131434372528c1f824fee35ab2df2092e6261f8e496e2b0b128110393d9` |
| NOTICE digest | `13e9343f0da90b29538ad5f1b95b0218d6c1d5f141f85e00cbf90cda5dc7a3c6` |
| LICENSES digest (all `LICENSES/*.txt`, concatenated in sorted filename order) | `d6512311a2d960e173f2f02963291b4dbc69e4d43e67e4cfebd2771f73a81857` |

## 4. NOTICE / LICENSES inventory

| Field | Value |
|---|---|
| Root NOTICE | `NOTICE` (repo root) |
| License texts committed | `LICENSES/Apache-2.0.txt`, `LICENSES/MPL-2.0.txt`, `LICENSES/ISC-libsodium.txt`, `LICENSES/MIT.txt`, `LICENSES/Unicode-3.0.txt`, `LICENSES/BouncyCastle.txt` (see `LICENSES/README.md` for source/method and SHA-256 of each) |
| MIT-only components found | `org.slf4j:slf4j-api` (Gradle, real runtime dep), `com.goterl:resource-loader` (Gradle, transitive), `bytes`/`cargo_metadata`/`zmij` (Cargo, linked into all 9 native artifacts) — see `docs/evidence/gradle_license_inventory.json` `mit_only_coordinates` and `docs/evidence/cargo_dependency_inventory.json` `mit_only_linked_packages` |
| Unicode-3.0 component found | `unicode-ident` (Cargo; compound `(MIT OR Apache-2.0) AND Unicode-3.0`; proc-macro-support-only per §9, not in any target's linked set) |
| Cross-check | `scripts/check_release_evidence.py` fails if NOTICE cites a `LICENSES/*.txt` file that does not exist, if a committed `LICENSES/*.txt` file is never cited by NOTICE, or if either inventory above is non-empty while `LICENSES/MIT.txt` is missing |

## 5. Package-level license/election mapping

Every Gradle-runtime coordinate (across every module discovered from
`settings.gradle.kts`) and every Cargo package linked into at least one of
the 9 committed native-artifact target triples is resolved to a license in
generated evidence, not narrated by hand here:

| Report | Coverage | Method |
|---|---|---|
| `docs/evidence/gradle_license_inventory.json` | `resolved_count`/`runtime_coordinate_count` of all Gradle-runtime coordinates | `scripts/license_catalog.py` (curated, dated) first, then the coordinate's own POM `<licenses>` block from the local Gradle module cache |
| `docs/evidence/cargo_dependency_inventory.json` | Every package reachable in any of the 9 target-triple graphs | The package's own `license` field from `cargo metadata` (Cargo.toml, not guessed) |

A dual/OR license (e.g. `Apache-2.0 OR LGPL-2.1-or-later`) is recorded with
an explicit `election` value only when the coordinate's own POM/Cargo.toml
genuinely lists more than one license; a single-license coordinate (e.g.
`org.slf4j:slf4j-api`, MIT-only) has `election: null` and is never treated
as if an `Apache-2.0 OR X` election elsewhere covers it. This is the exact
mistake the 2026-08-24 independent review flagged.

### 5a. Elections made, and the reviewer-acceptance gate for each

| Coordinate | Available licenses (source) | Elected | Reviewer acceptance |
|---|---|---|---|
| `net.java.dev.jna:jna:5.19.1` | Apache-2.0 OR LGPL-2.1-or-later (own POM) | Apache-2.0 | OPEN — pending per-election reviewer acceptance |
| `ed25519-bip32` (Rust, 0.4.2) | MIT OR Apache-2.0 (own Cargo.toml) | Apache-2.0 | OPEN — pending per-election reviewer acceptance |
| `cryptoxide` (Rust, 0.5.3, transitive) | MIT/Apache-2.0 (own Cargo.toml) | Apache-2.0 | OPEN — pending per-election reviewer acceptance |

Compound (not disjunctive) expressions found — no election applies, but each
still needs a named reviewer determination that this repository's build-time
vs. linked-in classification is accepted:

| Coordinate | Expression (source) | This repo's classification | Reviewer acceptance |
|---|---|---|---|
| `unicode-ident` (Rust, 1.0.24) | `(MIT OR Apache-2.0) AND Unicode-3.0` (own Cargo.toml) | proc-macro-support-only; not linked into any of the 9 targets (`docs/evidence/cargo_dependency_inventory.json`) | OPEN — pending per-election reviewer acceptance |
| `linux-raw-sys` (Rust, 0.12.1) | `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT` (own Cargo.toml) | Linux/Android target-linked (per §9); Apache-2.0-with-exception branch not separately elected | OPEN — pending per-election reviewer acceptance |
| `r-efi` (Rust, 6.0.0, transitive via `getrandom`) | `MIT OR Apache-2.0 OR LGPL-2.1-or-later` (own Cargo.toml) | present in Cargo.lock; membership per target in `docs/evidence/cargo_dependency_inventory.json` | OPEN — pending per-election reviewer acceptance |

No election is recorded for `org.slf4j:slf4j-api`, `com.goterl:resource-loader`,
`bytes`, `cargo_metadata`, or `zmij` (all single-license MIT, no `OR` clause
in their own metadata) — they need only `LICENSES/MIT.txt` (§4), not an
election.

## 6. MPL-2.0 obligations — OPEN, not asserted satisfied

MPL-2.0 is file-level, not whole-program, copyleft (MPL-2.0 §3.1–§3.2).
Kardano SDK does not modify the Source Code Form of either MPL-2.0 component
below. **Whether directing recipients to the upstream repository fully
discharges every MPL-2.0 obligation for a dependency that is compiled/linked
into a distributed binary (as opposed to merely redistributed unmodified) is
an OPEN counsel determination.** An earlier version of this file asserted
this obligation was satisfied and did not require Kardano SDK's own source
to be released under MPL-2.0; that legal conclusion is removed here.

| Component | Distributed as | Fact | Counsel determination |
|---|---|---|---|
| `com.goterl:lazysodium-android` 5.2.0 | Android `.aar`, unmodified | Recipients can obtain the Source Code Form from `github.com/terl/lazysodium-android` | OPEN — pending owner/counsel review |
| `uniffi` Rust crate `=0.29.5` | Compiled/linked into all 9 committed native artifacts (§9) | Recipients can obtain the Source Code Form from `github.com/mozilla/uniffi-rs`; generated binding files are inventoried in `docs/evidence/uniffi_bindings_inventory.json` (same unresolved status, not concluded there either) | OPEN — pending owner/counsel review |

## 6b. Identus `apollo` embedded native — Apache-2.0 wrapper, MPL-2.0 uncertainty

`org.hyperledger.identus:bip32-ed25519-android` 1.8.8's own POM declares
Apache-2.0. Its `.aar` also bundles a compiled native library per Android ABI
(`libuniffi_ed25519_bip32_wrapper.so`; see
`docs/evidence/maven_native_carriers_inventory.json`). This repository has
**not** obtained that native library's own source or build-time dependency
graph, and does **not** claim an exact source-to-binary mapping for it. Given
the library name (`libuniffi_...`), it plausibly links a UniFFI runtime the
same way this repo's own `crypto-signing-backend` does — which would carry
the same MPL-2.0 file-level question as §6 — but this is stated as a
plausible, unverified structural similarity, not a fact. Whether the
Apache-2.0 wrapper license covers the whole distributed `.so`, and whether an
embedded MPL-2.0 (or other) component changes that, is an **OPEN counsel
determination**, tracked separately from — and not resolved by — upstream
`hyperledger-identus/apollo` issue #226 (which is about the missing
`win32-x86-64` build, a distribution-availability gap, not a license
question).

| Field | Value |
|---|---|
| Wrapper POM license | Apache-2.0 |
| Embedded native's own license/source graph | Not obtained; not reviewed |
| Structural similarity to this repo's own MPL-2.0 exposure (§6) | Plausible (same generator family), unverified |
| Windows build availability | Not published upstream (issue #226) — a distribution gap, not this license question |
| Determination | OPEN — pending owner/counsel review |

## 7. Bouncy Castle — transcription vs. source-HTML hash

`LICENSES/BouncyCastle.txt` is a **manual transcription** of the license
paragraphs rendered at `https://www.bouncycastle.org/licence.html`, typed on
2026-08-24 — it is **not** the fetched HTML bytes, and its SHA-256 cannot be
reproduced by re-fetching that URL the way the other five `LICENSES/*.txt`
files can. `docs/evidence/bouncycastle_license_source.json` records both
hashes as independently verifiable facts:

| Field | Value |
|---|---|
| Source URL | `https://www.bouncycastle.org/licence.html` |
| Source HTML snapshot (committed, for independent re-checking) | `docs/evidence/license-sources/bouncycastle-licence-2026-08-24.html` |
| Source HTML SHA-256 | See `docs/evidence/bouncycastle_license_source.json` `source_html_sha256` (recomputed and cross-checked by `scripts/check_release_evidence.py` on every run) |
| Transcription SHA-256 (`LICENSES/BouncyCastle.txt`) | `3216ec8f5e256138322eb8d7adb2c7d176af83e29193e38041a62a83ab55fd63` |
| These two hashes are expected to differ | Yes — one is raw HTML with site markup, the other is plain transcribed text; a match would actually be suspicious |
| Transcription faithfulness/completeness | OPEN — pending owner/counsel review |

## 8. Native carriers (third-party Maven artifacts bundling compiled binaries)

Distinct from `crypto-signing-backend/CHECKSUMS.sha256` (§10), which lists
only first-party binaries built from this repository's own Rust crate. Full
detail, including every embedded member path and size: `docs/evidence/
maven_native_carriers_inventory.json` (point-in-time inspection, 2026-08-24 —
see §13 for why this is not re-derived live on every run).

| Coordinate | Carrier kind | Embedded natives | Windows build upstream? |
|---|---|---|---|
| `net.java.dev.jna:jna:5.19.1` | JVM/Android jar | 25 platform-specific `libjnidispatch` binaries (all bundled in the one jar; only one loads per host) | Yes (`win32-x86-64`, `win32-aarch64`) |
| `org.hyperledger.identus:bip32-ed25519-android:1.8.8` | Android `.aar` | 4 (`libuniffi_ed25519_bip32_wrapper.so` per ABI) | No (issue #226; see §6b) |
| `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings-jvm:0.9.5` | JVM `.jar` | 4 (libsodium per OS/arch, including a Windows `.dll`) | Yes |
| `com.goterl:lazysodium-android:5.2.0` | Android `.aar` | 4 (`libsodium.so` per ABI) | No (Android-only carrier) |
| `org.jetbrains.skiko:skiko-awt-runtime-macos-arm64:0.144.6` | JVM `.jar` (desktopApp sample only) | 2 (macOS Skia `.dylib`, arm64 + x64) | No (only macOS-arm64 variant resolved in this repo's lockfiles) |

Do not classify JNA as source-only (§5's election table is about the
*source* license; this table is about the *separate* fact that the same jar
also carries compiled binaries).

## 9. Cargo per-target-triple inventory (9 separate graphs)

Replaces an earlier single merged 69-package/63-linked heuristic, which
could not distinguish "linked into target X" from "linked into target Y" and
(before an independent-review fix in this same change) incorrectly counted
`uniffi`'s optional, never-activated `bindgen`/`cli`-feature dependency chain
(`uniffi_bindgen`, `askama`, `goblin`, `nom`, `weedle2`, `textwrap`, `smawk`,
`clap`) as linked. `docs/evidence/cargo_dependency_inventory.json`'s
`method` field documents the current two-tool approach
(`cargo metadata --filter-platform` for per-package facts, `cargo tree` for
the real feature-activation-correct reachable set) and why `cargo metadata`
alone was insufficient.

| Target triple | Committed artifact | Linked | Proc-macro + support | Host build-only | Dev-only |
|---|---|---|---|---|---|
| `aarch64-apple-darwin` | `darwin-aarch64/*.dylib` | 32 | 12 | 1 | 0 |
| `x86_64-apple-darwin` | `darwin-x86-64/*.dylib` | 32 | 12 | 1 | 0 |
| `aarch64-linux-android` | `arm64-v8a/*.so` | 33 | 12 | 1 | 0 |
| `armv7-linux-androideabi` | `armeabi-v7a/*.so` | 33 | 12 | 1 | 0 |
| `i686-linux-android` | `x86/*.so` | 33 | 12 | 1 | 0 |
| `x86_64-linux-android` | `x86_64/*.so` | 33 | 12 | 1 | 0 |
| `aarch64-apple-ios` | `iosArm64/*.a` | 32 | 12 | 1 | 0 |
| `aarch64-apple-ios-sim` | `iosSimulatorArm64/*.a` | 32 | 12 | 1 | 0 |
| `x86_64-unknown-linux-gnu` | `linux-x86-64/*.so` | 33 | 12 | 1 | 0 |

Total distinct package/version/source combinations across all 9 graphs
combined: `package_count` = 46 (`docs/evidence/cargo_dependency_inventory.json`);
33 of those 46 are `linked_into_compiled_artifact` in at least one target
(`linked_in_any_target_count`).

`dev_dependency_only` is 0 for every target because this crate declares no
`[dev-dependencies]`, and Cargo never activates a dependency's own
dev-dependencies when it is built as a library dependency of another crate
(documented, not just observed, in the report's `method` field). The single
`host_build_dependency_only` package for every target is `autocfg` (used only
by `fs-err`'s `build.rs`, itself a support dependency of `uniffi_macros`).
The Darwin/iOS totals (32 linked) are one lower than Linux/Android (33
linked) because `getrandom`'s Linux/Android-only backend pulls in one extra
platform-gated package not needed on Darwin/iOS; see the per-target
`membership_by_target` object in the JSON for the exact package-level diff.

Do not hand-copy the full per-package table here; read
`docs/evidence/cargo_dependency_inventory.json` `packages[]`, each with
`version`, `source`, `license` (from Cargo.toml, not guessed), and
`cargo_lock_checksum` (the crates.io tarball digest Cargo itself pins in
`Cargo.lock`, not a digest invented by this script).

## 10. Committed native provenance (9 artifacts)

Exact mapping of all 9 rows in `crypto-signing-backend/CHECKSUMS.sha256` to
platform/arch/source owner/hash/provenance/rebuild workflow is generated at
`docs/evidence/native_artifacts_inventory.json` and cross-checked against the
CHECKSUMS file, and against every native binary file `git ls-files` finds
under `crypto-signing-backend/src/`, by `scripts/check_release_evidence.py`
(exact-match in both directions — no extra, missing, or uninventoried row).

| Field | Value |
|---|---|
| Row count | 9 (checked: exactly 9, not "at least 9") |
| 10th candidate row | Windows x86-64 JVM (`win32-x86-64/kardano_ed25519_bip32_signing.dll`) — technical GO on PE-structure evidence, explicitly **not** added to CHECKSUMS.sha256 or the generated catalog. See §11. |

## 11. Not distributed (explicit statement)

| Item | Status | Detail |
|---|---|---|
| Windows x86-64 JVM signing-backend candidate DLL | Not distributed | Technical GO on native-artifact PE evidence; withheld until the two named gates in §14 are resolved (independent PE re-review; upstream issue #226) |
| Identus `apollo` Android derivation-backend native library, Windows build | Not distributed by Kardano SDK | Upstream (`hyperledger-identus/apollo`) has not published a `win32-x86-64` build; Kardano SDK cannot distribute what upstream has not built — tracked as upstream issue #226 |

## 12. Scope binding: subject commit/tree vs. evidence-packet commit/tree

`docs/evidence/scope_binding.json`'s `subject_commit`/`subject_tree` are the
repository `HEAD` **at generation time** — necessarily the parent of
whatever commit later carries that generated file, because a commit cannot
record the hash of its own resulting tree in advance. This is a structural
property of Git, not a gap in this script: there is no way to make this
field self-referential, and this file does not pretend otherwise.

To verify the binding for a specific evidence-packet commit `E`:

```bash
git log -1 --format='%H %T' E^   # the commit BEFORE E
cat docs/evidence/scope_binding.json   # E's own committed subject_commit/subject_tree
# subject_commit/subject_tree in E must equal E^'s hash/tree above
```

`scripts/check_release_evidence.py` checks that `scope_binding.json`
regenerates with the same *keys* (structural shape) but does not require the
*values* to stay fixed across commits — `subject_commit` is expected to
change every time `HEAD` changes, by design.

## 13. Network and cache dependency (determinism)

Two of the seven generators in `scripts/generate_legal_evidence.py` are
**not** reproducible from the tracked tree alone on a machine that has not
already resolved certain dependencies:

- `gradle_license_inventory()` falls back to the local Gradle module cache
  (`GRADLE_USER_HOME/caches/modules-2/files-2.1/.../*.pom`) for any
  coordinate not in the curated `scripts/license_catalog.py`. On a machine
  whose cache does not have a given coordinate's POM already resolved (e.g.
  a clean CI container that has not run the corresponding Gradle task), that
  coordinate is reported in `unresolved` rather than guessed. This is a
  **read-only** cache lookup — the generator never triggers a network fetch
  or Gradle invocation itself, so it cannot silently mutate a lockfile.
- `maven_native_carriers_inventory()` is a **static, dated table** (2026-08-24
  point-in-time inspection of specific resolved artifact bytes), not a live
  re-derivation, precisely so that this generator never needs network access
  to reproduce it. Re-verify by re-running the `unzip -l`/hash commands
  against a freshly resolved copy of the same coordinate+version before
  relying on this table for a release decision.

Every Cargo invocation (`cargo metadata --locked --filter-platform <triple>`
and `cargo tree --locked --target <triple> -e <edges>`) hashes
`crypto-signing-backend/Cargo.lock` immediately before and immediately after
the call and raises a fail-closed `EvidenceError` if the hash changed —
`--locked` is required to make Cargo refuse to update the lockfile rather
than silently doing so, and this script independently verifies that refusal
instead of trusting the flag alone. `verify.yml`'s `legal-evidence-scan` job
additionally runs `git diff --exit-code -- docs/evidence` after regenerating
twice, so a CI run cannot silently commit drifted evidence either.

## 14. Unresolved / decision fields

| Field | Status | Detail |
|---|---|---|
| Counsel review | OPEN — pending owner/counsel review | Every §2/§5a/§6/§6b/§7 field naming this marker |
| Upstream Identus win32-x86-64 build | OPEN — pending upstream hyperledger-identus/apollo issue #226 | §6b, §11 |
| Windows signing-backend PE re-review | OPEN — pending independent PE re-review | §11 |
| Per-election reviewer acceptance | OPEN — pending per-election reviewer acceptance | §5a (3 elections, 3 compound expressions) |
| Release / tag decision | Not made in this packet | This packet prepares evidence only; it does not recommend, schedule, or make a release decision |

## 15. Gate cross-references

- Independent PE re-review gate: see `docs/HANDOFF.md` Branch-Stack Status
  (Prompt 7) and `crypto-signing-backend/README.md` "Windows x86-64 —
  candidate-only".
- Upstream Identus issue #226: see `docs/HANDOFF.md` "Next Recommended Task"
  and `docs/DEPENDENCY_PROVENANCE.md`.
- MPL-2.0/Identus-embedded-native counsel determinations: §6/§6b above; not
  restated with different wording anywhere else.
- This packet does not change any of these gates' status. All remain open
  after this change.

## Regeneration and verification

```bash
python3 scripts/generate_legal_evidence.py   # writes docs/evidence/*
python3 scripts/generate_legal_evidence.py   # run a second time
git diff --quiet docs/evidence                # expect no diff (subject_commit unchanged if HEAD didn't move)
python3 scripts/check_release_evidence.py               # ci-structural mode (CI default)
python3 scripts/check_release_evidence.py --mode release  # expected to fail today
python3 -m unittest discover -s scripts/tests -p "test_*.py"
```

Do not treat a passing `ci-structural` run as legal clearance. It only
confirms that the evidence packet is internally consistent, deterministic,
dynamically scoped (no uninventoried module/file/native binary), and free of
unresolved generic filler text or an unsupported claim of release sign-off —
not that counsel has reviewed it or that a release decision has been made.
`--mode release` is expected to keep failing, and list every still-present
named gate, until that review actually happens.
