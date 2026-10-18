# SPEC-0005: Calendar deny, design

> Spec: sdlc/specs/SPEC-0005-calendar-deny/spec.md
> Nature: FEAT
> Depth: S
> Security: n/a
> Designed on: 2026-10-18
> Target tier: 2 (default, no constitution field, no `.spec.json`)

## 1. Stack and skills
| Element | Choice | Version | DEC |
|---|---|---|---|
| Language, CLI, HTTP, tests | existing: Python 3.13, Typer, httpx async, pytest, respx (`pyproject.toml`) | as locked in `uv.lock` | DEC-001 |

Skills loaded: python. Effect: `make check` gate, no duplicated code, `trace_span` on external calls, `%` log formatting, `typer.echo`/rich console for output. No new dependency, so no context7 lookup.

## 2. Approaches
### Chosen: generalize the accept flow into one private response method
`accept_event` and the new `deny_event` call one shared `_respond_to_invitation(event_id, action)`; the CLI shares one message printer. Pros: zero duplication (python skill), parity with accept guaranteed. Cons: touches the accept code path (guarded by the unmodified accept tests). Scope: `services/calendar.py`, `outlook_tool.py`.
### Rejected: copy `accept_event` as `deny_event`
Duplicates 10 lines and the confirmation logic; violates the zero duplication rule (DEC-002).

## 3. Architecture
`CalendarService` gains `deny_event(event_id) -> str | None`. Both wrappers call `_respond_to_invitation`, which POSTs `/me/events/{id}/{action}` with `{"sendResponse": False}`, then calls `get_event` and returns its `response_status`, or `None` on `GraphError`. The POST failing raises and `get_event` is never reached (existing behavior, `src/services/calendar.py:79-89`). The CLI command `cal deny` mirrors `cal accept` (`src/outlook_tool.py:690-701`).

## 4. Data model
None.

## 5. Contracts and interfaces
- `CalendarService.deny_event(self, event_id: str) -> str | None`; `accept_event` signature unchanged.
- Graph call: `POST /me/events/{event_id}/decline`, body `{"sendResponse": false}`.
- CLI `outlook-tool cal deny <event_id>`; docstring `Deny (decline) a meeting invitation (no response email sent).` A missing id is a Typer usage error, exit 2 (E2E-011).
- Output (rich console, green verb): `Declined event id=<id> (confirmed status: <label>)` or `Declined event id=<id> (status could not be confirmed)`. The accept strings stay byte identical: `Accepted event id=<id> (confirmed status: ...)`.
- Trace span `calendar.decline` with attribute `event.id` (accept keeps `calendar.accept`).

## 6. File structure impact
| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/services/calendar.py` | modify (extract `_respond_to_invitation`, add `deny_event`) | FR-NEW-001..004 | US-0003 |
| `src/outlook_tool.py` | modify (add `cal deny`, shared message helper) | FR-NEW-001..004 | US-0003 |
| `tests/test_calendar.py` | modify (add deny tests) | FR-NEW-001, 003 | US-0003 |
| `tests/test_cli.py` | modify (add E2E-001..011, skill mention test) | all | US-0003, US-0004 |
| `src/skill.md` | modify (tree line and workflow note) | discoverability by agents, BL-0021 | US-0004 |
| `README.md` | modify (command list) | docs rule of the project | US-0004 |
| `AGENTS.md` | modify (`cal add\|list\|update\|delete` line, add `accept\|deny`) | docs rule, BL-0009 | US-0004 |

Affected existing tests: all accept tests keep unmodified (they pin the accept strings and body). Affected docs: the three above.

## 7. Compatibility and risks
No breaking change. Risk: the refactor alters accept; mitigated by the unmodified accept tests (`tests/test_calendar.py:176,191`, `tests/test_cli.py:732-800`). Graph returns 202 for decline as for accept; an event the operator organizes returns an error from Graph, which surfaces as the E2E-005 failure. Rollback: revert the commit.

## 9. Test strategy
| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| E2E-001..011 | functional e2e | `CliRunner` + respx | `tests/test_cli.py` (section `cal deny`) | US-0003 |
| deny service tests (extra, no id) | unit | respx | `tests/test_calendar.py` | US-0003 |
| skill mentions `cal deny` (extra) | functional e2e | `CliRunner` | `tests/test_cli.py` | US-0004 |

E2E-006 automated check is the request body `{"sendResponse": false}`; the mailbox check is manual (`.agent_docs/e2e-testing.md`). Test data: generated inline dicts like the existing accept tests.

## 10. Decisions log
- **DEC-001:** Reuse the existing stack, no new dependency. **Obliged by:** n/a (no code impact): constrains every FR. **Rationale:** the feature is one more Graph call. **Alternatives considered:** none viable. **Source:** existing code `pyproject.toml`. **Evidence:** `src/services/calendar.py:79`.
- **DEC-002:** Share one private response method between accept and deny, and one CLI message helper. **Obliged by:** SPEC-0005/FR-NEW-002, FR-NEW-003 (same confirmation behavior as accept, SPEC-0004/FR-MOD-002). **Rationale:** guarantees parity; python skill forbids duplication. **Alternatives considered:** copy accept. **Source:** design, python skill. **Evidence:** `src/services/calendar.py:79-89`.
- **DEC-003:** Decline via `POST /me/events/{id}/decline` with `{"sendResponse": false}`, which works for both accepted and unanswered invitations. **Obliged by:** SPEC-0005/FR-NEW-001. **Rationale:** same body and semantics as accept, so the no email rule holds. **Alternatives considered:** `tentativelyAccept` (out of scope, BL-0019); PATCH of the response status (not writable in Graph). **Source:** design, accept precedent. **Evidence:** `src/services/calendar.py:82`.
- **DEC-004:** An unknown id, a Graph refusal and a missing id fail as accept does: `GraphError` propagates to the shared error handler, exit non zero; usage error exit 2 from Typer. **Obliged by:** SPEC-0005/FR-NEW-004. **Rationale:** parity with `tests/test_cli.py:787`. **Alternatives considered:** a custom message. **Source:** existing code. **Evidence:** `tests/test_cli.py:787-796`.

## 11. Stories
| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0003 | Deny a meeting invitation with confirmation | P1 | FR-NEW-001, 002, 003, 004 | main | 2 | no |
| US-0004 | Document cal deny for operators and agents | P2 | FR-NEW-001 (discoverability) | US-0003 | 2 | yes |
