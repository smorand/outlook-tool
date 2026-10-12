---
Id: BL-0013
Title: pyproject.toml has no [tool.bandit] section despite Makefile referencing it
Nature: DEBT
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: Low
Fingerprint: debt:Makefile:security:bandit-c-pyproject.toml
---

## What

The `security` Makefile target runs `uv run bandit -r src/ -c pyproject.toml`, falling back to a
plain `bandit -r src/` if that fails. `pyproject.toml` has no `[tool.bandit]` section at all, so
the first invocation's `-c` flag points at a config file with nothing for bandit to read.

## Why

The fallback silently masks whether `-c pyproject.toml` is doing anything; any intended bandit
configuration (skip rules, severity thresholds) that someone assumes is active in `pyproject.toml`
is not actually being applied.

## Evidence

- `Makefile:135`: `uv run bandit -r $(SRC_DIR)/ -c pyproject.toml 2>/dev/null || uv run bandit -r $(SRC_DIR)/`.
- `pyproject.toml`: no `[tool.bandit]` section present.

## Notes

Not fixed by this pass. Suggested next command: `/sdlc-spec --debt`.
