# ADR-0016: Transaction Signing Backend & Vector-Source Gate

| Field   | Value                                                                 |
|---------|------------------------------------------------------------------------|
| Status  | **Accepted** (Block 1.10b-pre gate result). **Gate result: BLOCKED** — an extended Ed25519-BIP32 signature known-answer test (KAT) is pinned, but no *resolved or currently-published* all-target KMP backend can sign a Cardano extended key; a concrete unblock path is identified. Docs-only; authorizes no signing code and no Gradle/dependency change. |
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

**BLOCKED, with the extended-key KAT pinned and a concrete unblock path identified.**

- **KAT: PASS.** A citable, unambiguous **extended** Ed25519-BIP32 signature known-answer vector
  is pinned (§3) — from the reference implementation (`ed25519-bip32` crate, cited by CIP-3).
- **Backend: BLOCKED.** **No currently-resolved or currently-published KMP artifact exposes
  extended-key signing across all targets** (§1). A viable, evidence-backed backend *path* exists
  (§2) — expose the reference crate's `XPrv::sign` through the same uniffi mechanism already used
  for derivation — but it is **not a resolved artifact today**: it requires a backend-provisioning
  task (build/publish or adopt a wrapper that exports `sign`) plus real-runtime verification, both
  of which are outside this docs-only block and gate ADR-0015 §4's PASS condition (Android runtime
  verification required before code is accepted).

Therefore **Block 1.10b (signing implementation) stays blocked.** The immediate next task is a
scoped backend-provisioning task (§2, §5), not signing code.

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

### 3. Vector source — pinned extended-key KAT (PASS)

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
"must be an extended-key KAT" pass condition. The message here is 11 bytes rather than a 32-byte
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
by this docs-only block. Before Block 1.10b begins, it should be reconciled once to reflect that
the signing backend gate landed **BLOCKED with a pinned KAT** (not PASS) and that signing
implementation additionally depends on a separately-authorized backend-provisioning task — so the
agreement's signing-related wording matches ADR-0015 §4 and this ADR. That reconciliation is a
docs edit to schedule at the start of 1.10b, not part of this gate.

---

## Consequences

- **Block 1.10b remains blocked.** No signing code and no dependency/Gradle change is authorized.
  The next task is backend provisioning (§2/§5), not `:crypto`/`:tx`/`:wallet` signing code.
- The extended-key KAT is now pinned (§3), so once a backend exists, the KAT and target-coverage
  plan (§4) can be applied immediately without re-litigating the vector.
- ADR-0015 §4/§6 are satisfied on the vector requirement and updated to reference this ADR for the
  gate outcome; §4's backend PASS condition is **not yet met**.
- The reference-crate provenance also confirms the current derivation backend and a future signing
  backend can share one Rust crate (`ed25519-bip32`) exposed via one uniffi mechanism.

## Non-goals

- No signing implementation; no witness/transaction assembly; no `:shared` checkpoint code.
- No Gradle or dependency change; no dependency is pinned by this block (§5 lists candidates only).
- No mainnet; no real mnemonics, private keys, or funds; no native assets, scripts, metadata,
  multisig, or general-purpose/user-supplied wallet signing.
- No handwritten cryptography; no acceptance of a plain (seed-based) Ed25519 vector as the gate KAT.
- No readiness, external-review, or audit claim.

## Follow-up work

- **Backend-provisioning task (new, blocking, requires its own Gradle/dependency authorization):**
  obtain a wrapper that exports extended `sign`/`verify` (§2/§5), confirm it at symbol level, then
  verify it per §4 (JVM + Android real runtime + iOS compile/link).
- **Reconcile `docs/AI_WORKING_AGREEMENT.md`** at the start of 1.10b (§6).
- **Block 1.10b** implements ADR-0015 §1/§3/§5/§6 only after the provisioned backend is verified
  and named.
- **Block 1.10c** wires the `:shared` "Signed Transaction (not submitted)" checkpoint.
- ADR-0004 (crypto strategy), ADR-0009/ADR-0010 (derivation/projection + key-material rules), and
  ADR-0015 (transaction signing) remain the governing decisions this gate builds on; this ADR does
  not supersede them.
