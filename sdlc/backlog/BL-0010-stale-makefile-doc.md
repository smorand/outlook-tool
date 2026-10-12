---
Id: BL-0010
Title: .agent_docs/makefile.md references targets that no longer exist and an outdated check description
Nature: DEBT
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Low
Fingerprint: stale-doc:.agent_docs/makefile.md:install-editable
---

## What

`.agent_docs/makefile.md` documents `install-editable` and `install-global` targets that do not
exist in the current `Makefile` (only `install`/`uninstall` exist), and describes the `check`
target as running "lint, format-check, typecheck, test", omitting `security` and `test-cov` that
the real target runs.

## Why

An agent or operator consulting this doc would look for nonexistent make targets and would
underestimate what `make check` actually verifies before a commit.

## Evidence

- `.agent_docs/makefile.md`: lists `install-editable`/`install-global` under "Build & Install
  Targets".
- `Makefile:131-133`: `check` target runs `lint format-check typecheck security test-cov`.
- `Makefile` defines only `install`/`uninstall` (no editable/global variants).

## Notes

Read-only documentation outside `sdlc/`; not fixed by this pass. Suggested next command:
`/sdlc-retro-doc` (once available).
