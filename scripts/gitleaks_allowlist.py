"""Match-level Gitleaks allowlist used by unit tests.

A finding is allowlisted only when the secret equals the cited CIP-19 hex
taken from .gitleaks.toml AND the path is an exact repo-root match for one
of the allowlisted files. Paths are not rewritten; a prefix, suffix, or
alternate separator does not match.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / ".gitleaks.toml"

_HEX_IN_ANCHORED_REGEX = re.compile(r"\^\s*([0-9a-fA-F]{56})\s*\$")


def load_match_allowlists(config_path: Path = CONFIG_PATH) -> list[dict]:
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    entries: list[dict] = []
    for rule in data.get("rules", []):
        entries.extend(rule.get("allowlists", []))
    entries.extend(data.get("allowlists", []))
    return entries


def cited_vector(config_path: Path = CONFIG_PATH) -> str:
    """Return the cited hex from the config regex; do not store a parallel copy."""
    for entry in load_match_allowlists(config_path):
        for pattern in entry.get("regexes", []):
            matched = _HEX_IN_ANCHORED_REGEX.search(pattern)
            if matched:
                return matched.group(1).lower()
    raise ValueError("no cited CIP-19 hex regex in .gitleaks.toml allowlists")


def is_allowlisted(secret: str, path: str, config_path: Path = CONFIG_PATH) -> bool:
    for entry in load_match_allowlists(config_path):
        if entry.get("condition") != "AND":
            continue
        regexes = [re.compile(pattern) for pattern in entry.get("regexes", [])]
        paths = [re.compile(pattern) for pattern in entry.get("paths", [])]
        secret_ok = any(pattern.search(secret) for pattern in regexes)
        # fullmatch on the path as given — no slash folding, no suffix strip.
        path_ok = any(pattern.fullmatch(path) for pattern in paths)
        if secret_ok and path_ok:
            return True
    return False
