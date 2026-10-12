# Mail: Specification (as-built)

> Id: SPEC-0002
> Nature: FEAT
> Status: as-built
> Area: Mail
> Generated on: 2026-10-12 by /sdlc-retro-spec at 6956ac5
> Confidence: high

## 1. Summary

Lets an operator send new messages and threaded replies (with or without attachments of any
size), manage drafts, and triage an inbox: list, search, read, flag, mark, move, archive, trash,
and download attachments.

## 2. Current State

### 2.1 How it works today

Sending a message with small or no attachments is a single operation. Once the attachments grow
past a threshold, the tool transparently switches to creating a draft, uploading each large
attachment in chunks, and sending the draft; the operator sees the same `send` command either way.
Replying to a message produces a true threaded reply (correct conversation, "RE: " subject,
citation of the original) rather than a new unrelated message; a custom reply body is added above
the citation, never replacing it. Drafts can be built up over several calls (change the body, add
or remove attachments) before being sent. Listing, searching and reading mail support the usual
triage actions, and an attachment can be downloaded whether Graph returns it inline or requires a
separate fetch.

### 2.2 Existing specifications governing this area

SPEC-0001 governs the authentication and Graph-client plumbing this area depends on; this spec
documents only the mail-specific behavior layered on top.

### 2.3 Existing test coverage

121 tests pass repository-wide (baseline `make check`, exit 0, 94.43% coverage). Mail-specific:
29 tests in `tests/test_mail.py`, 8 model tests in `tests/test_models.py`, and ~25 CLI-level tests
in `tests/test_cli.py`. No test is currently red.

## 3. Scope

### 3.1 Covered by this spec

`send`, `draft`, `draft-update`, `draft-send`, and every `mail` subcommand (list, search, get,
read, mark-read, mark-unread, trash, flag, archive, move, attachments, download).

### 3.2 Not covered

Calendar (SPEC-0003). Authentication and the shared Graph client (SPEC-0001).

## 4. Actors

- **Operator**: sends, drafts, and triages mail through the CLI.

## 5. Usage Scenarios

### SC-001: Send a small message
Trigger: `send --to ... --subject ... --body ...` with attachments (if any) under the inline
threshold. Outcome: one message sent in a single call, no draft left behind.

### SC-002: Send a message with large attachments
Trigger: `send` with attachments whose total size exceeds the inline threshold. Outcome: a draft
is created, each attachment is uploaded (small ones directly, large ones in chunks), then the draft
is sent; no draft remains afterward.

### SC-003: Reply in-thread with a custom note
Trigger: `draft --reply-to <id> --body "<note>"` (optionally `--reply-all`). Outcome: a true
threaded reply draft is created; the custom note is inserted above the quoted original, the
original is never replaced.

### SC-004: Build a draft incrementally
Trigger: `draft` (standalone) then one or more `draft-update` calls (new body, add/remove
attachments), then `draft-send`. Outcome: the draft reflects every update; nothing is sent until
`draft-send` is called.

### SC-005: Triage the inbox
Trigger: `mail list`, `mail search <query>`, `mail get <id>`, `mail read <id>`,
`mail mark-read|mark-unread|flag|archive|move|trash <id>`. Outcome: the operator sees a summary or
full content, and the message's state changes accordingly.

### SC-006: Download an attachment
Trigger: `mail download <id> [--name <filter>] [--include-inline]`. Outcome: matching attachment(s)
are written to disk, decoded whether Graph returned them inline or required a separate fetch.

## 6. Functional Requirements

| ID | Requirement (EARS) | Scenario | Evidence |
|---|---|---|---|
| FR-001 | WHEN the total attachment size of a message is at or below the configured inline limit THE system SHALL send it with a single call and leave no draft behind | SC-001 | `src/services/mail.py:97-112` |
| FR-002 | WHEN the total attachment size exceeds the configured inline limit THE system SHALL create a draft, upload every attachment, and send that draft | SC-002 | `src/services/mail.py:97-122` |
| FR-003 | WHEN an individual attachment is at or below the inline limit THE system SHALL attach it directly; WHEN it exceeds the limit THE system SHALL upload it via a chunked upload session | SC-002 | `src/services/mail.py:124-156` |
| FR-004 | WHEN the operator replies to a message THE system SHALL create a true threaded reply (correct conversation, "RE: " subject, quoted original), addressed to all recipients when `--reply-all` is given | SC-003 | `src/services/mail.py:232-234` |
| FR-005 | WHEN a reply is created with a custom body THE system SHALL insert that text above the quoted original rather than replacing it | SC-003 | `src/services/mail.py:242-258` |
| FR-006 | IF `--reply-all` is given without `--reply-to` THEN THE system SHALL reject the command before any network call | SC-003 | `src/outlook_tool.py:193-195` |
| FR-007 | WHEN the operator creates a standalone draft THE system SHALL store it without sending it | SC-004 | `src/services/mail.py:193-207` |
| FR-008 | WHEN the operator updates an existing draft's body THE system SHALL fully replace the previous body, not merge it | SC-004 | `src/services/mail.py:176-186` |
| FR-009 | WHEN the operator adds or removes attachments on an existing draft THE system SHALL reflect exactly that change without resending the draft | SC-004 | `src/services/mail.py:159-174` |
| FR-010 | IF `draft-update` is called with none of body, add-attach, or remove-attach THEN THE system SHALL reject the command, exit code 2 | SC-004 | `src/outlook_tool.py:258-260` |
| FR-011 | WHEN the operator runs `draft-send` on an existing draft id THE system SHALL send that draft and nothing else | SC-004 | `src/services/mail.py:187-191` |
| FR-012 | WHEN the operator lists messages in a folder THE system SHALL return them ordered most-recent-first, optionally filtered to unread only | SC-005 | `src/services/mail.py:367-382` |
| FR-013 | WHEN the operator searches mail THE system SHALL return matches for the given query across the mailbox | SC-005 | `src/services/mail.py:266-275` |
| FR-014 | WHEN the operator retrieves a single message THE system SHALL return its full content, including meeting start/end times when the message is a meeting request | SC-005 | `src/services/mail.py:293-324` |
| FR-015 | WHEN the operator marks a message read or unread, flags or unflags it, archives it, trashes it, or moves it to a named folder THE system SHALL apply exactly that change and no other | SC-005 | `src/services/mail.py:277-341` |
| FR-016 | WHEN the operator lists a message's attachments THE system SHALL return each one's name, type, size, and whether it is inline | SC-006 | `src/services/mail.py:343-348` |
| FR-017 | WHEN the operator downloads an attachment THE system SHALL write its decoded bytes to disk, whether Graph returned them inline or required a separate fetch | SC-006 | `src/services/mail.py:350-365`, `src/outlook_tool.py:520` |
| FR-018 | IF no attachment matches the requested name filter (respecting whether inline attachments are included) THEN THE system SHALL fail with exit code 1 and no file written | SC-006 | `src/outlook_tool.py:512-516` |
| FR-019 | IF `send` or `draft` (standalone) is called without a body THEN THE system SHALL reject the command before any network call | SC-001, SC-004 | `src/outlook_tool.py:132-135`, `src/outlook_tool.py:196-204` |

## 7. Non-Functional Requirements

None observed beyond what is already stated as functional (size-based routing is itself an
observable behavior, captured in FR-001 to FR-003).

## 8. End-to-End Tests

| ID | Covers | Test | Level | State |
|---|---|---|---|---|
| E2E-001 | FR-001 | `tests/test_mail.py::test_send_inline_small_message` | unit (mocked Graph) | green |
| E2E-002 | FR-002, FR-003 | `tests/test_mail.py::test_send_via_draft_with_upload_session` | unit | green |
| E2E-003 | FR-007 | `tests/test_mail.py::test_create_draft_small_message`, `test_create_draft_with_attachment` | unit | green |
| E2E-004 | FR-004 | `tests/test_mail.py::test_create_reply_draft_simple`, `test_create_reply_draft_reply_all_uses_createreplyall` | unit | green |
| E2E-005 | FR-005 | `tests/test_mail.py::test_create_reply_draft_custom_body_prepends_not_replaces`, `test_create_reply_draft_custom_body_plain_text`, `test_create_reply_draft_custom_body_no_body_tag_fallback` | unit | green |
| E2E-006 | FR-006 | `tests/test_cli.py::test_draft_reply_all_requires_reply_to` | integration (CLI) | green |
| E2E-007 | FR-008 | `tests/test_mail.py::test_update_body_replaces_content_html`, `test_update_body_replaces_content_text` | unit | green |
| E2E-008 | FR-009 | `tests/test_mail.py::test_add_attachments_uploads_each_file`, `test_remove_attachment_calls_delete` | unit | green |
| E2E-009 | FR-010 | `tests/test_cli.py::test_draft_update_requires_an_action` | integration (CLI) | green |
| E2E-010 | FR-011 | `tests/test_mail.py::test_send_draft_calls_send_endpoint` | unit | green |
| E2E-011 | FR-012 | `tests/test_mail.py::test_list_messages`, `test_list_messages_unread_filter` | unit | green |
| E2E-012 | FR-013 | `tests/test_mail.py::test_search_messages` | unit | green |
| E2E-013 | FR-014 | `tests/test_mail.py::test_get_message_uses_eventmessage_cast_for_meeting` | unit | green |
| E2E-014 | FR-015 | `tests/test_mail.py::test_mark_read`, `test_mark_unread`, `test_trash_message`, `test_flag_message`, `test_unflag_message`, `test_move_and_archive_message` | unit | green |
| E2E-015 | FR-016 | `tests/test_mail.py::test_list_attachments` | unit | green |
| E2E-016 | FR-017 | `tests/test_mail.py::test_download_attachment_inline_content`, `test_download_attachment_value_fallback` | unit | green |
| E2E-017 | FR-018 | `tests/test_cli.py::test_mail_download_no_match` | integration (CLI) | green |
| E2E-018 | FR-019 | `tests/test_cli.py::test_send_requires_body`, `test_draft_requires_body`, `test_draft_requires_to_or_reply_to` | integration (CLI) | green |
| E2E-019 | FR-014 (eventMessage cast failure path) | untested | | |

## 9. Glossary

- **Inline send**: a single Graph `sendMail` call with no intermediate draft.
- **Upload session**: Graph's chunked-upload mechanism for attachments too large for a single
  request.
- **Threaded reply**: a reply created via Graph's `createReply`/`createReplyAll`, which carries the
  original conversation id and quoted content, as opposed to a new unrelated message.

## 10. Confidence notes

- The eventMessage-cast fallback in `get_message` silently swallows a `GraphError` on the secondary
  request (`src/services/mail.py:313-315`); only the success path is tested, so the failure branch
  is marked `untested` (E2E-019) rather than invented, and filed to backlog as a finding (swallowed
  error, no logging).
- `search_messages` wraps the query in literal double quotes with no escaping
  (`src/services/mail.py:272`); documented as observed behavior (FR-013) without judging it, with a
  separate backlog finding for the unescaped-quote edge case.
- Confidence is high: every requirement cites lines read directly, not only the subagent summary.
