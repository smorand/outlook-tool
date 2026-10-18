# Calendar deny: functional specification

> Id: SPEC-0005
> Nature: FEAT
> Depth: S
> Depth evidence: 1 behavior (refuse an invitation), 1 module (calendar), 4 requirements, no persisted change.
> Status: specified
> Generated on: 2026-10-18
> Project: existing
> From backlog: n/a
> Depends on: SPEC-0003, SPEC-0004
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary

An operator can accept a meeting invitation but cannot refuse one. This increment adds the command
`cal deny <id>`, which declines an invitation, whether it was already accepted or not yet answered,
and confirms the resulting state the same way accepting does. No email is sent to the organizer.

## 2. Current State

The operator can accept an invitation without notifying the organizer, and the confirmation states
the resulting response state, or says it could not be confirmed. The calendar already knows a
`Declined` response state. Accepting on an unknown id fails with an error. There is no way to refuse
an invitation from the tool; the operator must use another application.

### 2.1 What users can do today
- `cal accept <id>`: accept, with a confirmation naming the resulting state.
- `cal get <id>` and `cal list`: see each event's response state.

### 2.2 Specs governing this area
- SPEC-0003/FR-010 (accept sends no response email), SPEC-0004/FR-MOD-002 (accept confirms the
  state), SPEC-0004/FR-NEW-002 (state vocabulary). This increment mirrors them for refusal and
  does not modify them.

### 2.3 What is verified today
Accepting is exercised for success, unknown id, failed confirmation and already accepted events.
Nothing exercises refusing, because it does not exist.

## 3. Scope
### 3.1 In scope
- A `cal deny <id>` command with the same confirmation behavior as accepting.
### 3.2 Out of scope, and why
- Tentative acceptance: separate request, stays in BL-0019.
- Sending a response email or a comment to the organizer: not requested; accept sends none either.
- Denying several events at once: not requested.
### 3.3 Constraints imposed by the context
- None.

## 5. Usage scenarios
### SC-001: Deny an invitation not yet answered
**Actor:** operator
**Preconditions:** an invitation exists whose state is `Not yet responded`.
**Flow:**
1. The operator types `cal deny <id>` → the calendar records the refusal, sends nothing to the organizer, re-checks the event and prints the confirmation.
**Postconditions:** the event's state is `Declined`; the organizer received nothing.
**Exceptions:**
- EXC-001a: the id matches no event → the command fails with an error and prints no confirmation.
- EXC-001b: the service refuses the operation (for example the event is not an invitation) → the command fails with an error and prints no success message.
- EXC-001c: the re-check fails → the command still succeeds and says the state could not be confirmed.
- EXC-001d: no id is given → usage error, nothing changes.

### SC-002: Deny a previously accepted event
**Actor:** operator
**Preconditions:** an invitation whose state is `Accepted`.
**Flow:**
1. The operator types `cal deny <id>` → same as SC-001.
**Postconditions:** the state is `Declined`; `cal get` and `cal list` show `Declined`.
**Exceptions:** same as SC-001.
**Interactions:** denying an already declined event leaves it `Declined` and succeeds.

## 6. Functional requirements
### 6.1 New
#### FR-NEW-001 [EARS-E]: Deny an invitation
> WHEN the operator denies a meeting invitation, whether already accepted or not yet answered, THE calendar SHALL record it as declined and SHALL NOT send a response email to the organizer.
- **Business rules:** denying an already declined event succeeds and leaves it declined.
- **Scenario:** SC-001, SC-002
- **Priority:** Must

#### FR-NEW-002 [EARS-E]: Confirm the resulting state
> WHEN a deny succeeds THE calendar SHALL re-check the event and print `Declined event id=<id> (confirmed status: <state>)`, where `<state>` is one of the labels of SPEC-0004/FR-NEW-002.
- **User visible text:** `Declined event id=<id> (confirmed status: Declined)`.
- **Scenario:** SC-001, SC-002
- **Priority:** Must

#### FR-NEW-003 [EARS-O]: Confirmation unavailable
> IF the re-check fails THEN THE calendar SHALL still report success and print `Declined event id=<id> (status could not be confirmed)`.
- **Business rules:** the refusal is not retried and not reported as failed.
- **Scenario:** SC-001, SC-002
- **Priority:** Must

#### FR-NEW-004 [EARS-O]: Refusal not possible
> IF the id matches no event the operator can see, or the operation is refused, or no id is given, THEN THE calendar SHALL fail with a non-zero exit, SHALL print no success message and SHALL NOT re-check the event.
- **Business rules:** same failure behavior as accepting on an unknown id.
- **Scenario:** SC-001
- **Priority:** Must

## 9. Acceptance tests (the contract)
### 9.1 Summary
| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | journey | SC-001 | FR-NEW-001, 002, 003 | Critical |
| E2E-002 | New | journey | SC-002 | FR-NEW-001, 002 | Critical |
| E2E-003 | New | failure | SC-001 | FR-NEW-004 | High |
| E2E-004 | New | failure | SC-001 | FR-NEW-003 | High |
| E2E-005 | New | failure | SC-001 | FR-NEW-004 | High |
| E2E-006 | New | side effect | SC-001 | FR-NEW-001 | High |
| E2E-007 | New | edge | SC-002 | FR-NEW-001 | Medium |
| E2E-008 | New | edge | SC-001 | FR-NEW-002 | Medium |
| E2E-009 | New | state transition | SC-002 | FR-NEW-001, 002 | Medium |
| E2E-010 | New | edge | SC-002 | FR-NEW-003 | Medium |
| E2E-011 | New | failure | SC-001 | FR-NEW-004 | Medium |

Coverage: happy 2, failure 4, side effect 1, edge 3, state transition 1, security 0 (no security surface: no new input is interpreted). Happy to failure ratio 1:2 (failure plus edge 7 against happy 2).

### 9.2 New tests
#### E2E-001: Deny an unanswered invitation
- **Scenario:** SC-001. **Requirements:** FR-NEW-001, 002, 003.
- **Given** an invitation `Team sync` with id `E1` in state `Not yet responded`
- **When** the operator types `cal deny E1`
- **Then** the output is `Declined event id=E1 (confirmed status: Declined)` and the exit is 0
- **And** the output does not contain `could not be confirmed`

#### E2E-002: Deny an accepted event
- **Scenario:** SC-002. **Requirements:** FR-NEW-001, 002.
- **Given** event `E2` in state `Accepted`
- **When** the operator types `cal deny E2`
- **Then** the output is `Declined event id=E2 (confirmed status: Declined)`, exit 0

#### E2E-003: Unknown id
- **Given** no event with id `E96` is visible to the operator
- **When** the operator types `cal deny E96`
- **Then** the exit is non-zero, the output contains neither `confirmed status` nor `could not be confirmed`
- **And** no re-check of the event was made

#### E2E-004: Re-check fails
- **Given** event `E97` is declinable but looking it up afterwards fails
- **When** the operator types `cal deny E97`
- **Then** the output is `Declined event id=E97 (status could not be confirmed)`, exit 0

#### E2E-005: Operation refused
- **Given** event `E95` is a personal event with no invitation, so the service refuses the refusal with a permission error
- **When** the operator types `cal deny E95`
- **Then** the exit is non-zero, the output contains no `Declined event id=`
- **And** no re-check was made

#### E2E-006: No email to the organizer
- **Given** invitation `E1` from `bob@example.com`
- **When** the operator types `cal deny E1`
- **Then** the refusal request carries the instruction not to notify the organizer
- **And** `bob@example.com` receives no mail (observed in the organizer's mailbox in the end to end run)

#### E2E-007: Already declined
- **Given** event `E3` already in state `Declined`
- **When** the operator types `cal deny E3`
- **Then** the output is `Declined event id=E3 (confirmed status: Declined)`, exit 0

#### E2E-008: Unrecognised state on re-check
- **Given** event `E4` whose state after the refusal is reported in a form the calendar does not recognise
- **When** the operator types `cal deny E4`
- **Then** the output is `Declined event id=E4 (confirmed status: Not yet responded)`, exit 0

#### E2E-009: Listing after deny
- **Given** `E2` in state `Accepted`
- **When** the operator types `cal deny E2`, then `cal get E2`, then `cal list` for the day of the event
- **Then** both `cal get` and `cal list` show `Declined` for `E2`

#### E2E-010: Re-check fails on an accepted event
- **Given** event `E5` in state `Accepted`, lookup failing after the refusal
- **When** the operator types `cal deny E5`
- **Then** the output is `Declined event id=E5 (status could not be confirmed)`, exit 0

#### E2E-011: No id
- **Given** any state
- **When** the operator types `cal deny` with no id
- **Then** the exit is non-zero and a usage message is shown
- **And** no event changed

## 10. Traceability
| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, 002, 003, 004 | E2E-001 | E2E-003, 004, 005, 011 | E2E-008 |
| SC-002 | FR-NEW-001, 002, 003 | E2E-002 | E2E-010 | E2E-007, 009 |

Requirement coverage: FR-NEW-001: E2E-001, 002, 006, 007; FR-NEW-002: E2E-001, 002, 008, 009; FR-NEW-003: E2E-001, 004, 010; FR-NEW-004: E2E-003, 005, 011.

## 12. Glossary
| Term | Definition | Context |
|---|---|---|
| Deny | Refuse a meeting invitation so that its state becomes `Declined` | calendar |
| Response state | The operator's answer to an invitation, one of five labels | SPEC-0004/FR-NEW-002 |
| Invitation | An event the operator was invited to by an organizer | calendar |

## 13. Implementability gate
| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 0 | 0 | IMPLEMENTABLE (inline checklist) |

**Amendments applied:** E2E-010 and E2E-011 added to reach 3 tests for FR-NEW-003 and FR-NEW-004.
**No implementation detail outside Section 14:** PASS (the only technical words are the typed commands `cal deny`, `cal get`, `cal list`).

## 14. Evidence appendix
### 14.1 Current State evidence
| Claim (Section 2) | Evidence |
|---|---|
| Accept command, confirmation and fallback messages | `src/outlook_tool.py:690-701` |
| Accept sends no response email | `src/services/calendar.py:82` |
| Accept re-checks the event and returns the state or none | `src/services/calendar.py:79-89` |
| `Declined` label exists, unknown shapes map to `Not yet responded` | `src/models.py:224-238` |
| Unknown id on accept fails, no re-check | `tests/test_cli.py:787-796` |
| Accept tests | `tests/test_calendar.py:176,191`, `tests/test_cli.py:732-800` |
Test command: `make test`

### 14.3 Design inputs
- The refusal endpoint takes the same body as accept, with the notify flag false; mirror `accept_event` and share the confirm step (`src/services/calendar.py:79-89`). Signal: parity tests with accept.
- Update `src/skill.md:62,206-213`, `README.md`, `AGENTS.md` for the new command (see BL-0009, BL-0021).
- E2E-006 second observation (organizer mailbox) is only checkable in the manual end to end protocol (`.agent_docs/e2e-testing.md`); the automated check is the request body.
- E2E-005 relies on the service returning a refusal for a non invitation; confirm the real status during design.
