# US-0004: Document cal deny for operators and agents

> Spec: SPEC-0005 (sdlc/specs/SPEC-0005-calendar-deny/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0003
> min_tier: 2
> Files touched: 4
> Closes spec: yes

## Objective

The embedded manual (`outlook-tool skill`) is how AI agents discover commands. This story makes
`cal deny` discoverable there and in the README and AGENTS.md, and closes SPEC-0005.

## Requirements covered

> Discoverability of the command introduced by US-0003.

- SPEC-0005/FR-NEW-001: WHEN the operator denies a meeting invitation, whether already accepted or not yet answered, THE calendar SHALL record it as declined and SHALL NOT send a response email to the organizer. (documentation part)

## Independent Test

`outlook-tool skill` (via `CliRunner`) prints text containing `cal deny`; `rg -n "cal deny" README.md AGENTS.md src/skill.md` returns a hit in each file.

## Design excerpt
### Decisions
- DEC-002/DEC-003 (SPEC-0005): the command sends no response email; document it that way.
### Paths
| Path | Action |
|---|---|
| `src/skill.md` | modify: tree line after `accept <id>` (line 62) `└── deny <id>   # Refuser une invitation de réunion (sans envoyer de réponse)` (fix the tree glyphs: `accept` becomes `├──`); add one sentence near the workflow note (line 213) that `cal deny <id>` refuses an invitation whether accepted or not, with the same event id. |
| `README.md` | modify: add `cal deny` where `cal accept` or the cal commands are listed (if `cal accept` is absent, add both `cal accept` and `cal deny`). |
| `AGENTS.md` | modify: the `cal add\|list\|update\|delete` line becomes `cal add\|list\|get\|update\|delete\|accept\|deny`. |
| `tests/test_cli.py` | modify: add one test running `skill` and asserting `cal deny` in stdout. |
### Existing patterns
Existing skill tests in `tests/test_cli.py` (search `skill`).

## Acceptance tests
### Skill mentions deny (extra to the spec, guards discoverability)
- Given the embedded manual; When `outlook-tool skill`; Then exit 0 and stdout contains `deny <id>`.
All SPEC-0005 acceptance tests E2E-001..011 (from US-0003) must remain green: this is the closing story, `make check` runs the whole set.

## Constraints
- Files not to touch: all of `src/*.py`; `CLAUDE.md` is generated separately (note in the report if it duplicates `AGENTS.md`).
- Scope boundary: no behavior change.

## Definition of done
- [ ] RED evidence for the skill test before editing `skill.md`.
- [ ] `make check` green.
- [ ] Docs updated: `src/skill.md`, `README.md`, `AGENTS.md`.
- [ ] Closes spec: every E2E-001..011 green and every FR-NEW cited by a story (US-0003, US-0004).
- [ ] One commit `US-0004: Document cal deny for operators and agents`, body `Spec: SPEC-0005`.
