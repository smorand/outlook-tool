# Mail: Design (as-built)

> Spec: SPEC-0002
> Status: as-built
> Generated on: 2026-10-12 at 6956ac5

## 1. Components

| Component | Responsibility | Location |
|---|---|---|
| `MailService` | All mail operations against Graph | `src/services/mail.py` |
| `outlook_tool.py` mail commands | CLI surface for `send`/`draft*`/`mail *` | `src/outlook_tool.py:119-523` |
| `models.py` (Recipient, Attachment, OutgoingMessage, MailSummary, AttachmentSummary) | Value objects and Graph (de)serialization | `src/models.py` |

## 2. Flows

### Send, inline vs draft (FR-001, FR-002, FR-003)
`MailService.send` (`src/services/mail.py:97-109`): if
`message.total_attachment_size <= settings.attachment_inline_limit` → `_send_inline`
(POST `/me/sendMail`, `src/services/mail.py:111-112`). Else → `_send_via_draft`: POST
`/me/messages` to create the draft (`src/services/mail.py:115-118`), then per-attachment
`_add_attachment` (small: POST `/me/messages/{id}/attachments`; large: POST
`.../attachments/createUploadSession` then PUT each chunk of `upload_chunk_size` bytes with
`authenticated=False`, `src/services/mail.py:124-156`), then POST
`/me/messages/{id}/send` (`src/services/mail.py:122`).

### Reply (FR-004, FR-005, FR-006)
`create_reply_draft` (`src/services/mail.py:209-264`): POST
`/me/messages/{id}/createReply` or `createReplyAll` (`src/services/mail.py:232-234`) — the
server supplies `conversationId`, the `RE: ` subject and the quoted body. If a custom body,
subject, or recipient override is given, `_prepend_reply_body` builds the merged content
(HTML: insert right after the first `<body...>` tag, falling back to a bare prepend with no
separator if no `<body>` tag is found; plain text: prepend with a blank line,
`src/services/mail.py:79-86`) and a single follow-up PATCH
`/me/messages/{draft_id}` applies body/subject/to/cc/bcc together
(`src/services/mail.py:242-258`); attachments are added after, via the same
`_add_attachment` helper (`src/services/mail.py:259-260`). CLI validates
`--reply-all` requires `--reply-to` before any network call
(`src/outlook_tool.py:193-195`).

### Draft lifecycle (FR-007 to FR-011)
`create_draft`: POST `/me/messages`, never sent (`src/services/mail.py:193-207`).
`update_body`: PATCH `/me/messages/{id}` with `{"body": {...}}`, full replace
(`src/services/mail.py:176-186`). `add_attachments`/`remove_attachment`: per-item POST/DELETE
(`src/services/mail.py:159-174`). `send_draft`: POST `/me/messages/{id}/send`
(`src/services/mail.py:187-191`). CLI `draft-update` requires at least one of
body/add-attach/remove-attach (`src/outlook_tool.py:258-260`).

### Triage (FR-012 to FR-016)
`list_messages`: GET `/me/mailFolders/{folder}/messages` with `$top`, `$select`,
`$orderby=receivedDateTime desc`, `$filter=isRead eq false` when `unread_only`
(`src/services/mail.py:367-382`). `search_messages`: GET `/me/messages?$search="<query>"`,
no `$orderby` (`src/services/mail.py:266-275`). `get_message`: GET
`/me/messages/{id}?$select=...`; if `@odata.type` indicates a meeting message, a second GET
via the `microsoft.graph.eventMessage` cast segment fetches start/end, swallowing
`GraphError` on failure (`src/services/mail.py:293-324`). `move_message` (and the
`archive_message`/`trash_message` wrappers): POST `/me/messages/{id}/move` with
`destinationId` `"archive"`/`"deleteditems"` (`src/services/mail.py:277-291,332-334`).
`mark_read`: PATCH `{"isRead": read}` (`src/services/mail.py:326-330`). `flag_message`:
PATCH `{"flag": {"flagStatus": ...}}` (`src/services/mail.py:336-341`).

### Attachments (FR-017, FR-018)
`list_attachments`: GET `/me/messages/{id}/attachments?$select=...`
(`src/services/mail.py:343-348`). `download_attachment`: GET attachment metadata; if
`contentBytes` present, base64-decode inline; else GET `.../attachments/{id}/$value` for raw
bytes (`src/services/mail.py:350-365`). CLI `mail download` filters by case-insensitive
substring match on name and `--include-inline`, writes to disk via
`dest.write_bytes(data)` (`src/outlook_tool.py:512-520`); no match → exit 1
(`src/outlook_tool.py:514-516`).

## 3. Interfaces

CLI: `send --to/--subject/-s/--body/-b/--body-file/--cc/--bcc/--attach/-a/--html/--text`
(`src/outlook_tool.py:119-150`); `draft` (same flags plus `--reply-to`/`--reply-all`,
`src/outlook_tool.py:153-235`); `draft-update <message_id> [--body/-b/--body-file/--html/--text/--add-attach/--remove-attach]`
(`src/outlook_tool.py:237-271`); `draft-send <message_id>` (`src/outlook_tool.py:273-285`);
`mail list [--top/-n/--folder/-f/--unread/--json]` (`src/outlook_tool.py:288-306`);
`mail search <query> [--top/-n/--json]` (`src/outlook_tool.py:310-326`);
`mail get <message_id> [--json]` (`src/outlook_tool.py:330-351`);
`mail read <message_id>` (`src/outlook_tool.py:447-459`);
`mail mark-read|mark-unread|trash|archive <message_id>`
(`src/outlook_tool.py:355-427`); `mail flag <message_id> [--unflag]`
(`src/outlook_tool.py:400-414`); `mail move <message_id> <destination>`
(`src/outlook_tool.py:429-444`); `mail attachments <message_id> [--json]`
(`src/outlook_tool.py:463-486`); `mail download <message_id> [--out/-o/--name/--include-inline]`
(`src/outlook_tool.py:490-523`).

## 4. Data and state

Graph resources only (no local persistence besides downloaded attachment files written by the
operator's `--out` path). Models: `Recipient`, `Attachment` (`from_path` reads local files and
base64-encodes, `src/models.py:44-46` and surrounding), `OutgoingMessage` (serializes to
Graph's `message` shape, computes `total_attachment_size`), `MailSummary` (parses a Graph
message into a CLI-friendly summary, including `is_meeting_request`), `AttachmentSummary`.

## 5. Configuration

Shared with SPEC-0001: `attachment_inline_limit` (default `3_000_000` bytes),
`upload_chunk_size` (default `3_276_800` bytes, must be a multiple of 320 KiB per
`src/config.py:55-56`), `graph_base`, `request_timeout`. No mail-specific settings beyond
those.

## 6. Observability

Every `MailService` operation wraps its Graph call(s) in an OpenTelemetry span via
`trace_span` (e.g. `"mail.send"` with attribute `mail.attachments`,
`src/services/mail.py:105`); no mail-specific metrics or structured logs beyond the shared
`GraphClient` span (`api.graph`, see SPEC-0001 design §6).

## 7. Decisions (observed)

| ID | Decision | Evidence | Rationale |
|---|---|---|---|
| DEC-001 | Size-based routing between inline `sendMail` and draft+upload-session, both for the whole message and per attachment | `src/services/mail.py:97-156` | Documented inline: Graph caps a single-request `sendMail` near 4 MB (`src/config.py:53-54` comment) |
| DEC-002 | A custom reply body is always prepended to the server-supplied quote via a follow-up PATCH, never a replacement | `src/services/mail.py:242-258` | Documented: preserves true threading and the original citation |
| DEC-003 | HTML prepend without a `<body>` tag falls back to a bare prepend with no separator, unlike the plain-text branch which adds a blank line | `src/services/mail.py:79-86` | Not documented; observed asymmetry, not explained in code or comments |
| DEC-004 | `search_messages` does not sort (`$orderby` omitted) | `src/services/mail.py:266-275` | Documented inline: Graph's `$search` is incompatible with `$orderby` |

## 8. Requirement to code map

| Requirement | Files |
|---|---|
| SPEC-0002/FR-001 | `src/services/mail.py:97-112` |
| SPEC-0002/FR-002 | `src/services/mail.py:97-122` |
| SPEC-0002/FR-003 | `src/services/mail.py:124-156` |
| SPEC-0002/FR-004 | `src/services/mail.py:232-234` |
| SPEC-0002/FR-005 | `src/services/mail.py:242-258` |
| SPEC-0002/FR-006 | `src/outlook_tool.py:193-195` |
| SPEC-0002/FR-007 | `src/services/mail.py:193-207` |
| SPEC-0002/FR-008 | `src/services/mail.py:176-186` |
| SPEC-0002/FR-009 | `src/services/mail.py:159-174` |
| SPEC-0002/FR-010 | `src/outlook_tool.py:258-260` |
| SPEC-0002/FR-011 | `src/services/mail.py:187-191` |
| SPEC-0002/FR-012 | `src/services/mail.py:367-382` |
| SPEC-0002/FR-013 | `src/services/mail.py:266-275` |
| SPEC-0002/FR-014 | `src/services/mail.py:293-324` |
| SPEC-0002/FR-015 | `src/services/mail.py:277-341` |
| SPEC-0002/FR-016 | `src/services/mail.py:343-348` |
| SPEC-0002/FR-017 | `src/services/mail.py:350-365`, `src/outlook_tool.py:520` |
| SPEC-0002/FR-018 | `src/outlook_tool.py:512-516` |
| SPEC-0002/FR-019 | `src/outlook_tool.py:132-135`, `src/outlook_tool.py:196-204` |
