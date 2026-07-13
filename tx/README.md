# :tx

The transaction-building module for Kardano SDK, introduced in Phase 1 Block 1.9b-1 and
extended with coin selection and fee/change in Block 1.9b-2.

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
  `TransactionBodyRequest`, `TransactionDraft` (carries `bodyCbor()`), and the sealed
  `TxBuildError`.
- Orders inputs by the ledger `(transaction_id, index)` rule and rejects duplicates; encodes
  outputs in the legacy/Alonzo `[address, coin]` array form.

See [docs/DECISIONS/0014-minimal-ada-transaction-builder.md](../docs/DECISIONS/0014-minimal-ada-transaction-builder.md)
for the full decision record this module implements.

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
  §1): `:tx` is a pure, I/O-free, signing-free function over data the caller supplies.
- **Unsigned `transaction_body` only.** Neither `TransactionBuilder` nor
  `TransactionBodySerializer` ever produce a full `transaction` array, a witness set, a
  signature, or a submitted transaction. The transaction id (`Blake2b-256` of the body bytes)
  is computed by the caller through `:crypto`, not by `:tx` (ADR-0014 §2).
- No `:core` CBOR policy change. The `transaction_body` map keys (`0`/`1`/`2`/`3`) are all
  single-byte integers, so `:core`'s existing RFC 8949 bytewise map-key-order rule coincides
  with the RFC 7049 §3.9 length-first order Cardano requires (ADR-0014 §3); `:core` itself is
  reused unchanged. This coincidence does **not** extend to future heterogeneous or
  multi-byte-keyed maps (multiasset, withdrawals) — see ADR-0014 §3's recorded limitation.

## Testing

- `:tx` common tests: `./gradlew :tx:jvmTest`
- Android host tests: `./gradlew :tx:testAndroidHostTest`
- iOS simulator compile: `./gradlew :tx:compileKotlinIosSimulatorArm64`

Per ADR-0014 §9, tests are structural and CDDL-derived: the serialized body is decoded back
through `:core`'s `Cbor.decode` and inspected against the CDDL shape (field-key order, input
ordering/duplicate rejection, output encoding form, defensive copies). No
`transaction_body` golden bytes are invented; test addresses reuse the CIP-19 "Test vectors"
already cited in `:core`'s `AddressTest`. A few `TransactionBuilder` tests use a
`ProtocolParameters` with `minFeeCoefficient = 0` to isolate the change/min-ADA decision from
the size-dependent fee formula, so an exact change amount can be asserted without duplicating
`:core`'s CBOR byte-size accounting by hand; this is a test-isolation technique, not a claim
about real Cardano fees. See [docs/TESTING.md](../docs/TESTING.md) for the project's overall
testing strategy and test-vector policy.
