---
Id: BL-0001
Title: Add tests for the unreadable-cache and unreadable-rule-file fallback paths
Nature: DEBT
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Medium
Fingerprint: untested:src/auth.py:_load_cache
---

## What

Two requirements of SPEC-0001 are implemented but have no test exercising their failure branch:
FR-009 (a corrupted/unreadable token cache is treated as absent rather than crashing) and FR-014
(an unreadable personal rule file is skipped with a warning rather than failing `skill`).

## Why

A future refactor of either fallback could silently break the graceful-degradation behavior and
the test suite would stay green.

## Evidence

- `src/auth.py:184-190` — `except (ValueError, OSError)` fallback, no test supplies a corrupt file.
- `src/skill_cmd.py:74-76` — unreadable rule file warning, no test makes a file unreadable.
- Listed as `untested` at SPEC-0001/E2E-015 and SPEC-0001/E2E-016.

## Notes

Related: SPEC-0001/FR-009, SPEC-0001/FR-014. Suggested next command: `/sdlc-retro-tests`.
