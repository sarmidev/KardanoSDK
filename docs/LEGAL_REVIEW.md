# Legal Review — Distribution Evidence Checklist

**This is an evidence checklist and template for owner/counsel review. It is
not legal advice, not a legal opinion, and not counsel approval. Nothing in
this file, `NOTICE`, `LICENSES/`, `docs/THIRD_PARTY_NOTICES.md`, or
`docs/evidence/` states that Kardano SDK is cleared to release, and nothing
in it should be read that way.**

Every factual field below is machine-checked by
`scripts/check_release_evidence.py` (run in CI by `verify.yml`,
job `legal-evidence-scan`) and is regenerated deterministically by
`scripts/generate_legal_evidence.py`. Open review fields use one of the
literal markers in that script's `ALLOWED_OPEN_GATE_MARKERS`; any other
generic filler text (see the forbidden-token list in that script) fails the
checker.

## 1. Candidate commit / tag scope

| Field | Value |
|---|---|
| Candidate commit | `c65a20acf485bf842b90655fcc6967ade4474671` |
| Candidate tag | None. No tag exists yet; this packet is prepared for a future tagged review, not for the commit above alone. |
| Branch | `fix/native-build-and-platform-evidence` (stacked; Prompt 7) |
| Scope statement | ADA-only, testnet/preprod, Phase 1 fixture-scoped signing (ADR-0015/ADR-0019). No mainnet. Windows x86-64 JVM signing backend is candidate-only and excluded from this scope (see §6). |

## 2. Reviewer / counsel / date

| Field | Value |
|---|---|
| Preparer | Automated evidence-generation session (this repository's AI working agreement, `docs/AI_WORKING_AGREEMENT.md`) |
| Preparation date | 2026-08-24 |
| Counsel reviewer | OPEN — pending owner/counsel review |
| Counsel review date | OPEN — pending owner/counsel review |
| Counsel determination | OPEN — pending owner/counsel review |

## 3. Digests (from `docs/evidence/LEGAL_EVIDENCE_DIGEST.txt`)

Regenerate with `python3 scripts/generate_legal_evidence.py`; the digests
below must match that file exactly (checked by
`scripts/check_release_evidence.py`).

| Field | SHA-256 |
|---|---|
| Gradle lock digest (all 10 `*/gradle.lockfile`, concatenated in fixed module order) | `4339a9ed4fb19ba4aae22eb4dae1abc8334d557ba4a2f3c2278acc6b92ad007e` |
| Cargo.lock digest (`crypto-signing-backend/Cargo.lock`) | `855373baa265413f3929a85bb90aa83f137674fe58c6324b5d4de3cce2f93d8e` |
| Native CHECKSUMS digest (`crypto-signing-backend/CHECKSUMS.sha256`) | `55c3b131434372528c1f824fee35ab2df2092e6261f8e496e2b0b128110393d9` |
| NOTICE digest | `a5a2270ce355ae1f980bbe0829b80f28e1086745a9053d09e0d40dd9712a881a` |
| LICENSES digest (all `LICENSES/*.txt`, concatenated in sorted filename order) | `c1875545b1924183bc3eef22d55d73692b1bec1c02f643d04887e62afdf40aa8` |

## 4. NOTICE / LICENSES inventory

| Field | Value |
|---|---|
| Root NOTICE | `NOTICE` (repo root) |
| License texts committed | `LICENSES/Apache-2.0.txt`, `LICENSES/MPL-2.0.txt`, `LICENSES/ISC-libsodium.txt`, `LICENSES/BouncyCastle.txt` (see `LICENSES/README.md` for source URL and fetch-date SHA-256 of each) |
| Licenses evaluated but not separately included | MIT (evaluated; every MIT-eligible redistributed/compiled-in component either elects Apache-2.0 under a dual license or is not distributed — see `LICENSES/README.md` "About MIT") |
| Cross-check | `scripts/check_release_evidence.py` fails if NOTICE cites a `LICENSES/*.txt` file that does not exist, or if a committed `LICENSES/*.txt` file is never cited by NOTICE |

## 5. JNA license election

`net.java.dev.jna:jna` `5.19.1` is dual-licensed `Apache-2.0 OR LGPL-2.1`.
Kardano SDK elects **Apache-2.0** for this distribution (see `NOTICE`). This
is a factual election record, not a statement that LGPL-2.1 compliance would
otherwise be unavailable.

| Field | Value |
|---|---|
| Coordinate | `net.java.dev.jna:jna:5.19.1` |
| Available licenses | Apache-2.0 OR LGPL-2.1 |
| Elected license | Apache-2.0 |
| Election recorded in | `NOTICE`, `LICENSES/README.md` |

## 6. MPL-2.0 file-level obligations

MPL-2.0 is file-level, not whole-program, copyleft (MPL-2.0 §3.1–§3.2).
Kardano SDK does not modify the Source Code Form of either MPL-2.0 component
below, so the obligation is satisfied by directing recipients to the
upstream repository; it does not require Kardano SDK's own source to be
released under MPL-2.0.

| Component | Distributed as | Obligation | Satisfied by |
|---|---|---|---|
| `com.goterl:lazysodium-android` 5.2.0 | Android `.aar`, unmodified | Recipients must be able to obtain the Source Code Form | `github.com/terl/lazysodium-android` (cited in `NOTICE` and `docs/THIRD_PARTY_NOTICES.md`) |
| `uniffi` Rust crate `=0.29.5` | Compiled/linked into all 9 committed native artifacts (see §8) | Recipients must be able to obtain the Source Code Form | `github.com/mozilla/uniffi-rs` at the pinned tag (cited in `NOTICE`, `docs/evidence/uniffi_bindings_inventory.json`) |

## 7. libsodium carriers

`libsodium` (ISC license) is never a direct Gradle dependency. It is bundled
as a compiled native binary inside two separate upstream artifacts, which are
themselves already reviewed in §6/§8 and `docs/THIRD_PARTY_NOTICES.md`:

| Carrier | Platforms bundled | Distinct from |
|---|---|---|
| `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings` 0.9.5 (JVM jar) | macOS, Linux (arm64/x86-64), Windows (MSVC x86-64) | Kardano's own `crypto-signing-backend` native artifacts (§8); this libsodium carrier ships a Windows `.dll` today, which is unrelated to the still-unpromoted Kardano Windows signing candidate |
| `com.goterl:lazysodium-android` 5.2.0 (Android `.aar`) | Android, per ABI | Same as above |

Full detail: `docs/evidence/maven_native_carriers_inventory.json`.

## 8. Committed native provenance (9 artifacts)

Exact mapping of all 9 rows in `crypto-signing-backend/CHECKSUMS.sha256` to
platform/arch/source owner/hash/provenance/rebuild workflow is generated at
`docs/evidence/native_artifacts_inventory.json` and cross-checked against the
CHECKSUMS file by `scripts/check_release_evidence.py` (exact-match, no extra
or missing row). See that JSON file for the current 9-row table; do not
hand-copy it here, since a copy would drift from the generated evidence.

| Field | Value |
|---|---|
| Row count | 9 (checked: exactly 9, not "at least 9") |
| 10th candidate row | Windows x86-64 JVM (`win32-x86-64/kardano_ed25519_bip32_signing.dll`) — technical GO on PE-structure evidence, explicitly **not** added to CHECKSUMS.sha256 or the generated catalog. See §11. |

## 9. Not distributed (explicit statement)

| Item | Status |
|---|---|
| Windows x86-64 JVM signing-backend candidate DLL | **Not distributed.** Technical GO on native-artifact PE evidence; withheld pending independent PE re-review and upstream issue #226 (see §11). |
| Identus `apollo` Android derivation-backend native library, Windows build | **Not distributed by Kardano SDK.** Upstream (`hyperledger-identus/apollo`) has not published a `win32-x86-64` build; Kardano SDK cannot distribute what upstream has not built. Tracked as upstream issue #226. |

## 10. Unresolved / decision fields

| Field | Value |
|---|---|
| Counsel review | OPEN — pending owner/counsel review |
| Upstream Identus win32-x86-64 build | OPEN — pending upstream hyperledger-identus/apollo issue #226 |
| Windows signing-backend PE re-review | OPEN — pending independent PE re-review |
| Release / tag decision | Not made in this packet. This packet prepares evidence only; it does not recommend, approve, or schedule a release. |

## 11. Gate cross-references

- Independent PE re-review gate: see `docs/HANDOFF.md` Branch-Stack Status
  (Prompt 7) and `crypto-signing-backend/README.md` "Windows x86-64 —
  candidate-only".
- Upstream Identus issue #226: see `docs/HANDOFF.md` "Next Recommended Task"
  and `docs/DEPENDENCY_PROVENANCE.md`.
- This packet does not change either gate's status. Both remain open after
  this change.

## Regeneration and verification

```bash
python3 scripts/generate_legal_evidence.py   # writes docs/evidence/*
python3 scripts/generate_legal_evidence.py   # run a second time
git diff --quiet docs/evidence                # expect no diff
python3 scripts/check_release_evidence.py     # fails closed on any drift
python3 -m unittest discover -s scripts/tests -p "test_*.py"
```

Do not treat a passing `check_release_evidence.py` run as legal clearance.
It only confirms that the evidence packet is internally consistent,
deterministic, and free of unresolved generic placeholders — not that
counsel has reviewed it or that a release decision has been made.
