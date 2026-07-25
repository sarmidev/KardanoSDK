# Security Policy — Kardano SDK

## Current status

> **Kardano SDK has an experimental Phase 1 test-only, preprod transaction flow.**
> It has not received an independent review. Do not use it with mainnet funds, user-supplied
> private keys, or user-supplied mnemonics.

The current demo restores a cited public fixture, builds ADA-only drafts, signs through the
fixture-scoped flow, and can submit to Blockfrost preprod. These capabilities do not make the
project a general-purpose wallet or a mainnet SDK.

## Scope

| Component | Current status | Notes |
|-----------|----------------|-------|
| Byte primitives / hex | Implemented | Typed errors and defensive byte handling |
| Bech32 / Bech32m | Implemented | Bounded checksum and payload handling |
| CBOR subset | Implemented | Documented definite-length subset |
| CIP-19 addresses | Implemented | Structural parsing and generation support |
| Key restoration / derivation | Implemented for the test flow | Public fixture only in the Playground |
| Transaction signing | Implemented for the test flow | Testnet/preprod fixture scope only |
| Transaction submission | Implemented for Blockfrost preprod | Test funds only |
| Native-asset transactions | Not implemented | Phase 1 rejects or filters unsupported inputs |
| Mainnet / imported wallets | Not implemented | Explicitly out of scope |

## Reporting a vulnerability

If you find a security issue in any released version of this SDK, please report it
privately rather than filing a public issue.

**Contact:** open a GitHub Security Advisory on the hosting repository. If that path is not
available, email [sarmidev@outlook.es](mailto:sarmidev@outlook.es).

Please include:
- A description of the issue and affected component.
- Steps to reproduce or a minimal proof-of-concept.
- Your assessment of severity and potential impact.

We aim to acknowledge reports within 72 hours and to coordinate a fix and disclosure
timeline with you.

## Out-of-scope reports

- Reports that require an explicitly unsupported capability — for example mainnet operation,
  imported wallets, general-purpose signing, native-asset transactions, scripts, or staking —
  will be tracked as feature requests unless they demonstrate an effect on an implemented path.
- Issues in the sample apps (`androidApp`, `desktopApp`, `iosApp`) that do not affect the
  SDK core.

## Implementation principles

These principles govern implementation:

1. **No handwritten cryptography.** Cryptographic primitives are always delegated to
   externally maintained libraries or platform bindings. Concrete libraries and bindings
   are selected per implementation block through documented evaluation. See
   `docs/DECISIONS/0004-crypto-strategy.md`.
2. **Parser safety.** Parsers never allocate from untrusted length fields; all inputs
   are bounded by named constants; malformed input is rejected, not normalized.
3. **No silent failures.** Parsers and validators return typed errors; they do not
   silently succeed on malformed input.
4. **No secrets in the repository.** Real mnemonics, private keys, or addresses holding
   real funds must never appear in code, tests, fixtures, or documentation.
5. **Pinned dependencies.** No dynamic or floating versions.
