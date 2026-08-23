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
2. Run the JVM, Android-host, and iOS compile checks documented in `TESTING.md`.
3. Run `git diff --check` and `python3 scripts/check_restricted_claims.py`.
   The script classifies each phrase match on its own and prints
   `path:line:column`. It is not a credential scanner.
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
4. Record the original UTF-8 SHA-256 and extend `scripts/check_handoff_archive.py`
   so the snapshot can be restored and hashed.
5. Run `python3 scripts/check_handoff_archive.py` before declaring the curation
   done.

## CI tool review — Gitleaks

Credential scanning uses the **Gitleaks CLI** (`gitleaks/gitleaks`), not a
third-party GitHub Action wrapper.

| Item | Value |
|---|---|
| Selected release | `v8.30.1` (GitHub `releases/latest` on 2026-08-23; published 2026-03-21T02:17:58Z) |
| Checksums file | `https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_checksums.txt` |
| Checksums file SHA-256 | `061476c21adaf5441516f96f185c1a4706a83cd6329b9b38762271b3d4a52fae` |
| Licence | MIT (upstream `gitleaks/gitleaks`) |
| Installer | `scripts/install_gitleaks.py` — verifies the checksums file, then the selected archive, then extracts. The binary is never committed. |
| Why not an Action wrapper | This repo pins Actions by commit SHA already; a wrapper would add a second, unverified tool chain. Installing the CLI lets CI and a local checkout run the same pinned binary. |
| Scan scope | Full git history (`fetch-depth: 0`, `git fetch --prune --tags origin`, `gitleaks detect --log-opts=--all`). Output is redacted. |
| Allowlist | Match-level only in `.gitleaks.toml`: the cited CIP-19 payment-credential hex **and** the exact test path that `generic-api-key` flags. No directory, rule, or commit exclusions. |

This tool is CI-only. It is not redistributed in an SDK artifact.

## Publishing artifacts later

Maven publication requires a separate decision covering group ownership, coordinates, versioning,
signing, repository selection, native artifact coverage, and support expectations. Do not imply
that artifacts are published until that decision and its verification have landed.
