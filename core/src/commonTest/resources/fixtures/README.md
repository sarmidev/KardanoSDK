# Test fixtures (`:core`)

Test input/expected-output data for `:core` tests. Fixtures are kept separate from
implementation and from test code. See [docs/TESTING.md](../../../../../docs/TESTING.md)
for the full policy.

## Status

The generic Bech32/Bech32m codec is implemented; its official BIP-173/BIP-350 vectors are
embedded verbatim in the `:core` test source (with cited source URLs) rather than as
resource files, because `:core` has no shared (common) resource loader (see `bech32/`).
CBOR and address parsing are not implemented yet. The subfolders below name the
authoritative source for the vectors of each area.

## Layout

- `bech32/` — BIP-173 / BIP-350 vectors (implemented; vectors embedded in the test source).
- `cbor/` — RFC 8949 Appendix A vectors (added with the CBOR subset implementation).
- `address/` — CIP-19 vectors (added with address structural validation).

## Rules (summary)

- Vectors are copied verbatim from cited specs or trusted reference implementations.
- Generated or AI-invented vectors are not allowed.
- Each fixture file cites its source spec and URL in a header comment.
- Invalid vectors stay invalid; validators are never weakened to make a test pass.
- No real mnemonics, private keys, or anything touching real funds — ever.
