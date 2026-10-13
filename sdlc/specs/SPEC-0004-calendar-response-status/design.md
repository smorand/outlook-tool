# SPEC-0004: Calendar response status, design

> Spec: sdlc/specs/SPEC-0004-calendar-response-status/spec.md
> Nature: FEAT
> Depth: S
> Security: n/a
> Designed on: 2026-10-13
> Target tier: 2 (default: no `--tier` flag, no `Tier:` field in `sdlc/constitution.md`, no `.spec.json`)

## 1. Stack and skills

| Element | Choice | Version | DEC |
|---|---|---|---|
| Language/runtime | Python, existing | 3.13+ (per `pyproject.toml: requires-python = ">=3.13"`) | n/a (existing) |
| CLI framework | Typer, existing | per `uv.lock` | n/a (existing) |
| HTTP client | httpx (async), existing | per `uv.lock` | n/a (existing) |
| Test runner | pytest + pytest-asyncio + respx, existing | per `uv.lock` | n/a (existing) |

No new dependency. This feature reads one additional field (`responseStatus`) already returned by
the same Microsoft Graph event resource the codebase already calls; no new library, service or
infrastructure.

Skills loaded: `python` (async-first, Ruff, mypy strict, Typer, pydantic-settings, `make check` gate,
flat `src/` layout, `tests/` mirrors `src/`). Effect: new code follows the existing `src/services/*.py`
+ `src/models.py` + `src/outlook_tool.py` split; tests land in the matching `tests/test_*.py` files;
`make check` (lint, format-check, typecheck, security, test-cov >=80%) is each story's gate, run via
`make check`, never a bare `pytest`.

## 2. Approaches

### Chosen: read `responseStatus` from the event resource Graph already returns

Summary: add `responseStatus` to the existing `$select` clause used by both listing and the new
single-event lookup, map its `response` sub-value to the spec's five labels in one shared function,
and store it on `CalendarEventSummary`. For `cal accept`, re-fetch the event right after accepting
(via the same new lookup) and read the resulting label.

Pros: no new Graph permission or scope (the field is already covered by the existing delegated
scopes); reuses the exact `$select` and defensive-coercion pattern already used for `organizer`,
`location`, `categories` (`src/models.py:230-262`); the "organizer" distinction is supplied by Graph
itself, with no need to compare emails or call a `/me` profile endpoint that does not exist anywhere
in this codebase today.

Cons and risks: `responseStatus` on an event the operator organizes is documented to read
`"organizer"` rather than one of the attendee states, so the mapping needs that case explicit (DEC-001
below) rather than treated as an error.

Affected scope: `src/models.py`, `src/services/calendar.py`, `src/outlook_tool.py` (calendar
commands only).

Best suited when: the field needed is already present on a resource the code already fetches, which
is the case here — confirmed via Microsoft Graph's `responseStatus` resource documentation (fetched
2026-10-13: `response` is one of `none`, `organizer`, `tentativelyAccepted`, `accepted`, `declined`,
`notResponded`).

### Rejected: derive "organizer" by comparing the event's organizer email to the operator's own identity

Summary: fetch the signed-in user's own profile (a new `/me` call) and compare its address to the
event's `organizer.emailAddress.address` to decide whether to show `Organizer`.

Why rejected (DEC-001): Graph's own `responseStatus.response` already returns `"organizer"` directly
for events the signed-in user organizes, with no extra call needed; adding a `/me` profile fetch and
an email comparison would duplicate logic Graph already does, for no behavioral gain.

## 3. Architecture

No new component. Three existing components are extended:

- `CalendarService` (`src/services/calendar.py`): `_EVENT_SELECT` gains `responseStatus`; a new
  method `get_event` is added, parallel to the existing `update_event`/`delete_event`/`accept_event`,
  which already target `/me/events/{event_id}` (`src/services/calendar.py:58-77`); `accept_event` is
  changed to re-fetch via `get_event` after accepting and return the resulting label (or `None` on
  failure), instead of returning nothing.
- `models.py`: `CalendarEventSummary` gains a `response_status: str` field; a new module-level mapping
  function translates Graph's raw `responseStatus` sub-object to one of the five spec labels,
  following the same defensive style already used by `CalendarEventSummary.from_graph` for
  `organizer`/`location`/`categories` (`src/models.py:230-262`).
- `outlook_tool.py` cal commands (`src/outlook_tool.py:526-672`): `cal list`'s table gains a status
  column and its `--json` output gains the field for free (via `model_dump()`); a new `cal get
  <event_id> [--json]` command is added, mirroring `cal list`'s existing rendering; `cal accept`'s
  confirmation message is extended with the re-fetched label.

```
cal list / cal get  ──▶  CalendarService.list_events / .get_event  ──▶  GET /me/calendarView
                                                                          GET /me/events/{id}
                                 │
                                 ▼
                     CalendarEventSummary.from_graph (+ response-status mapping)

cal accept  ──▶  CalendarService.accept_event  ──▶  POST /me/events/{id}/accept
                                 │
                                 ▼
                     CalendarService.get_event (re-fetch)  ──▶  GET /me/events/{id}
                                 │
                                 ▼
                     mapped label, or None if the re-fetch failed
```

## 4. Data model

No persisted data change (Graph owns the event resource; nothing is stored locally). Model change
only:

`CalendarEventSummary` (`src/models.py:225-229`), before:

```
id: str
subject: str
start: str
end: str
organizer: str
location: str
categories: list[str] = Field(default_factory=list)
```

After, one field added:

```
response_status: str   # one of: "Accepted", "Tentatively accepted", "Declined",
                        # "Not yet responded", "Organizer"
```

No migration: this is an in-memory value object built fresh from each Graph response, never
persisted to disk.

## 5. Contracts and interfaces

**CLI:**
- `cal list --start <iso> --end <iso> [--tz <zone>] [--json]` (existing, unchanged flags): table
  gains a `status` column; `--json` output gains a `response_status` field per event.
- `cal get <event_id> [--json]` (new): table shows the single event's full summary including
  `status`; `--json` shows the same fields `cal list --json` shows for one event.
- `cal accept <event_id>` (existing, unchanged flags): confirmation message changes from
  `Accepted event id=<id>` to exactly one of:
  - `Accepted event id=<id> (confirmed status: <status>)` when the re-fetch succeeds, `<status>` one
    of the five labels (expected: `Accepted`, but re-accepting an already-`Accepted` event also
    prints `Accepted`).
  - `Accepted event id=<id> (status could not be confirmed)` when the re-fetch itself fails; the
    accept call's own success is unaffected.
- Unknown `event_id` on `cal get`: the command fails the same way `cal update`/`cal delete`/`cal
  accept` already do today — the raised `GraphError` is not caught, exit is non-zero, no event is
  printed (per SPEC-0004/FR-NEW-003, DEC-007 below; the raw-crash behavior itself is tracked
  separately as `BL-0018`, not fixed here).

**Service (`CalendarService`, internal, not consumed outside this codebase):**
- `async def get_event(self, event_id: str) -> CalendarEventSummary` — GET `/me/events/{event_id}`
  with the same `$select=_EVENT_SELECT` listing already uses.
- `async def accept_event(self, event_id: str) -> str | None` (signature changed: previously
  `-> None`) — POST `/me/events/{event_id}/accept` as today, then calls `get_event` and returns its
  `response_status`; returns `None` if the re-fetch raises `GraphError` (the accept itself already
  succeeded by that point and is not retried or rolled back).

**Model (`models.py`, internal):**
- A module-level function mapping Graph's raw `responseStatus` object to one of the five labels,
  defaulting to `"Not yet responded"` for a missing field, a missing `response` sub-value, or any
  value outside `{"accepted", "tentativelyAccepted", "declined", "organizer"}` (this also covers
  Graph's own `"none"` and `"notResponded"` values, per the Graph documentation fetched for this
  design, which states clients can treat `notResponded == none`).

No configuration keys added.

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/models.py` | Modify: add `response_status` field, add the mapping function, update `from_graph` | FR-MOD-001, FR-NEW-001, FR-NEW-002 | US-0001 |
| `src/services/calendar.py` | Modify: add `responseStatus` to `_EVENT_SELECT`, add `get_event` | FR-MOD-001, FR-NEW-001 | US-0001 |
| `src/outlook_tool.py` | Modify: `cal list` status column, new `cal get` command | FR-MOD-001, FR-NEW-001, FR-NEW-003 | US-0001 |
| `tests/test_models.py` | Modify: mapping function tests (defensive defaults, all five labels) | FR-NEW-002 | US-0001 |
| `tests/test_calendar.py` | Modify: `list_events`/`get_event` response-status tests | FR-MOD-001, FR-NEW-001 | US-0001 |
| `tests/test_cli.py` | Modify: `cal list` column test, `cal get` command tests | FR-MOD-001, FR-NEW-001, FR-NEW-003 | US-0001 |
| `src/services/calendar.py` | Modify: `accept_event` re-fetches and returns the label | FR-MOD-002 | US-0002 |
| `src/outlook_tool.py` | Modify: `cal accept` confirmation message | FR-MOD-002 | US-0002 |
| `tests/test_calendar.py` | Modify: `accept_event` confirmation and failure tests | FR-MOD-002 | US-0002 |
| `tests/test_cli.py` | Modify: `cal accept` confirmation message tests | FR-MOD-002 | US-0002 |

Affected existing tests: none removed; `tests/test_calendar.py::test_accept_event` and
`tests/test_cli.py::test_cal_accept_command` (both cited in SPEC-0003's as-built evidence) assert the
old generic confirmation message and must be updated to the new one in US-0002 (this is the modified
test pair `E2E-MOD-001`/`E2E-MOD-002` the spec already names).

Affected documentation: `AGENTS.md`'s command list already omits `cal accept` (tracked as `BL-0009`,
out of scope here); adding `cal get` to that same list is a natural follow-up for whichever command
reconciles `AGENTS.md`, not for this design to edit (Invariant 1 of this command does not restrict
`AGENTS.md`, but no story below touches it, since the spec's own scope does not ask for a doc
update and `/sdlc-retro-doc` owns that reconciliation).

## 7. Compatibility and risks

- `CalendarService.accept_event`'s return type changes from `None` to `str | None`. It is an internal
  service method with exactly one caller (`src/outlook_tool.py`'s `cal accept` command,
  `src/outlook_tool.py:664-672`); not a public contract, no deprecation window needed.
- `cal accept`'s printed message changes text; this is the declared behavior change the spec itself
  requires (FR-MOD-002), not an incidental break. No script is known to parse this CLI's human
  output (the `--json` option exists precisely for machine consumption, and `cal accept` has no
  `--json` flag today or after this design).
- No dependency added or removed. No ordering constraint between US-0001 and US-0002 beyond the
  stated `Depends on` (US-0002 needs `get_event`, built in US-0001).

## 9. Test strategy

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| E2E-001 | functional e2e | CLI (`CliRunner`) | `tests/test_cli.py` | US-0001 |
| E2E-002 | functional e2e | CLI | `tests/test_cli.py` | US-0001 |
| E2E-003 | functional e2e | CLI | `tests/test_cli.py` | US-0001 |
| E2E-004 | functional e2e | CLI | `tests/test_cli.py` | US-0001 |
| E2E-012 | integration | direct call, Graph mocked via `respx` | `tests/test_calendar.py` | US-0001 |
| E2E-014 | unit | direct call | `tests/test_models.py` | US-0001 |
| E2E-018 | integration | direct call, Graph mocked via `respx` | `tests/test_calendar.py` | US-0001 |
| E2E-005 | functional e2e | CLI | `tests/test_cli.py` | US-0001 |
| E2E-006 | functional e2e | CLI | `tests/test_cli.py` | US-0001 |
| E2E-008 | functional e2e | CLI | `tests/test_cli.py` | US-0001 |
| E2E-007 | functional e2e | CLI | `tests/test_cli.py` | US-0001 |
| E2E-013 | integration | direct call, Graph mocked via `respx` | `tests/test_calendar.py` | US-0001 |
| E2E-015 | functional e2e | CLI | `tests/test_cli.py` | US-0001 |
| E2E-009 | functional e2e | CLI | `tests/test_cli.py` | US-0002 |
| E2E-017 | functional e2e | CLI | `tests/test_cli.py` | US-0002 |
| E2E-010 | functional e2e | CLI | `tests/test_cli.py` | US-0002 |
| E2E-011 | functional e2e | CLI | `tests/test_cli.py` | US-0002 |
| E2E-016 | functional e2e | CLI | `tests/test_cli.py` | US-0002 |
| E2E-MOD-001 | functional e2e | CLI | `tests/test_cli.py` | US-0002 |
| E2E-MOD-002 | functional e2e | CLI | `tests/test_cli.py` | US-0002 (same assertion as E2E-011) |

Test data: generated inline per test (concrete Graph JSON fixtures built in the test body), matching
the existing style in `tests/test_calendar.py` and `tests/test_cli.py`; no fixture files, nothing
user-provided.

## 10. Decisions log

- **DEC-001:** Use Microsoft Graph's `responseStatus.response` field (already present on every event
  resource) as the sole source for the five-label vocabulary, mapping `accepted` → `Accepted`,
  `tentativelyAccepted` → `Tentatively accepted`, `declined` → `Declined`, `organizer` → `Organizer`,
  and anything else (`none`, `notResponded`, missing, or unrecognized) → `Not yet responded`.
  **Obliged by:** SPEC-0004/FR-NEW-002. **Rationale:** the field already differentiates the organizer
  case without comparing identities. **Alternatives considered:** fetching the signed-in user's own
  profile and comparing emails (rejected, see Section 2). **Source:** spec constraint + external API
  documentation. **Evidence:** Microsoft Graph `responseStatus` resource documentation
  (learn.microsoft.com/en-us/graph/api/resources/responsestatus, fetched 2026-10-13: `response` is
  one of `none, organizer, tentativelyAccepted, accepted, declined, notResponded`; "Clients can treat
  notResponded == none").

- **DEC-002:** Request `responseStatus` in the `$select` clause of both `list_events` and the new
  `get_event`, as a plain additional field alongside `organizer`/`location`/`categories`, rather than
  a second request. **Obliged by:** SPEC-0004/FR-MOD-001, FR-NEW-001. **Rationale:** it is a scalar
  sub-object exactly like the fields already selected; no reason to split. **Alternatives
  considered:** none (the existing pattern directly extends). **Source:** existing code.
  **Evidence:** `src/services/calendar.py:18`.

- **DEC-003:** Add `CalendarService.get_event(event_id)` as GET `/me/events/{event_id}` with the same
  `$select` as listing, parallel to the existing `update_event`/`delete_event`/`accept_event` which
  already target `/me/events/{event_id}`. **Obliged by:** SPEC-0004/FR-NEW-001. **Rationale:**
  consistent with the existing per-event path pattern; standard Graph REST GET on the same resource.
  **Alternatives considered:** filtering a full `list_events` window client-side to find one id
  (rejected: requires the caller to already know a window containing the event, which `cal get`
  explicitly must not require). **Source:** existing code. **Evidence:**
  `src/services/calendar.py:58-77`.

- **DEC-004:** Implement the accept-confirmation (FR-MOD-002) by having `accept_event` call the
  existing POST accept, then call `get_event` to re-fetch and read the resulting label, returning it
  (or `None` on a `GraphError` from the re-fetch, caught separately from the accept call itself).
  **Obliged by:** SPEC-0004/FR-MOD-002. **Rationale:** reuses DEC-003's new retrieval rather than a
  second mechanism; isolates the re-fetch's own failure from the accept call's success, matching
  EXC-003a exactly. **Alternatives considered:** reading a status from the accept POST's own response
  body (rejected: the current code discards that response entirely and Graph's `/accept` action
  returns no event resource to read a status from). **Source:** design + existing code. **Evidence:**
  `src/services/calendar.py:72-77`.

- **DEC-005:** Represent the mapped label as `response_status: str` on `CalendarEventSummary`,
  populated by a module-level mapping function, following the same defensive-coercion style already
  used for `organizer`/`location`/`categories`. **Obliged by:** SPEC-0004/FR-NEW-002 (defensive
  default), FR-MOD-001, FR-NEW-001. **Rationale:** keeps all Graph-shape-to-display translation in one
  place, consistent with the existing pattern. **Source:** existing code. **Evidence:**
  `src/models.py:230-262`.

- **DEC-006:** `cal get <event_id>` mirrors `cal list`'s existing `--json`/table rendering
  (single-row table, or `model_dump()` JSON on `--json`), reusing `CalendarEventSummary` rather than a
  new summary type. **Obliged by:** SPEC-0004/FR-NEW-001. **Rationale:** minimal new surface,
  identical display semantics the spec requires ("the same fields the listing shows"). **Source:**
  spec requirement + existing code. **Evidence:** `src/outlook_tool.py:526-559`.

- **DEC-007:** `cal get` on a failing id lets the `GraphError` propagate uncaught, exactly like `cal
  update`/`cal delete`/`cal accept` today. **Obliged by:** SPEC-0004/FR-NEW-003. **Rationale:**
  FR-NEW-003 explicitly requires matching current behavior, not inventing a new one; the raw-crash
  gap itself is `BL-0018`, out of scope here. **Source:** spec requirement + existing code.
  **Evidence:** `src/outlook_tool.py:57-63`.

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0001 | Show response status in calendar listing and lookup | P1 | FR-MOD-001, FR-NEW-001, FR-NEW-002, FR-NEW-003 | main | 1 | no |
| US-0002 | Confirm the response status after accepting an invitation | P2 | FR-MOD-002 | US-0001 | 2 | yes |
