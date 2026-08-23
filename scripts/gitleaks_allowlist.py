"""Match-level Gitleaks allowlist used by unit tests.

Mirrors .gitleaks.toml: a finding is allowlisted only when the secret
equals the cited CIP-19 hex AND the path is one of the exact test files.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / ".gitleaks.toml"

# Public CIP-19 Blake2b-224 payment credential (IntersectMBO / CIP-19 vector).
CITED_CIP19_PAYMENT_CREDENTIAL = "9493315cd92eb5d8c4304e67b7e16ae36d61d34502694657811a2c8e"


def load_match_allowlists(config_path: Path = CONFIG_PATH) -> list[dict]:
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    entries: list[dict] = []
    for rule in data.get("rules", []):
        entries.extend(rule.get("allowlists", []))
    entries.extend(data.get("allowlists", []))
    return entries


def is_allowlisted(secret: str, path: str, config_path: Path = CONFIG_PATH) -> bool:
    posix_path = path.replace("\\", "/")
    for entry in load_match_allowlists(config_path):
        if entry.get("condition") != "AND":
            continue
        regexes = [re.compile(pattern) for pattern in entry.get("regexes", [])]
        paths = [re.compile(pattern) for pattern in entry.get("paths", [])]
        secret_ok = any(pattern.search(secret) for pattern in regexes)
        path_ok = any(pattern.search(posix_path) for pattern in paths)
        if secret_ok and path_ok:
            return True
    return False
