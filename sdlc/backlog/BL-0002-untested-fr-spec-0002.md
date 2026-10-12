---
Id: BL-0002
Title: Add a test for the eventMessage-cast failure path in get_message
Nature: DEBT
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Medium
Fingerprint: untested:src/services/mail.py:get_message
---

## What

`get_message`'s fallback request for a meeting message's start/end (the `microsoft.graph.eventMessage`
cast) can raise `GraphError`, which is caught and ignored. No test exercises this failure branch;
only the success path is tested.

## Why

If this fallback starts failing in production (API shape change, permission issue), the tool would
silently return an incomplete message with no signal in the test suite.

## Evidence

- `src/services/mail.py:313-315` — `except GraphError: pass`, no test triggers the exception.
- Listed as `untested` at SPEC-0002/E2E-019.
- Only `tests/test_mail.py::test_get_message_uses_eventmessage_cast_for_meeting` exists (success path).

## Notes

Related: SPEC-0002/FR-014. Related: BL-0004 (same code path, swallowed-error finding). Suggested
next command: `/sdlc-retro-tests`.
