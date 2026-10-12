---
Id: BL-0017
Title: Expose meeting response status in calendar JSON output
Nature: FEAT
Created: 2026-10-12
---

## What

`outlook-tool` does not expose the response status (accepted / tentatively accepted / not yet
responded) of a calendar event in its JSON output. After running `cal accept`, there is no way to
formally confirm the acceptance actually registered.

## Why

Without this, an operator (or an agent driving the CLI) cannot verify that `cal accept` succeeded
beyond the absence of an error; the event's actual response state stays invisible.

## Notes

Graph exposes this as `responseStatus` on an event. Candidate for `/sdlc-spec` against
SPEC-0003 (Calendar): likely a new field on `CalendarEventSummary`/`--json` output, and possibly a
verification step after `cal accept`.
