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
| NOTICE digest | `99f67c0bb0ba4386bf697815b9613e1e811ce3fb74eccb10b60e41940dd9971d` |
| LICENSES digest (all `LICENSES/*.txt`, concatenated in sorted filename order) | `3553cfb8536b72b63824e4248751e1c9057b5a449dce6e3a79523dd330de9c26` |

## 4. NOTICE / LICENSES inventory

| Field | Value |
|---|---|
| Root NOTICE | `NOTICE` (repo root) |
| License texts committed | `LICENSES/Apache-2.0.txt`, `LICENSES/MPL-2.0.txt`, `LICENSES/ISC-libsodium.txt`, `LICENSES/MIT.txt`, `LICENSES/Unicode-3.0.txt`, `LICENSES/Unlicense.txt`, `LICENSES/BouncyCastle.txt` (see `LICENSES/README.md` for source/method and SHA-256 of each) |
| MIT-only components found | `org.slf4j:slf4j-api` (Gradle, real runtime dep), `com.goterl:resource-loader` (Gradle, transitive), `bytes`/`cargo_metadata`/`zmij` (Cargo, linked into all 9 native artifacts) — see `docs/evidence/gradle_license_inventory.json` `mit_only_coordinates` and `docs/evidence/cargo_dependency_inventory.json` `mit_only_linked_packages` |
| Unicode-3.0 component found | `unicode-ident` (Cargo; compound `(MIT OR Apache-2.0) AND Unicode-3.0`; proc-macro-support-only per §9, not in any target's linked set) |
| Cross-check | `scripts/check_release_evidence.py` fails if NOTICE cites a `LICENSES/*.txt` file that does not exist, if a committed `LICENSES/*.txt` file is never cited by NOTICE, or if either inventory above is non-empty while `LICENSES/MIT.txt` is missing |

## 5. Package-level license/election mapping

Every Gradle-runtime coordinate (across every module discovered from
`settings.gradle.kts`) and every Cargo package reachable in any of the 9
target-triple graphs is resolved to a license in generated evidence, not
narrated by hand here:

| Report | Coverage | Method |
|---|---|---|
| `docs/evidence/gradle_license_inventory.json` | `resolved_count`/`runtime_coordinate_count` of all Gradle-runtime coordinates — 298/298, `unresolved_count` 0 | `scripts/license_catalog.GRADLE_LICENSE_CATALOG` (curated, hand-reviewed, dated) first, then `scripts/license_catalog_harvested.HARVESTED_POM_LICENSE_CATALOG` (mechanically harvested from POMs, committed, single-license-only) second; a live local-Gradle-cache read is defense-in-depth only and is never required — see the clean-`GRADLE_USER_HOME` tests in `scripts/tests/test_generate_legal_evidence.py::ColdGradleCacheTests`. Generation fails closed (raises, writes nothing) if any coordinate is unresolved by all three paths. |
| `docs/evidence/cargo_dependency_inventory.json` | Every package reachable in any of the 9 target-triple graphs | The package's own `license` field from `cargo metadata` (Cargo.toml, not guessed) |

A dual/OR license (e.g. `Apache-2.0 OR LGPL-2.1-or-later`) is recorded with
an explicit `election` value only when the coordinate's own POM/Cargo.toml
genuinely lists more than one license; a single-license coordinate (e.g.
`org.slf4j:slf4j-api`, MIT-only) has `election: null` and is never treated
as if an `Apache-2.0 OR X` election elsewhere covers it. This is the exact
mistake the 2026-08-24 independent review flagged.

### 5a. Complete Cargo election table (every target-linked non-single-license package)

`docs/evidence/cargo_dependency_inventory.json`'s `license_elections` section
is the authoritative, generated source (27 mandatory rows as of 2026-08-24,
one per target-linked package whose Cargo.toml `license` is not a single
unambiguous SPDX license); `scripts/cargo_election_catalog.py` is the
hand-reviewed catalog backing it, and
`scripts/check_release_evidence.py --mode release` fails while any mandatory
row's `status` is not exactly `"ACCEPTED"` (with a non-empty `reviewer` and
an ISO-8601 `review_date`) — **all 27 are `status: "OPEN"` today; none has
been accepted.** A prior version of this table hand-picked 3 dual-license
crates plus 2 compound-expression crates and a since-corrected, non-existent
`r-efi` entry (that package is not actually present in this crate's
Cargo.lock or dependency graph for any of the 9 targets — removed here); this
undercounted the real 27 by omitting crates such as `bitflags`, `hashbrown`,
`indexmap`, `serde`, `serde_json`, `tempfile`, `thiserror`, and others with
the identical `MIT OR Apache-2.0` (or legacy `/`-separated) expression.

| Coordinate | Expression | Proposed election | AND-required (always mandatory) | Status |
|---|---|---|---|---|
| `anyhow` 1.0.103 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `bitflags` 2.13.0 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `camino` 1.2.4 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `cargo-platform` 0.1.9 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `cfg-if` 1.0.4 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `cryptoxide` 0.5.3 (transitive) | `MIT/Apache-2.0` (legacy slash syntax) | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `ed25519-bip32` 0.4.2 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `equivalent` 1.0.2 | `Apache-2.0 OR MIT` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `errno` 0.3.14 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `fastrand` 2.4.1 | `Apache-2.0 OR MIT` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `getrandom` 0.4.3 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `hashbrown` 0.17.1 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `heck` 0.5.0 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `indexmap` 2.14.0 | `Apache-2.0 OR MIT` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `itoa` 1.0.18 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `libc` 0.2.186 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `linux-raw-sys` 0.12.1 | `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT` | Apache-2.0 (plain, no exception) | — | OPEN — pending per-election reviewer acceptance |
| `memchr` 2.8.3 | `Unlicense OR MIT` | **none proposed** | — | OPEN — pending per-election reviewer acceptance |
| `once_cell` 1.21.4 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `rustix` 1.1.4 | `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT` | Apache-2.0 (plain, no exception) | — | OPEN — pending per-election reviewer acceptance |
| `semver` 1.0.28 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `serde` 1.0.228 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `serde_core` 1.0.228 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `serde_json` 1.0.150 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `static_assertions` 1.1.0 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `tempfile` 3.27.0 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |
| `thiserror` 2.0.18 | `MIT OR Apache-2.0` | Apache-2.0 | — | OPEN — pending per-election reviewer acceptance |

`memchr` is a deliberate exception to the "propose Apache-2.0" pattern: no
election is proposed between `Unlicense` and `MIT`, and `LICENSES/Unlicense.txt`
is committed and cited in NOTICE precisely because that election has not been
made — see `scripts/cargo_election_catalog.py`'s module docstring.

Non-target-linked packages with the same kind of non-single expression
(`autocfg`, `fs-err`, `proc-macro2`, `quote`, `serde_derive`, `siphasher`,
`syn`, `thiserror-impl`, `toml`, `unicode-ident`) are not shipped in any of
the 9 committed native artifacts, so no election row is mandatory for them;
they still appear in `license_elections.rows` with `status: "NOT_APPLICABLE"`
for completeness. `unicode-ident`'s compound expression
(`(MIT OR Apache-2.0) AND Unicode-3.0`) is the one case with a real
AND-required component: even though it is not target-linked here, the
Unicode-3.0 text is still committed (`LICENSES/Unicode-3.0.txt`) and cited in
NOTICE, since Unicode-3.0 is never satisfied merely by electing a side of the
`OR` — that is true regardless of linkage.

No election is recorded for `org.slf4j:slf4j-api`, `com.goterl:resource-loader`,
`bytes`, `cargo_metadata`, or `zmij` (all single-license MIT, no `OR` clause
in their own metadata) — they need only `LICENSES/MIT.txt` (§4), not an
election. `net.java.dev.jna:jna:5.19.1` (Gradle side, Apache-2.0 OR
LGPL-2.1-or-later) keeps its existing OPEN election row in
`docs/evidence/gradle_license_inventory.json`.

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
`docs/evidence/maven_native_carriers_inventory.json`). A separate
JVM-classified artifact of the same upstream project,
`org.hyperledger.identus:bip32-ed25519-jvm` 1.8.8 (found by this generator's
dynamic native-carrier discovery, 2026-08-24 — see §8), bundles its own
compiled natives (macOS/Linux `.dylib`/`.so`/`.a`, no Windows build at all)
under the identical `libuniffi_ed25519_bip32_wrapper` name and raises the
exact same question below. This repository has **not** obtained either
native library's own source or build-time dependency graph, and does **not**
claim an exact source-to-binary mapping for either. Given the library name
(`libuniffi_...`), both plausibly link a UniFFI runtime the same way this
repo's own `crypto-signing-backend` does — which would carry the same
MPL-2.0 file-level question as §6 — but this is stated as a plausible,
unverified structural similarity, not a fact. Whether the Apache-2.0 wrapper
license covers the whole distributed binary, and whether an embedded
MPL-2.0 (or other) component changes that, is an **OPEN counsel
determination** for both artifacts, tracked separately from — and not
resolved by — upstream `hyperledger-identus/apollo` issue #226 (which is
about the missing `win32-x86-64` build for the Android artifact, a
distribution-availability gap, not a license question; the JVM artifact has
no Windows build at all, an even narrower gap not itself tracked as #226).

| Field | Value (Android `.aar`) | Value (JVM `.jar`) |
|---|---|---|
| Wrapper POM license | Apache-2.0 | Apache-2.0 |
| Embedded native's own license/source graph | Not obtained; not reviewed | Not obtained; not reviewed |
| Structural similarity to this repo's own MPL-2.0 exposure (§6) | Plausible (same generator family), unverified | Plausible (same generator family), unverified |
| Windows build availability | Not published upstream (issue #226) — a distribution gap, not this license question | Not published upstream at all (no tracked issue) |
| Redistributed by Kardano in this release? | Yes | No — Kardano SDK does not publish Maven/JVM artifacts yet (`docs/RELEASING.md`) |
| Determination | OPEN — pending owner/counsel review | OPEN — pending owner/counsel review |

## 7. Bouncy Castle — transcription vs. source-HTML hash

`LICENSES/BouncyCastle.txt` is a **manual transcription** of the license
paragraphs rendered at `https://www.bouncycastle.org/licence.html`, typed on
2026-08-24 — it is **not** the fetched HTML bytes, and its SHA-256 cannot be
reproduced by re-fetching that URL the way the other six `LICENSES/*.txt`
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
detail — every carrier's own `artifact_sha256`, and every embedded member's
path/size/SHA-256/platform/arch (not just path/size) — is in
`docs/evidence/maven_native_carriers_inventory.json` (point-in-time
inspection, 2026-08-24, via Python `zipfile` per-member extraction and
hashing — see §13 for why this is not re-derived live on every run).

`distribution_status` is one of `resolved_runtime_dependency`,
`transitively_available`, `redistributed_by_kardano`, or
`not_in_first_release_scope` (`scripts/generate_legal_evidence.py`'s
`VALID_CARRIER_DISTRIBUTION_STATUSES`); Skiko is deliberately
`not_in_first_release_scope`, not `redistributed_by_kardano`, because no
Desktop installer is built or distributed in this release (§1a) even though
the coordinate is genuinely resolved in `desktopApp/gradle.lockfile`.

| Coordinate | Carrier kind | Embedded natives | `distribution_status` | Windows build upstream? |
|---|---|---|---|---|
| `net.java.dev.jna:jna:5.19.1` | JVM `.jar` **and** a separate Android `.aar` Gradle Module Metadata variant of the same coordinate | 34 total: 27 platform-specific `libjnidispatch` binaries in the `.jar` (only one loads per host — a prior version of this evidence said 25, missing the two AIX variants; corrected by a full zip-member enumeration) **plus** 7 more (`jni/<abi>/libjnidispatch.so`) in the separate `.aar`, found by this generator's dynamic local-cache cross-check (2026-08-24) | `redistributed_by_kardano` | Yes (`win32-x86-64`, `win32-aarch64`) |
| `org.hyperledger.identus:bip32-ed25519-android:1.8.8` | Android `.aar` | 4 (`libuniffi_ed25519_bip32_wrapper.so` per ABI) | `redistributed_by_kardano` | No (issue #226; see §6b) |
| `org.hyperledger.identus:bip32-ed25519-jvm:1.8.8` | JVM `.jar` (separate artifact of the same upstream project, found by this generator's dynamic local-cache cross-check, 2026-08-24) | 8 (`libuniffi_ed25519_bip32_wrapper` `.dylib`/`.so` + `.a` for macOS arm64/x86-64 and Linux aarch64/x86-64) | `transitively_available` (Kardano SDK does not publish Maven/JVM artifacts yet; see `docs/RELEASING.md`) | No (no Windows build published for this JVM artifact at all — narrower than issue #226) |
| `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings-jvm:0.9.5` | JVM `.jar` | 4 (libsodium per OS/arch, including a Windows `.dll`) | `redistributed_by_kardano` | Yes |
| `com.goterl:lazysodium-android:5.2.0` | Android `.aar` | 4 (`libsodium.so` per ABI) | `redistributed_by_kardano` | No (Android-only carrier) |
| `androidx.graphics:graphics-path:1.0.1` | Android `.aar` (found by this generator's dynamic local-cache cross-check, 2026-08-24) | 4 (`libandroidx.graphics.path.so` per ABI) | `redistributed_by_kardano` | No (Android-only carrier) |
| `org.jetbrains.skiko:skiko-awt-runtime-macos-arm64:0.144.6` | JVM `.jar` (desktopApp sample only) | 2 (macOS Skia `.dylib`, arm64 + x64) | `not_in_first_release_scope` | No (only macOS-arm64 variant resolved in this repo's lockfiles) |

Do not classify JNA as source-only (§5's election table is about the
*source* license; this table is about the *separate* fact that the same jar
also carries compiled binaries). The `org.hyperledger.identus:bip32-ed25519-jvm`
and `androidx.graphics:graphics-path` rows above were found only after this
2026-08-24 independent review added `generate_legal_evidence.py`'s dynamic
Maven native-carrier discovery (a live cross-check against the actual
resolved `.jar`/`.aar` bytes in a warm local Gradle module cache, which fails
generation closed on any undeclared native-carrying coordinate) — neither
had been reviewed by hand before, illustrating why this table is generated
and cross-checked rather than curated purely by manual inspection.

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
| Windows x86-64 JVM signing-backend candidate DLL | Not distributed | Independent PE technical review is complete (`c65a20a`; see §14); withheld solely because of the remaining named gate in §14 (upstream issue #226), plus any separate manual/release decision — completion of the PE technical review does not promote this candidate or imply any DLL is distributed |
| Identus `apollo` Android derivation-backend native library, Windows build | Not distributed by Kardano SDK | Upstream (`hyperledger-identus/apollo`) has not published a `win32-x86-64` build; Kardano SDK cannot distribute what upstream has not built — tracked as upstream issue #226 |
| `org.hyperledger.identus:bip32-ed25519-jvm:1.8.8` (JVM artifact, all platforms) | Not distributed by Kardano SDK | Kardano SDK does not publish Maven/JVM artifacts through any channel yet (`docs/RELEASING.md`); resolved/reachable for JVM tests only — see §6b/§8 |

## 12. Scope binding: two-commit seal (evidence-content commit + seal commit)

A `scope_binding.json` written in the SAME commit as the evidence it
describes cannot prove anything on its own: regenerating it always
trivially "passes" by rewriting the binding to whatever `HEAD` happens to
be at check time, so a later commit could silently edit an
already-generated evidence file and no fresh regeneration would ever
notice. A 2026-08-24 independent review named this self-reference gap
explicitly; this section replaces the earlier single-commit design.

The packet now uses two separate commits, never amended once made:

1. **Evidence-content commit** (`evidence_commit`). Produced by
   `python3 scripts/generate_legal_evidence.py` (no flag), which writes
   every `docs/evidence/*.json` file except `scope_binding.json` — plus
   `LEGAL_EVIDENCE_DIGEST.txt` over exactly those files — against whatever
   is currently `HEAD`. That `HEAD`, `evidence_commit`'s own immediate
   parent, is the immutable **subject-source commit** (`subject_commit`):
   the actual `crypto-signing-backend/Cargo.lock`, every
   `*/gradle.lockfile`, `CHECKSUMS.sha256`, `NOTICE`, and `LICENSES/*.txt`
   state that was inventoried.
2. **Seal commit** (built on top of `evidence_commit`, with a clean
   worktree). Produced by
   `python3 scripts/generate_legal_evidence.py --seal`, which reads back
   `evidence_commit`'s own hash (`git rev-parse HEAD`) and its immediate
   parent (`subject_commit`), records a SHA-256 of every evidence-content
   file's bytes (`sealed_evidence_digests`), writes `scope_binding.json`,
   and rewrites `LEGAL_EVIDENCE_DIGEST.txt` to add a
   `scope_binding.json_sha256=` line — the manifest now covers the seal
   file's own bytes without needing to hash itself.

`scripts/check_release_evidence.py`'s `check_scope_binding_seal()` verifies
this independently of regeneration — it never rewrites `scope_binding.json`
to a fresh `HEAD`. It confirms, purely from git history plus current
worktree bytes:

- `evidence_commit`/`subject_commit` exist as real commit objects, and
  `evidence_tree`/`subject_tree` are exactly those commits' own trees.
- `subject_commit` is EXACTLY `evidence_commit`'s immediate parent (not
  merely some ancestor).
- `evidence_commit` is an ancestor of (or equal to) current `HEAD`.
- Every sealed evidence file's CURRENT bytes match both the recorded digest
  in `scope_binding.json` AND the actual bytes committed at
  `evidence_commit`'s tree (`git show <evidence_commit>:<path>`) — so a
  later commit that edits an already-sealed evidence file without a
  re-seal is caught, even though the freshness check elsewhere only ever
  compares against the current tracked tree.

To manually verify a specific sealed `scope_binding.json`:

```bash
cat docs/evidence/scope_binding.json                 # read evidence_commit/subject_commit
git rev-parse <evidence_commit>^                     # must equal subject_commit exactly
git show <evidence_commit>:docs/evidence/cargo_dependency_inventory.json | sha256sum
# must equal sealed_evidence_digests["cargo_dependency_inventory.json"] (repeat per file)
```

If new evidence content is generated later (a new evidence-content commit),
`scope_binding.json` must be re-sealed against that new commit — an old
seal bound to a superseded `evidence_commit` will fail the "current bytes
match sealed digest" check the moment the evidence files move on without a
matching new seal.

## 13. Network and cache dependency (determinism)

**Gradle license resolution no longer depends on any local cache.**
`scripts/license_catalog.py` (hand-curated) plus the mechanically harvested
`scripts/license_catalog_harvested.py` (`scripts/harvest_gradle_pom_licenses.py`)
together cover all 298 currently locked Gradle-runtime coordinates with zero
unresolved; `gradle_license_inventory()` raises (fails generation, writes
nothing) if any coordinate is still unresolved after checking both catalogs
and, as a last-resort defense-in-depth, the local Gradle module cache. This
is proved by `ColdGradleCacheTests` (`scripts/tests/test_generate_legal_evidence.py`),
which point `GRADLE_USER_HOME` at a brand-new empty temp directory and
require byte-identical resolution, and by `verify.yml`'s
"Regenerate from a clean temporary GRADLE_USER_HOME" step, which does the
same in CI.

`maven_native_carriers_inventory()` remains a **static, dated table**
(2026-08-24 point-in-time inspection of specific resolved artifact bytes),
not a live re-derivation, precisely so that this generator never needs
network access to reproduce it. Re-verify by re-running the
`unzip -l`/hash commands against a freshly resolved copy of the same
coordinate+version before relying on this table for a release decision.

**`java_class_version_evidence.json` is the one deliberate exception --
live-verified every run, network access included by design.** A
2026-08-25 independent review found the opposite tradeoff (the same
"local-cache cross-check, cold cache is a safe no-op" pattern
`maven_native_carriers_inventory()` uses above) meant this evidence's own
live check silently returned success with nothing actually checked on this
repo's own legal-evidence-scan CI job, which never populates a Gradle
cache at all -- exactly the environment it needed to be authoritative in.
The fix: `live_verify_java_class_version_evidence()` always resolves an
ACTUAL `org.bouncycastle:bcprov-jdk18on:1.85.2` `.jar` to scan --
`--bcprov-jar PATH`, the `KARDANO_LEGAL_EVIDENCE_BCPROV_JAR` environment
variable, or (the default) `fetch_and_verify_bcprov_jar()`'s pinned-host
(`repo1.maven.org`, no redirect elsewhere), SHA-256-and-size-verified
download from Maven Central. There is no skip branch: a missing or
unreachable jar is a hard failure of generation/checking, never a silent
pass. `.github/workflows/verify.yml`'s `legal-evidence-scan` job bootstraps
this once via a dedicated step (immediately after the Cargo bootstrap
step) and every later step in that job reuses the SAME already-verified
local copy via the environment variable instead of re-fetching.

**Cargo network access is explicit, bounded to one bootstrap step, and
never implicit inside generation.** The only Cargo command in this
packet's workflow allowed to touch the network is
`cargo fetch --locked --manifest-path crypto-signing-backend/Cargo.toml`,
run once before generation (`.github/workflows/verify.yml`'s
"Bootstrap Cargo registry over the network" step; `--locked` means it
populates the local registry cache with exactly what `Cargo.lock` already
pins and refuses to re-resolve). Every Cargo invocation inside
`scripts/generate_legal_evidence.py` itself
(`cargo metadata --locked --offline --filter-platform <triple>` and
`cargo tree --locked --offline --target <triple> -e <edges>`) additionally
passes `--offline`, so generation can only ever read the registry cache
that bootstrap step already populated — a generation run that unexpectedly
needed network access fails loudly (a real `cargo` error) instead of
silently re-fetching mid-run. Every such invocation also hashes
`crypto-signing-backend/Cargo.lock` immediately before and immediately
after the call and raises a fail-closed `EvidenceError` if the hash
changed, independently verifying `--locked`'s refusal instead of trusting
the flag alone. `verify.yml` additionally sets `CARGO_NET_OFFLINE=true` for
every step that runs the generator or its tests, so even a code path that
forgot the `--offline` flag would still fail rather than silently reaching
the network.

**Full-worktree mutation is checked, not just `docs/evidence/`.**
`verify.yml`'s `legal-evidence-scan` job captures the entire tracked
worktree's status (`git status --porcelain=v1`) and
`crypto-signing-backend/Cargo.lock`'s SHA-256 before the Cargo bootstrap
step, then — after the cold-cache run, the double-regeneration-diff run,
and the release-evidence checker have all executed — re-diffs the ENTIRE
tracked worktree (not merely `docs/evidence/`) against that snapshot and
fails if any tracked file outside `docs/evidence/` changed, with a second,
independent re-hash of `Cargo.lock` as an explicit belt-and-suspenders
check on top of the per-Cargo-invocation guard above. This catches a
generator bug that rewrote a lockfile, a gradle lockfile, or any other
tracked source file even if every narrower check happened to miss it — not
just evidence drift, but ANY unexpected worktree mutation during the whole
legal-evidence job.

## 14. Unresolved / decision fields

| Field | Status | Detail |
|---|---|---|
| Counsel review | OPEN — pending owner/counsel review | Every §2/§5a/§6/§6b/§7 field naming this marker |
| Upstream Identus win32-x86-64 build | OPEN — pending upstream hyperledger-identus/apollo issue #226 | §6b, §11 |
| Windows signing-backend independent PE technical review | COMPLETE at `c65a20a` (this is a technical structural review, not a legal or counsel determination) | §11 |
| Per-election reviewer acceptance | OPEN — pending per-election reviewer acceptance | §5a/§5b (mandatory target-linked Cargo election rows plus mandatory Gradle election rows, one per non-single-license coordinate) |
| Release / tag decision | Not made in this packet | This packet prepares evidence only; it does not recommend, schedule, or make a release decision |

## 15. Gate cross-references

- Independent PE technical review: COMPLETE at `c65a20a` (native-artifact
  PE-structure evidence only — see `docs/HANDOFF.md` Branch-Stack Status
  (Prompt 7) and `crypto-signing-backend/README.md` "Windows x86-64 —
  candidate-only"). This closes ONLY the technical-review gate; it is not a
  legal approval and does not promote the Windows candidate or imply a DLL
  is distributed. The Windows candidate remains unpromoted/not-distributed
  because the upstream Identus issue #226 gate below (and any separate
  manual/release decision) is still open.
- Upstream Identus issue #226: still OPEN; see `docs/HANDOFF.md` "Next
  Recommended Task" and `docs/DEPENDENCY_PROVENANCE.md`.
- MPL-2.0/Identus-embedded-native counsel determinations: §6/§6b above; not
  restated with different wording anywhere else.
- This packet closes only the PE technical-review gate above; every other
  gate's status is unchanged by this change.

## Regeneration and verification

```bash
# Network bootstrap (the two steps allowed to touch the network -- see §13):
cargo fetch --locked --manifest-path crypto-signing-backend/Cargo.toml
# java_class_version_evidence.json's own live verification fetches its
# pinned bcprov-jdk18on jar itself if neither --bcprov-jar nor
# KARDANO_LEGAL_EVIDENCE_BCPROV_JAR is already set -- no separate manual
# bootstrap command is required here, unlike the Cargo step above.

# Evidence-content commit (everything except scope_binding.json):
CARGO_NET_OFFLINE=true python3 scripts/generate_legal_evidence.py
CARGO_NET_OFFLINE=true python3 scripts/generate_legal_evidence.py   # run again -- must be byte-identical
git diff --quiet docs/evidence                # expect no diff after two runs
git add -A && git commit -m "evidence-content commit"

# Seal commit (run only against the clean commit made above -- see §12):
python3 scripts/generate_legal_evidence.py --seal
git add -A && git commit -m "seal commit"

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
