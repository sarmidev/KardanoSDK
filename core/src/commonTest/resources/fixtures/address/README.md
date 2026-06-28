# Address fixtures (CIP-19)

Placeholder. No vectors yet — structural address validation is not implemented in Phase 0.

## Future source (authoritative)

- CIP-19 (Cardano addresses):
  <https://cips.cardano.org/cip/CIP-19>

Use the CIP-19 example addresses (testnet preferred) plus known-bad inputs (wrong
checksum, wrong network id, bad length). Validation is structural only — it does not prove
an address exists, is owned, or is spendable. Preserve and check the network id. Do not
invent addresses, and never include addresses holding real funds. See
[docs/TESTING.md](../../../../../../docs/TESTING.md).
