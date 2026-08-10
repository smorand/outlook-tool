# outlook-tool

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
make install   # installe la commande 'outlook-tool' (uv tool)
```

## Architecture (src/, layout flat)

- `outlook_tool.py` : entry point Typer. Commandes: `login`, `send`, `version`,
  `mail list|get|read|search|archive|move|trash|mark-read|mark-unread|flag|attachments|download`, `cal add|list|update|delete`,
  `skill|skill learn`. Injection de dépendances dans
  `_with_services` (crée httpx client, Authenticator, GraphClient, services).
- `config.py` : `Settings` (pydantic-settings, prefix `OUTLOOK_TOOL_`). Client ID Office
  public par défaut, scopes, chemin du cache token, seuils pièces jointes.
- `auth.py` : `Authenticator`. Device code flow, cache token (0600, écriture atomique),
  refresh silencieux. `get_access_token()` lève `LoginRequiredError` si pas de token.
- `graph_client.py` : `GraphClient`, wrapper httpx async qui injecte le bearer et lève
  `GraphError` sur statut >= 400. Param `authenticated=False` pour les PUT d'upload session.
- `models.py` : value models pydantic (`Recipient`, `Attachment`, `OutgoingMessage`,
  `MailSummary`, `AttachmentSummary`, `CalendarEventInput`, `CalendarEventSummary`) + sérialisation Graph.
- `services/mail.py` : `MailService`. Envoi inline (<= seuil) ou draft + upload session
  (> seuil). `create_draft` (message autonome). `create_reply_draft` (vraie réponse
  threadée via Graph `createReply`/`createReplyAll` : conversationId correct, sujet
  "RE: " auto, citation de l'original ; un corps custom est **prepend** au-dessus de la
  citation, jamais un remplacement, via PATCH). `list_messages` (option `unread_only`),
  `search_messages` ($search), `get_message`, `move_message`/`archive_message`/`trash_message`,
  `mark_read`, `flag_message`, `list_attachments`, `download_attachment` (contentBytes
  inline ou fallback `/$value`).
- `services/calendar.py` : `CalendarService`. `list_events` (calendarView + Prefer tz),
  `create_event`, `update_event`, `delete_event`.
- `skill_cmd.py` : commandes `skill` / `skill learn`. `skill.md` embarqué + concaténation
  des fichiers `~/.config/outlook-tool/*.md` (rules utilisateur).
- `skill.md` : mode d'emploi complet pour agents IA (style email-manager).
- `tracing.py`, `logging_config.py`, `version.py` : depuis le template python.

## Conventions

- Suit la skill `python` (async-first, Ruff, mypy strict, Typer, pydantic-settings, otel).
- `from __future__ import annotations` partout. Path/httpx en TYPE_CHECKING sauf quand
  pydantic (champ `Attachment.path`) ou Typer (options `--attach`) exigent le symbole au
  runtime (noqa TC003 ciblé).
- Jamais de secret en dur; le cache token vit hors du repo (`~/.cache/outlook-tool/`).
- Logs silencieux par défaut: sans flag = ERROR, `-v` = INFO, `-vv` = DEBUG (compteur Typer).
  Fichiers app + otel toujours écrits dans `~/.cache/outlook-tool/` (via `Settings.log_dir`).

## Quality Gate

`make check` avant chaque commit: lint, format-check, typecheck, security, test-cov (>=80%).
Couverture actuelle ~94%.

## Tests

- Unit/integration: `respx` mocke Graph et les endpoints OAuth. `StubAuth` évite le réseau
  pour les services. CLI testé via `typer.testing.CliRunner` + cache token seedé.
- Vérification e2e réelle (nécessite login interactif): voir `.agent_docs/e2e-testing.md`.

## Documentation Index

- `.agent_docs/auth-client-id.md` : risque de dépendance au client ID public Microsoft,
  détection d'un blocage tenant (codes AADSTS) et fallbacks.
- `.agent_docs/e2e-testing.md` : protocole de vérification e2e (mail + calendrier +
  `draft --reply-to`) via `seb.morand@gmail.com` et email-manager.
- `.agent_docs/python.md` : standards de code Python.
- `.agent_docs/makefile.md` : documentation du Makefile.
