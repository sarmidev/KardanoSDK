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

Release pages:

- https://github.com/actions/checkout/releases/tag/v7.0.1
- https://github.com/actions/setup-java/releases/tag/v5.7.0
- https://github.com/gradle/actions/releases/tag/v5.0.2
- https://github.com/actions/configure-pages/releases/tag/v6.0.0
- https://github.com/actions/upload-pages-artifact/releases/tag/v5.0.0
- https://github.com/actions/deploy-pages/releases/tag/v5.0.0

`checkout` v7.0.1, `setup-java` v5.7.0, `configure-pages` v6.0.0, and
`deploy-pages` v5.0.0 are javascript Actions (`runs.using: node24`).
Their `action.yml` files contain no nested `uses:`.

`checkout` v7 blocks fork checkouts on `pull_request_target` /
`workflow_run` unless `allow-unsafe-pr-checkout` is set. This repository
does not use those events. Runner requirement for the Node 24 Actions is
`>= 2.327.1`; GitHub-hosted `ubuntu-latest` and `macos-latest` meet that.

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

`configure-pages` and `deploy-pages` are javascript Actions and have no
nested `uses:`.

## Checker

```bash
python3 -m unittest scripts.tests.test_check_action_pins
python3 scripts/check_action_pins.py
```

The checker walks `.github/workflows/*.{yml,yaml}` and
`.github/actions/**/action.yml`. Local `./` composites are allowed; their
own external `uses:` still need a recorded SHA. A recorded composite
with a non-SHA transitive entry is a finding.

## Build platform and UI/network pins (2026-08-23)

Resolved live from `https://services.gradle.org/versions/current`,
`https://services.gradle.org/distributions/gradle-9.7.1-bin.zip.sha256`,
Google Maven `maven-metadata.xml`, and Maven Central `maven-metadata.xml`.
Pre-upgrade `androidApp:lintDebug` on this host reported 0 errors / 36
warnings and named several of these upgrades (Gradle 9.7.1, AGP 9.3.1,
Kotlin 2.4.10, lifecycle 2.11.0, Ktor 3.5.2, OldTargetApi 36).

| Coordinate | Before | After | Source |
|---|---|---|---|
| Gradle wrapper | 9.1.0 (`a17ddd85…c806`) | 9.7.1 (`acd53f1e…d20a`) | services.gradle.org current + `.sha256` file |
| AGP (`com.android.application` / `com.android.kotlin.multiplatform.library`) | 9.0.1 | 9.3.1 | Google Maven last stable (9.4/9.5 are alpha/rc) |
| Kotlin | 2.4.0 | 2.4.10 | Maven Central last stable (2.4.20 is RC) |
| Android compile/target SDK | 36 | 37 (compile minor 0) | Installed `platforms/android-37.0`; AGP 9.3 max API 37; min AGP for 37.0 is 9.1.1 |
| JetBrains lifecycle Compose | 2.11.0-beta01 | 2.11.0 | Maven Central `org.jetbrains.androidx.lifecycle` |
| Ktor | 3.5.1 | 3.5.2 | Maven Central; 3.5.2 changelog has no OkHttp retry-default change |
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

AGP 9.3 requires Gradle >= 9.5.0 (documented on
https://developer.android.com/build/releases/about-agp). The installed
platform directory is `android-37.0`, not `android-37`. Modules set
`compileSdk { version = release(37) { minorApiLevel = 0 } }`. Application
`targetSdk` uses `release(37)` (that DSL has no minor lambda). Configure,
`:androidApp:assembleDebug`, and `:desktopApp:compileKotlin` succeeded on
this host after the upgrade.

Android 17 (`targetSdk` 37) published target-sdk notes reviewed, not
executed on a device: lock-free `MessageQueue`; `static final` fields
cannot be changed via reflection/JNI; `ACCESS_LOCAL_NETWORK` for LAN;
large-screen orientation/aspect/resizability constraints cannot be opted
out of (`sw >= 600dp`); SMS OTP delay; BluetoothSocket `read` alignment.
This Playground uses INTERNET to Blockfrost HTTPS, does not reflect on
`MessageQueue`, and does not modify `static final` fields. No device or
emulator execution is claimed.

Residual toolchain notes (not blockers): Kotlin/AGP now warn that
`androidLibrary {}` is deprecated in favor of `android {}`; Gradle 9.6+
warns on `cinterop.creating` delegates in `:crypto`. Those are not
migrated here (broad rename / native-source-set behavior). The
`gradlew wrapper` task rewrote `gradlew` / `gradlew.bat` / the wrapper
jar; `gradlew.bat` keeps upstream trailing spaces on several `@rem`
lines, scoped in `.gitattributes` so `git diff --check` stays clean
without editing the generated script.

## Android 17 target notes (no device run)

Source: https://developer.android.com/about/versions/17/behavior-changes-17
and https://developer.android.com/about/versions/17/behavior-changes-all
fetched 2026-08-23. This is a documentation review of the published
notes, not a runtime pass.

## Gradle dependency locking (2026-08-23)

Strict locking is on for every project compile/runtime classpath that
this repository can lock without an AGP variant-selection failure.

| Item | Value |
|---|---|
| Mode | `LockMode.STRICT` in the root `build.gradle.kts` `allprojects` block |
| Activated configurations | resolvable names ending in `CompileClasspath` or `RuntimeClasspath` |
| Excluded | any name containing `AndroidTest` (instrumented-test classpaths) |
| Generation task | `./gradlew --no-daemon --no-configuration-cache resolveAndLockAll --write-locks` |
| Per-project state | `<project>/gradle.lockfile` for all ten included projects |
| Settings catalog | `settings-gradle.lockfile` (`empty=incomingCatalogForLibs0`) |

`lockAllConfigurations()` plus `Configuration.resolve()` cannot pick a
unique AGP variant for `:androidApp` instrumented-test classpaths (and
some app classpaths) **outside** the AGP task graph. Those
configurations are left unlocked rather than forcing a broken resolve.
Kotlin/Native configurations use names such as `*CompileKlibraries`,
not `*CompileClasspath`, so they are not in the lockable set; their
Maven artifacts still appear in verification metadata because iOS
compile was part of the generation graph.

Plugin versions remain catalog-pinned (`gradle/libs.versions.toml`).
`settings.gradle.kts` pins `org.gradle.toolchains.foojay-resolver-convention`
at `1.0.0`. Buildscript classpaths are not lock-activated (this repo
uses the `plugins {}` DSL). Gradle still prints persist lines for
buildscript / "unknown" during `--write-locks`; those lines did not
write extra lockfiles.

`:desktopApp` compile can be UP-TO-DATE and skip resolution, so
`resolveAndLockAll` explicitly resolves that project's lockable
classpaths in `doLast`. `:androidApp:compileDebugUnitTestKotlin` and
`:androidApp:generateReleaseLintModel` are in the lock graph so STRICT
mode has state for lint's unit-test classpaths (there is no
`compileReleaseUnitTestKotlin` task in this module).

## Android lint gate (2026-08-23)

`androidApp` lint uses `abortOnError`, `warningsAsErrors`, and
`checkReleaseBuilds`. Disabled checks are only the online freshness
detectors — `GradleDependency`, `NewerVersionAvailable`,
`AndroidGradlePluginVersion` — because catalog pins, lockfiles, and
`gradle/verification-metadata.xml` already record reviewed versions.
No lint baseline is committed.

Asset disposition after Debug+Release lint (`No issues found.`):

| Finding | Disposition |
|---|---|
| Freshness / OldTargetApi / AGP / Kotlin | Resolved by commits 2–4 or disabled as online freshness |
| `MonochromeLauncherIcon` | Added `drawable-nodpi/ic_launcher_monochrome.png` (white silhouette from `drawable-xxxhdpi/ic_launcher_foreground.png` alpha) to both adaptive XMLs |
| `IconLocation` | Moved splash PNGs to `drawable-nodpi/` and `drawable-night-nodpi/` |
| `IconLauncherShape` on 10 legacy `ic_launcher.png` squares | 1-pixel transparent inset so the asset is not a filled square. Mark and brand fill are unchanged. Owner visual check remains for pre-API-26 tiles. Round mipmaps were already not filled squares. |

`verify.yml` job `android-lint` runs both variants. Existing
claim / archive / Gitleaks / action-pin jobs are unchanged.

Re-running `resolveAndLockAll --write-locks` on 2026-08-23 produced
byte-identical SHA-256 hashes for every lockfile. Do not hand-edit
generated lock lines.

## Gradle dependency verification (2026-08-23)

| Item | Value |
|---|---|
| File | `gradle/verification-metadata.xml` |
| Algorithms | SHA-256 only (`verify-signatures` is `false`) |
| Generation | `./gradlew --no-daemon --no-configuration-cache --write-verification-metadata sha256` plus the same compile/test/assemble graph as lock generation |
| Host | macOS arm64, Gradle 9.7.1 |
| Bootstrap | Gradle writes `origin="Generated by Gradle"` on every checksum |

Review performed on the generated file (checksums were not invented
or rewritten):

- No `sha1`, `md5`, or `pgp` entries.
- No `trusted-artifacts` exceptions.
- Spot-check: local Gradle-cache `junit-4.13.2.jar` SHA-256
  `8e495b634469d64fb8acfa3495a065cbacc8a0fff55ce1e31007be4c16dc57d3`
  matches the metadata row.
- Spot-check: Maven Central
  `org/bouncycastle/bcprov-jdk18on/1.85.2/bcprov-jdk18on-1.85.2.jar.sha256`
  is `986b0fb92ec10e0c66b43e036ce0077e6150cfaecd1db9fb92b56672e157afe5`,
  matching the metadata row.

Tamper proof (not committed): the `junit-4.13.2.jar` SHA-256 first
nibble was changed `8` → `9`. `:core:jvmTest` failed at
`:core:compileTestKotlinJvm` with `Dependency verification failed`
for `junit:junit:4.13.2`. The generated checksum was restored.

A first Ubuntu CI run may still request a Linux-only artifact that
this macOS generation did not hash. If that happens, regenerate
metadata on that runner with `--write-verification-metadata sha256`
and review the diff. Do not invent checksums to hide the miss.

## Cargo lock and Rust toolchain (2026-08-23)

| Item | Value |
|---|---|
| Toolchain file | `crypto-signing-backend/rust-toolchain.toml` |
| Channel | `1.97.0` (README pin; rustup resolved `1.97.0 (2d8144b78 2026-07-07)`) |
| Direct crates | `ed25519-bip32 = "=0.4.2"`, `uniffi = "=0.29.5"` |
| Lockfile | `crypto-signing-backend/Cargo.lock` (unchanged by the exact-pin edit) |
| Rebuild flags | every documented `cargo` / `cargo ndk` rebuild uses `--locked` |

`cargo metadata --locked` was run twice after the pin edit; `Cargo.lock`
had no diff. Natives were not rebuilt.
