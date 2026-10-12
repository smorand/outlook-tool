---
Id: BL-0012
Title: CI does not run the full make check gate (missing security and coverage enforcement)
Nature: BUG
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Medium
Fingerprint: suspected-defect:.github/workflows/ci.yml:missing-security-and-coverage
---

## What

`.github/workflows/ci.yml` runs `make lint`, `make format-check`, `make typecheck`, and `make test`
as four separate steps. It never calls `make check` as a single gate, and it never runs
`make security` (bandit) or `make test-cov` (the >=80% coverage gate).

## Why

AGENTS.md and README both describe `make check` (lint, format-check, typecheck, security,
test-cov >=80%) as the quality gate expected before every commit. CI silently enforces less than
that: a pull request with a security finding or a coverage regression would still pass CI green.

## Evidence

- `.github/workflows/ci.yml:14-29`: four separate `make lint`/`make format-check`/`make typecheck`/
  `make test` steps, no `make security`, no `make test-cov`, no single `make check` call.
- `Makefile:131-133`: `check` target runs `lint format-check typecheck security test-cov`.
- `AGENTS.md`: "`make check` avant chaque commit: lint, format-check, typecheck, security,
  test-cov (>=80%)."

## Notes

Not fixed by this pass (outside `sdlc/`). Suggested next command: `/sdlc-spec --debt`.
