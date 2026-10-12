---
Id: BL-0011
Title: Docker packaging was never adapted from the project template
Nature: BUG
Source: retro-spec 20261012-214338
Created: 2026-10-12
Severity: High
Fingerprint: suspected-defect:Dockerfile:ENTRYPOINT-hello
---

## What

`Dockerfile`'s `ENTRYPOINT ["hello"]` is the unedited template placeholder; the actual CLI entry
point is `outlook-tool` (per `pyproject.toml`'s `[project.scripts]`). `docker-compose.yml` is
likewise still the generic template: no healthcheck, commented-out placeholder
environment/volumes.

## Why

The Docker image as committed would fail at startup (`hello` does not exist in the built venv),
so `make docker-build && make run-up` does not produce a working container for this CLI.

## Evidence

- `Dockerfile:52-55`: comment block explicitly shows `ENTRYPOINT ["hello"]` as the CLI-type
  example, and line 55 uses it unchanged.
- `pyproject.toml` `[project.scripts]`: `outlook-tool = "outlook_tool:app"` (the real entry point).
- `docker-compose.yml`: no `healthcheck:` key; `environment:`/`volumes:` left as comments.

## Notes

Not fixed by this pass (outside `sdlc/`, Invariant 1/2). Suggested next command: `/sdlc-spec --debt`.
