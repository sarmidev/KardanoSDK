# ADR-0010: Key-Derivation Backend Swap And Public-Key Projection (Block 1.6c Follow-Up)

| Field   | Value                                             |
|---------|---------------------------------------------------|
| Status  | **Accepted** — dependency swap and public-key projection are implemented and verified on JVM, iOS (compile/link), and Android (real-runtime execution, API 24/35/36) for every target; no open blocker remains from this ADR |
| Scope   | Phase 1 Block 1.6c-follow-up + 1.6c-follow-up-2 — closes the two blockers ADR-0009 §Block 1.6c gate result opened, then closes the Android-projection sub-blocker this ADR opened |
| Phase   | Phase 1 (follow-up to Block 1.6c)                 |
| Updated | 2026-07-12                                        |

---

## Context

ADR-0009 §Block 1.6c gate result narrowed Block 1.6c to private derivation only and left two
items open:

1. **Blocker 1 — no public-key-from-private-key primitive.** The pinned
   `dev.allain:bip32-ed25519:2.3.0` backend exposes only private→private and
   already-public→public child derivation; nothing projects a private/extended key to its
   public key. `ExtendedPublicKey` and `KeyDerivation.publicKey(...)` were deferred.
2. **Blocker 2 — Android derivation blocked.** The published `bip32-ed25519-android-2.3.0`
   AAR ships no native library (`unzip -l` showed no `jni/<abi>/*.so`), so calling the
   backend threw a confirmed `UnsatisfiedLinkError` under `:crypto:testAndroidHostTest`. No
   Android emulator or device was available in that verification environment, so this was a
   confirmed host-JVM/artifact-inspection failure, not an on-device-confirmed verdict.

This ADR records a gated follow-up investigation (evidence gates, then execution) that closes
Blocker 2 outright and closes Blocker 1 for JVM/iOS while opening a narrower, Android-specific
sub-blocker in its place. No handwritten cryptographic algorithm is introduced anywhere in
this ADR (ADR-0004 §3.1); both changes below delegate to third-party native libraries.

### Method

An Android runtime was not available in the initial verification environment either. Rather
than accept an artifact-only verdict for the second time, a local Android emulator (API 36,
`arm64-v8a` system image) was provisioned in the working environment specifically so the
derivation and projection backends could be exercised on real Android runtime — `adb devices`
and `:crypto:connectedAndroidDeviceTest` executions below are against that emulator, not the
host JVM. Candidate backends were evaluated only from resolved-artifact evidence (`javap`,
`unzip -l`, `nm`/`strings` symbol inspection, and live probe calls/tests), per the same
discipline ADR-0008/ADR-0009 already established — no candidate is accepted or rejected from
documentation claims.

---

## Decision

### 1. Derivation backend: swap to `org.hyperledger.identus:bip32-ed25519:1.8.8` — resolves Blocker 2

`org.hyperledger.identus:bip32-ed25519` is the upstream coordinate for the same uniffi Kotlin
wrapper `dev.allain:bip32-ed25519` republishes (both wrap the IOG Rust `ed25519-bip32` crate;
identical `uniffi.ed25519_bip32_wrapper` package, identical `deriveBytes`/`deriveBytesPub`/
`fromNonextended` function signatures — confirmed by `javap`, so no adapter code changed, only
`gradle/libs.versions.toml`'s module coordinate and version). Its `bip32-ed25519-android` AAR
**does** ship the native `jni/<abi>/*.so` the `dev.allain` republish omitted.

**Verification — real Android runtime, not host JVM.** A test-only `androidDeviceTest` source
set was added to `:crypto` (`withDeviceTest {}` in `crypto/build.gradle.kts`,
`KeyDerivationDeviceTest.kt`), exercising the same two cited
`IntersectMBO/cardano-addresses` golden vectors ADR-0009 §4 already pins
(`root_xsk` and `addr_xsk` for `m/1852'/1815'/0'/0/0`).
`./gradlew :crypto:connectedAndroidDeviceTest`, run against the provisioned emulator, **passed
both tests** — real on-device native-library loading and derivation, superseding the earlier
host-JVM-only `UnsatisfiedLinkError` finding. `:crypto:jvmTest` and
`:crypto:compileKotlinIosSimulatorArm64`/`compileKotlinIosArm64` were re-run with the swapped
coordinate and are unaffected (same wrapper API, same byte layouts).

**Outcome: Blocker 2 is resolved, not merely downgraded to a lower risk.**
`KeyDerivation.derivePrivate` now has a confirmed-working Android path. Android derivation is
no longer blocked for this dependency.

### 2. Public-key projection: `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings:0.9.5` — resolves Blocker 1 for JVM/iOS; opens an Android-specific projection blocker

> **Historical: this was the 1.6c-follow-up (first follow-up) result.** The Android-specific
> blocker this section describes is closed by §2a below (1.6c-follow-up-2). This section is
> kept as the accurate record of what was verified at that point; it does not describe the
> current state.

The extended private key's left 32-byte scalar `kL` (already clamped/tweaked by the CIP-3/
Ed25519-BIP32 derivation chain) is projected to its public key via libsodium's
`crypto_scalarmult_ed25519_base_noclamp(kL)` — the standard Ed25519 "scalar × base point,
without re-clamping" operation, delegated entirely to libsodium (no handwritten curve or
scalar math). The unchanged chain code is carried through unmodified, matching the
`addr_xvk`/`addr_xsk` chain-code-sharing structure the cited goldens already exhibit.

**Verification — JVM: PASS against the cited `addr_xvk` vectors.** The projected public key,
concatenated with the (unchanged) chain code, byte-for-byte matches all three
`IntersectMBO/cardano-addresses` golden `addr_xvk` values ADR-0009 §4 already pins and 1.6c
left unused (`m/1852'/1815'/0'/0/{0,1,1442}`) — the same commit, same license, no new vector
invented. This is exercised by `KeyDerivationVectorsTest`'s
`publicKey_role0Index{0,1,1442}_matchesGoldenAddrXvk{0,1,1442}` tests.

**Verification — Android runtime: FAIL, with a confirmed root cause.** On the same provisioned
emulator, calling the projection backend throws `UnsatisfiedLinkError: undefined symbol:
crypto_scalarmult_ed25519_base_noclamp`. Static inspection (`nm`/`strings`) of the native
libraries bundled in this library's published artifacts confirms the root cause: the **Android**
`.so` exports only `crypto_sign_ed25519_*` symbols — no `crypto_core_ed25519_*` or
`crypto_scalarmult_ed25519_*` symbol exists in it at all — while the **JVM** artifact's bundled
macOS dylib exports the full Ed25519 low-level set, including
`crypto_scalarmult_ed25519_base_noclamp` (also present in this JVM artifact's dylib on other
architectures/platforms it bundles). **This is a real gap in this specific published Android
native build, not a math error, an API-usage error, or a wiring error** — the identical Kotlin
call that returns the exact cited golden bytes on JVM cannot even load its native symbol on
Android.

**Decision (reported to and explicitly approved by the project owner), given the JVM/Android
split above:**

- **Implement `ExtendedPublicKey` and `KeyDerivation.publicKey(key)` now, for JVM and iOS.**
  The projection math and API shape are proven correct (JVM golden-vector match); withholding
  them from JVM/iOS callers to wait for an Android-capable build of the same library would
  block real, working functionality for no benefit.
- **At this point, Android public-key projection was treated as a separate, explicit, open
  blocker — not silently degraded and not implemented by any other backend in this ADR.**
  (Superseded by §2a below, which implements a working Android backend; kept here as the
  historical record of the decision taken at this stage.) `KeyDerivation.publicKey` is
  implemented via a per-platform seam (`internal expect fun projectPublicKey(kL): 
  KardanoResult<ByteArray, KeyDerivationError>`, mirroring the existing PBKDF2 platform-seam
  pattern from ADR-0009's Block 1.6b gate result). At this stage, the `androidMain` actual did
  **not** attempt the native call at all (there was no libsodium dependency in `androidMain`
  yet); it returned the new `KeyDerivationError.PublicKeyProjectionUnavailable` immediately.
  This was verified on the same real Android runtime via the now-removed
  `PublicKeyUnavailableDeviceTest` (`:crypto:connectedAndroidDeviceTest`): calling
  `KeyDerivation.publicKey(...)` on-device returned the typed error and did not crash, throw,
  or hang.
- **`KeyDerivation.derivePrivate` was unaffected by this blocker and worked on Android
  already** (§1) — the Android gap at this stage was scoped exactly to public-key projection,
  not to key derivation in general. (As of §2a, both now work on Android; this bullet is kept
  to explain why the two were never conflated while the projection gap was still open.)

### 2a. Android public-key projection resolution (Block 1.6c-follow-up-2): `com.goterl:lazysodium-android:5.2.0`

The Android-specific blocker §2 opened is now closed. `com.goterl:lazysodium-android` (MPL-2.0)
bundles a **fuller** libsodium `.so` build than the Ionspin/Android build §2 found lacking:
static inspection (`nm -D`, the dynamic/exported symbol table, not just any local symbol)
confirms `crypto_scalarmult_ed25519_base_noclamp` is exported as a global symbol on **all four**
bundled ABIs (`arm64-v8a`, `armeabi-v7a`, `x86`, `x86_64`). Its own `Sodium`/`SodiumAndroid` JNA
interfaces do not declare that function anywhere in the library's Java/Kotlin API (checked by
disassembling `classes.jar` with `javap` across every class), so the `androidMain`
`projectPublicKey` actual defines a minimal JNA `Library` interface for the one native symbol it
needs, loaded via `Native.load("sodium", ...)` after `SodiumAndroid()` triggers the library's
normal native-load path — the same "define a minimal binding to a maintained native library"
pattern already used for the derivation backend, not a hand-written re-implementation of
anything libsodium already does.

**Verification — real Android runtime, three independent runtimes.** Unlike §1/§2's single
provisioned emulator, this gate ran on three real Android runtimes simultaneously available in
the working environment: a physical device (`SM-A356B`, Android 15, **API 35**), the
already-provisioned API 36 emulator (§1), and a newly provisioned **API 24** emulator
(`system-images;android-24;google_apis;arm64-v8a` — Google publishes an `arm64-v8a` image for
API 24, which runs natively on Apple Silicon), added specifically because this project's
`minSdk = 24` and a higher-API-only verification would not have covered it. The lead candidate's
own AAR manifest declares `minSdkVersion="21"`, imposing no floor above 24.

`PublicKeyProjectionDeviceTest` (via `:crypto:connectedAndroidDeviceTest`) derives
`m/1852'/1815'/0'/0/0`, calls `KeyDerivation.publicKey(...)`, and asserts both (a) the result
matches the cited `addr_xvk0` golden byte-for-byte, and (b) `Hashing.blake2b224` of the projected
public key matches the CIP-19 payment credential pinned in `HashingVectorsTest` — cross-linking
two independently cited sources for the same key, per ADR-0009 §4. **Both assertions passed on
all three runtimes** (JUnit XML: `tests="4" failures="0" errors="0"` per device, covering this
test plus the unaffected `KeyDerivationDeviceTest`). `:crypto:jvmTest`,
`:crypto:testAndroidHostTest`, and `:crypto:compileKotlinIosSimulatorArm64`/
`compileKotlinIosArm64` were re-run and remain green — the Android-only dependency addition does
not affect JVM/iOS, which keep the Ionspin backend from §2 unchanged.

**Outcome: the Android public-key-projection blocker is resolved, not merely narrowed.**
`KeyDerivation.publicKey` now returns `Ok` and reproduces the cited goldens on Android exactly as
it already did on JVM and iOS (compile/link). `KeyDerivationError.PublicKeyProjectionUnavailable`
remains declared in the public API (removing a sealed-interface member is itself a breaking
change) but no current target returns it; it is reserved for a platform without a projection
backend added in the future.

A minor packaging note, not a cryptographic concern: `net.java.dev.jna:jna` publishes both a
`.jar` and an `.aar` artifact for the same coordinate, and this project already depends on it
transitively (via the derivation backend, §1). Depending on it from two source sets that each
resolved a different artifact type triggered AGP's duplicate-class check on the merged
device-test APK. Fixed by excluding JNA from the projection candidate's own dependency metadata
and depending on it explicitly with a single, pinned, `@aar`-typed coordinate instead, plus a
`packaging { resources.excludes += [...] }` block for a duplicated license-notice resource file
this produces regardless. This is a Gradle/AGP artifact-resolution detail with no effect on which
native code loads or runs.

### 3. Key-material handling for the new type and seam

`ExtendedPublicKey` follows the same rules ADR-0009 §7 already established: private
constructor, defensive copies on construction and on its one accessor
(`publicKeyBytes(): ByteArray`, a copy — the public key is not secret, but the accessor still
never exposes the backing array), a structural `toString()`, and a best-effort `clear()`. The
JVM/iOS `projectPublicKey` actuals wipe every intermediate native-call buffer they allocate
(the `UByteArray` copy of `kL` made for the native call, and the native call's own `UByteArray`
result) immediately after copying the needed bytes out — not just the `ByteArray` handles the
common-code caller already wipes — so no unwiped scalar or projected-key copy is left for the
garbage collector beyond what the native library itself may retain internally (unchanged,
pre-existing caveat, same as every other delegated-crypto call in this repository). The Android
actual (§2a) passes `kL` directly to the JNA call (no intermediate type-conversion copy is
needed, unlike JVM/iOS's `UByteArray` conversion) and wipes its own output buffer on any failure
path before discarding it, so the same "no unwiped intermediate copy" discipline holds there too.

---

## Consequences

- **1.6c's own Android derivation blocker (ADR-0009 §Block 1.6c gate result) is resolved.**
  `KeyDerivation.derivePrivate` is now verified on real Android runtime, not merely on JVM.
- **1.6d's fingerprint-display checkpoint is now unblocked on every target, including
  Android.** The checkpoint needs a Blake2b-224 fingerprint of the *derived public key*.
  `KeyDerivation.publicKey(...)` is golden-vector-verified on JVM and Android (real-runtime
  execution, §2a) and compile/link-verified on iOS, so 1.6d's fingerprint step can now proceed
  on every target this SDK supports. This corrects §2's original expectation that 1.6d's
  Android checkpoint would stay blocked.
- **Block 1.7 (address generation) is not started, evaluated, or unblocked by this ADR.**
  Address generation is out of scope here; it should still run its own dependency/target
  verification gate even though the public-key-projection prerequisite it would have needed is
  now available on every target.
- The `bip32-ed25519` version-catalog entry now points at
  `org.hyperledger.identus:bip32-ed25519:1.8.8` instead of `dev.allain:bip32-ed25519:2.3.0`.
  No public API changed as a result of this swap (same wrapper functions, same byte layouts).
- Three new production dependencies enter `:crypto`:
  `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings:0.9.5` (`jvmMain`, `iosArm64Main`,
  `iosSimulatorArm64Main` only) and `org.jetbrains.kotlinx:kotlinx-coroutines-core:1.11.0`
  (needed to call the libsodium bindings' suspending `LibsodiumInitializer.initialize()`
  synchronously via `runBlocking` on JVM/iOS actuals), plus `com.goterl:lazysodium-android:5.2.0`
  and `net.java.dev.jna:jna:5.17.0` (`androidMain` only, §2a) for the Android projection
  backend.

---

## Non-goals

- No transaction signing, no address generation, no wallet/UI changes.
- No handwritten Ed25519 or BIP-32 arithmetic anywhere in this ADR — both the derivation swap
  and the projection addition delegate to third-party native libraries.
- No dynamic (`+`) or unpinned dependency versions.
- No backend type appears in any public API signature (`ExtendedPublicKey`,
  `KeyDerivation.publicKey`, and `KeyDerivationError.PublicKeyProjectionUnavailable` are all
  backend-neutral).
- No claim of Android coverage beyond what real-runtime execution actually verified: §2a's
  on-device tests ran on API 24, 35, and 36 specifically, and the record above names exactly
  those three, not a general "all API levels" claim.

---

## Follow-up work

- **Android public-key projection is resolved (§2a); no open blocker remains from this ADR.**
- **1.6d:** can now implement its Android path-derivation/error-state work against a working
  `derivePrivate` on Android, and its fingerprint-display step against a working
  `KeyDerivation.publicKey` on every target including Android.
- **1.7 (address generation):** not started; must still run its own dependency/target-
  verification gate (this ADR does not pre-approve any address-generation dependency), but no
  longer needs to account for an Android public-key-projection gap when scoping it.

---

## Relationship to ADR-0008 and ADR-0009

- ADR-0004's no-handwritten-crypto rule and ADR-0009 §7's key-material rules apply unchanged
  to `ExtendedPublicKey` and the `projectPublicKey` seam (§3 above).
- This ADR closes both items ADR-0009 §Block 1.6c gate result left open under "Follow-up
  work," and, as of §2a (Block 1.6c-follow-up-2), closes the Android-projection sub-blocker
  this ADR itself opened in between. ADR-0009 should be read together with this ADR for
  1.6c/1.6c-follow-up/1.6c-follow-up-2's actual, current status; this ADR does not edit
  ADR-0009's own historical findings, which remain an accurate record of what was verified at
  the time.
