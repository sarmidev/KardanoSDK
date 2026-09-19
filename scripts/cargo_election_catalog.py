"""Per-package Cargo license-election catalog for target-linked crates.

Every target-linked crate in `crypto-signing-backend`'s dependency graph
whose Cargo.toml `license` field is not a single unambiguous SPDX license
(contains `OR`, `AND`, `WITH`, or the legacy `/`-separated syntax) MUST have
an explicit row here -- `scripts/generate_legal_evidence.py`'s
`cargo_license_elections()` fails generation for a target-linked package
with no row (see its docstring; this is the exact "no blanket election"
requirement from the 2026-08-24 independent review).

`status` only ever becomes `"ACCEPTED"` by a human editing this file to also
fill in `reviewer` and `review_date` (ISO 8601) -- this script never sets
`status` to `"ACCEPTED"` itself. Owner-recorded `"ACCEPTED"` on a catalog
row is owner acceptance of that row's `proposed_election`; it is not a
counsel determination and does not close `docs/LEGAL_REVIEW.md` counsel,
MPL/Identus/Bouncy, or Identus #226 fields. `scripts/check_release_evidence.py`'s
`release` mode fails while any mandatory row is not `"ACCEPTED"`.

On 2026-09-19 the project owner recorded `"ACCEPTED"` for every applicable
target-linked row in this catalog:

- Apache-2.0 where Apache-2.0 is an explicit OR branch, including the
  plain Apache-2.0 branch for `rustix`/`linux-raw-sys`
  (`Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT`).
- MIT for `memchr` (`Unlicense OR MIT`).

A mandatory AND-required component remains separately required and is
accepted only according to its own `and_component_acceptance` schema.
This catalog does not invent acceptance for non-applicable /
not-target-linked AND-component rows. The only AND-required component in
this crate's graph today (`unicode-ident`'s `Unicode-3.0`) is not
target-linked for any of the 9 committed artifacts, so no AND-component
acceptance is mandatory.

`proposed_election` names the option recorded for the row -- almost always
`Apache-2.0` where available, matching this project's already-adopted
Gradle-side Apache-2.0 option for `net.java.dev.jna:jna`. `memchr` is the
deliberate exception (`MIT`). `LICENSES/Unlicense.txt` remains committed
and referenced in NOTICE as the other OR-branch text; the owner-recorded
catalog option for `memchr` is MIT.

An entry may optionally carry `and_component_acceptance`: a mapping from an
AND-required component's exact name (e.g. `"Unicode-3.0"`) to its own
`{"status", "reviewer", "review_date"}` dict, independent of this row's OR
election above. `scripts/generate_legal_evidence.py`'s
`cargo_license_elections()` defaults any AND-required component missing
from this mapping to `status: "OPEN"` (target-linked) or `"NOT_APPLICABLE"`
(not target-linked) -- accepting the OR election above never implicitly
accepts an AND-required component, and `release` mode requires both to be
independently `"ACCEPTED"`. No entry below currently needs this key.
"""

from __future__ import annotations

from typing import Any

_OWNER_REVIEWER = "Javier Sarmiento Mañus (project owner)"
_OWNER_REVIEW_DATE = "2026-09-19"

# "name@version" -> election entry.
CARGO_ELECTION_CATALOG: dict[str, dict[str, Any]] = {
    "anyhow@1.0.103": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "bitflags@2.13.0": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "camino@1.2.4": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "cargo-platform@0.1.9": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "cfg-if@1.0.4": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "cryptoxide@0.5.3": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": (
            "Uses the legacy pre-SPDX Cargo `license = \"MIT/Apache-2.0\"` "
            "slash syntax, parsed by parse_spdx_expression() as equivalent "
            "to `MIT OR Apache-2.0`."
        ),
    },
    "ed25519-bip32@0.4.2": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": "Direct dependency of crypto-signing-backend.",
    },
    "equivalent@1.0.2": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "errno@0.3.14": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "fastrand@2.4.1": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "getrandom@0.4.3": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "hashbrown@0.17.1": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "heck@0.5.0": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "indexmap@2.14.0": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "itoa@1.0.18": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "libc@0.2.186": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "linux-raw-sys@0.12.1": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": (
            "Three-way expression `Apache-2.0 WITH LLVM-exception OR "
            "Apache-2.0 OR MIT`; the owner-recorded catalog option is the "
            "plain Apache-2.0 branch (neither the LLVM-exception variant "
            "nor MIT). Owner acceptance of this row is not a counsel "
            "determination."
        ),
    },
    "memchr@2.8.3": {
        "proposed_election": "MIT",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": (
            "Unlicense OR MIT. Owner recorded MIT as the catalog option "
            "on 2026-09-19. Owner acceptance of this row is not a counsel "
            "determination. LICENSES/Unlicense.txt remains committed and "
            "cited in NOTICE as the other OR-branch text."
        ),
    },
    "once_cell@1.21.4": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "rustix@1.1.4": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": (
            "Three-way expression `Apache-2.0 WITH LLVM-exception OR "
            "Apache-2.0 OR MIT`; the owner-recorded catalog option is the "
            "plain Apache-2.0 branch (neither the LLVM-exception variant "
            "nor MIT). Owner acceptance of this row is not a counsel "
            "determination."
        ),
    },
    "semver@1.0.28": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "serde@1.0.228": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "serde_core@1.0.228": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "serde_json@1.0.150": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "static_assertions@1.1.0": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "tempfile@3.27.0": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
    "thiserror@2.0.18": {
        "proposed_election": "Apache-2.0",
        "status": "ACCEPTED",
        "reviewer": _OWNER_REVIEWER,
        "review_date": _OWNER_REVIEW_DATE,
        "note": None,
    },
}


def lookup(name: str, version: str) -> dict[str, Any] | None:
    return CARGO_ELECTION_CATALOG.get(f"{name}@{version}")
