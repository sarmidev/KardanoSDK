# ADR-0009: Mnemonic, Seed, And Key Derivation (Block 1.6)

| Field   | Value                                             |
|---------|---------------------------------------------------|
| Status  | **Accepted** (module / scheme / API / vector-gate / process decisions; dependency selections are verified against published artifacts but adoption is committed only in the implementing subphase) |
| Scope   | Phase 1 Block 1.6a — API, dependency, and vector-source decision for mnemonic / seed / key derivation |
| Phase   | Phase 1 (Block 1.6a)                              |
| Updated | 2026-07-11                                        |

---

## Context

Block 1.5b completed the first `:crypto` boundary: Blake2b-224/256 behind the backend-neutral
`Hashing` interface, backed by KotlinCrypto `blake2` `0.8.0`. Block 1.6 adds test-wallet
restoration and key derivation. It is split into four gated subphases, each its own diff:

- **1.6a** (this ADR, docs-only): API, dependency, and vector-source decisions.
- **1.6b**: BIP-39 mnemonic validation + Icarus (CIP-3) master-key derivation only.
- **1.6c**: Ed25519-BIP32 extended-key derivation + CIP-1852 path derivation only.
- **1.6d**: test-wallet fixture + Android Playground checkpoint (public metadata only).

ADR-0004 (crypto strategy) and ADR-0008 (module/seam/process; `KeyDerivation` named as the
next seam) remain in force. The governing lesson from Block 1.5b: **verify API presence in
published artifacts, not in matrix or README claims** — ADR-0008's matrix had listed Blake2b
for Apollo and the published jar did not contain it. Every dependency claim in this ADR
therefore records its verification method, and anything not verified is marked
`To verify in 1.6b` / `To verify in 1.6c`.

### Terminology

This ADR writes `'` (prime) for the BIP-32 index class at or above 2^31 (the spec notation
in `m / 1852' / 1815' / account' / role / index`) and "soft" for indexes below 2^31. The
BIP-32 spec's own name for the prime class is not used in this repository's docs because it
collides with a banned claim word; the meaning here is exactly the BIP-32 index class,
nothing more.

---

## Decision

### 1. Module placement: all of Block 1.6 lands in `:crypto`; no `:wallet` module yet

Mnemonic parsing, master-key derivation, extended-key types, and CIP-1852 path derivation
all land in `:crypto` (package `org.sarmidev.kardano.crypto`), behind the seam ADR-0008 §2
already names (`KeyDerivation`, plus a mnemonic boundary). No `:wallet` module is created in
Block 1.6: per ADR-0002/ADR-0005, a module is extracted only under dependency or ownership
pressure, and 1.6's dependencies are crypto dependencies that belong in `:crypto`.

**Recorded trigger for a future `:wallet` split:** the first block that composes derivation
with non-crypto concerns — account/address orchestration, wallet state, or persistence
(earliest candidates: Blocks 1.7/1.8). That block re-evaluates extraction; until then,
key-material types stay in `:crypto`.

### 2. Scheme: Phase 1 targets the Icarus/CIP-3 restoration path only

**Phase 1 targets the Icarus/CIP-3 restoration path for the MVP test wallet; Byron,
Ledger, Trezor, and other scheme variants are deferred.** This SDK does not support all
Cardano wallet restoration schemes in Block 1.6, and nothing in this ADR implies otherwise.

The Icarus master-key generation (CIP-3, `Icarus.md`) is:

- master key = PBKDF2-HMAC-SHA-512(password = passphrase bytes, salt = **BIP-39 entropy
  bytes** (not the BIP-39 seed, not the mnemonic string), iterations = 4096,
  output = 96 bytes), followed by the CIP-3 bit tweaks on the first 64 bytes
  (`data[0] &= 0b1111_1000; data[31] &= 0b0001_1111; data[31] |= 0b0100_0000`).
- The 96-byte result is the root extended key: a 64-byte extended private key plus a
  32-byte chain code. There is no separate "root from seed" library step.

Outputs 1.6b produces: the opaque Icarus master key only. The plain BIP-39 seed function
(PBKDF2 over the mnemonic string with salt `"mnemonic" + passphrase`) is **not** exposed:
Cardano's Icarus path does not use it, and no cited need exists in the Phase 1 MVP flow.

Scope restrictions recorded now:

- **English BIP-39 wordlist only** in 1.6b; other wordlists are deferred.
- Input handling rejects rather than normalizes: 1.6b accepts lowercase ASCII words from
  the English wordlist and rejects anything else with a typed error. BIP-39 mandates NFKD
  normalization for arbitrary Unicode input; on the English-wordlist ASCII domain NFKD is
  the identity, so restricting the domain avoids shipping a Unicode-normalization
  dependency while staying spec-consistent. This is the same "reject, never normalize"
  posture as the Phase 0 parsers.
- Deferred schemes: Byron (`retry-old`/legacy pbkdf master-key generation), Ledger
  (BIP32-Ed25519 master key from BIP-39 seed via HMAC), Trezor's 24-word deviation
  (CIP-3 documents its checksum-byte bug), multi-wordlist support.

### 3. Dependency-per-algorithm table

Verification methods used for this ADR (2026-07-11, all against published artifacts or
pinned source tags; no repository build was touched):

- `javap` over the published `apollo-jvm-1.8.8.jar` (Maven Central) and source reads at
  `hyperledger-identus/apollo` tag `v1.8.7` / branch `main`.
- `javap` + archive listing over the published `bip32-ed25519-jvm-2.3.0.jar` and the
  `dev.allain` Maven Central group listing (iOS cinterop klib artifacts confirmed:
  `bip32-ed25519-iosarm64`, `bip32-ed25519-iossimulatorarm64`).
- Maven Central group listings for `org.kotlincrypto.*` and `dev.whyoleg.cryptography`.

| Algorithm | Selected dependency | Enters in | Verification / notes |
|-----------|--------------------|-----------|----------------------|
| BIP-39 wordlist + mnemonic validation (word count, wordlist membership, checksum bit-unpacking) | SDK-owned data handling in `:crypto` (wordlist table + 11-bit unpacking), with the checksum's SHA-256 delegated (next row). Apollo's mnemonic API is **rejected** — see finding A | 1.6b | Finding A below; classification rationale in §3.1 |
| SHA-256 (BIP-39 checksum) | `org.kotlincrypto.hash:sha2` `0.8.0` (Apache-2.0; same project and version line as the pinned `blake2` backend) | 1.6b | Artifact + version confirmed on Maven Central; API shape is the same `Digest` pattern `Blake2bHashing` already wraps |
| PBKDF2-HMAC-SHA-512 (Icarus master key) | Lead: cryptography-kotlin `dev.whyoleg.cryptography:cryptography-core:0.6.0` + `cryptography-provider-jdk:0.6.0` (JVM/Android) + `cryptography-provider-apple:0.6.0` (iOS) — PBKDF2 `SecretDerivation` takes a `ByteArray` salt, required for entropy-bytes salt. Apollo's PBKDF2 is **rejected** — see finding B | 1.6b | Artifacts confirmed on Maven Central (Apache-2.0 per POM). `To verify in 1.6b`: per-provider PBKDF2-SHA-512 coverage on all four targets, and Android API 24/25 availability (the JDK provider delegates to JCA; `PBKDF2WithHmacSHA512` is reported as API 26+ in the Android `SecretKeyFactory` table, vs project `minSdk = 24`). Fallback if verification fails: ADR-0008-style platform seam (`expect`/`actual`) — a maintained pure-JVM PBKDF2 source on JVM/Android + Apple CommonCrypto `CCKeyDerivationPBKDF` on iOS |
| HMAC-SHA-512 | **No direct dependency needed in 1.6.** It is internal to PBKDF2 (previous row) and to the Ed25519-BIP32 child-derivation step inside the Rust crate (next row). `org.kotlincrypto.macs:hmac-sha2` `0.8.0` exists (confirmed on Maven Central) if a later block needs it directly | — | Recorded so 1.6b/1.6c do not add an unused artifact |
| Ed25519-BIP32 extended keys (child derivation, private only in 1.6c) | `dev.allain:bip32-ed25519:2.3.0` (Apache-2.0 per POM; uniffi Kotlin bindings over the IOG Rust `ed25519-bip32` crate; published from the `hyperledger-identus/apollo` repo as a standalone module) | 1.6c | Finding C below. `To verify in 1.6c`: **closed, see §Block 1.6c gate result** — byte layouts confirmed (`deriveBytes` in: 64-byte xsk + 32-byte chain code + `UInt` index; out: map keys `secret_key`/`chain_code`), V2/Icarus-only confirmed, iOS simulator compile-and-link **passed**, Android runtime loading **failed with a confirmed `UnsatisfiedLinkError`** (no native library in the published AAR — this dependency's Android derivation path is **blocked**, not merely an open risk, per the recorded decision not to make it a hard gate for 1.6c's own JVM/iOS scope). No public-key-derivation primitive exists in this dependency; public/soft derivation is deferred to a follow-up block |
| CIP-1852 path model (`m / 1852' / 1815' / account' / role / index`) | SDK-owned value types in `:crypto` (path constants + index validation are data handling, not cryptography). The per-step derivation math is the row above | 1.6c | CIP-1852 pins the constants (`1852'` purpose, `1815'` coin type, roles 0/1/2) |
| Platform CSPRNG (mnemonic generation) | **Deferred out of Block 1.6** (§8) | — | ADR-0004 §Randomness |

The main `org.hyperledger.identus:apollo` artifact is **not added in Block 1.6** (finding
A/B). The Ed25519-BIP32 value ADR-0008 attributed to the Apollo stack lives in the
separately published `bip32-ed25519` module, which is consumed directly without the main
Apollo artifact (and without its transitive secp256k1/bitcoinj/guava/BouncyCastle surface).
The Block 1.5a spike compiled both artifacts, so compile compatibility for
`bip32-ed25519:2.3.0` under Kotlin 2.4.0 is already established (ADR-0008 §6).

#### Verified findings (the 1.5b-style artifact checks)

**Finding A — Apollo 1.8.8's mnemonic API is unsuitable for this block.** Verified via
`javap` on the published jar and the `MnemonicHelper.kt` source at tag `v1.8.7`:
`isValidMnemonicCode(code) = code.all { it in MnemonicCodeEnglish.wordList }` — wordlist
membership only, **no checksum validation and no word-count validation**; `createSeed`
computes PBKDF2-HMAC-SHA-512(password = mnemonic string, salt = passphrase string,
c = 2048, dkLen = 64) with default passphrase `"AtalaPrism"` — neither the BIP-39 seed
function (whose salt is `"mnemonic" + passphrase`) nor the Icarus master key (whose salt is
the entropy bytes and whose iteration count is 4096). There is no public words-to-entropy
API. This is the Identus/PRISM derivation path, not Cardano's.

**Finding B — Apollo 1.8.8's PBKDF2 API cannot express the Icarus call.** The `expect
object PBKDF2SHA512` signature is `derive(p: String, s: String, c: Int, dkLen: Int)`
(verified in the jar and in `commonMain` source). The salt parameter is a `String`; the
Icarus salt is raw entropy bytes, which are not in general valid UTF-8. The Apple `actual`
also routes the salt through `encodeToByteArray()`. A byte-salt PBKDF2 is required, which
Apollo does not publish.

**Finding C — `dev.allain:bip32-ed25519:2.3.0` exposes exactly the derivation calls 1.6c
needs.** Verified via `javap` on the published jvm jar: three top-level functions in
`uniffi.ed25519_bip32_wrapper` — `deriveBytes(privKey, chainCode, index):
Map<String, ByteArray>` (private-key child derivation, prime and soft),
`deriveBytesPub(pubKey, chainCode, index)` (public/soft derivation; throws a typed
`DerivationException.ExpectedSoftDerivation` on a prime index), and
`fromNonextended(key, chainCode)` (not needed for the Icarus path — the 96-byte master key
is already the root extended key). The jvm jar bundles darwin/linux native libraries via
JNA; Android has a separate `bip32-ed25519-android` artifact; iOS targets are cinterop
klibs with static libraries. Apollo's own `EdHDKey.initFromSeed` requires a 64-byte seed
split 32+32 through `fromNonextended` — again the PRISM path, not Icarus — so the SDK wraps
the wrapper functions directly rather than Apollo's `EdHDKey`.

#### 3.1 Classification: wordlist handling and CIP-3 bit tweaks are data handling

ADR-0004 prohibits handwritten cryptographic algorithms. Two Block 1.6 pieces are
classified as **data handling**, not cryptography, and are SDK-owned:

- BIP-39 wordlist lookup and 11-bit group packing/unpacking (a table lookup plus bit
  shifts defined by the BIP-39 encoding; the only cryptographic operation in mnemonic
  validation is the SHA-256 checksum, which is delegated to KotlinCrypto `sha2`).
- The CIP-3 `tweakBits` masking of three bytes of the PBKDF2 output (bit operations
  specified verbatim by CIP-3; PBKDF2 itself is delegated).

This is the same line Phase 0 drew for the Bech32 BCH checksum arithmetic (ADR-0001
context): spec-defined data manipulation around delegated cryptographic primitives. PBKDF2,
SHA-256, HMAC-SHA-512, and all Ed25519-BIP32 curve/scalar math remain delegated — none of
them is implemented in this repository.

### 4. Vector-source gate — all three families PASS

Gate rule (1.5b-pre pattern): each family needs exact, official, citable vectors — concrete
inputs, exact expected outputs, source URL, pinned commit, license — before its subphase
may start. Generated vectors are prohibited as a source of truth (ADR-0004 §7); bloxbean
cardano-client-lib remains at most a JVM-only secondary cross-check oracle (ADR-0008).

| Family | Result | Source |
|--------|--------|--------|
| BIP-39 mnemonic validation + entropy | **PASS** | `trezor/python-mnemonic` `vectors.json` (MIT), referenced normatively by BIP-39 ("Test vectors"). Pinned commit `b57a5ad77a981e743f4167ab2f7927a55c1e82a8` (2024-08-27). 24 English vectors of (entropy hex, mnemonic, BIP-39 seed with passphrase `"TREZOR"`, xprv). 1.6b uses the entropy↔mnemonic pairs for validation/round-trip of entropy extraction; the seed/xprv columns are **not** used (they exercise the BIP-39 seed function and BTC serialization, which 1.6b does not expose). Invalid-case tests (bad checksum, unknown word, wrong count) are labeled derived rule tests built by mutating a cited vector, per `docs/TESTING.md`. Wordlist source: `bitcoin/bips` `bip-0039/english.txt` |
| CIP-3 / Icarus master key | **PASS** | CIP-3 `Icarus.md` test vectors (CC-BY-4.0), repo `cardano-foundation/CIPs`, path `CIP-0003/Icarus.md`, pinned commit `a36e1ebca139ab4b31e12f0bf84bfb99481528bb` (2021-04-27). Vector 1 (no passphrase): recovery phrase `eight country switch draw meat scout mystery blade tip drift useless good keep usage title` → 96-byte master key `c065afd2832cd8b087c4d9ab7011f481ee1e0721e78ea5dd609f3ab3f156d245d176bd8fd4ec60b4731c3918a2a72a0226c0cd119ec35b47e4d55884667f552a23f7fdcd4a10c6cd2c7393ac61d877873e248f417634aa3d812af327ffe9d620`. Vector 2 (passphrase `foo` as UTF-8): same phrase → `70531039904019351e1afb361cd1b312a4d0565d4ff9f8062d38acf4b15cce41d7b5738d9c893feea55512a3004acb0d222c35d3e3d5cde943a15a9824cbac59443cf67e589614076ba01e354b1a432e0e6db3b59e37fc56b5fb0222970a010e` |
| Ed25519-BIP32 + CIP-1852 derivation | **PASS** | `IntersectMBO/cardano-addresses` Shelley golden tests (Apache-2.0), path `test/golden/addresses_5574d91d/golden`, pinned commit `46d01319015275941f96126b2496453693f89538` (2025-01-30). The golden corresponds to the 12-word mnemonic `test walk nut penalty hip pave soap entry language right filter choice`; the filename mapping was confirmed by recomputing the spec's `shortHex` (first 8 hex chars of SHA3-256 of the underscore-joined mnemonic — `ShelleySpec.hs`, same commit) = `5574d91d`. It pins, in CIP-5 bech32: `root_xsk` (Icarus root), `acct_xsk` for `1852'/1815'/0'` and `1852'/1815'/1'`, and `addr_xsk`/`addr_xvk` for role 0 indexes 0, 1, and 1442. **1.6c uses only the `root_xsk`/`acct_xsk`/`addr_xsk` (private-key) values** — the vector family covers public derivation too (`addr_xvk`), but 1.6c's narrowed scope (§Block 1.6c gate result) does not implement public derivation, so `addr_xvk` is reserved for the follow-up block. Tests decode the bech32 with `:core`'s generic `Bech32.decode` plus a test-only 5-bit-to-8-bit helper local to `crypto/jvmTest` (these HRPs are outside the `CardanoBech32` allowlist by design; `Bech32.convertBits` is `internal` to `:core`) |

Cross-link that strengthens 1.6d (usable once the public-key-derivation follow-up block
lands — see §Block 1.6c gate result; 1.6c itself does not derive a public key): the golden's
`addrXPub0` (`addr_xvk1w0l2sr2zgfm26ztc6nl9xy8ghsk5sh6ldwemlpmp9xylzy4dtf7...`) carries the
same 32 public-key bytes as the CIP-19 verification key `addr_vk1w0l2sr...st80zhd` already
pinned by the Block 1.5b-pre gate (ADR-0008 §7) — CIP-19's vectors are derived from this same
public mnemonic. So the 1.6d fixture wallet can restore this phrase, derive
`m/1852'/1815'/0'/0/0`, hash the derived public key with the existing `Hashing.blake2b224`,
and match the CIP-19 payment credential the 1.5b tests already pin. Two independent official
sources corroborate the same expected fingerprint.

### 5. Public API shape (signatures only; implemented in 1.6b/1.6c)

**Narrowed by the Block 1.6c gate result (below): `KeyDerivation.publicKey(...)` and
`ExtendedPublicKey` are NOT part of 1.6c's actual shape — the pinned backend has no
public-key-derivation primitive. They are deferred to a follow-up block. The signatures
below are left as originally planned, for historical context; see the gate result section
for what 1.6c actually implements.**

Package `org.sarmidev.kardano.crypto`. All failable operations return `KardanoResult` with
a typed sealed error and never throw across the Swift/ObjC boundary (ADR-0004 §6). No
backend type appears in any public signature.

```kotlin
// 1.6b — mnemonic boundary (opaque, input-only parse result)
public class Mnemonic private constructor(/* internal: entropy bytes */) {
    public val wordCount: Int
    public fun clear() // best-effort wipe; no memory guarantee (ADR-0004 §5)
    public companion object {
        /** Validates word count, wordlist membership, and checksum. English wordlist only. */
        public fun parse(words: List<String>): KardanoResult<Mnemonic, MnemonicError>
        public fun parse(phrase: String): KardanoResult<Mnemonic, MnemonicError>
    }
}

// 1.6b — Icarus master key (opaque handle over the 96-byte root extended key)
public class IcarusMasterKey private constructor(/* internal: 96 bytes */) {
    public fun clear()
    public companion object {
        public fun fromMnemonic(
            mnemonic: Mnemonic,
            passphrase: ByteArray = ByteArray(0),
        ): KardanoResult<IcarusMasterKey, KeyDerivationError>
    }
}

// 1.6c — CIP-1852 path model (SDK-owned value types; validation, no crypto)
public class Cip1852Path /* account (prime), role (0|1|2), index (soft) */

// 1.6c — derivation seam (ADR-0008 §2 pattern; adapter over the chosen backend)
public interface KeyDerivation {
    public fun derivePrivate(
        master: IcarusMasterKey,
        path: Cip1852Path,
    ): KardanoResult<ExtendedPrivateKey, KeyDerivationError>

    public fun publicKey(
        key: ExtendedPrivateKey,
    ): KardanoResult<ExtendedPublicKey, KeyDerivationError>

    public companion object { public fun default(): KeyDerivation }
}

// 1.6c — opaque extended-key handles (private constructors, defensive copies,
// content equality, structural toString that renders no key bytes)
public class ExtendedPrivateKey /* 64-byte key + 32-byte chain code, opaque */ { public fun clear() }
public class ExtendedPublicKey  /* 32-byte key + 32-byte chain code */ {
    /** The only raw-byte accessor in this block: the public key bytes (a copy), needed by 1.7 for credential hashing. */
    public fun publicKeyBytes(): ByteArray
}
```

The exact shape may be refined in 1.6b/1.6c within these constraints: opaque handles,
`KardanoResult` errors, no private-key byte accessor, backend-neutral names. Signing does
not appear anywhere in Block 1.6 (it is Block 1.10).

### 6. Error model: two new sealed, backend-neutral types

`CryptoError` stays hashing-scoped. Block 1.6 adds:

```kotlin
public sealed interface MnemonicError {
    public data class InvalidWordCount(public val count: Int) : MnemonicError   // not in {12,15,18,21,24}
    public data class WordNotInWordlist(public val position: Int) : MnemonicError // position only; never the word itself
    public data object ChecksumMismatch : MnemonicError
    public data class InvalidCharacters(public val position: Int) : MnemonicError // non-ASCII/uppercase input rejected, not normalized
}

public sealed interface KeyDerivationError {
    public data class InvalidKeyMaterial(public val expectedBytes: Int, public val actualBytes: Int) : KeyDerivationError
    public data class IndexOutOfRange(public val value: Long) : KeyDerivationError
    public data object SoftDerivationRequired : KeyDerivationError // public derivation asked for a prime index
    public data class DerivationFailed(public val message: String) : KeyDerivationError // mapped backend failure; carries no backend type
}
```

Variant lists may gain (not lose) precision in 1.6b/1.6c. Error payloads never contain
mnemonic words, entropy, seeds, or key bytes.

### 7. Key-material handling rules (applies ADR-0004 §5)

- Opaque handles with private constructors; construction only through validating factories.
- Defensive copy on construction and on every accessor; `contentEquals` /
  `contentHashCode` for byte comparisons; never `ByteArray ==`.
- **No public accessor returns private key bytes** in Block 1.6. The single raw-byte
  accessor is `ExtendedPublicKey.publicKeyBytes()` (a copy), required by Block 1.7 for
  credential hashing. If Block 1.10 (signing) needs private-key access, that block designs
  it explicitly; it is not pre-built here.
- `toString()` on every key-material type is structural and renders no bytes, no words,
  and no entropy.
- Mnemonics are **input-only parse results**: the words are consumed at the `parse`
  boundary, converted to entropy, and never echoed through `toString`, logs, error
  payloads, or any accessor.
- `clear()` is provided where the type owns secret bytes, documented as best-effort
  memory wiping with no guarantee about compiler, runtime, or GC behavior (ADR-0004 §5
  wording; on the JVM a zeroed backing array may not be the only copy).
- Secret material is held as `ByteArray`, not `String`, wherever the SDK controls the
  representation.

### 8. Mnemonic generation is deferred; Block 1.6 is restore-only

Generating a new mnemonic requires the platform CSPRNG decision (ADR-0004 §Randomness:
per-platform system CSPRNG, exact API recorded by the block that introduces key
generation). That decision is not made here. Block 1.6 restores from an existing phrase
only, which lets every 1.6 test and the 1.6d checkpoint run exclusively on public, cited
fixture vectors — no generated key material exists anywhere in the block.

**1.6d Android checkpoint scope (recorded now, implemented in 1.6d):** the Playground
restores the fixture wallet (the cited `test walk nut ...` public vector, clearly labeled
test-only) and shows **derived public metadata only**:

- the CIP-1852 derivation path used (e.g. `m/1852'/1815'/0'/0/0`),
- a Blake2b-224 fingerprint of the derived public key (via the existing `Hashing`),
  matching the CIP-19 payment credential pinned in 1.5b,
- a typed success/error state (invalid mnemonic input shows a `MnemonicError` without
  crashing).

The raw or hex public key is **not** displayed unless a later plan explicitly justifies
it. No private key bytes, no seed, no mnemonic words are rendered. No signing. Address
display belongs to Block 1.7 (which also requires the address-encoding ADR per
ADR-0005 §6).

---

> **Update (2026-07-12) — see [ADR-0010](0010-key-derivation-backend-swap-and-public-key-projection.md)
> for the current, superseding status.** The two items this ADR's Block 1.6c gate result left
> open are both closed there, with one correction: (1) **Android derivation is no longer
> blocked** — a coordinate swap to `org.hyperledger.identus:bip32-ed25519:1.8.8` (same wrapper
> API) was verified on real Android runtime; (2) `ExtendedPublicKey`/`KeyDerivation.publicKey`
> are now implemented and golden-vector-verified for JVM/iOS, but **Android public-key
> projection is a new, separate, open blocker** (a different backend's published Android
> native library is missing the needed symbol) — do not read this as fully resolved. This
> ADR's own findings below remain an accurate historical record of what was verified at the
> time; ADR-0010 is the current source of truth for 1.6c-follow-up status.

---

## Blockers (gates for the following subphases)

**1.6b may not start until all of these hold** (all pass as of this ADR except the marked
verification items, which 1.6b itself must close before its tests are written):

1. BIP-39 and CIP-3 vector families: **PASS** (§4).
2. Mnemonic model and error model fixed: **done** (§5, §6).
3. `To verify in 1.6b` (closes inside 1.6b, before wiring is accepted): cryptography-kotlin
   PBKDF2-SHA-512 provider coverage on JVM, Android (including API 24/25 vs the JCA
   `PBKDF2WithHmacSHA512` API-26+ concern), iosArm64, and iosSimulatorArm64. If it fails,
   use the recorded platform-seam fallback (§3) — do not hand-write PBKDF2.

**1.6c may not start until all of these hold:**

1. 1.6b complete (tests green against the cited vectors).
2. Ed25519-BIP32/CIP-1852 vector family: **PASS** (§4).
3. `To verify in 1.6c` (closes inside 1.6c): `bip32-ed25519` input/output byte layouts and
   derivation-scheme version (V2/Icarus) confirmed against the cited golden vectors;
   Android runtime loading of the bundled native library (`testAndroidHostTest` at
   minimum); iosSimulatorArm64 compile **and link** (the 1.5a spike proved compile only —
   the Rust-derived static library link is unproven). An iOS link failure reopens this
   ADR's dependency decision and falls back per ADR-0008 §4's order.

**Result, recorded in full below (§Block 1.6c gate result): item 3 closed with two
blockers, both resolved by an explicit scope/risk decision rather than by an ADR-0008 §4
fallback** — no public-key-derivation primitive exists in the pinned backend (narrows 1.6c
to private derivation only), and the published Android artifact ships no native library, so
`deriveBytes` (the call `derivePrivate` makes) throws a confirmed `UnsatisfiedLinkError`
under `:crypto:testAndroidHostTest`. **1.6c's own JVM/iOS scope is not gated on Android by
this decision, but Android derivation itself is blocked, not merely an open risk — this is
a reproduced failure, not an absence of verification.** JVM is the verified target for
1.6c; iOS compile-and-link **passed**.

**1.6d may not start until** 1.6c's JVM-verified private-derivation output reproduces the
cited golden vectors (done). **1.6d's own Android checkpoint is blocked, not merely
carrying an open risk forward**, until Android on-device/emulator verification either
disproves the reproduced `UnsatisfiedLinkError` or an Android-capable alternative is found;
1.6d's fingerprint-display step is separately blocked on the public-key-derivation
follow-up block (Blake2b-224 of the *public* key — 1.6c produces only the private key).
Neither blocker prevents 1.6d from *starting* its non-Android path-derivation/error-state
work.

---

## Block 1.6b gate result — PBKDF2 platform-seam fallback (closes the `To verify in 1.6b` item)

Before accepting any Icarus master-key wiring, §Blockers item 3 required verifying
cryptography-kotlin `0.6.0`'s PBKDF2-HMAC-SHA-512 coverage on JVM, Android (including the
API 24/25 vs JCA API-26+ concern), iosArm64, and iosSimulatorArm64 — against the published
artifact, not documentation claims, per the 1.5b-style discipline this ADR's intro invokes.

**Verification method:** direct read of the pinned `cryptography-kotlin` `0.6.0` source
(`whyoleg/cryptography-kotlin`, tag `0.6.0`), not README/docs-site claims.

**Findings:**

- `PBKDF2.secretDerivation(digest, iterations, outputSize, salt: ByteArray)` takes a raw
  `ByteArray` salt — the Icarus entropy-bytes salt is expressible. This part of the ADR's
  provisional lead is confirmed.
- JVM (`JdkPbkdf2`): calls `javax.crypto.SecretKeyFactory.getInstance("PBKDF2WithHmac$digest")`
  — i.e. JCA. `PBKDF2WithHmacSHA512` is present on desktop JDK 8+.
- iOS (`CCPbkdf2`): calls `platform.CoreCrypto.CCKeyDerivationPBKDF` directly (no JCA
  dependency). Compiles.
- **Android — fails the gate.** The JDK provider is the only cryptography-kotlin provider
  applicable to Android, and it routes through the same JCA
  `SecretKeyFactory.getInstance("PBKDF2WithHmacSHA512")` call as the JVM path. Per the Android
  `SecretKeyFactory` algorithm table, `PBKDF2withHmacSHA512` is available starting API level 26;
  this repository's `minSdk = 24` (`gradle/libs.versions.toml`). On a real API 24/25 device this
  call throws `NoSuchAlgorithmException`. **`:crypto:testAndroidHostTest` cannot detect this
  failure**, because Android host tests run on the local host JVM (which does have the
  algorithm) rather than an emulator/device at the target API level — a green host-test run
  would give false confidence, not gate closure.
- No `org.kotlincrypto.*` PBKDF2/KDF module exists (checked the Maven Central group listing) as
  a same-family drop-in replacement.

**Outcome: the cryptography-kotlin PBKDF2 path does not pass the gate for Android.** Per
§Blockers item 3 and §3 ("If it fails, use the recorded platform-seam fallback (§3) — do not
hand-write PBKDF2"), Block 1.6b adopts the documented platform-seam fallback instead of
cryptography-kotlin:

| Target | PBKDF2-HMAC-SHA-512 backend | Notes |
|--------|------------------------------|-------|
| JVM + Android | BouncyCastle `PKCS5S2ParametersGenerator` with `SHA512Digest` (`org.bouncycastle:bcprov-jdk18on`, pinned version) | Does not call JCA `SecretKeyFactory`; not subject to the Android API-26 `PBKDF2withHmacSHA512` restriction. Raw `ByteArray` password and salt. |
| iosArm64 / iosSimulatorArm64 | Apple `CCKeyDerivationPBKDF` with `kCCPRFHmacAlgSHA512`, reached through the `kardano_ccpbkdf2_hmac_sha512` interop shim in `pbkdf2raw.def` (see the cinterop addendum below) | Raw-byte APIs; no JCA involved. |

**Passphrase byte handling (all targets).** The Icarus PBKDF2 password is the raw passphrase
bytes (§2); no target decodes the passphrase to or from `String`/UTF-8. On iOS the CommonCrypto
binding is called with a pinned raw pointer to the passphrase `ByteArray`, not a `String`
argument, so no platform-specific passphrase behavior is introduced across the seam.

**Consequence.** Block 1.6b adds `org.bouncycastle:bcprov-jdk18on` (pinned, JVM+Android source
sets only) instead of `dev.whyoleg.cryptography:cryptography-*`; `cryptography-kotlin` is not
added to this repository. The SDK-owned data-handling classification (§3.1) is unchanged: PBKDF2
itself remains delegated (now to BouncyCastle / Apple CommonCrypto rather than
cryptography-kotlin), and the CIP-3 `tweakBits` bit-masking around it stays SDK-owned.

### Addendum — iOS cinterop: from `noStringConversion` to an inline C shim

The shipped Kotlin/Native `platform.CoreCrypto.CCKeyDerivationPBKDF` binding maps its
`password` parameter to `String` (the default cinterop heuristic for `const char *`), which
cannot carry raw, possibly non-UTF-8 passphrase bytes. Two approaches were tried, in this
order:

1. **`noStringConversion` directly on `CCKeyDerivationPBKDF`** via a custom `.def`
   (`modules = CommonCrypto`, mirroring JetBrains' own shipped
   `platformLibs/src/platform/ios/CommonCrypto.def`). This produced a cinterop klib with the
   target package but **zero declarations** in this repository's build environment — confirmed
   with `klib dump-metadata`, and reproduced even after removing `-fmodules` to match the
   shipped `.def` exactly.
2. **An inline C interop shim**, defined in `pbkdf2raw.def`'s own glue block (below the `---`
   separator): `kardano_ccpbkdf2_hmac_sha512(const uint8_t *password, size_t password_len,
   const uint8_t *salt, size_t salt_len, unsigned int rounds, uint8_t *derived_key, size_t
   derived_key_len)`, with explicit `<stdint.h>`, `<stddef.h>`, and
   `<CommonCrypto/CommonKeyDerivation.h>` includes. It casts `password` to `const char *` only
   at the call boundary to `CCKeyDerivationPBKDF` and delegates the entire derivation to it —
   no PBKDF2 logic is implemented in the shim. This was the fix: `klib dump-metadata` confirmed
   `kardano_ccpbkdf2_hmac_sha512` bound with `password` as `CValuesRef<UByteVarOf<UByte>>?`
   (raw bytes, not `String`) before the `iosArm64Main`/`iosSimulatorArm64Main` actuals were
   updated to call it with pinned pointers. The plain `static int` form of the shim bound
   correctly; no escalation to `static inline int` or an explicit header-shim file was needed.

**Result: `:crypto:compileKotlinIosSimulatorArm64` and `:crypto:compileKotlinIosArm64` both
pass.** This closes the iOS *compile* gap only. **iOS runtime execution of the CIP-3/BIP-39
vectors is still future verification** — no iOS-simulator/device test run has exercised this
binding; only `:crypto:jvmTest` and `:crypto:testAndroidHostTest` have executed the cited
vectors so far.

---

## Block 1.6c gate result — private-derivation-only scope, Android derivation blocked (closes the `To verify in 1.6c` item)

Before accepting any `KeyDerivation` wiring, §Blockers item 3 required verifying
`dev.allain:bip32-ed25519:2.3.0`'s exact input/output byte layouts, its derivation-scheme
version, Android runtime loading, and iOS compile-and-link — against the actually published
artifacts, not README/matrix claims, per this ADR's own discipline.

**Verification method.** Added the dependency to `:crypto` on a throwaway basis (reverted
before this block's real diff), then: `javap -p -v` on the resolved
`bip32-ed25519-jvm-2.3.0.jar` (top-level functions, `UniffiLib`'s native ABI bindings, and the
constant pool); `unzip -l` on the resolved `bip32-ed25519-android` AAR; a probe source file in
`commonMain` calling the wrapper's functions directly, compiled for all four targets; a probe
test in `commonTest`/`jvmTest` actually invoking `deriveBytes`/`deriveBytesPub`/
`fromNonextended` and printing the live result map; `:crypto:testAndroidHostTest` against that
probe; and `:crypto:linkDebugTestIosSimulatorArm64` (an actual test-binary link, not just a
compile).

**Findings — passed cleanly:**

- **Resolution:** resolves on JVM, Android, iosArm64, iosSimulatorArm64 via Gradle's KMP
  variant selection; no target-specific coordinates needed in `crypto/build.gradle.kts`.
- **API location — Design A confirmed:** `deriveBytes`, `deriveBytesPub`, and
  `fromNonextended` (package `uniffi.ed25519_bip32_wrapper`) are directly callable from
  `:crypto`'s `commonMain` on every target. No `expect`/`actual` seam is needed for this
  dependency, unlike the PBKDF2 platform seam (§ above).
- **Index parameter type:** Kotlin `UInt` (confirmed by the mangled JVM signature
  `deriveBytes-jXDDuk8`, a Kotlin inline-value-class name-mangling artifact, and by actually
  calling `deriveBytes(sk, cc, 0x8000_0000u)` successfully). A prime index is a plain
  `(offset + n).toUInt()`; no signed-`Int` two's-complement bit-pattern conversion is needed
  anywhere in this SDK.
- **`deriveBytes(sk: ByteArray, cc: ByteArray, index: UInt): Map<String, ByteArray>`** →
  exactly `{"secret_key": 64 bytes, "chain_code": 32 bytes}` (runtime-verified via an actual
  call, keys and lengths printed from the live result, not inferred from bytecode).
- **`deriveBytesPub(pk: ByteArray, cc: ByteArray, index: UInt): Map<String, ByteArray>`** →
  exactly `{"public_key": 32 bytes, "chain_code": 32 bytes}`; throws
  `uniffi.ed25519_bip32_wrapper.DerivationException.ExpectedSoftDerivation` on a prime index
  (runtime-verified).
- **`fromNonextended(key: ByteArray, cc: ByteArray): Map<String, ByteArray>`** →
  `{"secret_key": 64 bytes, "chain_code": 32 bytes}` — a 32-byte-seed expansion, not a
  private-to-public projection; confirmed not needed for the Icarus path (the CIP-3 root is
  already the 96-byte extended form).
- **Derivation-scheme version:** V2/Icarus-only by design — the underlying Rust
  `ed25519-bip32` crate has no `V1` variant to silently regress to.
- **iOS compile and link — passes, closing the item this ADR's §Blockers explicitly left
  open.** `compileKotlinIosSimulatorArm64`, `compileKotlinIosArm64`, and
  `linkDebugTestIosSimulatorArm64` (an actual test-binary link against the Rust-derived
  static library) all succeeded. No iOS simulator was available in the verification
  environment to run the linked binary, so iOS *runtime* execution of the golden vectors
  stays future work, the same status as the 1.6b PBKDF2 result above.

**Finding — Blocker 1: no public-key-from-private-key primitive exists in this dependency.**
`javap -p` on `UniffiLib` (the JNA native-ABI interface) shows exactly three real bound
functions: `derive_bytes`, `derive_bytes_pub`, `from_nonextended` (plus generic
uniffi/rust-future/buffer plumbing). None of them projects a private or extended private key
to its public key: `deriveBytes` is private-child-from-private-parent, `deriveBytesPub` is
public-child-from-*already-known*-public-parent (it needs a public key as input, not just a
private one), and `fromNonextended` is seed expansion. The resolved JVM jar contains no
class outside the `uniffi.ed25519_bip32_wrapper` package, so there is no separate keypair
utility either. This is exactly the risk this ADR's 1.6c planning flagged as the "highest"
risk before implementation — now confirmed, not hypothetical.

**Finding — Blocker 2: the published `bip32-ed25519-android` artifact ships no native
library.** `unzip -l` on the resolved `bip32-ed25519-android-2.3.0.aar` shows only
`classes.jar`, `AndroidManifest.xml`, and `R.txt` — no `jni/<abi>/*.so` anywhere. Calling any
of the three wrapper functions under `:crypto:testAndroidHostTest` threw
`java.lang.UnsatisfiedLinkError` for all three, before this block's real diff removed the
backend-calling tests from any source set that Android host test runs. The AAR's POM
declares a runtime dependency on the plain desktop `net.java.dev.jna:jna:5.13.0` (which
bundles Windows/Linux/macOS natives, not Android), reinforcing that Android support looks
incomplete as published rather than merely untested. No Android emulator or device was
available in the verification environment, so this is not a fully on-device-confirmed
verdict — only a confirmed absence of any native binary in the resolved artifact graph plus a
confirmed host-JVM load failure.

**Decision (reported to the project owner; both explicitly approved before any 1.6c
wrapper-facing code was written):**

1. **Narrow 1.6c to private derivation only.** `KeyDerivation` has a single method,
   `derivePrivate(master, path): KardanoResult<ExtendedPrivateKey, KeyDerivationError>`.
   There is no `publicKey()`, no `ExtendedPublicKey`, and no `derivePublicSoft`/public-soft
   derivation in this block. `ExtendedPublicKey`/`publicKey()`/the `addr_xvk` vectors in §4
   are deferred to a follow-up block, which must make its own dependency decision for an
   Ed25519 "public key from a clamped 32-byte scalar" primitive (standard Ed25519 keypair
   derivation, not BIP32-specific — still a delegated cryptographic primitive per ADR-0004,
   not something to hand-roll) before it can close. `KeyDerivationError.SoftDerivationRequired`
   stays defined (no variant removed) but is not exercised by this block's public surface;
   [Bip32Ed25519KeyDerivation](../../crypto/src/commonMain/kotlin/org/sarmidev/kardano/crypto/Bip32Ed25519KeyDerivation.kt)'s
   `mapThrowable` still maps `DerivationException.ExpectedSoftDerivation` to it defensively,
   and this mapping is unit-tested directly (with a synthetic exception, no native call) so
   the follow-up block inherits a proven mapping.
2. **Proceed with JVM as the verified target for 1.6c's own scope; Android derivation is
   blocked for this dependency, not merely an open risk.** `:crypto:jvmTest` exercises every
   cited golden vector. `:crypto:testAndroidHostTest` passes because — after this decision —
   no backend-calling test lives in a source set Android host test runs
   (`commonTest`/`androidHostTest`); the vector-execution tests moved to `crypto/src/jvmTest`
   specifically because of this finding, with a comment citing it. This is a scope decision
   about what 1.6c itself must prove to be usable on JVM/iOS — it does **not** mean Android
   derivation is considered working: `KeyDerivation.derivePrivate` currently throws
   `UnsatisfiedLinkError` on Android, a confirmed failure. A real device/emulator run of the
   private-derivation vectors is recorded as follow-up work (§Follow-up work) that could
   disprove this; until it does, no code or documentation in this repository should describe
   Android derivation as supported, working, or merely "at risk." If that follow-up run
   reproduces the same `UnsatisfiedLinkError` on-device, this reopens the ADR-0008 §4
   fallback dependency decision for Android specifically — the same escalation path an iOS
   link failure would have triggered here.

**Consequence for 1.6d (§8):** 1.6d's Playground checkpoint needs a Blake2b-224 fingerprint
of the *derived public key*. 1.6c alone cannot produce that key (Blocker 1), so 1.6d cannot
finish its checkpoint until the public-key-derivation follow-up block lands, even though
1.6d *can* start on top of 1.6c's private-derivation path and path/error-state UI work.
**1.6d's own Android checkpoint is blocked, not merely at-risk:** it depends on the same
`KeyDerivation.derivePrivate` call that is confirmed broken on Android, so the checkpoint
cannot be demonstrated on Android until the follow-up device/emulator run either disproves
that failure or an Android-capable alternative is adopted.

---

## Relationship to ADR-0004 and ADR-0008

- ADR-0004 remains the governing strategy: no handwritten crypto (§3.1 records the
  data-handling classification this ADR relies on), key-material lifecycle (§7 applies it),
  error policy (§5/§6 apply it), test-vector policy (§4 applies it).
- ADR-0008's module/seam/process decisions carry forward unchanged. This ADR **corrects
  one expectation** the same way ADR-0008 §8 corrected the Blake2b row: the main Apollo
  artifact does not enter Block 1.6 either — its mnemonic and PBKDF2 APIs do not fit the
  Cardano Icarus path (findings A/B). The Ed25519-BIP32 capability arrives through the
  standalone `dev.allain:bip32-ed25519` artifact instead. ADR-0008 gains a short
  cross-reference note; its candidate matrix is otherwise historical.

---

## Consequences

- 1.6b has an actionable start: SDK-owned mnemonic validation (wordlist + checksum via
  KotlinCrypto `sha2`), Icarus master key via a byte-salt PBKDF2 backend, tests against the
  Trezor and CIP-3 vectors — roughly the size and shape of the 1.5b hashing block.
- 1.6c is a thin adapter over one verified wrapper function (`deriveBytes`) plus SDK-owned
  path types, tested against the cardano-addresses goldens on JVM. Public-key derivation is
  out of scope for 1.6c (§Block 1.6c gate result); a follow-up block picks it up.
- 1.6d needs no new external dependency for its private-derivation-path UI, but two of its
  pieces are blocked, not merely open: its fingerprint-display checkpoint (§8) cannot finish
  until the public-key-derivation follow-up block lands, and its Android checkpoint cannot
  run until Android derivation of this dependency is confirmed working (or replaced);
  `:shared` still only needs a project dependency on `:crypto` and a Playground section
  limited to public metadata.
- The main Apollo artifact's remaining candidacy is narrowed to Block 1.10 (signing), to be
  re-evaluated there with the same published-artifact discipline.

---

## Non-goals

- No implementation, dependency addition, or Kotlin/Gradle/module change in 1.6a (this
  ADR is docs-only; no compile probe was needed — all API checks ran against published
  artifacts and pinned source tags outside the repository).
- No transaction signing, no transaction building, no address generation (Block 1.7),
  no wallet persistence.
- No mnemonic generation and no CSPRNG selection.
- No real mnemonics, private keys, or funds — the only phrases in Block 1.6 are the
  public, cited test vectors in §4, copied verbatim.
- No Byron/Ledger/Trezor scheme variants, no non-English wordlists.
- No claim of fitness, review status, or completeness for any third-party library.

---

## Follow-up work

- Block 1.6b: implement §2 + §5 (mnemonic + Icarus master key), close the §Blockers
  verification items, add the cited vectors, record the outcome in a result section here
  (ADR-0008 §6–§8 pattern).
- Block 1.6c: implemented the `KeyDerivation` seam (private derivation only) + CIP-1852 path
  types over `bip32-ed25519`; gate result and narrowed-scope decision recorded above.
- **New, opened by the 1.6c gate result:** a public-key-derivation block. Needs its own
  dependency decision for an Ed25519 "public key from a clamped 32-byte scalar" primitive
  (delegated per ADR-0004, not hand-rolled), then adds `ExtendedPublicKey`,
  `KeyDerivation.publicKey(...)`, and the `addr_xvk`/CIP-19-cross-link vectors from §4.
  Gates 1.6d's fingerprint checkpoint.
- **New, opened by the 1.6c gate result, and currently blocking 1.6d's Android
  checkpoint:** Android on-device/emulator verification of
  `dev.allain:bip32-ed25519:2.3.0`'s private-derivation vectors, to confirm or rule out
  Android viability for this dependency beyond the host-JVM-confirmed `UnsatisfiedLinkError`
  recorded above. Until this closes (by disproving the failure) or an Android-capable
  alternative is adopted, Android derivation for this dependency stays blocked — this
  reopens the ADR-0008 §4 fallback dependency decision for Android specifically if the
  on-device run reproduces the same failure.
- Block 1.6d: fixture wallet + Playground checkpoint per §8; record the owner-verified
  checkpoint in `docs/PHASE_1_PLAN.md`. Can start now on the non-Android
  private-derivation path and error-state UI; its fingerprint step and its Android
  checkpoint are both blocked on the two follow-ups directly above, not merely open items.
- Block 1.10 (signing) re-evaluates the signing backend (Apollo, the same wrapper stack,
  or another candidate) with published-artifact verification.
