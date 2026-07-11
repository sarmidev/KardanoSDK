# :crypto

The cryptographic boundary for Kardano SDK: hashing (Phase 1 Block 1.5b), BIP-39/CIP-3
mnemonic + Icarus master-key derivation (Phase 1 Block 1.6b), and Ed25519-BIP32/CIP-1852
private-key derivation (Phase 1 Block 1.6c).

## Status

Phase 1 — pre-alpha, experimental. Not audited. Not for real funds.

Block 1.6b is complete on JVM and Android, with executed CIP-3/BIP-39 vectors. On iOS, the
`:crypto:compileKotlinIosSimulatorArm64` and `:crypto:compileKotlinIosArm64` compile targets
pass via an interop shim (see "iOS PBKDF2 cinterop" below); iOS runtime execution of the CIP-3
vectors is still future verification — no iOS-simulator/device test run has executed the
derivation.

Block 1.6c is narrowed to private derivation only and is **JVM-verified + iOS compile/link
verified; Android derivation is blocked, not merely unverified.** Its full gate result,
narrowed scope, and open items are recorded in
[ADR-0009 §Block 1.6c gate result](../docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md):

- **Private derivation only.** `KeyDerivation.derivePrivate(...)` and `ExtendedPrivateKey`
  ship; there is no `publicKey()` and no `ExtendedPublicKey` in this block — the pinned
  `dev.allain:bip32-ed25519:2.3.0` backend has no primitive to project a private key to its
  public key. Public-key derivation is deferred to a follow-up block.
- **JVM is the verified target for the golden vectors; Android derivation is blocked for
  this dependency.** The published `bip32-ed25519-android` AAR ships no native library at
  all, so calling `deriveBytes` — the function `derivePrivate` calls — under
  `:crypto:testAndroidHostTest` throws a confirmed `UnsatisfiedLinkError`. This is a
  reproduced failure, not an absence of verification: no working Android path currently
  exists for `KeyDerivation.derivePrivate`. `:crypto:testAndroidHostTest` still passes for
  this block only because no backend-calling test runs there (see "Testing" below) — it
  verifies compilation against Android, not runtime derivation. A real device/emulator run
  (which is expected to reproduce the same failure, since the AAR has no native binary for
  any ABI) is recorded as follow-up work, not yet done.
- iOS **compile and link** both pass (`:crypto:compileKotlinIosSimulatorArm64`,
  `:crypto:compileKotlinIosArm64`, and an actual test-binary link all succeed) — this closes
  the "link is unproven" gap 1.6b's iOS section left open, for this dependency. iOS runtime
  execution of the vectors is still future verification, same status as 1.6b.

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
  (`1852'`, `1815'`, `account'`, `role`, `index`). Backed by `dev.allain:bip32-ed25519:2.3.0`'s
  `deriveBytes`, called directly from `commonMain` (no platform seam needed for this
  dependency). Failures map to a typed `KeyDerivationError`.
- Defines `ExtendedPrivateKey`: opaque like `IcarusMasterKey` (private constructor, defensive
  copies, structural `toString()`, best-effort `clear()`, no public raw-byte accessor).

All operations return `KardanoResult` and never throw, which keeps the API compatible with
Swift/ObjC interop.

## Scope

- **Hashing (1.5b), mnemonic/Icarus-master-key derivation (1.6b), and CIP-1852 private
  derivation (1.6c) only.** There is no public-key derivation, no `ExtendedPublicKey`, no
  signing, no wallet, no transaction, and no address generation here.
- No real mnemonics, private keys, or funds are involved anywhere — every mnemonic in this
  module's tests is a public, cited test vector, clearly labeled as such.
- English BIP-39 wordlist only; other wordlists, and the Byron/Ledger/Trezor scheme
  variants, are deferred (ADR-0009 §2).

## Boundaries

- Depends only on `:core` (for `KardanoResult` and, in `jvmTest` only, the generic
  `Bech32.decode` used to decode CIP-5 test vectors) and `dev.allain:bip32-ed25519:2.3.0`
  (Ed25519-BIP32 private derivation, Block 1.6c). `:core` does not depend on `:crypto`.
- No backend type appears in any public API. Per
  [ADR-0008](../docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md),
  Apollo 1.8.8 does not ship a Blake2b implementation, so hashing is backed by KotlinCrypto
  `org.kotlincrypto.hash:blake2`. Per
  [ADR-0009](../docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md), Apollo's mnemonic
  and PBKDF2 APIs do not fit the Icarus path either, so Block 1.6 does not add the main Apollo
  artifact; the Ed25519-BIP32 value arrives separately via `dev.allain:bip32-ed25519`
  (Block 1.6c) instead — pinned, `commonMain`-only, no other Apollo module added.
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
- Android host tests: `./gradlew :crypto:testAndroidHostTest`
- iOS compile targets: `./gradlew :crypto:compileKotlinIosSimulatorArm64` and
  `./gradlew :crypto:compileKotlinIosArm64` (both pass; see "iOS PBKDF2 cinterop" above —
  compile-only, no iOS runtime vector execution yet)

Tests use only official, cited vectors copied verbatim: Blake2b-224 from CIP-19, Blake2b-256
from the IntersectMBO/plutus conformance goldens, BIP-39 entropy/mnemonic pairs from
`trezor/python-mnemonic` `vectors.json`, the CIP-3 `Icarus.md` master-key vectors (with
and without a passphrase), and the `IntersectMBO/cardano-addresses` Shelley golden (CIP-1852
private-derivation) vectors. No expected digest, entropy, or key is generated by this SDK or
any backend library. Invalid-input cases for `Mnemonic.parse` are derived rule tests built by
mutating a cited vector one property at a time (see `MnemonicRuleTest`), per
`docs/TESTING.md`.

**Placement rule for CIP-1852 vector tests (`crypto/jvmTest`, not `commonTest`):** any test
that calls the real `bip32-ed25519` backend lives in `crypto/src/jvmTest`. `commonTest` runs
under `:crypto:testAndroidHostTest` too, and that dependency's published Android artifact has
no native library to load there (see "Status" above) — placing a backend-calling test in
`commonTest` would make `:crypto:testAndroidHostTest` fail with `UnsatisfiedLinkError` for a
reason unrelated to this SDK's own logic. Structural/validation tests that never call the
backend (`Cip1852Path`, `ExtendedPrivateKey`, the adapter's exception-mapping rule test) stay
in `commonTest` and run on every target.

See [docs/TESTING.md](../docs/TESTING.md) for the testing strategy and test-vector policy,
[docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md](../docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md)
for the hashing dependency decision, and
[docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md](../docs/DECISIONS/0009-mnemonic-seed-and-key-derivation.md)
for the mnemonic/key-derivation scheme, dependency, and PBKDF2 platform-seam decisions.
