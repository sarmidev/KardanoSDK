# :shared

Currently the sample/UI host module. It carries the Compose Multiplatform sample UI and
builds the iOS `Shared` framework that the Xcode app consumes.

## Status

Phase 1 — pre-alpha, experimental. Not for real funds.

## Role today

- Hosts the SDK Playground (`playground/PlaygroundScreen.kt`, `playground/PlaygroundPresenter.kt`),
  introduced in Block 1.2, as the Android-facing diagnostic surface for existing `:core`/
  `:crypto`/`:wallet`/`:tx`/`:provider` SDK behavior (address parsing, Hex, CBOR, test-wallet
  derivation + address generation, read-only wallet balance, an unsigned transaction-draft
  checkpoint, a signed-but-not-submitted transaction checkpoint, and a submit-transaction
  checkpoint) and, from Block 1.3a, a read-only "Provider" section (mock by default, with an
  optional live-Blockfrost toggle added in Block 1.3b).
- Hosts `App.kt` (theme wrapper that renders `PlaygroundScreen`) and the iOS UI entry point
  (`MainViewController.kt`).
- Retains the sample glue (`Greeting.kt`, `GreetingUtil.kt`) used by `PlaygroundScreen` to
  show the platform name.
- Depends on `:core` for encoding/address SDK logic (`Address.parse`, `Address.baseAddress`,
  `Address.toBech32()`, `AddressCredential`, `Hex`, `Cbor`, `Platform`), on `:crypto` for the
  test-wallet derivation checkpoint (`Mnemonic`, `IcarusMasterKey`, `KeyDerivation`, `Hashing`
  — see "Test Wallet & Address Generation" below), on `:provider` for the read-only query
  boundary (`ChainQueryProvider`) and its in-memory mock, and, from Block 1.11a, the submit
  boundary (`TxSubmitProvider`, `SubmitError`) and its in-memory mock, on `:provider-blockfrost`
  for the live Blockfrost query provider and, from Block 1.11b, the live Blockfrost submit
  provider (`BlockfrostTxSubmitProvider`), on `:wallet` (Block 1.8b) for the read-only
  wallet-balance checkpoint (`ReadOnlyWallet`, `WalletBalance`, `WalletError` — see "Wallet
  Balance" below), and, from Block 1.9c, on `:tx` for the unsigned transaction-draft checkpoint
  (`TransactionBuilder`, `TransactionBuildRequest`, `TransactionDraft`, `TxBuildError` — see
  "Transaction Draft" below). Block 1.10c (signing) and Block 1.11c (submission) reuse these
  same `:wallet`/`:tx`/`:provider` dependencies — `ReadOnlyWallet.signTransaction`,
  `WalletSignedTransaction`, and `TxSubmitProvider.submit` — with no new Gradle module added
  (see "Signed Transaction" and "Submit Transaction" below).
- Builds the static iOS framework named `Shared` (`baseName = "Shared"`), consumed by
  `iosApp` via `MainViewControllerKt.MainViewController()`.

### Test Wallet & Address Generation section (Block 1.6d, extended by Block 1.7b)

The "Test Wallet & Address Generation" section restores `playground/TestWalletFixture.kt`'s
cited test-only BIP-39 mnemonic (the same public vector `:crypto`'s `KeyDerivationVectorsTest`
and `PublicKeyProjectionDeviceTest` already cite from `IntersectMBO/cardano-addresses`) —
**never a real mnemonic, never associated with real funds** — and derives the two fixed
CIP-1852 paths `paymentPath` (`m/1852'/1815'/0'/0/0`) and `stakePath` (`m/1852'/1815'/0'/2/0`)
via `:crypto`'s `KeyDerivation.derivePrivate`/`publicKey`. Each derived public key's
Blake2b-224 credential hash is computed via `:crypto`'s `Hashing.blake2b224`, wrapped with
`:core`'s `AddressCredential.keyHash(...)`, and passed to
`Address.baseAddress(Network.TESTNET, paymentCredential, stakeCredential)`
(Block 1.7a). The generated address is immediately re-parsed with
`Address.parse(address.toBech32())` for a structural round-trip check. The screen displays
**only** both path strings, both credential-hash hex values (public CIP-19 credentials, not
secret key material), the generated `addr_test1...` address, and the round-trip status —
never the mnemonic, entropy, seed, root/private key bytes, or a raw public key. All
derivation, projection, hashing, credential, and address-encoding logic belongs to
`:crypto`/`:core`; `PlaygroundPresenter` only calls it and formats the result, per this file's
standing rule below. This is structural address generation only: no signing, no transaction
logic, and no claim that the generated address is owned, funded, or registered.

### Provider section

The "Provider" section exercises `:provider`'s read-only `ChainQueryProvider`. It defaults to
`InMemoryChainQueryProvider`, whose data is **fake and test-only** — no real network, no funds,
no secrets, no committed chain fixtures. Two documented seed addresses (both valid public
CIP-19 testnet vectors) drive the mock checkpoint:

- Has UTxOs: `addr_test1vz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerspjrlsz`
  (`InMemoryChainQueryProvider.SEED_ADDRESS_WITH_UTXOS`).
- Empty: `addr_test1qz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgs68faae`
  (`InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY`).

The screen provides one-tap buttons to fill either seed address.

A "Use live Blockfrost (preprod)" toggle (Block 1.3b) switches the same section to a live
`BlockfrostChainQueryProvider` (`:provider-blockfrost`) built from a `project_id` you paste in.
That key is held only in non-persistent Compose state (`remember`, not `rememberSaveable`) — it
is never stored, saved, or logged — and live calls hit the real preprod network (test funds).
No key is committed to the repo. See
[docs/DECISIONS/0006-provider-boundary-and-strategy.md](../docs/DECISIONS/0006-provider-boundary-and-strategy.md)
and [docs/DECISIONS/0007-http-client-and-blockfrost-provider.md](../docs/DECISIONS/0007-http-client-and-blockfrost-provider.md).

### Wallet Balance section (Block 1.8b)

The "Wallet Balance (read-only)" section restores the same `TestWalletFixture` mnemonic as the
Test Wallet section above, but through `:wallet`'s `ReadOnlyWallet.restore(TestWalletFixture.words,
Network.TESTNET)` — always `Network.TESTNET`; that call site, not `ReadOnlyWallet.restore`
itself, is what enforces the Phase 1 no-mainnet boundary here (`ReadOnlyWallet.restore` is
generic over `Network`, see [docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md](../docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md)
§3). It then queries whichever `ChainQueryProvider` is currently selected in the Provider
section above (mock or live) via `wallet.balance(provider)` and displays only the generated
`addr_test1...` address, the UTxO count, and the balance in lovelace — never the mnemonic,
seed, entropy, or any private/raw key bytes. `:shared` reimplements none of mnemonic parsing,
derivation, hashing, address generation, or balance summation; all of that logic belongs to
`:wallet`/`:crypto`/`:core`, and `PlaygroundPresenter.presentWalletBalance` only calls it and
formats the result. A zero balance/UTxO count under the default `InMemoryChainQueryProvider` is
the expected, honest result (ADR-0013 §7) — that provider has no fake UTxOs seeded for this
generated address — and is displayed as a normal success, not an error; a live Blockfrost
preprod provider can show a non-zero balance only after the generated address is funded with
test ADA from a preprod faucet.

### Transaction Draft section (Block 1.9c)

The "Transaction Draft (unsigned)" section restores the same `TestWalletFixture` mnemonic as
the Wallet Balance section above (always `Network.TESTNET`, via `ReadOnlyWallet.restore`),
queries whichever `ChainQueryProvider` is currently selected in the Provider section for that
wallet's candidate UTxOs and the current `ProtocolParameters`, and calls `:tx`'s
`TransactionBuilder.build(TransactionBuildRequest)` to build a minimal, single-payment,
**unsigned** ADA transaction: a fixed 2 ADA payment to a reused cited CIP-19 testnet vector
(`InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY`, already used elsewhere in this Playground as a
provider seed address — not invented for this checkpoint), with any change returned to the
restored wallet's own address. `:shared` performs no coin selection, fee estimation, change
decision, or CBOR encoding itself — all of that belongs to `:tx`
(`TransactionBuilder`/`TransactionBodySerializer`), and `PlaygroundPresenter.presentTransactionDraft`
only builds the request and formats the result. On success the screen shows only the selected
input and output counts, the fee and (if present) change amounts in lovelace, the encoded body
size in bytes, and a truncated hex preview of the body bytes — always labeled as an unsigned
draft. On failure (for example no UTxOs, insufficient funds, or an amount below minimum ADA) the
screen shows a message distinguishing the cause, mapped from `:tx`'s typed `TxBuildError`. Under
the default `InMemoryChainQueryProvider`, the restored wallet's address has no fake UTxOs seeded
for it — same honest-empty behavior as the Wallet Balance section (ADR-0013 §7) — so this section
normally reports "no UTxOs" as the expected mock result, not a failure; a live Blockfrost preprod
provider can build a real draft only after that address is funded with test ADA from a preprod
faucet. **No signing, no witness construction, no transaction id hashing, and no submission**
anywhere in this checkpoint — see
[docs/DECISIONS/0014-minimal-ada-transaction-builder.md](../docs/DECISIONS/0014-minimal-ada-transaction-builder.md).

**ADA-only filtering (Block 1.11d, narrowed in 1.11d-2).** A manual Android checkpoint found
that a preprod address funded with mixed (ADA + native-asset) UTxOs let a draft build and sign,
then get rejected by the node at submit time (`ValueNotConservedUTxO`) once the built
transaction implicitly dropped the native assets those inputs carried. `:tx`'s
`TransactionBuilder` now drops every UTxO with `Value.hasNativeAssets` set before selecting
inputs, so a wallet with a mix of ADA-only and native-asset UTxOs still builds normally from
just the ADA-only ones; it only fails (`TxBuildError.UnsupportedFeature`) when that leaves no
candidates at all, and `presentTxBuildError` then shows a dedicated message: "This wallet has
no ADA-only UTxOs to spend — only UTxOs containing native assets/tokens. Phase 1 only builds
ADA-only transactions." This is honest filtering, not multi-asset support: no token quantities,
policy ids, sending, or change-preserving logic were added anywhere in this stack, and a
native-asset UTxO is never selected as an input.

### Signed Transaction (not submitted) section (Block 1.10c)

The "Signed Transaction (not submitted)" section builds the same unsigned draft as the
Transaction Draft section above — through a shared `PlaygroundPresenter.buildTransactionDraft`
helper extracted from that checkpoint so both sections build the identical draft — then signs it
by calling `:wallet`'s `ReadOnlyWallet.signTransaction(TestWalletFixture.words, Network.TESTNET,
draft)`, always passing the cited test-only fixture words and `Network.TESTNET` explicitly:
`:wallet` itself is not fixture-aware and enforces neither (ADR-0015 §2a), so this call site is
what keeps this checkpoint on the fixture/testnet-only path. `:shared` performs no hashing,
signing, or witness/CBOR assembly itself — all of that belongs to `:wallet` (which itself
delegates to `:crypto`'s `Signing` and `:tx`'s `TransactionAssembler`) — and
`PlaygroundPresenter.presentSignedTransaction` only calls it and formats the result. On success
the screen shows only the 32-byte transaction id (hex), the witness count (always `1` for this
single-key checkpoint), a truncated hex preview of the full signed `transaction` CBOR, and an
explicit `signed, not submitted — testnet-only, test fixture, no real funds` label — never the
mnemonic, seed, private/root key bytes, or the full (untruncated) signed CBOR. On failure the
screen shows a message distinguishing the cause, covering both the same draft-building failures
the Transaction Draft section can report and every `WalletError` `ReadOnlyWallet.signTransaction`
itself can return (a signing failure or a witness/transaction-assembly failure). Under the
default `InMemoryChainQueryProvider`, the restored wallet's address has no fake UTxOs seeded for
it — same honest-empty behavior as the sections above — so this section normally reports "no
UTxOs" as the expected mock result, not a failure; a live Blockfrost preprod provider can sign a
real draft only after that address is funded with test ADA from a preprod faucet. **No
submission anywhere in this checkpoint** — submitting a transaction is Block 1.11, see
[docs/DECISIONS/0015-transaction-signing.md](../docs/DECISIONS/0015-transaction-signing.md).

### Submit Transaction (preprod) section (Block 1.11c)

The "Submit Transaction (preprod)" section builds and signs the same fixture transaction as
the Signed Transaction section above — through `PlaygroundPresenter.presentSubmitTransaction`,
which reuses the exact same `buildTransactionDraft` + `ReadOnlyWallet.signTransaction` sequence
— then calls `:provider`'s `TxSubmitProvider.submit(signed.signedTransaction.cbor())` directly
on the resulting `WalletSignedTransaction`. **No new `:wallet` orchestration method was added
for this** (ADR-0017 "Non-goals"): the presenter sequences build → sign → submit itself, and
the accepted-id/local-id comparison lives in the presenter, not in `:wallet` or `:provider`.

A new `activeSubmitProvider: TxSubmitProvider` is wired alongside the existing `activeProvider:
ChainQueryProvider`, gated by the same "Use live Blockfrost (preprod)" toggle and `project_id`
field the Provider section already uses (no second key field is added): the default is
`InMemoryTxSubmitProvider()` (fake/test-only — it always returns
`SubmitError.SubmissionNotSupported`, per ADR-0017, never a fake accepted id); enabling the
toggle with a `project_id` switches to a live `BlockfrostTxSubmitProvider.create(BlockfrostConfig(projectId
= key))` (real preprod submission, test funds only, never mainnet). On success the screen
shows only the accepted transaction id, the locally-signed transaction id, whether the two
match (with a readable mismatch note if they do not), and an explicit `submitted to preprod —
testnet-only, test fixture, no real funds` label. On failure the screen shows a message
distinguishing the cause, covering every `SubmitError` variant (including
`SubmissionNotSupported`'s explicit "this provider does not support submission (mock)"
message) and every upstream draft-building/signing failure the Transaction Draft and Signed
Transaction sections can already report. **No automatic polling**: once a submission is
accepted, the screen shows the accepted id once, for a manual preprod-explorer lookup — a
single-shot submit-and-display checkpoint has no justification yet for the added complexity
(see `PlaygroundPresenter.presentSubmitTransaction`'s KDoc). See
[docs/DECISIONS/0017-transaction-submission-boundary.md](../docs/DECISIONS/0017-transaction-submission-boundary.md).

**SDK logic and the protocol/cryptographic test-vector suites belong in `:core`/`:crypto`/
`:wallet`/`:tx`, not here.** `:shared` only calls `:core`/`:crypto`/`:provider`/`:wallet`/`:tx`
APIs and formats/displays results. `PlaygroundPresenter` is a display-only mapping layer with no
protocol or cryptographic rules of its own — it does not reimplement derivation, projection,
hashing, address generation, balance summation, coin selection, fee/change computation, or CBOR
encoding. `:shared` tests use a minimum of cited CIP-19/CIP-1852 vectors to verify presenter
wiring, but do not replicate the `:core`/`:crypto`/`:wallet`/`:tx` test-vector suites.

## Why it still contains UI

The SDK core direction is UI-free and lives in `:core`. `:shared` keeps Compose because the
iOS app needs a Kotlin-produced UI framework. Removing Compose from `:shared` outright would
break the iOS sample app.

## Planned direction

`:shared` is expected to migrate toward a dedicated sample module (a candidate `:sample:*`
name) in a later step. It is intentionally not renamed now to avoid changing the iOS Xcode
project. See [docs/DECISIONS/0002-module-structure.md](../docs/DECISIONS/0002-module-structure.md).

## Consumers

- `:androidApp`, `:desktopApp` depend on `:shared`.
- `iosApp` (Xcode) links the `Shared` framework produced here.

## Testing

`:shared` carries example tests in `commonTest`, `jvmTest`, `androidHostTest`, and `iosTest`
that demonstrate the wiring per target. The protocol/cryptographic test-vector suites and
SDK-logic tests belong in `:core`/`:crypto`/`:wallet`; `:shared` uses only a minimum of cited
CIP-19/CIP-1852 vectors for presenter-wiring verification. The test-wallet + address-generation
checkpoint's `commonTest` coverage (`PlaygroundWalletPresenterTest`) is deliberately
native-free — it covers only error mapping, path formatting, and mnemonic-parsing failures
that are rejected before any native derivation call, because `:crypto`'s native backend
cannot load under the Android host-JVM target (`androidHostTest`); the end-to-end
fingerprint/address golden check (`PlaygroundWalletDerivationDesktopTest`) lives only in
`jvmTest`, where the native backend does load — it asserts the cited golden payment
credential and a structural generate-then-parse round trip, never a self-generated address
pinned as if it were an external vector. The wallet-balance checkpoint follows the same split:
`PlaygroundWalletBalancePresenterTest` (`commonTest`) is native-free, feeding constructed
`WalletBalance`/`WalletError` values and a `Address.parse`-derived address into
`mapWalletBalanceResult`/`presentWalletError` directly; `PlaygroundWalletBalanceDesktopTest`
(`jvmTest`-only) is the only place `presentWalletBalance` and `ReadOnlyWallet.restore` run end
to end together, asserting the honest zero balance under the default mock and that the
checkpoint's own restore call uses `Network.TESTNET`. The transaction-draft checkpoint follows
the same split: `PlaygroundTransactionDraftPresenterTest` (`commonTest`) is native-free, building
real `TransactionDraft`/`TxBuildError` values via `TransactionBuilder.build` against hand-built
fake UTxOs and cited CIP-19 addresses (no mnemonic, no native call) and feeding them into
`mapTransactionDraftResult`/`presentTxBuildError` directly; `PlaygroundTransactionDraftDesktopTest`
(`jvmTest`-only) is the only place `presentTransactionDraft` and `ReadOnlyWallet.restore` run end
to end together, asserting the honest "no UTxOs" result under the default mock and a successful
draft once the mock is seeded with a UTxO for the restored wallet's own address.
`PlaygroundTransactionDraftPresenterTest` also covers the Block 1.11d/1.11d-2 ADA-only
filtering: a hand-built, sole `Utxo` with `Value.hasNativeAssets = true` fed through the real
`TransactionBuilder` is rejected with `TxBuildError.UnsupportedFeature` (message asserted to
mention "native" and "ADA-only"), while a *mixed* candidate list (one native-asset UTxO plus a
sufficient ADA-only one) builds successfully and selects only the ADA-only input;
`PlaygroundTransactionDraftDesktopTest` covers both the sole-native-asset rejection and the
mixed-candidates success end to end, once seeded for the restored wallet's own address, without
a live Blockfrost call. The signed-
transaction checkpoint (Block 1.10c) follows the same split:
`PlaygroundSignedTransactionPresenterTest` (`commonTest`) is native-free, feeding constructed
`WalletError` values (`Signing`, `TransactionAssembly`) into `mapSignedTransactionResult`/
`presentSigningError`/`presentWalletError` directly (no mnemonic, no native call);
`PlaygroundSignedTransactionDesktopTest` (`jvmTest`-only) is the only place
`presentSignedTransaction` and `ReadOnlyWallet.signTransaction` run end to end together,
asserting the honest "no UTxOs" result under the default mock, and — once the mock is seeded
with a UTxO for the restored wallet's own address — a successful signed transaction whose rows
carry a well-formed 32-byte hex transaction id, exactly one witness, a truncated CBOR preview,
the exact not-submitted/testnet/fixture label, and none of the fixture's mnemonic words. The
submit-transaction checkpoint (Block 1.11c) follows a related but slightly different split:
`PlaygroundSubmitTransactionPresenterTest` (`commonTest`) is native-free and, unlike the
signed-transaction split, covers **both** branches of its raw-result mapper
(`mapSubmitTransactionResult`) — its accepted-id parameter is a plain `TxHash` (a `:core` value
constructible from any 32 bytes, no native call needed), not a `:wallet`-internal type — so
both the accepted/local-id match-and-mismatch cases and every `SubmitError` variant
(`presentSubmitError`) are exercised directly; `PlaygroundSubmitTransactionDesktopTest`
(`jvmTest`-only) is the only place `presentSubmitTransaction` runs end to end (it reaches
`ReadOnlyWallet.signTransaction`'s native backend), asserting the honest "no UTxOs" result
under the default mock and, once the mock query provider is seeded with a UTxO for the
restored wallet's own address, that the mock submit provider still reports its honest
not-supported failure rather than a fake accepted id — there is no automated end-to-end
*success* path, since an actual accepted submission only comes from a live Blockfrost preprod
call, which these tests must not perform. See [docs/TESTING.md](../docs/TESTING.md) for the
testing strategy and test-vector policy.

- Desktop (JVM) tests: `./gradlew :shared:jvmTest`
- Android host tests: `./gradlew :shared:testAndroidHostTest`
- iOS simulator tests: `./gradlew :shared:iosSimulatorArm64Test`
