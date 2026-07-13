# :shared

Currently the sample/UI host module. It carries the Compose Multiplatform sample UI and
builds the iOS `Shared` framework that the Xcode app consumes.

## Status

Phase 1 — pre-alpha, experimental. Not for real funds.

## Role today

- Hosts the SDK Playground (`playground/PlaygroundScreen.kt`, `playground/PlaygroundPresenter.kt`),
  introduced in Block 1.2, as the Android-facing diagnostic surface for existing `:core`/
  `:crypto`/`:wallet`/`:tx` SDK behavior (address parsing, Hex, CBOR, test-wallet derivation +
  address generation, read-only wallet balance, and an unsigned transaction-draft checkpoint)
  and, from Block 1.3a, a read-only "Provider" section (mock by default, with an optional
  live-Blockfrost toggle added in Block 1.3b).
- Hosts `App.kt` (theme wrapper that renders `PlaygroundScreen`) and the iOS UI entry point
  (`MainViewController.kt`).
- Retains the sample glue (`Greeting.kt`, `GreetingUtil.kt`) used by `PlaygroundScreen` to
  show the platform name.
- Depends on `:core` for encoding/address SDK logic (`Address.parse`, `Address.baseAddress`,
  `Address.toBech32()`, `AddressCredential`, `Hex`, `Cbor`, `Platform`), on `:crypto` for the
  test-wallet derivation checkpoint (`Mnemonic`, `IcarusMasterKey`, `KeyDerivation`, `Hashing`
  — see "Test Wallet & Address Generation" below), on `:provider` for the read-only query
  boundary (`ChainQueryProvider`) and its in-memory mock, on `:provider-blockfrost` for the
  live Blockfrost provider, on `:wallet` (Block 1.8b) for the read-only wallet-balance
  checkpoint (`ReadOnlyWallet`, `WalletBalance`, `WalletError` — see "Wallet Balance" below),
  and, from Block 1.9c, on `:tx` for the unsigned transaction-draft checkpoint
  (`TransactionBuilder`, `TransactionBuildRequest`, `TransactionDraft`, `TxBuildError` — see
  "Transaction Draft" below).
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
draft once the mock is seeded with a UTxO for the restored wallet's own address. See
[docs/TESTING.md](../docs/TESTING.md) for the testing strategy and test-vector policy.

- Desktop (JVM) tests: `./gradlew :shared:jvmTest`
- Android host tests: `./gradlew :shared:testAndroidHostTest`
- iOS simulator tests: `./gradlew :shared:iosSimulatorArm64Test`
