# Dependency Review — CI Actions And Build Pins

Dated inventory of first-party GitHub Action pins and the composite
Action metadata those pins pull in. Resolved live on **2026-08-23** from
the GitHub Releases API and peeled Git tag objects. Do not reuse SHAs
from older audit notes.

This page is the human-readable twin of `scripts/action_pin_inventory.py`.
`scripts/check_action_pins.py` requires every external workflow `uses:`
to match a recorded 40-character lowercase SHA, and requires every SHA
below to remain in this file.

Gradle library versions, lockfiles, and native-backend acceptance are
reviewed in later commits on this branch and appended here.

## How pins were resolved

For each Action:

1. `GET https://api.github.com/repos/{owner}/{repo}/releases?per_page=8`
   and `.../releases/latest` (User-Agent `kardano-pin-resolver`, 2026-08-23).
2. Peel `GET .../git/refs/tags/{tag}` to the commit object (annotated tags
   followed to the commit SHA).
3. Fetch `action.yml` (or `setup-gradle/action.yml`) from
   `raw.githubusercontent.com` at that tag and inspect `runs.using` plus
   every nested `uses:`.

No Action SHA in this table was copied from `docs/AUDIT/` or from the
previous `v4.3.1` / `v4.9.1` / `v4.4.3` comments.

## v4 versus v4.3.1

The 2026-08-22 audit (W9-2) listed floating major-version tags:
`actions/checkout@v4`, `actions/setup-java@v4`,
`gradle/actions/setup-gradle@v4`. The later SHA-pin commit did **not**
pin those moving `v4` tags. It pinned exact patch releases:

| Action | Comment people may have read as "v4" | Actual previous pin |
|---|---|---|
| `actions/checkout` | `@v4` (moving major tag) | `v4.3.1` `34e114876b0b11c390a56381ad16ebd13914f8d5` |
| `actions/setup-java` | `@v4` | `v4.9.1` `cf277c60eb25467037889841efdb72551f06f6c3` |
| `gradle/actions/setup-gradle` | `@v4` | `v4.4.3` `ed408507eac070d1f99cc633dbcf757c94c7933a` |

On 2026-08-23, `actions/checkout`'s `v4` tag is **v4.4.0** (published
2026-07-20), which is not `34e114876b0b11c390a56381ad16ebd13914f8d5`.
This batch upgrades from the exact patch pins above, not from a moving
`v4` tag.

## First-party workflow pins

| Workflow `uses:` | Release | Commit SHA | Runtime | Kind |
|---|---|---|---|---|
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` | node24 | javascript |
| `actions/setup-java` | v5.7.0 | `b6effb05e454b25005698d916606bdc6ffcbf961` | node24 | javascript |
| `gradle/actions/setup-gradle` | v5.0.2 | `0723195856401067f7a2779048b490ace7a47d7c` | node24 | javascript |
| `actions/configure-pages` | v6.0.0 | `45bfe0192ca1faeb007ade9deae92b16b8254a0d` | node24 | javascript |
| `actions/upload-pages-artifact` | v5.0.0 | `fc324d3547104276b827a68afc52ff2a11cc49c9` | composite | composite |
| `actions/deploy-pages` | v5.0.0 | `cd2ce8fcbc39b97be8ca5fce6e763baed58fa128` | node24 | javascript |
| `actions/upload-artifact` | v7.0.1 | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` | node24 | javascript |
| `actions/download-artifact` | v8.0.1 | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` | node24 | javascript |

Release pages:

- https://github.com/actions/checkout/releases/tag/v7.0.1
- https://github.com/actions/setup-java/releases/tag/v5.7.0
- https://github.com/gradle/actions/releases/tag/v5.0.2
- https://github.com/actions/configure-pages/releases/tag/v6.0.0
- https://github.com/actions/upload-pages-artifact/releases/tag/v5.0.0
- https://github.com/actions/deploy-pages/releases/tag/v5.0.0
- https://github.com/actions/upload-artifact/releases/tag/v7.0.1
- https://github.com/actions/download-artifact/releases/tag/v8.0.1

`checkout` v7.0.1, `setup-java` v5.7.0, `configure-pages` v6.0.0, and
`deploy-pages` v5.0.0 are javascript Actions (`runs.using: node24`).
Their `action.yml` files contain no nested `uses:`.

`checkout` v7 blocks fork checkouts on `pull_request_target` /
`workflow_run` unless `allow-unsafe-pr-checkout` is set. This repository
does not use those events. Runner requirement for the Node 24 Actions is
`>= 2.327.1`; GitHub-hosted `ubuntu-latest` and `macos-latest` meet that.

`windows-jvm-rebuild-evidence.yml` reuses the same `checkout`,
`setup-java`, `setup-gradle`, `upload-artifact`, and `download-artifact`
pins. No new Action SHA was added.

`setup-java` v5.7.0 was `releases/latest` on 2026-08-23. A `v4.9.1`
backport was published on 2026-08-04 and is not this pin. The workflows
keep `distribution: temurin` and `java-version: "17"`. Adopt aliases are
deprecated in v5; this repo does not use them.

## setup-gradle: v5 adopted, v6 not adopted

`gradle/actions` `releases/latest` on 2026-08-23 is **v6.3.0**. That
major version is **not** used here.

v6 extracts caching into `gradle-actions-caching`, a separate commercial
component. The v6 `setup-gradle/action.yml` default is
`cache-provider: enhanced`. Using that default accepts a separate Terms
of Use. That is an unproven license/compatibility gate, so this commit
stops at **v5.0.2** (last v5, Node 24, published 2026-02-23).

v4.4.3 and v5.0.2 share these cache defaults:

- `cache-disabled`: `false`
- `cache-read-only`: true when the ref is not the repository default branch
- `cache-write-only`: `false`
- `cache-cleanup`: `on-success`

`verify.yml` sets those four inputs explicitly so a later major-version
default change cannot silently change cache behavior.

## Composite inspection — Pages upload

`actions/upload-pages-artifact@v3.0.1` (the previous pin) is a composite
Action whose `action.yml` contained:

```text
uses: actions/upload-artifact@v4
```

That is a floating major tag (NF-4). v5.0.0 replaces it with:

```text
uses: actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f # v7.0.0
```

Source:
https://raw.githubusercontent.com/actions/upload-pages-artifact/v5.0.0/action.yml

The other composite steps are inline `run:` archive commands (no further
`uses:`). `actions/upload-artifact` v7.0.1
(`043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`, published 2026-04-10) exists
and is newer than the composite's v7.0.0 pin. This repo does not rewrite
the official Pages packaging steps; it records that transitive SHA and
requires it to stay pinned.

`native-rebuild-evidence.yml` uses `actions/upload-artifact` as a
first-party workflow pin at v7.0.1 (same SHA as above). That Action's
`action.yml` is javascript (`runs.using: node24`) with no nested `uses:`.
The job uploads staging reports and rebuilt copies only; it never writes
those files back over the committed natives.

`linux-jvm-rebuild-evidence.yml` adds `actions/download-artifact` v8.0.1
(`3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`, `releases/latest` on
2026-08-23). That Action is javascript (`runs.using: node24`) with no
nested `uses:`. The compare job downloads same-run candidate A/B
uploads only; permissions stay `contents: read`.

`configure-pages` and `deploy-pages` are javascript Actions and have no
nested `uses:`.

## Checker

```bash
python3 -m unittest scripts.tests.test_check_action_pins
python3 scripts/check_action_pins.py
```

`scripts/yaml_uses_extract.rb` walks each document with Ruby stdlib
Psych (no gems) and emits JSON. The Python checker does not discover
`uses` with a line regex. It recursively inspects every mapping/list
`uses` value, including flow mappings and `uses :` whitespace.

External actions and reusable workflows must be
`owner/repo@<40-char lowercase SHA>` and match the inventory owner/repo
and SHA. Local `./path` values are resolved from the repository root
against `action.yml` and `action.yaml`; missing metadata, `..` escape,
cycles, and unreviewed nested external uses are findings. The walker
also inspects every `action.yml` / `action.yaml` in the tree, including
top-level `runs.using` and `runs.image`. YAML aliases and anchors are
rejected in every scanned workflow and action metadata file; non-string
or empty `uses`, `runs`, `runs.using`, and `runs.image` values are
extractor errors (never treated as absent). This repository has no
approved Docker actions: `runs.using: docker` is a finding that names
the metadata path and image (floating tag, digest, or Dockerfile).
Direct workflow `uses: docker://...` is rejected the same way until a
digest/inventory policy exists.

## Build platform and UI/network pins (2026-08-23)

Historical Prompt 6 commit 2 used Gradle 9.7.1 / AGP 9.3.1 / API 37
because those versions existed on Maven and local builds passed.
The official Kotlin 2.4.10 table (fetched 2026-08-23 from
https://kotlinlang.org/docs/gradle-configure-project.html) covers
Gradle **7.6.3–9.5.0** and AGP **8.5.2–9.1.0** only. The review-fix
moves to that envelope. See ADR-0021.

Resolved live from `https://services.gradle.org/distributions/gradle-9.5.0-bin.zip.sha256`,
Google Maven `maven-metadata.xml`, Maven Central `maven-metadata.xml`,
and the Kotlin compatibility table.

| Coordinate | Prompt 6 commit 2 | Review-fix pin | Source |
|---|---|---|---|
| Gradle wrapper | 9.7.1 (`acd53f1e…d20a`) | **9.5.0** (`553c78f5…b746`) | Kotlin 2.4.10 max + services.gradle.org `.sha256` |
| AGP | 9.3.1 | **9.1.0** | Kotlin 2.4.10 max (Google also publishes 9.1.1; not used) |
| Kotlin | 2.4.10 | **2.4.10** | Maven Central last stable (2.4.20 is RC) |
| Android compile/target SDK | 37 (minor 0) | **36** | AGP 9.1.0 published max; API 37 deferred (ADR-0021) |
| JetBrains lifecycle Compose | 2.11.0 | **2.10.0** | AndroidX 2.11.0 requires compile SDK 37 and AGP >= 9.2.0 |
| Ktor | 3.5.2 | **3.5.2** | Maven Central; unchanged |
| Compose Multiplatform | 1.11.1 | 1.11.1 | Latest 1.11 stable; 1.12.0-rc01 left out of this group |
| Compose Material3 | 1.11.0-alpha07 | 1.11.0-alpha07 | Latest 1.11-line artifact; 1.12.0-alpha03 tracks Compose 1.12 |
| androidx.activity:activity-compose | 1.13.0 | 1.13.0 | Google Maven latest stable |
| kotlinx-coroutines / serialization | 1.11.0 | 1.11.0 | Maven Central latest stable |
| foojay-resolver-convention | 1.0.0 | 1.0.0 | Gradle Plugin Portal latest |

Removed unused catalog entries rather than upgrading them:
`androidx-appcompat`, `androidx-core` / `androidx-core-ktx`,
`androidx-espresso` / `androidx-espresso-core`, `junit`,
`kotlin-testJunit`. No call site referenced them.

Crypto / native-support pins as of commit 3: see ADR-0020. Bouncy Castle
1.85.2 and JNA 5.19.1 were upgraded; the 0.x pins were retained with
dated acceptance.

Modules set integer `compileSdk` / `targetSdk` **36**. API 37 remains
installed on this host (`platforms/android-37.0`) but is not targeted
(ADR-0021). `OldTargetApi` is disabled for that dated deferral only.

Residual toolchain notes (not blockers): Kotlin/AGP still warn that
`androidLibrary {}` is deprecated in favor of `android {}`; cinterop
commonization remains off. Those are not migrated here. The
`gradlew wrapper` task rewrote `gradlew` / `gradlew.bat` / the wrapper
jar; `gradlew.bat` keeps upstream trailing spaces on several `@rem`
lines, scoped in `.gitattributes` so `git diff --check` stays clean
without editing the generated script.

Independent publisher checksum comparison is in
[DEPENDENCY_PROVENANCE.md](DEPENDENCY_PROVENANCE.md).

## Android 17 target notes (no device run)

Source: https://developer.android.com/about/versions/17/behavior-changes-17
and https://developer.android.com/about/versions/17/behavior-changes-all
fetched 2026-08-23. This is a documentation review of the published
notes, not a runtime pass.

## Gradle dependency locking (2026-08-23 review-fix)

| Item | Value |
|---|---|
| Mode | `LockMode.STRICT` in the root `build.gradle.kts` `allprojects` block |
| Activated configurations | `lockAllConfigurations()` — no suffix filter |
| Exclusions | none. `Configuration.resolve()` is **not** used; AGP/KMP variant
  attributes come from the real task graph (`resolveAndLockAll`) |
| Generation | `./gradlew --no-daemon --no-configuration-cache resolveAndLockAll --write-locks` |
| Per-project state | `<project>/gradle.lockfile` for all ten included projects |
| Settings catalog | `settings-gradle.lockfile` |

`lockAllConfigurations()` plus a blind `Configuration.resolve()` still
fails on AGP variant ambiguity (`debugAndroidTestCompileClasspath`,
some `:shared` variants) **outside** the task graph. That is a Gradle
limitation, not an exclusion list. Generation depends on compile, test,
assemble, and lint tasks so those configurations resolve with attributes.

Confirmed on this macOS arm64 host after generation: lockfiles include
Kotlin/Native `*CompileKlibraries` (for example
`iosArm64CompileKlibraries` in `:core` / `:provider-blockfrost`), lint
classpaths, and plugin/compiler classpaths that Gradle can lock.
Buildscript / "unknown" persist lines still appear; they did not write
extra lockfiles. Plugin and buildscript artifacts are checked through
`gradle/verification-metadata.xml` (see provenance).

Host-specific rows that are real variant selection, not accidents:

- `:desktopApp` / `:shared` Compose `desktop-jvm-macos-arm64` and
  `skiko-awt-runtime-macos-arm64` — generated on this runner. Ubuntu
  Verify does not compile `:desktopApp`. Windows variants are omitted
  until Prompt 7.
- `kotlin-native-prebuilt` macos-aarch64 appears in verification
  metadata because iOS compile ran here. Ubuntu JVM/lint jobs do not
  download that tarball.

Re-running `resolveAndLockAll --write-locks` twice on this host after
the review-fix moves produced no lockfile diff.

## Android lint gate (2026-08-23)

`androidApp` lint uses `abortOnError`, `warningsAsErrors`, and
`checkReleaseBuilds`. Disabled checks are the online freshness
detectors — `GradleDependency`, `NewerVersionAvailable`,
`AndroidGradlePluginVersion` — plus `OldTargetApi` (ADR-0021: API 37
is deferred). Catalog pins, lockfiles, and
`gradle/verification-metadata.xml` already record reviewed versions.
No lint baseline is committed.

Asset disposition after Debug+Release lint (`No issues found.`):

| Finding | Disposition |
|---|---|
| Freshness / OldTargetApi / AGP / Kotlin | Resolved by commits 2–4 or disabled as online freshness |
| `MonochromeLauncherIcon` | Added `drawable-nodpi/ic_launcher_monochrome.png` (white silhouette from `drawable-xxxhdpi/ic_launcher_foreground.png` alpha) to both adaptive XMLs |
| `IconLocation` | Moved splash PNGs to `drawable-nodpi/` and `drawable-night-nodpi/` |
| `IconLauncherShape` on 10 legacy `ic_launcher.png` squares | Regenerated from `kardano_mark_{light,dark}.png` via `scripts/generate_legacy_launcher_icons.py`: 12.5% transparent margin and a rounded-rect brand-fill silhouette. Adaptive XML, monochrome, splash, and round mipmaps were not changed. Owner visual check remains for pre-API-26 tiles. |

`verify.yml` job `android-lint` runs lint Debug/Release, then
assemble Debug/Release. Existing claim / archive / Gitleaks /
action-pin jobs are unchanged.

Re-running `resolveAndLockAll --write-locks` on 2026-08-23 produced
byte-identical SHA-256 hashes for every lockfile. Do not hand-edit
generated lock lines.

## Gradle dependency verification (2026-08-23)

| Item | Value |
|---|---|
| File | `gradle/verification-metadata.xml` |
| Algorithms | SHA-256 only (`verify-signatures` is `false`) |
| Generation | `./gradlew --no-daemon --no-configuration-cache --write-verification-metadata sha256` plus the same compile/test/assemble graph as lock generation |
| Host | macOS arm64, Gradle 9.5.0 (review-fix) |
| Bootstrap | Gradle writes `origin="Generated by Gradle"` on resolved checksums |

Linux AAPT2 `aapt2-9.1.0-14792394-linux.jar` was **not** invented and
was **not** produced by the macOS Gradle run. It was downloaded from
Google Maven and recorded only after the publisher `.sha256` sidecar
matched. See [DEPENDENCY_PROVENANCE.md](DEPENDENCY_PROVENANCE.md).

Review of the generated file:

- No `sha1`, `md5`, or `pgp` entries (except the independent JNA
  SHA-1 sidecar comparison in the provenance page).
- No `trusted-artifacts` exceptions.

Tamper proof (not committed): flipping the first nibble of the
`junit-4.13.2.jar` SHA-256 makes `:core:compileTestKotlinJvm` fail
with `Dependency verification failed`. That is enforcement evidence
only. Publisher comparison is the provenance page.

Docker was not available on the generation host. Ubuntu Verify
(`push` to `main` and `fix/**`, plus `pull_request`) is the remaining
Linux-resolved evidence for any artifact this record still misses.
Do not invent checksums to hide a miss. No Windows classifiers until
Prompt 7.

Verify run `32654915900` (head `0786237`) failed on Ubuntu and
macOS-arm64 at root `classpath` verification for four Maven Central
metadata files that the cold CI cache requested and the local
generation did not hash: `guava-parent-33.3.1-jre.pom`,
`junit-bom-5.10.2.module`, `junit-bom-5.11.0-M2.module`, and
`kotlinx-coroutines-bom-1.8.0.pom`. Those rows were added only after
publisher sidecar / hash-of-download comparison
([DEPENDENCY_PROVENANCE.md](DEPENDENCY_PROVENANCE.md)). They are not
copied from CI log text. Lockfiles were not rewritten for this miss.

## Cargo lock and Rust toolchain (2026-08-23)

| Item | Value |
|---|---|
| Toolchain file | `crypto-signing-backend/rust-toolchain.toml` |
| Channel | `1.97.0` (README pin; rustup resolved `1.97.0 (2d8144b78 2026-07-07)`). Hosted images may expose rustc `1.97.1` first; rebuild jobs activate the `1.97.0` toolchain `bin`. |
| Direct crates | `ed25519-bip32 = "=0.4.2"`, `uniffi = "=0.29.5"` |
| Lockfile | `crypto-signing-backend/Cargo.lock` (unchanged by the exact-pin edit) |
| Rebuild flags | every documented `cargo` / `cargo ndk` rebuild uses `--locked` |

`cargo metadata --locked` was run twice after the pin edit; `Cargo.lock`
had no diff. Natives were not rebuilt.
