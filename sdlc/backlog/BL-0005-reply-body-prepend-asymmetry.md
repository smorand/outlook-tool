---
Id: BL-0005
Title: Fix missing separator when the HTML reply body has no <body> tag to anchor on
Nature: BUG
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Low
Fingerprint: suspected-defect:src/services/mail.py:_prepend_reply_body
---

## What

`_prepend_reply_body` inserts the custom note right after the first `<body...>` tag when one is
found. When no `<body>` tag is found, it falls back to concatenating the note directly in front of
the existing content with zero separator. The plain-text branch, by contrast, always adds a blank
line between the note and the quoted original.

## Why

The HTML no-`<body>`-tag fallback likely renders the custom note glued to the start of the quoted
HTML with no visual break, an inconsistent and probably unintended result compared to the
plain-text behavior.

## Evidence

- `src/services/mail.py:79-80` (plain text: `f"{addition}\n\n{existing_content}"`)
- `src/services/mail.py:83-84` (HTML fallback: `f"{addition}{existing_content}"`, no separator)
- Tested only for presence/absence, not visual separation:
  `tests/test_mail.py::test_create_reply_draft_custom_body_no_body_tag_fallback`.

## Notes

Related: SPEC-0002/FR-005. Suggested next command: `/sdlc-spec --debt`.
