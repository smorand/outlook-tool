---
Id: BL-0009
Title: AGENTS.md and CLAUDE.md command list omits cal accept
Nature: DEBT
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Medium
Fingerprint: doc-contradicts-code:AGENTS.md:cal-accept
---

## What

AGENTS.md's architecture section lists the CLI command surface as `cal add|list|update|delete`,
omitting `cal accept`, which exists in code, is used in the embedded `skill.md` manual, and has
dedicated tests.

## Why

AGENTS.md is the document AI agents (and this very retro pass) load first to understand the
command surface; an agent relying only on it would not know `cal accept` exists.

## Evidence

- `AGENTS.md` architecture section: `"Commandes: ... cal add|list|update|delete"`.
- `src/outlook_tool.py:664-672`: `@cal_app.command("accept")` exists.
- `CLAUDE.md` is a symlink to `AGENTS.md`, carrying the same gap.
- `tests/test_cli.py` contains a `cal accept` test section.

## Notes

Related: SPEC-0003/FR-010. This is read-only documentation outside `sdlc/`; not fixed by this
pass per Invariant 1/2. Suggested next command: `/sdlc-retro-doc` (once available).
