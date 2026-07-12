# :wallet

The read-only wallet-state layer for Kardano SDK, introduced in Phase 1 Block 1.8a.

## Status

Phase 1 — pre-alpha, experimental. Not for real funds.

## Role

- Composes `:core` (address construction/encoding), `:crypto` (mnemonic restoration, key
  derivation, hashing), and `:provider`'s read-only `ChainQueryProvider` interface into a
  minimal read-only wallet: restore a mnemonic, derive its payment/stake keys, build its
  testnet/mainnet base address, and query a provider for its ADA balance.
- Defines `ReadOnlyWallet` (the restored wallet handle), `WalletBalance` (a provider-neutral,
  ADA-only balance model), and `WalletError` (a sealed error wrapping each upstream typed
  error).
- Introduces no persistence, transaction building, signing, or submission — see
  [docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md](../docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md)
  for the full decision record.

All fail-capable operations return `KardanoResult` (they never throw), which keeps the API
compatible with Swift/ObjC interop.

## Boundaries

- Depends on `:core`, `:crypto`, and `:provider`. `commonMain` adds no third-party dependency
  of its own; only `commonTest` uses `kotlinx-coroutines-test`.
- Does **not** depend on `:provider-blockfrost`. `ReadOnlyWallet.balance` takes a
  `ChainQueryProvider` as a parameter (dependency inversion); the caller (today, `:shared`)
  chooses whether to inject the in-memory mock or the live Blockfrost provider. `:wallet`
  itself stays provider-neutral and gains no HTTP-client dependency.
- `ReadOnlyWallet.restore` is the only entry point that reaches native cryptography
  (`:crypto`'s mnemonic/derivation/hashing backends); `ReadOnlyWallet.balance` reaches no
  native code, only the injected provider.
- `ReadOnlyWallet.restore(words, network)` accepts either SDK `Network`, mirroring
  `Address.baseAddress`'s existing policy (ADR-0012 §2): it is a pure wallet/address
  construction operation with no mainnet/testnet judgment of its own. This does **not**
  authorize mainnet use anywhere in this project's Phase 1 sample/UI surface — every Phase 1
  sample/UI caller (the Android Playground checkpoint, Block 1.8b) must pass
  `Network.TESTNET`; no Phase 1 checkpoint constructs, displays, or restores a mainnet wallet.
- A restored wallet's generated address is **not** guaranteed to have a non-zero balance under
  the default `InMemoryChainQueryProvider`: that provider only seeds its two documented sample
  addresses, so a freshly restored wallet address reads as zero-balance under the mock. This is
  intentional (ADR-0013 §7) and is not changed to make a restored wallet look funded; a live
  provider after real preprod faucet funding is the path that shows a genuinely non-zero
  balance.

## Testing

- `:wallet` common tests: `./gradlew :wallet:jvmTest`
- Android host tests: `./gradlew :wallet:testAndroidHostTest`
- iOS simulator compile: `./gradlew :wallet:compileKotlinIosSimulatorArm64`

Balance summation, error wrapping, and provider-fake UTxO queries are covered in `commonTest`
without reaching native cryptography. The end-to-end `ReadOnlyWallet.restore` check against the
cited test mnemonic (which does reach `:crypto`'s native derivation/hashing backends) lives
only in `jvmTest`, mirroring the same native-vs-host-JVM split already established for
`:crypto` and `:shared`'s Playground checkpoints. See [docs/TESTING.md](../docs/TESTING.md)
for the testing strategy and test-vector policy.
