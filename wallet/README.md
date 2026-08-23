# :wallet

The read-only wallet-state layer for Kardano SDK, introduced in Phase 1 Block 1.8a and extended
with scoped transaction-signing orchestration in Block 1.10b (ADR-0015).

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
- **(Block 1.10b, ADR-0015 §1/§2a)** `ReadOnlyWallet.signTestnetFixtureTransaction(words, network,
  draft)` signs an already-built `TransactionDraft` (from `:tx`) with the account-0 payment key
  derived from `words`: it hashes the draft's body (`Blake2b-256`, via `:crypto`'s `Hashing`) to
  the 32-byte `bodyHash`/transaction id, signs that hash (via `:crypto`'s `Signing`) — never the
  raw body bytes — projects the payment public key for the witness `vkey`, and assembles a
  single-witness signed `transaction` (via `:tx`'s `TransactionAssembler`). Returns a
  `WalletSignedTransaction` pairing the `:tx` `SignedTransaction` with the computed transaction
  id. It takes the same explicit `(words, network)` inputs `restore` already takes, plus a
  `TransactionDraft` — `network` is not read by the implementation (payment-key derivation and
  signing are network-independent, and this function builds no address); it is kept purely so
  the signature mirrors `restore`'s shape and every call site still declares the network it
  intends to sign for (ADR-0015 §1/§2a). It is **not** a general-purpose wallet signing API —
  see "Boundaries" below for the exact scope. The mnemonic and both derived payment key handles
  are cleared in a `finally` block on every path.
- **(2026-08-23, ADR-0018)** `signTestnetFixtureTransaction` requires an explicit
  `@OptIn(ExperimentalKardanoSigningScope::class)` at every call site. This is a
  **compiler/IDE-visible intent signal, not a runtime enforcement check**: opting in does not
  verify the mnemonic is the fixture, the network is testnet, or that the draft was built for
  the declared network — see `ExperimentalKardanoSigningScope`'s own KDoc. The opt-in requirement
  is Kotlin-compiler-only and does not carry over to Swift/iOS consumers of the compiled
  `:shared` framework.
- Introduces no persistence or submission — see
  [docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md](../docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md)
  for the read-only decision record and
  [docs/DECISIONS/0015-transaction-signing.md](../docs/DECISIONS/0015-transaction-signing.md)
  for the Block 1.10b signing-orchestration decision record.

All fail-capable operations return `KardanoResult` (they never throw), which keeps the API
compatible with Swift/ObjC interop.

## Boundaries

- Depends on `:core`, `:crypto`, and `:provider`. Block 1.10b (ADR-0015 §1) added a new
  `:wallet → :tx` dependency (for `TransactionDraft`/`TransactionAssembler`/witness types) — an
  acyclic edge, since `:tx` does not depend on `:wallet`. `commonMain` adds no third-party
  dependency of its own; only `commonTest` uses `kotlinx-coroutines-test`.
- Does **not** depend on `:provider-blockfrost`. `ReadOnlyWallet.balance` takes a
  `ChainQueryProvider` as a parameter (dependency inversion); the caller (today, `:shared`)
  chooses whether to inject the in-memory mock or the live Blockfrost provider. `:wallet`
  itself stays provider-neutral and gains no HTTP-client dependency.
- **Still does not depend on `:shared`** (ADR-0011 §3, reaffirmed by ADR-0015 §2a): `:wallet`
  cannot recognize `:shared`'s `TestWalletFixture`, so `signTestnetFixtureTransaction` accepts
  whatever `words`/`network`/`draft` it is given. **Block 1.10 signing is scoped to
  testnet/preprod, the existing Phase 1 test fixture, and ADA-only single-payment
  `TransactionBuilder` drafts** by Phase 1 call-site/checkpoint/test discipline, not by a
  `:wallet`-internal check — the function's name and its `ExperimentalKardanoSigningScope`
  opt-in requirement (ADR-0018) say this explicitly, but neither is a runtime check; do not
  treat `signTestnetFixtureTransaction` as a general-purpose or public wallet signing API.
  Widening that scope requires its own later, explicit block/ADR (a `TransactionDraft`
  network-binding redesign is already scheduled per ADR-0018 §4, not yet implemented).
- `ReadOnlyWallet.restore` and `ReadOnlyWallet.signTestnetFixtureTransaction` are the entry
  points that reach native cryptography (`:crypto`'s mnemonic/derivation/hashing/signing
  backends); `ReadOnlyWallet.balance` reaches no native code, only the injected provider.
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

Balance summation, error wrapping, provider-fake UTxO queries, and
`signTestnetFixtureTransaction`'s mnemonic-rejection paths are covered in `commonTest` without
reaching native cryptography. The end-to-end `ReadOnlyWallet.restore` and
`ReadOnlyWallet.signTestnetFixtureTransaction` checks against the cited test mnemonic (which do
reach `:crypto`'s native derivation/hashing/signing backends) live only in `jvmTest`, mirroring
the same native-vs-host-JVM split already established for `:crypto` and `:shared`'s Playground
checkpoints. `signTestnetFixtureTransaction`'s `jvmTest` coverage is a labeled self-consistency
check (ADR-0015 §6): it independently re-derives the same payment key and body hash and checks
`signTestnetFixtureTransaction`'s output against that independent computation, since no external
signed-transaction golden exists to cite for a minimal ADA-only transaction. Every test call site
carries the explicit `@OptIn(ExperimentalKardanoSigningScope::class)` any other caller must also
write (ADR-0018). See [docs/TESTING.md](../docs/TESTING.md) for the testing strategy and
test-vector policy.
