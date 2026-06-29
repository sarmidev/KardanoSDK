# ADR-0001: CBOR and Parser Implementation Policy

| Field    | Value                         |
|----------|-------------------------------|
| Status   | **Accepted**                  |
| Scope    | CBOR subset, Bech32/Bech32m   |
| Phase    | Phase 0                       |
| Updated  | 2026-06-29                    |

---

## Context

Kardano SDK requires a minimal CBOR decoder/encoder (RFC 8949) and a Bech32/Bech32m
codec (BIP-173/350). Both are parser-like components with a meaningful security surface:
malformed input, truncated data, allocation bombs, and non-canonical encodings are all
realistic attack inputs when the SDK eventually processes on-chain data.

Two options exist for each component:

1. **Wrap a vetted KMP-compatible library.**
2. **Implement a custom, minimal, well-tested subset in pure Kotlin.**

This decision record captures the evaluation and records the accepted approach. It must be
**Accepted** before a PR touching `encoding/cbor/` or `encoding/bech32/` is opened.

---

## Evaluation criteria

For each component, answer these questions:

### 1. Vetted library option

| Question | Answer |
|----------|--------|
| Does a suitable KMP-compatible library exist? | Bech32: no well-known KMP library as of 2026. CBOR: no KMP-native option covering the required definite-length subset (see candidates below). |
| Is it actively maintained? | Not applicable — no suitable KMP candidate selected. |
| Does it support all required KMP targets (Android, iosArm64, iosSimulatorArm64, JVM)? | No single candidate covers all targets for both components. |
| Does it support the required Cardano-compatible encoding (e.g. canonical CBOR)? | Not in a constrained, definite-length-only form matching SDK policy. |
| What is the library's last release date and issue-tracker health? | Not applicable — no candidate selected. |
| What is the transitive dependency footprint? | Avoided entirely by the internal approach. |
| Is it audited, or does it have a known security track record? | Not applicable — no candidate selected. (Phase 0 makes no audit claims either way.) |

**Candidate libraries evaluated:**
- CBOR: `kotlinx-serialization` (no native CBOR), `cbor-java` (JVM-only), `ktor-io` (no CBOR).
- Bech32: no well-known KMP Bech32 library as of 2026.

### 2. Custom implementation option

| Question | Answer |
|----------|--------|
| What is the exact supported subset? (list major types / HRP rules) | See the Bech32/Bech32m policy and CBOR policy sections below. |
| What are the hard limits? (MAX_INPUT_BYTES, MAX_NESTING_DEPTH, MAX_COLLECTION_ELEMENTS) | See the Parser limits section below. |
| Are full BIP/RFC spec test vectors available and will they be included? | Yes — BIP-173, BIP-350, and RFC 8949 Appendix A. See the Test policy section. |
| Will property-based / fuzz testing be added? | Recommended in addition to the mandatory valid/invalid/edge table tests. |
| Who reviews the implementation? | The maintainer reviews each implementation PR against this ADR and the cited specs. |

### 3. Cardano compatibility

| Question | Answer |
|----------|--------|
| Does Cardano require canonical CBOR (CBOR-canonical/CBOR-definite-length)? | Yes — Cardano transactions use definite-length encoding. |
| Does the chosen approach correctly reject indefinite-length encodings? | Yes — indefinite-length values are rejected with a typed error. |
| Are Cardano-specific CBOR tags (e.g. tag 121, 122 for Plutus) in or out of scope for Phase 0? | Out of scope — Phase 0 subset only; all tags rejected. |
| Are CBOR bignum tags (2, 3) in or out of scope for Phase 0? | **Out of scope.** Reject explicitly with a typed error. |

---

## Decision

Phase 0 uses **constrained internal implementations in pure Kotlin** for both components,
with **no external dependency** added for either:

- **Bech32/Bech32m:** internal constrained implementation, validated against BIP-173 and
  BIP-350 vectors.
- **CBOR:** internal constrained subset of RFC 8949 (definite-length only), validated
  against RFC 8949 Appendix A vectors for the supported types.

The Bech32 polymod/checksum routine is **checksum and parsing logic, not cryptography**.
This decision adds no cryptographic algorithms; the no-handwritten-crypto rule is not
relevant to it.

---

## Bech32/Bech32m policy

- The internal engine supports both **Bech32** and **Bech32m** variants (the two differ
  only by the checksum constant).
- Public Cardano Phase 0 APIs **default to Bech32** where Cardano specs require it; the
  Bech32m variant is available at the engine level for callers/specs that need it.
- **Reject mixed-case** input. The HRP and data part must not mix upper and lower case.
- The **encoder emits lowercase** only.
- Validate, at minimum: the **HRP** (allowed characters and length), the **separator**
  (`1`, using the last occurrence), the **data charset** (the 32-character Bech32 alphabet,
  excluding `1`, `b`, `i`, `o`), the **checksum** (variant-appropriate polymod), and the
  **5-bit/8-bit conversion padding** (reject non-zero padding bits and invalid leftover).
- Do **not** blindly apply the BIP-173 90-character maximum to Cardano APIs: CIP-19
  addresses can exceed it. Cardano-mode length bounds are SDK-owned (see Parser limits).
- Define **SDK-owned parser limits for Cardano mode** rather than inheriting BIP-173's
  general-purpose 90-character cap (see Parser limits).
- The initial Cardano **HRP allowlist** focuses on: `addr`, `addr_test`, `stake`,
  `stake_test`. Other HRPs are rejected by the Cardano-facing APIs in Phase 0 (the generic
  engine may still encode/decode arbitrary valid HRPs for internal use).

---

## CBOR policy

The Phase 0 CBOR subset (RFC 8949) supports only the following and rejects everything else
with a typed error:

- **Definite-length values only.** Indefinite-length encodings are rejected.
- **Major type 0 (unsigned int)** and **major type 1 (negative int)**, restricted to the
  **signed `Long` range**. Values outside that range are rejected (no silent truncation).
- **Byte strings** (major type 2) and **text strings** (major type 3), definite-length,
  within explicit length limits.
- **Arrays** (major type 4) and **maps** (major type 5), definite-length, within explicit
  element-count and nesting limits.

Explicitly rejected in Phase 0 (unless a later ADR adds them):

- **Indefinite lengths** (all major types).
- **Tags** (major type 6), **including bignum tags 2 and 3**.
- **Floats and simple values** (major type 7), including **`null`/`undefined`** and
  booleans, unless later explicitly added.
- **Trailing bytes** after a complete top-level value.
- **Out-of-range integers** (outside signed `Long`).
- **Duplicate map keys.**

**Map ordering policy:** for the deterministic/Cardano mode, map keys must follow RFC 8949
canonical (deterministic) ordering. The decoder rejects maps whose keys are not in canonical
order (in deterministic mode) and rejects duplicate keys unconditionally; the encoder emits
keys in canonical order.

---

## Parser limits

These are **named, SDK-owned limits** enforced by the parsers. They are **Phase 0 limits**
and may be revisited by a future ADR. No buffer is ever allocated directly from an untrusted
declared length; a declared length is validated against the remaining input first.

Bech32 (Cardano mode):

- `BECH32_MAX_INPUT_CHARS` — maximum encoded string length (SDK-owned; not BIP-173's 90).
- `BECH32_MAX_HRP_CHARS` — maximum human-readable-part length.
- `BECH32_MAX_DATA_BYTES` — maximum decoded data-part length after 5-bit/8-bit conversion.

CBOR:

- `CBOR_MAX_INPUT_BYTES` — maximum total input size.
- `CBOR_MAX_NESTING_DEPTH` — maximum array/map nesting depth.
- `CBOR_MAX_COLLECTION_ELEMENTS` — maximum element count per array/map.
- `CBOR_MAX_STRING_BYTES` / `CBOR_MAX_BYTESTRING_BYTES` — maximum text/byte-string lengths.

Concrete numeric values are set in the implementation PRs (Blocks 0.5/0.6) as named
constants and documented there; this ADR fixes the names and the policy that each limit
exists and is enforced with a typed error.

---

## Test policy

- **Bech32** — valid and invalid vectors from **BIP-173**.
- **Bech32m** — valid and invalid vectors from **BIP-350**.
- **CBOR** — vectors from **RFC 8949 Appendix A** for each supported type.
- Include **official malformed-input examples** where the specs provide them; invalid
  vectors must stay invalid.
- **No generated or AI-invented protocol vectors.** Vectors are copied verbatim from the
  cited specs with the source noted in the fixture header.

---

## Consequences

- **Smaller dependency surface:** no third-party CBOR/Bech32 dependency is added in Phase 0.
- **More internal parser code to maintain:** the SDK owns the parsers, their limits, and
  their test suites.
- **Strict subset:** because the SDK enforces a constrained subset, some inputs that are
  generally valid CBOR or Bech32 (for example, indefinite-length CBOR, tags, floats, or
  non-canonical map ordering) may be **rejected by SDK policy**. This is intentional.
- The chosen approach becomes the required approach for Phase 0. Deviations need a follow-up
  ADR.
- This ADR is referenced from `docs/AI_WORKING_AGREEMENT.md` — do not delete it.

---

## Follow-up tasks

- **Block 0.5 — Hex first**, then the **Bech32/Bech32m** implementation according to this
  ADR.
- **Block 0.6 — CBOR subset** implementation according to this ADR.
- **Block 0.7 — address parsing** after Bech32 exists.

**Reviewer sign-off:** maintainer (this ADR / Block 0.4 closure).
