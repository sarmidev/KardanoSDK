"""Per-package Cargo license-election catalog for target-linked crates.

Every target-linked crate in `crypto-signing-backend`'s dependency graph
whose Cargo.toml `license` field is not a single unambiguous SPDX license
(contains `OR`, `AND`, `WITH`, or the legacy `/`-separated syntax) MUST have
an explicit row here -- `scripts/generate_legal_evidence.py`'s
`cargo_license_elections()` fails generation for a target-linked package
with no row (see its docstring; this is the exact "no blanket election"
requirement from the 2026-08-24 independent review).

Every entry's `status` is `"OPEN"` as of 2026-08-24: NONE of these elections
have actually been accepted by an owner/counsel reviewer yet. `status` only
ever becomes `"ACCEPTED"` by a human editing this file to also fill in
`reviewer` and `review_date` (ISO 8601) -- this script never sets `status`
to `"ACCEPTED"` itself, and `scripts/check_release_evidence.py`'s `release`
mode fails while any mandatory row is not `"ACCEPTED"`.

`proposed_election` names the option this repository would elect if/when a
reviewer accepts it -- almost always `Apache-2.0` where available, matching
this project's already-adopted election for `net.java.dev.jna:jna` and
`org.hyperledger.identus:bip32-ed25519` (Gradle side) and `ed25519-bip32`/
`cryptoxide` (Cargo side, all `MIT OR Apache-2.0`/`MIT/Apache-2.0`). This is
a *proposal* for review, not a legal election made by this repository.

`memchr` (`Unlicense OR MIT`) is a deliberate exception: per explicit
instruction, `proposed_election` stays `None` (no election proposed) and
`LICENSES/Unlicense.txt` is committed and referenced in NOTICE alongside
`LICENSES/MIT.txt` so that whichever branch ultimately applies, its text is
already present -- this repository does not pre-elect away from Unlicense
before a reviewer has actually accepted an MIT election for this package.

An entry may optionally carry `and_component_acceptance`: a mapping from an
AND-required component's exact name (e.g. `"Unicode-3.0"`) to its own
`{"status", "reviewer", "review_date"}` dict, independent of this row's OR
election above. `scripts/generate_legal_evidence.py`'s
`cargo_license_elections()` defaults any AND-required component missing
from this mapping to `status: "OPEN"` (target-linked) or `"NOT_APPLICABLE"`
(not target-linked) -- accepting the OR election above never implicitly
accepts an AND-required component, and `release` mode requires both to be
independently `"ACCEPTED"`. No entry below currently needs this key: the
only AND-required component in this crate's graph today
(`unicode-ident`'s `Unicode-3.0`) is on a package that is not target-linked
for any of the 9 committed artifacts, so no AND-component acceptance is
mandatory yet -- this docstring exists so the schema is documented before
it is ever needed, not narrated only after the fact.
"""

from __future__ import annotations

from typing import Any

# "name@version" -> election entry.
CARGO_ELECTION_CATALOG: dict[str, dict[str, Any]] = {
    "anyhow@1.0.103": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "bitflags@2.13.0": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "camino@1.2.4": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "cargo-platform@0.1.9": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "cfg-if@1.0.4": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "cryptoxide@0.5.3": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": (
            "Uses the legacy pre-SPDX Cargo `license = \"MIT/Apache-2.0\"` "
            "slash syntax, parsed by parse_spdx_expression() as equivalent "
            "to `MIT OR Apache-2.0`."
        ),
    },
    "ed25519-bip32@0.4.2": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": "Direct dependency of crypto-signing-backend.",
    },
    "equivalent@1.0.2": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "errno@0.3.14": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "fastrand@2.4.1": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "getrandom@0.4.3": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "hashbrown@0.17.1": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "heck@0.5.0": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "indexmap@2.14.0": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "itoa@1.0.18": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "libc@0.2.186": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "linux-raw-sys@0.12.1": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": (
            "Three-way expression `Apache-2.0 WITH LLVM-exception OR "
            "Apache-2.0 OR MIT`; the proposed election is the plain "
            "Apache-2.0 branch (neither the LLVM-exception variant nor MIT)."
        ),
    },
    "memchr@2.8.3": {
        "proposed_election": None,
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": (
            "Unlicense OR MIT. No election is proposed here; "
            "LICENSES/Unlicense.txt is committed and referenced in NOTICE "
            "alongside LICENSES/MIT.txt so the Unlicense text is present "
            "unless/until a reviewer explicitly accepts an MIT election for "
            "this specific package."
        ),
    },
    "once_cell@1.21.4": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "rustix@1.1.4": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": (
            "Three-way expression `Apache-2.0 WITH LLVM-exception OR "
            "Apache-2.0 OR MIT`; the proposed election is the plain "
            "Apache-2.0 branch (neither the LLVM-exception variant nor MIT)."
        ),
    },
    "semver@1.0.28": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "serde@1.0.228": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "serde_core@1.0.228": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "serde_json@1.0.150": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "static_assertions@1.1.0": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "tempfile@3.27.0": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
    "thiserror@2.0.18": {
        "proposed_election": "Apache-2.0",
        "status": "OPEN",
        "reviewer": None,
        "review_date": None,
        "note": None,
    },
}


def lookup(name: str, version: str) -> dict[str, Any] | None:
    return CARGO_ELECTION_CATALOG.get(f"{name}@{version}")
