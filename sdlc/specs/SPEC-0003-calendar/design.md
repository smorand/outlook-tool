# Calendar: Design (as-built)

> Spec: SPEC-0003
> Status: as-built
> Generated on: 2026-10-12 at 6956ac5

## 1. Components

| Component | Responsibility | Location |
|---|---|---|
| `CalendarService` | All calendar operations against Graph | `src/services/calendar.py` |
| `outlook_tool.py` cal commands | CLI surface for `cal add\|list\|update\|delete\|accept` | `src/outlook_tool.py:526-672` |
| `models.py` (CalendarEventInput, CalendarEventSummary) | Value objects and Graph (de)serialization | `src/models.py:174-262` |

## 2. Flows

### List (FR-001, FR-002)
`list_events(start, end, time_zone="Europe/Paris", top=50)`
(`src/services/calendar.py:30-46`): GET `/me/calendarView` with `startDateTime`,
`endDateTime`, `$select=id,subject,start,end,organizer,location,categories`,
`$orderby=start/dateTime`, `$top=50`, header `Prefer: outlook.timezone="<tz>"`. `top` is
hardcoded at the service signature, not exposed as a CLI flag, and no `@odata.nextLink` is
ever followed, so a window with more than 50 events silently loses the remainder.

### Create (FR-003, FR-004, FR-005)
`create_event` POSTs `/me/events` with `event.to_graph_event()`
(`src/services/calendar.py:50-56`). `to_graph_event` (`src/models.py:205-219`) builds
`start`/`end` as `{dateTime, timeZone}`, includes `body` only if not None, `location` only
if truthy, `attendees` always mapped to `type: "required"`, `showAs`/`categories` only if
set/non-empty. `CalendarEventInput.show_as` is validated against the frozenset
`SHOW_AS_VALUES = {free, tentative, busy, oof, workingElsewhere, unknown, away}`
(`src/models.py:174,189-196`) before any network call.

### Update (FR-006, FR-007, FR-008)
CLI `cal update` builds an arbitrary `changes` dict from whichever flags were given
(`src/outlook_tool.py:620-625`), rejecting the no-op case
(`src/outlook_tool.py:633-637`) and the `--category`/`--clear-categories` conflict
(`src/outlook_tool.py:613-616`) before calling `update_event`, which PATCHes
`/me/events/{event_id}` with exactly that dict (`src/services/calendar.py:58-64`).

### Delete (FR-009)
`delete_event`: DELETE `/me/events/{event_id}` (`src/services/calendar.py:66-70`).

### Accept (FR-010)
`accept_event`: POST `/me/events/{event_id}/accept` with body `{"sendResponse": false}`,
hardcoded, no CLI flag to change it (`src/services/calendar.py:72-77`,
`src/outlook_tool.py:664-672`).

## 3. Interfaces

CLI: `cal list --start --end [--tz] [--json]` (`src/outlook_tool.py:526-559`);
`cal add --subject --start --end [--tz] [--location] [--body] [--attendee ...]
[--show-as] [--category ...]` (`src/outlook_tool.py:564-600`);
`cal update <event_id> [--subject] [--start] [--end] [--tz] [--show-as] [--category ...] |
[--clear-categories]` (`src/outlook_tool.py:602-650`); `cal delete <event_id>`
(`src/outlook_tool.py:652-660`); `cal accept <event_id>` (`src/outlook_tool.py:664-672`).
`cal list`/`cal update` table views truncate event ids to 16 characters; `--json` on
`cal list` returns full ids (`src/outlook_tool.py:555`).

## 4. Data and state

Graph resources only, no local persistence. `CalendarEventSummary.from_graph`
defensively coerces `start`/`end`/`organizer`/`location`/`categories` from nested dicts,
defaulting to empty strings/list on malformed input (`src/models.py:230-262`).

## 5. Configuration

| Name | Source | Default | Evidence |
|---|---|---|---|
| time zone | CLI flag `--tz` on `cal list`/`cal add`/`cal update` | `Europe/Paris` | `src/outlook_tool.py:531,569,609`, `src/models.py:180`, `src/services/calendar.py:30` |
| `$top` (event count per list) | hardcoded in `CalendarService.list_events` | `50` | `src/services/calendar.py:30` |

No `OUTLOOK_TOOL_*` setting exists for either value; the `Europe/Paris` default is a literal
duplicated in four separate locations with no single source of truth.

## 6. Observability

Every `CalendarService` method wraps its Graph call in an OpenTelemetry span via
`trace_span` (`src/services/calendar.py:51,60,67,74`); no calendar-specific metrics beyond
the shared `GraphClient` span (see SPEC-0001 design §6).

## 7. Decisions (observed)

| ID | Decision | Evidence | Rationale |
|---|---|---|---|
| DEC-001 | List results capped at 50 with no pagination support | `src/services/calendar.py:30-46` | Not documented; observed limitation |
| DEC-002 | All attendees added as `type: "required"`, no optional-attendee support | `src/models.py:212-215` | Not documented |
| DEC-003 | `accept_event` always sends `sendResponse: false`, no CLI override | `src/services/calendar.py:72-77` | Not documented |
| DEC-004 | No `recurrence` field; recurring events are entirely unsupported | absence confirmed in `src/models.py:175-221` | Not documented |

## 8. Requirement to code map

| Requirement | Files |
|---|---|
| SPEC-0003/FR-001 | `src/services/calendar.py:30-46` |
| SPEC-0003/FR-002 | `src/services/calendar.py:31` |
| SPEC-0003/FR-003 | `src/models.py:205-219` |
| SPEC-0003/FR-004 | `src/models.py:212-215` |
| SPEC-0003/FR-005 | `src/models.py:174,191-196` |
| SPEC-0003/FR-006 | `src/services/calendar.py:58-64`, `src/outlook_tool.py:620-625` |
| SPEC-0003/FR-007 | `src/outlook_tool.py:633-637` |
| SPEC-0003/FR-008 | `src/outlook_tool.py:613-616` |
| SPEC-0003/FR-009 | `src/services/calendar.py:66-70` |
| SPEC-0003/FR-010 | `src/services/calendar.py:72-77` |
