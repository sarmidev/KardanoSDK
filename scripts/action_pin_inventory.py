"""Recorded GitHub Action pins and composite transitive metadata.

Resolved live from the GitHub Releases and Git refs APIs on 2026-08-23.
Do not copy SHAs from older audit notes. Update this inventory, the
workflows, and docs/DEPENDENCY_REVIEW.md together.
"""

from __future__ import annotations

from dataclasses import dataclass

SHA_LENGTH = 40


@dataclass(frozen=True)
class TransitiveUse:
    """One `uses:` line recorded from a pinned composite action.yml."""

    action: str
    sha: str
    release: str
    source: str


@dataclass(frozen=True)
class ActionPin:
    """One first-party workflow pin plus inspection of that Action's metadata."""

    action: str
    sha: str
    release: str
    resolved_on: str
    source: str
    runtime: str
    kind: str
    note: str
    transitive: tuple[TransitiveUse, ...] = ()


# Peel tag -> commit via GET /repos/{owner}/{repo}/git/refs/tags/{tag}
# (annotated tags followed to the commit object). action.yml fetched from
# raw.githubusercontent.com at the same tag.
ACTION_PINS: tuple[ActionPin, ...] = (
    ActionPin(
        action="actions/checkout",
        sha="3d3c42e5aac5ba805825da76410c181273ba90b1",
        release="v7.0.1",
        resolved_on="2026-08-23",
        source="https://github.com/actions/checkout/releases/tag/v7.0.1",
        runtime="node24",
        kind="javascript",
        note=(
            "Previous pin was checkout v4.3.1 "
            "(34e114876b0b11c390a56381ad16ebd13914f8d5), not the moving v4 "
            "tag. On 2026-08-23 the v4 tag is v4.4.0 (published 2026-07-20). "
            "v5/v6/v7 require runner >= 2.327.1 (GitHub-hosted ubuntu-latest "
            "and macos-latest). This repo does not use pull_request_target."
        ),
    ),
    ActionPin(
        action="actions/setup-java",
        sha="b6effb05e454b25005698d916606bdc6ffcbf961",
        release="v5.7.0",
        resolved_on="2026-08-23",
        source="https://github.com/actions/setup-java/releases/tag/v5.7.0",
        runtime="node24",
        kind="javascript",
        note=(
            "Previous pin was setup-java v4.9.1 "
            "(cf277c60eb25467037889841efdb72551f06f6c3). v5.7.0 is the "
            "latest v5 release (releases/latest). A v4.9.1 backport was "
            "published later (2026-08-04) and is not this pin. Temurin "
            "remains a supported distribution; Adopt values are deprecated "
            "in v5. Node 24, runner >= 2.327.1."
        ),
    ),
    ActionPin(
        action="gradle/actions/setup-gradle",
        sha="0723195856401067f7a2779048b490ace7a47d7c",
        release="v5.0.2",
        resolved_on="2026-08-23",
        source="https://github.com/gradle/actions/releases/tag/v5.0.2",
        runtime="node24",
        kind="javascript",
        note=(
            "Previous pin was setup-gradle v4.4.3 "
            "(ed408507eac070d1f99cc633dbcf757c94c7933a), Node 20. v5.0.2 is "
            "the last v5 release (Node 24). v6.3.0 was the latest tag on "
            "2026-08-23 but is not adopted: v6 extracts caching into the "
            "proprietary gradle-actions-caching component (default "
            "cache-provider=enhanced) and requires accepting a separate "
            "Terms of Use. That is an unproven license/compatibility gate. "
            "v4.4.3 and v5.0.2 cache defaults match: cache-disabled=false, "
            "cache-read-only is true off the default branch, "
            "cache-write-only=false, cache-cleanup=on-success. Workflows "
            "set those inputs explicitly so a later major-version default "
            "change cannot silently alter cache behavior."
        ),
    ),
    ActionPin(
        action="actions/configure-pages",
        sha="45bfe0192ca1faeb007ade9deae92b16b8254a0d",
        release="v6.0.0",
        resolved_on="2026-08-23",
        source="https://github.com/actions/configure-pages/releases/tag/v6.0.0",
        runtime="node24",
        kind="javascript",
        note="Previous pin was v5.0.0. v6.0.0 is Node 24; javascript action.",
    ),
    ActionPin(
        action="actions/upload-pages-artifact",
        sha="fc324d3547104276b827a68afc52ff2a11cc49c9",
        release="v5.0.0",
        resolved_on="2026-08-23",
        source=(
            "https://github.com/actions/upload-pages-artifact/releases/tag/v5.0.0"
        ),
        runtime="composite",
        kind="composite",
        note=(
            "Previous pin was v3.0.1, whose action.yml used the floating "
            "tag actions/upload-artifact@v4 (NF-4). v5.0.0 pins that "
            "transitive use to a 40-character SHA. A later "
            "actions/upload-artifact v7.0.1 exists "
            "(043fb46d1a93c77aae656e7c1c64a875d1fc6a0a) and is recorded "
            "here only as context; this repo keeps the official composite "
            "pin rather than rewriting Pages packaging."
        ),
        transitive=(
            TransitiveUse(
                action="actions/upload-artifact",
                sha="bbbca2ddaa5d8feaa63e36b76fdaad77386f024f",
                release="v7.0.0",
                source=(
                    "https://raw.githubusercontent.com/actions/"
                    "upload-pages-artifact/v5.0.0/action.yml"
                ),
            ),
        ),
    ),
    ActionPin(
        action="actions/deploy-pages",
        sha="cd2ce8fcbc39b97be8ca5fce6e763baed58fa128",
        release="v5.0.0",
        resolved_on="2026-08-23",
        source="https://github.com/actions/deploy-pages/releases/tag/v5.0.0",
        runtime="node24",
        kind="javascript",
        note="Previous pin was v4.0.5. v5.0.0 is Node 24; javascript action.",
    ),
    ActionPin(
        action="actions/upload-artifact",
        sha="043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        release="v7.0.1",
        resolved_on="2026-08-23",
        source="https://github.com/actions/upload-artifact/releases/tag/v7.0.1",
        runtime="node24",
        kind="javascript",
        note=(
            "First-party pin for native-rebuild-evidence.yml report upload. "
            "Resolved live from releases/latest (v7.0.1, published "
            "2026-04-10T17:31:14Z). The tag object is a commit "
            "(043fb46d1a93c77aae656e7c1c64a875d1fc6a0a). action.yml is "
            "javascript (runs.using: node24) with no nested uses:. This is "
            "newer than the Pages composite's transitive v7.0.0 pin "
            "(bbbca2ddaa5d8feaa63e36b76fdaad77386f024f). The workflow "
            "uploads staging reports only; it does not replace committed "
            "natives."
        ),
    ),
    ActionPin(
        action="actions/download-artifact",
        sha="3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        release="v8.0.1",
        resolved_on="2026-08-23",
        source="https://github.com/actions/download-artifact/releases/tag/v8.0.1",
        runtime="node24",
        kind="javascript",
        note=(
            "First-party pin for linux-jvm-rebuild-evidence.yml candidate "
            "compare. Resolved live from releases/latest (v8.0.1, published "
            "2026-03-11T15:44:25Z). The tag object is a commit "
            "(3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c). action.yml is "
            "javascript (runs.using: node24) with no nested uses:. Used "
            "only to download same-run upload-artifact outputs with "
            "contents: read."
        ),
    ),
)

REVIEW_DOC = "docs/DEPENDENCY_REVIEW.md"

PIN_BY_ACTION: dict[str, ActionPin] = {pin.action: pin for pin in ACTION_PINS}


def is_lowercase_sha(value: str) -> bool:
    return len(value) == SHA_LENGTH and all(ch in "0123456789abcdef" for ch in value)


def all_recorded_shas() -> frozenset[str]:
    shas: set[str] = set()
    for pin in ACTION_PINS:
        shas.add(pin.sha)
        for child in pin.transitive:
            shas.add(child.sha)
    return frozenset(shas)
