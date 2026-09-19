# Intersect Tooling Sustainability — Phase 1 Application Draft

This is an internal draft for the Intersect Open Source Committee Tooling
Sustainability Program Phase 1 intake. It is **not** a submitted application,
**not** a Phase 2 demo script, and **not** a funding award claim.

Official program:
https://committees.docs.intersectmbo.org/intersect-open-source-committee/about/paid-open-source-model-posm/tooling-sustainability

Official attestation scripts:
https://github.com/IntersectMBO/Project-Compliance-Attestation

Intake form (open manually; do not submit from this draft):
https://tinyurl.com/OSC-Tooling

## Official phase distinction

| Phase | What it is | What Kardano SDK is doing now |
|---|---|---|
| **Phase 1 — Interest and eligibility** | ClickUp intake form plus the official self-attestation PDF and evidence links | This document prepares answers and repository evidence. The form is not submitted in this change. |
| **Phase 2 — Evaluation and demo** | About 5–10 minutes of demo, repository artifact review against the attestation, and Q&A | Out of scope here. No pitch deck is added in this change. |
| **Phase 3 — Selection and funding terms** | Milestones, acceptance criteria, reporting cadence, disbursement, optional non-funding support | Funding amount and band are aligned here, after evaluation and demand evidence. |

Do **not** fix an ask or payment band in Phase 1. Program bands are guidance
only; final amounts are OSC discretion. Internal planning may consider work
that the program currently groups with Band 2 (SDKs and language tools,
USD 5,000–15,000), but that is not an application claim and is not written
into the intake answers below.

## Current facts that the form must not overstate

- No Git tag or public release exists yet.
- No external adoption or production integrator is claimed.
- No formal CycloneDX/SPDX SBOM is published. Locked Gradle and Cargo
  inventories plus the native-carrier inventory are evidence lists, not a
  standard SBOM. See [DEPENDENCY_REVIEW.md](DEPENDENCY_REVIEW.md).
- LinkedIn is owner-supplied later. It is not invented in the repository.
- Counsel review and several named legal-evidence gates remain open
  (`docs/LEGAL_REVIEW.md`).
- The official attestation script queries the **default branch**. A PDF
  generated before this change merges to `main` is diagnostic only. The
  workflow is `workflow_dispatch` only; do not add a recurring
  pull-request trigger.

## Draft form answers

Use these answers as a starting point. Copy only what still matches `main`
on the day of submission.

### Project summary

Kardano SDK is an Apache-2.0 Kotlin Multiplatform library for native Cardano
Android, iOS, and JVM apps. Shared Cardano logic stays in UI-free Kotlin
modules. Phase 1 delivers a documented, test-only, ADA-only preprod
transaction flow that restores a cited public fixture, builds a draft, signs
through a scoped backend, and can submit to Blockfrost preprod.

### Problem

Native Cardano mobile apps currently split Android and iOS work or wrap a
web stack. There is no published, UI-free Kotlin Multiplatform SDK that
keeps address, provider, wallet, and transaction logic in one tested shared
layer with explicit Phase 1 limits.

### Target users

Mobile and JVM developers who want shared Kotlin Cardano logic for native
apps, and later loyalty/ticketing teams if Phase 2 is validated. The
current audience is developers who can run the Playground and read the
repository docs. There is no claimed external user base yet.

### Ecosystem value

A documented KMP Cardano path reduces duplicated mobile integration work
and keeps parser, address, and transaction boundaries explicit. Value today
is the public source, tests, and demo — not measured adoption.

### Current delivered status

Phase 0 core primitives and Phase 1 fixture-scoped preprod flow are
implemented and recorded in [DELIVERY_RECORD.md](DELIVERY_RECORD.md) and
[ROADMAP.md](ROADMAP.md). Limits: testnet/preprod, ADA-only, public
fixture only, Android-primary runtime validation, no mainnet, no imported
wallets, no native-asset transactions, no scripts, no tagged release.

### Adoption

**No external adoption is claimed.** There are no published integrator case
studies, download counts used as proof, or production deployments. Demand
evidence is a Phase 2/3 topic.

### Governance

Sole-maintainer governance. Javier Sarmiento Mañus (Sarmidev) is the only
maintainer. Decisions are recorded as ADRs. See [GOVERNANCE.md](../GOVERNANCE.md)
and [MAINTAINERS.md](../MAINTAINERS.md). There is no board or invented team.
Bus factor is 1.

### Roadmap

Current focus is Phase 1 closure, public evidence, and honest funding
readiness. Planned direction is a gated loyalty/ticketing native-asset
pilot ([PHASE_2_PLAN.md](PHASE_2_PLAN.md)). That direction is not a
delivery schedule.

### Sustainability

The project is currently unpaid sole-maintainer work. Tooling
Sustainability support, if awarded later, would fund continued maintenance,
documentation, and scoped delivery — not a change of license and not a
claim that other funding already exists.

### Support requested in Phase 1

Phase 1 asks only to be considered eligible. Concrete funding amount, band,
milestones, and disbursement belong in Phase 3 after evaluation. Optional
non-funding help (review, documentation, community testing) can be
discussed later; it is not requested as a substitute for honest scope.

### Other funding and conflicts

No other grant, retainer, or OSC budget award is currently funding this
repository. The maintainer is not claiming a conflict-of-interest role on
the Tooling Working Group or OSC. If a later form field requires a formal
COI statement, the owner completes it at submission time.

### Funding amount / band (do not fill as a Phase 1 ask)

Leave amount and band unset, or write:

> Funding amount and band to be aligned in Phase 3 based on evaluation and
> demand evidence. This Phase 1 intake does not request a specific payout
> or band.

Internal planning may look at the current Band 2 guidance range. That is
not written as the application request.

## Evidence links

Use repository-root and documentation URLs on `main` after merge:

| Evidence | Path |
|---|---|
| README | https://github.com/sarmidev/KardanoSDK/blob/main/README.md |
| License | https://github.com/sarmidev/KardanoSDK/blob/main/LICENSE |
| Contributing | https://github.com/sarmidev/KardanoSDK/blob/main/CONTRIBUTING.md |
| Code of Conduct | https://github.com/sarmidev/KardanoSDK/blob/main/CODE_OF_CONDUCT.md |
| Security policy | https://github.com/sarmidev/KardanoSDK/blob/main/SECURITY.md |
| Governance | https://github.com/sarmidev/KardanoSDK/blob/main/GOVERNANCE.md |
| Support | https://github.com/sarmidev/KardanoSDK/blob/main/SUPPORT.md |
| Maintainers | https://github.com/sarmidev/KardanoSDK/blob/main/MAINTAINERS.md |
| Changelog | https://github.com/sarmidev/KardanoSDK/blob/main/CHANGELOG.md |
| Roadmap | https://github.com/sarmidev/KardanoSDK/blob/main/docs/ROADMAP.md |
| Delivery record | https://github.com/sarmidev/KardanoSDK/blob/main/docs/DELIVERY_RECORD.md |
| Verify workflow | https://github.com/sarmidev/KardanoSDK/blob/main/.github/workflows/verify.yml |
| CodeQL workflow | https://github.com/sarmidev/KardanoSDK/blob/main/.github/workflows/codeql.yml |
| Dependabot | https://github.com/sarmidev/KardanoSDK/blob/main/.github/dependabot.yml |
| Dependency review | https://github.com/sarmidev/KardanoSDK/blob/main/docs/DEPENDENCY_REVIEW.md |
| Landing page | https://sarmidev.github.io/KardanoSDK/ |
| Attestation workflow | https://github.com/sarmidev/KardanoSDK/blob/main/.github/workflows/intersect-attestation.yml |

Attach the attestation PDF generated **after** merge by a manual
dispatch on `main`:

```text
gh workflow run intersect-attestation.yml --ref main
```

Treat the HTML/PDF/Markdown artifacts as script output, not as
certification. A one-time pre-merge diagnostic
(https://github.com/sarmidev/KardanoSDK/actions/runs/35451128768 and
https://github.com/sarmidev/KardanoSDK/actions/runs/35451205414)
already proved HTML/PDF/Markdown generation under `xvfb-run -a`. Do not
attach that diagnostic PDF as the Phase 1 submission evidence.

## Owner placeholders

Fill these only when the owner supplies the real value. Do not invent them
in the repository.

| Field | Placeholder |
|---|---|
| LinkedIn profile | `[OWNER TO ADD]` |
| Form-specific fields not visible without opening ClickUp | `[OWNER TO ADD]` after inspecting the live form |
| ADA payment identity / recipient details (Phase 3 if requested) | `[OWNER TO ADD]` |
| Any identity document or invoice field the form later requires | `[OWNER TO ADD]` |

LinkedIn is intentionally absent from `MAINTAINERS.md`.

## Attestation checklist — expected results

Official script pin: `IntersectMBO/Project-Compliance-Attestation`
commit `e8dc883517a116f745dda0d9b23204e76326445b` (2025-09-24). The script
checks top-level files on the **default branch** and a few GitHub API
signals.

### Before this change is on `main`

| Check | Expected |
|---|---|
| Root `SECURITY.md` | RED (missing at top level; policy lived under `docs/`) |
| Root `GOVERNANCE.md` / `SUPPORT.md` | AMBER (missing) |
| `MAINTAINERS.md` / CODEOWNERS / OWNERS | AMBER (absent) |
| Code scanning alerts API | AMBER (not enabled) |
| CI workflows | GREEN if `.github/workflows` is present on `main` |
| Tagged releases | AMBER (none) |
| Overall | RED because missing root `SECURITY.md` is a hard fail in the script |

### After this change merges to `main`

| Check | Expected |
|---|---|
| LICENSE, README, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, GOVERNANCE, SUPPORT, CHANGELOG | GREEN (present at top level) |
| Maintainers file | GREEN |
| Workflows | GREEN |
| Code scanning | AMBER until a default-branch CodeQL analysis is the
  recorded `main` analysis. A pull-request CodeQL job, or an alerts API
  that became reachable from a PR run, is not enough to claim GREEN |
| Releases | AMBER (still no tag) |
| Contributors (180d unique emails) | **RED** while there is one unique
  committer (`traffic_light_count` thresholds are GREEN ≥ 5, AMBER ≥ 2,
  otherwise RED). This row does not drive overall |
| Overall | **AMBER**. Do not claim GREEN. Expect AMBER until a
  default-branch CodeQL run exists and the remaining release/contributor
  warnings are understood. Overall becomes RED only if a must-have file
  is missing, code scanning is RED, or 90-day activity is RED; contributor
  RED and release AMBER are warnings, not that overall driver |

The attestation workflow has no automatic pull-request or push trigger.
The diagnostic runs above are historical evidence that the xvfb/PDF path
works. After merge, dispatch on `main` for the submission PDF. Do not
attach a pre-merge artifact.

## ClickUp intake checklist (manual)

Open https://tinyurl.com/OSC-Tooling while logged into the account that
will submit. For each field:

1. Copy the matching draft answer above if the label is clear.
2. If the label is not in this document, mark `[OWNER TO ADD]` and paste
   the exact field label here before submitting.
3. Attach the post-merge attestation PDF.
4. Add the evidence links.
5. Confirm the form does not require a funding band or payout figure. If
   it does, write the Phase 3 alignment sentence; do not invent a number.
6. Confirm the form does not require a CycloneDX/SPDX upload. If it does,
   generate a formal SBOM first (recommended follow-up in
   [DEPENDENCY_REVIEW.md](DEPENDENCY_REVIEW.md)); do not upload the lock
   inventories as if they were a standard SBOM.
7. Do not submit until `main` contains this change, the attestation PDF
   matches that `main`, and the owner has filled every `[OWNER TO ADD]`
   field.

Unknown fields seen at submission time (leave blank until inspected):

- `[OWNER TO ADD]` — paste ClickUp labels that have no draft answer

## What this change does not do

- It does not submit the intake form.
- It does not create a tag or GitHub Release.
- It does not add a Phase 2 pitch deck.
- It does not claim Band 2, adoption, or counsel clearance.
