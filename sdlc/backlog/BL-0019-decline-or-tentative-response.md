---
Id: BL-0019
Title: Allow declining or tentatively accepting a meeting invitation, not just accepting
Nature: FEAT
Source: YAGNI defer from SPEC-0004
Created: 2026-10-13
---

## What

Only `cal accept` exists today. An operator who wants to decline or tentatively accept an
invitation has no CLI command for it.

## Why

Came up while specifying SPEC-0004 (which only confirms acceptance, as requested). A full response
story would also cover decline and tentative accept, but the original request only asked to confirm
that acceptance registered.

## Notes

Candidate for `/sdlc-spec` against SPEC-0003/SPEC-0004 once wanted; would likely reuse the same
response-state vocabulary SPEC-0004 introduces.
