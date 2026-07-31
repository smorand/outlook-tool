# Outlook Mail (pro IBM) — Mode d'emploi pour agent

Ce document est imprimé par `outlook-mail skill`. Il décrit le workflow complet
de gestion des emails Outlook professionnels via le binaire `outlook-mail`, à
destination d'un agent (Claude, Cursor, etc.) qui doit assister l'utilisateur.

## Quand utiliser

Déclencheurs typiques (français) :

- "scanner / trier / gérer mes mails pro"
- "envoyer un email / mail pro"
- "cherche / trouve / lis un mail professionnel"
- "mes non-lus pro", "résumé des mails IBM"
- "mail de X chez IBM", "mail d'un collègue"
- "agenda / calendrier / réunion pro"
- "ajouter / modifier / supprimer un event"

Pour les emails **personnels** (Gmail), utiliser `email-manager` à la place.

## Authentification

- Flow OAuth2 device-code (client public Microsoft Office, aucun secret).
- Token mis en cache : `~/.cache/outlook-mail/token.json`
- **Reconnexion automatique** : le binaire rafraîchit silencieusement le token
  expiré. Si le refresh token est invalide, la commande échoue avec exit code 2
  et un message clair. L'agent doit alors demander à l'utilisateur de lancer
  `outlook-mail login` manuellement.

```bash
outlook-mail login   # ou re-login si token révoqué
```

## Commandes disponibles

```
outlook-mail
├── login                             # Authentification device-code interactive
├── version                           # Version du binaire
├── send                              # Envoyer un email
├── mail
│   ├── list [--top N] [--folder F] [--unread] [--json]
│   ├── get <id> [--json]             # Lire un message complet
│   ├── search <query> [--top N] [--json]
│   ├── read <id>                     # Afficher un message (corps complet)
│   ├── mark-read <id>                # Marquer comme lu
│   ├── mark-unread <id>              # Marquer comme non lu
│   ├── archive <id>                  # Archiver (déplacer vers Archive)
│   ├── move <id> <destination>       # Déplacer vers un dossier
│   ├── trash <id>                    # Mettre à la corbeille
│   └── flag <id> [--unflag]          # Marquer / démarquer avec un flag (suivi)
└── cal
    ├── list --start ISO --end ISO [--tz TZ] [--json]
    ├── add --subject ... --start ISO --end ISO [--tz TZ] [--location ...] [--body ...] [--attendee ...]
    ├── update <id> [--subject ...] [--start ISO] [--end ISO] [--tz TZ]
    └── delete <id>
```

Toute commande accepte `--help` pour voir les options détaillées.

## Workflow type : résumé des non-lus

```bash
# 1. Lister les non-lus (inbox par défaut)
outlook-mail mail list --unread --top 50 --json

# 2. Pour un message à lire en détail
outlook-mail mail get <id> --json

# 3. Marquer comme lu après traitement
outlook-mail mail mark-read <id>

# 4. Archiver si traité
outlook-mail mail archive <id>

# 5. Flaguer si nécessite un suivi
outlook-mail mail flag <id>
```

## Workflow type : envoi

```bash
# Corps texte
outlook-mail send --to "alice@corp.com" --subject "CR réunion" --body "Bonjour..."

# Corps HTML
outlook-mail send --to "bob@corp.com" --subject "Rapport" --body "<h1>...</h1>" --html

# Avec pièce jointe
outlook-mail send --to "alice@corp.com" --subject "Rapport" --body "Voir PJ" \
  --attach rapport.pdf
```

## Workflow type : calendrier

```bash
# Voir les événements de la semaine
outlook-mail cal list --start 2026-07-28T00:00:00 --end 2026-08-04T00:00:00 --json

# Créer un événement
outlook-mail cal add --subject "Point équipe" --start 2026-08-04T10:00:00 \
  --end 2026-08-04T11:00:00 --attendee "alice@corp.com"

# Modifier
outlook-mail cal update <id> --subject "Point équipe (reporté)"

# Supprimer
outlook-mail cal delete <id>
```

## Dossiers bien connus (--folder et move)

| Nom                | Description              |
|--------------------|--------------------------|
| `inbox`            | Boîte de réception       |
| `archive`          | Archive                  |
| `deleteditems`     | Corbeille                |
| `junkemail`        | Courrier indésirable     |
| `drafts`           | Brouillons               |
| `sentitems`        | Éléments envoyés         |

## Bilan de fin de traitement

Format type à produire à l'utilisateur après un scan des non-lus :

```
📧 Scan des emails pro terminé

✅ Actions effectuées :
- 5 emails marqués lus (newsletters IBM internes)
- 3 emails archivés (notifications automatiques)
- 1 email flagué pour suivi (RFP Accor)

⚠️ Nécessitent attention :
- Candidature alternance IA : réponse en attente (Audrey Thach)
- ACCOR AIFastTrack : questions techniques à traiter (Olivier Cales)

📊 Total : 9 emails traités
```

## Apprentissage de règles : `skill learn`

Quand l'utilisateur dit "ces mails tu peux toujours les traiter comme ça" ou
autre connaissance permanente, persister la règle :

```bash
outlook-mail skill learn --rule "Tous les emails de iec@us.ibm.com -> mark-read + archive (newsletters IBM internes)"
```

Avant d'exécuter `skill learn`, **toujours demander confirmation utilisateur**
avec la formulation exacte de la règle.

### Fichiers de connaissance utilisateur

Stockés dans `~/.config/outlook-mail/` et automatiquement concaténés à la
sortie de `outlook-mail skill` :

- `regles-tri.md` — règles de traitement par expéditeur / type
- `patterns-emails.md` — patterns pour identifier les types d'emails
- `filtres-evolutifs.md` — historique des filtres appris

Ces fichiers sont concaténés automatiquement à chaque appel à `outlook-mail skill`.

## Confirmation utilisateur OBLIGATOIRE avant action

- Envoi d'un email au nom de l'utilisateur
- Suppression vers la corbeille (`trash`)
- Marquage spam / déplacement hors inbox
- Toute réponse à un email confidentiel ou sensible (RH, juridique, finance)
