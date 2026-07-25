# Release Process

Kardano SDK does not publish Maven artifacts yet. Until publication, a release is a reviewed Git
tag plus release notes that identify the source revision, verified targets, and known limits.

## Before the first public release

1. Confirm the copyright owner named in `LICENSE`.
2. Complete the third-party notice review in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
3. Verify repository history contains no API keys, real mnemonics, private keys, or live-fund
   addresses.
4. Confirm the public README, quickstart, roadmap, and security-reporting path match delivered
   behavior.
5. Run the CI-equivalent test matrix and record platform limitations.
6. Add the release entry to `CHANGELOG.md`.

## Release checklist

1. Choose a semantic version and create a release branch if the change needs stabilisation.
2. Run the JVM, Android-host, and iOS compile checks documented in `TESTING.md`.
3. Run `git diff --check` and the project’s restricted-claim scan.
4. Review public API changes and update KDoc/module READMEs.
5. Create an annotated Git tag from the verified commit.
6. Publish release notes containing:
   - scope and non-goals;
   - verification commands and environment;
   - known target limitations;
   - upgrade notes;
   - linked demo/quickstart material.

## Publishing artifacts later

Maven publication requires a separate decision covering group ownership, coordinates, versioning,
signing, repository selection, native artifact coverage, and support expectations. Do not imply
that artifacts are published until that decision and its verification have landed.
