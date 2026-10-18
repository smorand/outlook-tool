---
Id: BL-0020
Title: Refresh stale file:LINE citations in as-built SPEC-0001, SPEC-0002 and SPEC-0003
Nature: DEBT
Source: retro-spec 20261018-185639
Created: 2026-10-18
Severity: Low
Fingerprint: stale-citation:src/outlook_tool.py:render_event_table-line-shift
---

## What

Commits `8a5042c` (US-0001) and `0431579` (US-0002) changed `src/outlook_tool.py`,
`src/services/calendar.py` and `src/models.py` after the as-built specs were written at base
`6956ac5`. Line numbers moved, so citations no longer match the cited content. The behaviors
described are still accurate except where SPEC-0004 explicitly modifies them (SPEC-0003/FR-001
listing, SPEC-0003/FR-010 accept).

## Why

Evidence cells that point at the wrong lines mislead reviewers and `/sdlc-analysis` baselines.

## Evidence

Comparison of every `src/...:LINE` citation between `6956ac5` and HEAD (content at the cited range differs):

- `SPEC-0001/spec.md` and `design.md`: `src/outlook_tool.py:104-106`, `109-123`, `111-121`
  (old `async def _do(authenticator...`, now `"""Render a list of MailSummary as a rich table."""`; the `_render_event_table` helper inserted at `src/outlook_tool.py:80` shifts later lines by +23).
- `SPEC-0002/spec.md` and `design.md`: `src/outlook_tool.py:132-135`, `193-195`, `196-204`, `258-260`, `512-520`, plus the per command ranges in the design flows (`119-523`).
- `SPEC-0003/spec.md` and `design.md`: `src/outlook_tool.py:526-672`, `613-637`, `664-672`; `src/services/calendar.py:30-77` (`get_event` inserted at line 31); `src/models.py:174-262` (`map_response_status` and `response_status` added).

## Notes

Rewriting an as-built spec is a `/sdlc-spec` job; this retro run did not edit them. Suggested next
command: `/sdlc-spec` delta on SPEC-0003 (fold in SPEC-0004) then re-run `/sdlc-retro-spec`.
