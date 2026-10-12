# Calendar: Specification (as-built)

> Id: SPEC-0003
> Nature: FEAT
> Status: as-built
> Area: Calendar
> Generated on: 2026-10-12 by /sdlc-retro-spec at 6956ac5
> Confidence: high

## 1. Summary

Lets an operator list events in a time window, create a single (non-recurring) event, update one,
delete one, and accept a meeting invitation without sending a response email.

## 2. Current State

### 2.1 How it works today

Listing requires an explicit start/end window (no implicit "today"/"this week" default) and shows
events in the requested time zone, defaulting to Europe/Paris. Creating an event takes a subject,
start/end, optional location, body, attendees, free/busy status, and categories; attendees are
always added as required (no optional-attendee distinction). Updating an event replaces only the
fields explicitly given. Deleting removes an event outright. Accepting a meeting invitation marks it
accepted on the calendar without notifying the organizer.

### 2.2 Existing specifications governing this area

SPEC-0001 governs authentication and the shared Graph client this area depends on.

### 2.3 Existing test coverage

121 tests pass repository-wide (baseline, exit 0, 94.43% coverage). Calendar-specific: 11 tests in
`tests/test_calendar.py`, 2 model tests in `tests/test_models.py`, and 9 CLI-level tests in
`tests/test_cli.py`. No test is currently red.

## 3. Scope

### 3.1 Covered by this spec

`cal list`, `cal add`, `cal update`, `cal delete`, `cal accept`.

### 3.2 Not covered

Mail (SPEC-0002). Authentication and the shared Graph client (SPEC-0001). Recurring events: not
supported by this tool at all (no requirement exists for them; see Confidence notes and backlog).

## 4. Actors

- **Operator**: manages their own calendar through the CLI.

## 5. Usage Scenarios

### SC-001: List events in a window
Trigger: `cal list --start <iso> --end <iso> [--tz <zone>] [--json]`. Outcome: up to 50 overlapping
events are shown, ordered by start time, in the requested (or default) time zone.

### SC-002: Create a one-off event
Trigger: `cal add --subject ... --start ... --end ... [--location] [--body] [--attendee ...]
[--show-as ...] [--category ...]`. Outcome: the event is created with exactly the given fields;
omitted optional fields are not sent to Graph at all.

### SC-003: Update an event
Trigger: `cal update <id> [--subject] [--start] [--end] [--show-as] [--category ...] |
[--clear-categories]`. Outcome: only the given fields change; nothing else on the event is touched.

### SC-004: Delete an event
Trigger: `cal delete <id>`. Outcome: the event is removed from the calendar.

### SC-005: Accept an invitation
Trigger: `cal accept <id>`. Outcome: the event is marked accepted; the organizer receives no
response email.

## 6. Functional Requirements

| ID | Requirement (EARS) | Scenario | Evidence |
|---|---|---|---|
| FR-001 | WHEN the operator lists events for a start/end window THE system SHALL return up to 50 overlapping events ordered by start time, displayed in the requested time zone (default Europe/Paris) | SC-001 | `src/services/calendar.py:30-46` |
| FR-002 | IF more than 50 events overlap the requested window THEN THE system SHALL silently return only the first 50 | SC-001 | `src/services/calendar.py:31` |
| FR-003 | WHEN the operator creates an event THE system SHALL include only the fields explicitly given (location, body, attendees, show-as, categories are omitted entirely when not provided, rather than sent empty) | SC-002 | `src/models.py:205-219` |
| FR-004 | WHEN the operator adds attendees to a new event THE system SHALL add every one as a required attendee; the tool has no concept of an optional attendee | SC-002 | `src/models.py:212-215` |
| FR-005 | IF the operator gives a free/busy status outside the accepted set (free, tentative, busy, oof, workingElsewhere, unknown, away) THEN THE system SHALL reject the event before any network call | SC-002 | `src/models.py:174,191-196` |
| FR-006 | WHEN the operator updates an event THE system SHALL change only the fields explicitly given and leave every other field untouched | SC-003 | `src/services/calendar.py:58-64`, `src/outlook_tool.py:620-625` |
| FR-007 | IF `cal update` is called with no field to change THEN THE system SHALL reject the command, exit code 2, no network call | SC-003 | `src/outlook_tool.py:633-637` |
| FR-008 | IF `cal update` is given both `--category` and `--clear-categories` THEN THE system SHALL reject the command, exit code 2, no network call | SC-003 | `src/outlook_tool.py:613-616` |
| FR-009 | WHEN the operator deletes an event by id THE system SHALL remove it | SC-004 | `src/services/calendar.py:66-70` |
| FR-010 | WHEN the operator accepts a meeting invitation THE system SHALL mark it accepted and SHALL NOT send a response email to the organizer | SC-005 | `src/services/calendar.py:72-77` |

## 7. Non-Functional Requirements

None observed beyond what is already functional (the 50-event cap and the time-zone default are
themselves observable behaviors, captured in FR-001/FR-002).

## 8. End-to-End Tests

| ID | Covers | Test | Level | State |
|---|---|---|---|---|
| E2E-001 | FR-001 | `tests/test_calendar.py::test_list_events` | unit (mocked Graph) | green |
| E2E-002 | FR-003 | `tests/test_calendar.py::test_create_event`, `test_create_event_with_show_as`, `test_create_event_with_categories`, `test_create_event_without_categories_omits_field` | unit | green |
| E2E-003 | FR-004 | `tests/test_models.py::test_calendar_event_input_graph` | unit | green |
| E2E-004 | FR-006 | `tests/test_calendar.py::test_update_event`, `test_update_event_show_as`, `test_update_event_categories` | unit | green |
| E2E-005 | FR-007 | `tests/test_cli.py::test_cal_update_requires_change` | integration (CLI) | green |
| E2E-006 | FR-008 | `tests/test_cli.py::test_cal_update_category_and_clear_conflict` | integration (CLI) | green |
| E2E-007 | FR-009 | `tests/test_calendar.py::test_delete_event` | unit | green |
| E2E-008 | FR-010 | `tests/test_calendar.py::test_accept_event`, `tests/test_cli.py::test_cal_accept_command` | unit + integration | green |
| E2E-009 | FR-002 | untested | | |
| E2E-010 | FR-005 | untested | | |

## 9. Glossary

- **calendarView**: the Graph endpoint used to list events overlapping a time window (as opposed
  to `/events`, which lists by creation, not occurrence).

## 10. Confidence notes

- FR-002 (the 50-event cap) is implemented (`top: int = 50` with no pagination/`@odata.nextLink`
  handling) but no test exercises more than 50 events; marked `untested` (E2E-009) and filed to
  backlog as a finding (silent data loss above 50 events in a window).
- FR-005 (show-as validation) is implemented via a pydantic validator but no test supplies an
  invalid value to confirm the rejection path; marked `untested` (E2E-010).
- Recurring events are not described as a requirement because no code path accepts a `recurrence`
  field anywhere in `CalendarEventInput`/`to_graph_event` (`src/models.py:175-221`); this is an
  absence, not a described-but-broken behavior, so it belongs in the backlog (missing capability
  claim check) rather than as a spec requirement.
- Confidence is high: every requirement cites lines read directly.
