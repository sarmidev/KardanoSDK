# :crypto

The cryptographic boundary for Kardano SDK: hashing (Phase 1 Block 1.5b), BIP-39/CIP-3
mnemonic + Icarus master-key derivation (Phase 1 Block 1.6b), and Ed25519-BIP32/CIP-1852
private- and public-key derivation (Phase 1 Block 1.6c + 1.6c-follow-up, ADR-0010).

## Status

Phase 1 — pre-alpha, experimental. Not audited. Not for real funds.

Block 1.6b is complete on JVM and Android, with executed CIP-3/BIP-39 vectors. On iOS, the
`:crypto:compileKotlinIosSimulatorArm64` and `:crypto:compileKotlinIosArm64` compile targets
pass via an interop shim (see "iOS PBKDF2 cinterop" below); iOS runtime execution of the CIP-3
vectors is still future verification — no iOS-simulator/device test run has executed the
derivation.

Block 1.6c's original gate (ADR-0009) narrowed it to private derivation only. A follow-up gate
([ADR-0010](../docs/DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md))
then closed the two blockers that left open, with one important correction: **private
derivation now works on JVM, real Android runtime, and iOS compile/link; public-key
projection works on JVM and iOS compile/link, but is unavailable on Android.**

- **Private derivation, all targets: verified.** `KeyDerivation.derivePrivate(...)` and
  `ExtendedPrivateKey` are backed by `org.hyperledger.identus:bip32-ed25519:1.8.8`'s
  `deriveBytes` (the coordinate ADR-0010 swapped to, from the `dev.allain` republish, for its
  Android native-library support — identical wrapper API, no adapter code changed). Verified
  against the cited golden vectors on `:crypto:jvmTest` and on a **real Android emulator**
  via `:crypto:connectedAndroidDeviceTest` (not host JVM); iOS compiles and links.
- **Public-key projection: verified on JVM, unavailable on Android.**
  `KeyDerivation.publicKey(key)` and `ExtendedPublicKey` are backed by libsodium's
  `crypto_scalarmult_ed25519_base_noclamp` (`com.ionspin.kotlin:
  multiplatform-crypto-libsodium-bindings:0.9.5`), verified byte-for-byte against the cited
  `addr_xvk` goldens on JVM; iOS compiles and links against the same backend. **On Android,
  the same real-emulator run that verified derivation throws a confirmed
  `UnsatisfiedLinkError` for this call specifically** — static symbol inspection confirmed the
  published Android native library for this projection backend does not export the needed
  symbol at all (present on its JVM/iOS builds). `KeyDerivation.publicKey` on Android returns
  `KeyDerivationError.PublicKeyProjectionUnavailable` instead of calling the backend (verified
  on-device to degrade gracefully, not crash). **This does not affect
  `KeyDerivation.derivePrivate`, which works on Android.**
- iOS **compile and link** both pass for both the derivation and projection backends
  (`:crypto:compileKotlinIosSimulatorArm64`, `:crypto:compileKotlinIosArm64`, and an actual
  test-binary link all succeed). iOS runtime execution of the vectors is still future
  verification, same status as 1.6b.

## Role

- Defines `Hashing`: a minimal, backend-neutral interface for the Blake2b digests Cardano
  uses — `blake2b224` (credential hashes) and `blake2b256` (transaction, datum, and script
  hashes).
- Defines `HashDigest`: a structural, fixed-length byte container for a digest, with a
  private constructor, defensive copies on construction and on every read, content-based
  equality, and a structural `toString()` that never renders the wrapped bytes.
- Defines the sealed, backend-neutral `CryptoError` (`HashingFailed`, `InvalidDigestLength`).
- Ships one hashing implementation: `Hashing.default()` returns an internal adapter backed
  by the KotlinCrypto `blake2` library.
- Defines `Mnemonic.parse(...)`: validates a BIP-39 English mnemonic (word count, wordlist
  membership, checksum) and extracts its entropy. Restore-only; there is no mnemonic
  generation. Non-conforming input (wrong length, unknown word, bad checksum, non-ASCII or
  uppercase characters) is rejected with a typed `MnemonicError`, never normalized.
- Defines `IcarusMasterKey.fromMnemonic(...)`: derives the CIP-3 (Icarus) 96-byte root
  extended key — PBKDF2-HMAC-SHA-512 over the mnemonic's entropy bytes (4096 iterations, 96
  bytes) followed by the CIP-3 bit tweaks. Failures map to a typed `KeyDerivationError`.
- Both `Mnemonic` and `IcarusMasterKey` are opaque: private constructors, defensive copies,
  a structural `toString()` that renders no words/entropy/key bytes, and a best-effort
  `clear()`. Neither type exposes a raw-byte accessor.
- Defines `Cip1852Path.of(...)` + `Cip1852Role`: SDK-owned value types for a validated
  CIP-1852 path `m/1852'/1815'/account'/role/index`. `account`/`index` are accepted as `Long`
  so out-of-`Int`-range values are rejectable rather than silently overflowing; validated
  values are stored internally as `Int`. Path components are public metadata (not key
  material) and are rendered by `toString()`.
- Defines `KeyDerivation.derivePrivate(master, path)`: derives an `ExtendedPrivateKey` at a
  `Cip1852Path` from an `IcarusMasterKey` root, via five successive Ed25519-BIP32 steps
  (`1852'`, `1815'`, `account'`, `role`, `index`). Backed by
  `org.hyperledger.identus:bip32-ed25519:1.8.8`'s `deriveBytes`, called directly from
  `commonMain` (no platform seam needed for this dependency). Failures map to a typed
  `KeyDerivationError`. Verified on JVM, real Android runtime, and iOS compile/link
  (ADR-0010).
- Defines `KeyDerivation.publicKey(key)`: projects an `ExtendedPrivateKey` to its
  `ExtendedPublicKey` via a per-platform seam backed by libsodium's
  `crypto_scalarmult_ed25519_base_noclamp`. Verified against the cited `addr_xvk` goldens on
  JVM; compiles and links on iOS. **Unavailable on Android** — returns
  `KeyDerivationError.PublicKeyProjectionUnavailable` (ADR-0010; the published Android native
  library for this backend is missing the required symbol).
- Defines `ExtendedPrivateKey` and `ExtendedPublicKey`: opaque like `IcarusMasterKey` (private
  constructor, defensive copies, structural `toString()`, best-effort `clear()`).
  `ExtendedPrivateKey` has no public raw-byte accessor; `ExtendedPublicKey.publicKeyBytes()`
  is the one raw-byte accessor in this module (a copy — the public key is not secret, but the
  underlying array is never exposed directly).

All operations return `KardanoResult` and never throw, which keeps the API compatible with
Swift/ObjC interop.

## Scope

- **Hashing (1.5b), mnemonic/Icarus-master-key derivation (1.6b), and CIP-1852 private and
  public derivation (1.6c + 1.6c-follow-up/ADR-0010) only.** Public-key projection is
  available on JVM/iOS only (unavailable on Android — see "Status"). There is no signing, no
  wallet, no transaction, and no address generation here.
- No real mnemonics, private keys, or funds are involved anywhere — every mnemonic in this
  module's tests is a public, cited test vector, clearly labeled as such.
- English BIP-39 wordlist only; other wordlists, and the Byron/Ledger/Trezor scheme
  variants, are deferred (ADR-0009 §2).

## Boundaries

- Depends only on `:core` (for `KardanoResult` and, in `jvmTest` only, the generic
  `Bech32.decode` used to decode CIP-5 test vectors),
  `org.hyperledger.identus:bip32-ed25519:1.8.8` (Ed25519-BIP32 private derivation, Block 1.6c;
  swapped from `dev.allain:bip32-ed25519:2.3.0` in ADR-0010 for Android native-library
  support), and — on `jvmMain`/`iosArm64Main`/`iosSimulatorArm64Main` only, not `androidMain`
  — `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings:0.9.5` plus
  `kotlinx-coroutines-core` (public-key projection, ADR-0010). `:core` does not depend on
  `:crypto`.
- No backend type appears in any public API. Per
  [ADR-0008](../docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md),
  Apollo 1.8.8 does not ship a Blake2b implementation, so hashing is backed by KotlinCrypto
  `org.kotlincrypto.hash:blake2`. Per
  [ADR-0009](../docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md), Apollo's mnemonic
  and PBKDF2 APIs do not fit the Icarus path either, so Block 1.6 does not add the main Apollo
  artifact; the Ed25519-BIP32 value arrives separately via `bip32-ed25519`
  (Block 1.6c) instead — pinned, no other Apollo module added.
- The BIP-39 checksum's SHA-256 is delegated to KotlinCrypto `org.kotlincrypto.hash:sha2`.
  PBKDF2-HMAC-SHA-512 is delegated to a platform seam (`expect`/`actual`): BouncyCastle
  `PKCS5S2ParametersGenerator` on JVM and Android, Apple CommonCrypto `CCKeyDerivationPBKDF`
  on iOS (reached through a signature-adapting interop shim — see "iOS PBKDF2 cinterop"
  below). No PBKDF2, SHA-256, or SHA-512 is hand-written in this module; the BIP-39 wordlist
  lookup/bit-packing and the CIP-3 bit tweaks are SDK-owned data handling around those
  delegated primitives (ADR-0009 §3.1).
- `blake2` publishes `jvm` and iOS artifacts plus artifacts expected to be usable by this
  repo's Android target; `:crypto:testAndroidHostTest` verifies Android target
  resolution/compile.

### iOS PBKDF2 cinterop (Block 1.6b)

The shipped Kotlin/Native `platform.CoreCrypto.CCKeyDerivationPBKDF` binding maps its
`password` parameter to `String`, which cannot carry raw (possibly non-UTF-8) passphrase
bytes. A custom cinterop `.def` with `noStringConversion` (rebinding `CCKeyDerivationPBKDF`
itself, still 100% delegated to Apple CommonCrypto, no hand-written PBKDF2) was tried first,
but in this repository's build environment that generated klib came out with **zero
declarations** (confirmed with `klib dump-metadata`, reproduced even after matching the
shipped `platform.CoreCrypto.def` exactly).

The fix is an inline C interop shim defined in
`src/nativeInterop/cinterop/pbkdf2raw.def`'s glue block:
`kardano_ccpbkdf2_hmac_sha512` declares `password` as `const uint8_t *` and casts it to
`const char *` only at the call boundary to `CCKeyDerivationPBKDF` — a signature adapter, not
a PBKDF2 implementation. The shim was confirmed bindable with `klib dump-metadata` (`password`
appears as `CValuesRef<UByteVarOf<UByte>>?`, not `String`) before the
`iosArm64Main`/`iosSimulatorArm64Main` actuals were written against it.

**Verified: the iOS compile targets pass** —
`:crypto:compileKotlinIosSimulatorArm64` and `:crypto:compileKotlinIosArm64` both succeed.
**Not yet verified: iOS runtime execution.** No iOS-simulator or device test run has executed
the CIP-3/BIP-39 vectors against this binding; only JVM and Android have executed vectors.
Confirming runtime behavior on iOS is deferred to when device/simulator test execution is
wired up.

## Testing

- Contract tests: `./gradlew :crypto:jvmTest`
- Android host tests: `./gradlew :crypto:testAndroidHostTest` (host JVM — compile/resolution
  only, not real Android native-library loading; see below)
- **Android on-device tests (real emulator/device, ADR-0010):**
  `./gradlew :crypto:connectedAndroidDeviceTest` — requires a running emulator or connected
  device (`adb devices` must list one first). This is the only task that actually loads the
  `bip32-ed25519`/libsodium native libraries on Android; `testAndroidHostTest` cannot detect
  native-loading failures because it runs on the host JVM, not Android.
- iOS compile targets: `./gradlew :crypto:compileKotlinIosSimulatorArm64` and
  `./gradlew :crypto:compileKotlinIosArm64` (both pass; see "iOS PBKDF2 cinterop" above —
  compile-only, no iOS runtime vector execution yet)

Tests use only official, cited vectors copied verbatim: Blake2b-224 from CIP-19, Blake2b-256
from the IntersectMBO/plutus conformance goldens, BIP-39 entropy/mnemonic pairs from
`trezor/python-mnemonic` `vectors.json`, the CIP-3 `Icarus.md` master-key vectors (with
and without a passphrase), and the `IntersectMBO/cardano-addresses` Shelley golden (CIP-1852
private- and public-derivation) vectors. No expected digest, entropy, or key is generated by
this SDK or any backend library. Invalid-input cases for `Mnemonic.parse` are derived rule
tests built by mutating a cited vector one property at a time (see `MnemonicRuleTest`), per
`docs/TESTING.md`.

**Placement rule for CIP-1852 vector tests (`crypto/jvmTest`, not `commonTest`):** any test
that calls the real `bip32-ed25519`/libsodium backends lives in `crypto/src/jvmTest`
(JVM-executed goldens) and `crypto/src/androidDeviceTest` (real-Android-runtime goldens, run
only when an emulator/device is attached — see above). `commonTest` runs under
`:crypto:testAndroidHostTest` too, which is host-JVM-only and cannot exercise Android's real
native-loading path either way, so placing a backend-calling test there would give false
confidence rather than a real gap. Structural/validation tests that never call a backend
(`Cip1852Path`, `ExtendedPrivateKey`, `ExtendedPublicKey`, the adapter's exception-mapping
rule test) stay in `commonTest` and run on every target.

See [docs/TESTING.md](../docs/TESTING.md) for the testing strategy and test-vector policy,
[docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md](../docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md)
for the hashing dependency decision,
[docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md](../docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md)
for the mnemonic/key-derivation scheme, dependency, and PBKDF2 platform-seam decisions, and
[docs/DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md](../docs/DECISIONS/0010-key-derivation-backend-swap-and-public-key-projection.md)
for the 1.6c-follow-up backend swap (Android derivation), public-key projection, and the
Android public-key-projection blocker.
