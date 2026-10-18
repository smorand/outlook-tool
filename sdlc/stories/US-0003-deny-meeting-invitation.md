# US-0003: Deny a meeting invitation with confirmation

> Spec: SPEC-0005 (sdlc/specs/SPEC-0005-calendar-deny/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

An operator cannot refuse an invitation from the tool. This story adds `cal deny <id>`, which
declines an invitation (accepted or unanswered) without emailing the organizer, then re-checks the
event and prints the resulting state, exactly as `cal accept` does.

## Requirements covered

> Scenarios: SPEC-0005/SC-001, SPEC-0005/SC-002.

- SPEC-0005/FR-NEW-001: WHEN the operator denies a meeting invitation, whether already accepted or not yet answered, THE calendar SHALL record it as declined and SHALL NOT send a response email to the organizer.
- SPEC-0005/FR-NEW-002: WHEN a deny succeeds THE calendar SHALL re-check the event and print `Declined event id=<id> (confirmed status: <state>)`.
- SPEC-0005/FR-NEW-003: IF the re-check fails THEN THE calendar SHALL still report success and print `Declined event id=<id> (status could not be confirmed)`.
- SPEC-0005/FR-NEW-004: IF the id matches no event the operator can see, or the operation is refused, or no id is given, THEN THE calendar SHALL fail with a non-zero exit, SHALL print no success message and SHALL NOT re-check the event.

## Independent Test

`make check` green, and `tests/test_cli.py -k "cal_deny"` shows `cal deny E1` printing `Declined event id=E1 (confirmed status: Declined)` where the status comes from a separately mocked GET route (`cal get E1` and `cal list` read it through other routes), while all pre existing accept tests pass unmodified.

## Design excerpt
### Decisions
- DEC-002 (SPEC-0005): Share one private response method between accept and deny, and one CLI message helper. No duplication.
- DEC-003 (SPEC-0005): Decline via `POST /me/events/{id}/decline` with `{"sendResponse": false}`.
- DEC-004 (SPEC-0005): Unknown id, Graph refusal, missing id fail like accept: `GraphError` propagates (non zero exit), Typer usage error exit 2.
### Contracts
- `CalendarService.deny_event(self, event_id: str) -> str | None`; `accept_event` signature unchanged.
- Private `async def _respond_to_invitation(self, event_id: str, action: str) -> str | None`: inside `trace_span(f"calendar.{action}", attributes={"event.id": event_id})` POST `/me/events/{event_id}/{action}` with `json={"sendResponse": False}`; then `try: event = await self.get_event(event_id)` `except GraphError: return None`; return `event.response_status`. `accept_event` calls it with `"accept"`, `deny_event` with `"decline"`.
- CLI `cal deny <event_id>`, prints with rich console `[green]Declined[/green] event id=<id> (confirmed status: <label>)` or `... (status could not be confirmed)`. Extract the accept printing at `src/outlook_tool.py:696-700` into a helper taking the verb (`Accepted` / `Declined`) so accept output stays byte identical.
### Paths
| Path | Action |
|---|---|
| `src/services/calendar.py` | modify |
| `src/outlook_tool.py` | modify |
| `tests/test_calendar.py` | modify |
| `tests/test_cli.py` | modify |
### Existing patterns
Mirror `cal_accept` (`src/outlook_tool.py:690-701`), `accept_event` (`src/services/calendar.py:79-89`), and the accept tests (`tests/test_cli.py:732-800`, `tests/test_calendar.py:176-197`), including the helper `_graph_event` and the `GRAPH` constant.

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.

All in `tests/test_cli.py` (functional e2e, `CliRunner` + `respx.mock`), under a `# cal deny` section; event GET routes use `url__regex=rf"{GRAPH}/me/events/<id>\?.*"`.

### SPEC-0005/E2E-001: Deny an unanswered invitation
- Given POST `/me/events/E1/decline` returns 202 and GET E1 returns `responseStatus {"response": "declined"}`
- When `cal deny E1`; Then exit 0, stdout contains `Declined event id=E1 (confirmed status: Declined)` and not `could not be confirmed`.
### SPEC-0005/E2E-002: Deny an accepted event
- Given GET E2 returns declined after the POST; When `cal deny E2`; Then stdout contains `Declined event id=E2 (confirmed status: Declined)`, exit 0.
### SPEC-0005/E2E-003: Unknown id
- Given POST `/me/events/E96/decline` returns 404 and a GET route that must stay uncalled; When `cal deny E96`; Then exit non zero, stdout has neither `confirmed status` nor `could not be confirmed`, GET route `.called` is False.
### SPEC-0005/E2E-004: Re-check fails
- Given POST E97 returns 202 and GET E97 returns 500; When `cal deny E97`; Then exit 0, stdout contains `Declined event id=E97 (status could not be confirmed)`.
### SPEC-0005/E2E-005: Operation refused
- Given POST E95 returns 403; When `cal deny E95`; Then exit non zero, stdout does not contain `Declined event id=`, GET route not called.
### SPEC-0005/E2E-006: No email to the organizer
- Given POST E1 mocked; When `cal deny E1`; Then `json.loads(route.calls.last.request.content) == {"sendResponse": False}`.
### SPEC-0005/E2E-007: Already declined
- Given GET E3 returns declined; When `cal deny E3`; Then stdout contains `Declined event id=E3 (confirmed status: Declined)`, exit 0.
### SPEC-0005/E2E-008: Unrecognised state on re-check
- Given GET E4 returns `responseStatus {"response": "somethingNew"}`; When `cal deny E4`; Then stdout contains `Declined event id=E4 (confirmed status: Not yet responded)`, exit 0.
### SPEC-0005/E2E-009: Listing after deny
- Given POST E2 mocked, GET E2 returns declined, and the calendarView route returns E2 with declined; When `cal deny E2`, `cal get E2`, `cal list --start ... --end ...`; Then the last two outputs contain `Declined`.
### SPEC-0005/E2E-010: Re-check fails on an accepted event
- Given GET E5 returns 500 after POST 202; When `cal deny E5`; Then exit 0 and stdout contains `Declined event id=E5 (status could not be confirmed)`.
### SPEC-0005/E2E-011: No id
- When `cal deny` with no argument; Then exit code is 2 (usage error), and no HTTP route was called.

Also add in `tests/test_calendar.py` two unit tests: `deny_event` returns `"Declined"` and posts `{"sendResponse": False}` to `/me/events/E1/decline`; returns `None` when the re-fetch raises GraphError.

## Constraints
- Files not to touch: `src/skill.md`, `README.md`, `AGENTS.md` (US-0004); existing accept tests.
- Dependencies not to add: any.
- Patterns to avoid: copy pasting `accept_event`; changing accept strings or body.
- Scope boundary: tentative accept (BL-0019), a notify flag, multi event deny.

## Definition of done
- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: all existing accept tests pass unmodified; accept output and body unchanged.
- [ ] Docs: none in this story (US-0004).
- [ ] Self review: duplication removed, mypy strict clean, log calls use `%`.
- [ ] One commit `US-0003: Deny a meeting invitation with confirmation`, body `Spec: SPEC-0005` and FR-NEW-001..004.
