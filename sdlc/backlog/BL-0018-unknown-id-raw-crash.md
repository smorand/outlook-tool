---
Id: BL-0018
Title: An unknown event or message id crashes with a raw traceback instead of a clean error
Nature: unknown
Source: YAGNI defer from SPEC-0004
Created: 2026-10-13
---

## What

`cal update`, `cal delete`, `cal accept` (and the equivalent mail commands) let an unknown id's
`GraphError` propagate uncaught, surfacing a raw Python traceback to the operator instead of a clean
message.

## Why

Came up while specifying SPEC-0004's new `cal get` lookup: deciding whether to give the new command
a nicer error than the existing ones would have been inconsistent. The underlying gap is real but
predates this increment and is not scoped to calendar alone.

## Evidence

- `src/outlook_tool.py:57-63`: `_run` only catches `LoginRequiredError`.
- `src/graph_client.py:22-30`: `GraphError` is an uncaught `Exception` subclass on any Graph call.

## Notes

Whether this is a BUG (inconsistent with the CLI's own UX elsewhere) or a DEBT (a shared error-
handling wrapper) is for `/sdlc-spec` to settle. Related: BL-0007 (event id not URL-encoded, same
code paths).
