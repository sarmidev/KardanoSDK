# ADR-0003: Core package structure

| Field    | Value                              |
|----------|------------------------------------|
| Status   | **Accepted**                       |
| Scope    | Internal package layout of `:core` |
| Phase    | Phase 0 (after Block 0.6, before Block 0.7) |
| Updated  | 2026-06-30                         |

---

## Context

Through Block 0.6 the `:core` module accumulated its primitives, encoding utilities, and
the CBOR subset directly under the single flat package `org.sarmidev.kardano`. The package
became hard to navigate, and `docs/AI_WORKING_AGREEMENT.md` already refers to
`encoding/bech32/`, `encoding/cbor/`, and `address/` as if those package paths existed.

Block 0.7 will add address parsing and the deferred `Address` value type. Reorganizing the
existing files into purpose-named packages **before** 0.7 means the new address code lands
in the right place from the start, rather than adding to a flat root that would later need
untangling.

Two structural options were considered:

1. Reorganize into subpackages inside the single `:core` module (packages only).
2. Split `:core` into several Gradle modules now (for example `:crypto`, `:tx`, `:wallet`,
   `:provider`).

## Decision

Reorganize packages **inside** `:core`; **defer** all Gradle module splits.

The Phase 0 package layout of `:core` is:

- `org.sarmidev.kardano` (root): `KardanoResult`, `Platform` / `getPlatform` (+ the
  `android`/`ios`/`jvm` actuals).
- `org.sarmidev.kardano.primitives`: `Network`, `Lovelace`, `TxHash`, `PolicyId`,
  `AssetName`, `UtxoRef`, `UtxoRefError`, `ByteSizeError`.
- `org.sarmidev.kardano.encoding.hex`: `Hex`, `HexError`.
- `org.sarmidev.kardano.encoding.bech32`: `Bech32`, `Bech32Variant`, `Bech32Decoded`,
  `Bech32Error`, `CardanoHrp`, `CardanoBech32`, `CardanoBech32Error`.
- `org.sarmidev.kardano.encoding.cbor`: `Cbor`, `CborValue`, `CborError`.

`KardanoResult` stays at the root because every package returns it; `Platform` stays at the
root so the `:shared` sample host (which calls `getPlatform()` in that package) needs no
change. `org.sarmidev.kardano.address` is **not** created here and is **not** stubbed with
placeholder files; it is introduced in Block 0.7 together with the real `Address` / CIP-19
code.

## Rationale

- Package organization improves navigability now, with no behavior change.
- Splitting into Gradle modules now would force some `internal` APIs to become `public`,
  because Kotlin `internal` is module-scoped. The current code relies on module-internal
  seams — `Bech32Variant.checksumConstant`, `Bech32.convertBits`, the `internal`
  constructor of `Bech32Decoded`, and `CardanoHrp.fromValue` — which keep working across
  subpackages in one module but would have to be widened to `public` (against
  `explicitApi()`) if those packages became separate modules.
- Future modules (`:crypto`, `:tx`, `:wallet`, `:provider`, and provider implementations)
  should be extracted only once there is code and dependency pressure to justify them
  (consistent with ADR-0002).
- The package seams introduced here are intended to make that future extraction easier
  without committing to module boundaries today.

## Consequences

- Public fully qualified names and imports change in this pre-alpha SDK (for example
  `org.sarmidev.kardano.Lovelace` becomes `org.sarmidev.kardano.primitives.Lovelace`).
  Class and type names are unchanged. This is a public **package move / source-level import
  change**, acceptable because the SDK has no external consumers yet, but it is recorded
  here explicitly rather than described as "no public API change".
- Behavior does not change.
- Tests and developer docs are updated in the same change.
- No dependencies are added and no Gradle configuration changes.

## Rejected alternatives

- **Split `:core` into multiple Gradle modules now.** Rejected: it would force `internal`
  seams public and create near-empty modules (`address`, `tx`, `wallet`) with no code to
  justify them, contradicting ADR-0002.
- **Create an empty `address` package (or placeholder file) now.** Rejected: empty
  folders carry no source and placeholder files are noise; `address` arrives with real
  code in Block 0.7.

## Follow-up work

- Block 0.7 introduces `org.sarmidev.kardano.address` with the `Address` value type and
  structural CIP-19 validation.
- Revisit Gradle module splits (`:crypto`, `:tx`, `:wallet`, `:provider`, provider
  implementations) when code and dependency pressure justify them, promoting these
  packages to modules at that point.
