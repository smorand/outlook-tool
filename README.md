# outlook-tool

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

Le refresh token est mis en cache (`~/.cache/outlook-tool/token.json`, permissions
`0600`) donc les exécutions suivantes sont non interactives jusqu'à révocation.

## Installation

```bash
make sync                 # installe les dépendances (uv)
make install              # installe l'outil 'outlook-tool' en global (uv tool)
```

## Utilisation

```bash
# 1. Login unique (ouvre le navigateur, MFA inclus)
outlook-tool login

# 2. Envoi HTML avec pièces jointes (destinataire répétable)
outlook-tool send \
  --to "Seb <seb.morand@gmail.com>" \
  --subject "Rapport" \
  --body "<h1>Salut</h1><p>Voici le doc.</p>" \
  --attach ./rapport.pdf --attach ./photo.jpg

# corps depuis un fichier, texte brut
outlook-tool send --to a@b.com -s "Note" --body-file note.txt --text

# 3. Lecture / recherche / rangement
outlook-tool mail list --top 10
outlook-tool mail list --json          # sortie JSON avec ids complets (scripting)
outlook-tool mail read <message-id>
outlook-tool mail search "from:alice subject:report" --top 10
outlook-tool mail archive <message-id>                 # -> dossier Archive
outlook-tool mail move <message-id> deleteditems       # dossier (nom connu ou id)

# Pièces jointes (lecture)
outlook-tool mail attachments <message-id>             # lister nom / taille / id
outlook-tool mail download <message-id> --out ~/Downloads          # télécharger les PJ
outlook-tool mail download <message-id> --name "rapport" --out .   # filtrer par nom

# Modifier puis envoyer un brouillon
outlook-tool draft-update <draft-id> --add-attach ./v2.pdf --remove-attach <att-id>
outlook-tool draft-update <draft-id> --body "<p>Corps corrigé.</p>"
outlook-tool draft-send <draft-id>

# 4. Calendrier
outlook-tool cal add --subject "Nuit" \
  --start 2026-07-29T03:00:00 --end 2026-07-29T03:30:00 \
  --attendee seb.morand@gmail.com
outlook-tool cal list --start 2026-07-29T00:00:00 --end 2026-07-30T00:00:00
outlook-tool cal list --start ... --end ... --json   # ids complets pour update/delete
outlook-tool cal update <event-id> --subject "Nuit v2"
outlook-tool cal add --subject "Congés" --start ... --end ... --category "Red category"
outlook-tool cal update <event-id> --category "Blue category"   # remplace toutes les catégories (couleur Outlook)
outlook-tool cal update <event-id> --clear-categories            # retire toute catégorie
outlook-tool cal delete <event-id>
```

Verbosité (silencieux par défaut): sans flag = erreurs seulement, `-v` = info, `-vv` = debug.
Les logs (app + OpenTelemetry) sont toujours écrits dans `~/.cache/outlook-tool/`
(`outlook-tool.log`, `outlook-tool-otel.log`), quel que soit le niveau console.

Les tableaux tronquent les ids pour
la lisibilité ; utilise `--json` sur `mail list` / `cal list` pour récupérer les ids complets
à passer à `read` / `update` / `delete`.

## Pièces jointes lourdes

En dessous de ~3 Mo (configurable), l'envoi se fait en un seul appel `sendMail`.
Au-delà, l'outil crée un brouillon, uploade chaque pièce jointe via une **upload
session** (PUT par chunks de 320 Ko multiples), puis envoie le brouillon.

## Configuration (env `OUTLOOK_TOOL_*`)

| Variable | Défaut | Rôle |
|---|---|---|
| `OUTLOOK_TOOL_CLIENT_ID` | client Office public | client ID OAuth2 emprunté |
| `OUTLOOK_TOOL_SCOPES` | Mail + Calendars | scopes délégués demandés |
| `OUTLOOK_TOOL_TOKEN_CACHE_PATH` | `~/.cache/outlook-tool/token.json` | cache token (0600) |
| `OUTLOOK_TOOL_ATTACHMENT_INLINE_LIMIT` | `3000000` | seuil inline vs upload session |
| `OUTLOOK_TOOL_GRAPH_BASE` | `https://graph.microsoft.com/v1.0` | base Graph |

## Développement

```bash
make check      # lint + format + typecheck + security + tests (couverture >= 80%)
make test       # tests seuls
make run ARGS='--help'
```

Voir `AGENTS.md` pour l'architecture et `.agent_docs/` pour les détails.

## Limites et risque principal

**Dépendance à un client ID Microsoft public.** L'outil emprunte le client ID public de
Microsoft Office plutôt que d'enregistrer sa propre app. Un tenant peut bloquer ce client
(politique de consentement d'apps, Conditional Access, blocage du device code flow).
Le client Office passe sur la plupart des tenants et a été testé OK sur un M365 verrouillé
standard, mais ce n'est pas garanti et un admin peut durcir la politique à tout moment:
l'outil cesserait alors de fonctionner sans changement de code.

Détection, codes d'erreur AADSTS et fallbacks (autre client ID, ta propre app publique,
plan B navigateur) sont détaillés dans **`.agent_docs/auth-client-id.md`**. La solution
stable qui supprime ce risque: enregistrer ta propre app publique (sans secret) et poser
`OUTLOOK_TOOL_CLIENT_ID=<ton-app-id>`.

Autres: non affilié à Microsoft, usage personnel.
