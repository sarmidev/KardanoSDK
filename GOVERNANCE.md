# Governance — Kardano SDK

Kardano SDK is maintained by a single person. There is no board, steering
committee, working group, or named reviewer team.

## Maintainer

Javier Sarmiento Mañus (Sarmidev) is the project owner and sole maintainer.
Public identity and responsibilities are listed in [MAINTAINERS.md](MAINTAINERS.md).

## How decisions are made

- Day-to-day implementation follows the documented Phase 1 scope, the
  [AI working agreement](docs/AI_WORKING_AGREEMENT.md), and the Cursor
  repository rules.
- Architecture, scope, and dependency decisions are recorded as Architecture
  Decision Records under [docs/DECISIONS/](docs/DECISIONS/).
- A change that alters a public boundary, a protocol assumption, or a
  dependency direction should add or amend an ADR in the same change.
- The maintainer accepts or rejects pull requests. There is no vote and no
  second required reviewer.

## Contribution and review

Contributions are welcome when they fit the documented scope. The process is
in [CONTRIBUTING.md](CONTRIBUTING.md):

1. Read the project brief, roadmap, and relevant ADRs before starting.
2. Discuss a broad change, new dependency, or public API expansion in an issue
   first.
3. Open a focused pull request with tests and matching documentation.
4. The maintainer reviews against the contribution boundaries and the current
   Phase 1 limits.

By contributing, you agree that the contribution is licensed under the
[Apache License, Version 2.0](LICENSE).

## Conflict handling

- Technical disagreement is discussed on the issue or pull request. The
  maintainer makes the final call and records an ADR when the outcome changes
  a documented decision.
- Conduct concerns follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Vulnerability reports follow [SECURITY.md](SECURITY.md) and stay private
  until a coordinated disclosure is agreed.

## Change of maintainers

Additional maintainers are added only by a recorded update to
[MAINTAINERS.md](MAINTAINERS.md). That update should name the person, their
public contact, their GitHub handle, and the responsibilities they accept.
A governance change that creates shared ownership should also add an ADR.

If the sole maintainer becomes unavailable, there is currently no second
committer with publish rights. See the bus-factor note in
[MAINTAINERS.md](MAINTAINERS.md).

## What this file does not claim

This file does not invent a foundation, a multi-person review board, or an
independent oversight body. Community participation happens through GitHub
Issues, Discussions, and pull requests.
