# CBOR fixtures

The CBOR/parser policy is **Accepted** (see
[ADR-0001](../../../../../../docs/DECISIONS/0001-cbor-and-parser-policy.md)): a constrained
internal CBOR subset (definite-length only), no external dependency.

No standalone fixture files are wired here yet. Following the Bech32 approach, the Block 0.6
CBOR tests cite their RFC 8949 Appendix A vectors **inline** (with the source URL in a
comment) in `core/src/commonTest/kotlin/org/sarmidev/kardano/CborDecodeTest.kt` and
`CborEncodeTest.kt`. If a fixture-loading mechanism is added later, verbatim vectors can move
here.

## Source (authoritative)

- RFC 8949 (CBOR), Appendix A — example encodings:
  <https://www.rfc-editor.org/rfc/rfc8949#appendix-A>

## Policy

- Copy Appendix A examples verbatim for each supported type (unsigned integers, negative
  integers, byte strings, text strings, arrays, and maps). The Block 0.6 subset supports these
  only; tags, bignums, floats/simple values, and indefinite lengths are out of scope and must
  be rejected, not normalized.
- Positive examples come verbatim from Appendix A. Malformed, non-canonical, over-limit,
  unsupported, and trailing-byte cases — including the collection rule tests (element-count
  and nesting-depth limits, non-canonical map key order, and duplicate map keys) — are small
  hand-written parser edge cases, each commented with the rule it exercises; they are not
  presented as official vectors unless the bytes are copied from RFC 8949. The Appendix A map
  vectors are already in canonical key order, so they decode under the strict deterministic
  rule. Do not invent expected outputs. See
  [docs/TESTING.md](../../../../../../docs/TESTING.md).
