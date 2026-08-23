# Dependency Review — CI Actions And Build Pins

Dated inventory of first-party GitHub Action pins and the composite
Action metadata those pins pull in. Resolved live on **2026-08-23** from
the GitHub Releases API and peeled Git tag objects. Do not reuse SHAs
from older audit notes.

This page is the human-readable twin of `scripts/action_pin_inventory.py`.
`scripts/check_action_pins.py` requires every external workflow `uses:`
to match a recorded 40-character lowercase SHA, and requires every SHA
below to remain in this file.

Gradle library versions, lockfiles, and native-backend acceptance are
reviewed in later commits on this branch and appended here.

## How pins were resolved

For each Action:

1. `GET https://api.github.com/repos/{owner}/{repo}/releases?per_page=8`
   and `.../releases/latest` (User-Agent `kardano-pin-resolver`, 2026-08-23).
2. Peel `GET .../git/refs/tags/{tag}` to the commit object (annotated tags
   followed to the commit SHA).
3. Fetch `action.yml` (or `setup-gradle/action.yml`) from
   `raw.githubusercontent.com` at that tag and inspect `runs.using` plus
   every nested `uses:`.

No Action SHA in this table was copied from `docs/AUDIT/` or from the
previous `v4.3.1` / `v4.9.1` / `v4.4.3` comments.

## v4 versus v4.3.1

The 2026-08-22 audit (W9-2) listed floating major-version tags:
`actions/checkout@v4`, `actions/setup-java@v4`,
`gradle/actions/setup-gradle@v4`. The later SHA-pin commit did **not**
pin those moving `v4` tags. It pinned exact patch releases:

| Action | Comment people may have read as "v4" | Actual previous pin |
|---|---|---|
| `actions/checkout` | `@v4` (moving major tag) | `v4.3.1` `34e114876b0b11c390a56381ad16ebd13914f8d5` |
| `actions/setup-java` | `@v4` | `v4.9.1` `cf277c60eb25467037889841efdb72551f06f6c3` |
| `gradle/actions/setup-gradle` | `@v4` | `v4.4.3` `ed408507eac070d1f99cc633dbcf757c94c7933a` |

On 2026-08-23, `actions/checkout`'s `v4` tag is **v4.4.0** (published
2026-07-20), which is not `34e114876b0b11c390a56381ad16ebd13914f8d5`.
This batch upgrades from the exact patch pins above, not from a moving
`v4` tag.

## First-party workflow pins

| Workflow `uses:` | Release | Commit SHA | Runtime | Kind |
|---|---|---|---|---|
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` | node24 | javascript |
| `actions/setup-java` | v5.7.0 | `b6effb05e454b25005698d916606bdc6ffcbf961` | node24 | javascript |
| `gradle/actions/setup-gradle` | v5.0.2 | `0723195856401067f7a2779048b490ace7a47d7c` | node24 | javascript |
| `actions/configure-pages` | v6.0.0 | `45bfe0192ca1faeb007ade9deae92b16b8254a0d` | node24 | javascript |
| `actions/upload-pages-artifact` | v5.0.0 | `fc324d3547104276b827a68afc52ff2a11cc49c9` | composite | composite |
| `actions/deploy-pages` | v5.0.0 | `cd2ce8fcbc39b97be8ca5fce6e763baed58fa128` | node24 | javascript |

Release pages:

- https://github.com/actions/checkout/releases/tag/v7.0.1
- https://github.com/actions/setup-java/releases/tag/v5.7.0
- https://github.com/gradle/actions/releases/tag/v5.0.2
- https://github.com/actions/configure-pages/releases/tag/v6.0.0
- https://github.com/actions/upload-pages-artifact/releases/tag/v5.0.0
- https://github.com/actions/deploy-pages/releases/tag/v5.0.0

`checkout` v7.0.1, `setup-java` v5.7.0, `configure-pages` v6.0.0, and
`deploy-pages` v5.0.0 are javascript Actions (`runs.using: node24`).
Their `action.yml` files contain no nested `uses:`.

`checkout` v7 blocks fork checkouts on `pull_request_target` /
`workflow_run` unless `allow-unsafe-pr-checkout` is set. This repository
does not use those events. Runner requirement for the Node 24 Actions is
`>= 2.327.1`; GitHub-hosted `ubuntu-latest` and `macos-latest` meet that.

`setup-java` v5.7.0 was `releases/latest` on 2026-08-23. A `v4.9.1`
backport was published on 2026-08-04 and is not this pin. The workflows
keep `distribution: temurin` and `java-version: "17"`. Adopt aliases are
deprecated in v5; this repo does not use them.

## setup-gradle: v5 adopted, v6 not adopted

`gradle/actions` `releases/latest` on 2026-08-23 is **v6.3.0**. That
major version is **not** used here.

v6 extracts caching into `gradle-actions-caching`, a separate commercial
component. The v6 `setup-gradle/action.yml` default is
`cache-provider: enhanced`. Using that default accepts a separate Terms
of Use. That is an unproven license/compatibility gate, so this commit
stops at **v5.0.2** (last v5, Node 24, published 2026-02-23).

v4.4.3 and v5.0.2 share these cache defaults:

- `cache-disabled`: `false`
- `cache-read-only`: true when the ref is not the repository default branch
- `cache-write-only`: `false`
- `cache-cleanup`: `on-success`

`verify.yml` sets those four inputs explicitly so a later major-version
default change cannot silently change cache behavior.

## Composite inspection — Pages upload

`actions/upload-pages-artifact@v3.0.1` (the previous pin) is a composite
Action whose `action.yml` contained:

```text
uses: actions/upload-artifact@v4
```

That is a floating major tag (NF-4). v5.0.0 replaces it with:

```text
uses: actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f # v7.0.0
```

Source:
https://raw.githubusercontent.com/actions/upload-pages-artifact/v5.0.0/action.yml

The other composite steps are inline `run:` archive commands (no further
`uses:`). `actions/upload-artifact` v7.0.1
(`043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`, published 2026-04-10) exists
and is newer than the composite's v7.0.0 pin. This repo does not rewrite
the official Pages packaging steps; it records that transitive SHA and
requires it to stay pinned.

`configure-pages` and `deploy-pages` are javascript Actions and have no
nested `uses:`.

## Checker

```bash
python3 -m unittest scripts.tests.test_check_action_pins
python3 scripts/check_action_pins.py
```

The checker walks `.github/workflows/*.{yml,yaml}` and
`.github/actions/**/action.yml`. Local `./` composites are allowed; their
own external `uses:` still need a recorded SHA. A recorded composite
with a non-SHA transitive entry is a finding.
