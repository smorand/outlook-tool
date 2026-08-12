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
├── draft                             # Sauvegarder un brouillon (--reply-to pour une réponse threadée)
├── draft-update <id>                 # Modifier un brouillon : corps (remplacement), PJ (--add-attach/--remove-attach)
├── draft-send <id>                   # Envoyer un brouillon déjà créé/validé
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
│   ├── flag <id> [--unflag]          # Marquer / démarquer avec un flag (suivi)
│   ├── attachments <id> [--json]     # Lister les pièces jointes (nom, taille, id)
│   └── download <id> [--out DIR] [--name TEXTE] [--include-inline]  # Télécharger les PJ
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

## Workflow type : pièces jointes

Ne JAMAIS lire le token en clair ni bricoler du curl/base64. Utilise ces commandes.

```bash
# Lister les PJ d'un message (les inline comme image001.jpg sont marquées inline)
outlook-tool mail attachments <id>
outlook-tool mail attachments <id> --json     # ids complets pour scripting

# Télécharger toutes les PJ non-inline dans ~/Downloads
outlook-tool mail download <id> --out ~/Downloads

# Télécharger seulement celles dont le nom contient un texte
outlook-tool mail download <id> --name "Portefeuille" --out ~/Downloads

# Inclure aussi les images inline
outlook-tool mail download <id> --include-inline --out ~/Downloads
```

Sans `--out`, le téléchargement va dans le dossier courant. Les gros fichiers (contentBytes
absent) sont récupérés via l'endpoint `/$value` automatiquement.

## Impératif : toujours vérifier la date du jour avant une opération temporelle

**Avant tout `cal list`/`cal add`/`cal update` avec une date relative** ("aujourd'hui",
"demain", "cette semaine", "lundi prochain", "dans 2h"...), **et avant tout `mail
list`/`mail search`/`mail get` filtré sur une période relative** ("hier", "cette
semaine", "le mois dernier"...) : lancer la commande shell `date` pour connaître la
date et l'heure exactes du jour, puis calculer les bornes ISO 8601 à partir de cette
date réelle.

Ne jamais déduire ou supposer la date actuelle à partir de la mémoire d'entraînement
ou d'une date vue plus tôt dans la conversation : elle peut être fausse ou périmée, et
une erreur ici crée un événement au mauvais jour ou rate les mails de la bonne période
sans qu'aucune erreur ne soit remontée par l'outil (Graph répond normalement sur une
plage de dates incorrecte, avec une liste vide ou décalée).

```bash
date                                   # ex: Wed Aug 12 21:46:46 CEST 2026
# -> "aujourd'hui" = 2026-08-12, "demain" = 2026-08-13, "cette semaine" = lundi 2026-08-10
#    à dimanche 2026-08-16, "hier" = 2026-08-11, etc.
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

## Workflow type : modifier puis envoyer un draft

```bash
# 1. Créer le brouillon
outlook-tool draft --to "alice@corp.com" --subject "Rapport" --body "<p>...</p>"
# -> id du draft retourné (ex: AAMkAG...)

# 2. Lister les PJ actuelles si besoin de savoir quoi retirer
outlook-tool mail attachments <draft_id>              # donne les attachment id pour --remove-attach

# 3. Ajouter/retirer des pièces jointes (les deux options sont cumulables en un appel)
outlook-tool draft-update <draft_id> --add-attach rapport-v2.pdf --remove-attach <old_att_id>

# 4. Corriger le corps (remplacement complet, pas un ajout)
outlook-tool draft-update <draft_id> --body "<p>Corps corrigé.</p>"

# 5. Envoyer une fois relu et validé par l'utilisateur
outlook-tool draft-send <draft_id>
```

`draft-update` exige au moins une action (`--body`/`--body-file`, `--add-attach` ou
`--remove-attach`), sinon il échoue avec exit code 2. `--remove-attach` prend l'**id
d'attachment** Graph (visible via `mail attachments <id>`), pas l'id du message. Il ne
touche jamais au sujet ni aux destinataires — utiliser `draft` (nouveau brouillon) ou
`draft --reply-to` pour ça.

**IMPÉRATIF** : `draft-send` envoie un email au nom de l'utilisateur — confirmation
obligatoire avant l'appel (voir section finale).

## Workflow type : répondre à un mail (vraie réponse threadée)

`draft --reply-to <id>` crée une **vraie réponse** via Graph (`createReply` /
`createReplyAll`), pas un nouveau message qui ressemble à une réponse : le brouillon
généré a le bon `conversationId`, un sujet "RE: ..." automatique, et cite déjà le
message d'origine. Il apparaît nesté sous le mail d'origine dans Outlook.

```bash
# Réponse simple à l'expéditeur, avec un texte au-dessus de la citation
outlook-tool draft --reply-to <message_id> --body "<p>Merci, je regarde ça.</p>"

# Répondre à tous (expéditeur + tous les destinataires du mail d'origine)
outlook-tool draft --reply-to <message_id> --reply-all --body "<p>Pour info...</p>"

# Réponse sans texte custom : juste la citation auto-générée par Graph, à compléter dans Outlook
outlook-tool draft --reply-to <message_id>

# Override des destinataires/sujet auto-remplis par Graph (rare)
outlook-tool draft --reply-to <message_id> --to "autre@corp.com" --subject "Sujet custom"
```

**IMPORTANT** : `--body` est **ajouté au-dessus** de la citation déjà générée par
Graph, jamais un remplacement — sinon la réponse perd tout son lien avec le fil de
discussion. Avec `--reply-to`, `--to` et `--subject` deviennent optionnels (Graph les
remplit automatiquement) ; sans `--reply-to`, ils restent obligatoires comme pour un
`draft`/`send` classique. `--reply-all` n'a de sens qu'avec `--reply-to`.

**IMPÉRATIF — HTML obligatoire** : tout email pro (`send`, `draft`, `draft-update`)
doit être écrit en HTML, **jamais `--text`**. Outlook casse la présentation d'un corps
plain-text (pas de mise en forme, citations mal rendues, liens non cliquables). L'outil
envoie en HTML par défaut ; ne jamais passer `--text` sur un email destiné à être lu
dans Outlook.

Règles à respecter :
- Utiliser des paragraphes `<p>` séparés, jamais un bloc de texte continu
- Structurer avec `<ol>` / `<ul>` quand il y a une liste de points
- Mettre en gras `<strong>` les éléments importants
- Les liens doivent être cliquables avec texte descriptif : `<a href="...">Nom du fichier</a>`, jamais une URL brute
- Terminer par la signature pro (voir section suivante)
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

<p>--<br>
Associate Partner Chief Architect IBM - Strategic AI Partners<br>
IBM France - Consulting<br>
17, avenue de l'Europe, 92275 Bois-Colombes Cedex<br>
Tél : +33 6 12 03 41 15</p>
```

## Signature pro obligatoire

Tout email envoyé ou mis en brouillon pour l'utilisateur (`send`, `draft`,
`draft-update`) doit se terminer par cette signature HTML, ajoutée par l'agent dans le
corps **avant** l'appel à la commande (l'outil ne l'insère jamais automatiquement) :

```html
<p>--<br>
Associate Partner Chief Architect IBM - Strategic AI Partners<br>
IBM France - Consulting<br>
17, avenue de l'Europe, 92275 Bois-Colombes Cedex<br>
Tél : +33 6 12 03 41 15</p>
```

Ne pas la dupliquer si le corps existant en contient déjà une (cas d'une citation de
reply qui inclurait déjà la signature du message précédent, ou d'un `draft-update` sur
un brouillon qui l'a déjà). Vérifier le corps actuel avant d'ajouter la signature.

---

## Confirmation utilisateur OBLIGATOIRE avant action

- Envoi d'un email au nom de l'utilisateur (`send`, ou `draft-send` sur un brouillon)
- Suppression vers la corbeille (`trash`)
- Marquage spam / déplacement hors inbox
- Toute réponse à un email confidentiel ou sensible (RH, juridique, finance)
