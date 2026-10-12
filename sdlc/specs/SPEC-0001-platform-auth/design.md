# Platform, Authentication & Skill: Design (as-built)

> Spec: SPEC-0001
> Status: as-built
> Generated on: 2026-10-12 at 6956ac5

## 1. Components

| Component | Responsibility | Location |
|---|---|---|
| `outlook_tool.py` (Typer app) | CLI wiring, dependency injection via `_with_services`, sync/async bridge `_run` | `src/outlook_tool.py:36-81` |
| `Authenticator` | Device code flow, token cache load/store/refresh | `src/auth.py` |
| `Settings` | pydantic-settings config, env prefix `OUTLOOK_TOOL_` | `src/config.py` |
| `GraphClient` | httpx async wrapper, bearer injection, `GraphError` on >=400 | `src/graph_client.py` |
| `setup_logging` | Rich console + file logging, verbosity mapping | `src/logging_config.py` |
| `configure_tracing`/`trace_span` | OpenTelemetry provider + JSONL exporter | `src/tracing.py` |
| `skill_cmd.py` | `skill`/`skill learn` commands | `src/skill_cmd.py` |
| `version.py` | `__version__` constant | `src/version.py` |

## 2. Flows

### Login (SC-001)
CLI `login` (`src/outlook_tool.py:109-123`) calls `Authenticator.login(prompt_cb)`
(`src/auth.py:109-121`): POST `{authority}/devicecode` (`src/auth.py:117-120`) →
prompt callback prints URI/code and calls `webbrowser.open` (`src/outlook_tool.py:111-114`) →
poll loop POST `{authority}/token` with `device_code` grant until `access_token` present,
`authorization_pending` continues, `slow_down` adds 5s to interval (`src/auth.py:138-156`) →
`_store` writes `token.json` atomically with `0600` (`src/auth.py:193-201`).

### Silent reuse / refresh (SC-002)
`get_access_token()` (`src/auth.py:88-98`): if `_token.is_valid` (expiry margin 120s,
`_EXPIRY_SKEW_SECONDS`, `src/auth.py:33,66`) return cached access token; elif
`refresh_token` present, call `_refresh` (POST `{authority}/token`, `refresh_token` grant,
`src/auth.py:148-156`), keep old refresh token if the response omits a new one
(`src/auth.py:163-165`); else raise `LoginRequiredError`.

### Expired/unrefreshable session (SC-003)
`_refresh` failure (`src/auth.py:160`) or absent token (`src/auth.py:98`) raises
`LoginRequiredError`. `_run` in the CLI catches it, prints a red message, exits with code 2
(`src/outlook_tool.py:57-63`).

### Logging and tracing wiring (SC-004)
`main()` callback builds `Settings()`, counts `-v` occurrences, calls `setup_logging(level, settings.log_dir, settings.app_name)` and `configure_tracing(settings)` (`src/outlook_tool.py:70-81`).
`_level_for_verbosity`: 0→ERROR, 1→INFO, 2+→DEBUG (`src/logging_config.py:22-27`).
Console handler always stderr (`src/logging_config.py:49`); file handler always attached
regardless of console level, writing `<log_dir>/<app_name>.log` (`src/logging_config.py:40-41,52-55`).
`httpx`/`httpcore` loggers forced to WARNING to avoid leaking upload-session URLs/tokens at
INFO (`src/logging_config.py:70-73`). `configure_tracing` writes JSONL spans to
`<log_dir>/<app_name>-otel.log` via `SimpleSpanProcessor` (`src/tracing.py:67-84`).

### Skill (SC-005, SC-006)
`skill` (`src/skill_cmd.py:57-78`): reads embedded `skill.md` next to the module
(`src/skill_cmd.py:38-40`), then lists `*.md` files under `~/.config/outlook-tool/` (or
`$XDG_CONFIG_HOME/outlook-tool`, `src/skill_cmd.py:27-33`), sorted, concatenated under a
header; unreadable files logged as a warning and skipped (`src/skill_cmd.py:74-76`).
`skill learn --rule <text>` (`src/skill_cmd.py:80-99`): rejects empty rule with exit 2
(`src/skill_cmd.py:89-91`); else creates the config dir (`0755`) and appends a timestamped
line to `regles-tri.md`, chmod `0644`.

## 3. Interfaces

CLI commands: `login` (no flags), `version` (no flags), `-v`/`-vv`/`--verbose` global count
flag (`src/outlook_tool.py:72-77`), `skill` (no flags), `skill learn --rule <text>`
(`src/skill_cmd.py`). `_with_services` builds `httpx.AsyncClient`, `Authenticator`,
`GraphClient`, `MailService`, `CalendarService` per invocation (`src/outlook_tool.py:48-54`).

## 4. Data and state

- `token.json` (session cache): `{access_token, refresh_token, expires_at, ...}` serialized
  via `TokenSet.model_dump_json()`, default path `~/.cache/outlook-tool/token.json`,
  permissions `0600`, atomic write (`.tmp` + `chmod` + `replace`) (`src/auth.py:193-201`,
  `src/config.py:51`).
- `<app_name>.log`, `<app_name>-otel.log`: always-on log/trace files, same directory as the
  token cache (`log_dir` = `token_cache_path.parent`, `src/config.py:63-65`).
- `~/.config/outlook-tool/*.md`: operator-authored rule files, read by `skill`
  (`src/skill_cmd.py:27-33`); `regles-tri.md` specifically written by `skill learn`.

## 5. Configuration

| Name | Source | Default | Evidence |
|---|---|---|---|
| `app_name` | env `OUTLOOK_TOOL_APP_NAME` | `outlook-tool` | `src/config.py:39` |
| `client_id` | env `OUTLOOK_TOOL_CLIENT_ID` | `d3590ed6-52b3-4102-aeff-aad2292ab01c` (public MS Office) | `src/config.py:14,42` |
| `authority` | env `OUTLOOK_TOOL_AUTHORITY` | `https://login.microsoftonline.com/common/oauth2/v2.0` | `src/config.py:43` |
| `scopes` | env `OUTLOOK_TOOL_SCOPES` | `Mail.ReadWrite Mail.Send Calendars.ReadWrite offline_access openid profile` | `src/config.py:17-21,44` |
| `graph_base` | env `OUTLOOK_TOOL_GRAPH_BASE` | `https://graph.microsoft.com/v1.0` | `src/config.py:47` |
| `request_timeout` | env `OUTLOOK_TOOL_REQUEST_TIMEOUT` | `60.0` | `src/config.py:48` |
| `token_cache_path` | env `OUTLOOK_TOOL_TOKEN_CACHE_PATH` | `~/.cache/outlook-tool/token.json` | `src/config.py:24-25,51` |
| `attachment_inline_limit` | env `OUTLOOK_TOOL_ATTACHMENT_INLINE_LIMIT` | `3_000_000` bytes | `src/config.py:54` |
| `upload_chunk_size` | env `OUTLOOK_TOOL_UPLOAD_CHUNK_SIZE` | `3_276_800` bytes (multiple of 320 KiB) | `src/config.py:55-56` |
| `-v`/`-vv` | CLI flag (count) | silent (errors only) | `src/outlook_tool.py:72-77` |
| skill config dir | env `XDG_CONFIG_HOME` or `~/.config` | `~/.config/outlook-tool/` | `src/skill_cmd.py:27-33` |

## 6. Observability

Rich console handler (stderr) + file handler, mapped from `-v` count. OpenTelemetry tracer
provider with a JSONL file exporter by default (`src/tracing.py`); spans named
`api.graph` for every Graph call with attributes `http.method`, `graph.path`,
`http.status_code`, `graph.error` on failure (`src/graph_client.py:79-96`). No OTLP exporter
configured by default; AGENTS.md's referenced `OTEL_DESTINATION`/`OTEL_API_KEY` convention
was not found implemented in `src/tracing.py` or `src/config.py` for this project (see
backlog finding, doc claims only apply to the generic python skill template, not confirmed
as implemented here).

## 7. Decisions (observed)

| ID | Decision | Evidence | Rationale |
|---|---|---|---|
| DEC-001 | Use the public, multi-tenant Microsoft Office first-party client ID instead of registering a dedicated Azure AD app | `src/config.py:10-14` | Documented inline: "locked-down tenants rarely block the genuine Office client, unlike Azure CLI" |
| DEC-002 | Device-code flow instead of an interactive redirect-based OAuth flow | `src/auth.py:109-156` | Not documented beyond the obvious CLI constraint (no redirect URI to host); inferred from code shape, not asserted as a comment |
| DEC-003 | Token cache always written with `0600` via atomic replace | `src/auth.py:196-201` | Documented inline: "contains a refresh token" |
| DEC-004 | Log and trace files are always written regardless of console verbosity | `src/logging_config.py:10-11` (module docstring) | Documented: diagnosability after the fact |
| DEC-005 | `httpx`/`httpcore` loggers forced to WARNING | `src/logging_config.py:70-73` | Documented: avoid leaking upload-session URLs/tokens at INFO |

## 8. Requirement to code map

| Requirement | Files |
|---|---|
| SPEC-0001/FR-001 | `src/outlook_tool.py:111-121`, `src/auth.py:117-120` |
| SPEC-0001/FR-002 | `src/auth.py:138-156` |
| SPEC-0001/FR-003 | `src/outlook_tool.py:111-121`, `src/auth.py:196-201` |
| SPEC-0001/FR-004 | `src/auth.py:88-93` |
| SPEC-0001/FR-005 | `src/auth.py:94-97`, `src/auth.py:148-156` |
| SPEC-0001/FR-006 | `src/auth.py:163-165` |
| SPEC-0001/FR-007 | `src/outlook_tool.py:57-63`, `src/auth.py:98` |
| SPEC-0001/FR-008 | `src/auth.py:160` |
| SPEC-0001/FR-009 | `src/auth.py:184-190` |
| SPEC-0001/FR-010 | `src/outlook_tool.py:72-77`, `src/logging_config.py:22-27` |
| SPEC-0001/FR-011 | `src/outlook_tool.py:72-77`, `src/logging_config.py:22-27` |
| SPEC-0001/FR-012 | `src/logging_config.py:52-55`, `src/tracing.py:76-84` |
| SPEC-0001/FR-013 | `src/skill_cmd.py:57-78` |
| SPEC-0001/FR-014 | `src/skill_cmd.py:74-76` |
| SPEC-0001/FR-015 | `src/skill_cmd.py:80-99` |
| SPEC-0001/FR-016 | `src/skill_cmd.py:89-91` |
| SPEC-0001/FR-017 | `src/outlook_tool.py:104-106`, `src/version.py:9-12` |
