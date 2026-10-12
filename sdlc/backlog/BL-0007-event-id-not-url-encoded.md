---
Id: BL-0007
Title: URL-encode event_id before interpolating it into Graph request paths
Nature: DEBT
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Low
Fingerprint: debt:src/services/calendar.py:event_id-interpolation
---

## What

`update_event`, `delete_event`, and `accept_event` interpolate `event_id` directly into an f-string
path (`/me/events/{event_id}`, `/me/events/{event_id}/accept`) with no URL-encoding.

## Why

Graph event ids are opaque base64-like strings in practice, so this is low risk today, but any id
containing `/` or another reserved character would corrupt the request path with no clear error.
The same pattern exists for `message_id` in the mail area.

## Evidence

- `src/services/calendar.py:60,67,74` — `event_id` interpolated raw into the path.
- No test supplies an id with a special character.

## Notes

Related: SPEC-0003/FR-006, SPEC-0003/FR-009, SPEC-0003/FR-010. Suggested next command:
`/sdlc-spec --debt`.
