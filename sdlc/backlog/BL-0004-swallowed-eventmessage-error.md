---
Id: BL-0004
Title: Log the swallowed GraphError in get_message's eventMessage-cast fallback
Nature: DEBT
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Low
Fingerprint: debt:src/services/mail.py:get_message:except GraphError: pass
---

## What

When retrieving a meeting message, `get_message` makes a second request to fetch the meeting's
start/end via the `microsoft.graph.eventMessage` cast. If that request fails, the `GraphError` is
caught and silently discarded with no log line.

## Why

A real failure (permission change, API change) becomes invisible: the operator gets an incomplete
message with no indication why the meeting times are missing, and there is nothing in the logs to
diagnose it.

## Evidence

- `src/services/mail.py:313-315`: `except GraphError: pass` with no `logger.warning` call.

## Notes

Related: SPEC-0002/FR-014. Related: BL-0002 (same path, untested). Suggested next command:
`/sdlc-spec`.
