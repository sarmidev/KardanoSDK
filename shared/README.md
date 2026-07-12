# :shared

Currently the sample/UI host module. It carries the Compose Multiplatform sample UI and
builds the iOS `Shared` framework that the Xcode app consumes.

## Status

Phase 0 — pre-alpha, experimental. Not audited. Not for real funds.

## Role today

- Hosts the SDK Playground (`playground/PlaygroundScreen.kt`, `playground/PlaygroundPresenter.kt`),
  introduced in Block 1.2, as the Android-facing diagnostic surface for existing `:core`/`:crypto`
  SDK behavior (address parsing, Hex, CBOR, test-wallet derivation) and, from Block 1.3a, a
  read-only "Provider" section (mock by default, with an optional live-Blockfrost toggle added
  in Block 1.3b).
- Hosts `App.kt` (theme wrapper that renders `PlaygroundScreen`) and the iOS UI entry point
  (`MainViewController.kt`).
- Retains the sample glue (`Greeting.kt`, `GreetingUtil.kt`) used by `PlaygroundScreen` to
  show the platform name.
- Depends on `:core` for encoding/address SDK logic (`Address.parse`, `Hex`, `Cbor`,
  `Platform`), on `:crypto` for the test-wallet derivation checkpoint (`Mnemonic`,
  `IcarusMasterKey`, `KeyDerivation`, `Hashing` — see "Test Wallet" below), on `:provider` for
  the read-only query boundary (`ChainQueryProvider`) and its in-memory mock, and on
  `:provider-blockfrost` for the live Blockfrost provider.

### Test Wallet section (Block 1.6d)

The "Test Wallet (derivation)" section restores `playground/TestWalletFixture.kt`'s cited
test-only BIP-39 mnemonic (the same public vector `:crypto`'s `KeyDerivationVectorsTest` and
`PublicKeyProjectionDeviceTest` already cite from `IntersectMBO/cardano-addresses`) — **never a
real mnemonic, never associated with real funds** — derives the fixed CIP-1852 path
`m/1852'/1815'/0'/0/0` via `:crypto`'s `KeyDerivation.derivePrivate`/`publicKey`, and computes
the Blake2b-224 fingerprint of the derived public key via `:crypto`'s `Hashing.blake2b224`. The
screen displays **only** the path string, the fingerprint hex, and whether it matches the cited
golden vector — never the mnemonic, entropy, seed, root/private key bytes, or the raw public
key. All derivation, projection, and hashing logic is `:crypto`'s; `PlaygroundPresenter` only
calls it and formats the result, per this file's standing rule below. Addresses are not part of
this checkpoint (Block 1.7).

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
- Builds the static iOS framework named `Shared` (`baseName = "Shared"`), consumed by
  `iosApp` via `MainViewControllerKt.MainViewController()`.

**SDK logic and the protocol/cryptographic test-vector suites belong in `:core`/`:crypto`, not
here.** `:shared` only calls `:core`/`:crypto` APIs and formats/displays results.
`PlaygroundPresenter` is a display-only mapping layer with no protocol or cryptographic rules
of its own — it does not reimplement derivation, projection, or hashing. `:shared` tests use a
minimum of cited CIP-19/CIP-1852 vectors to verify presenter wiring, but do not replicate the
`:core`/`:crypto` test-vector suites.

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
SDK-logic tests belong in `:core`/`:crypto`; `:shared` uses only a minimum of cited CIP-19/
CIP-1852 vectors for presenter-wiring verification. The test-wallet checkpoint's `commonTest`
coverage (`PlaygroundWalletPresenterTest`) is deliberately native-free — it covers only error
mapping, path formatting, and mnemonic-parsing failures that are rejected before any native
derivation call, because `:crypto`'s native backend cannot load under the Android host-JVM
target (`androidHostTest`); the end-to-end fingerprint golden check
(`PlaygroundWalletDerivationDesktopTest`) lives only in `jvmTest`, where the native backend
does load. See [docs/TESTING.md](../docs/TESTING.md) for the testing strategy and
test-vector policy.

- Desktop (JVM) tests: `./gradlew :shared:jvmTest`
- Android host tests: `./gradlew :shared:testAndroidHostTest`
- iOS simulator tests: `./gradlew :shared:iosSimulatorArm64Test`
