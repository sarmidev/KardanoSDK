# ADR-0013: Wallet Boundary And Read-Only State

| Field   | Value                                                                 |
|---------|------------------------------------------------------------------------|
| Status  | **Accepted**                                                          |
| Scope   | Block 1.8a — `:wallet` module creation, read-only wallet public API shape, error model, no-persistence stance |
| Phase   | Phase 1 (Block 1.8a)                                                  |
| Updated | 2026-07-12                                                            |

---

## Context

ADR-0009 §1 named the `:wallet` extraction trigger precisely: "the first block that composes
derivation with non-crypto concerns — account/address orchestration, wallet state, or
persistence." ADR-0011 §2 confirmed Block 1.7 (address generation, a pure function over
already-derived key material) does not fire that trigger, and deferred `:wallet`'s
creation/ownership/API-shape decision to Block 1.8 (Wallet State Read-Only), the first block
that holds wallet state and composes it with a provider query.

By the end of Block 1.7b, `:core` can build and canonically encode a Shelley base address
from already-computed credentials (`AddressCredential.keyHash`/`scriptHash`,
`Address.baseAddress`, `Address.toBech32()`), `:crypto` can restore a cited test-only mnemonic
and derive/hash CIP-1852 payment and stake public keys, and `:provider`/`:provider-blockfrost`
expose a read-only, provider-neutral `ChainQueryProvider` (UTxOs by address, protocol
parameters, chain tip). No existing module composes all three: `:core` is dependency-free by
design, `:crypto` and `:provider` each depend only on `:core`, and `:shared` (which does depend
on all three) is sample/UI-only per ADR-0011 §3 and must not own SDK logic. Block 1.8 needs
exactly this composition — restore a wallet, derive its address, query UTxOs, calculate an ADA
balance — so this ADR resolves the deferred module/API decision before any 1.8 code is written.

---

## Decision

### 1. Create a new Gradle module `:wallet`

A new module, not a package inside an existing module. This is the ADR-0009 §1 trigger firing
for the first time: wallet state (a restored address plus its derivation paths) composed with
a provider query is orchestration, not a pure function, and no existing module's dependency
direction can host it without inverting a boundary another ADR already fixed (`:core`
dependency-free; `:crypto`/`:provider` each `:core`-only; `:shared` sample/UI-only).

- Targets mirror `:provider`: `iosArm64`, `iosSimulatorArm64`, `jvm`,
  `androidLibrary { withHostTest }`, `explicitApi()`.
- Android namespace: `org.sarmidev.kardano.wallet`. Package: `org.sarmidev.kardano.wallet`.
- Registered in `settings.gradle.kts` as `:wallet`.

### 2. `:wallet` depends on `:core`, `:crypto`, and `:provider` — never `:provider-blockfrost`

`commonMain` adds `implementation(projects.core)`, `implementation(projects.crypto)`, and
`implementation(projects.provider)`. It does **not** depend on `:provider-blockfrost`:
`:wallet`'s public API takes a `ChainQueryProvider` as a caller-supplied parameter
(dependency inversion), the same pattern `PlaygroundPresenter.presentProviderUtxos` already
uses in `:shared`. The caller (today, `:shared`) decides whether to inject the in-memory mock
or the live Blockfrost provider; `:wallet` stays provider-neutral and does not gain a
transitive HTTP-client dependency. No new external `commonMain` dependency is introduced —
`suspend` needs no coroutines-core dependency in `commonMain`; `commonTest` adds
`kotlinx-coroutines-test`, matching `:provider`'s own test setup.

### 3. Minimal public API: `ReadOnlyWallet`, `WalletBalance`, `WalletError`

Package `org.sarmidev.kardano.wallet`:

- **`ReadOnlyWallet`** — an opaque, private-constructor handle over a restored wallet's public
  metadata only: `network: Network`, `address: Address`, `paymentPath: Cip1852Path`,
  `stakePath: Cip1852Path`.
  - `companion.restore(words: List<String>, network: Network): KardanoResult<ReadOnlyWallet, WalletError>`
    restores the mnemonic, derives the account-0 payment (`m/1852'/1815'/0'/0/0`) and stake
    (`m/1852'/1815'/0'/2/0`) keys, hashes each derived public key to a 28-byte credential, and
    builds a base address for `network`. This is the only entry point that reaches native
    crypto.
  - `suspend fun balance(provider: ChainQueryProvider): KardanoResult<WalletBalance, WalletError>`
    queries `provider.getUtxos(address)` and sums the result. No native crypto; pure
    provider-neutral composition.
  - An `internal` test-only assembly factory (from an already-built `Address` plus paths) lets
    `:wallet`'s own `commonTest` exercise `balance(...)` without restoring a mnemonic, keeping
    that coverage native-crypto-free (see §5).
  - `restore` stays generic over `Network` rather than hardcoded/restricted to testnet,
    mirroring `Address.baseAddress`'s own policy (ADR-0012 §2): it is a pure wallet/address
    construction operation with no mainnet/testnet judgment of its own, which is what lets
    `:wallet`'s own tests restore/assemble against either network value without a special
    case. This is a `:wallet`-level statement only — it does **not** authorize mainnet use
    anywhere in this project's Phase 1 sample/UI surface. Every Phase 1 sample/UI caller (the
    Android Playground checkpoint, Block 1.8b) must pass `Network.TESTNET`; enforcing that
    stays the caller's responsibility, the same boundary already drawn for
    `Address.baseAddress` in 1.7a.
- **`WalletBalance`** — `data class WalletBalance(val coin: Lovelace, val utxoCount: Int)`.
  Provider-neutral and ADA-only, matching `:provider`'s `Value(coin: Lovelace)` model. An empty
  UTxO list is `Ok(WalletBalance(Lovelace.ZERO, 0))`, not an error — mirrors
  `ChainQueryProvider.getUtxos`'s own "empty is not an error" contract.
- **`WalletError`** — a sealed interface wrapping each upstream typed error so callers have one
  failure channel (see §5).

Explicitly rejected additional surface, to keep the module proportional to what this block
needs:

- **No `WalletState` sealed type.** Empty/Loading/Failure/Success are `:shared` presenter
  display concerns, not an SDK-level state machine; the SDK returns one `KardanoResult` per
  call.
- **No `WalletAddress` wrapper.** `Address` already carries network, type, credentials, and
  `toBech32()`; wrapping it again would duplicate that surface for no new invariant.
- **No `TestWallet` type.** The cited test-only mnemonic stays exactly where ADR-0011 §3 put
  it — `:shared`'s `TestWalletFixture` — and `:wallet` takes a generic `words: List<String>`,
  so `:wallet` itself carries no fixture, cited or otherwise.

### 4. Key-material handling: restore, use immediately, clear, retain nothing secret

`restore(...)` reproduces the pattern already proven in
`PlaygroundPresenter.presentTestWalletWithWords` (Block 1.6d/1.7b): parse the mnemonic, derive
the master key, derive both extended private keys, project both extended public keys, hash
each public key, build both credentials, build the address — clearing the mnemonic, the master
key, and all four derived key handles in a `finally` block on every path (success or failure).
The `ReadOnlyWallet` returned on success retains only `network`, the built `Address`, and the
two `Cip1852Path` values — no mnemonic, seed, entropy, root/private key bytes, or raw public
key bytes are stored anywhere in the returned handle, so simply holding a `ReadOnlyWallet` (in
memory, for the lifetime of a Compose screen) exposes nothing secret. This ADR does not
introduce any persistence: nothing is written to disk, `SharedPreferences`, `Keychain`, or any
other durable store; a `ReadOnlyWallet` lives only as long as the caller keeps the in-memory
reference.

### 5. Balance calculation: sum lovelace, reject overflow, never truncate

`balance(provider)` sums `utxo.value.coin.value` (a non-negative `Long` per `Lovelace`'s own
invariant) across the returned UTxO list, checking for `Long` overflow before each addition
rather than after (`acc > Long.MAX_VALUE - next`), then wraps the total in `Lovelace.of(...)`.
An overflow is reported as `WalletError.BalanceOverflow`, never silently truncated or wrapped
— consistent with the project's parser-safety "never truncate silently" rule, applied here to
an accumulation rather than a decode. Native assets are ignored (`Value` is ADA-only for the
first MVP, ADR-0005 §1); no coin selection or advanced balance logic is introduced.

### 6. Error composition: `WalletError` wraps each upstream typed error

```kotlin
public sealed interface WalletError {
    public data class Mnemonic(public val error: MnemonicError) : WalletError
    public data class Derivation(public val error: KeyDerivationError) : WalletError
    public data class Hashing(public val error: CryptoError) : WalletError
    public data class AddressBuild(public val error: AddressError) : WalletError
    public data class Provider(public val error: ProviderError) : WalletError
    public data class BalanceOverflow(public val partialCount: Int) : WalletError
}
```

Every variant except `BalanceOverflow` wraps an already-typed error from the module that
produced it (`:crypto`'s `MnemonicError`/`KeyDerivationError`/`CryptoError`, `:core`'s
`AddressError`, `:provider`'s `ProviderError`) rather than re-deriving a parallel taxonomy.
`BalanceOverflow` is the only wallet-owned variant, naming the one failure mode that originates
in `:wallet`'s own summation logic rather than an upstream call. `:shared` maps `WalletError`
by delegating to the presenter helpers it already has for each wrapped type
(`presentMnemonicError`, `presentKeyDerivationError`, `presentCryptoError`,
`presentAddressError`, `presentProviderError`) rather than duplicating that formatting logic.

### 7. Mock-provider balance is honestly zero unless a test explicitly seeds the wallet address

The default `InMemoryChainQueryProvider` seeds only its two documented addresses
(`SEED_ADDRESS_WITH_UTXOS`, `SEED_ADDRESS_EMPTY`); a wallet address restored from the cited
test mnemonic matches neither, so querying it against the default mock returns an empty list
and therefore a zero balance. This is the correct, honest behavior and is not changed:
`InMemoryChainQueryProvider.defaultSeed()` (or any other default seed) is not modified to make
a restored wallet address appear funded. Any test that wants to exercise the non-empty
`balance(...)` path constructs its own explicitly fake, test-only `InMemoryChainQueryProvider`
instance seeded for that specific address (via the provider's existing public constructor
parameter), confined to test source sets, and never presented as, or mistaken for, real funds.
A live provider (Blockfrost preprod) after real faucet funding is the only path that shows a
genuinely non-zero balance for the restored address.

---

## Rationale

- Creating `:wallet` now, rather than deferring further, matches the exact trigger ADR-0009 §1
  wrote down two blocks in advance and ADR-0011 §2 explicitly pointed to this block; deferring
  again would just relocate the same unavoidable composition into `:shared`, which ADR-0011 §3
  already forbids for SDK logic.
- Depending on `:provider`'s interface rather than `:provider-blockfrost` keeps `:wallet` free
  of any HTTP-client dependency and free to be tested entirely against the in-memory mock;
  the caller's choice of concrete provider is a `:shared`/app concern, not a `:wallet` one.
- Wrapping each upstream error rather than inventing a new parallel taxonomy keeps every
  failure traceable to its origin (a caller can always pattern-match through to the original
  `MnemonicError`/`KeyDerivationError`/`CryptoError`/`AddressError`/`ProviderError`) and lets
  `:shared` reuse its existing per-type formatters instead of writing new ones.
- Rejecting the `WalletState`/`WalletAddress`/`TestWallet` extra types keeps the module
  proportional to what Block 1.8 actually asks for (restore, derive one address, query, sum),
  consistent with ADR-0011 §4's "no Clean Architecture boilerplate unless it removes real
  complexity."
- Recording the honest-zero-balance-under-mock behavior in this ADR (rather than only in a
  code comment) makes the constraint durable across future sessions: nothing about `:wallet`'s
  design, `:provider`'s seed data, or the Android checkpoint may silently make the mock look
  funded to simulate a positive-balance demo.
- Keeping `restore` generic over `Network` (rather than restricted to testnet) matches
  `Address.baseAddress`'s existing policy exactly, avoids introducing a `:wallet`-only
  network-restriction error variant that would have no `:core`-level counterpart, and keeps
  the "no mainnet in Phase 1" boundary where ADR-0005 §7 already put it: on the caller, not on
  a pure construction function.

## Rejected alternatives

- **Keep composing derivation + provider query inside `:shared`.** Rejected: ADR-0011 §3
  already restricts `:shared` to sample/UI/display code with no SDK protocol logic; wallet
  state composed with a provider query is exactly the orchestration that rule excludes.
- **Add a `WalletState` sealed type (`Empty`/`Loading`/`Success`/`Failure`) to `:wallet`.**
  Rejected: this is a UI display concern already served by `KardanoResult` plus the caller's
  own presentation layer; adding it to the SDK would duplicate that layer without adding a new
  invariant.
- **Let `:wallet` depend on `:provider-blockfrost` directly (for a "default" live provider
  convenience constructor).** Rejected: this would give the read-only wallet layer a
  transitive HTTP-client dependency it does not need and would blur the already-settled
  provider-neutral boundary (ADR-0005 §5/ADR-0006).
- **Seed `InMemoryChainQueryProvider`'s default map with the restored wallet's address so the
  Android checkpoint shows a non-zero balance out of the box.** Rejected per this task's
  explicit correction: this would silently misrepresent test/mock data as if the wallet were
  funded. The honest zero-under-mock behavior (§7) is recorded instead, with any non-empty
  balance assertion confined to an explicitly fake, test-only provider instance.
- **Return `Long`/raw lovelace instead of a typed `WalletBalance`.** Rejected: a typed result
  with both `coin: Lovelace` and `utxoCount: Int` matches this SDK's existing typed-model
  convention and gives the caller the UTxO count without a second round trip.
- **Restrict `ReadOnlyWallet.restore` to `Network.TESTNET` only, adding a `WalletError`
  variant for an unsupported wallet network.** Rejected: `Address.baseAddress` (1.7a) is
  already generic over `Network` as a pure construction function, and `:core`'s own tests
  restore/build against both mainnet and testnet vectors; restricting only the `:wallet`-level
  wrapper would create an inconsistent policy between the two layers for no additional safety,
  since the real "no mainnet in Phase 1" boundary is enforced by what the sample/UI caller
  passes, not by what a pure construction function accepts.

## Consequences

- A new Gradle module `:wallet` exists, depending only on `:core`, `:crypto`, and `:provider`;
  no other module's dependency graph changes, and `:core` stays dependency-free.
- `:wallet` exposes exactly three new public types: `ReadOnlyWallet`, `WalletBalance`,
  `WalletError`; `:shared`'s eventual Playground checkpoint (Block 1.8b) calls
  `ReadOnlyWallet.restore(...)` and `wallet.balance(provider)` and formats the result — it
  gains no wallet-orchestration logic of its own.
- The mock-vs-live balance behavior is settled: a restored wallet address reads as zero-balance
  under the default `InMemoryChainQueryProvider` and only shows funds via a live provider
  after real faucet funding, or via an explicitly fake test-only seeded provider confined to
  test source sets.
- No persistence, transaction building, signing, or submission is introduced by this decision;
  those remain scoped to their own future blocks (1.9-1.11).

## Follow-up work

- Block 1.8a implements this ADR: the `:wallet` module, `ReadOnlyWallet`/`WalletBalance`/
  `WalletError`, and their tests (common balance/error/provider-fake coverage plus a JVM-only
  native-crypto restore end-to-end test).
- Block 1.8b wires `:wallet` into the `:shared` Android Playground checkpoint (a
  balance/UTxO-count display, with the honest zero-under-mock behavior documented in the
  checkpoint's own copy) per §7.
- Any future multi-asset (native token) balance support, coin selection, or wallet persistence
  remains out of scope for this ADR and is deferred to whichever later block needs it.
