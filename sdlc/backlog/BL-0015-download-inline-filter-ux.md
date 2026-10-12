---
Id: BL-0015
Title: mail download gives no hint when a match was excluded by the inline filter
Nature: DEBT
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Low
Fingerprint: debt:src/outlook_tool.py:mail-download:include-inline
---

## What

`mail download` filters attachments by a case-insensitive substring match on name, then by
`--include-inline` (default false). If the only matching attachment is inline-only and
`--include-inline` was not passed, the command reports "No matching attachment" (exit 1) exactly
as it would for a genuinely absent attachment, with no hint that an inline attachment was excluded.

## Why

An operator searching for an attachment they can see in their mail client gets the same generic
"not found" message whether the attachment truly doesn't exist or was filtered out by a flag they
didn't know to pass.

## Evidence

- `src/outlook_tool.py:512-516`: substring match combined with `--include-inline` check, same exit
  path for both "not found" and "found but excluded".
- No test distinguishes "no attachments at all" from "excluded by inline filter".

## Notes

Related: SPEC-0002/FR-018. Suggested next command: `/sdlc-spec --debt`.
