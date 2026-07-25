# ADR-0012: Address Encoding And Round-Trip Policy

| Field   | Value                                                                 |
|---------|------------------------------------------------------------------------|
| Status  | **Accepted**                                                          |
| Scope   | Block 1.7a — `:core` address-generation/encoding public API, canonical Bech32 policy, round-trip contract |
| Phase   | Phase 1 (Block 1.7a)                                                  |
| Updated | 2026-07-12                                                            |

---

## Context

`Address.parse` (Block 0.7) is decode-only: it validates a Bech32 string structurally and
exposes the parsed fields, but `:core` has no way to construct an `Address` from credential
bytes or re-encode one to Bech32. ADR-0005 §6 recorded an address encoding/round-trip ADR as
a hard prerequisite, to be resolved "before or at Block 1.7," and ADR-0011 §2 fixed the
ownership split (`:core` owns address assembly and encoding; `:crypto` may own only a narrow
public-key-to-credential-hash helper; no `:wallet` module; `:shared` owns no SDK logic) but
explicitly deferred the API shape itself to this ADR, warning that the existing
`Address`/`AddressCredential` types are parse-oriented and must not be assumed reusable as-is.

This ADR resolves that prerequisite and fixes the exact public API shape before any 1.7a
code is written.

---

## Decision

### 1. `AddressCredential`: public companion, narrow new factories

The `AddressCredential` companion object changes from `internal` to a **public companion**,
so external callers can construct a credential from raw hash bytes. Within it:

- `HASH_SIZE` (`28`) stays `internal` — it is an implementation constant, not part of the
  public contract (callers get the same validation through the factories below without
  needing to know the exact number).
- `of(kind, hash)`, the parser's internal factory, stays `internal` — it remains the single
  construction path `Address.parse` uses; the new public factories delegate to it rather than
  duplicating validation.
- Two new public factories are added:
  - `public fun keyHash(hash: ByteArray): KardanoResult<AddressCredential, AddressError>`
  - `public fun scriptHash(hash: ByteArray): KardanoResult<AddressCredential, AddressError>`

  Both length-check `hash` against `HASH_SIZE` and defensive-copy it (via the existing `of`
  path), returning `AddressError.InvalidCredentialLength` on a mismatch. No other member is
  widened: the primary constructor and the wrapped `hash` field stay `private`.

### 2. `Address.baseAddress`: a base-only builder

A new public factory is added to `Address`:

```kotlin
public fun baseAddress(
    network: Network,
    paymentCredential: AddressCredential,
    stakeCredential: AddressCredential,
): KardanoResult<Address, AddressError>
```

It builds the CIP-19 base-address header byte (type nibble 0-3, chosen from the two
credentials' `CredentialKind`, mirroring the existing decode-side `classifyHeader`) and the
network nibble (from `network.id`), assembles `rawBytes = [header, paymentHash..., 
stakeHash...]` (57 bytes), resolves the `CardanoHrp` (`ADDR`/`ADDR_TEST`, matching
`network`), and encodes to Bech32. Scope is **base addresses only** (the type-0..3 matrix),
matching ADR-0011 §2's "generates a testnet base address" framing; enterprise, reward, and
pointer *builders* remain deferred (see §5). The builder itself is not restricted to
`Network.TESTNET` — accepting either network keeps it a pure function and lets `:core`'s own
tests round-trip the cited mainnet CIP-19 vectors; the "no mainnet" boundary (ADR-0005 §7) is
enforced by the caller (`:shared` only ever passes `Network.TESTNET`), not by the builder.

### 3. `Address.bech32` vs `Address.toBech32()`: two distinct, non-conflated values

- **`bech32` is unchanged**: it remains the exact source string `Address.parse` accepted,
  byte-for-byte, still excluded from `equals`/`hashCode`/`toString`. It is *not* redefined as
  canonical.
- **`toBech32(): String` is new** and always returns the canonical lowercase Bech32 encoding
  derived from the address's `rawBytes` and `hrp`, independent of any source string. It is
  computed once at construction (both the parse path and the new generation path) and stored
  in a separate private field (`canonicalBech32`), so the getter cannot fail and never throws
  across the ObjC boundary.
- For a **generated** address there is no external source string, so the constructor sets
  `bech32` to the same canonical value `toBech32()` returns. This is the only case where the
  two coincide, and only because generation has nothing else to put in `bech32`.
- Encoding direction: `rawBytes` (8-bit) → `Bech32.convertBits(rawBytes, 8, 5, pad = true)`
  (the existing `internal` bit-conversion helper, already used by `:core`'s own test helpers
  for the inverse direction) → `CardanoBech32.encode(hrp, data5Bit)`. This is plain Bech32
  (never Bech32m), matching what `Address.parse`/`CardanoBech32` already enforce for Cardano
  addresses.

### 4. Round-trip contract

Two round-trip directions are asserted, and only one of them is unconditional:

- **`decode(encode(x)) == x`** (safe direction, per the Phase 0 test-vector policy): for a
  freshly built `Address` (from `baseAddress`), `Address.parse(built.toBech32())` must yield
  a structurally equal `Address` (equality already ignores the source string, so this holds
  regardless of which path produced `built`).
- **`parse(vector).toBech32() == vector`** for every *canonical* CIP-19 vector already cited
  in `:core`'s tests. `toBech32()` re-encodes whatever `Address.parse` already validated —
  header, network, and credential/pointer bytes — for **every currently supported parsed
  type** (base, enterprise, reward, pointer; mainnet and testnet), not only base, because the
  encoding path only depends on `rawBytes + hrp`, not on how the address was constructed.
  This is broader than the builder's base-only scope (§2, §5).
- This does **not** license accepting non-canonical input on decode: `Address.parse`'s
  existing non-canonical rejections (bad checksum, wrong variant, non-allowlisted HRP, wrong
  payload length, non-canonical pointer encoding, etc.) are unchanged and their tests stay in
  place. `toBech32()` never runs on a value `Address.parse` rejected.

### 5. Scope boundaries (what this ADR does not authorize)

- **Builder scope**: only `baseAddress` (base, type 0-3). Enterprise, reward/stake, and
  pointer *builders* are deferred to a future block — `Address.parse` already models them
  structurally, so adding a builder is a small, separately reviewable follow-up, not blocked
  by anything decided here.
- **No raw-byte/hex `Address` constructor**: still deferred (ADR-0003/ROADMAP), unrelated to
  this ADR's Bech32-level encoding.
- **No Byron/Base58**: unrelated and still deferred (ADR-0003/ROADMAP).
- **`AddressError` gets no new variant**: `InvalidCredentialLength` (wrong hash length) and
  `Bech32` (wrapping a `CardanoBech32Error`, for the unreachable-in-practice case that
  `CardanoBech32.encode` rejects valid-looking data) already cover every failure this ADR's
  API can produce. Its type-level KDoc is updated (not its variants) so it no longer reads as
  parse-only, since credential factories and `baseAddress` now return it too; the update
  states plainly that every variant remains a structural construction/encoding failure, never
  an ownership, funds, or ledger-state claim.
- **`:crypto` is untouched by this ADR.** Per ADR-0011 §2, hashing a derived public key into a
  28-byte credential hash stays a two-call composition
  (`ExtendedPublicKey.publicKeyBytes()` → `Hashing.blake2b224(...)`) the 1.7b caller performs
  directly; no new `:crypto` API is added or required by this decision.
- **Structural only.** `keyHash`/`scriptHash`, `baseAddress`, and `toBech32()` perform
  structural construction and encoding only. They make no claim that a resulting address
  exists on-chain, is owned, is controllable, or holds any balance — matching the disclaimer
  `Address.parse` already carries.

---

## Rationale

- Keeping `bech32` as the untouched source string (rather than redefining it as canonical)
  preserves the existing round-trip and equality tests (`bech32PreservesFixedSizeSourceString`
  etc.) without change, and keeps "what the caller typed" distinguishable from "the canonical
  form" — useful for a future caller that wants to detect non-canonical-but-valid input
  (e.g. mixed case would already be rejected by `Bech32.decode`, but any future looser variant
  would surface here).
- A public companion with two narrowly-scoped factories (rather than a public constructor or a
  public `of`) keeps the credential's invariant (exactly 28 bytes, defensive copy) enforced in
  exactly one place, matches the existing `Network.fromId`/`Lovelace.of`-style factory
  convention this SDK already uses everywhere else, and avoids exposing `HASH_SIZE` or the
  parser-only `of` unnecessarily.
- Scoping the builder to base-only (while letting `toBech32()` cover every parsed type) keeps
  the 1.7a diff proportional to what ADR-0011 §2 actually asked for ("generates a testnet base
  address") while still fully answering the round-trip prerequisite ADR-0005 §6 raised for
  `Address.parse`'s existing decode surface.

## Rejected alternatives

- **Redefine `bech32` as the canonical re-encoding for parsed addresses too.** Rejected: this
  would silently discard the caller's original input for any non-byte-identical-but-otherwise-
  canonical case and break the "exact source string" contract several existing tests assert
  against; a separate `canonicalBech32`/`toBech32()` costs one extra field and preserves both
  contracts.
- **Public `AddressCredential` constructor instead of factories.** Rejected: a public
  constructor cannot return a typed error for a bad length; it would have to throw (violating
  the KMP no-throw error policy) or silently truncate/pad (violating the parser-safety rule).
- **Add builders for every address type now.** Rejected: ADR-0011 §2 scoped 1.7 to base
  addresses; adding four builders in the same diff exceeds the block's stated scope and the
  ~300-400 line guardrail without a corresponding immediate need (no caller needs an
  enterprise/reward/pointer builder yet).
- **Add a new `AddressError` variant for encoding failures.** Rejected: `InvalidCredentialLength`
  and `Bech32` already cover every failure path this API can produce; a new variant would be
  unreachable dead code.

## Consequences

- `:core` gains a minimal, reviewable generation surface: `AddressCredential.keyHash`/
  `scriptHash`, `Address.baseAddress`, and `Address.toBech32()`. `:core` stays
  dependency-free.
- `AddressError`'s KDoc now describes it as covering parse, construction, and encoding
  failures; no new variant, no behavior change to any existing variant.
- The address encoding/round-trip prerequisite ADR-0005 §6 flagged for Block 1.7 is resolved;
  Block 1.7b (the `:shared` checkpoint) can proceed against this API.
- Existing `Address.parse` tests and their non-canonical rejection cases are unaffected;
  `AddressTest.kt` gains `toBech32()` canonicalization coverage across all parsed types.

## Follow-up work

- Block 1.7b wires `Address.baseAddress`/`toBech32()` into the `:shared` Playground checkpoint
  per ADR-0011 §2.
- Enterprise/reward/pointer builders, raw-byte/hex constructors, and Byron/Base58 remain
  deferred to their own future blocks/decisions, unaffected by this ADR.
