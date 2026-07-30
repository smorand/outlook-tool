# outlook-mail

## Overview

CLI Python (async, Typer) pour envoyer/lire du mail Outlook et gérer le calendrier via
Microsoft Graph, sans app registration ni client secret. Auth = OAuth2 device code flow
avec le client ID public Microsoft Office, token+refresh mis en cache sur disque.

Stack: Python 3.13+, Typer, httpx (async), pydantic/pydantic-settings, OpenTelemetry, uv.

## Key Commands

```
make sync      # installe les dépendances (uv)
make check     # quality gate: lint, format-check, typecheck, security, test-cov (>=80%)
make test      # tests
make run ARGS='send --to ... --subject ...'
make install   # installe la commande 'outlook-mail' (uv tool)
```

## Architecture (src/, layout flat)

- `outlook_mail.py` : entry point Typer. Commandes: `login`, `send`, `version`,
  `mail list|read`, `cal add|list|update|delete`. Injection de dépendances dans
  `_with_services` (crée httpx client, Authenticator, GraphClient, services).
- `config.py` : `Settings` (pydantic-settings, prefix `OUTLOOK_MAIL_`). Client ID Office
  public par défaut, scopes, chemin du cache token, seuils pièces jointes.
- `auth.py` : `Authenticator`. Device code flow, cache token (0600, écriture atomique),
  refresh silencieux. `get_access_token()` lève `LoginRequiredError` si pas de token.
- `graph_client.py` : `GraphClient`, wrapper httpx async qui injecte le bearer et lève
  `GraphError` sur statut >= 400. Param `authenticated=False` pour les PUT d'upload session.
- `models.py` : value models pydantic (`Recipient`, `Attachment`, `OutgoingMessage`,
  `MailSummary`, `CalendarEventInput`, `CalendarEventSummary`) + sérialisation Graph.
- `services/mail.py` : `MailService`. Envoi inline (<= seuil) ou draft + upload session
  (> seuil). `list_messages`, `get_message`.
- `services/calendar.py` : `CalendarService`. `list_events` (calendarView + Prefer tz),
  `create_event`, `update_event`, `delete_event`.
- `tracing.py`, `logging_config.py`, `version.py` : depuis le template python.

## Conventions

- Suit la skill `python` (async-first, Ruff, mypy strict, Typer, pydantic-settings, otel).
- `from __future__ import annotations` partout. Path/httpx en TYPE_CHECKING sauf quand
  pydantic (champ `Attachment.path`) ou Typer (options `--attach`) exigent le symbole au
  runtime (noqa TC003 ciblé).
- Jamais de secret en dur; le cache token vit hors du repo (`~/.cache/outlook-mail/`).

## Quality Gate

`make check` avant chaque commit: lint, format-check, typecheck, security, test-cov (>=80%).
Couverture actuelle ~94%.

## Tests

- Unit/integration: `respx` mocke Graph et les endpoints OAuth. `StubAuth` évite le réseau
  pour les services. CLI testé via `typer.testing.CliRunner` + cache token seedé.
- Vérification e2e réelle (nécessite login interactif): voir `.agent_docs/e2e-testing.md`.

## Documentation Index

- `.agent_docs/e2e-testing.md` : protocole de vérification e2e (mail + calendrier) via
  `seb.morand@gmail.com` et email-manager.
- `.agent_docs/python.md` : standards de code Python.
- `.agent_docs/makefile.md` : documentation du Makefile.
