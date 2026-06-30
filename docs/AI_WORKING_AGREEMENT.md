# AI Working Agreement — Kardano SDK (Phase 0)

This document governs how AI agents and contributors make changes to this repository
during Phase 0. Kardano will eventually handle keys and funds; the discipline starts now.

---

## Project summary

Kardano SDK is an open-source **Kotlin Multiplatform** SDK for native Cardano mobile
apps, targeting **Android, iOS, and JVM/Desktop**. Group: `org.sarmidev.kardano`.
The SDK **core must be UI-free** (no Compose dependency).

---

## Phase 0 scope

Pure-Kotlin, deterministic, **no cryptography required**:

- Byte primitives and helpers (immutable, length-checked).
- Hex encoding/decoding.
- Bech32 / Bech32m (BIP-173 / BIP-350, CIP-5 prefixes).
- A minimal, documented CBOR subset (RFC 8949).
- Structural address validation/parsing (CIP-19) — parsing only, not derivation.
- Crypto strategy doc and `expect` declarations only (no implementations).
- Project hygiene: license, READMEs, CI, KDoc/Dokka.

---

## Non-goals (Phase 0)

- No transaction building, serialization for submission, or signing.
- No key generation, mnemonics (BIP-39), or HD derivation.
- No address derivation from keys (only structural validation of existing addresses).
- No network/IO, node clients, or wallet connection.
- No full CBOR/COSE — only the documented subset.
- No over-modularization before there is code to justify it.

---

## Forbidden actions

- Do **not** implement cryptographic algorithms by hand (Blake2b, Ed25519, SHA, etc.).
- Do **not** add transaction signing.
- Do **not** add real mnemonics, private keys, or anything touching real funds —
  not in code, tests, fixtures, or docs.
- Do **not** use banned marketing/security words (see below).
- Do **not** modify Gradle, Kotlin source, iOS, or Android project files unless the
  task explicitly authorizes it.
- Do **not** add dependencies to the SDK core without an explicit rationale and
  documented decision (see Dependency policy below).

---

## Dependency policy

"No unnecessary dependencies" does not mean "stdlib-only at all costs."

- The SDK core must stay **lean and KMP-compatible**. Do not add a dependency because
  implementation is inconvenient.
- For security-sensitive parser components (CBOR, Bech32), the choice between a vetted
  library and a custom implementation **requires a decision record** before coding begins.
  See `docs/DECISIONS/0001-cbor-and-parser-policy.md` for the template and first decision.
- A decision record must evaluate: vetted library vs. custom; Cardano compatibility;
  canonical encoding requirements; KMP target support; test vectors; fuzz/property testing
  needs; maintenance risk.
- No dynamic (`+`) or unpinned dependency versions, ever.
- Every dependency added must document its rationale in the decision record or PR.
- Prefer small, actively-maintained, KMP-compatible libraries.
- `kotlin-test` and property/fuzz testing libraries (e.g. Kotest property) are allowed
  in test source sets without a decision record.

---

## Security-sensitive areas

Extra care, test vectors, and review required for:

- `encoding/bech32/` — checksum logic; malformed input must be rejected cleanly.
- `encoding/cbor/` — see Parser anti-DoS rules below; never crash on attacker-controlled
  bytes.
- `address/` — CIP-19 header, network-id, and length validation.
- `crypto/` — strategy and seam declarations only in Phase 0; no implementation bodies.
  See `docs/DECISIONS/0004-crypto-strategy.md`.

When crypto arrives (later phases), delegate to externally maintained libraries or
platform bindings selected through documented evaluation (per ADR-0004). The seam may
be `expect`/`actual` for per-platform libraries, or a common interface backed by a
KMP-capable library's own `commonMain` API — the choice is made per algorithm during
evaluation. Never reimplement cryptographic primitives.

---

## Parser anti-DoS rules

These apply to every parser (CBOR, Bech32, hex, address):

- **Never allocate a buffer from an untrusted length field.** Reading a length from input
  and immediately doing `ByteArray(declaredLen)` is a memory-exhaustion vulnerability.
  Validate the declared length against the actual remaining bytes first.
- Define named constants for limits: `MAX_INPUT_BYTES`, `MAX_NESTING_DEPTH`,
  `MAX_COLLECTION_ELEMENTS`. Reject inputs that exceed any limit with a typed error.
- Reject malformed, non-canonical, and unsupported encodings explicitly — never normalize
  invalid input to make it appear valid or to make a test pass.

---

## KMP public API error policy

Public APIs that can fail **must** use sealed error / result types, not exceptions.
Throwing exceptions across the Swift/ObjC boundary crashes the iOS app.

- Default: the SDK's `KardanoResult<T, E>` (or a sealed `Either`-style type) for all
  failable public APIs. Do not name the SDK type `Result`, to avoid confusion with
  `kotlin.Result`.
- Any API that unavoidably throws must be **explicitly documented** and annotated with
  `@Throws` in the KDoc and in the actual declaration.
- Internal helpers may throw; the public surface must not unless annotated.

---

## ByteArray correctness rules

Every byte wrapper or byte-based value object must:

- Use `contentEquals` / `contentHashCode` for value equality — **never** `ByteArray ==`.
- Make a **defensive copy** of any `ByteArray` passed to its constructor.
- Return a **defensive copy** from any accessor that exposes internal bytes.
- Never expose a mutable internal `ByteArray` directly.

---

## Integer-range policy (CBOR and numeric primitives)

- Enumerate and document the supported numeric ranges for each type.
- **Reject** out-of-range values with a typed error — never silently truncate.
  (Example: a CBOR uint64 silently cast to `Long` can corrupt lovelace quantities.)
- CBOR bignum/`BigInteger` tags (major type 6, tags 2 and 3): **out of scope for
  Phase 0**. Document this limit and reject them explicitly.
- Decide per-component whether negative integers are supported and document it.

---

## Address validation rules

Address validation in Phase 0 is **structural only**:

- Parse the Bech32 payload, inspect the header byte (address type + network nibble).
- Validate payload byte-length for each address type per CIP-19.
- **Preserve and expose the network id**; never discard or ignore it.
- Reject unsupported network ids with a typed error (do not silently accept them).
- Distinguish mainnet / testnet / preprod / preview where the network id allows.
- **KDoc must state** that validation is structural only — it does not prove that an
  address exists, is owned, or is spendable.

---

## AI coding rules

- Make the **smallest change that satisfies the task**. Prefer editing existing files.
- Parsers/validators must be **total**: reject malformed input cleanly via a sealed error
  or documented `@Throws` — never crash on bad input.
- Bounds-check before indexing; validate all lengths before use.
- Use `ByteArray`-based APIs for internal binary data. `String` is acceptable for public
  textual encodings (hex, Bech32, address strings). **Never** use `String` for secrets
  or internal binary representations.
- Keep the SDK core free of UI and unnecessary dependencies.
- For **broad refactors, write a short plan first** (files touched, approach, risks)
  and get agreement before editing.

---

## Unit testing policy

- Tests use `kotlin.test` in `commonTest` so they run on all KMP targets.
- **Every** primitive, encoding function, parser, and validator change has tests.
- Each tested unit covers **valid**, **invalid**, and **edge** cases (empty, max-length,
  boundary bytes, bad checksum/chars, truncated input, nesting limits).
- Round-trip tests are encouraged but not sufficient alone.

---

## Test integrity rules

- **Never invent test vectors.** Authoritative vectors for security-sensitive units must
  be copied verbatim from cited specs or trusted reference implementations. An AI must
  not generate its own "expected" outputs for checksum, CBOR, or address tests.
- **Never weaken a validator to make a test pass.** If a test fails, fix the
  implementation or the test data — not the acceptance criteria.
- Round-trip direction matters:
  - `decode(encode(x)) == x` — this is safe to test.
  - `encode(decode(y)) == y` — **use with caution.** This must not be used to normalize
    or silently accept non-canonical encodings. If you test this direction, also assert
    that non-canonical input is rejected before decoding.
- Each fixture file cites its source spec/URL in a header comment.

**Required external vector sources:**

- Bech32/Bech32m → BIP-173 and BIP-350 valid **and** invalid vectors.
- CBOR → RFC 8949 Appendix A examples for each supported type.
- Addresses → CIP-19 examples (testnet preferred) plus known-bad inputs.

---

## Documentation policy

- Every module has a developer-facing `README.md`: purpose, scope, what it does **not**
  do, a short usage example, and links to relevant BIP/CIP/RFC.
  Package-level KDoc is an acceptable alternative for very small modules.
- Cross-cutting docs live in `docs/` (architecture, crypto strategy, security model,
  decisions).
- Code examples in docs must be runnable (ideally backed by a test so they cannot drift).
- Update docs in the **same change** as the code they describe.

---

## Public API KDoc policy

- **Every public declaration** (class, function, property) has KDoc.
- Public functions document parameters, return value, error/failure behavior, and link to
  the relevant spec section.
- KDoc for validators must explicitly state: **structural validation only**.
- Prefer `explicitApi()` in the core module so public surface is deliberate.

---

## Banned marketing and security words

Do not use these words unless backed by a formal, cited external audit or proof:

> `secure`, `safe`, `hardened`, `audited`, `production-ready`, `guaranteed`,
> `cryptographically safe`, `bank-grade`

Prefer factual wording:

> `structurally validates`, `checks checksum`, `rejects malformed input`,
> `Phase 0 experimental`, `not audited`, `not for mainnet use`

---

## Supply-chain rules

- No dynamic (`+`) or floating dependency versions — ever.
- All dependency versions must be pinned in the version catalog.
- Every dependency added to the SDK core must have a documented rationale
  (decision record or PR description).
- Prefer small, actively-maintained, KMP-compatible libraries.
- Do not add a dependency solely because writing the code is inconvenient.

---

## Review checklist (before accepting generated code)

- [ ] No handwritten crypto, no signing, no real keys/mnemonics/funds.
- [ ] No banned marketing/security words.
- [ ] SDK core stays UI-free; no unauthorized dependencies added.
- [ ] New/changed public APIs have KDoc (including `@Throws` where applicable).
- [ ] Parsers: never allocate from untrusted lengths; named limits defined and enforced.
- [ ] ByteArray value types use `contentEquals`/defensive copies.
- [ ] Numeric types reject out-of-range values; no silent truncation.
- [ ] Address validation exposes and validates network id; KDoc says structural-only.
- [ ] New behavior has valid + invalid + edge tests.
- [ ] Security-sensitive tests cite external vectors (not AI-invented).
- [ ] No validator was weakened to make a test pass.
- [ ] Developer docs updated in the same change.
- [ ] Only authorized files were modified.
- [ ] Diff targets < ~400 changed lines; split if larger.

---

## Small diff policy

- One logical change per change set. Do not mix refactor + feature + formatting.
- **Target fewer than ~300–400 changed lines.** If a change grows larger, split it into
  smaller reviewable steps. For broad refactors, write the plan first and get agreement.

---

## Definition of done (every implementation task)

- [ ] Compiles on common and JVM targets.
- [ ] Android target compiles and tests pass where applicable.
- [ ] iOS simulator target compiles and tests pass where applicable.
- [ ] Relevant unit tests pass.
- [ ] New behavior has valid/invalid/edge tests.
- [ ] Security-sensitive behavior has cited external test vectors.
- [ ] Public APIs have KDoc; validators say "structural only" where applicable.
- [ ] Developer-facing docs are updated in the same change.
- [ ] No banned words or unsafe crypto/signing/production claims were introduced.
- [ ] Diff is small enough to review manually (target < ~400 lines).
