---
Id: BL-0003
Title: Add tests for the 50-event cap and the invalid show-as rejection
Nature: DEBT
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Medium
Fingerprint: untested:src/services/calendar.py:list_events
---

## What

Two requirements of SPEC-0003 are implemented but untested: FR-002 (a window with more than 50
overlapping events silently returns only 50) and FR-005 (an invalid `show-as` value is rejected
before any network call).

## Why

FR-002 is a silent data-loss path (see also BL-0008); without a test, a change to the cap or an
accidental pagination fix would go unnoticed either way. FR-005's validator could be removed by
accident with no test catching it.

## Evidence

- `src/services/calendar.py:30-46` — `top: int = 50`, no pagination, no test with >50 items.
- `src/models.py:174,189-196` — `SHOW_AS_VALUES` validator, no test supplies an invalid value.
- Listed as `untested` at SPEC-0003/E2E-009 and SPEC-0003/E2E-010.

## Notes

Related: SPEC-0003/FR-002, SPEC-0003/FR-005. Suggested next command: `/sdlc-retro-tests`.
