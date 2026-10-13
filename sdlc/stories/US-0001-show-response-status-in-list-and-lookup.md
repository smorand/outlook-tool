# US-0001: Show response status in calendar listing and lookup

> Spec: SPEC-0004 (sdlc/specs/SPEC-0004-calendar-response-status/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 1
> Files touched: 6
> Closes spec: no

## Objective

An operator listing events, or looking up one event by id, can see its response state (accepted,
tentatively accepted, declined, not yet responded, or organizer) alongside the fields already
shown. There is no lookup-by-id command today; this story adds one.

## Requirements covered

> Scenarios: SPEC-0004/SC-001 (listing), SPEC-0004/SC-002 (lookup).

- SPEC-0004/FR-MOD-001: WHEN the operator lists events for a start/end window THE calendar SHALL
  show each event's response state alongside the fields already shown, using the vocabulary of
  FR-NEW-002.
- SPEC-0004/FR-NEW-001: WHEN the operator looks up an event by id THE calendar SHALL show that
  event's full summary, including its response state, in the table or machine-readable form the
  operator requested.
- SPEC-0004/FR-NEW-002: The calendar SHALL express an event's response state using exactly one of:
  `Accepted`, `Tentatively accepted`, `Declined`, `Not yet responded`, `Organizer`, and no other
  value, in every place a response state is shown.
- SPEC-0004/FR-NEW-003: IF the given event id does not correspond to an event the operator can see
  THEN THE calendar SHALL fail the lookup and show no event, in the same way the update, delete and
  accept commands already fail today on an unknown id.

## Independent Test

Run `outlook-tool cal list --start <iso> --end <iso>` against a window containing an accepted event,
a not-yet-responded event, and an event the operator organizes: each row shows the correct status.
Then run `outlook-tool cal get <event_id>` for each of those three ids individually: each prints the
same status as the listing did. Then run `outlook-tool cal get <unknown-id>`: the command exits
non-zero and prints no event. None of these assertions mock the story's own output: each reads a
`respx`-mocked Graph response shaped exactly like a real Graph event resource.

## Design excerpt

### Decisions

- DEC-001 (SPEC-0004): Use Microsoft Graph's `responseStatus.response` field as the sole source for
  the five-label vocabulary: `accepted` → `Accepted`, `tentativelyAccepted` → `Tentatively
  accepted`, `declined` → `Declined`, `organizer` → `Organizer`, anything else (`none`,
  `notResponded`, missing, or unrecognized) → `Not yet responded`.
- DEC-002 (SPEC-0004): Request `responseStatus` in the `$select` clause of both listing and the new
  lookup, alongside the existing `organizer`/`location`/`categories` fields.
- DEC-003 (SPEC-0004): Add `CalendarService.get_event(event_id)` as GET `/me/events/{event_id}` with
  the same `$select` listing uses, parallel to the existing `update_event`/`delete_event`.
- DEC-005 (SPEC-0004): Represent the mapped label as `response_status: str` on
  `CalendarEventSummary`, via a module-level mapping function, following the same defensive style
  already used for `organizer`/`location`/`categories`.
- DEC-006 (SPEC-0004): `cal get <event_id>` mirrors `cal list`'s existing `--json`/table rendering,
  reusing `CalendarEventSummary`.
- DEC-007 (SPEC-0004): `cal get` on a failing id lets `GraphError` propagate uncaught, exactly like
  `cal update`/`cal delete`/`cal accept` today (this is the existing behavior, not something to add
  a new try/except around; see `BL-0018` for the separate, out-of-scope cleanup of that pattern).

### Data model

`CalendarEventSummary` (`src/models.py:225-262`), add one field:

```python
response_status: str  # one of: "Accepted", "Tentatively accepted", "Declined",
# "Not yet responded", "Organizer"
```

Add a module-level mapping function (name and exact signature at the implementer's discretion,
following the file's existing style), used by `CalendarEventSummary.from_graph`:

```python
_RESPONSE_STATUS_LABELS = {
    "accepted": "Accepted",
    "tentativelyAccepted": "Tentatively accepted",
    "declined": "Declined",
    "organizer": "Organizer",
}
# default: "Not yet responded" for anything else (missing field, missing "response"
# sub-value, "none", "notResponded", or any unrecognized raw value)
```

Applied inside `from_graph` the same defensive way `organizer`/`location`/`categories` already are
(`src/models.py:230-262`): read `item.get("responseStatus")`, guard non-dict shapes, read its
`"response"` key, look it up in the mapping with a default.

### Contracts

- `CalendarService._EVENT_SELECT` (`src/services/calendar.py:18`): add `,responseStatus` to the
  existing comma-joined field list.
- `CalendarService.get_event(self, event_id: str) -> CalendarEventSummary`: new method. GET
  `/me/events/{event_id}?$select=<_EVENT_SELECT>`, parse the single returned event resource through
  `CalendarEventSummary.from_graph`, wrapped in a `trace_span` the same way every other
  `CalendarService` method already is (`src/services/calendar.py:50-77`).
- CLI `cal get <event_id> [--json]`: new Typer command under `cal_app`, in `src/outlook_tool.py`
  alongside the existing `cal_add`/`cal_list`/`cal_update`/`cal_delete`/`cal_accept` commands
  (`src/outlook_tool.py:526-672`). Table rendering: a single-row table with the same columns
  `cal list` uses (`start`, `end`, `subject`, `location`, `categories`, `id`) plus a `status` column.
  `--json`: `typer.echo(json.dumps(event.model_dump(), ensure_ascii=False))` (one object, not a
  list, since this is a single event — mirror `cal list --json`'s per-item shape at
  `src/outlook_tool.py:538-540` but without the surrounding list).
- CLI `cal list`: add a `status` table column reading `event.response_status`; `--json` needs no
  code change (the new model field appears automatically via `model_dump()`).

### Paths

| Path | Action |
|---|---|
| `src/models.py` | Modify |
| `src/services/calendar.py` | Modify |
| `src/outlook_tool.py` | Modify |
| `tests/test_models.py` | Modify |
| `tests/test_calendar.py` | Modify |
| `tests/test_cli.py` | Modify |

### Existing patterns

- Defensive coercion in `from_graph`: `src/models.py:230-262` (the `organizer`/`location`/
  `categories` handling is the template to follow for `response_status`).
- Service method shape with `trace_span`: `src/services/calendar.py:50-77` (`create_event`,
  `update_event`, `delete_event`, `accept_event` are all the same shape: `with trace_span(...):`
  wrapping one Graph call and a `logger.info` line).
- CLI command shape: `src/outlook_tool.py:526-559` (`cal_list`) is the closest template for `cal_get`
  (single-row table instead of multi-row, same `--json` branch structure).

## Acceptance tests

> 100% must pass, run through `make check`. Never run test files ad hoc.

### SPEC-0004/E2E-001: Listing shows "Accepted" for an event the operator already accepted
- Level / Driver / Location: functional e2e / CLI (`CliRunner`) / `tests/test_cli.py`
- Preconditions: a `respx`-mocked `GET /me/calendarView` response containing one event with
  `"responseStatus": {"response": "accepted", "time": "2026-01-01T00:00:00Z"}`.
- Given a window containing that event
- When the operator runs `cal list --start <iso> --end <iso>`
- Then the table row for that event shows `Accepted` in the status column

### SPEC-0004/E2E-002: Listing shows "Not yet responded" for a pending invitation
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given a window containing one event with `"responseStatus": {"response": "notResponded", ...}`
- When the operator runs `cal list --start <iso> --end <iso>`
- Then the table row for that event shows `Not yet responded`

### SPEC-0004/E2E-003: Listing shows "Organizer" for an event the operator organizes
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given a window containing one event with `"responseStatus": {"response": "organizer", ...}`
- When the operator runs `cal list --start <iso> --end <iso>`
- Then the table row for that event shows `Organizer`

### SPEC-0004/E2E-004: Machine-readable listing includes response state
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given a window containing one event with `"responseStatus": {"response": "tentativelyAccepted",
  ...}`
- When the operator runs `cal list --start <iso> --end <iso> --json`
- Then the parsed JSON output for that event has `"response_status": "Tentatively accepted"`

### SPEC-0004/E2E-012: Listing defaults to "Not yet responded" when the state is missing
- Level / Driver / Location: integration / direct call, Graph mocked via `respx` /
  `tests/test_calendar.py`
- Given a `respx`-mocked `GET /me/calendarView` response for one event with no `responseStatus` key
  at all
- When `CalendarService.list_events(...)` is called for that window
- Then the returned `CalendarEventSummary.response_status` is `"Not yet responded"`
- And the call does not raise

### SPEC-0004/E2E-014: Listing defaults to "Not yet responded" for an unrecognized state value
- Level / Driver / Location: unit / direct call / `tests/test_models.py`
- Given a raw event dict with `"responseStatus": {"response": "somethingUnexpected"}`
- When `CalendarEventSummary.from_graph(...)` is called with it
- Then the resulting `response_status` is `"Not yet responded"`, never `"somethingUnexpected"`

### SPEC-0004/E2E-018: Listing still shows a response state when other fields on the same event are malformed
- Level / Driver / Location: integration / direct call, Graph mocked via `respx` /
  `tests/test_calendar.py`
- Given a `respx`-mocked event whose `"location"` and `"organizer"` are malformed (e.g. `"location":
  "not-an-object"`, `"organizer": null`), but whose `"responseStatus": {"response": "accepted"}` is
  well formed
- When `CalendarService.list_events(...)` is called for that window
- Then the returned summary's `response_status` is `"Accepted"`
- And the call does not raise

### SPEC-0004/E2E-005: Looking up one event shows its response state
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given a `respx`-mocked `GET /me/events/{event_id}` response for one event with
  `"responseStatus": {"response": "tentativelyAccepted"}`
- When the operator runs `cal get <event_id>`
- Then the single-row table shows `Tentatively accepted` in the status column
- Also covers SPEC-0004/FR-NEW-003's "happy" counterpart (the id exists)

### SPEC-0004/E2E-006: Machine-readable lookup includes response state
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given a `respx`-mocked event with `"responseStatus": {"response": "accepted"}`
- When the operator runs `cal get <event_id> --json`
- Then the parsed JSON output has `"response_status": "Accepted"`

### SPEC-0004/E2E-008: Looking up a declined event shows "Declined"
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given a `respx`-mocked event with `"responseStatus": {"response": "declined"}`
- When the operator runs `cal get <event_id>`
- Then the table shows `Declined`

### SPEC-0004/E2E-007: Looking up an unknown id fails and shows nothing
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given a `respx`-mocked `GET /me/events/{event_id}` returning HTTP 404
- When the operator runs `cal get <unknown-event-id>`
- Then the command exits with a non-zero status
- And no event table or JSON is printed

### SPEC-0004/E2E-013: Lookup defaults to "Not yet responded" when the state is missing
- Level / Driver / Location: integration / direct call, Graph mocked via `respx` /
  `tests/test_calendar.py`
- Given a `respx`-mocked `GET /me/events/{event_id}` response with no `responseStatus` key
- When `CalendarService.get_event(event_id)` is called
- Then the returned `response_status` is `"Not yet responded"`
- And the call does not raise

### SPEC-0004/E2E-015: Looking up an id the operator cannot access fails the same way as an unknown id
- Level / Driver / Location: functional e2e / CLI / `tests/test_cli.py`
- Given a `respx`-mocked `GET /me/events/{event_id}` returning HTTP 403
- When the operator runs `cal get <event_id>`
- Then the command exits with a non-zero status, the same way E2E-007 does
- And no event is displayed

## Constraints

- Files not to touch: `src/services/mail.py`, `src/auth.py`, `src/config.py`, `src/graph_client.py`
  (this story is calendar-only).
- Dependencies not to add: none; this reuses the existing `httpx`/`respx`/Typer/pydantic stack.
- Patterns to avoid: do not add a `/me` profile fetch to determine "organizer" (DEC-001 rejects it);
  do not add a try/except around `cal get`'s unknown-id path (DEC-007, matches existing behavior).
- Scope boundary: `cal accept`'s confirmation message is US-0002's job, not this story's; do not
  touch `accept_event` or the `cal accept` command here.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: every existing `tests/test_calendar.py`, `tests/test_models.py`,
      `tests/test_cli.py` test for `cal list`, `cal add`, `cal update`, `cal delete` passes unchanged
      (this story adds a column and a command; it does not remove or reshape an existing one).
- [ ] Docs updated: none required by this story's scope (see design.md Section 6; `AGENTS.md`'s
      `cal accept` omission, BL-0009, is pre-existing and out of scope).
- [ ] Self review: full.
- [ ] One commit `US-0001: Show response status in calendar listing and lookup`, body `Spec:
      SPEC-0004` and the requirement ids FR-MOD-001, FR-NEW-001, FR-NEW-002, FR-NEW-003.
