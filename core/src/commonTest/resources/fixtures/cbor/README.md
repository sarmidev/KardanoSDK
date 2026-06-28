# CBOR fixtures

Placeholder. No vectors yet — the CBOR subset is not implemented in Phase 0 and its
implementation policy is still Open (see
[ADR-0001](../../../../../../docs/DECISIONS/0001-cbor-and-parser-policy.md)).

## Future source (authoritative)

- RFC 8949 (CBOR), Appendix A — example encodings:
  <https://www.rfc-editor.org/rfc/rfc8949#appendix-A>

Copy examples verbatim for each supported major type. Cardano uses definite-length
encoding; indefinite-length and out-of-scope tags (e.g. bignum tags 2 and 3) must be
rejected, not normalized. Do not invent values. See
[docs/TESTING.md](../../../../../../docs/TESTING.md).
