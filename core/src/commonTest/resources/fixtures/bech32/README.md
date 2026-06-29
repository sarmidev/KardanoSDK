# Bech32 / Bech32m fixtures

The generic Bech32/Bech32m codec is implemented in `:core` per
[ADR-0001](../../../../../../docs/DECISIONS/0001-cbor-and-parser-policy.md) (Accepted).

The official BIP-173 and BIP-350 valid and invalid vectors are embedded verbatim in the
test source (`core/src/commonTest/kotlin/org/sarmidev/kardano/Bech32Test.kt`), each block
citing its source URL, rather than as separate resource files: `:core` has no shared
(common) resource loader wired up, and the existing tests (for example `HexTest`) keep
vectors inline. This folder is kept as the documented home for any future Bech32 vector
files.

## Source (authoritative)

- BIP-173: <https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki>
- BIP-350: <https://github.com/bitcoin/bips/blob/master/bip-0350.mediawiki>

Both valid and invalid vectors are used verbatim. Do not invent or modify values; invalid
vectors stay invalid. See
[docs/TESTING.md](../../../../../../docs/TESTING.md).
