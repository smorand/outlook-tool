---
Id: BL-0016
Title: README configuration table omits several existing OUTLOOK_TOOL_* settings
Nature: DEBT
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Low
Fingerprint: stale-doc:README.md:config-table-omissions
---

## What

README's environment variable table lists `OUTLOOK_TOOL_CLIENT_ID`, `OUTLOOK_TOOL_SCOPES`,
`OUTLOOK_TOOL_TOKEN_CACHE_PATH`, `OUTLOOK_TOOL_ATTACHMENT_INLINE_LIMIT`, and
`OUTLOOK_TOOL_GRAPH_BASE`, but `Settings` also exposes `OUTLOOK_TOOL_UPLOAD_CHUNK_SIZE`,
`OUTLOOK_TOOL_REQUEST_TIMEOUT`, `OUTLOOK_TOOL_AUTHORITY`, and `OUTLOOK_TOOL_APP_NAME`, none of
which are documented, even though the body text right above the table discusses chunked uploads.

## Why

An operator wanting to tune the chunk size or request timeout, or point at a non-default
authority/app name, has no documented way to discover these variables exist.

## Evidence

- `README.md` configuration table: 5 rows only.
- `src/config.py:39,43,48,55-56`: `app_name`, `authority`, `request_timeout`,
  `upload_chunk_size` fields, all overridable via the same `OUTLOOK_TOOL_` prefix.

## Notes

Read-only documentation outside `sdlc/`; not fixed by this pass. Suggested next command:
`/sdlc-retro-doc` (once available).
