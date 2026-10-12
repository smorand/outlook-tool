---
Id: BL-0014
Title: A missing attachment path surfaces as a raw traceback instead of a clean CLI error
Nature: BUG
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Medium
Fingerprint: suspected-defect:src/models.py:Attachment.from_path:FileNotFoundError
---

## What

`Attachment.from_path` raises a bare `FileNotFoundError` with a custom message when the given path
is not a file. None of `send`, `draft`, or `draft-update` catch this exception, so passing a
nonexistent `--attach`/`--add-attach` path produces an unhandled Python traceback instead of a
clean, red-styled CLI error like every other validation failure in the same commands.

## Why

Every other user-input validation error in these commands (missing body, missing recipients, etc.)
is reported with a styled message and exit code 2; a typo'd attachment path instead dumps a stack
trace, inconsistent with the rest of the CLI's UX and more alarming than necessary.

## Evidence

- `src/models.py:44-46`: `raise FileNotFoundError(...)` with a custom message, uncaught upstream.
- `src/outlook_tool.py` `send`/`draft`/`draft-update` commands: no `try/except FileNotFoundError`
  around the point where `Attachment.from_path` is called.
- No test exercises a missing attachment path at the CLI level.

## Notes

Related: SPEC-0002/FR-001, SPEC-0002/FR-009. Suggested next command: `/sdlc-spec --debt`.
