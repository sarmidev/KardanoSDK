# ADR-0001: CBOR and Parser Implementation Policy

| Field    | Value                         |
|----------|-------------------------------|
| Status   | **Open — decision required before implementation** |
| Scope    | CBOR subset, Bech32/Bech32m   |
| Phase    | Phase 0                       |
| Updated  | 2026-06-28                    |

---

## Context

Kardano SDK requires a minimal CBOR decoder/encoder (RFC 8949) and a Bech32/Bech32m
codec (BIP-173/350). Both are parser-like components with a meaningful security surface:
malformed input, truncated data, allocation bombs, and non-canonical encodings are all
realistic attack inputs when the SDK eventually processes on-chain data.

Two options exist for each component:

1. **Wrap a vetted KMP-compatible library.**
2. **Implement a custom, minimal, well-tested subset in pure Kotlin.**

This decision record captures the evaluation that must happen before either component
is implemented. It must be completed and the Status updated to **Accepted** before a
PR touching `encoding/cbor/` or `encoding/bech32/` is opened.

---

## Evaluation criteria

For each component, answer these questions:

### 1. Vetted library option

| Question | Answer |
|----------|--------|
| Does a suitable KMP-compatible library exist? | _to be filled_ |
| Is it actively maintained? | _to be filled_ |
| Does it support all required KMP targets (Android, iosArm64, iosSimulatorArm64, JVM)? | _to be filled_ |
| Does it support the required Cardano-compatible encoding (e.g. canonical CBOR)? | _to be filled_ |
| What is the library's last release date and issue-tracker health? | _to be filled_ |
| What is the transitive dependency footprint? | _to be filled_ |
| Is it audited, or does it have a known security track record? | _to be filled_ |

**Candidate libraries to evaluate:**
- CBOR: `kotlinx-serialization` (no native CBOR), `cbor-java` (JVM-only), `ktor-io` (no CBOR), custom.
- Bech32: no well-known KMP Bech32 library as of 2026; likely custom.

### 2. Custom implementation option

| Question | Answer |
|----------|--------|
| What is the exact supported subset? (list major types / HRP rules) | _to be filled_ |
| What are the hard limits? (MAX_INPUT_BYTES, MAX_NESTING_DEPTH, MAX_COLLECTION_ELEMENTS) | _to be filled_ |
| Are full BIP/RFC spec test vectors available and will they be included? | _to be filled_ |
| Will property-based / fuzz testing be added? | _to be filled_ |
| Who reviews the implementation? | _to be filled_ |

### 3. Cardano compatibility

| Question | Answer |
|----------|--------|
| Does Cardano require canonical CBOR (CBOR-canonical/CBOR-definite-length)? | Yes — Cardano transactions use definite-length encoding. |
| Does the chosen approach correctly reject indefinite-length encodings? | _to be confirmed_ |
| Are Cardano-specific CBOR tags (e.g. tag 121, 122 for Plutus) in or out of scope for Phase 0? | Out of scope — Phase 0 subset only. |
| Are CBOR bignum tags (2, 3) in or out of scope for Phase 0? | **Out of scope.** Reject explicitly with a typed error. |

---

## Decision

_Fill this section when the evaluation above is complete._

**CBOR:**
- [ ] Use library: _(name, version, rationale)_
- [ ] Use custom implementation — supported subset: _(list types)_; limits: _(constants)_

**Bech32/Bech32m:**
- [ ] Use library: _(name, version, rationale)_
- [ ] Use custom implementation — with BIP-173 and BIP-350 full vector suites

**Reviewer sign-off:** _name / PR link_

---

## Consequences

- The chosen approach becomes the required approach for Phase 0. Deviations need a
  follow-up ADR.
- If a library is chosen, it is added to `libs.versions.toml` with a pinned version and
  this ADR as the documented rationale.
- If custom is chosen, the implementation must include: named limit constants, full
  BIP/RFC vectors cited verbatim, and (recommended) property-based tests in addition to
  the mandatory valid/invalid/edge table tests.
- This ADR is referenced from `docs/AI_WORKING_AGREEMENT.md` — do not delete it.
