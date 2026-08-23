# :tx

The transaction-building module for Kardano SDK, introduced in Phase 1 Block 1.9b-1, extended
with coin selection and fee/change in Block 1.9b-2, and extended with witness-set/full-signed-
`transaction` CBOR assembly in Block 1.10b (ADR-0015).

## Status

Phase 1 — pre-alpha, experimental. Not for real funds.

## Role

- `TransactionBuilder.build(TransactionBuildRequest)` selects inputs from candidate UTxOs
  largest-first, estimates the fee, decides payment/change, and returns a `TransactionDraft`.
  This is the high-level entry point most callers want.
- `TransactionBodySerializer.serialize(TransactionBodyRequest)` is the lower-level primitive
  `TransactionBuilder` delegates to: given already-decided inputs, outputs, fee, and ttl, it
  serializes the unsigned Cardano `transaction_body` (CDDL keys `0` inputs, `1` outputs, `2`
  fee, optional `3` ttl) into canonical CBOR bytes. Useful directly when a caller has already
  done its own coin selection.
- Defines the transaction model: `TransactionOutput`, `TransactionBuildRequest`,
  `TransactionBodyRequest`, `TransactionDraft` (carries `bodyCbor()`, plus the bound
  `network` and `scope` stamped by `TransactionBodySerializer` / `TransactionBuilder`,
  ADR-0019), `TransactionDraftScope`, and the sealed `TxBuildError`. Mainnet draft
  construction remains available; signing, not this module, rejects a mainnet draft.
- Orders inputs by the ledger `(transaction_id, index)` rule and rejects duplicates; encodes
  outputs in the legacy/Alonzo `[address, coin]` array form.
- **(Block 1.11d, narrowed in 1.11d-2: ADA-only filtering)** `TransactionBuilder.build` drops
  every `TransactionBuildRequest.candidateInputs` entry with `Value.hasNativeAssets` set before
  coin selection — Phase 1 never spends a native-asset UTxO, but a wallet with a mix of
  ADA-only and native-asset UTxOs still builds from the ADA-only ones. It returns
  `TxBuildError.UnsupportedFeature` only if that filtering leaves no candidates at all (or the
  usual `TxBuildError.InsufficientFunds`, against just the ADA-only total, if the remaining
  candidates cannot cover `payment + fee`). Native-asset quantities/policy ids/asset names are
  never inspected — only the presence flag is read, and a native-asset UTxO is never selected.
- **(Block 1.10b, ADR-0015 §1/§3)** `TransactionAssembler.assemble(draft, witnessSet)` builds
  the full signed `transaction` array `[transaction_body, transaction_witness_set, true, null]`
  from an already-built `TransactionDraft` and a caller-supplied `TransactionWitnessSet`,
  embedding `draft.bodyCbor()` unchanged as field `0`. `VerificationKeyWitness` holds one
  Shelley `vkeywitness` (32-byte vkey + 64-byte signature, length-validated);
  `TransactionWitnessSet` holds a non-empty list of them and encodes only field `0`
  (`{0: [[vkey, sig], ...]}` — no script/bootstrap/Plutus witness fields are representable);
  `SignedTransaction` carries the final CBOR bytes plus the witness set. **`:tx` stays
  crypto-free**: it never derives, hashes, signs, or verifies — every byte in a
  `VerificationKeyWitness` is caller-supplied (typically `:wallet`, via `:crypto`'s `Signing`).

See [docs/DECISIONS/0014-minimal-ada-transaction-builder.md](../docs/DECISIONS/0014-minimal-ada-transaction-builder.md)
for the unsigned-body decision record, and
[docs/DECISIONS/0015-transaction-signing.md](../docs/DECISIONS/0015-transaction-signing.md) for
the Block 1.10b witness/assembly decision record.

## Fee is an estimate, not a final value

`TransactionBuilder.build` computes `fee = minFeeCoefficient * txSize + minFeeConstant`
(ADR-0014 §6) against a **sized-but-never-constructed** witness set: it accounts for exactly
one Ed25519 vkey witness per selected input and no other witness (no scripts, no multi-sig),
because `:tx` never builds a real witness set — there is no signing in this module or Phase 1
Block 1.9. The estimate is only correct under that one-vkey-witness-per-input assumption; it
must be revisited once real signing lands (Phase 1 Block 1.10) and a caller can compare the
estimate against an actually-signed transaction's true size.

The fee/change fixed-point loop is bounded (`MAX_FEE_ITERATIONS = 8`); on non-convergence it
takes the conservative (larger) of the last two estimates and rebuilds exactly once more. That
final rebuild can itself need to select more inputs — adding more witness weight than the
conservative estimate accounted for — so `build` checks it too: if the re-estimated fee still
exceeds what was just encoded, it returns `TxBuildError.FeeEstimateDidNotConverge` rather than
a `TransactionDraft` with a known-too-low fee.

`build` also validates `ProtocolParameters.minFeeCoefficient`, `minFeeConstant`, `maxTxSize`,
and `coinsPerUtxoByte` are all non-negative before using them in any arithmetic, returning
`TxBuildError.InvalidProtocolParameters` otherwise — `ProtocolParameters` is a plain data
class with no such invariant of its own, and a negative `coinsPerUtxoByte` in particular would
otherwise silently defeat the min-ADA check.

## Boundaries

- Depends only on `:core` (for `Address`, `Lovelace`, `UtxoRef`, `TxHash`, `Network`,
  `KardanoResult`, and the `encoding.cbor` subset) and `:provider` (for `Utxo`, `Value`,
  `ProtocolParameters`, the models `TransactionBuilder` selects inputs and prices fee/min-ADA
  from). `commonMain` adds no third-party dependency.
- Does **not** depend on `:wallet`, `:shared`, `:provider-blockfrost`, or `:crypto` (ADR-0014
  §1, reaffirmed by ADR-0015 §1): `:tx` is a pure, I/O-free, crypto-free function over data the
  caller supplies — Block 1.10b's `TransactionAssembler` only encodes already-computed
  `(vkey, signature)` bytes, it never derives, hashes, signs, or verifies.
- **`TransactionBuilder`/`TransactionBodySerializer` still produce only an unsigned
  `transaction_body`** — they never build a witness set or a full `transaction`.
  `TransactionAssembler` (Block 1.10b) is the one function in this module that produces a full
  signed `transaction`, and only from a caller-supplied witness set; it never rebuilds or
  alters the `TransactionDraft` body or fee it is given. No submitted-transaction concept exists
  anywhere in this module (that's Block 1.11). The transaction id (`Blake2b-256` of the body
  bytes) is computed by the caller through `:crypto`, not by `:tx` (ADR-0014 §2, ADR-0015 §3).
- **`:core` CBOR policy: one narrow addition, no other change.** The `transaction_body` map
  keys (`0`/`1`/`2`/`3`) are all single-byte integers, so `:core`'s existing RFC 8949 bytewise
  map-key-order rule coincides with the RFC 7049 §3.9 length-first order Cardano requires
  (ADR-0014 §3); that stays unchanged. Assembling the full `transaction` wrapper's fixed
  `is_valid`/`auxiliary_data` fields did require `:core`'s CBOR subset to add the three fixed
  major-type-7 simple values `true`/`false`/`null` (`CborValue.CborBool`/`CborValue.CborNull`) —
  a narrow, out-of-band addition recorded as a 2026-07-13 addendum to
  `docs/DECISIONS/0001-cbor-and-parser-policy.md`; every other major-type-7 value remains
  rejected. This coincidence/addition does **not** extend to future heterogeneous or
  multi-byte-keyed maps (multiasset, withdrawals) — see ADR-0014 §3's recorded limitation.

## Testing

- `:tx` common tests: `./gradlew :tx:jvmTest`
- Android host tests: `./gradlew :tx:testAndroidHostTest`
- iOS simulator compile: `./gradlew :tx:compileKotlinIosSimulatorArm64`

Per ADR-0014 §9 (and ADR-0015 §6 for the Block 1.10b assembly tests), tests are structural and
CDDL-derived: the serialized body / assembled `transaction` is decoded back through `:core`'s
`Cbor.decode` and inspected against the CDDL shape (field-key order, input ordering/duplicate
rejection, output encoding form, witness-set map key `0` only, `is_valid`/`auxiliary_data`
fields, defensive copies, no body/fee mutation). No `transaction_body` or full-`transaction`
golden bytes are invented (ADR-0014 §9 and ADR-0015 §6 both record that no such golden was
locatable for a minimal ADA-only body/transaction); `VerificationKeyWitness` fixtures in these
tests are synthetic byte arrays, clearly labeled as such, since `:tx` is crypto-free and cannot
produce a real signature itself. Test addresses reuse the CIP-19 "Test vectors" already cited
in `:core`'s `AddressTest`. A few `TransactionBuilder` tests use a `ProtocolParameters` with
`minFeeCoefficient = 0` to isolate the change/min-ADA decision from the size-dependent fee
formula, so an exact change amount can be asserted without duplicating `:core`'s CBOR
byte-size accounting by hand; this is a test-isolation technique, not a claim about real
Cardano fees. See [docs/TESTING.md](../docs/TESTING.md) for the project's overall testing
strategy and test-vector policy.
