# Contributing to Kardano SDK

Kardano SDK is an Apache-2.0 Kotlin Multiplatform project for native Cardano mobile integration.
Contributions are welcome when they fit the documented scope and preserve the project’s typed-error,
bounded-parser, and cross-platform design.

## Before opening a change

1. Read the [project brief](docs/PROJECT_BRIEF.md), [roadmap](docs/ROADMAP.md), and relevant
   decision records in [docs/DECISIONS](docs/DECISIONS).
2. Check whether the work belongs to the current Phase 2 plan in
   [docs/PHASE_2_PLAN.md](docs/PHASE_2_PLAN.md).
3. Open or discuss an issue before a broad change, new dependency, public API expansion, or
   protocol-scope decision.
4. Do not include real mnemonics, private keys, API keys, or funds in code, tests, examples, or
   issue text.

## Contribution boundaries

- Keep `:core` UI-free.
- Do not hand-write cryptographic algorithms.
- Keep public failable APIs typed; do not throw across the Swift/ObjC boundary.
- Preserve defensive handling for `ByteArray`.
- Do not relax a parser or validator to make a test pass.
- Copy protocol vectors verbatim from cited specifications or reference implementations.
- Do not add an unpinned dependency.

The detailed engineering rules are in [docs/AI_WORKING_AGREEMENT.md](docs/AI_WORKING_AGREEMENT.md)
and the repository rules under `.cursor/rules/`.

## Tests and documentation

Every behavior change needs valid, invalid, and edge coverage where applicable. Run the narrowest
affected tests, then the relevant target checks described in [docs/TESTING.md](docs/TESTING.md).

Update in the same change:

- KDoc for public APIs;
- module README files affected by the behavior;
- decision records or plans when scope/architecture changes;
- `CHANGELOG.md` under **Unreleased** for user-visible behavior.

## Pull request expectations

Keep a pull request focused and reviewable. Describe:

- the user or integrator problem being solved;
- scope and non-goals;
- verification commands and results;
- documentation and test updates;
- any platform limitations that remain.

By contributing, you agree that your contribution is licensed under the
[Apache License, Version 2.0](LICENSE).
