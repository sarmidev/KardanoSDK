# Security Policy — Kardano SDK

## Current status

> **Kardano SDK is in Phase 0 (pre-alpha).
> It has not been audited.
> Do not use it with mainnet funds or real private keys.**

Phase 0 covers structural encoding and address parsing only. No cryptography, key
handling, or transaction signing is implemented.

## Scope

| Component | Phase 0 status | Notes |
|-----------|---------------|-------|
| Byte primitives / hex | In scope | No crypto |
| Bech32 / Bech32m | In scope | Checksum only (BCH polymod) |
| CBOR subset | In scope | Structural decode/encode |
| CIP-19 address validation | In scope | Structural only |
| Cryptographic primitives | **Not implemented** | Strategy doc only |
| Transaction signing | **Not implemented** | Phase 1+ |
| Key / mnemonic handling | **Not implemented** | Phase 1+ |

## Reporting a vulnerability

If you find a security issue in any released version of this SDK, please report it
privately rather than filing a public issue.

**Contact:** open a GitHub Security Advisory on this repository, or email the maintainer
directly (see `README.md` for contact details).

Please include:
- A description of the issue and affected component.
- Steps to reproduce or a minimal proof-of-concept.
- Your assessment of severity and potential impact.

We aim to acknowledge reports within 72 hours and to coordinate a fix and disclosure
timeline with you.

## What we will not accept as vulnerabilities (Phase 0)

- Issues that require a component that is explicitly out of scope for Phase 0 (e.g.
  transaction signing, key derivation) — these will be tracked as feature requests.
- Issues in the sample apps (`androidApp`, `desktopApp`, `iosApp`) that do not affect the
  SDK core.

## Implementation security principles

These principles govern implementation from Phase 0 onward:

1. **No handwritten cryptography.** Cryptographic primitives are always delegated to
   vetted, peer-reviewed libraries (BouncyCastle on JVM/Android, libsodium on iOS).
2. **Parser safety.** Parsers never allocate from untrusted length fields; all inputs
   are bounded by named constants; malformed input is rejected, not normalized.
3. **No silent failures.** Parsers and validators return typed errors; they do not
   silently succeed on malformed input.
4. **No secrets in the repository.** Real mnemonics, private keys, or addresses holding
   real funds must never appear in code, tests, fixtures, or documentation.
5. **Pinned dependencies.** No dynamic or floating versions.
