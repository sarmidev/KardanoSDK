# ADR-0002: Initial SDK Module Structure (introduce :core)

| Field    | Value                         |
|----------|-------------------------------|
| Status   | **Accepted**                  |
| Scope    | Phase 0 Block 0.2 module structure |
| Phase    | Phase 0                       |
| Updated  | 2026-06-29                    |

---

## Context

The repository started from the Kotlin Multiplatform wizard with modules `:shared`,
`:androidApp`, `:desktopApp` and an `iosApp` Xcode project. The `:shared` module mixed
UI-free logic (`Platform` `expect`/`actual`) with Compose Multiplatform sample UI
(`App.kt`, `MainViewController.kt`) and carried Compose dependencies in its `commonMain`
source set. This conflicts with the Phase 0 goal that the SDK core be UI-free.

Block 0.2 calls for moving toward an SDK-oriented structure without over-splitting. The
roadmap lists candidate future modules (`:core`, `:crypto`, `:wallet`, `:tx`, `:provider`,
`:sample:*`) but they are not all justified yet.

A key constraint: the iOS app consumes a Kotlin-produced UI framework named `Shared`
(`MainViewControllerKt.MainViewController()`). UI for iOS cannot simply leave the Kotlin
layer, so the module that produces the iOS framework must keep the Compose UI for now.

## Decision

1. Introduce a single new UI-free Kotlin Multiplatform module, `:core`, as the seed of the
   SDK core. It uses `explicitApi()`, has no Compose plugin or dependency, and targets
   Android library, JVM, iosArm64, and iosSimulatorArm64.
2. Move only the `Platform` `expect`/`actual` declarations from `:shared` into `:core`,
   keeping the package `org.sarmidev.kardano`.
3. Make `:shared` depend on `:core`. Keep Compose and the sample UI (`App.kt`,
   `MainViewController.kt`, `Greeting.kt`, `GreetingUtil.kt`) in `:shared`.
4. Keep `:shared` as the sample/UI host for now, including building the iOS `Shared`
   framework. Do not rename it in this step.
5. Defer `:crypto`, `:wallet`, `:tx`, `:provider`, and `:sample:*` until there is code that
   justifies each one.

## Rejected alternatives

- **Strip Compose/UI from `:shared` immediately.** Rejected: the iOS app depends on the
  Kotlin-produced `Shared` UI framework, so removing UI from `:shared` would break the iOS
  sample app. Not the smallest low-risk step.
- **No module reorganization (reorganize inside `:shared` only).** Rejected: Compose would
  remain in the core source set, so it would not actually establish a UI-free SDK core,
  which is the point of Block 0.2.

## Consequences

- The UI-free SDK-core boundary now exists in `:core`; future Phase 0 primitives and
  parsers land there.
- The sample apps are unchanged: they still depend on `:shared` and receive `:core`
  transitively; the iOS Xcode project and Swift files are untouched.
- `:core` and `:shared` both build Android library variants and use distinct Android
  namespaces (`org.sarmidev.kardano.core` vs `org.sarmidev.kardano.shared`).

## Follow-up work

- Decide whether `:shared` should later become a dedicated sample module (candidate
  `:sample:*` name); that step would touch the iOS Xcode project and is out of scope here.
- Revisit additional module splits (`:crypto`, `:wallet`, `:tx`, `:provider`) when code
  exists to justify them.
- `LICENSE` selection remains an owner decision and is not made here.
- ADR-0001 (CBOR/parser policy) was Open at the time of this decision and unaffected by it;
  it was later Accepted.
