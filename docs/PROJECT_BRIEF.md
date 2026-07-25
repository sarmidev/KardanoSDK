# Kardano SDK - Project Brief

## 1. Project Summary

Kardano SDK is an Apache-2.0 Kotlin Multiplatform SDK for native Cardano mobile applications.

The goal is to provide a mobile-first Cardano infrastructure layer that lets Android and iOS apps share core Cardano logic without relying on WebViews, JavaScript runtimes, duplicated platform logic, or ad-hoc platform wrappers.

The current product thesis is intentionally narrow:

> A native Android/iOS app should be able to demonstrate a bounded, test-only Cardano wallet and
> transaction flow through shared Kotlin Multiplatform logic.

Phase 0 established the foundation. Phase 1 delivered an Android-primary, ADA-only preprod
demonstration: a cited fixture wallet, provider query, transaction building, scoped local signing,
and Blockfrost submission. The full delivery record is in `docs/ROADMAP.md`.

## 2. Why This Exists

Cardano has strong infrastructure in several areas:

- TypeScript/web tooling, such as Mesh and related dApp libraries.
- Rust low-level libraries and serialization layers.
- Some Java/JVM and Swift-specific libraries.
- Wallet connectors and web-first dApp flows.

However, there is no clearly dominant mobile-first, Kotlin Multiplatform-first SDK for teams that want to build native Android and iOS apps sharing the same Cardano business logic.

Kardano SDK exists to fill that gap.

## 3. Target Users

Primary users:

- Android developers building Cardano mobile apps.
- iOS teams that want shared Cardano logic through KMP.
- Wallet teams exploring native mobile architecture.
- dApp teams that want mobile apps without depending on web wrappers.
- Startups building loyalty, ticketing, identity, gaming, NFT or payment apps on Cardano.

Secondary users:

- Open-source Cardano contributors.
- Grant reviewers in Project Catalyst or Intersect.
- Technical partners evaluating Cardano mobile infrastructure.

## 4. Initial Use Case

The first practical use case is:

> Embedded Cardano wallet and transaction layer for native mobile apps.

Examples:

- Loyalty app using native assets.
- Ticketing or NFT claim app.
- Identity or credential app.
- Gaming app with Cardano assets.
- Enterprise app that needs mobile transaction signing.
- Simple wallet demo for preprod/testnet.

## 5. Delivered MVP Scope

The delivered Phase 1 demonstration lets a developer:

1. Create a test wallet backed by a cited public fixture.
2. Generate and display its testnet address.
3. Query mock UTxOs or Blockfrost preprod UTxOs.
4. Build an ADA-only transaction draft with fees and change.
5. Sign the fixture transaction locally.
6. Submit the signed transaction to Blockfrost preprod.
7. Reuse the Playground and SDK logic from Android, iOS, and JVM/Desktop targets.

The current limits are deliberate:

- The transaction flow is ADA-only.
- The signed flow is testnet/preprod and fixture-scoped.
- Mainnet, imported wallets, user-supplied mnemonics, general-purpose signing, and native-asset
  transaction construction are not implemented.
- Android is the Phase 1 runtime validation target; iOS and JVM/Desktop have shared sample hosts
  and documented compile/link limits.

Phase 2 plans native-asset support for a loyalty/ticketing pilot. See
`docs/PHASE_2_PLAN.md`.

## 6. Phase 0 Definition

Phase 0 is not the MVP.

Phase 0 is the documented foundation for the SDK.

Phase 0 scope:

- Project structure and module boundaries.
- Testing infrastructure.
- Documentation and AI working rules.
- Core primitives.
- Hex/base encoding utilities.
- Bech32 investigation and implementation decision.
- Minimal CBOR policy and implementation decision.
- Address parsing and structural validation.
- Crypto strategy documentation.
- Compatibility fixture strategy.

Phase 0 must not include:

- Transaction signing.
- Custom cryptography.
- Real mnemonic/private key examples.
- Real funds.
- Readiness claims beyond the evidence.
- Plutus V3 support.
- Staking/delegation.
- WalletConnect.
- Full CIP-30/CIP-95 support.
- Hydra, Mithril, governance or full node behavior.

## 7. Positioning

Kardano SDK should not be positioned as:

- A replacement for Mesh in advanced web dApp development.
- A full Cardano node.
- A full wallet application.
- A full Plutus framework.
- A general-purpose wallet product in early versions.

It should be positioned as:

- A native mobile Cardano SDK.
- A Kotlin Multiplatform shared core for Android and iOS.
- A developer-friendly infrastructure layer.
- A documented starting point for Cardano mobile integrations.

Suggested claim:

> Open-source Kotlin Multiplatform SDK for native Cardano mobile apps.

Suggested subclaim:

> Shared Android/iOS Cardano transaction and provider integration without JavaScript runtimes or
> WebView bridges.

## 8. Differentiation

Kardano SDK should differentiate through:

- KMP-first architecture.
- Mobile-first ergonomics.
- Android and iOS shared logic.
- Cited test vectors and cross-target checks.
- Public developer documentation.
- Explicit scope boundaries.
- Provider abstraction.
- Clear scope boundaries.
- Real sample apps.

The goal is not to support every Cardano feature first.

The goal is to make the first mobile-native integration path understandable and maintainable.

## 9. Monetization And Funding

Kardano SDK should remain open source at the core.

Potential funding paths:

- Project Catalyst grants.
- Intersect grants.
- Ecosystem infrastructure funding.
- Paid integration work.
- Enterprise support.
- Architecture reviews.
- Key-material and transaction-architecture consulting.
- Long-term maintenance contracts.
- Potential institutional partnership if the SDK becomes widely adopted.

Initial grant positioning should focus on:

> Native Cardano Mobile Infrastructure: shared Kotlin Multiplatform provider, wallet, and
> transaction capabilities for Android and iOS teams.

Funding requests must be based on delivered milestones, pilot evidence, and reviewable work
packages. The current process is documented in `docs/FUNDING_AND_PILOT_PLAYBOOK.md`.

## 10. Success Criteria

Phase 1 is complete when:

- A developer can follow the quickstart and run the mock demonstration.
- The Android Playground can build, sign, and submit the scoped test flow to preprod.
- Tests cover meaningful valid, invalid, and edge behavior.
- Documented target limitations are visible to an integrator.

Phase 2 is successful when:

- Android and iOS demonstrate the documented integration path.
- Native assets can be represented and transferred without losing selected input value.
- A provider capability decision is documented.
- An external loyalty/ticketing team has attempted the integration or given a written indication
  that it will do so.
- The project can submit a milestone-based ecosystem funding request.

## 11. Communication Style

Public communication should be:

- Serious.
- Honest.
- Technical.
- Clear about key-material and transaction scope.
- Clear about experimental status.

Avoid unsupported words such as:

- readiness claims that exceed the evidence

Prefer:

- experimental
- not independently reviewed
- validates structurally
- rejects malformed input
- pre-MVP
- not for real funds

