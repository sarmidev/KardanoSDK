# Support — Kardano SDK

Kardano SDK is an experimental, pre-alpha Kotlin Multiplatform project. The
shipped transaction flow is test-only, ADA-only, and bound to a cited public
preprod fixture. It is not a general-purpose wallet and is not for mainnet
funds or user-supplied keys.

This page describes how to ask for help. It is not a support contract and it
does not promise a response time.

## How-to questions and integration discussion

Use [GitHub Discussions](https://github.com/sarmidev/KardanoSDK/discussions)
for:

- how to run the Playground in mock mode;
- questions about documented scope and limits;
- feedback after trying the quickstart;
- ideas that are not yet a concrete bug report.

Read [README.md](README.md) and [docs/QUICKSTART.md](docs/QUICKSTART.md)
before opening a discussion.

## Bugs and defects

Use [GitHub Issues](https://github.com/sarmidev/KardanoSDK/issues) for a
reproducible defect in implemented behavior. Include:

- the commit or clone revision;
- the command or Playground step that failed;
- expected versus actual result;
- whether mock or live preprod mode was used.

Do not paste Blockfrost project ids, mnemonics, private keys, or any material
that could touch real funds.

## Vulnerabilities

Do not file a public issue for a vulnerability. Follow [SECURITY.md](SECURITY.md).

## What the maintainer can look at

The current implemented surface is listed in the README and
[docs/DELIVERY_RECORD.md](docs/DELIVERY_RECORD.md). Reports that require
mainnet operation, imported wallets, general-purpose signing, native-asset
transactions, scripts, staking, metadata, or hardware wallets are out of
scope unless they show an effect on an implemented path.

## Response expectations

The project has a single maintainer (see [MAINTAINERS.md](MAINTAINERS.md)).
Reports are reviewed as time allows. Vulnerability reports are acknowledged
on the aim stated in `SECURITY.md`. Ordinary issues and discussions have no
promised turnaround and no service-level agreement.

## Related documents

- [GOVERNANCE.md](GOVERNANCE.md) — how decisions are made
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to propose a change
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — expected behaviour
- [docs/TESTING.md](docs/TESTING.md) — how to run the test matrix
