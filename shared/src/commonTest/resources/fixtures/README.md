# Test fixtures (`:shared`)

`:shared` is the sample/UI host module, not the SDK core. Protocol vectors (Bech32, CBOR,
addresses) belong in `:core` at `core/src/commonTest/resources/fixtures/`, alongside the
logic they exercise.

Do not place protocol test vectors here. If a sample-only fixture is ever needed, it must
still follow the policy in [docs/TESTING.md](../../../../../docs/TESTING.md): no invented
vectors, no real mnemonics, private keys, or anything touching real funds, and every
fixture cites its source.
