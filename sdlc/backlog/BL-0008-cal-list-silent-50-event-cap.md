---
Id: BL-0008
Title: cal list silently drops events beyond the first 50 in a window
Nature: BUG
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Medium
Fingerprint: suspected-defect:src/services/calendar.py:list_events:top=50
---

## What

`CalendarService.list_events` hardcodes `$top=50` with no CLI override and never follows
`@odata.nextLink`. A time window with more than 50 overlapping events returns only the first 50,
with no warning that results were truncated.

## Why

An operator reviewing a busy week could believe their calendar is emptier than it is, with no
indication that anything was cut off.

## Evidence

- `src/services/calendar.py:30-46`: `top: int = 50` parameter, no pagination loop, no
  `@odata.nextLink` handling anywhere in the file.
- No CLI flag exposes or overrides `top` (`src/outlook_tool.py:526-559`).

## Notes

Related: SPEC-0003/FR-001, SPEC-0003/FR-002 (untested, see BL-0003). Suggested next command:
`/sdlc-spec`.
