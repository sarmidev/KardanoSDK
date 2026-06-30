# Address fixtures (CIP-19)

## Source (authoritative)

- CIP-19 (Cardano addresses), "Test vectors" section:
  <https://github.com/cardano-foundation/CIPs/blob/master/CIP-0019/README.md>
  (also <https://cips.cardano.org/cip/CIP-19>)

## Vectors in use (Block 0.7 Steps 1-3)

The Block 0.7 address parser covers, so far, the base (CIP-19 header types 0-3), pointer
(header types 4 and 5), enterprise (header types 6 and 7), and reward/stake (header types
14 and 15) Shelley types. The mainnet and testnet `type-00`, `type-01`, `type-02`,
`type-03`, `type-04`, `type-05`, `type-06`, `type-07`, `type-14`, and `type-15` example
addresses are copied **verbatim** from the CIP-19 "Test vectors" section into the constants
in `core/src/commonTest/.../address/AddressTest.kt`, with the source cited there. They are
not duplicated into a separate fixture file; this README records their source.

Step 1 added the single-credential types (`type-06/07/14/15`). Step 2 added the base
types (`type-00/01/02/03`), exposing both a payment credential and a stake (delegation)
credential. Step 3 added the pointer types (`type-04/05`): a payment credential plus a chain
pointer. CIP-19 documents the pointer used to generate every `type-04`/`type-05` vector as
`(slot=2498243, transactionIndex=27, certificateIndex=3)`; the tests assert exactly these
spec-provided coordinates (they are not invented).

## Rules

- Valid addresses are only the verbatim CIP-19 strings; none are invented or derived.
- Invalid/edge inputs in the tests are hand-written rule tests derived from a cited CIP-19
  vector (decode, mutate one field, re-encode). They are labeled as such in the test source
  and are never presented as CIP-19 vectors.
- Validation is structural only — it does not prove an address exists, is owned, or is
  spendable. The network id is preserved and checked against the HRP.
- Never include addresses holding real funds. See
  [docs/TESTING.md](../../../../../../docs/TESTING.md).
