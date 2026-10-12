# Platform, Authentication & Skill: Specification (as-built)

> Id: SPEC-0001
> Nature: FEAT
> Status: as-built
> Area: CLI, Auth, Config, GraphClient, Skill
> Generated on: 2026-10-12 by /sdlc-retro-spec at 6956ac5
> Confidence: high

## 1. Summary

Lets an operator authenticate once against Microsoft Graph with no app registration or client
secret, then run every other command non-interactively until the session is revoked. Provides
shared cross-cutting behavior for every command: verbosity control, always-on log files, error
reporting on an expired session, and version reporting. Also lets an AI agent retrieve the tool's
usage instructions, including rules the operator has taught it, so it can operate the CLI correctly.

## 2. Current State

### 2.1 How it works today

The operator runs `login`, which starts a device code flow: the tool prints a verification URL and
a short code, opens the default browser, and waits for the operator to approve in the browser. Once
approved, a session (access + refresh token) is stored on disk, readable only by the owner. Every
subsequent command reuses that session silently; if it has expired, it is refreshed silently without
another login. If no usable session exists, any command that needs Graph fails with a clear message
telling the operator to run `login` first, rather than a raw network error.

By default every command is silent except for errors; `-v` shows informational progress, `-vv` shows
debug detail. Regardless of the console verbosity, a detailed log file and a trace file are always
written to a local directory so a problem can be diagnosed after the fact.

`skill` prints the tool's embedded usage manual (intended for an AI agent driving the CLI), followed
by any personal rule the operator has previously recorded. `skill learn --rule <text>` records a new
rule, timestamped, for future invocations of `skill` to include. `version` prints the installed
version string.

### 2.2 Existing specifications governing this area

None (first as-built pass, no prior spec existed for this repository).

### 2.3 Existing test coverage

121 tests pass repository-wide (`make check`, baseline run, exit 0, coverage 94.43%). For this area:
7 tests in `tests/test_auth.py`, 6 in `tests/test_config.py`, 2 in `tests/test_graph_client.py`,
5 in `tests/test_logging.py`, 4 in `tests/test_tracing.py`, 4 skill tests and several CLI-wiring
tests in `tests/test_cli.py`. No test is currently red. No requirement in this spec is untested.

## 3. Scope

### 3.1 Covered by this spec

Login/device-code flow, session cache and refresh, "session expired" error path, CLI-wide verbosity
and logging, version reporting, the `skill` and `skill learn` commands.

### 3.2 Not covered

Mail operations (SPEC-0002). Calendar operations (SPEC-0003). The content of the usage manual itself
is not restated here (it is operator/agent-facing text, not a contract).

## 4. Actors

- **Operator**: the person running the CLI interactively or via a script.
- **AI agent**: an automated caller driving the CLI on the operator's behalf, consuming `skill`.

## 5. Usage Scenarios

### SC-001: First-time login
Actor: Operator. Trigger: runs `login` with no prior session. Steps: tool requests a device code,
shows a URL and code, opens the browser, polls until the operator approves. Outcome: a session is
stored on disk and a confirmation is printed.

### SC-002: Silent reuse across runs
Actor: Operator. Trigger: runs any Graph-backed command after a prior successful login. Outcome: no
browser interaction; the stored session is reused, refreshed first if it had expired.

### SC-003: Expired, unrefreshable session
Actor: Operator. Trigger: runs any Graph-backed command with no stored session, or a refresh that
Microsoft rejects. Outcome: command fails with a message instructing to run `login`, exit code 2,
no stack trace.

### SC-004: Diagnosing a problem after the fact
Actor: Operator. Trigger: ran a command without `-v`/`-vv` and later wants detail. Outcome: a log
file and a trace file on disk contain the full detail regardless of what was shown on screen.

### SC-005: Agent learns usage
Actor: AI agent. Trigger: runs `skill`. Outcome: receives the embedded manual plus any operator-
recorded rules, so it can operate the CLI correctly without separate documentation.

### SC-006: Operator teaches a rule
Actor: Operator. Trigger: runs `skill learn --rule "<text>"`. Outcome: the rule is appended, with a
timestamp, to a personal file; future `skill` invocations include it.

## 6. Functional Requirements

| ID | Requirement (EARS) | Scenario | Evidence |
|---|---|---|---|
| FR-001 | WHEN the operator runs `login` THE system SHALL request a device code, print the verification URL and user code, and open the default browser to that URL | SC-001 | `src/outlook_tool.py:111-121`, `src/auth.py:117-120` |
| FR-002 | WHEN the device code flow is pending approval THE system SHALL keep polling until the operator approves, respecting a server-requested slow-down, and SHALL give up with an error after a fixed deadline | SC-001 | `src/auth.py:138-156` |
| FR-003 | WHEN a login completes THE system SHALL store the session on disk readable only by its owner and SHALL print a confirmation | SC-001 | `src/outlook_tool.py:111-121`, `src/auth.py:196-201` |
| FR-004 | WHEN a command needs Graph access and a stored session is still valid THE system SHALL reuse it without any network call to the identity provider | SC-002 | `src/auth.py:88-93` |
| FR-005 | WHEN a command needs Graph access and the stored session has expired but carries a refresh capability THE system SHALL silently obtain a new session without operator interaction | SC-002 | `src/auth.py:94-97`, `src/auth.py:148-156` |
| FR-006 | WHEN a session is refreshed and the identity provider does not return a new refresh capability THE system SHALL keep using the previous one | SC-002 | `src/auth.py:163-165` |
| FR-007 | IF no usable session exists and none can be obtained THEN THE system SHALL fail the command with a message instructing the operator to run `login`, exit code 2, and no raw exception | SC-003 | `src/outlook_tool.py:57-63`, `src/auth.py:98` |
| FR-008 | IF a refresh attempt is rejected THEN THE system SHALL fail the command the same way as FR-007 | SC-003 | `src/auth.py:160` |
| FR-009 | WHEN the stored session file is unreadable or corrupted THE system SHALL treat it as absent (requiring login) rather than crashing | SC-003 | `src/auth.py:184-190` |
| FR-010 | WHEN no verbosity flag is given THE system SHALL show only errors on screen | SC-004 | `src/outlook_tool.py:72-77`, `src/logging_config.py:22-27` |
| FR-011 | WHEN `-v` is given THE system SHALL show informational progress on screen; WHEN `-vv` is given THE system SHALL show debug detail on screen | SC-004 | `src/outlook_tool.py:72-77`, `src/logging_config.py:22-27` |
| FR-012 | WHEN any command runs THE system SHALL always write a detailed log file and a trace file to a local directory, regardless of the screen verbosity | SC-004 | `src/logging_config.py:52-55`, `src/tracing.py:76-84` |
| FR-013 | WHEN the operator runs `skill` THE system SHALL print the embedded usage manual followed by every personally recorded rule, each rule's source file identified | SC-005 | `src/skill_cmd.py:57-78` |
| FR-014 | IF a personal rule file cannot be read THEN THE system SHALL skip it with a warning rather than failing the `skill` command | SC-005 | `src/skill_cmd.py:74-76` |
| FR-015 | WHEN the operator runs `skill learn --rule "<text>"` THE system SHALL append the rule with a timestamp to a personal rules file, creating it if absent | SC-006 | `src/skill_cmd.py:80-99` |
| FR-016 | IF `skill learn` is run with an empty rule THEN THE system SHALL fail with exit code 2 and no file change | SC-006 | `src/skill_cmd.py:89-91` |
| FR-017 | WHEN the operator runs `version` THE system SHALL print the installed version string, or `dev` when none is available | - | `src/outlook_tool.py:104-106`, `src/version.py:9-12` |

## 7. Non-Functional Requirements

- A session file, once written, is only readable by its owner (observable via filesystem
  permissions after `login`). Evidence: `src/auth.py:197-201`.
- A command never emits the session's secret material to the console or the default-level log; it
  is only ever persisted to the session file. Evidence: `src/logging_config.py:70-73` (noisy HTTP
  libraries forced quiet to avoid leaking upload-session URLs/tokens at info level).

## 8. End-to-End Tests

| ID | Covers | Test | Level | State |
|---|---|---|---|---|
| E2E-001 | FR-001, FR-002, FR-003, SC-001 | `tests/test_auth.py::test_login_device_code_flow` | unit (mocked HTTP) | green |
| E2E-002 | FR-001, FR-003, SC-001 | `tests/test_cli.py::test_login_command` | integration (CLI, mocked HTTP) | green |
| E2E-003 | FR-004, SC-002 | `tests/test_auth.py::test_get_access_token_uses_valid_cache` | unit | green |
| E2E-004 | FR-005, FR-006, SC-002 | `tests/test_auth.py::test_refresh_when_expired` | unit | green |
| E2E-005 | FR-007, SC-003 | `tests/test_auth.py::test_get_access_token_requires_login_when_empty` | unit | green |
| E2E-006 | FR-007, SC-003 | `tests/test_cli.py::test_login_required_without_cache` | integration (CLI) | green |
| E2E-007 | FR-008, SC-003 | `tests/test_auth.py::test_refresh_failure_raises_login_required` | unit | green |
| E2E-008 | FR-003, FR-009 | `tests/test_auth.py::test_store_and_load_cache_roundtrip` | unit | green |
| E2E-009 | FR-010, FR-011 | `tests/test_logging.py::test_level_for_verbosity_mapping`, `test_setup_logging_default_is_error`, `test_setup_logging_vv_sets_debug` | unit | green |
| E2E-010 | FR-012 | `tests/test_logging.py::test_setup_logging_writes_file_at_info`, `tests/test_tracing.py::test_trace_span_writes_jsonl` | unit | green |
| E2E-011 | FR-013, SC-005 | `tests/test_cli.py::test_skill_prints_embedded`, `test_skill_includes_user_knowledge` | integration (CLI) | green |
| E2E-012 | FR-015, SC-006 | `tests/test_cli.py::test_skill_learn_appends_rule` | integration (CLI) | green |
| E2E-013 | FR-016, SC-006 | `tests/test_cli.py::test_skill_learn_requires_rule` | integration (CLI) | green |
| E2E-014 | FR-017 | `tests/test_cli.py::test_version` | integration (CLI) | green |
| E2E-015 | FR-009 | untested | | |
| E2E-016 | FR-014 | untested | | |

## 9. Glossary

- **Session**: the access token plus refresh token pair cached on disk after `login`.
- **Device code flow**: the OAuth2 flow where the CLI shows a code the operator enters in a browser,
  used because the CLI has no way to host a redirect URI.

## 10. Confidence notes

- FR-009 and FR-014 (graceful handling of an unreadable cache/rule file) are implemented but have no
  dedicated test exercising the failure branch; marked `untested` (E2E-015, E2E-016) rather than
  invented. Filed to backlog as part of the untested-requirements entry for this spec.
- The skill manual's content (`src/skill.md`) is operator/agent-facing prose, not restated as
  requirements here; only the mechanism that serves it (FR-013/FR-014) is in scope.
- Confidence is high: every requirement has a direct, self-read citation; no behavior was inferred
  from the subagent summary alone without opening the cited lines.
