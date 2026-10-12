---
Id: BL-0006
Title: Escape double quotes before wrapping the search query for Graph $search
Nature: BUG
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Low
Fingerprint: suspected-defect:src/services/mail.py:search_messages:$search
---

## What

`search_messages` wraps the operator-supplied query in literal double quotes
(`f'"{query}"'`) with no escaping. A query that itself contains a `"` will break or alter how
Graph parses the `$search` parameter.

## Why

An operator searching for a subject or sender containing a quote character gets a confusing error
or wrong results instead of the intended search.

## Evidence

- `src/services/mail.py:272`: `f'"{query}"'`, no escaping of embedded `"`.
- No test covers a query containing a double quote.

## Notes

Related: SPEC-0002/FR-013. Not a security issue (the operator only searches their own mailbox);
filed as a correctness defect. Suggested next command: `/sdlc-spec --debt`.
