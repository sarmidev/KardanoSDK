# ADR-0015: Transaction Signing

| Field   | Value                                                                 |
|---------|------------------------------------------------------------------------|
| Status  | **Accepted**; Block 1.10b (`:crypto` `Signing`, `:tx` witness/transaction assembly, `:wallet` signing orchestration) **implemented and verified** — see §9 result note. Block 1.10c (Playground checkpoint) remains open. |
| Scope   | Block 1.10a — signing ownership/module boundary, exact signing scope, fixture-only enforcement boundary, signing message, signing artifact, crypto-backend gate, error model, test/vector policy, Playground checkpoint, guardrail reconciliation, sub-block split |
| Phase   | Phase 1 (Block 1.10a/1.10b)                                            |
| Updated | 2026-08-23 — §2a enforcement amended by ADR-0019; original §2a text left as the Block 1.10 decision. |

---

## Context

By the end of Block 1.9, the read-and-build path is complete without any signing: `:tx` builds
an unsigned ADA-only `transaction_body`, selects inputs largest-first, estimates a fee, handles
change/min-UTxO, and emits the canonical body CBOR through `:core`'s unchanged definite-length
subset (ADR-0014); `:wallet` restores the cited test-only wallet, derives its CIP-1852 payment
and stake keys, generates a testnet base address, and sums an ADA-only balance from a
caller-supplied `ChainQueryProvider` (ADR-0013); `:crypto` exposes Blake2b-224/256 hashing,
Icarus/CIP-3 mnemonic restore, and CIP-1852 Ed25519-BIP32 private derivation plus public-key
projection (ADR-0009/ADR-0010). The Android checkpoint for the unsigned draft (Block 1.9c) was
verified manually on preprod.

Block 1.10 (Transaction Signing) is the first block authorized to introduce signing. The
standing guardrail (`docs/AI_WORKING_AGREEMENT.md` and
`.cursor/rules/kardano-sdk-guardrails.mdc`) has, from Phase 0 onward, disallowed transaction
signing and said it "may be introduced only when a future explicit block/ADR (planned for
Phase 1 Block 1.10) updates this rule with its own scoped signing API and dependency decision."
This ADR is that block/ADR. It follows the pre-implementation pattern of ADR-0012 (Block 1.7a),
ADR-0013 (Block 1.8a), and ADR-0014 (Block 1.9a): record the decision first, then split the
implementation into gated `b-pre`/`b`/`c` sub-blocks. **Block 1.10a is docs-only and authorizes
no signing code.** Signing code is additionally gated on the Block 1.10b-pre backend/vector gate
(§4) passing.

The remaining hard rules stand and are re-affirmed for this block: no mainnet; no real
mnemonics, private keys, or funds; no handwritten cryptographic algorithm (signing must delegate
to a verified backend, ADR-0004 §3.1); no readiness/audit claims; typed errors with no throwing
across the Swift/ObjC boundary; ByteArray defensive-copy/`contentEquals` discipline; and no
Gradle/dependency change is authorized by this ADR (dependency selection is deferred to the
Block 1.10b-pre gate).

### Key material and backend facts this ADR is built on

- `:crypto`'s `ExtendedPrivateKey` is an opaque handle with **no public private-key byte
  accessor** (ADR-0009 §7); it currently exposes only an internal `leftScalarAndChainCode()`
  (left 32-byte scalar `kL` + chain code, used by public-key projection) and an internal
  test-only `xskBytesForTesting()`. Cardano/Ed25519-BIP32 signing needs the **full 64-byte
  extended scalar** (`kL` ‖ `kR`), so Block 1.10b will add a second module-internal accessor for
  the signing backend — still with no public private-key byte accessor.
- `KeyDerivation.publicKey(...)` already yields the 32-byte public key (the vkey) needed for the
  witness, verified on JVM/Android runtime and iOS compile/link (ADR-0010).
- `Hashing.blake2b256` already exists in `:crypto` (Block 1.5b), so the body hash / transaction
  id needs no new crypto primitive.
- **Signing backend gap (verified from resolved Gradle artifacts, not documentation):** the
  pinned Ed25519-BIP32 backend `org.hyperledger.identus:bip32-ed25519:1.8.8` (uniffi wrapper
  `uniffi.ed25519_bip32_wrapper`) exposes **only** `deriveBytes`, `deriveBytesPub`, and
  `fromNonextended` — it has **no signing function**. `org.hyperledger.identus:apollo-jvm:1.8.8`
  contains no extended Ed25519-BIP32 signing class. libsodium's `crypto_sign_*` expands a 32-byte
  seed via SHA-512 and cannot sign a **pre-expanded** 64-byte extended scalar, so the libsodium
  bindings already in `:crypto` (Ionspin on JVM/iOS, lazysodium on Android) cannot sign a Cardano
  extended key either. Composing the Ed25519-BIP32 signature equation from scalar/hash primitives
  would be a handwritten cryptographic algorithm, which ADR-0004 §3.1 bans. **Therefore no
  currently-shipped dependency can produce a Cardano extended-key signature, and the backend must
  be resolved by an explicit gate (§4) before any signing code is written.**

---

## Decision

### 1. Signing responsibilities split across existing modules; no new module is created

Signing decomposes into three distinct concerns, each of which maps cleanly onto an existing
module's existing responsibility, so **no new Gradle module is created** (this is not the
ADR-0009 §1 / ADR-0002 extraction trigger: there is no dependency direction that an existing
module cannot host):

- **`:crypto` owns the cryptographic signing primitive.** A new backend-neutral `Signing`
  interface signs a message with an `ExtendedPrivateKey` and returns a 64-byte Ed25519 signature,
  mirroring the existing `Hashing` / `KeyDerivation` seam pattern (a `default()` factory over a
  swappable internal adapter; no backend type in any public signature). `ExtendedPrivateKey`
  gains a **module-internal** full-extended-scalar accessor (`kL` ‖ `kR`) for the signing
  adapter only; the "no public private-key byte accessor" rule (ADR-0009 §7) is preserved. This
  keeps all cryptography isolated inside `:crypto` (ADR-0004).
- **`:tx` owns witness-set and full-`transaction` CBOR assembly, and stays crypto-free.** `:tx`
  assembles a `transaction_witness_set` and the full `transaction` array from **already-computed**
  `(vkey, signature)` pairs supplied by the caller. Building CBOR from given bytes needs no
  cryptography, so `:tx` keeps its ADR-0014 §1 dependency set (`:core` + `:provider` only) and
  does **not** gain a `:crypto` dependency. Keeping `:tx` crypto-free remains the correct
  separation.
- **`:wallet` owns the signing orchestration, through an explicitly-scoped entry point — not a
  general-purpose wallet signing API.** `:wallet` already holds the private-key lifecycle and
  depends on `:core` + `:crypto` + `:provider` (ADR-0013). Block 1.10b adds a **`:wallet →
  :tx`** dependency (a new, acyclic edge: `:wallet` → `:tx` → `:core`/`:provider`) so `:wallet`
  can compose the full flow — derive the payment key, hash the body, sign the hash, assemble the
  witness/full transaction — behind one wallet-level entry point that takes the same explicit
  `(words, network)` shape `ReadOnlyWallet.restore` already takes, plus a `TransactionDraft` to
  sign. `:wallet` has **no dependency on `:shared`** and therefore cannot reference `:shared`'s
  `TestWalletFixture` directly — see §2a for how the Block 1.10 fixture-only scope is actually
  enforced given that constraint.
- **`:shared` implements no signing logic.** As with every prior checkpoint (ADR-0011 §3),
  `:shared` only calls the SDK and displays results; it performs no derivation, hashing, signing,
  or CBOR assembly of its own.

Why no new module: the three concerns above are each a natural extension of a module that already
exists for exactly that concern (crypto in `:crypto`, transaction serialization in `:tx`, key
lifecycle + orchestration in `:wallet`). Introducing a `:signing` module would either duplicate
`:crypto`'s crypto ownership or `:wallet`'s orchestration ownership, or force a circular/awkward
dependency, with no boundary benefit.

### 2. Exact signing scope for Block 1.10

Block 1.10 signs **only**:

- **Testnet/preprod only.** The wallet-level signing entry point restores and signs on
  `Network.TESTNET` only and rejects any other network; there is no mainnet path.
- **The existing test-fixture / restored-wallet path already used in Phase 1** — the cited
  test-only mnemonic behind `TestWalletFixture` / `ReadOnlyWallet.restore(...)`. No arbitrary or
  user-supplied wallet, no real mnemonic, no real key. **This is a call-site scope, not a
  `:wallet`-internal check** — `:wallet` cannot itself recognize "this is the fixture" (see §2a
  for how it is actually enforced).
- **ADA-only single-payment drafts produced by `TransactionBuilder`** — the exact
  `TransactionDraft` shape Block 1.9 already produces (one payment output, optional change
  output, computed fee, optional ttl).

Out of scope for Block 1.10 (each deferred to its own later block/phase): mainnet; any
non-fixture / user-supplied wallet; native assets / multi-asset values; native or Plutus scripts
and script witnesses; metadata / auxiliary data; multisig / multiple distinct signing keys;
certificates; withdrawals; collateral; datums; reference inputs; minting; required signers;
Byron witnesses; and hardware-wallet signing.

### 2a. Enforcement boundary: fixture-only scope is a Phase 1 call-site policy, not a `:wallet`-internal check

`:wallet` cannot depend on `:shared` (ADR-0011 §3: `:shared` is the sample/UI host and may only
call SDK modules, never the reverse), so `:wallet`'s signing entry point cannot import or
special-case `:shared`'s `TestWalletFixture`. §1 places signing orchestration inside `:wallet`
and §2 restricts Block 1.10 to the existing test fixture; this subsection reconciles the two so
the ADR does not read as if `:wallet` itself somehow recognizes the fixture, which is
architecturally impossible given the fixed module boundary.

**Block 1.10 must not introduce a general-purpose wallet signing API.** `:wallet`'s signing entry
point takes the same explicit-input shape `ReadOnlyWallet.restore(words, network)` already takes
(mnemonic words + `Network`), plus a `TransactionDraft` to sign — it is a narrow extension of the
existing read-only API shape (ADR-0013), not a new "sign anything for anyone" surface. Its public
KDoc **must** state that Block 1.10 authorizes this entry point only for the Phase 1 testnet test
fixture flow and ADA-only `TransactionBuilder` drafts (§2), and must **not** describe or imply
support for an arbitrary, user-supplied, or general-purpose wallet, or for a non-`TransactionBuilder`
draft.

**Enforcement therefore lives at the Phase 1 call sites/checkpoint/tests, not inside `:wallet`'s
type signature or runtime logic:** the `:shared` Playground checkpoint (§7) and any test that
exercises real signing pass in the cited `TestWalletFixture` words/path and `Network.TESTNET`
explicitly — the same pattern `ReadOnlyWallet.restore` callers already follow in Blocks
1.8b/1.9c. `:wallet` accepts whatever words/network/draft it is given (it has no way to verify
"this mnemonic is the Phase 1 fixture" without depending on `:shared`), so the fixture-only
guarantee is a **call-site and test-suite discipline**, not a `:wallet`-enforced runtime
invariant. Docs, KDoc, and Playground copy must never present this capability as arbitrary or
general-purpose wallet signing — every description must name the Phase 1 test fixture and
`Network.TESTNET` explicitly.

**Any future public/general-purpose wallet signing** — an arbitrary caller-supplied mnemonic, a
mainnet path, or a non-`TransactionBuilder` draft — is out of scope for Block 1.10 and requires
its own later, explicit ADR/block, mirroring the same "explicit block/ADR" gate the standing
guardrail already required before Block 1.10 could introduce signing at all.

### 3. Signing artifact and the exact signing message

**Signing message (explicit).** The message that is signed is the **transaction body hash**, not
the raw body bytes:

- `bodyHash = Blake2b-256(TransactionDraft.bodyCbor())` — a **32-byte** value. This is exactly
  the Cardano transaction id.
- **Ed25519-BIP32 signs the 32-byte `bodyHash`.** It must **not** sign the raw `transaction_body`
  CBOR bytes directly. (Cardano vkey witnesses are signatures over the blake2b-256 hash of the
  transaction body; signing the raw body bytes would produce an invalid witness.)
- The **transaction id is the same `bodyHash`** — `:wallet`/the caller computes it once via
  `:crypto` `Hashing.blake2b256(draft.bodyCbor())` and both signs it and reports it as the id.

**Artifact.** Block 1.10 produces a **full signed `transaction`** and the structured metadata
around it:

- `:tx` assembles the full `transaction` array
  `[ transaction_body, transaction_witness_set, true, null ]` (the `bool` is the validity flag;
  `auxiliary_data` is `null` for the MVP) and the `transaction_witness_set` map
  `{ 0 : [ [ vkey /* 32 bytes */, signature /* 64 bytes */ ], ... ] }`, encoded through `:core`'s
  CBOR subset. It exposes a structured `SignedTransaction` carrying the full signed CBOR bytes and
  the witness count. `:tx` stays crypto-free — it never hashes or signs, only assembles supplied
  bytes.
- `:wallet`'s signing entry point returns a signing result that pairs the `:tx` `SignedTransaction`
  with the `bodyHash` / transaction id it computed (via `:crypto`). This is the "structured
  signed-transaction" artifact: full signed CBOR + witness count + transaction id + the
  "signed, not submitted" framing (§7).

**Relation to `TransactionDraft.bodyCbor()`.** Signing consumes `draft.bodyCbor()` from `:tx`
(ADR-0014) **unchanged**: the same body bytes are (a) hashed to `bodyHash` and (b) embedded
verbatim as field 0 of the full `transaction`. The signature and the transaction id are both
derived from those exact body bytes, so the signed transaction's id equals the hash of the body
that was signed.

**Fee handling (Block 1.10 does not rebuild the body).** ADR-0014 §6 estimated the fee assuming
**one vkey witness per selected input**. For the Phase 1 single-key test wallet, multiple selected
inputs may all be spent by the **same** payment key, so the real transaction needs only **one**
vkey witness regardless of input count — meaning the Block 1.9 estimate can **over-estimate** the
witness count and therefore the fee. An over-estimated fee yields a still-valid transaction (the
encoded fee is ≥ the ledger minimum; the surplus reduces change), so **Block 1.10 signs the
existing `TransactionDraft` body unchanged and does not minimize or rebuild the fee.**
Exact, witness-aware fee minimization (deduplicating witnesses per distinct payment key and
rebuilding the body at the true minimum fee) is explicitly **deferred** to a later block; Block
1.10's Playground copy and KDoc state that the fee is a conservative, non-minimized value for the
test wallet.

### 4. Crypto backend: a blocking Block 1.10b-pre gate must resolve and verify an extended Ed25519-BIP32 signing backend before any signing code

> **Gate result (Block 1.10b-pre): see ADR-0016 (`docs/DECISIONS/0016-transaction-signing-backend-gate.md`) — BLOCKED.** Symbol-level inspection of the resolved artifacts confirmed the Context finding (`bip32-ed25519:1.8.8`'s native lib exports only the three derive functions; Apollo signs standard seed-based Ed25519; libsodium is seed-based), so **no resolved/published all-target KMP backend can sign an extended key.** A concrete unblock path is identified (expose the reference `ed25519-bip32` crate's `XPrv::sign` through the same uniffi mechanism as derivation), and the extended-key KAT below is pinned — but the backend PASS condition in this section is **not yet met**, so Block 1.10b stays blocked pending a separately-authorized backend-provisioning task.

Because no currently-shipped dependency can sign a Cardano extended key (see Context), signing
implementation is gated. **Block 1.10b-pre is a blocking, docs-only gate** (mirroring the 1.5a
compatibility spike, the 1.5b-pre / 1.6a vector gates, and the ADR-0010 backend investigation)
that must, from **resolved-artifact evidence only** (`javap` / `unzip -l` / `nm`/`strings` symbol
inspection / live probe calls and tests — never from documentation claims):

1. **Identify a backend that signs with a pre-expanded 64-byte Ed25519-BIP32 extended scalar
   (`kL` ‖ `kR`)** — i.e. Cardano extended-key signing, not standard RFC 8032 seed-based Ed25519.
2. **Verify it across every target:** JVM and **Android at real runtime**
   (`connectedAndroidDeviceTest`, per the ADR-0010 / `kotlin-tests-and-docs.mdc` discipline), and
   iOS at least compile+link (iOS runtime execution recorded honestly as future work if not run),
   with no handwritten crypto anywhere.
3. **Pin a citable known-answer signature vector** for extended Ed25519-BIP32 signing (§6).

**Vector-gate pass condition (explicit).** The known-answer test **must** be for **Cardano
extended Ed25519-BIP32 signing** — signing with the pre-expanded 64-byte extended scalar. **If
only plain (RFC 8032, seed-based) Ed25519 vectors are available, the gate is NOT passed**, because
a plain-Ed25519 KAT does not prove the extended-key signing path this SDK actually uses.

**Candidate backends to evaluate in the gate (none pre-selected here):**

- A uniffi/Kotlin wrapper that exposes IOG `ed25519-bip32`'s `XPrv::sign` (the crate implements
  extended-key signing; the currently-pinned identus wrapper does not export it — a different or
  newer wrapper version, or an added binding, would be required).
- Apollo's Ed25519-BIP32 signing, **only if** a resolved artifact actually exports extended-key
  signing on all targets (the JVM facade inspected for this ADR does not).
- `cardano-multiplatform-lib` / `cardano-serialization-lib` (evaluate KMP/iOS reach honestly; may
  be JVM/Android-only).
- bloxbean `cardano-client-lib` and CSL as **JVM-only vector oracles** only (not shippable
  dependencies, consistent with ADR-0008's oracle posture), to produce/cross-check the pinned
  vector.

**Fallback shape if no single all-target backend exists.** A per-platform seam is permitted
(the same pattern already used for PBKDF2 in Block 1.6b and public-key projection in ADR-0010:
an `internal expect fun` with per-platform `actual`s delegating to a maintained native library),
**provided every actual delegates to a verified backend and none reimplements the signing
equation by hand.** If a target cannot be satisfied without handwritten crypto, that target's
signing path returns a typed "unavailable on this platform" error (§5) rather than shipping
handwritten crypto — and the gate records the gap honestly instead of claiming coverage.

**Block 1.10b-pre must PASS (backend verified on JVM + Android runtime, iOS at least
compile/link; extended-key KAT pinned) before Block 1.10b writes any signing code.** No Gradle or
dependency change is authorized until that gate passes and names the exact dependency.

### 5. Error model: typed errors, no throwing across KMP, defined key-material clearing

- **`:crypto` gains a sealed `SigningError`** returned via `KardanoResult` (never thrown),
  covering at least: backend failure; signing unavailable on this platform (the §4 fallback
  case); and invalid/unexpected key material. Backend exceptions are caught and mapped to a
  backend-neutral `SigningError` (mirroring `Bip32Ed25519KeyDerivation.mapThrowable`), never
  rethrown across the Swift/ObjC boundary.
- **`:tx` assembly errors are typed** (extend `TxBuildError` or add a small sibling sealed type
  for witness/full-transaction assembly — the exact placement is a Block 1.10b implementation
  detail), covering malformed witness inputs (wrong vkey/signature length) and any CBOR encoding
  failure (wrapping `:core`'s `CborError`, as `TxBuildError.Serialization` already does).
- **`:wallet` wraps upstream errors cleanly**, following ADR-0013's pattern of wrapping each
  upstream typed error rather than inventing a parallel taxonomy: a new `WalletError.Signing(...)`
  (and, if needed, an assembly wrapper) maps `SigningError` / `KeyDerivationError` /
  `CryptoError` / `TxBuildError` into the wallet-level sealed error without loss.
- **Key-material clearing.** Every signing path clears the full extended scalar and any
  intermediate key/nonce buffers in a `finally` block (best-effort wipe per ADR-0004 §5, with no
  guarantee about compiler/GC behavior), exactly as `derivePrivate`/`publicKey` already do. The
  derived `ExtendedPrivateKey`, the master key, and the mnemonic are cleared by the orchestrating
  `:wallet` call after signing, whether it succeeds or fails.

### 6. Test and vector policy

- **No invented signing vectors.** Consistent with the project's test-integrity rule and
  `kotlin-tests-and-docs.mdc`.
- **A citable extended Ed25519-BIP32 signature KAT is pinned by the Block 1.10b-pre gate** (URL +
  pinned commit + license), and it must be an **extended-key** vector, not plain Ed25519 (§4).
  **Pinned by ADR-0016 §3:** the reference `ed25519-bip32` crate (`0.4.2`, MIT OR Apache-2.0)
  `xprv_sign` test vector (extended scalar + `"Hello World"` ⇒ fixed 64-byte signature), with the
  CIP-0100 32-byte-body-hash vector recorded as a secondary reproduce-to-confirm example.
- **If no full signed-transaction golden exists** (as in ADR-0014 §9, none was locatable for a
  minimal ADA-only body), tests are split:
  - **Backend known-answer test** (`jvmTest`, and Android device test): a fixed extended key +
    fixed message ⇒ fixed 64-byte signature, from the pinned ADR-0016 vector. The pinned primary
    vector's message is the reference crate's own `"Hello World"` test string (11 bytes, not 32) —
    it proves the extended-scalar signing primitive itself, which is message-length-agnostic; it is
    not required to be 32 bytes. The actual Block 1.10 signing path always signs the 32-byte
    `bodyHash` (§3), not this KAT's message. The CIP-0100 vector, which does sign a 32-byte
    Blake2b-256 body hash, remains secondary/reproduce-to-confirm for that exact shape (ADR-0016
    §3) and is not itself the pinned backend KAT.
  - **Structural witness/full-transaction CBOR tests** (`commonTest`): assemble the witness set
    and full `transaction`, decode back through `:core` `Cbor.decode`, and assert the CDDL shape
    (`[body, witness_set, true, null]`; witness set `{0: [[vkey(32), sig(64)], ...]}`).
  - **Sign-then-verify self-consistency test**, explicitly labeled as a self-consistency check
    (sign with the extended key, verify with the projected public key), **not** as an external
    golden.
- **Android runtime verification is required**, not only host tests — a
  `connectedAndroidDeviceTest` must exercise the real signing backend on Android (per ADR-0010 and
  `kotlin-tests-and-docs.mdc`). iOS is compile/link-verified at minimum; iOS runtime execution is
  recorded honestly as future work unless a simulator/device run is actually performed.

### 7. Playground checkpoint (Block 1.10c)

The `:shared` Android Playground gains a "Signed Transaction (not submitted)" section that builds
the same unsigned draft as Block 1.9c, then signs it by calling `:wallet`'s signing entry point
with the cited `TestWalletFixture` words/path and `Network.TESTNET` **explicitly** (per §2a —
`:wallet` does not know about the fixture itself; `:shared` supplies it), and displays:

- the **transaction id** (`bodyHash`) — now justified, because signing/finalization exists (its
  display was deferred out of Block 1.9c precisely until this block, ADR-0014 §2);
- the **witness count**;
- a **truncated signed-transaction CBOR preview**;
- an explicit **"signed, not submitted — testnet-only, test fixture, no real funds"** label.

**No submission happens in Block 1.10** — submit is Block 1.11 (ADR-0006). The checkpoint copy
stays factual: test-only fixture, testnet only, no real funds, no readiness/audit claim.

### 8. Guardrail / rules reconciliation

The `.cursor/rules/kardano-sdk-guardrails.mdc` hard rule that currently reads "No transaction
signing" is **narrowed, not removed**, to authorize signing **strictly inside the Block 1.10
scope defined in §2** (testnet/preprod only, the existing test fixture/restored-wallet path only,
ADA-only single-payment `TransactionBuilder` drafts only), and to keep signing outside that scope
disallowed until a future explicit block/ADR widens it. All other bans are kept verbatim: no real
funds, no real mnemonics/private keys, no mainnet, no handwritten cryptographic algorithms, and no
readiness, external-review, or audit-status claims. `docs/HANDOFF.md`'s "What Not To Do Yet" is likewise
narrowed to "transaction signing outside Block 1.10 scope," and `docs/AI_WORKING_AGREEMENT.md`
remains the canonical long-form statement (unchanged by this docs-only block beyond the summary
rule; any edit there is a Block 1.10b concern if the API text needs it).

### 9. Sub-block split

- **1.10a** — this ADR (docs-only). Resolves ownership/boundary, scope, signing message,
  artifact, the backend gate's shape and pass condition, the error model, the test/vector policy,
  the checkpoint contents, and the guardrail reconciliation.
- **1.10b-pre** — the blocking backend + vector-source gate (docs-only, §4). Identifies and
  verifies the extended Ed25519-BIP32 signing backend across targets and pins a citable
  extended-key signature KAT. **Must PASS before 1.10b.**
- **1.10b** — implementation: `:crypto` `Signing` (+ the internal full-extended-scalar accessor
  and `SigningError`), `:tx` witness-set/full-`transaction` assembly (+ `SignedTransaction` and
  its typed errors), `:wallet` signing orchestration (+ the `:wallet → :tx` dependency and
  `WalletError.Signing`), and the split tests (§6). May be split into `1.10b-1` (`:crypto`
  signing) and `1.10b-2` (`:tx` assembly + `:wallet` orchestration) if the diff would exceed the
  ~300–400-line review target.

  > **Result (Block 1.10b): IMPLEMENTED.** All three pieces landed exactly as designed above,
  > with no scope widening:
  > - `:crypto` gained `Signing`/`SigningError`/`Ed25519Bip32Signing` (an internal adapter over
  >   the adopted `:crypto-signing-backend`, ADR-0016 §9i) plus
  >   `ExtendedPrivateKey.extendedPrivateKeyBytesForSigning()`, a second module-internal
  >   accessor alongside the existing test-only `xskBytesForTesting()` — no public
  >   private-key-byte accessor was added (ADR-0009 §7 stands).
  > - `:tx` gained `VerificationKeyWitness`, `TransactionWitnessSet`, `SignedTransaction`, and
  >   `TransactionAssembler` (+ three new `TxBuildError` variants:
  >   `InvalidVerificationKeyLength`, `InvalidSignatureLength`, `EmptyWitnessSet`). `:tx` gained
  >   no `:crypto` dependency and stayed crypto-free, as designed. Assembling the full
  >   `[body, witness_set, true, null]` array required `:core`'s CBOR subset to support the
  >   fixed simple values `true`/`false`/`null` (major type 7) — a narrow, out-of-band addition
  >   to the ADR-0001 policy, recorded as an addendum to
  >   `docs/DECISIONS/0001-cbor-and-parser-policy.md` rather than re-opening this ADR's scope.
  > - `:wallet` gained the `:wallet → :tx` dependency and
  >   `ReadOnlyWallet.signTransaction(words, network, draft)` — the same explicit
  >   `(words, network)` shape `restore` already takes, plus a `TransactionDraft` — returning a
  >   new `WalletSignedTransaction(signedTransaction, transactionId)` pairing type, plus two new
  >   `WalletError` variants (`Signing`, `TransactionAssembly`). No `:wallet → :shared`
  >   dependency was added; the fixture-only scope remains a call-site discipline (§2a).
  > - Verified per §6: `:crypto:jvmTest`, `:tx:jvmTest`, `:wallet:jvmTest`,
  >   `:crypto-signing-backend:jvmTest` pass; `:crypto:testAndroidHostTest`,
  >   `:tx:testAndroidHostTest`, `:wallet:testAndroidHostTest` pass;
  >   `:crypto-signing-backend:connectedAndroidDeviceTest` passes on a real device and an
  >   emulator; `:crypto:compileKotlinIosArm64`, `:tx:compileKotlinIosArm64`,
  >   `:wallet:compileKotlinIosArm64`, `:crypto-signing-backend:compileKotlinIosArm64`, and
  >   `:crypto-signing-backend:linkDebugTestIosSimulatorArm64` all pass.
  > - No submission, mainnet path, or general-purpose wallet signing API was introduced. Block
  >   1.10c (the `:shared` Playground checkpoint, §7) is complete, including the manual Android
  >   runtime checkpoint — see `docs/PHASE_1_PLAN.md`'s 1.10c entry for the full record.
- **1.10c** — the `:shared` Android Playground "Signed Transaction (not submitted)" checkpoint
  (§7) plus Android runtime verification.

**This ADR authorizes no code.** Block 1.10b is authorized only after Block 1.10b-pre passes and
names the exact signing dependency; if the gate cannot find an all-target backend without
handwritten crypto, that outcome is recorded here (or in a follow-up ADR) and the scope/targets
are adjusted rather than shipping handwritten crypto.

---

## Rationale

- Splitting signing across `:crypto` (primitive), `:tx` (witness/tx assembly), and `:wallet`
  (orchestration) keeps each module's existing single responsibility intact, keeps `:tx`
  crypto-free (matching ADR-0014), keeps all cryptography inside `:crypto` (matching ADR-0004),
  and keeps `:shared` free of protocol logic (matching ADR-0011 §3) — without inventing a new
  module for a concern each existing module already owns.
- Signing the 32-byte `bodyHash` (not the raw body bytes) matches how Cardano vkey witnesses are
  actually defined; making the message explicit here prevents a Block 1.10b implementation from
  signing the wrong bytes and producing an invalid witness.
- Making the backend an explicit, blocking gate — with a pass condition that requires an
  **extended-key** KAT — reflects the verified fact that no shipped dependency can sign a Cardano
  extended key today, and prevents the two failure modes the guardrails most care about here:
  silently shipping handwritten signing math, or "verifying" signing with a plain-Ed25519 vector
  that does not exercise the extended-key path.
- Signing the existing body without fee minimization keeps Block 1.10 focused on signing;
  documenting the over-estimate (single key, ≤ inputs witnesses) and deferring exact minimization
  keeps the fee semantics honest and testable, consistent with ADR-0014 §6 already labeling the
  fee an estimate.
- Reusing the ADR-0013 error-wrapping pattern and the ADR-0004/ADR-0009 key-clearing discipline
  keeps the new signing surface consistent with the rest of `:crypto`/`:wallet`.
- Making the fixture-only scope a **call-site** discipline (§2a) rather than a `:wallet`-internal
  check keeps `:wallet`'s dependency graph correct (still no `:shared` dependency) while keeping
  Block 1.10 honestly scoped in docs/KDoc; the alternative (having `:wallet` depend on `:shared`
  to recognize the fixture) would invert an already-fixed module boundary (ADR-0011 §3).

## Rejected alternatives

- **Put signing in `:tx` (giving `:tx` a `:crypto` dependency).** Rejected: it would break the
  ADR-0014 crypto-free boundary and conflate transaction serialization with cryptography.
- **Create a new `:signing` module.** Rejected: no dependency direction requires it; it would
  duplicate `:crypto`'s crypto ownership or `:wallet`'s orchestration ownership.
- **Sign the raw `transaction_body` CBOR bytes.** Rejected: Cardano witnesses sign
  `Blake2b-256(body)`; signing the raw bytes produces an invalid witness.
- **Rebuild/minimize the fee against the real witness count in Block 1.10.** Deferred, not done:
  the Block 1.9 estimate over-counts witnesses for a single-key wallet, so the fee is already
  valid (a conservative over-estimate); exact minimization is a separate, later, tested decision.
- **Select a signing dependency in this ADR.** Rejected: no shipped dependency signs extended
  keys today; the choice is deferred to the Block 1.10b-pre gate, which must verify it on real
  runtime with an extended-key KAT before it is pinned.
- **Accept a plain-Ed25519 KAT as sufficient.** Rejected: it would not exercise the extended-key
  signing path this SDK uses; the gate requires an extended Ed25519-BIP32 vector.
- **Compose the signature from libsodium scalar/hash primitives.** Rejected: assembling the
  Ed25519-BIP32 signing equation by hand is a handwritten cryptographic algorithm (ADR-0004 §3.1).
- **Have `:wallet` depend on `:shared` so it can recognize `TestWalletFixture` directly.**
  Rejected: `:wallet` is an SDK module and `:shared` is the sample/UI host; that dependency
  direction is backwards per ADR-0011 §3 and would leak a sample-app fixture into the SDK. The
  fixture-only scope is enforced at Phase 1 call sites instead (§2a).
- **Give `:wallet`'s signing entry point a hidden "fixture mode" flag or a fixture-specific
  overload.** Rejected: it would still require `:wallet` to know what the fixture is (the same
  problem), and it would misleadingly suggest the API is fixture-aware when the actual boundary
  is enforced by the caller, not the callee.

## Consequences

- After Block 1.10b, `:crypto` will expose a `Signing` primitive, `:tx` will assemble witness
  sets and full signed transactions from supplied `(vkey, signature)` pairs (still crypto-free),
  and `:wallet` will gain a `:tx` dependency and a signing orchestration entry point. `:core`
  stays dependency-free; `:shared` gains only display code.
- `:wallet`'s signing entry point takes explicit `(words, network, draft)` inputs and is not
  fixture-aware; Phase 1 call sites (the Playground checkpoint, tests) are responsible for
  supplying the cited fixture and `Network.TESTNET` (§2a). Treating this entry point as
  general-purpose requires a later, explicit ADR/block.
- A new production dependency will enter `:crypto` (and possibly a per-platform seam) — but only
  after the Block 1.10b-pre gate names and verifies it. This ADR authorizes none.
- The transaction id becomes displayable for the first time (Block 1.10c), closing the item
  ADR-0014 §2 deferred here.
- The signing guardrail is narrowed to Block 1.10 scope; all other Phase 0/1 bans remain.
- No submit, mainnet, native assets, scripts, metadata, multisig, or non-fixture wallet is
  introduced; each remains scoped to its own later block/phase.

## Non-goals

- No transaction submission (Block 1.11).
- No mainnet; no real mnemonics, private keys, or funds; no non-fixture/user-supplied wallet.
- No native assets, scripts (native or Plutus), script witnesses, metadata, certificates,
  withdrawals, collateral, datums, reference inputs, minting, required signers, multisig, or
  multiple distinct signing keys.
- No handwritten cryptography; no dependency/Gradle change in Block 1.10a; no dependency selection
  before the Block 1.10b-pre gate passes.
- No exact witness-aware fee minimization / body rebuild in Block 1.10.
- No general-purpose or public wallet signing API: the Block 1.10 entry point is scoped to the
  Phase 1 test fixture flow and ADA-only `TransactionBuilder` drafts by call-site discipline and
  KDoc (§2a), not by widening `:wallet`'s dependency graph or adding a `:wallet → :shared`
  dependency.
- No readiness, external-review, or audit claim.

## Follow-up work

- **Block 1.10b-pre** runs the blocking backend + extended-key-vector gate (§4) and records its
  result (PASS with a named, verified dependency and a pinned extended-key KAT, or a recorded gap
  with adjusted scope/targets) — here or in a follow-up ADR.
- **Block 1.10b** implements §1/§3/§5/§6 once the gate passes.
- **Block 1.10c** wires the `:shared` "Signed Transaction (not submitted)" checkpoint (§7) and
  Android runtime verification.
- **Block 1.11** (Submit) consumes the full signed-transaction CBOR this block produces.
- **A later block** may add exact witness-aware fee minimization (deferred in §3).
- ADR-0004 (crypto strategy), ADR-0009/ADR-0010 (derivation/projection + key-material rules),
  ADR-0013 (`:wallet`), and ADR-0014 (`:tx` / unsigned body) remain the governing decisions this
  ADR builds on; this ADR does not supersede them.

---

## Addendum (2026-08-23): §2a enforcement is now a `:wallet` runtime check (ADR-0019)

§2a's original "call-site discipline only" wording was correct for Block 1.10: `:wallet`
could not import `:shared`'s `TestWalletFixture`, and `TransactionDraft` carried no network.
ADR-0019 implements the scheduled binding without reversing that module rule:

- `TransactionDraft` now carries `network` and `TransactionDraftScope.Phase1AdaOnlySinglePayment`.
- `ReadOnlyWallet.signTestnetFixtureTransaction` rejects a non-testnet draft, a declared-network
  mismatch, an unsupported scope, or an incompatible shape **before** `Mnemonic.parse`.
- Fixture recognition uses `Phase1FixtureIdentity`'s cited public payment-credential
  fingerprint, not a stored mnemonic and not a `:wallet → :shared` dependency.
- The ADR-0018 `@ExperimentalKardanoSigningScope` opt-in is retained as a Kotlin-compiler
  signal. `@RequiresOptIn` still does not carry over to Swift; the new runtime
  `WalletError.SigningScopeViolation` checks do.

The original §2a prose above is left as the Block 1.10 decision record. Current enforcement
is ADR-0019.
