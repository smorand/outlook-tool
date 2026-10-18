---
Id: BL-0021
Title: README, AGENTS.md, CLAUDE.md and skill.md omit cal get and the response status column
Nature: DEBT
Source: retro-spec 20261018-185639
Created: 2026-10-18
Severity: Medium
Fingerprint: doc-contradicts-code:src/skill.md:cal-get-response-status
---

## What

`cal get <id>` and the `status` column / `response_status` JSON field of `cal list` were added by
SPEC-0004, and `cal accept` now prints the confirmed status. None of the user facing docs mention them.

## Why

`src/skill.md` is the manual embedded for AI agents; without `cal get` agents cannot discover
how to read one event's response state.

## Evidence

- `src/outlook_tool.py:80-100` (`_render_event_table`, `status` column), `cal_get` command in `src/outlook_tool.py` (`@cal_app.command("get")`).
- `rg -n 'cal get|response_status|Not yet responded' README.md AGENTS.md CLAUDE.md src/skill.md .agent_docs` returns no hit.
- `src/skill.md:206-213` documents `cal accept` only, with the old output.

## Notes

Related: BL-0009 (cal accept missing from AGENTS.md). SPEC-0004. Suggested next command: `/sdlc-retro-doc` (once available).
