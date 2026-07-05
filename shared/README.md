# :shared

Currently the sample/UI host module. It carries the Compose Multiplatform sample UI and
builds the iOS `Shared` framework that the Xcode app consumes.

## Status

Phase 0 — pre-alpha, experimental. Not audited. Not for real funds.

## Role today

- Hosts the SDK Playground (`playground/PlaygroundScreen.kt`, `playground/PlaygroundPresenter.kt`),
  introduced in Block 1.2, as the Android-facing diagnostic surface for existing `:core` SDK
  behavior (address parsing, Hex, CBOR).
- Hosts `App.kt` (theme wrapper that renders `PlaygroundScreen`) and the iOS UI entry point
  (`MainViewController.kt`).
- Retains the sample glue (`Greeting.kt`, `GreetingUtil.kt`) used by `PlaygroundScreen` to
  show the platform name.
- Depends on `:core` for all SDK logic (`Address.parse`, `Hex`, `Cbor`, `Platform`).
- Builds the static iOS framework named `Shared` (`baseName = "Shared"`), consumed by
  `iosApp` via `MainViewControllerKt.MainViewController()`.

**SDK logic and the protocol test-vector suite belong in `:core`, not here.** `:shared` only
calls `:core` APIs and formats/displays results. `PlaygroundPresenter` is a display-only
mapping layer with no protocol rules of its own. `:shared` tests use a minimum of cited
CIP-19 vectors to verify presenter wiring, but do not replicate the `:core` test-vector suite.

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
that demonstrate the wiring per target. The protocol test-vector suite and SDK-logic tests
belong in `:core`; `:shared` uses only a minimum of cited CIP-19 vectors for presenter-wiring
verification. See [docs/TESTING.md](../docs/TESTING.md) for the testing strategy and
test-vector policy.

- Desktop (JVM) tests: `./gradlew :shared:jvmTest`
- Android host tests: `./gradlew :shared:testAndroidHostTest`
- iOS simulator tests: `./gradlew :shared:iosSimulatorArm64Test`
