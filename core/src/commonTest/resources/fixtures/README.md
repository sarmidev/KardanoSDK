# Test fixtures (`:core`)

Test input/expected-output data for `:core` tests. Fixtures are kept separate from
implementation and from test code. See [docs/TESTING.md](../../../../../docs/TESTING.md)
for the full policy.

## Status

No protocol vectors exist yet. Phase 0 has not implemented Bech32, CBOR, or address
parsing. The subfolders below are placeholders that name the authoritative source for the
vectors that will live there once the matching feature is implemented.

## Layout

- `bech32/` — BIP-173 / BIP-350 vectors (added with the Bech32 implementation).
- `cbor/` — RFC 8949 Appendix A vectors (added with the CBOR subset implementation).
- `address/` — CIP-19 vectors (added with address structural validation).

## Rules (summary)

- Vectors are copied verbatim from cited specs or trusted reference implementations.
- Generated or AI-invented vectors are not allowed.
- Each fixture file cites its source spec and URL in a header comment.
- Invalid vectors stay invalid; validators are never weakened to make a test pass.
- No real mnemonics, private keys, or anything touching real funds — ever.
