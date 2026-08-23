# `:crypto-signing-backend` — Cardano extended Ed25519-BIP32 signing backend

Permanent, project-owned SDK module that exposes Cardano **extended** Ed25519-BIP32
`sign`/`verify` across JVM + Android + iOS, by wrapping the reference `ed25519-bip32` Rust crate
via UniFFI. It is the adopted, non-disposable replacement for the `scratch-signing-backend`
provisioning spike (ADR-0016 §8), landed per **ADR-0016 §9, Option R1**.

- **No handwritten crypto.** The Rust wrapper (`src/commonMain/rust/lib.rs`) delegates directly to
  `ed25519_bip32::XPrv::sign` / `XPub::verify` (the primitive cited in ADR-0016 §3 / CIP-3). It is
  not plain RFC-8032 seed-based Ed25519.
- **Thin seam only.** The module exposes only the generated backend seam
  (`sign` / `verify` / `deriveXpub` in package `org.sarmidev.kardano.crypto.signing.backend.internal`).
  There is no high-level `Signing` API, no witness/transaction assembly, and no wallet
  orchestration in *this* module — those landed in `:crypto`/`:tx`/`:wallet` respectively in
  Block 1.10b (ADR-0015), which added a `commonMain` dependency from `:crypto` on this module.
  `:crypto`'s internal `Ed25519Bip32Signing` adapter is the only caller of this module's `sign`;
  this module's generated bindings never appear in `:crypto`'s public API.

## Option R1: how the module is built (no Rust/Cargo/Gobley Gradle plugin)

This module applies **no** Rust/Cargo/Gobley Gradle plugin. The native artifacts and the UniFFI
Kotlin bindings are **built ahead of time, offline, and committed as reviewed inputs**:

| Committed input | Path |
|---|---|
| Generated common/jvm/native/android bindings | `src/{commonMain,jvmMain,nativeMain,androidMain}/kotlin/.../internal/kardano_ed25519_bip32_signing.*.kt` |
| UniFFI C header + cinterop def | `src/nativeInterop/cinterop/` |
| JVM cdylibs (macOS) | `src/jvmMain/resources/{darwin-aarch64,darwin-x86-64}/libkardano_ed25519_bip32_signing.dylib` |
| Android `.so` (4 ABIs) | `src/androidMain/jniLibs/{arm64-v8a,armeabi-v7a,x86_64,x86}/libkardano_ed25519_bip32_signing.so` |
| iOS static libs | `src/nativeInterop/libs/{iosArm64,iosSimulatorArm64}/libkardano_ed25519_bip32_signing.a` |

A Gobley-free single module is required because Gobley `0.3.7` cannot coexist with an
`androidLibrary {}` target under this repo's AGP `9.0.1` pin (ADR-0016 §8, `gobley/gobley#153`).
The Rust crate (`Cargo.toml`, `Cargo.lock`) is retained in-tree only for offline regeneration; it
is `publish = false` and is **not** compiled by Gradle.

### JVM native coverage is macOS-only (deliberate scope, ADR-0016 §9)

JNA loads the committed cdylib per host from `src/jvmMain/resources/<jna-prefix>/`. There is **no
CI** in this repo and the SDK is developed/verified on macOS, so only the macOS cdylibs are
committed:

- `darwin-aarch64` — **runtime-verified** here (`jvmTest` runs on the macOS arm64 dev host).
- `darwin-x86-64` — cross-built on macOS, **not** runtime-verified on this arm64 host.
- **Linux / Windows JVM hosts are not covered** — no committed cdylib for those prefixes, so JNA
  loading would fail there. Broadening host coverage (or publishing a multi-host artifact) is
  future work (ADR-0016 §9, Option R3). This module does not claim general cross-host JVM
  verification.

## Verified (ADR-0016 §7d / §9f) — all four legs against this real module

| Leg | Command | Result |
|---|---|---|
| JVM KAT (through JNA bindings) | `./gradlew :crypto-signing-backend:jvmTest` | 4/4 pass (macOS arm64) |
| Android real-runtime KAT (through packaged Kotlin/JNA bindings) | `./gradlew :crypto-signing-backend:connectedAndroidDeviceTest` | 4/4 on `SM-A356B` (Android 15, physical) + 4/4 on `kardano_api24` (API 24 emulator = SDK `minSdk`) |
| iOS compile + link | `./gradlew :crypto-signing-backend:compileKotlinIosArm64` + `:linkDebugTestIosSimulatorArm64` | both `BUILD SUCCESSFUL`; the simulator test binary links the committed `.a` |
| Symbol proof (per target) | `nm -gU` (macOS/iOS), `llvm-nm -D` (Android) | `kardano_ed25519_bip32_signing_fn_func_sign` exported on all 8 artifacts |

The KAT is ADR-0016 §3 `D1_H0`: extended scalar signs `"Hello World"` ⇒ `D1_H0_SIGNATURE`
(reproduced exactly), plus sign-then-verify, tampered-signature rejection, and wrong-length-xprv
rejection. iOS on-simulator/on-device *execution* of assertions is honest future work (this leg is
compile+link), matching the repo's iOS posture.

## Versions and licenses

| Component | Version | License |
|---|---|---|
| `ed25519-bip32` (crate) | `0.4.2` (pinned; `Cargo.lock`) | MIT OR Apache-2.0 |
| `cryptoxide` (transitive; underlying `signature_extended` primitive) | `0.5.3` | MIT OR Apache-2.0 |
| `uniffi` (Rust crate) | `=0.29.5` (`Cargo.toml` + `Cargo.lock`) | MPL-2.0 |
| `gobley-uniffi-bindgen` (CLI, offline binding generation only) | `0.3.7` | Apache-2.0 OR MIT |
| Rust toolchain (`rustc`/`cargo`) | `1.97.0` (`rust-toolchain.toml`) | MIT OR Apache-2.0 |
| `cargo-ndk` (offline Android cross-build only) | `4.1.2` | MIT |
| Android NDK (offline Android cross-build only) | `27.2.12479018` | Android NDK license (Apache-2.0) |
| `net.java.dev.jna:jna` (jvm jar / android `@aar`) | `5.19.1` (`gradle/libs.versions.toml`) | Apache-2.0 OR LGPL-2.1 |
| `org.jetbrains.kotlinx:atomicfu` (bindings' handle-map counter) | `0.26.1` (`gradle/libs.versions.toml`) | Apache-2.0 |
| Kotlin / Gradle / AGP | `2.4.10` / `9.7.1` / `9.3.1` (repo-pinned) | — |

`rustup`, `cargo-ndk`, the Android NDK, and `gobley-uniffi-bindgen` are host-machine toolchain
installs used only for the offline regeneration below; none is a Gradle build dependency of this
module and none is added to any SDK module.

## Regenerating the committed artifacts (offline)

Run from this module directory. Requires the toolchain versions above.

```bash
export ANDROID_NDK_HOME="$HOME/Library/Android/sdk/ndk/27.2.12479018"
LIB=libkardano_ed25519_bip32_signing

# 1. JVM cdylibs (macOS arm64 host + x86_64 cross-build)
cargo build --locked --release --lib
cp target/release/$LIB.dylib                       src/jvmMain/resources/darwin-aarch64/
rustup target add x86_64-apple-darwin
cargo build --locked --release --lib --target x86_64-apple-darwin
cp target/x86_64-apple-darwin/release/$LIB.dylib   src/jvmMain/resources/darwin-x86-64/

# 2. Android .so, 4 ABIs
cargo ndk -t arm64-v8a -t armeabi-v7a -t x86_64 -t x86 -o src/androidMain/jniLibs build --locked --release --lib

# 3. iOS static libs
cargo build --locked --release --lib --target aarch64-apple-ios
cargo build --locked --release --lib --target aarch64-apple-ios-sim
cp target/aarch64-apple-ios/release/$LIB.a         src/nativeInterop/libs/iosArm64/
cp target/aarch64-apple-ios-sim/release/$LIB.a     src/nativeInterop/libs/iosSimulatorArm64/

# 4. Kotlin UniFFI bindings (common/jvm/native/android + C header) via the gobley-uniffi-bindgen CLI.
#    Config keys live at the TOML root (uniffi-bindgen.toml). The CLI is installed by Gobley's own
#    Gradle plugin; obtain it (e.g.) by building any Gobley module once, then:
#      gobley-uniffi-bindgen --library --config uniffi-bindgen.toml -o <out> target/release/$LIB.dylib
#    and copy the generated files into src/{commonMain,jvmMain,nativeMain,androidMain}/kotlin/... and
#    src/nativeInterop/cinterop/headers/... . The `.def` in src/nativeInterop/cinterop/ is hand-written
#    (the CLI does not emit it) and must keep `package = kardano_ed25519_bip32_signing.cinterop`.

# 5. Symbol proof
nm -gU src/jvmMain/resources/darwin-aarch64/$LIB.dylib | grep _fn_func_sign
"$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-nm" -D \
  src/androidMain/jniLibs/arm64-v8a/$LIB.so | grep _fn_func_sign

# 6. Regenerate the checksum manifest (see "Verifying the committed binaries" below)
shasum -a 256 \
  src/nativeInterop/libs/iosArm64/$LIB.a \
  src/nativeInterop/libs/iosSimulatorArm64/$LIB.a \
  src/androidMain/jniLibs/arm64-v8a/$LIB.so \
  src/androidMain/jniLibs/armeabi-v7a/$LIB.so \
  src/androidMain/jniLibs/x86/$LIB.so \
  src/androidMain/jniLibs/x86_64/$LIB.so \
  src/jvmMain/resources/darwin-aarch64/$LIB.dylib \
  src/jvmMain/resources/darwin-x86-64/$LIB.dylib \
  > CHECKSUMS.sha256
```

## Verifying the committed binaries (checksum manifest, W5-2)

[`CHECKSUMS.sha256`](CHECKSUMS.sha256) records the SHA-256 of all 8 committed native binaries
(the two iOS `.a`, the four Android `.so`, the two macOS JVM `.dylib`), so a consumer can confirm
which exact bytes they are trusting without cloning the repository at every historical commit to
diff them by hand. Verify from this module's directory:

```bash
shasum -a 256 -c CHECKSUMS.sha256
```

**What this manifest does and does not prove.** A passing check confirms only that the binaries in
your working tree are byte-identical to the ones this manifest was generated against — it is a
tamper/corruption/transfer-integrity check, tied to a specific commit. **It does not prove, and
this project does not claim, that these binaries were actually built from the visible Rust source**
(`src/commonMain/rust/lib.rs` and the pinned `Cargo.lock`) — that would require an independent
reproducible-build verification (rebuilding with the exact pinned toolchain in step 1 above and
diffing the result against the committed binaries), which this project has not performed and which
remains an open residual risk (see `docs/AUDIT/2026-08-22-pre-release-audit.md` §6 item 7).

**Regeneration rule:** this manifest must be regenerated in the *same commit* as any change to one
or more of the 8 binaries above (step 6 in the regeneration recipe), never as a separate follow-up
commit — a stale manifest that doesn't match the binaries it ships alongside is worse than no
manifest, since it would falsely suggest the pair was checked together.
