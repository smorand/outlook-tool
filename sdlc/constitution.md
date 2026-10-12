# Constitution (DRAFT, written by /sdlc-retro-spec on 2026-10-12, review before relying on it)

> Status: draft

| Rule | Source | Enforced by |
|---|---|---|
| `make check` (lint, format-check, typecheck, security, test-cov >=80%) runs before every commit | `Makefile:131-133`, `AGENTS.md` ("Quality Gate" section) | Partially: CI (`.github/workflows/ci.yml:14-29`) runs lint/format-check/typecheck/test but not security/test-cov (see backlog BL-0012); no enforcement outside CI |
| Session/token cache is written atomically with owner-only (`0600`) permissions | `src/auth.py:196-201`, `AGENTS.md` ("auth.py" architecture line) | `tests/test_auth.py::test_store_and_load_cache_roundtrip` |
| Configuration is layered through `pydantic-settings` with a single `OUTLOOK_TOOL_` env prefix, never raw `os.environ` reads | `src/config.py:34-56`, `AGENTS.md` ("config.py" architecture line) | `tests/test_config.py::test_default_settings`, `test_settings_from_env` |
| No client secret is ever stored or required; auth relies solely on a public first-party client id and device-code flow | `src/config.py:10-14`, `AGENTS.md`, `README.md` | Convention only, no automated check |
| Every Graph call goes through `GraphClient`, which raises `GraphError` on any status >= 400 rather than letting callers inspect raw responses | `src/graph_client.py:24,95-98`, 14 of 14 call sites across `services/mail.py` and `services/calendar.py` | Convention only (no lint rule forbids direct `httpx` calls outside `GraphClient`) |
