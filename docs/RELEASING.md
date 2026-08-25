# Release Process

Kardano SDK does not publish Maven artifacts yet. Until publication, a release is a reviewed Git
tag plus release notes that identify the source revision, verified targets, and known limits.

## Before the first public release

1. Confirm the copyright owner named in `LICENSE`.
2. Complete the third-party notice review in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
3. Verify repository history contains no API keys, real mnemonics, private keys, or live-fund
   addresses. Run `python3 scripts/check_gitleaks.py` after
   `python3 scripts/install_gitleaks.py`. This does not replace an owner-authenticated
   GitHub secret-scanning pass.
4. Confirm the public README, quickstart, roadmap, and security-reporting path match delivered
   behavior.
5. Run the CI-equivalent test matrix and record platform limitations.
6. Add the release entry to `CHANGELOG.md`.
7. When `CHANGELOG.md` records a **Breaking (pre-alpha)** public type change, copy the
   upgrade note into the release notes. Do not claim binary compatibility or exhaustive
   `when` compatibility for those changes even if a default argument keeps some source
   call sites compiling.

## Pre-alpha upgrade notes (Unreleased)

These are source-level breaks in an unpublished API. They are not a binary-compatibility
promise and they do not keep exhaustive `when` expressions compiling without edits.

- `ProviderError.RemoteStatus` is now `RemoteStatus(code, detail: String? = null)`.
  Call sites that pass only `code` still compile. Generated data-class members include
  `detail`.
- `ProviderError` gained `ResultTruncated(fetchedCount, cap)`. Every exhaustive `when`
  over `ProviderError` needs a new branch.

## Release checklist

1. Choose a semantic version and create a release branch if the change needs stabilisation.
2. Run the JVM, Android-host, iOS compile, and Android lint Debug/Release
   checks documented in `TESTING.md`. Lint warnings fail the build.
   Confirm the wrapper SHA-256 still matches
   `https://services.gradle.org/distributions/gradle-9.5.0-bin.zip.sha256`
   when that is the pinned wrapper.
3. Run `git diff --check`, `python3 scripts/check_restricted_claims.py`,
   and `python3 scripts/check_action_pins.py`.
   The claim script classifies each phrase match on its own and prints
   `path:line:column`. It is not a credential scanner. The pin script
   requires every external workflow `uses:` to be a 40-character lowercase
   SHA recorded in `scripts/action_pin_inventory.py` and
   `docs/DEPENDENCY_REVIEW.md`.
4. Run the full-history credential scan: `python3 scripts/install_gitleaks.py`
   then `python3 scripts/check_gitleaks.py`. Confirm zero non-allowlisted
   findings. Output is redacted; do not paste raw matches into notes.
5. Review public API changes and update KDoc/module READMEs.
6. Create an annotated Git tag from the verified commit.
7. Publish release notes containing:
   - scope and non-goals;
   - verification commands and environment;
   - known target limitations;
   - upgrade notes;
   - linked demo/quickstart material.

## HANDOFF curation

`docs/HANDOFF.md` is the living resume document. It should hold current project
context, recent sessions, active risks and gates, branch-stack status, and the next
task.

Older implementation notes and session logs are **not deleted**. They live under
[archive/handoff/](archive/handoff/README.md):

- [archive/handoff/2026-08-23-pre-curation.md](archive/handoff/2026-08-23-pre-curation.md)
  is a verbatim snapshot of `docs/HANDOFF.md` immediately before the 2026-08-23
  curation (from `3936047`), with only the six `DECISIONS/` Markdown links rewritten
  so they resolve from the archive directory.

Policy:

1. Append a short session summary to the living handoff at the end of each session.
2. When the living file is no longer reviewable, move older sections into a new
   dated file under `docs/archive/handoff/` without editing the prose.
3. After a move, adjust only repo-relative Markdown links that would otherwise
   break. Do not rewrite historical meaning.
4. Record the original SHA-256 of the raw file bytes and extend
   `scripts/check_handoff_archive.py` so the snapshot can be restored and
   hashed at the byte level (no newline normalization).
5. Run `python3 scripts/check_handoff_archive.py` before declaring the curation
   done. If the snapshot already ends with a trailing blank line, add a
   path-scoped `.gitattributes` `whitespace=-blank-at-eof` for that file only
   so `git diff --check` stays clean.

## CI tool review — Gitleaks

Credential scanning uses the **Gitleaks CLI** (`gitleaks/gitleaks`), not a
third-party GitHub Action wrapper.

| Item | Value |
|---|---|
| Selected release | `v8.30.1` (GitHub `releases/latest` on 2026-08-23; published 2026-03-21T02:17:58Z) |
| Checksums file | `https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_checksums.txt` |
| Checksums file SHA-256 | `061476c21adaf5441516f96f185c1a4706a83cd6329b9b38762271b3d4a52fae` |
| Licence | MIT (upstream `gitleaks/gitleaks`) |
| Installer | `scripts/install_gitleaks.py` — verifies the checksums file, then the selected archive, reads the member into memory, writes every byte to an exclusive temp sibling, `fchmod`s `0755` on that descriptor, and atomically replaces a non-symlink destination. The binary is never committed. |
| Why not an Action wrapper | This repo pins Actions by commit SHA already; a wrapper would add a second, unverified tool chain. Installing the CLI lets CI and a local checkout run the same pinned binary. |
| Scan scope | After `fetch-depth: 0` and `git fetch --prune --tags origin`, reachable commits are `git rev-list --all`. Gitleaks (v8.30.1 `--log-opts` string) scans `git log --full-history --all -m`: every ref, no history simplification, one diff per merge parent. A credential introduced only in a merge resolution is therefore visible. Output is redacted (`--redact`). |
| Allowlist | Match-level only in `.gitleaks.toml`: the cited CIP-19 payment-credential hex **and** an exact repo-root path (`^…$`). Paths are the cited test files plus `scripts/gitleaks_allowlist.py` (the helper historically embedded the same vector). No directory, rule, or commit exclusions. |

This tool is CI-only. It is not redistributed in an SDK artifact.

## CI tool review — GitHub Action pins

Third-party Actions are pinned by commit SHA, not by a moving major tag.
`docs/DEPENDENCY_REVIEW.md` records the live 2026-08-23 resolution,
including the v4 versus `v4.3.1` correction (the previous pins were exact
patch releases, not `@v4`) and the Pages upload composite's transitive
`actions/upload-artifact` SHA.

| Item | Value |
|---|---|
| Checker | `scripts/check_action_pins.py` |
| Inventory | `scripts/action_pin_inventory.py` |
| Human review | `docs/DEPENDENCY_REVIEW.md` |
| Checkout | `v7.0.1` `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| setup-java | `v5.7.0` `b6effb05e454b25005698d916606bdc6ffcbf961` |
| setup-gradle | `v5.0.2` `0723195856401067f7a2779048b490ace7a47d7c` (v6 not adopted) |
| configure-pages | `v6.0.0` `45bfe0192ca1faeb007ade9deae92b16b8254a0d` |
| upload-pages-artifact | `v5.0.0` `fc324d3547104276b827a68afc52ff2a11cc49c9` |
| deploy-pages | `v5.0.0` `cd2ce8fcbc39b97be8ca5fce6e763baed58fa128` |
| Transitive Pages upload | `actions/upload-artifact` `v7.0.0` `bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` |

`gradle/actions` v6.3.0 remains unused because its default cache provider
is a separate commercial component with a Terms of Use gate.

## Dependency locking and verification

Library coordinates are locked per project in `*/gradle.lockfile` with
`LockMode.STRICT` on compile/runtime classpaths. Artifact bytes are
checked against SHA-256 rows in `gradle/verification-metadata.xml`.
The Rust wrapper uses `rust-toolchain.toml` channel `1.97.0` and
`cargo --locked`. Regeneration commands and the tamper-check record
are in `docs/DEPENDENCY_REVIEW.md` and `docs/TESTING.md`.

Before a release that changes a catalog version, regenerate lock
state and verification metadata, review the generated diff, and keep
`Cargo.lock` matched to the exact `Cargo.toml` pins. Do not rewrite
generated checksums by hand.

## Publishing artifacts later

Maven publication requires a separate decision covering group ownership, coordinates, versioning,
signing, repository selection, native artifact coverage, and support expectations. Do not imply
that artifacts are published until that decision and its verification have landed.
