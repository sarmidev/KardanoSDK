# Archived HANDOFF records

This directory holds historical `docs/HANDOFF.md` content that was moved out of the
living handoff so the current file stays reviewable. **Nothing here is deleted
history.** Older implementation notes and session logs are preserved verbatim.

## Inventory

| File | What it is | Original SHA-256 (raw bytes) |
|---|---|---|
| [2026-08-23-pre-curation.md](2026-08-23-pre-curation.md) | Complete `docs/HANDOFF.md` as of `fix/provider-boundaries-and-timeouts` (`3936047`), immediately before curation | `39998bd77ee96a55c3e2473e4aee73f7a9cc2a65f91136fc340a1af849cf21c4` |

The snapshot is 358,808 bytes / 4,875 lines in its original form. The archived
copy differs only by rewriting the six `](DECISIONS/…)` Markdown links to
`](../../DECISIONS/…)` so they resolve from this directory. Reversing that
rewrite at the byte level restores the original bytes;
`scripts/check_handoff_archive.py` hashes those bytes with no newline
normalization. The snapshot already ended with a trailing blank line;
`.gitattributes` sets `whitespace=-blank-at-eof` on this file only so
`git diff --check` does not treat that preserved ending as a defect.

## Section index (snapshot)

Headings below are in the archived file, in order:

- Purpose
- Current Project Context
- Historical Implementation Detail
- Important Files
- Current Phase (long Phase 0 / Phase 1 implementation log)
- Decisions Already Made
- Open Decisions
- What Not To Do Yet
- Session Update Template and every dated session summary through 2026-08-23
  (provider-boundaries / Playground lifecycle / signing-scope / pre-release
  contracts / earlier Phase 1 and Phase 0 sessions)
- Cursor business, technical-planning, and handoff-update prompts

## Curation policy

See [docs/RELEASING.md](../../RELEASING.md) ("HANDOFF curation"). Do not edit
archived prose to "improve" it. If a later curation adds another snapshot, give
it a dated filename and extend `scripts/check_handoff_archive.py`.
