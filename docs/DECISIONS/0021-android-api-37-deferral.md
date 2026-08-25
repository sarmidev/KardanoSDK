# ADR-0021: Defer Android API 37 Until The Supported Toolchain Envelope

| Field   | Value |
|---------|--------|
| Status  | **Accepted** (2026-08-23). Dated deferral, not a claim that API 36
          is the latest platform. |
| Scope   | Prompt 6 review fix: Kotlin / Gradle / AGP compatibility vs
          compile/target SDK 37. |
| Phase   | Pre-release hygiene |
| Updated | 2026-08-23 |

---

## Context

Prompt 6 commit 2 paired Kotlin **2.4.10** with Gradle **9.7.1** and
AGP **9.3.1** so the Playground could compile and target API **37**.
Those local builds succeeded.

The official Kotlin Gradle plugin table
(https://kotlinlang.org/docs/gradle-configure-project.html, fetched
2026-08-23) lists Kotlin **2.4.0–2.4.10** as fully supported only for:

| Tool | Official min–max |
|---|---|
| Gradle | 7.6.3–**9.5.0** |
| AGP | 8.5.2–**9.1.0** |

The same bounds appear in the Kotlin Multiplatform compatibility guide.
Kotlin's own note says newer Gradle/AGP releases may be used but can
emit deprecations or miss features. The review required the latest
**mutually supported stable** combination, not a locally passing
out-of-envelope pair.

AGP 9.1.0's published compile/target ceiling on this host is **API 36**.
API 37 is published as `platforms/android-37.0` and needs a newer AGP
line (9.1.1+ / 9.3.x) that Kotlin 2.4.10 does not fully support.

## Decision

1. Pin **Kotlin 2.4.10**, **Gradle 9.5.0**, **AGP 9.1.0**.
2. Pin Android **compileSdk / targetSdk 36** (catalog integers).
3. Pin JetBrains lifecycle Compose at **2.10.0**. AndroidX 2.11.0
   requires compile SDK 37 and AGP >= 9.2.0, which is outside this
   envelope (https://developer.android.com/jetpack/androidx/releases/lifecycle
   version 2.11.0-beta01 notes, still true for 2.11.0).
4. Disable only the **OldTargetApi** lint check, with this ADR as the
   rationale, so CI does not fail solely because API 37 exists.
5. Revisit API 37 (and lifecycle 2.11) when an official Kotlin row
   lists an AGP that documents API 37 as a supported compile/target.

This is not a device-compatibility claim. No emulator or device run is
part of this decision.

## Consequences

- Prompt 6's API 37 target notes stay historical. Current pins are 36.
- Lint freshness detectors remain disabled because versions are locked
  and SHA-256 verified; OldTargetApi is a separate, narrow disable.
- Do not raise Gradle/AGP past the Kotlin table to "get" API 37.
