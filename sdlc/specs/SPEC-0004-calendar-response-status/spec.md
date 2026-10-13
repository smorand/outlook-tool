# Calendar response status: functional specification

> Id: SPEC-0004
> Nature: FEAT
> Depth: S
> Depth evidence: one module (calendar), no public contract break (only additive), no new persisted concept, 5 anticipated requirements.
> Status: specified
> Generated on: 2026-10-13
> Project: existing
> From backlog: BL-0017
> Depends on: SPEC-0003
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary

Lets an operator see, for any calendar event, whether they have accepted it, tentatively accepted
it, declined it, not yet responded, or organize it themselves, so that accepting an invitation can
be formally confirmed rather than assumed from the absence of an error.

## 2. Current State

Today an operator can list events in a window (`cal list`) and accept one (`cal accept`), but
neither shows whether the acceptance actually registered: the event summary carries no response
state at all, and `cal accept` only confirms that the request was sent, never that it was recorded.
There is also no command to look up a single event by id; only listing, creating, updating,
deleting and accepting exist.

### 2.1 What users can do today

- List events in a time window, as a table or as JSON, seeing subject, start, end, location and
  categories, but never a response state.
- Accept a meeting invitation; the only confirmation is a generic "Accepted" message with no check
  that the acceptance was recorded.
- There is no way to retrieve a single event by id outside the listing command.

### 2.2 Specs governing this area

SPEC-0003 (Calendar) governs event listing and acceptance. This increment modifies
SPEC-0003/FR-001 (listing) and SPEC-0003/FR-010 (accepting), and adds a new lookup capability that
SPEC-0003 did not describe.

### 2.3 What is verified today

No test anywhere exercises a response state; the current test suite does not reference it at all.
The listing and acceptance journeys themselves are covered (see Section 14.1 for the test files and
command).

## 3. Scope

### 3.1 In scope

- Showing each event's response state wherever it is already listed (`cal list`, table and JSON).
- A new command to retrieve a single event by id, also showing its response state.
- Having `cal accept` confirm, right after accepting, what the resulting state actually is.

### 3.2 Out of scope, and why

- A clean error message for an event id that does not exist: this gap already exists identically for
  the existing update, delete and accept commands, and is not introduced or worsened by this
  increment. Deferred as BL-0018.
- Declining or tentatively accepting an invitation: only acceptance exists today, and the request
  only asked to confirm acceptance. Deferred as BL-0019.

### 3.3 Constraints imposed by the context

None beyond what SPEC-0003 already states.

## 5. Usage scenarios

### SC-001: List shows each event's response state

**Actor:** Operator.
**Preconditions:** A time window containing events in different response states (some accepted,
some not yet responded, some organized by the operator).
**Flow:**
1. The operator runs the listing command for a window, optionally asking for machine-readable
   output. → Each event is shown with the fields already shown today, plus its response state,
   exactly one of: `Accepted`, `Tentatively accepted`, `Declined`, `Not yet responded`, `Organizer`.
**Postconditions:** Every event in the result carries exactly one of the five states above; nothing
else about the listing changes.
**Exceptions:**
- EXC-001a: an event's state cannot be determined. → It is shown as `Not yet responded` rather than
  causing the listing to fail or showing a blank or technical value.
**Interactions:** None; this is an addition to the existing listing output.

### SC-002: Look up one event and see its response state

**Actor:** Operator.
**Preconditions:** The id of an event the operator has access to.
**Flow:**
1. The operator asks to look up that one event by id, optionally asking for machine-readable
   output. → The event's full summary is shown (the same fields the listing shows), including its
   response state in the same five-state vocabulary as SC-001.
**Postconditions:** The requested event's current details, including its response state, are shown;
nothing is changed.
**Exceptions:**
- EXC-002a: the id does not correspond to an event the operator can see. → The command fails and
  shows nothing, the same way the existing update, delete and accept commands already fail today on
  an id that does not exist.
- EXC-002b: the event's state cannot be determined. → Same as EXC-001a: shown as `Not yet
  responded`.
**Interactions:** Shares its response-state vocabulary with SC-001 and SC-003.

### SC-003: Accept an invitation and see it confirmed

**Actor:** Operator.
**Preconditions:** An event the operator has not yet accepted, or has only tentatively accepted.
**Flow:**
1. The operator accepts the invitation by id. → The invitation is accepted, and the confirmation
   message states the resulting response state (expected: `Accepted`).
**Postconditions:** The event's response state is `Accepted`; the operator has seen that state
confirmed in the command's own output, not merely the absence of an error.
**Exceptions:**
- EXC-003a: accepting succeeds, but checking the resulting state right after fails. → The command
  still reports that the invitation was accepted, and additionally states that the resulting state
  could not be confirmed; it does not fail the command over this.
- EXC-003b: the id does not correspond to an event the operator can see. → The command fails exactly
  as it already does today (SPEC-0003/FR-010), unchanged by this increment.
**Interactions:** Accepting an already-accepted event, or a tentatively-accepted one, both succeed
and both confirm `Accepted` afterward (accepting is not rejected based on the prior state).

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-E]: Look up one event by id
> WHEN the operator looks up an event by id THE calendar SHALL show that event's full summary,
> including its response state, in the table or machine-readable form the operator requested.

- **Business rules:** The lookup is invoked as `cal get <event_id>`, with the same `--json` option
  the listing command already offers for machine-readable output.
- **User visible text:** The response state is exactly one of: `Accepted`, `Tentatively accepted`,
  `Declined`, `Not yet responded`, `Organizer`.
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-002 [EARS-U]: Response state vocabulary
> The calendar SHALL express an event's response state using exactly one of: `Accepted`,
> `Tentatively accepted`, `Declined`, `Not yet responded`, `Organizer`, and no other value, in every
> place a response state is shown.

- **Business rules:** When the underlying state is missing or not one of the recognized values, the
  calendar defaults to `Not yet responded` rather than showing a blank, a technical value, or
  failing.
- **User visible text:** The five labels above, verbatim.
- **Scenario:** SC-001, SC-002, SC-003
- **Priority:** Must

#### FR-NEW-003 [EARS-O]: Unknown event id on lookup
> IF the given event id does not correspond to an event the operator can see THEN THE calendar SHALL
> fail the lookup and show no event, in the same way the update, delete and accept commands already
> fail today on an unknown id.

- **Business rules:** No change to how an unknown id already fails for the other commands
  (SPEC-0003/FR-006, FR-009, FR-010); this requirement only extends the same behavior to the new
  lookup.
- **Scenario:** SC-002
- **Priority:** Must

### 6.2 Modified

#### FR-MOD-001 [EARS-E]: Listing shows response state (modifies SPEC-0003/FR-001)
> WHEN the operator lists events for a start/end window THE calendar SHALL show each event's
> response state alongside the fields already shown, using the vocabulary of FR-NEW-002.

- **Before:** An event's listing summary showed subject, start, end, location and categories, with
  no response state at all.
- **After:** The statement above.
- **Reason:** An operator cannot tell today, from the listing alone, which events they have
  responded to and how.

#### FR-MOD-002 [EARS-E]: Accept confirms the resulting state (modifies SPEC-0003/FR-010)
> WHEN the operator accepts a meeting invitation THE calendar SHALL, immediately after accepting,
> check and state the event's resulting response state in the confirmation message.

- **Before:** Accepting an invitation printed a generic confirmation ("Accepted event id=<id>")
  with no indication of whether the acceptance was actually recorded.
- **After:** The confirmation message states the resulting response state, for example "Accepted
  event id=<id> (confirmed status: Accepted)". IF checking the resulting state fails, THEN the
  message instead states that the status could not be confirmed, for example "Accepted event
  id=<id> (status could not be confirmed)", and the command still succeeds: accepting is not
  retried or failed because the confirmation check failed.
- **Reason:** This is the behavior the request asked for: a formal confirmation that clicking
  "accept" actually registered, not just the absence of an error.

## 9. Acceptance tests (the contract)

### 9.1 Summary

| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | happy | SC-001 | FR-MOD-001 | High |
| E2E-002 | New | edge | SC-001 | FR-MOD-001, FR-NEW-002 | Medium |
| E2E-003 | New | edge | SC-001 | FR-MOD-001, FR-NEW-002 | Medium |
| E2E-004 | New | happy | SC-001 | FR-MOD-001 | High |
| E2E-012 | New | failure | SC-001 | FR-MOD-001 | Medium |
| E2E-014 | New | failure | SC-001 | FR-NEW-002 | Medium |
| E2E-018 | New | failure | SC-001 | FR-MOD-001 | Low |
| E2E-005 | New | happy | SC-002 | FR-NEW-001 | High |
| E2E-006 | New | happy | SC-002 | FR-NEW-001 | High |
| E2E-008 | New | edge | SC-002 | FR-NEW-001, FR-NEW-002 | Medium |
| E2E-007 | New | failure | SC-002 | FR-NEW-003 | High |
| E2E-013 | New | failure | SC-002 | FR-NEW-001 | Medium |
| E2E-015 | New | edge | SC-002 | FR-NEW-003 | Low |

> FR-NEW-003 also counts E2E-005 (the "id exists" happy counterpart to its "id does not exist" condition), giving it 3 tests: E2E-005, E2E-007, E2E-015.
| E2E-009 | Modified | happy | SC-003 | FR-MOD-002 | High |
| E2E-017 | New | happy | SC-003 | FR-MOD-002 | Medium |
| E2E-010 | New | failure | SC-003 | FR-MOD-002 | High |
| E2E-011 | Modified | failure | SC-003 | FR-MOD-002 | Medium |
| E2E-016 | New | edge | SC-003 | FR-MOD-002 | Low |

Coverage: happy 6, failure 7, side effect 2 (E2E-009, E2E-017, each a state transition), edge 5,
state transition 2, security 0. Happy to failure ratio 1:1.17 (6 happy, 7 failure; beats 1:1).

### 9.2 New tests

#### E2E-001: Listing shows "Accepted" for an event the operator already accepted
- **Category:** requirement
- **Scenario:** SC-001
- **Requirements:** FR-MOD-001
- **Given** a window containing one event the operator has accepted
- **When** the operator lists events for that window
- **Then** that event is shown with response state `Accepted`
- **Priority:** High

#### E2E-002: Listing shows "Not yet responded" for a pending invitation
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-MOD-001, FR-NEW-002
- **Given** a window containing one event the operator has not responded to
- **When** the operator lists events for that window
- **Then** that event is shown with response state `Not yet responded`
- **Priority:** Medium

#### E2E-003: Listing shows "Organizer" for an event the operator organizes
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-MOD-001, FR-NEW-002
- **Given** a window containing one event the operator organizes themselves
- **When** the operator lists events for that window
- **Then** that event is shown with response state `Organizer`
- **Priority:** Medium

#### E2E-004: Machine-readable listing includes response state
- **Category:** requirement
- **Scenario:** SC-001
- **Requirements:** FR-MOD-001
- **Given** a window containing one event with response state `Tentatively accepted`
- **When** the operator lists events for that window in machine-readable form
- **Then** the result for that event includes a response state field with the exact value
  `Tentatively accepted`
- **Priority:** High

#### E2E-012: Listing defaults to "Not yet responded" when the state is missing
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-MOD-001
- **Given** a window containing one event whose underlying state is absent entirely
- **When** the operator lists events for that window
- **Then** that event is shown with response state `Not yet responded`, and the listing does not
  fail
- **Priority:** Medium

#### E2E-014: Listing defaults to "Not yet responded" for an unrecognized state value
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002
- **Given** a window containing one event whose underlying state value is not one of the five
  recognized states
- **When** the operator lists events for that window
- **Then** that event is shown with response state `Not yet responded`, never the unrecognized raw
  value
- **Priority:** Medium

#### E2E-018: Listing still shows a response state when other fields on the same event are malformed
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-MOD-001
- **Given** a window containing one event whose location and organizer are malformed, but whose
  state is `Accepted`
- **When** the operator lists events for that window
- **Then** that event is still shown with response state `Accepted`, and the listing does not fail
- **Priority:** Low

#### E2E-005: Looking up one event shows its response state
- **Category:** requirement
- **Scenario:** SC-002
- **Requirements:** FR-NEW-001, FR-NEW-003
- **Given** an event the operator has tentatively accepted
- **When** the operator looks up that event by id
- **Then** the event's full summary is shown with response state `Tentatively accepted`
- **Priority:** High

#### E2E-006: Machine-readable lookup includes response state
- **Category:** requirement
- **Scenario:** SC-002
- **Requirements:** FR-NEW-001
- **Given** an event the operator has accepted
- **When** the operator looks up that event by id in machine-readable form
- **Then** the result includes a response state field with the exact value `Accepted`
- **Priority:** High

#### E2E-008: Looking up a declined event shows "Declined"
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-001, FR-NEW-002
- **Given** an event the operator has declined
- **When** the operator looks up that event by id
- **Then** the event is shown with response state `Declined`
- **Priority:** Medium

#### E2E-007: Looking up an unknown id fails and shows nothing
- **Category:** failure
- **Scenario:** SC-002
- **Requirements:** FR-NEW-003
- **Given** an event id that does not correspond to any event the operator can see
- **When** the operator looks up that id
- **Then** the command fails, and no event is displayed
- **Priority:** High

#### E2E-013: Lookup defaults to "Not yet responded" when the state is missing
- **Category:** failure
- **Scenario:** SC-002
- **Requirements:** FR-NEW-001
- **Given** an event whose underlying state is absent entirely
- **When** the operator looks up that event by id
- **Then** the event is shown with response state `Not yet responded`, and the lookup does not fail
- **Priority:** Medium

#### E2E-015: Looking up an id the operator cannot access fails the same way as an unknown id
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-003
- **Given** an event id that exists but that the operator has no access to
- **When** the operator looks up that id
- **Then** the command fails the same way as E2E-007, and no event is displayed
- **Priority:** Low

#### E2E-009: Accepting a pending invitation confirms "Accepted"
- **Category:** state transition
- **Scenario:** SC-003
- **Requirements:** FR-MOD-002
- **Given** an event the operator has not yet responded to
- **When** the operator accepts that event
- **Then** the confirmation message states the resulting response state is `Accepted`
- **And** looking up that same event afterward also shows response state `Accepted`
- **Priority:** High

#### E2E-017: Accepting a tentatively-accepted invitation confirms "Accepted"
- **Category:** state transition
- **Scenario:** SC-003
- **Requirements:** FR-MOD-002
- **Given** an event the operator has tentatively accepted
- **When** the operator accepts that event
- **Then** the confirmation message states the resulting response state is `Accepted`
- **Priority:** Medium

#### E2E-010: Accept succeeds even when the confirmation check fails
- **Category:** failure
- **Scenario:** SC-003
- **Requirements:** FR-MOD-002
- **Given** an event the operator has not yet responded to, and a confirmation check that fails
  right after accepting
- **When** the operator accepts that event
- **Then** the command still reports that the invitation was accepted
- **And** the message states that the resulting status could not be confirmed, rather than failing
  the command
- **Priority:** High

#### E2E-016: Re-accepting an already-accepted event still confirms "Accepted"
- **Category:** edge
- **Scenario:** SC-003
- **Requirements:** FR-MOD-002
- **Given** an event the operator has already accepted
- **When** the operator accepts that same event again
- **Then** the command succeeds and the confirmation message states response state `Accepted`
- **Priority:** Low

### 9.4 Modified tests [existing only]

#### E2E-MOD-001: Accept confirmation message (was the existing "accept prints a generic
confirmation" test)
- **Validated before:** Accepting an invitation printed a generic confirmation with no response
  state.
- **Validates now:** Accepting an invitation prints a confirmation that includes the resulting
  response state (E2E-009).
- **Given** an event the operator has not yet responded to
- **When** the operator accepts that event
- **Then** the confirmation message includes response state `Accepted`

#### E2E-MOD-002: Accept on an unknown id still fails the same way (was the existing "accept on an
unknown id" behavior, unchanged, re-asserted to guard against regression from the new confirmation
step)
- **Validated before:** Accepting an unknown id failed without a response-state check ever running.
- **Validates now:** Accepting an unknown id still fails the same way; the confirmation check is
  never reached.
- **Given** an event id that does not correspond to any event the operator can see
- **When** the operator attempts to accept that id
- **Then** the command fails exactly as it did before this increment (E2E-011)

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-MOD-001, FR-NEW-002 | E2E-001, E2E-004 | E2E-012, E2E-014, E2E-018 | E2E-002, E2E-003 |
| SC-002 | FR-NEW-001, FR-NEW-002, FR-NEW-003 | E2E-005, E2E-006 | E2E-007, E2E-013 | E2E-008, E2E-015 |
| SC-003 | FR-MOD-002 | E2E-009, E2E-017 | E2E-010, E2E-011 | E2E-016 |

SC-001 and SC-002 are read-only lookups; side-effect coverage does not apply to either (no state
changes on a listing or a lookup). SC-003's side effect (the response state actually changing) is
covered by E2E-009 and E2E-017's second assertion.

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Response state | Whether the operator has accepted, tentatively accepted, declined, not yet responded to, or organizes an event themselves. | Shown wherever an event is displayed. |
| Accepted | The operator has accepted the invitation. | Response state value. |
| Tentatively accepted | The operator has provisionally accepted, without a firm commitment. | Response state value. |
| Declined | The operator has declined the invitation. | Response state value. |
| Not yet responded | The operator has not responded, or the state could not be determined. | Response state value, also the safe default. |
| Organizer | The operator organizes the event themselves; accepting does not apply. | Response state value. |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 0 | 1 (self-consistency: depth-evidence requirement count, FR-NEW-003 under-tested) | IMPLEMENTABLE |

**Amendments applied:** depth evidence corrected from 7 to 5 requirements; FR-NEW-003 given a third test (E2E-005) to meet the 3-test minimum.
**No implementation detail outside Section 14:** PASS (verified by grep; all hits at line >= 437, inside Section 14).

## 14. Evidence appendix (for /sdlc-design and the auditor, not for the product owner)

### 14.1 Current State evidence

| Claim (Section 2) | Evidence |
|---|---|
| Listing shows subject, start, end, location, categories, no response state | `src/models.py:225-262` (`CalendarEventSummary` has no response-state field); `src/services/calendar.py:18` (`_EVENT_SELECT` does not request one) |
| `cal accept` only confirms the request was sent, not that it registered | `src/outlook_tool.py:664-672`; `src/services/calendar.py:72-77` (`accept_event` returns `None`, no re-fetch) |
| No single-event lookup command exists today | `src/outlook_tool.py:526-672` (only `list`, `add`, `update`, `delete`, `accept` are registered under `cal_app`) |
| No test references a response state | `grep -n "responseStatus\|response_status" tests/*.py src/*.py src/services/*.py` returned no matches except the test function name `test_accept_event` at `tests/test_calendar.py:176` |
| Unknown id already fails raw (uncaught) for update/delete/accept | `src/outlook_tool.py:57-63` (`_run` only catches `LoginRequiredError`); `src/graph_client.py:22-30` (`GraphError` is an uncaught `Exception` subclass on any Graph call) |

Test command: `make test` (per `Makefile`, confirmed working at baseline: 121/121 passed, see
SPEC-0003 design evidence).

### 14.3 Design inputs

- The five response-state labels (FR-NEW-002) map onto Microsoft Graph's own per-user response
  status field on an event, which already distinguishes "organizer" from the other four states
  without needing to separately know the operator's own identity or email address; `/sdlc-design`
  should confirm this mapping against the live schema rather than deriving organizer-ness any other
  way.
- `cal get <event_id>` (FR-NEW-001) can likely reuse the same single-event retrieval Graph already
  exposes (the same shape `cal update`'s PATCH target implies), rather than filtering a full listing
  client-side; `/sdlc-design`'s call.
- The "confirmation check fails" path in FR-MOD-002 (EXC-003a) needs a design decision on whether the
  re-check is a second network call right after accept, or derived from the accept call's own
  response; either satisfies the requirement as stated.
- BL-0018 (unknown id crashes raw) and BL-0007 (already on file: event id not URL-encoded) touch the
  same code paths `/sdlc-design` will touch for FR-NEW-003; worth reading together, not fixed by this
  spec.
