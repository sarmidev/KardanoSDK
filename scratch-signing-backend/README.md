# `scratch-signing-backend` — disposable Block 1.10b provisioning spike

**This module is not part of the Kardano SDK.** It is not published, no SDK module depends on
it, and it is meant to be **deleted** once its evidence is recorded in
`docs/DECISIONS/0016-transaction-signing-backend-gate.md` (§7e). It exists only to answer one
question: *can a project-owned UniFFI/KMP wrapper over `ed25519-bip32 = "0.4.2"` expose Cardano
extended Ed25519-BIP32 `sign`/`verify` across JVM + Android + iOS?*

Result: **PARTIAL.** JVM and iOS: yes, verified below. Android: the underlying Rust primitive
cross-compiles and runs correctly on real Android hardware, but wiring it through Gradle via
Gobley 0.3.7 is blocked by an upstream Gobley↔AGP-9 incompatibility (see "Android" below).
**Block 1.10b stays blocked** — this spike does not meet the ADR-0016 §7d bar (all of JVM +
Android real-runtime KAT *through the packaged wrapper* + iOS + symbol proof), because the
Android real-runtime KAT could not be run through the wrapper's own Gradle/AGP packaging.

## What this proves

The Rust wrapper (`src/commonMain/rust/lib.rs`) exposes exactly two functions plus one
diagnostic helper, all delegating directly to the reference crate — **no handwritten crypto**:

- `sign(xprv: Vec<u8>, message: Vec<u8>) -> Vec<u8>` → `ed25519_bip32::XPrv::sign`
- `verify(xpub: Vec<u8>, message: Vec<u8>, signature: Vec<u8>) -> bool` → `ed25519_bip32::XPub::verify`
- `derive_xpub(xprv: Vec<u8>) -> Vec<u8>` → `ed25519_bip32::XPrv::public` (test-only helper, not a
  new capability — the shipped `bip32-ed25519:1.8.8` wrapper already exposes and verifies this
  same derivation, per ADR-0016 §1)

## Versions and licenses (record before deleting this module)

| Component | Version | License |
|---|---|---|
| `ed25519-bip32` (crate) | `0.4.2` (pinned, from crates.io) | MIT OR Apache-2.0 |
| `cryptoxide` (transitive; underlying `signature_extended` primitive) | `0.5.3` | MIT OR Apache-2.0 |
| `uniffi` (Rust crate) | `0.29.5` (resolved from `"0.29.4"` requirement) | MPL-2.0 |
| Gobley (`dev.gobley.cargo` / `dev.gobley.uniffi`) | `0.3.7` | Apache-2.0 OR MIT |
| Rust toolchain (`rustc`/`cargo`) | `1.97.0` (installed via `rustup` for this spike; was not previously installed in this environment) | MIT OR Apache-2.0 |
| `cargo-ndk` | `4.1.2` (installed via `cargo install` for this spike) | MIT |
| Android NDK | `27.2.12479018` (installed via `sdkmanager` for this spike; not previously installed) | Apache-2.0 (Android NDK license) |
| Kotlin / Gradle / AGP | `2.4.0` / `9.1.0` / `9.0.1` (repo-pinned, unchanged) | — |

None of the crate/toolchain installs above touched any SDK module; `rustup`, `cargo-ndk`, and the
Android NDK package are host-machine toolchain installs, analogous to already-required Xcode/JDK.

## JVM: PASS (real Gobley/UniFFI/JNA bindings, not just `cargo test`)

```
./gradlew :scratch-signing-backend:jvmTest
```

4/4 tests passed against the actual generated Kotlin bindings (JNA-backed native call, not the
plain Rust unit test in `lib.rs`, which also passes standalone via `cargo test`):

- `reproduces ADR-0016 D1_H0 primary KAT` — reproduces `D1_H0` + `"Hello World"` ⇒
  `D1_H0_SIGNATURE` exactly.
- `sign-then-verify self-consistency using the derived xpub`
- `verify rejects a tampered signature`
- `rejects wrong-length extended private key`

Native artifact produced: `target/aarch64-apple-darwin/debug/libsigning_backend_wrapper.dylib`.
Symbol proof (`nm -gU`):

```
_uniffi_signing_backend_wrapper_fn_func_sign
_uniffi_signing_backend_wrapper_fn_func_verify
_uniffi_signing_backend_wrapper_fn_func_derive_xpub
```

## iOS: PASS (compile + link, per ADR-0016 §4 "iOS is compile/link at minimum")

```
./gradlew :scratch-signing-backend:compileKotlinIosArm64
./gradlew :scratch-signing-backend:linkDebugTestIosSimulatorArm64
```

Both succeeded (`BUILD SUCCESSFUL`), producing:

- `target/aarch64-apple-ios/debug/libsigning_backend_wrapper.a`
- `target/aarch64-apple-ios-sim/debug/libsigning_backend_wrapper.a`

Symbol proof (`nm -gU`) on **both** static libraries confirms `_uniffi_signing_backend_wrapper_fn_func_sign`,
`..._fn_func_verify`, and `..._fn_func_derive_xpub`. iOS **runtime** execution (simulator/device)
was not performed and remains future work, consistent with `kotlin-tests-and-docs.mdc`'s iOS
posture ("compile+link ... iOS runtime execution is separate future work unless a
simulator/device run is explicitly recorded").

## Android: blocked at the Gradle/Gobley layer (not at the Rust/crate layer)

**What is blocked.** This repository pins AGP `9.0.1` (`gradle/libs.versions.toml`, unchanged by
this spike). Under AGP 9, the classic `com.android.library` plugin refuses to combine with
`org.jetbrains.kotlin.multiplatform`:

```
Failed to apply plugin 'com.android.internal.library'.
> The 'com.android.library' (or 'com.android.application') plugin is not compatible with the
  'org.jetbrains.kotlin.multiplatform' plugin since AGP 9.0.
  Solution: Replace the 'com.android.library' plugin with the
  'com.android.kotlin.multiplatform.library' plugin.
```

Gobley `0.3.7` does not yet support `com.android.kotlin.multiplatform.library`
(confirmed upstream, open, unreleased fix as of this spike:
<https://github.com/gobley/gobley/issues/153> — a maintainer there reports the same error and
says they downgraded their own project to AGP `8.12.3` to keep using Gobley with
`com.android.library`). Downgrading this repo's AGP pin is out of this spike's scope (it is a
project-wide Gradle change requiring its own decision, and would affect every SDK module, not
just this disposable one) — so **no Android Kotlin target is declared in this module's
`build.gradle.kts`**, and no Gradle-driven `connectedAndroidDeviceTest`/instrumented KAT through
the packaged UniFFI+JNA bindings was attempted or is possible today with this toolchain
combination.

**What is proven instead, entirely outside Gradle/AGP** (so nothing here touches any SDK module):

1. **Cross-compilation, all 4 ABIs**, via `cargo-ndk` 4.1.2 + NDK `27.2.12479018`:

   ```
   cargo ndk -t arm64-v8a -t armeabi-v7a -t x86_64 -t x86 build --lib
   ```

   All four `libsigning_backend_wrapper.so` built cleanly.

2. **Symbol proof per ABI** (NDK `llvm-nm -D`):

   ```
   <NDK>/toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-nm -D <abi>/libsigning_backend_wrapper.so
   ```

   `uniffi_signing_backend_wrapper_fn_func_sign`, `..._fn_func_verify`, and
   `..._fn_func_derive_xpub` are exported on **every** ABI (arm64-v8a, armeabi-v7a, x86_64, x86).

3. **Real Android-runtime execution of the underlying primitive** (not through UniFFI/JNI/Kotlin —
   through a standalone diagnostic Rust binary, `src/bin/android_runtime_kat_check.rs`, that
   calls `ed25519_bip32::XPrv::sign`/`XPub::verify` directly and reproduces the exact ADR-0016 §3
   `D1_H0` KAT):

   ```
   cargo ndk -t arm64-v8a build --bin android_runtime_kat_check
   adb -s <device> push target/aarch64-linux-android/debug/android_runtime_kat_check /data/local/tmp/
   adb -s <device> shell chmod 755 /data/local/tmp/android_runtime_kat_check
   adb -s <device> shell /data/local/tmp/android_runtime_kat_check
   ```

   Ran successfully (`ANDROID_RUNTIME_KAT: PASS`, exit code 0) on:
   - a **physical device** (arm64-v8a, Android 15 / API 35), and
   - the project's existing `kardano_test`/`kardano_api24` **emulator** (arm64-v8a, Android 7.0 /
     API 24 — the SDK's own `minSdk`).

   This is real evidence that the extended-signing primitive executes correctly under Android's
   actual ARM64 userspace/libc on both ends of the SDK's supported API range. It is **not**
   equivalent to a `connectedAndroidDeviceTest` through the packaged UniFFI+JNA bindings (the
   Kotlin/JNI bridge itself was never exercised on-device, because that bridge cannot currently
   be built by Gradle for Android at all — see above), so it does not, by itself, satisfy
   ADR-0016 §7d's Android requirement.

**Why this isn't "improvising on SDK modules."** Nothing above touches `:crypto`, `:tx`,
`:wallet`, `:shared`, `:core`, any provider/app module, or any SDK Gradle file; `cargo`, `rustup`,
`cargo-ndk`, and the Android NDK package are host-toolchain installs (like Xcode/JDK), and the
diagnostic binary and all commands above live only in this disposable module / `adb`/`/tmp`.

**Recommended follow-up (separate, future-authorized task; not done here).** ADR-0016 §7a
Option B2 (fork/adopt an identus-apollo-style Cargo + cinterop packaging) is the natural fallback,
but note it likely needs to skip Gobley's *Android Gradle plugin* specifically (not Gobley
wholesale) and instead: (a) keep using `cargo ndk` exactly as proven above to build the 4 ABI
`.so` files, (b) generate the Kotlin bindings with the `uniffi-bindgen`/`gobley-uniffi-bindgen`
CLI directly (library mode) rather than the Gobley Gradle plugin, and (c) wire the resulting
`.so`s + generated Kotlin file into this SDK's existing AGP-9-compatible `androidLibrary {}` KMP
DSL by hand (the same shape `crypto/build.gradle.kts` already uses for `bip32-ed25519:1.8.8`
jniLibs). That is new build-plumbing work requiring its own scoped authorization, not something
this spike should start.

## How to reproduce

```bash
# JVM
./gradlew :scratch-signing-backend:jvmTest

# iOS compile/link
./gradlew :scratch-signing-backend:compileKotlinIosArm64
./gradlew :scratch-signing-backend:linkDebugTestIosSimulatorArm64

# Plain Rust KAT (host, no Gradle/Gobley)
cd scratch-signing-backend && cargo test

# Android cross-compile + symbol proof (no Gradle/AGP)
export ANDROID_NDK_HOME=<sdk>/ndk/27.2.12479018
cargo ndk -t arm64-v8a -t armeabi-v7a -t x86_64 -t x86 -o /tmp/scratch-android-out build --lib
<ndk>/toolchains/llvm/prebuilt/<host>/bin/llvm-nm -D /tmp/scratch-android-out/arm64-v8a/libsigning_backend_wrapper.so | rg fn_func
```

## Disposal

This module should be deleted (and the `include(":scratch-signing-backend")` line removed from
the root `settings.gradle.kts`) once ADR-0016 records this spike's evidence. It has no
consumers.
