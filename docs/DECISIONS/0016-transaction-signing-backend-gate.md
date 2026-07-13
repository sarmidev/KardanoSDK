# ADR-0016: Transaction Signing Backend & Vector-Source Gate

| Field   | Value                                                                 |
|---------|------------------------------------------------------------------------|
| Status  | **Accepted** (Block 1.10b-pre gate). **Gate result: backend ADOPTED and VERIFIED (§9i).** The provisioning spike (§7e/§8) has been adopted per §9 Option R1 into the permanent, project-owned module `:crypto-signing-backend`, and every §7d verification leg was re-run and **passes against that real module**: JVM KAT (4/4, macOS arm64), Android real-runtime KAT *through the packaged wrapper* (`connectedAndroidDeviceTest`, 4/4 on a physical device + 4/4 on an emulator), iOS compile/link, and `nm`/`llvm-nm` symbol proof on all 8 committed native artifacts (§9i). The disposable `scratch-signing-backend` / `scratch-signing-backend:android` modules are deleted. **ADR-0015 §4's backend condition is now satisfied, so Block 1.10b (the signing implementation) is unblocked.** This adoption block itself pinned only the backend module and added **no** signing API, **no** `:crypto`→`:crypto-signing-backend` dependency, and no change to any other SDK module. JVM native coverage is macOS-only by design (no CI in-repo; §9e/§9i). |
| Scope   | Block 1.10b-pre — resolve/verify the extended Ed25519-BIP32 signing backend from resolved-artifact evidence, pin a citable extended-key signature vector, define the target-coverage plan, and record the gate result required by ADR-0015 §4/§6 |
| Phase   | Phase 1 (Block 1.10b-pre)                                              |
| Updated | 2026-07-13                                                            |

---

## Context

ADR-0015 §4 made the signing backend a **blocking, docs-only gate**: before any Block 1.10b
signing code, and from **resolved-artifact evidence only**, this block must (1) identify a backend
that signs with a **pre-expanded 64-byte Ed25519-BIP32 extended scalar** (`kL` ‖ `kR`) — i.e.
Cardano extended-key signing, not standard RFC 8032 seed-based Ed25519; (2) verify it across
JVM + Android real runtime + iOS (compile/link at minimum) with no handwritten crypto; and (3) pin
a **citable extended-key** signature KAT (a plain-Ed25519 KAT does **not** pass, per ADR-0015
§4/§6).

This ADR records the gate's outcome. The signed message for Block 1.10 remains
`bodyHash = Blake2b-256(TransactionDraft.bodyCbor())`, a 32-byte transaction id (ADR-0015 §3); a
signing backend is correct for this SDK only if it signs an arbitrary message with the extended
scalar, so a length-agnostic extended-signing KAT proves the primitive.

**Inspection method (resolved artifacts, not documentation claims).** Evidence below comes from
`unzip -l` (jar/AAR contents), `javap -p -c` (JVM method surface and bytecode delegation), and
`nm -gU` / `strings` (native-library exported symbols) run against the artifacts already resolved
in the Gradle cache, plus reading the pinned upstream source for the reference implementation and
the cited vector.

---

## Decision (gate result)

**Backend ADOPTED and VERIFIED (§9i); ADR-0015 §4's backend condition is now met, so Block 1.10b
(signing implementation) is unblocked.** The extended-key KAT is pinned (§3), the provisioning
spike (§7e/§8) has been adopted per §9 Option R1 into the permanent, project-owned module
`:crypto-signing-backend`, and every §7d verification leg was **re-run and passes against that real
module** (§9i): JVM KAT, iOS compile/link, Android real-runtime KAT *through the packaged wrapper*
(`connectedAndroidDeviceTest`, on both a physical device and an emulator), and `nm`/`llvm-nm`
symbol proof on all 8 committed native artifacts. The disposable spike modules are deleted.

- **KAT vector requirement: met.** A citable, unambiguous **extended** Ed25519-BIP32 signature
  known-answer vector is pinned (§3) — from the reference implementation (`ed25519-bip32` crate,
  cited by CIP-3). This satisfies the *vector* requirement of ADR-0015 §4/§6.
- **Backend requirement: met.** No currently-resolved or currently-published third-party KMP
  artifact exposes extended-key signing across all targets (§1), so this SDK now **vendors its
  own**: `:crypto-signing-backend` wraps the reference crate's `XPrv::sign`/`XPub::verify` through
  UniFFI (§9c/§9i), with the crate pinned (`ed25519-bip32 = "0.4.2"`, `Cargo.lock` committed) and
  the native artifacts + generated bindings committed as reviewed inputs (Option R1, §9b). JVM,
  iOS (compile/link), Android (real-runtime KAT through the packaged wrapper), and per-target
  symbol proof all pass against the real module (§9i). ADR-0015 §4's backend condition is therefore
  **satisfied**.

Therefore **Block 1.10b (signing implementation) is unblocked.** Note the scope boundary: this
adoption block pinned only the **backend module** and its native artifacts. It added **no** signing
API, **no** `:crypto`→`:crypto-signing-backend` dependency, and no change to any other SDK module —
those are the next block (§9i, follow-up). JVM native coverage is macOS-only by design (§9e/§9i):
there is no CI in-repo and the SDK is developed/verified on macOS, so only the macOS cdylibs are
committed (`darwin-aarch64` runtime-verified; `darwin-x86-64` cross-built); Linux/Windows JVM
hosts are explicit future work (§9 Option R3).

### 1. Resolved artifacts inspected — none can sign an extended key

| Artifact (resolved) | What was inspected | Signing capability | Verdict |
|---|---|---|---|
| `org.hyperledger.identus:bip32-ed25519:1.8.8` (uniffi `ed25519_bip32_wrapper`) | JVM jar classes; the four bundled native libs (`darwin-{aarch64,x86-64}`, `linux-{aarch64,x86-64}`) via `nm -gU` | Native library **exports only** `..._fn_func_derive_bytes`, `..._fn_func_derive_bytes_pub`, `..._fn_func_from_nonextended`. There is **no `sign` symbol** — the gap is in the shipped Rust cdylib itself, not merely the Kotlin binding, so a custom binding could not reach a `sign` that isn't exported. | **FAIL — no signing** |
| `org.hyperledger.identus:apollo-jvm:1.8.8` | `javap -p -c` of `utils.KMMEdPrivateKey` / `KMMEdKeyPair`; `derivation.EdHDKey` | `KMMEdPrivateKey(byte[])` + `sign(byte[])` delegates on JVM to BouncyCastle `Ed25519PrivateKeyParameters([B,I)` + `Ed25519Signer` — i.e. **standard RFC 8032 seed-based** Ed25519 (the 32-byte seed is SHA-512-expanded internally). It cannot consume a pre-expanded 64-byte `kL‖kR` scalar. `EdHDKey` is SLIP-0010-style Ed25519 HD derivation, not Cardano's Ed25519-BIP32 V2 scheme. | **FAIL — wrong algorithm (plain, seed-based)** |
| `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings:0.9.5` (JVM/iOS) and `com.goterl:lazysodium-android:5.2.0` (Android) | `javap -p` of `signature.Signature` | Surface is standard libsodium Ed25519: `sign`/`detached`/`seedKeypair`/`ed25519SkToSeed`/`ed25519SkToPk`. The secret key is the 64-byte `seed‖pk` layout and the scalar is re-derived from the seed via SHA-512 (`ed25519SkToSeed` confirms the seed layout). There is **no API to sign with an externally supplied pre-expanded scalar**. | **FAIL — seed-based only** |

Composing the Ed25519-BIP32 signing equation from libsodium scalar/hash primitives would be a
handwritten cryptographic algorithm, which ADR-0004 §3.1 and ADR-0015 §4 ban. So the ADR-0015
Context conclusion holds under direct symbol-level inspection: **no shipped dependency can produce
a Cardano extended-key signature.**

### 2. Candidate backends evaluated (from artifact/source evidence)

- **Uniffi/Kotlin wrapper exposing the reference crate's `XPrv::sign` — the identified path, not
  yet a resolved artifact.** The resolved `bip32-ed25519:1.8.8` is itself a uniffi wrapper of the
  reference Rust crate `ed25519-bip32` (namespace `uniffi.ed25519_bip32_wrapper`, native lib
  `libuniffi_ed25519_bip32_wrapper`). That crate **does implement extended signing**:
  `XPrv::sign(message)` calls `signature_extended(message, &self.0[0..64])` over the 64-byte
  extended key (confirmed in `src/key.rs`, and exercised by the crate's own `xprv_sign` test). The
  wrapper simply does not expose `sign` in its UDL. The clean unblock path is therefore to obtain a
  wrapper build that **also exports `sign` (and `verify`)** through the identical uniffi mechanism
  already proven for derivation across JVM/Android/iOS — either an upstream/newer/forked wrapper
  that adds it, or a project-owned uniffi wrapper vendored from `ed25519-bip32` `0.4.2`. Both are
  **build/dependency/toolchain changes** (new native artifact: `.so`/`.dylib`/`.klib`/xcframework),
  so they belong to a separate provisioning task, not this docs-only block. *No published Maven
  artifact exposing extended `sign` is known today* — the identus/`dev.allain` `bip32-ed25519`
  line (incl. 2.x) advertises HD **derivation** only and must be re-inspected at symbol level by
  the provisioning task before being assumed to add `sign`.
- **Apollo Ed25519-BIP32 signing.** Rejected as the backend: its `sign` is standard seed-based
  Ed25519 (§1), not extended.
- **`cardano-multiplatform-lib` / `cardano-serialization-lib`.** These *can* sign extended keys,
  but their distribution is not KMP-uniform (wasm/JS, JNI AAR for Android, C headers for iOS) and
  neither is a resolved artifact here; not adopted as the shipped KMP backend. Usable at most as a
  JVM/host **vector oracle**.
- **bloxbean `cardano-client-lib` / CSL as JVM-only vector oracles.** Consistent with ADR-0008's
  oracle posture: not shippable KMP dependencies (no iOS reach), but available on the JVM to
  cross-check the pinned KAT (§3) and to produce a full signed-transaction golden later (ADR-0015
  §6). Not needed to pass the KAT gate, since the reference-crate KAT below is authoritative.

**Fallback shape (ADR-0015 §4).** A per-platform `expect`/`actual` seam is still permitted, but no
resolved per-platform native library exports extended signing on any target, so the seam collapses
into the same provisioning task (a backend that exports `sign` must first exist per target).

### 3. Vector source — pinned extended-key KAT (vector requirement met)

**Primary KAT (authoritative, unambiguous, extended).** From the reference implementation cited by
CIP-3, `ed25519-bip32`, `src/tests.rs`, test `xprv_sign` / `verify_signature`:

- Source: `ed25519-bip32` crate, **version `0.4.2`** (immutable on crates.io), repo
  `https://github.com/typed-io/rust-ed25519-bip32` (formerly `input-output-hk/rust-ed25519-bip32`),
  file `src/tests.rs`. License: **MIT OR Apache-2.0**. Underlying primitive: `cryptoxide`
  `signature_extended` (no handwritten crypto).
- Extended signing key `XPrv` (96 bytes = 64-byte extended scalar `kL‖kR` + 32-byte chain code),
  the `D1_H0` constant:
  - extended scalar `kL‖kR` (64 bytes):
    `60d399da83ef80d8d4f8d223239efdc2b8fef387e1b5219137ffb4e8fbdea15adc9366b7d003af37c11396de9a83734e30e05e851efa32745c9cd7b42712c890`
  - chain code (32 bytes):
    `608763770eddf77248ab652984b21b849760d1da74a6f5bd633ce41adceef07a`
- Message (`MSG`): ASCII `"Hello World"` = `48656c6c6f20576f726c64` (11 bytes).
- Expected signature (`D1_H0_SIGNATURE`, 64 bytes):
  `90194d57cde4fdadd01eb7cf161780c277e129fc7135b97779a3268837e4cd2e9444b9bb91c0e84d23bba870df3c4bda91a110ef735638fa7a34ea2046d4be04`
- The verify test derives the public key via `XPrv::public()` (it is not separately hardcoded) and
  asserts `XPub::verify(MSG, sig) == true`.

This vector signs with the 64-byte extended scalar directly; a plain seed-based Ed25519
implementation cannot produce this signature from these bytes, so it satisfies the ADR-0015 §4/§6
"must be an extended-key KAT" vector requirement (and only that requirement). The message here is 11 bytes rather than a 32-byte
hash, but the extended-signing primitive is message-length-agnostic; a backend that reproduces
`D1_H0_SIGNATURE` is a correct extended-signing backend for the `bodyHash` use case.

**Secondary example (structural, matches our exact use pattern — reproduce-to-confirm, do not rely
until reproduced).** CIP-0100's test vector signs a **32-byte Blake2b-256 body hash** with a
64-byte extended signing key — structurally identical to `bodyHash = Blake2b-256(bodyCbor())`:

- Source: `cardano-foundation/CIPs`, `CIP-0100/test-vector.md`. License: **CC-BY-4.0** (CIPs repo).
- Extended signing key (hex, 64 bytes):
  `105d2ef2192150655a926bca9cccf5e2f6e496efa9580508192e1f4a790e6f53de06529129511d1cacb0664bcf04853fdc0055a47cc6d2c6d205127020760652`
- Public verification key (hex, 32 bytes):
  `7ea09a34aebb13c9841c71397b1cabfec5ddf950405293dee496cac2f437480a`
- Message (32-byte Blake2b-256 of the canonicalized body):
  `6d17e71c5793ed5945f58bf48e13bb1b3543187ab9c2afbd280a21afb4a90d35`
- Signature (64 bytes):
  `68078efeff90970d2320a2bb5021d1aea81bc4907bf33d54fd17989f020719f3f5c4da3dccf7aa61d51c1e6fececd95309c37e7eef331b199cd5f8e78992ea0d`

The CIP-100 page's "Ed25519 Online Tool" wording is ambiguous about extended-vs-plain, so this
vector is recorded as a **secondary, reproduce-to-confirm** example, not the gate KAT: Block 1.10b
must reproduce it with the chosen extended backend before relying on it. The primary gate KAT is
the reference-crate `xprv_sign` vector above, which is unambiguous.

**No invented vectors** were produced; both vectors are copied verbatim from cited, version/commit-
or license-pinned sources (ADR-0015 §6, test-integrity rule).

### 4. Target coverage plan

Once a backend that exports extended `sign` is provisioned (§2/§5), verification must cover:

- **JVM:** a `jvmTest` backend KAT reproducing `D1_H0_SIGNATURE` from `D1_H0` over `"Hello World"`,
  plus a labeled sign-then-verify self-consistency check.
- **Android real runtime (required before code is accepted, ADR-0015 §4/§6,
  `kotlin-tests-and-docs.mdc`):** the same KAT run as a `connectedAndroidDeviceTest` against the
  real native backend on a device/emulator — host tests alone do not satisfy the gate.
- **iOS:** compile+link at minimum (uniffi produces a Kotlin/Native binding + xcframework, matching
  the derivation backend's iOS integration); iOS **runtime** execution is recorded honestly as
  future work unless a simulator/device run is actually performed.
- **Per-platform seam:** only if a single all-target backend is not achievable; each `actual` must
  delegate to a verified backend, and any unsatisfiable target returns a typed
  "signing unavailable on this platform" error (ADR-0015 §4/§5) rather than shipping handwritten
  crypto.

### 5. Exact dependency to pin later (no Gradle edit in this block)

No published artifact can be pinned today because none exposes extended `sign`. The
backend-provisioning task must resolve to **one** of the following and then re-run §4 verification:

- **Preferred:** a uniffi wrapper artifact that exports `sign`/`verify` built from
  `ed25519-bip32 = "0.4.2"` (MIT OR Apache-2.0, `cryptoxide` primitive) — same mechanism as the
  resolved derivation backend. If project-owned, published under `org.sarmidev.kardano` coordinates
  (Maven coordinate **TBD by that task**); the exact wrapper commit and the `ed25519-bip32 0.4.2`
  pin must be recorded when vendored.
- **Alternative:** a future/forked `bip32-ed25519` wrapper version that adds `sign`, **only after**
  its native library is confirmed at symbol level (`nm`) to export a sign function and it is
  verified per §4.

Any of these is a Gradle/dependency change requiring its own explicit authorization (it is not
authorized by this docs-only block, per ADR-0015 §4 and the guardrail).

### 6. `AI_WORKING_AGREEMENT.md` reconciliation note

`docs/AI_WORKING_AGREEMENT.md` remains the canonical long-form working agreement and is unchanged
by this ADR's changes to date. The signing backend is now **adopted and verified** as the permanent,
project-owned `:crypto-signing-backend` module (§9i) — not merely blocked with a pinned KAT — so
ADR-0015 §4's backend condition is satisfied and Block 1.10b (the signing API implementation) is
unblocked. `docs/AI_WORKING_AGREEMENT.md` **still needs one reconciliation pass before the Block
1.10b `Signing` API lands**, to reflect that outcome (the backend is a real, vendored SDK
dependency, not a disposable spike) and to keep the agreement's signing-related wording aligned
with ADR-0015 §4 and this ADR. That reconciliation is a docs edit to schedule at the start of the
Block 1.10b signing-implementation task; it has not been done as part of this backend-adoption
block.

### 7. Backend-provisioning plan (recommended path; still blocking for 1.10b)

This section records the recommended way to obtain an extended-signing backend. It is a **plan
only** — it changes no code, pins no dependency, and **does not unblock Block 1.10b**. 1.10b remains
blocked until the spike below actually passes and its evidence is recorded (§7d).

**How the reference derivation backend reaches each target (packaging reference, from
resolved-artifact + upstream inspection).** The resolved `bip32-ed25519:1.8.8` is a uniffi wrapper
of `ed25519-bip32` that reaches JVM via JNA over a bundled `.dylib`/`.so`, Android via jniLibs
`.so` (4 ABIs), and iOS via a Kotlin/Native **cinterop over a bundled static `libuniffi_…​.a`**
(`bip32-ed25519-cinterop-ed25519_bip32_wrapper.klib`). Its upstream source is `hyperledger-identus/apollo`
`bip32-ed25519/` (Apache-2.0), whose Rust wrapper is the `wrapper/` crate inside the
`input-output-hk/rust-ed25519-bip32` submodule; the identus module drives the build with a custom
Cargo/cinterop Gradle setup. **It has *not* been verified that this upstream wrapper uses Gobley** —
identus-apollo is cited here only as a *packaging reference* for what a working JVM+Android+iOS
uniffi artifact looks like, not as evidence of any particular bindings generator.

**§7a. Provisioning options.**

- **Option A — wait for / adopt an upstream published wrapper exposing `sign`/`verify`.** Not
  available today: identus `1.8.8` and `dev.allain:bip32-ed25519:2.3.0` are derivation-only (§2). An
  upstream feature request / PR to add `sign` to the wrapper crate is worth filing in parallel, but
  its timeline is out of our control, so it is not the unblock path. If a future version ships
  `sign`, it must still be confirmed at symbol level (`nm`) and verified per §4.
- **Option B1 (recommended) — a project-owned scratch uniffi/KMP wrapper over
  `ed25519-bip32 = "0.4.2"`.** A small, disposable wrapper crate that adds a uniffi export for
  `sign(xprv, message) -> [u8;64]` and `verify(xpub, message, signature) -> bool` over the reference
  crate, built for KMP with the **recommended provisioning-spike toolchain: Gobley 0.3.7**
  (`dev.gobley.cargo` / `dev.gobley.uniffi`, published on Maven Central; the maintained successor to
  Trixnity's uniffi-kotlin-multiplatform-bindings; targets Android + JVM + Kotlin/Native). Gobley is
  a **recommendation to trial in the spike**, not an established project fact. Fastest route to a
  green JVM KAT; the spike then proves Android/iOS coverage.
- **Option B2 (fallback / packaging parity) — fork the reference wrapper and reuse an
  identus-apollo-style Cargo + cinterop build.** Fork `input-output-hk/rust-ed25519-bip32`, add the
  `sign`/`verify` uniffi exports to its `wrapper/` crate, and package JVM/Android/iOS with the same
  custom Cargo/cinterop build identus-apollo already uses. Higher build-plumbing cost, but mirrors a
  packaging shape already known to work for this exact crate/targets. Use if Gobley (B1) does not
  reach Android/iOS packaging parity.
- **Option C — CML / CSL / bloxbean.** Not a shippable KMP backend (not JVM+Android+iOS uniform);
  usable only as JVM-only vector oracles to cross-check the pinned KAT (§2/§3). Not the backend.

**§7b. Recommended unblock path.** Option B1. Build the backend as an **isolated, disposable scratch
module** (see the spike prompt) — **never** inside `:crypto`, `:tx`, `:wallet`, or `:shared`, and
without modifying any SDK Gradle file or adding any production dependency. The wrapper exposes
exactly:

- `sign(xprv, message) -> 64-byte signature` (extended-scalar signing), and
- `verify(xpub, message, signature) -> bool`.

**§7c. Spike target matrix and verification commands** (run by the spike, not here):

- **JVM KAT** — reproduce the ADR-0016 §3 primary vector (`D1_H0` extended scalar signs
  `"Hello World"` ⇒ `D1_H0_SIGNATURE`) in a scratch `jvmTest`.
- **Android real-runtime KAT (required)** — the same KAT as a `connectedAndroidDeviceTest` on a
  device/emulator; host tests alone do not count (ADR-0015 §4/§6, `kotlin-tests-and-docs.mdc`).
- **iOS compile/link (required)** — `compileKotlinIosArm64` + `linkDebugTestIosSimulatorArm64`; iOS
  runtime execution is honest future work unless a simulator/device run is actually performed.
- **Symbol proof (required)** — `nm` confirmation that each produced native artifact (JVM dylib/so,
  Android `.so` per ABI, iOS static `.a`) exports a `sign` uniffi function.

**§7d. Evidence required before Block 1.10b may start.** All of: JVM KAT reproduced; Android
real-runtime KAT reproduced; iOS compile/link green; `nm` symbol proof per target; and the exact
artifact recorded — crate version (`ed25519-bip32 0.4.2`) + wrapper commit + toolchain versions
(Gobley/UniFFI/Cargo) + licenses (crate MIT OR Apache-2.0; Gobley Apache-2.0/MIT). Until that
evidence exists and names the artifact, this ADR keeps 1.10b **BLOCKED**.

**§7e. Exact next prompt for the provisioning spike.** Verbatim, for the follow-up task:

> Kardano SDK — Block 1.10b signing-backend provisioning spike (isolated, disposable). Goal: prove
> a uniffi/KMP wrapper over `ed25519-bip32 = "0.4.2"` can expose extended
> `sign(xprv, message) -> [u8;64]` and `verify(xpub, message, signature) -> bool` across JVM +
> Android real runtime + iOS compile/link, and reproduce the ADR-0016 §3 primary KAT.
>
> Explicitly authorized in this spike: create ONE new, clearly disposable scratch Gradle module
> named `scratch-signing-backend` containing Gradle, Rust (Cargo), and Gobley
> (`dev.gobley.cargo` / `dev.gobley.uniffi` 0.3.7) files, plus a minimal Rust wrapper crate
> depending on `ed25519-bip32 0.4.2` with `#[uniffi::export]` `sign`/`verify` (no handwritten
> crypto — delegate to `XPrv::sign` / `XPub::verify`). Ask before pinning any version not already
> cited.
>
> Explicitly forbidden: do NOT modify or add signing to `:crypto`, `:tx`, `:wallet`, `:shared`, or
> any SDK API. The **only** permitted root-level Gradle edit is adding
> `include(":scratch-signing-backend")` to `settings.gradle.kts` — no other line, block, or
> reformatting in that file. Do NOT modify any SDK module's own Gradle file (`core/build.gradle.kts`,
> `crypto/build.gradle.kts`, `tx/build.gradle.kts`, `wallet/build.gradle.kts`,
> `shared/build.gradle.kts`, the provider modules' (`provider`, `provider-blockfrost`)
> `build.gradle.kts`, or any app module's `build.gradle.kts`). Do NOT add any production dependency
> to any SDK module. Every Gradle/Rust/Gobley build file for this experiment — the module's own
> `build.gradle.kts`, `Cargo.toml`, and any Gobley/cinterop config — lives inside
> `scratch-signing-backend/`, which is meant to be deleted after the spike.
>
> Verify and record: (1) JVM KAT reproducing `D1_H0` + `"Hello World"` ⇒ `D1_H0_SIGNATURE`;
> (2) Android `connectedAndroidDeviceTest` reproducing the same KAT; (3) `compileKotlinIosArm64` +
> `linkDebugTestIosSimulatorArm64`; (4) `nm` proof each native artifact exports a `sign` uniffi
> function. Record crate/wrapper/toolchain versions and licenses.
>
> Do NOT start `:crypto` signing (Block 1.10b) in this spike: 1.10b stays blocked until this spike
> passes and names the exact artifact/dependency to pin. If Gobley cannot reach Android/iOS
> packaging parity, fall back to the ADR-0016 §7a Option B2 packaging style and report that.

### 8. Provisioning spike results — all §7d verification legs PASS; adoption decision remains

The §7e spike, and a second Android-packaging follow-up, both ran in disposable, isolated
modules (Gradle/Rust/Gobley files only inside `scratch-signing-backend/`; Gradle/Kotlin/AGP files
only inside the sibling `scratch-signing-backend/android/`; the only root-level edits were the two
`include(...)` lines in `settings.gradle.kts`). Full evidence, commands, and versions/licenses are
recorded in `scratch-signing-backend/README.md`; this section summarizes the result against the
§7d bar.

**JVM: PASS.** `./gradlew :scratch-signing-backend:jvmTest` — 4/4 tests passed against the real
Gobley-generated JNA-backed bindings (not just a plain `cargo test`), including an exact
reproduction of the `D1_H0` + `"Hello World"` ⇒ `D1_H0_SIGNATURE` KAT from §3. `nm -gU` on the
produced `libsigning_backend_wrapper.dylib` confirms `_uniffi_signing_backend_wrapper_fn_func_sign`
(and `..._fn_func_verify`) are exported.

**iOS: PASS (compile/link, per §4's "compile/link at minimum").**
`compileKotlinIosArm64` and `linkDebugTestIosSimulatorArm64` both succeeded. `nm -gU` on both
produced static libraries (`aarch64-apple-ios` and `aarch64-apple-ios-sim`) confirms the same
`sign`/`verify` symbols are exported. iOS runtime execution was not performed (recorded honestly
as future work, matching `kotlin-tests-and-docs.mdc`'s iOS posture).

**Android: PASS, via a Gobley-Gradle-free packaging follow-up (not the Gradle/Gobley path
originally attempted).** The first spike round found Android **blocked at the Gradle/Gobley
layer, not the Rust/crate layer**: this repo pins AGP `9.0.1`, under which the classic
`com.android.library` plugin refuses to combine with `org.jetbrains.kotlin.multiplatform` (AGP 9
requires `com.android.kotlin.multiplatform.library` instead), and Gobley `0.3.7` does not support
that plugin (upstream-confirmed: `github.com/gobley/gobley/issues/153`, open). Downgrading this
repo's AGP pin remained out of scope. A follow-up task then found that even *adding* an
`androidLibrary {}` block to the same Gradle module as Gobley's `dev.gobley.cargo`/
`dev.gobley.uniffi` plugins fails configuration unconditionally
(`"Android JVM targets are added, but Android Gradle Plugin is not found."` — confirmed by reading
`gobley-gradle-cargo-0.3.7.jar`'s bytecode: Gobley probes for a classic AGP extension whenever any
`androidJvm`-platform Kotlin target exists in the module, regardless of whether Gobley is asked to
build anything for it). The fix was a **second, disposable sibling Gradle module**,
`scratch-signing-backend:android`, that applies **no** Gobley/Cargo/Rust Gradle plugin at all:

1. `cargo ndk` cross-compiled the already-proven wrapper crate for all four Android ABIs
   (arm64-v8a, armeabi-v7a, x86_64, x86) directly into `android/src/androidMain/jniLibs/`.
2. The Kotlin UniFFI bindings were generated **directly via the `gobley-uniffi-bindgen` CLI**
   (library mode, `kotlin_targets = ["android"]`) — the same tool version (`0.3.7`) Gobley's own
   Gradle plugin already used for JVM/iOS, just invoked by hand instead of through Gobley's
   Android Gradle integration — and committed as regular, pre-generated source under
   `android/src/androidMain/kotlin/`.
3. Both were wired into this SDK's normal AGP-9-compatible `androidLibrary {}` KMP DSL (the same
   shape `crypto/build.gradle.kts` uses for `bip32-ed25519:1.8.8`'s jniLibs) — the standard
   `src/androidMain/jniLibs/<abi>/` and `src/androidMain/kotlin/` source layout, auto-discovered by
   AGP with no extra configuration.
4. `llvm-nm -D` confirmed `uniffi_signing_backend_wrapper_fn_func_sign` (and `_verify`,
   `_derive_xpub`) exported in **every** ABI's `.so`.
5. `./gradlew :scratch-signing-backend:android:connectedAndroidDeviceTest` — **4/4 tests passed**,
   reproducing the `D1_H0` + `"Hello World"` ⇒ `D1_H0_SIGNATURE` KAT *through the packaged
   Kotlin/JNA UniFFI bindings*, on both a physical device (Android 15) and an emulator (Android
   7.0/API 24 — the SDK's own `minSdk`). This is the exact §7d Android requirement — the previous
   round's standalone-binary evidence (bypassing UniFFI/JNI entirely) did **not**, by itself,
   satisfy it; this does.

**§7d status: all four verification legs (JVM KAT, Android real-runtime KAT through the packaged
wrapper, iOS compile/link, `nm` symbol proof per target) now individually PASS, and the exact
spike artifact/toolchain is named in `scratch-signing-backend/README.md`.** This is a materially
different, narrower position than the first spike round's PARTIAL result. It is **not**, however,
the same as §7d being fully satisfied in the sense of unblocking 1.10b: the passing wrapper exists
only inside two disposable, to-be-deleted scratch modules (`scratch-signing-backend` and
`scratch-signing-backend:android`), never depended on by any SDK module. Turning this into a real
backend — vendoring the wrapper crate permanently into a non-disposable module/coordinate (e.g.
under `org.sarmidev.kardano`), or adopting a published equivalent, and re-running this same
verification against that real dependency — is a Gradle/dependency change that ADR-0016 §5
explicitly requires its own separate authorization for. **That adoption/pinning decision, not
further technical verification, is now the only remaining gap before Block 1.10b may start.**

### 9. Backend adoption/pinning plan (recommended path to unblock 1.10b)

This section records the concrete plan to turn the proven-but-disposable spike (§8) into a real,
permanently-vendored SDK backend. Like §7, it is a **plan only**: it changes no SDK signing code
and, by itself, does **not** unblock Block 1.10b. 1.10b unblocks only after the adoption block below
actually lands the real module and re-runs §7d verification against it (§9f).

**§9a. What is already proven (do not re-litigate).** §8 established, on all four §7d legs, that the
mechanism works: a project-owned Rust wrapper crate over `ed25519-bip32 0.4.2` (delegating to
`XPrv::sign`/`XPub::verify`, no handwritten crypto), exposed via UniFFI, reaches JVM (JNA over a
cdylib), Android (jniLibs `.so` on 4 ABIs + JNA), and iOS (Kotlin/Native cinterop over a static
`.a`). The adoption block reuses that exact wrapper source and the pinned crate/toolchain versions
recorded in `scratch-signing-backend/README.md`; it changes only *where the artifact lives and how
it is named/pinned*, not the cryptographic mechanism.

**§9b. Adoption options.**

- **Option R1 (recommended) — one permanent, in-repo, project-owned module that ships committed
  prebuilt native artifacts + committed pre-generated UniFFI bindings, applying no
  Rust/Cargo/Gobley Gradle plugin.** A single `androidLibrary {} + jvm() + iosArm64() +
  iosSimulatorArm64()` module. There is no Gobley⇄AGP-9 conflict because a Gobley-free module never
  probes for the classic AGP extension (the §8 conflict came *only* from Gobley's probe — already
  proven Gobley-free-and-green by `:scratch-signing-backend:android`). No Rust/NDK toolchain is
  forced into SDK builds or CI, and consumers of the SDK never need Rust. Native artifacts +
  bindings are regenerated offline via the pinned toolchain (documented step), reviewed, and
  committed — the same consumption shape the SDK already uses for `bip32-ed25519:1.8.8` (a published
  artifact that bundles native libs + bindings), just vendored in-repo. Trade-off: binaries live in
  git, and the JVM cdylib is per-host-OS/arch (commit at least the CI/dev host targets — see §9e and
  §9 risks).
- **Option R2 (fallback) — keep Gobley building JVM/iOS from source at build time, plus a
  committed-artifact Android sibling (exactly the §8 two-module split, promoted to permanent
  coordinates).** Forces a pinned Rust toolchain + NDK into every SDK build/CI and keeps a
  two-module split for a shipped component; use only if committing binaries is rejected.
- **Option R3 (eventual clean state, not this block) — publish the wrapper as a Maven artifact
  under `org.sarmidev.kardano` and consume it exactly like `bip32-ed25519:1.8.8`.** Needs
  publishing/CI infrastructure; out of scope for a small first adoption block, but R1's committed
  layout is its natural precursor.

Recommendation: **R1, recreated cleanly (not `git mv`) as a permanent module.** The spike files are
saturated with "disposable/scratch/spike" naming and comments that would be incorrect in a shipped
module. Reuse the proven Rust wrapper source, the `uniffi-bindgen` config, and the verbatim test
vectors; regenerate the artifacts; then delete both scratch modules.

**§9c. Exact module/coordinate shape.**

- New Gradle module `:crypto-signing-backend`. A **dedicated module** (rather than a `:crypto`
  sub-package) is justified under ADR-0011's "real ownership/packaging pressure" exception: it bears
  its own native artifacts, jniLibs, iOS cinterop, a JNA dependency, and generated bindings, and
  must not entangle `:crypto`'s existing lazysodium/JNA packaging workarounds
  (`crypto/build.gradle.kts` already excludes duplicated JNA license resources to avoid an
  AGP duplicate-class clash).
- Namespace / package: `org.sarmidev.kardano.crypto.signing.backend`; generated UniFFI bindings
  under `...signing.backend.internal` (the `internal.*` platform-seam convention). No public signing
  API here — the module exposes only the thin `sign`/`verify` seam; `:crypto`'s `Signing` API is
  Block 1.10b, not this block.
- Vendored Rust crate renamed from `signing-backend-wrapper` to a non-scratch name (e.g.
  `kardano-ed25519-bip32-signing`), `publish = false`, pinned `ed25519-bip32 = "0.4.2"`, with
  `Cargo.lock` committed.
- `:crypto` gains a dependency on `:crypto-signing-backend` only in Block 1.10b (**not** in the
  adoption block).

**§9d. Gradle files changed, and why (adoption block only).**

- `settings.gradle.kts` — remove the two `include(":scratch-signing-backend")` /
  `include(":scratch-signing-backend:android")` lines; add `include(":crypto-signing-backend")`.
- `crypto-signing-backend/build.gradle.kts` (new) — `kotlinMultiplatform` +
  `androidMultiplatformLibrary` (+ `kotlin("plugin.atomicfu")` for the bindings' handle-map
  counter); `jvm()` + `iosArm64()` + `iosSimulatorArm64()` + `androidLibrary {}` with
  `withDeviceTest {}`; JNA `@aar` on `androidMain`, JNA jar on `jvmMain`; jniLibs + iOS cinterop
  wiring. Uses the version catalog, matching `crypto/build.gradle.kts`'s shape.
- `gradle/libs.versions.toml` — add the `atomicfu` version + plugin alias (JNA/AGP/Kotlin already
  present). This is the one pinned change the whole adoption is authorized for.
- **Not changed:** `:crypto`/`:tx`/`:wallet`/`:shared`/`:core`/provider/app `build.gradle.kts`
  (those belong to Block 1.10b, kept out of this block to keep it small and signing-code-free).

**§9e. Artifacts — commit vs. task-generate.**

- **Commit** (reviewed, provenance-documented, regenerable offline from the pinned crate +
  toolchain): Android `.so` × 4 ABIs; iOS static `.a` × 2 (device + simulator) + the cinterop
  `.def`; the JVM cdylib for each CI/dev host target; the generated
  `signing_backend_wrapper.{common,jvm,android}.kt` bindings; `Cargo.lock`.
- **Never commit / never build in Gradle** (under R1): the Rust `target/` directory (gitignored);
  no Rust/Cargo/Gobley Gradle task runs in the module.
- Regeneration commands and exact toolchain versions (Rust, `cargo-ndk`, NDK,
  `gobley-uniffi-bindgen`) are documented in the module README, copied from the spike README's
  "Versions and licenses" and reproduce steps.

**§9f. Verification — re-run every §7d leg against the real module.**

- `./gradlew :crypto-signing-backend:jvmTest` — JVM KAT (`D1_H0` + `"Hello World"` ⇒
  `D1_H0_SIGNATURE`).
- `./gradlew :crypto-signing-backend:connectedAndroidDeviceTest` — Android real-runtime KAT through
  the packaged wrapper.
- `./gradlew :crypto-signing-backend:compileKotlinIosArm64` +
  `:crypto-signing-backend:linkDebugTestIosSimulatorArm64` — iOS compile/link.
- `nm` / `llvm-nm` symbol proof (`..._fn_func_sign`) on every committed native artifact.
- Banned-word/claim scan on touched docs; `git diff` review confirming no
  `:crypto`/`:tx`/`:wallet`/`:shared`/`:core`/provider/app change; both scratch modules deleted.
- Record the exact adopted artifact (crate `ed25519-bip32 0.4.2` + wrapper commit + toolchain
  versions + licenses) in the module README and update this ADR §9 to "adopted, verified".

**§9g. 1.10b stays blocked until §9f passes.** This planning task pins no dependency and creates no
module; it only records the plan. Block 1.10b unblocks only after the adoption block lands
`:crypto-signing-backend` and every §7d/§9f leg passes against it and names the exact artifact.

**§9 risks / unknowns (state explicitly).**

- **JVM cdylib is per-host-OS/arch.** Under R1 the committed JVM `.dylib`/`.so`/`.dll` only covers
  the hosts whose binary is committed; a JVM host without a committed binary fails to load. Mitigate
  by committing at least the CI host + common dev host targets and documenting the limitation, or
  fall back to R2 (Gobley builds the host cdylib at build time), or R3 (published multi-host
  artifact). This is the main reason R1 is proposed as a *first* step, not the final state.
- **Committing native binaries in git** (provenance, review, repo size). Precedent exists (the spike
  already commits Android `.so`s), and every artifact is regenerable from the pinned crate +
  toolchain, but a reviewer must accept binary blobs; R3 (publishing) removes them later.
- **Toolchain reproducibility.** Byte-identical rebuilds require the exact pinned Rust/`cargo-ndk`/
  NDK/`gobley-uniffi-bindgen` versions; these are recorded, but drift is a maintenance risk to note.
- **iOS remains compile/link-only** (no simulator/device runtime execution), unchanged from §8 and
  consistent with the repo's iOS posture; on-device iOS runtime stays honest future work.

**§9h. Exact next prompt for the adoption block.** Verbatim, for the follow-up task:

> Kardano SDK — Block 1.10b backend adoption/pinning (not signing implementation). Goal: convert the
> proven-but-disposable `scratch-signing-backend` / `scratch-signing-backend:android` spike (ADR-0016
> §8) into ONE permanent, project-owned SDK backend module, `:crypto-signing-backend`, and re-run
> every ADR-0016 §7d verification leg against it (ADR-0016 §9, Option R1). Do NOT implement
> `:crypto`/`:tx`/`:wallet` signing.
>
> Explicitly authorized: create the new permanent module `:crypto-signing-backend` (namespace
> `org.sarmidev.kardano.crypto.signing.backend`; generated bindings under `...backend.internal`),
> reusing the spike's exact Rust wrapper source (delegating to `ed25519_bip32::XPrv::sign` /
> `XPub::verify`, no handwritten crypto), the `uniffi-bindgen` config, and the verbatim ADR-0016 §3
> `D1_H0` test vectors. Apply Option R1: NO Rust/Cargo/Gobley Gradle plugin; commit the prebuilt
> native artifacts (Android `.so` ×4 ABIs, iOS static `.a` ×2 + cinterop `.def`, the JVM cdylib for
> the CI/dev host targets) and the pre-generated `signing_backend_wrapper.{common,jvm,android}.kt`
> bindings as reviewed source, regenerable offline from the pinned toolchain (document the exact
> commands + versions in the module README). Rename the crate off "scratch"/"wrapper" naming (e.g.
> `kardano-ed25519-bip32-signing`, `publish = false`, pinned `ed25519-bip32 = "0.4.2"`, commit
> `Cargo.lock`). The permitted Gradle edits are exactly: (a) `settings.gradle.kts` — remove the two
> `scratch-signing-backend` includes and add `include(":crypto-signing-backend")`; (b) the new
> `crypto-signing-backend/build.gradle.kts` (mirror `crypto/build.gradle.kts`'s
> `kotlinMultiplatform` + `androidMultiplatformLibrary` + JNA `@aar`/jar + cinterop shape, plus
> `kotlin("plugin.atomicfu")`); (c) `gradle/libs.versions.toml` — add the `atomicfu` version +
> plugin alias only. Delete both scratch modules (`scratch-signing-backend/` and its `android/`
> sibling) in this same change. Ask before pinning any version not already recorded in
> `scratch-signing-backend/README.md`.
>
> Explicitly forbidden: do NOT add signing to or otherwise modify `:crypto`, `:tx`, `:wallet`,
> `:shared`, `:core`, the provider modules, or any app module, or their `build.gradle.kts` files
> (the `:crypto` → `:crypto-signing-backend` dependency and the `Signing` API are Block 1.10b, a
> later block). Do NOT downgrade this repo's AGP `9.0.1` pin. Do NOT use plain RFC-8032 seed-based
> Ed25519 or write any handwritten crypto. No mainnet, no real mnemonics/private keys/funds, no
> general-purpose wallet signing, no readiness/audit/external-review claims.
>
> Verify and record (all against the real module): (1) `./gradlew :crypto-signing-backend:jvmTest`
> reproducing `D1_H0` + `"Hello World"` ⇒ `D1_H0_SIGNATURE`; (2)
> `./gradlew :crypto-signing-backend:connectedAndroidDeviceTest` reproducing the same KAT through the
> packaged Kotlin/JNA bindings on a device/emulator; (3)
> `./gradlew :crypto-signing-backend:compileKotlinIosArm64` +
> `:crypto-signing-backend:linkDebugTestIosSimulatorArm64`; (4) `nm`/`llvm-nm` proof each committed
> native artifact exports `..._fn_func_sign`. Then update ADR-0016 §9 to "adopted, verified", naming
> the exact artifact/toolchain/licenses, and run a banned-word/claim scan + `git diff` review
> confirming no SDK signing module changed. Block 1.10b stays blocked until every leg above passes
> against `:crypto-signing-backend` and the exact artifact is recorded.

**§9i. Adoption result — adopted, verified (2026-07-13).** The §9h adoption block was executed. The
disposable spike is now the permanent, project-owned module **`:crypto-signing-backend`** (Gradle
path `:crypto-signing-backend`, namespace `org.sarmidev.kardano.crypto.signing.backend`, generated
seam under `...backend.internal`), landed as **Option R1** (no Rust/Cargo/Gobley Gradle plugin;
committed native artifacts + pre-generated UniFFI bindings). The `scratch-signing-backend` /
`scratch-signing-backend:android` modules and their `settings.gradle.kts` includes are deleted.

- **Crate.** Renamed to `kardano-ed25519-bip32-signing` (`publish = false`), `ed25519-bip32 = "0.4.2"`
  pinned, `Cargo.lock` committed; the wrapper delegates to `ed25519_bip32::XPrv::sign` /
  `XPub::verify` (no handwritten crypto). Resolved pins: `ed25519-bip32 0.4.2`, `cryptoxide 0.5.3`,
  `uniffi 0.29.5`. Built offline with `rustc/cargo 1.97.0`, `cargo-ndk 4.1.2`, NDK
  `27.2.12479018`, and `gobley-uniffi-bindgen 0.3.7` (binding generation only). Licenses:
  `ed25519-bip32`/`cryptoxide` MIT OR Apache-2.0, `uniffi` MPL-2.0, `gobley-uniffi-bindgen`
  Apache-2.0 OR MIT (full table in the module `README.md`).
- **Committed artifacts (8) + bindings.** JVM cdylibs `darwin-aarch64` + `darwin-x86-64`; Android
  `.so` ×4 ABIs (`arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86`); iOS static `.a` ×2
  (`iosArm64`, `iosSimulatorArm64`) + hand-written cinterop `.def`/header; pre-generated
  `kardano_ed25519_bip32_signing.{common,jvm,native,android}.kt` under `...internal`.
- **Gradle footprint (exactly as authorized).** `settings.gradle.kts` (swap scratch includes for
  `include(":crypto-signing-backend")`); new `crypto-signing-backend/build.gradle.kts`
  (`kotlinMultiplatform` + `androidMultiplatformLibrary` + JVM + `iosArm64`/`iosSimulatorArm64`
  cinterop + JNA jar/`@aar` + `kotlin("plugin.atomicfu")`); `gradle/libs.versions.toml` (added the
  `atomicfu = "0.26.1"` version, `kotlinx-atomicfu` library, and `atomicfu` plugin alias only). No
  other SDK module or its `build.gradle.kts` was touched; no `:crypto`→backend dependency was added.
- **Verification re-run against the real module — all pass:**
  - `./gradlew :crypto-signing-backend:jvmTest` — **4/4** (macOS arm64), reproduces `D1_H0` +
    `"Hello World"` ⇒ `D1_H0_SIGNATURE`, plus sign-then-verify, tampered-signature rejection,
    wrong-length-xprv rejection.
  - `./gradlew :crypto-signing-backend:connectedAndroidDeviceTest` — **4/4 on `SM-A356B`
    (Android 15, physical) + 4/4 on `kardano_api24` (API 24 emulator)**, through the packaged
    Kotlin/JNA bindings + committed jniLibs.
  - `./gradlew :crypto-signing-backend:compileKotlinIosArm64` + `:linkDebugTestIosSimulatorArm64` —
    both `BUILD SUCCESSFUL`; a minimal `iosTest` forces the simulator test binary to link the
    committed `.a` (real symbol resolution). On-simulator/device *execution* remains honest future
    work.
  - Symbol proof — `nm -gU` (macOS/iOS) / `llvm-nm -D` (Android) confirm
    `kardano_ed25519_bip32_signing_fn_func_sign` is exported on all 8 committed artifacts.
- **JVM host coverage (scoped, per §9e critical check).** Host = macOS arm64; **no CI exists** in
  this repo. Only the macOS cdylibs are committed: `darwin-aarch64` is runtime-verified via
  `jvmTest`; `darwin-x86-64` is cross-built and **not** runtime-verified here; Linux/Windows JVM
  hosts are **not** covered and are explicit future work (Option R3, publishing). R1 was not
  narrowed further because there is no CI host left uncovered; the module does not claim general
  cross-host JVM verification.

**Result: ADR-0015 §4's backend condition is satisfied and Block 1.10b (the signing API
implementation) is unblocked.** The `Signing` API, `:crypto`→`:crypto-signing-backend` wiring,
witness/transaction assembly, and wallet orchestration remain the next block — none was implemented
here.

---

## Consequences

- **Block 1.10b is unblocked** (backend adopted + verified, §9i). This adoption block itself added
  no signing code and no `:crypto`→backend dependency; the only Gradle footprint is the permanent
  `:crypto-signing-backend` module + its three authorized wiring edits (§9i). The next task is the
  Block 1.10b signing implementation (`Signing` API, `:crypto` wiring, witness/transaction
  assembly) — not further backend verification.
- The extended-key KAT is now pinned (§3) **and reproduced against the real
  `:crypto-signing-backend` module**: real JVM bindings, real Android on-device execution through
  the packaged wrapper (physical + emulator), and iOS compile/link with per-target symbol proof
  (§9i). The target-coverage plan (§4) is done against the permanent module — JVM host coverage is
  macOS-only by design (§9e/§9i).
- ADR-0015 §4/§6 are satisfied on both the vector requirement and the backend requirement; §4's
  backend condition is now **met** by the vendored, pinned `:crypto-signing-backend` module (§9i).
- The reference-crate provenance also confirms the current derivation backend and a future signing
  backend can share one Rust crate (`ed25519-bip32`) exposed via one uniffi mechanism.
- Gobley `0.3.7` is confirmed as a working JVM+iOS uniffi/KMP toolchain for this crate in this repo
  (§8); it is confirmed **not** to reach Android under this repo's AGP 9.0.1 pin today (upstream
  `gobley/gobley#153`) — but the same `gobley-uniffi-bindgen` CLI, invoked directly rather than
  through Gobley's Android Gradle plugin, does reach Android (§8).

## Non-goals

- No signing implementation; no witness/transaction assembly; no `:shared` checkpoint code.
- No signing-related change to the existing SDK modules (`:crypto`, `:tx`, `:wallet`, `:shared`,
  `:core`, providers, apps) or their `build.gradle.kts`, and no `:crypto`→`:crypto-signing-backend`
  dependency. The §9i adoption added exactly one new module (`:crypto-signing-backend`) plus its
  three authorized wiring edits (`settings.gradle.kts`, the new module `build.gradle.kts`, and the
  `atomicfu` entries in `gradle/libs.versions.toml`); the backend crate is pinned there (Option R1),
  not in any existing SDK module. The `Signing` API and `:crypto` wiring remain the separate Block
  1.10b decision.
- No mainnet; no real mnemonics, private keys, or funds; no native assets, scripts, metadata,
  multisig, or general-purpose/user-supplied wallet signing.
- No handwritten cryptography; no acceptance of a plain (seed-based) Ed25519 vector as the gate KAT.
- No readiness, external-review, or audit claim.

## Follow-up work

- **Backend adoption/pinning decision — DONE (§9i).** The disposable spike is now the permanent,
  vendored, pinned `:crypto-signing-backend` module (Option R1); all four verification legs pass
  against it and the exact artifact/toolchain/licenses are recorded (§9i + module `README.md`).
- **Reconcile `docs/AI_WORKING_AGREEMENT.md`** at the start of 1.10b (§6) — still pending; the
  signing-backend guardrail must be updated before the 1.10b signing API lands.
- **Block 1.10b** implements ADR-0015 §1/§3/§5/§6 (the `Signing` API,
  `:crypto`→`:crypto-signing-backend` wiring, witness set + signed-transaction assembly). Now
  unblocked (§9i); not started in this adoption block.
- **Block 1.10c** wires the `:shared` "Signed Transaction (not submitted)" checkpoint.
- ADR-0004 (crypto strategy), ADR-0009/ADR-0010 (derivation/projection + key-material rules), and
  ADR-0015 (transaction signing) remain the governing decisions this gate builds on; this ADR does
  not supersede them.
