# Kardano SDK

Kardano SDK is an Apache-2.0 Kotlin Multiplatform SDK for native Cardano mobile apps. It keeps
shared Cardano logic in Kotlin for Android, iOS, and JVM/Desktop while keeping the SDK modules
free of UI dependencies.

## Status

> **Phase 1 MVP is implemented for a test-only, preprod transaction flow.**
> It is experimental, has not received an independent review, and is not for mainnet funds or
> user-supplied private keys.

The implemented Playground flow restores a cited public fixture, queries mock or Blockfrost
preprod UTxOs, builds an ADA-only transaction, signs it locally through the scoped fixture flow,
and can submit to preprod. It is a developer demo, not a general-purpose wallet.

## What works today

- UI-free core primitives, bounded hex/Bech32/CBOR handling, and structural CIP-19 address
  parsing.
- Icarus/CIP-3 test-wallet restoration and CIP-1852 address generation.
- Provider-neutral UTxO, protocol-parameter, and submit boundaries.
- In-memory demo data plus Blockfrost preprod query and submission providers.
- ADA-only transaction draft building, scoped local signing, and preprod submission from the
  test fixture.
- Android-first Playground demo with shared Android/iOS/JVM/Desktop UI code.

## Current limits

- The shipped transaction flow is testnet/preprod-focused, ADA-only, and uses a public
  test-only fixture.
- Mainnet, arbitrary wallet import, general-purpose wallet signing, native-asset transactions,
  scripts, staking, metadata, and hardware-wallet support are not implemented.
- iOS and JVM/Desktop compile as shared targets; Phase 1 runtime validation is Android-primary.
- The signing backend includes macOS JVM artifacts, Android artifacts, and iOS static libraries;
  Linux and Windows JVM signing artifacts are future work.

## Public landing page

A short, dependency-free static landing page lives in [`site/`](site/) and deploys to GitHub
Pages from `main` (see [`site/README.md`](site/README.md) for local preview and the one-time
Pages repository setting). Expected URL once enabled:
[sarmidev.github.io/KardanoSDK](https://sarmidev.github.io/KardanoSDK/). It links back to this
README and the documents below rather than duplicating them.

## Documentation

- [Project brief](docs/PROJECT_BRIEF.md) — product positioning and delivered scope.
- [Quickstart](docs/QUICKSTART.md) — run the Playground in mock mode.
- [Roadmap](docs/ROADMAP.md) — current focus, planned direction, and scope limits.
- [Delivery record](docs/DELIVERY_RECORD.md) — completed Phase 0/1 technical outcomes and
  supporting evidence.
- [Phase 2 plan](docs/PHASE_2_PLAN.md) — native-asset loyalty/ticketing pilot direction.
- [Funding and pilot playbook](docs/FUNDING_AND_PILOT_PLAYBOOK.md) — public evidence,
  outreach, and proposal preparation.
- [Testing guide](docs/TESTING.md) — target matrix, fixtures, and test-vector policy.
- [Release process](docs/RELEASING.md) — public release prerequisites and verification.
- [Third-party notices](docs/THIRD_PARTY_NOTICES.md) — initial dependency notice inventory.
- [Decision records](docs/DECISIONS/) — architecture decisions and scope boundaries.
- [Security reporting](docs/SECURITY.md) — private reporting path and known scope limits.

## Try the Playground

The default mock mode is the quickest way to see the guided flow without a network key:

```bash
./gradlew :desktopApp:run
```

The mock provides deterministic ADA-only sample UTxOs so the demo reaches build and signing. Mock
submission reports that it does not submit to a network. Live Blockfrost mode is preprod only and
requires the operator's own project id. See the [quickstart](docs/QUICKSTART.md) before using live
mode.

## Build and test

```bash
# Portable JVM tests
./gradlew :core:jvmTest :provider:jvmTest :provider-blockfrost:jvmTest :tx:jvmTest

# macOS JVM signing-path tests
./gradlew :crypto:jvmTest :crypto-signing-backend:jvmTest :wallet:jvmTest :shared:jvmTest

# iOS target compilation
./gradlew :shared:compileKotlinIosArm64
```

See [docs/TESTING.md](docs/TESTING.md) for Android-host commands, the complete target matrix, and
environment limits.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change. Changes to transaction,
key-material, provider, or serialization behavior require tests and matching documentation.

## License

Copyright 2026 Javier Sarmiento Mañus (Sarmidev).

Licensed under the [Apache License, Version 2.0](LICENSE).

Project contact: [sarmidev@outlook.es](mailto:sarmidev@outlook.es).

---

Learn more about [Kotlin Multiplatform](https://www.jetbrains.com/help/kotlin-multiplatform-dev/get-started.html).
