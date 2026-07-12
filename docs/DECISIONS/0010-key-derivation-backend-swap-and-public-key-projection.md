# ADR-0010: Key-Derivation Backend Swap And Public-Key Projection (Block 1.6c Follow-Up)

| Field   | Value                                             |
|---------|---------------------------------------------------|
| Status  | **Accepted** (dependency swap and public-key-projection backend are implemented and verified per the scope below; Android public-key projection stays an explicit, open blocker) |
| Scope   | Phase 1 Block 1.6c-follow-up — closes the two blockers ADR-0009 §Block 1.6c gate result opened |
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
- **Android public-key projection is a separate, explicit, open blocker — not silently
  degraded and not implemented by any other backend in this ADR.** `KeyDerivation.publicKey`
  is implemented via a per-platform seam (`internal expect fun projectPublicKey(kL): 
  KardanoResult<ByteArray, KeyDerivationError>`, mirroring the existing PBKDF2 platform-seam
  pattern from ADR-0009's Block 1.6b gate result). The `androidMain` actual does **not**
  attempt the native call at all (there is no libsodium dependency in `androidMain`); it
  returns the new `KeyDerivationError.PublicKeyProjectionUnavailable` immediately. This was
  verified on the same real Android runtime via `PublicKeyUnavailableDeviceTest`
  (`:crypto:connectedAndroidDeviceTest`): calling `KeyDerivation.publicKey(...)` on-device
  returns the typed error and does not crash, throw, or hang.
- **`KeyDerivation.derivePrivate` is unaffected by this blocker and works on Android** (§1) —
  the Android gap is scoped exactly to public-key projection, not to key derivation in
  general. No code or documentation in this repository should describe Android as blocked for
  derivation, or as supported for public-key projection; the two must be stated separately.

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
pre-existing caveat, same as every other delegated-crypto call in this repository).

---

## Consequences

- **1.6c's own Android derivation blocker (ADR-0009 §Block 1.6c gate result) is resolved.**
  `KeyDerivation.derivePrivate` is now verified on real Android runtime, not merely on JVM.
- **1.6d's fingerprint-display checkpoint remains blocked on Android specifically, for a
  narrower and different reason than before.** The checkpoint needs a Blake2b-224 fingerprint
  of the *derived public key*. `KeyDerivation.publicKey(...)` now exists and is
  golden-vector-verified on JVM (and compile/link-verified on iOS), so 1.6d's fingerprint step
  can proceed on JVM/iOS. **On Android it cannot**: `KeyDerivation.publicKey` returns
  `PublicKeyProjectionUnavailable` there, so the fingerprint cannot be computed on Android
  until that gap closes. **1.6d's Android checkpoint is not unblocked by this ADR** — only the
  path-derivation/error-state portion of it (which depends solely on `derivePrivate`) gains a
  working Android path; the fingerprint-display portion of the same checkpoint stays blocked.
- **Block 1.7 (address generation) is not started, evaluated, or unblocked by this ADR.**
  Address generation is out of scope here; whether it needs the projected public key on every
  target (likely, since a payment credential is a hash of the public key) is that block's own
  gate to run.
- The `bip32-ed25519` version-catalog entry now points at
  `org.hyperledger.identus:bip32-ed25519:1.8.8` instead of `dev.allain:bip32-ed25519:2.3.0`.
  No public API changed as a result of this swap (same wrapper functions, same byte layouts).
- Two new production dependencies enter `:crypto`:
  `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings:0.9.5` (`jvmMain`, `iosArm64Main`,
  `iosSimulatorArm64Main` only — deliberately not `androidMain`, per the decision above) and
  `org.jetbrains.kotlinx:kotlinx-coroutines-core:1.11.0` (needed to call the libsodium
  bindings' suspending `LibsodiumInitializer.initialize()` synchronously via `runBlocking` on
  JVM/iOS actuals).

---

## Non-goals

- No transaction signing, no address generation, no wallet/UI changes.
- No handwritten Ed25519 or BIP-32 arithmetic anywhere in this ADR — both the derivation swap
  and the projection addition delegate to third-party native libraries.
- No dynamic (`+`) or unpinned dependency versions.
- No backend type appears in any public API signature (`ExtendedPublicKey`,
  `KeyDerivation.publicKey`, and `KeyDerivationError.PublicKeyProjectionUnavailable` are all
  backend-neutral).
- No claim that Android public-key projection works, is planned to be fixed by a specific
  date, or is merely "at risk" — it is a confirmed, reproduced failure on real Android runtime
  with a confirmed root cause (missing native symbol), exactly the same evidentiary standard
  ADR-0009 applied to the original Android derivation blocker.

---

## Follow-up work

- **Android public-key projection is an open blocker.** Options for a future block to
  evaluate (not decided here): an alternative Android-capable Ed25519 "public key from a
  clamped scalar" library; a different libsodium Android distribution/build that does export
  the needed symbol; or an explicit re-scope decision that a given checkpoint/feature ships
  JVM/iOS-only. Whichever path is chosen must be verified on real Android runtime, not host
  JVM or artifact inspection alone (the same lesson this ADR and ADR-0009 both apply).
- **1.6d:** can now implement its Android path-derivation/error-state work against a working
  `derivePrivate` on Android; its fingerprint-display step can proceed on JVM/iOS now, but
  stays blocked on Android pending the item above.
- **1.7 (address generation):** not started; must run its own dependency/target-verification
  gate, and should account for the Android public-key-projection gap when scoping its own
  Android checkpoint.

---

## Relationship to ADR-0008 and ADR-0009

- ADR-0004's no-handwritten-crypto rule and ADR-0009 §7's key-material rules apply unchanged
  to `ExtendedPublicKey` and the `projectPublicKey` seam (§3 above).
- This ADR closes both items ADR-0009 §Block 1.6c gate result left open under "Follow-up
  work," with one correction to that ADR's expectation: Blocker 1 (public-key projection) is
  **not** fully closed for every target — only for JVM/iOS. ADR-0009 should be read together
  with this ADR for 1.6c/1.6c-follow-up's actual, current status; this ADR does not edit
  ADR-0009's own historical findings, which remain an accurate record of what was verified at
  the time.
