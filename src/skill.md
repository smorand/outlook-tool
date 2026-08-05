# Outlook Mail (pro IBM) — Mode d'emploi pour agent

Ce document est imprimé par `outlook-tool skill`. Il décrit le workflow complet
de gestion des emails Outlook professionnels via le binaire `outlook-tool`, à
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
- Token mis en cache : `~/.cache/outlook-tool/token.json`
- **Reconnexion automatique** : le binaire rafraîchit silencieusement le token
  expiré. Si le refresh token est invalide, la commande échoue avec exit code 2
  et un message clair. L'agent doit alors demander à l'utilisateur de lancer
  `outlook-tool login` manuellement.

```bash
outlook-tool login   # ou re-login si token révoqué
```

## Commandes disponibles

```
outlook-tool
├── login                             # Authentification device-code interactive
├── version                           # Version du binaire
├── send                              # Envoyer un email
├── mail
│   ├── list [--top N] [--folder F] [--unread] [--json]
│   ├── get <id> [--json]             # Lire un message complet
│   ├── search <query> [--top N] [--json]
│   ├── read <id>                     # Afficher un message en texte plain (HTML strippé)
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
    ├── delete <id>
    └── accept <id>                   # Accepter une invitation de réunion (sans envoyer de réponse)
```

Toute commande accepte `--help` pour voir les options détaillées.

## Champs spéciaux dans les réponses JSON

### `mail list --json`
Chaque objet inclut `is_meeting_request: bool` — `true` quand le mail est une invitation de réunion (`eventMessageRequest`). Permet de détecter les invitations sans faire un `mail get` sur chaque mail.

### `mail get <id> --json`
Pour les invitations de réunion (`is_meeting_request: true`), le JSON inclut `startDateTime` et `endDateTime` (ISO 8601) donnant le créneau de l'événement. Évite de croiser avec `cal list` pour trouver les dates.

### `mail read <id>`
Retourne le corps en **texte plain** : si le contenu est HTML, les balises sont strippées automatiquement (stdlib `html.parser`). Plus besoin de post-traitement Python côté agent.

## Workflow type : résumé des non-lus

```bash
# 1. Lister les non-lus (inbox par défaut)
outlook-tool mail list --unread --top 50 --json

# 2. Pour un message à lire en détail
outlook-tool mail get <id> --json

# 3. Marquer comme lu après traitement
outlook-tool mail mark-read <id>

# 4. Archiver si traité
outlook-tool mail archive <id>

# 5. Flaguer si nécessite un suivi
outlook-tool mail flag <id>
```

## Workflow type : envoi

```bash
# Corps texte
outlook-tool send --to "alice@corp.com" --subject "CR réunion" --body "Bonjour..."

# Corps HTML
outlook-tool send --to "bob@corp.com" --subject "Rapport" --body "<h1>...</h1>" --html

# Avec pièce jointe
outlook-tool send --to "alice@corp.com" --subject "Rapport" --body "Voir PJ" \
  --attach rapport.pdf
```

## Workflow type : calendrier

```bash
# Voir les événements de la semaine
outlook-tool cal list --start 2026-07-28T00:00:00 --end 2026-08-04T00:00:00 --json

# Créer un événement
outlook-tool cal add --subject "Point équipe" --start 2026-08-04T10:00:00 \
  --end 2026-08-04T11:00:00 --attendee "alice@corp.com"

# Modifier
outlook-tool cal update <id> --subject "Point équipe (reporté)"

# Supprimer
outlook-tool cal delete <id>
```

## Workflow type : invitations de réunion

```bash
# 1. Détecter les invitations dans les non-lus
outlook-tool mail list --unread --top 50 --json
# -> filtrer sur is_meeting_request: true

# 2. Récupérer le créneau sans passer par cal list
outlook-tool mail get <id> --json
# -> startDateTime et endDateTime présents si is_meeting_request

# 3. Vérifier la dispo dans le calendrier
outlook-tool cal list --start <startDateTime> --end <endDateTime> --json

# 4a. Disponible : accepter + marquer lu + archiver
outlook-tool cal accept <event_id_from_cal_list>
outlook-tool mail mark-read <mail_id>
outlook-tool mail archive <mail_id>

# 4b. Conflit : signaler à l'utilisateur, ne pas toucher au mail
```

**Note :** `cal accept <id>` prend l'**event id** (calendrier), pas le mail id.
Récupérer l'event id via `cal list` sur le créneau de l'invitation.

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
outlook-tool skill learn --rule "Tous les emails de iec@us.ibm.com -> mark-read + archive (newsletters IBM internes)"
```

Avant d'exécuter `skill learn`, **toujours demander confirmation utilisateur**
avec la formulation exacte de la règle.

### Fichiers de connaissance utilisateur

Stockés dans `~/.config/outlook-tool/` et automatiquement concaténés à la
sortie de `outlook-tool skill` :

- `regles-tri.md` — règles de traitement par expéditeur / type
- `patterns-emails.md` — patterns pour identifier les types d'emails
- `filtres-evolutifs.md` — historique des filtres appris

Ces fichiers sont concaténés automatiquement à chaque appel à `outlook-tool skill`.

## Commandes d'envoi

```bash
# Envoyer directement
outlook-tool send \
  --to "Name <a@b.com>" --cc "c@d.com" \
  --subject "Sujet" \
  --body "<p>Corps HTML</p>" \
  --attach ./fichier.pdf

# Sauvegarder comme brouillon (à envoyer depuis Outlook)
outlook-tool draft \
  --to "Name <a@b.com>" --cc "c@d.com" \
  --subject "Sujet" \
  --body "<p>Corps HTML</p>" \
  --attach ./fichier.pdf
```

Préférer `draft` quand l'utilisateur veut relire avant envoi.

**IMPÉRATIF** : tout email envoyé via `outlook-tool send` doit être soigné visuellement.
L'outil envoie en HTML par défaut — en tirer parti systématiquement.

Règles à respecter :
- Utiliser des paragraphes `<p>` séparés, jamais un bloc de texte continu
- Structurer avec `<ol>` / `<ul>` quand il y a une liste de points
- Mettre en gras `<strong>` les éléments importants
- Les liens doivent être cliquables avec texte descriptif : `<a href="...">Nom du fichier</a>`, jamais une URL brute
- Terminer par une signature claire (`<p>Cordialement,<br>Sébastien</p>` ou équivalent)
- Aérer : un `<br>` entre la salutation et le corps, un `<br>` avant la signature

Exemple de structure minimale :
```html
<p>Bonjour Prénom,</p>

<p>Corps du message en un ou plusieurs paragraphes.</p>

<ol>
  <li>Point 1</li>
  <li>Point 2</li>
</ol>

<p>Lien : <a href="https://...">Nom du document</a></p>

<p>Cordialement,<br>Sébastien</p>
```

---

## Confirmation utilisateur OBLIGATOIRE avant action

- Envoi d'un email au nom de l'utilisateur
- Suppression vers la corbeille (`trash`)
- Marquage spam / déplacement hors inbox
- Toute réponse à un email confidentiel ou sensible (RH, juridique, finance)
