# US-0002: Confirm the response status after accepting an invitation

> Spec: SPEC-0004 (sdlc/specs/SPEC-0004-calendar-response-status/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0001
> min_tier: 2
> Files touched: 4
> Closes spec: yes

## Objective

Accepting a meeting invitation today only confirms that the request was sent, never that it was
recorded. This story makes `cal accept` re-check the event right after accepting and state the
resulting response state, so an operator (or an agent driving the CLI) can formally confirm the
acceptance registered.

## Requirements covered

> Scenario: SPEC-0004/SC-003 (accept confirmation).

- SPEC-0004/FR-MOD-002: WHEN the operator accepts a meeting invitation THE calendar SHALL,
  immediately after accepting, check and state the event's resulting response state in the
  confirmation message. Before: a generic "Accepted event id=<id>" message with no check. After: the
  confirmation message states the resulting response state, for example "Accepted event id=<id>
  (confirmed status: Accepted)". IF checking the resulting state fails, THEN the message instead
  states that the status could not be confirmed, for example "Accepted event id=<id> (status could
  not be confirmed)", and the command still succeeds.

## Independent Test

Run `outlook-tool cal accept <event_id>` against an event the operator has not yet responded to: the
confirmation message states `confirmed status: Accepted`, and a subsequent `cal get <event_id>`
(from US-0001) independently shows `Accepted` too — a second, different read path than the accept
command's own message, through a separately mocked `respx` route. Then run `cal accept` again with
the re-fetch's `respx` route returning a Graph error: the command still exits zero and prints
"status could not be confirmed".

## Design excerpt

### Decisions

- DEC-004 (SPEC-0004): Implement the accept-confirmation by having `accept_event` call the existing
  POST accept, then call `get_event` (built in US-0001) to re-fetch and read the resulting label,
  returning it, or `None` if the re-fetch raises `GraphError` (caught separately from the accept
  call's own success, which is never retried or rolled back because of a re-fetch failure).

### Data model

None beyond US-0001's `CalendarEventSummary.response_status` field, which this story reads via
`get_event`.

### Contracts

- `CalendarService.accept_event(self, event_id: str) -> str | None` (signature change from `-> None`
  in `src/services/calendar.py:72-77`): after the existing `POST
  /me/events/{event_id}/accept` call, call `self.get_event(event_id)` inside a `try`/`except
  GraphError`; on success return its `response_status`; on `GraphError` return `None`. The accept
  POST itself is unchanged: if it fails, it still raises and `get_event` is never reached.
- CLI `cal accept <event_id>` (`src/outlook_tool.py:664-672`): print
  `f"Accepted event id={event_id} (confirmed status: {status})"` when `accept_event` returns a
  string, else `f"Accepted event id={event_id} (status could not be confirmed)"` when it returns
  `None`.

### Paths

| Path | Action |
|---|---|
| `src/services/calendar.py` | Modify |
| `src/outlook_tool.py` | Modify |
| `tests/test_calendar.py` | Modify |
| `tests/test_cli.py` | Modify |

### Existing patterns

- `accept_event`'s current shape to extend: `src/services/calendar.py:72-77`.
- `get_event` built in US-0001, same file: use it exactly as US-0001 defined it (GET
  `/me/events/{event_id}?$select=...`, wrapped in `trace_span`).
- `cal accept`'s current CLI shape to extend: `src/outlook_tool.py:664-672`.

## Acceptance tests

> 100% must pass, run through `make check`. Never run test files ad hoc.

### SPEC-0004/E2E-009: Accepting a pending invitation confirms "Accepted"
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Preconditions: `respx`-mocked `POST /me/events/{event_id}/accept` returning 202/200, and a
  separately mocked `GET /me/events/{event_id}` returning `"responseStatus": {"response":
  "accepted"}`.
- Given an event the operator has not yet responded to
- When the operator runs `cal accept <event_id>`
- Then the printed message is `Accepted event id=<event_id> (confirmed status: Accepted)`
- And a separate `cal get <event_id>` call afterward (its own `respx` route) also shows `Accepted`

### SPEC-0004/E2E-017: Accepting a tentatively-accepted invitation confirms "Accepted"
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given an event the operator has tentatively accepted, with the post-accept re-fetch mocked to
  return `"responseStatus": {"response": "accepted"}`
- When the operator runs `cal accept <event_id>`
- Then the printed message is `Accepted event id=<event_id> (confirmed status: Accepted)`

### SPEC-0004/E2E-010: Accept succeeds even when the confirmation check fails
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given a `respx`-mocked accept call that succeeds, and a `respx`-mocked `GET
  /me/events/{event_id}` for the re-fetch that returns HTTP 500
- When the operator runs `cal accept <event_id>`
- Then the command exits zero (the accept itself succeeded)
- And the printed message is `Accepted event id=<event_id> (status could not be confirmed)`

### SPEC-0004/E2E-011 (also satisfies SPEC-0004/E2E-MOD-002): Accept on an unknown id still fails the same way
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given a `respx`-mocked `POST /me/events/{event_id}/accept` returning HTTP 404
- When the operator runs `cal accept <unknown-event-id>`
- Then the command fails exactly as it did before this story (non-zero exit, no confirmation
  message printed)
- And the re-fetch route is never called (the accept call's own failure is raised before
  `get_event` would run)

### SPEC-0004/E2E-016: Re-accepting an already-accepted event still confirms "Accepted"
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given an event already `"responseStatus": {"response": "accepted"}`, with the accept call and the
  re-fetch both mocked to succeed
- When the operator runs `cal accept <event_id>` again
- Then the command succeeds and prints `Accepted event id=<event_id> (confirmed status: Accepted)`

### SPEC-0004/E2E-MOD-001: Accept confirmation message (modifies the existing generic-confirmation test)
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Validated before: `tests/test_cli.py::test_cal_accept_command` asserted the message
  `Accepted event id=<id>` with no status.
- Validates now: the same test, updated, asserts `Accepted event id=<id> (confirmed status:
  Accepted)` (same scenario as E2E-009; this row tracks the existing test file being modified, not a
  new test).

## Constraints

- Files not to touch: `src/models.py` (no new field needed; this story only reads the field
  US-0001 already added).
- Dependencies not to add: none.
- Patterns to avoid: do not retry or fail the accept call because the confirmation re-fetch failed;
  the two are independent per FR-MOD-002's exception path.
- Scope boundary: `cal get`'s own behavior is US-0001's; do not change it here beyond calling it from
  `accept_event`.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_calendar.py::test_accept_event` and
      `tests/test_cli.py::test_cal_accept_command` are updated (not deleted) to assert the new
      message, per the design's Section 6 "Affected existing tests" note; every other existing
      calendar and CLI test passes unchanged.
- [ ] Docs updated: none required by this story's scope.
- [ ] Self review: full.
- [ ] Closes spec: SPEC-0004's full acceptance set (every E2E- listed across US-0001 and this story)
      is green, and every requirement of SPEC-0004 (FR-MOD-001, FR-MOD-002, FR-NEW-001, FR-NEW-002,
      FR-NEW-003) is cited by at least one story with status done or landed.
- [ ] One commit `US-0002: Confirm the response status after accepting an invitation`, body `Spec:
      SPEC-0004` and the requirement id FR-MOD-002.
