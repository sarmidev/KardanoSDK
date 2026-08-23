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
3. Run `git diff --check` and the project’s restricted-claim scan.
4. Review public API changes and update KDoc/module READMEs.
5. Create an annotated Git tag from the verified commit.
6. Publish release notes containing:
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

## Publishing artifacts later

Maven publication requires a separate decision covering group ownership, coordinates, versioning,
signing, repository selection, native artifact coverage, and support expectations. Do not imply
that artifacts are published until that decision and its verification have landed.
