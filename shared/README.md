# :shared

Currently the sample/UI host module. It carries the Compose Multiplatform sample UI and
builds the iOS `Shared` framework that the Xcode app consumes.

## Status

Phase 0 — pre-alpha, experimental. Not audited. Not for real funds.

## Role today

- Hosts the wizard-derived sample UI (`App.kt`) and the iOS UI entry point
  (`MainViewController.kt`).
- Holds the sample glue (`Greeting.kt`, `GreetingUtil.kt`).
- Depends on `:core` for the UI-free `Platform` descriptor.
- Builds the static iOS framework named `Shared` (`baseName = "Shared"`), consumed by
  `iosApp` via `MainViewControllerKt.MainViewController()`.

## Why it still contains UI

The SDK core direction is UI-free and lives in `:core`. `:shared` keeps Compose because the
iOS app needs a Kotlin-produced UI framework. Removing Compose from `:shared` outright would
break the iOS sample app.

## Planned direction

`:shared` is expected to migrate toward a dedicated sample module (a candidate `:sample:*`
name) in a later step. It is intentionally not renamed now to avoid changing the iOS Xcode
project. See [docs/DECISIONS/0002-module-structure.md](../docs/DECISIONS/0002-module-structure.md).

## Consumers

- `:androidApp`, `:desktopApp` depend on `:shared`.
- `iosApp` (Xcode) links the `Shared` framework produced here.

## Testing

`:shared` carries example tests in `commonTest`, `jvmTest`, `androidHostTest`, and `iosTest`
that demonstrate the wiring per target. Protocol vectors and SDK-logic tests belong in
`:core`, not here. See [docs/TESTING.md](../docs/TESTING.md) for the testing strategy and
test-vector policy.

- Desktop (JVM) tests: `./gradlew :shared:jvmTest`
- Android host tests: `./gradlew :shared:testAndroidHostTest`
- iOS simulator tests: `./gradlew :shared:iosSimulatorArm64Test`
