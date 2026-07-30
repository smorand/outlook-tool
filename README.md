# outlook-mail

Envoyer/lire des emails Outlook et gérer le calendrier depuis un compte Microsoft 365
**pro**, sans posséder d'app registration ni de client secret.

## Le problème résolu

Un compte pro verrouillé n'autorise pas toujours la création d'une app registration,
et Microsoft a supprimé l'authentification basique (SMTP AUTH souvent coupé). Impossible
donc d'utiliser un client secret classique.

La solution: OAuth2 **device code flow** avec un **client ID public first-party**
(Microsoft Office, `d3590ed6-52b3-4102-aeff-aad2292ab01c`). Aucun secret, aucune app à
enregistrer. Un login navigateur unique donne un token délégué + refresh token,
pré-consenti pour un large lot de scopes Graph (`Mail.ReadWrite`, `Mail.Send`,
`Calendars.ReadWrite`, ...). Les appels passent ensuite par **Microsoft Graph**.

Le refresh token est mis en cache (`~/.cache/outlook-mail/token.json`, permissions
`0600`) donc les exécutions suivantes sont non interactives jusqu'à révocation.

## Installation

```bash
make sync                 # installe les dépendances (uv)
make install              # installe l'outil 'outlook-mail' en global (uv tool)
```

## Utilisation

```bash
# 1. Login unique (ouvre le navigateur, MFA inclus)
outlook-mail login

# 2. Envoi HTML avec pièces jointes (destinataire répétable)
outlook-mail send \
  --to "Seb <seb.morand@gmail.com>" \
  --subject "Rapport" \
  --body "<h1>Salut</h1><p>Voici le doc.</p>" \
  --attach ./rapport.pdf --attach ./photo.jpg

# corps depuis un fichier, texte brut
outlook-mail send --to a@b.com -s "Note" --body-file note.txt --text

# 3. Lecture
outlook-mail mail list --top 10
outlook-mail mail read <message-id>

# 4. Calendrier
outlook-mail cal add --subject "Nuit" \
  --start 2026-07-29T03:00:00 --end 2026-07-29T03:30:00 \
  --attendee seb.morand@gmail.com
outlook-mail cal list --start 2026-07-29T00:00:00 --end 2026-07-30T00:00:00
outlook-mail cal update <event-id> --subject "Nuit v2"
outlook-mail cal delete <event-id>
```

Options globales: `-v` (debug), `-q` (warnings only).

## Pièces jointes lourdes

En dessous de ~3 Mo (configurable), l'envoi se fait en un seul appel `sendMail`.
Au-delà, l'outil crée un brouillon, uploade chaque pièce jointe via une **upload
session** (PUT par chunks de 320 Ko multiples), puis envoie le brouillon.

## Configuration (env `OUTLOOK_MAIL_*`)

| Variable | Défaut | Rôle |
|---|---|---|
| `OUTLOOK_MAIL_CLIENT_ID` | client Office public | client ID OAuth2 emprunté |
| `OUTLOOK_MAIL_SCOPES` | Mail + Calendars | scopes délégués demandés |
| `OUTLOOK_MAIL_TOKEN_CACHE_PATH` | `~/.cache/outlook-mail/token.json` | cache token (0600) |
| `OUTLOOK_MAIL_ATTACHMENT_INLINE_LIMIT` | `3000000` | seuil inline vs upload session |
| `OUTLOOK_MAIL_GRAPH_BASE` | `https://graph.microsoft.com/v1.0` | base Graph |

## Développement

```bash
make check      # lint + format + typecheck + security + tests (couverture >= 80%)
make test       # tests seuls
make run ARGS='--help'
```

Voir `AGENTS.md` pour l'architecture et `.agent_docs/` pour les détails.

## Limites

- Dépend d'un client ID Microsoft public: un tenant très strict peut le bloquer
  (politique de consentement d'apps). Testé OK sur un tenant M365 verrouillé standard.
- Non affilié à Microsoft. Usage personnel.
