# Funding And Pilot Playbook

This document turns the Phase 2 plan into owner-led work outside the codebase. It is a working
guide, not legal, tax, or investment advice. Dates, application fees, thresholds, and programme
rules change; verify them with the organiser before spending funds or submitting an application.

## Goal

Build enough public evidence and partner interest that a funding request can say:

> Kardano SDK has delivered a documented Phase 1 preprod flow. Phase 2 will add native-asset
> support, a provider selected for a real loyalty/ticketing pilot, and a reproducible Android/iOS
> integration path.

The request should be based on delivered work, named risks, and measurable next milestones rather
than an ambitious feature list.

## Owner checklist

### Week 1: establish the project identity

1. **Confirm the copyright owner.**
   - Decide whether it is you as an individual, a future company, or an assigned entity.
   - Check the copyright notice in `LICENSE` before any public release.
   - Keep records of contributor agreements or contribution provenance if other people contribute.

2. **Create the public project homes.**
   - Make the GitHub repository public when its history and secrets have been checked.
   - Reserve a simple project domain if you want one; do not block progress on a custom website.
   - Create a project email address for partnerships and vulnerability reports.
   - Create a simple public contact path: GitHub Discussions, a Discord channel, or a contact form.

3. **Choose one sentence to repeat everywhere.**
   - Suggested wording: “Open-source Kotlin Multiplatform infrastructure for native Cardano mobile
     apps.”
   - Do not claim mainnet support, general wallet support, native-asset support, or independent
     review before those are delivered.

### Weeks 1–2: prepare public proof

1. **Record a short demo.**
   - Target: 2–3 minutes.
   - Show the overview, mock flow, transaction draft, signing result, and explain that mock submit
     does not send to a network.
   - Separately record the preprod result only if you can show it without exposing a Blockfrost key
     or non-test wallet material.
   - Add captions and publish the video where a grant reviewer can open it without an account.

2. **Prepare a lightweight landing page — delivered.**
   - A dependency-free static page now lives in [`site/`](../site/) and deploys to GitHub Pages
     from `main`; see [`site/README.md`](../site/README.md) for local preview, content-source
     rules, asset provenance, and the one-time repository Pages setting.
   - It includes: problem/positioning, the delivered-evidence strip, current limits, a three-step
     Roadmap section (Phase 1 delivered evidence, a developer/community invitation to run the
     mock Playground and give feedback via GitHub, and the Phase 2 direction explicitly not a
     commitment), the Quickstart/GitHub links, and the pilot-feedback contact path — no backend
     form.
   - It reuses only the project's existing first-party icon mark (website-local derivatives); no
     third-party or generated artwork was added. It could not include a real Playground
     screenshot because the environment that built it had no attached display; `site/README.md`
     documents the manual capture steps for a future update.
   - The Playground remains the actual product demo; the public page stays a short entrance to
     it, not a duplicate of the repository documentation.
   - Remaining owner action: make the repository public (if not already) and set
     **Settings → Pages → Source → GitHub Actions** so the deployed page becomes reachable.

3. **Create a release packet.**
   - Tag the first public milestone after checking the repository history.
   - Publish release notes from `CHANGELOG.md`.
   - Attach or link the demo video, quickstart, test commands, known limits, and the roadmap.
   - Do not publish Maven artifacts until coordinates, versioning, support expectations, and
     distribution obligations have been decided.

### Weeks 2–4: find a pilot

Create a spreadsheet or private tracker with 15–25 candidates in four groups:

- loyalty and membership products;
- ticketing or event platforms;
- games or collectible apps;
- Cardano wallets and dApp teams with a native mobile need.

For each candidate, record only business contact details they have made public or have given you
permission to retain. Track:

- their product and current mobile stack;
- why native assets might matter to them;
- whether they use Android, iOS, Kotlin, Swift, React Native, Flutter, or web wrappers;
- the exact integration problem they would pay attention to;
- next action and date.

#### First outreach message

Use a short, specific message:

> I am building Kardano SDK, an open-source Kotlin Multiplatform layer for native Cardano mobile
> apps. The current demo runs an ADA-only preprod transaction flow. I am planning Phase 2 around
> loyalty/ticketing native assets and would value 20 minutes to understand whether shared
> Android/iOS Cardano logic would solve a problem for your team. I am asking for product feedback,
> not a commitment.

Do not begin by asking for a grant endorsement. First learn whether the proposed pilot problem is
real.

#### Discovery call questions

1. Which mobile platforms and languages do you maintain?
2. Where does Cardano logic live today?
3. What makes native assets difficult in your product flow?
4. Would a Kotlin shared layer change implementation time or maintenance?
5. What is the smallest loyalty/ticketing flow worth demonstrating?
6. Which provider or infrastructure constraints matter to you?
7. What would make an experimental integration worth trying?
8. Would the team provide written feedback or a non-binding letter of interest if the scope fits?

After each call, write a one-page summary: problem, evidence, requested capability, rejected
assumptions, and next step. Do not publish a company name or quote without permission.

### Monthly: build DRep and ecosystem context

1. Identify 10–15 DReps or ecosystem contributors who discuss developer tooling, mobile apps,
   open source, or adoption.
2. Share a concise update with working links: release, demo, quickstart, roadmap, and the current
   Phase 2 question.
3. Ask for criticism of the milestone plan and budget logic. Do not ask for a vote before a
   proposal is complete.
4. Publish a monthly update with:
   - one delivered item;
   - one measured signal, such as pilot conversations or demo runs;
   - one open decision;
   - the next milestone.

Prioritise GitHub, technical forums, Cardano developer communities, and direct pilot conversations.
Use social networks to point to evidence, not as a substitute for it.

## Funding preparation

### Intersect budget process

The 2026 submission window is closed. Intersect is preparing the 2027 budget process, but has not
published a new submission calendar. Prepare the proposal now and verify current rules when a
window opens.

Useful official references:

- [Cardano funding channels](https://developers.cardano.org/docs/community/funding/)
- [Intersect budget process documentation](https://committees.docs.intersectmbo.org/intersect-budget-committee/cardano-budget-process)
- [Budget proposal template](https://committees.docs.intersectmbo.org/intersect-budget-committee/cardano-budget-process/budget-proposal-submission-template-download)
- [Hydra Voting platform](https://hydra-voting.intersectmbo.org/)
- [GovTool](https://gov.tools/)

Prepare these sections in the Intersect template:

1. Problem and target users.
2. Evidence from Phase 1 and pilot discovery.
3. Phase 2 milestones from `PHASE_2_PLAN.md`.
4. Budget by work package, role, and milestone.
5. Measurable acceptance criteria and public artifacts.
6. Risks, dependencies, and what happens if a pilot partner changes direction.
7. Team capacity, legal recipient, contract and payment readiness.

The Intersect route is preferable to a direct treasury action for a first request because it includes
review and feedback stages. A direct Treasury Withdrawal Governance Action requires its own current
deposit, technical submission work, and DRep/Constitutional Committee support; verify current
protocol parameters and process rules before considering it.

### Catalyst and other channels

- Watch Project Catalyst while its stewardship transition continues; do not build a schedule around
  an unannounced round.
- Check current Intersect grant and contract opportunities for scoped tooling work.
- Consider the Maintainer Retainer programme after external projects rely on the repository.
- Consider an accelerator only if you form a company, have a commercial pilot, and want investment
  alongside open-source work.

## Proposal budget discipline

Do not choose a headline amount first. Estimate:

- people and time per work package;
- partner/pilot support;
- documentation, demo, and release work;
- provider infrastructure or test costs;
- administration fees required by the chosen programme;
- contingency for explicitly named technical risks.

Then split the request into independently reviewable milestones. A funding request should permit a
reviewer to stop after any completed milestone and still see a useful public outcome.

## Readiness gate before submitting

Do not submit a major funding request until all are true:

- Phase 1 closure is recorded and the public docs match delivered scope.
- Apache-2.0 ownership and third-party notice obligations have been reviewed.
- CI runs the declared JVM, Android-host, and iOS compile checks.
- A tagged release, changelog, quickstart, and demo video exist.
- The Phase 2 roadmap is consistent across GitHub docs and the Playground.
- At least one pilot candidate has validated the problem, ideally in writing.
- The proposal has milestones, budget, metrics, risks, and a named payment recipient.
