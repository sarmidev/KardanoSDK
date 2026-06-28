# Kardano SDK - Project Brief

## 1. Project Summary

Kardano SDK is an open-source Kotlin Multiplatform SDK for native Cardano mobile applications.

The goal is to provide a mobile-first Cardano infrastructure layer that lets Android and iOS apps share core Cardano logic without relying on WebViews, JavaScript runtimes, duplicated platform logic, or unsafe ad-hoc wrappers.

The first product thesis is intentionally narrow:

> A native Android/iOS app should be able to create or restore a Cardano wallet, validate addresses, query UTxOs, build a basic transaction, sign locally, and submit it through a provider using shared Kotlin Multiplatform logic.

Phase 0 does not implement the full MVP. Phase 0 exists to build a safe, tested, documented foundation.

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

## 5. MVP Definition

The MVP should allow a developer to:

1. Create or restore a wallet.
2. Generate a Cardano address.
3. Query UTxOs through a provider.
4. Build a transaction sending ADA.
5. Build a transaction sending native assets.
6. Calculate fee and change.
7. Sign locally.
8. Submit the transaction to preprod/mainnet through a provider.
9. Reuse the same core logic from Android and iOS.

The MVP must include:

- Android sample app.
- iOS sample app.
- JVM/Desktop sample or CLI for fast testing.
- Public documentation.
- Unit tests and compatibility fixtures.

## 6. Phase 0 Definition

Phase 0 is not the MVP.

Phase 0 is the safe foundation for the SDK.

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
- Production-ready claims.
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
- A production-audited security product in early versions.

It should be positioned as:

- A native mobile Cardano SDK.
- A Kotlin Multiplatform shared core for Android and iOS.
- A developer-friendly infrastructure layer.
- A clean, tested, documented starting point for Cardano mobile apps.

Suggested claim:

> Open-source Kotlin Multiplatform SDK for native Cardano mobile apps.

Suggested subclaim:

> Shared Android/iOS wallet, transaction building, signing and provider integration without JavaScript runtimes or WebView bridges.

## 8. Differentiation

Kardano SDK should differentiate through:

- KMP-first architecture.
- Mobile-first ergonomics.
- Android and iOS shared logic.
- Strong unit tests from the beginning.
- Public developer documentation.
- Conservative security posture.
- Provider abstraction.
- Clear scope boundaries.
- Real sample apps.

The goal is not to support every Cardano feature first.

The goal is to make the first mobile-native integration path feel obvious, safe and maintainable.

## 9. Monetization And Funding

Kardano SDK should remain open source at the core.

Potential funding paths:

- Project Catalyst grants.
- Intersect grants.
- Ecosystem infrastructure funding.
- Paid integration work.
- Enterprise support.
- Architecture reviews.
- Security hardening consulting.
- Long-term maintenance contracts.
- Potential institutional partnership if the SDK becomes widely adopted.

Initial grant positioning should focus on:

> Cardano Mobile Core KMP: shared Android/iOS wallet, transaction signing and provider SDK.

Grant proposals should be based on working milestones, not promises.

## 10. Success Criteria

Phase 0 is successful when:

- The repo structure supports SDK development.
- Documentation is clear enough for outside contributors.
- AI coding rules prevent unsafe generation.
- Core primitives and parsers have unit tests.
- CBOR and parser policy is documented.
- No unsafe cryptography or signing code exists.
- Android, iOS and JVM/Desktop targets remain healthy.

The MVP is successful when:

- A developer can follow a quickstart and run the demo.
- Android and iOS share the same Cardano core logic.
- A preprod transaction can be built, signed and submitted.
- Native assets are supported.
- Tests cover important valid, invalid and edge cases.
- The project can credibly apply for ecosystem funding.

## 11. Communication Style

Public communication should be:

- Serious.
- Honest.
- Technical.
- Conservative about security.
- Clear about experimental status.

Avoid unsupported words such as:

- secure
- audited
- hardened
- guaranteed
- battle-tested
- production-ready

Prefer:

- experimental
- not audited
- validates structurally
- rejects malformed input
- pre-MVP
- not for real funds

