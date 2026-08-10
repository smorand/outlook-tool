# Vérification e2e (réelle)

Ces tests touchent le vrai tenant et exigent un `outlook-tool login` interactif préalable
(le device code flow ouvre le navigateur). Les tests automatisés (`make test`) mockent
Graph et ne remplacent pas ces vérifications.

## Règles imposées

- **Destinataire unique**: `seb.morand@gmail.com`. Jamais un autre destinataire.
- **Vérification de réception**: via email-manager (Gmail perso). Charger le mode d'emploi
  avec `email-manager skill`, puis rechercher le mail reçu côté Gmail.
- **Calendrier**: événements de test placés **hier à 3h du matin** (creux, sans collision),
  invité unique `seb.morand@gmail.com`. Toujours supprimer l'événement après vérification.

## Mail

```bash
outlook-tool login            # une fois
outlook-tool send \
  --to seb.morand@gmail.com \
  --subject "e2e outlook-tool $(date +%s)" \
  --body "<h1>e2e</h1><p>test HTML</p>" \
  --attach ./README.md
```

Vérifier ensuite côté Gmail (email-manager) que le message est arrivé, HTML rendu,
pièce jointe présente. Tester aussi une pièce jointe > 3 Mo pour exercer l'upload session.

## Calendrier

Hier = `date -d yesterday +%Y-%m-%d` (ex: 2026-07-29). Créneau 03:00 -> 03:30.

```bash
# create
outlook-tool cal add --subject "e2e nuit" \
  --start 2026-07-29T03:00:00 --end 2026-07-29T03:30:00 \
  --attendee seb.morand@gmail.com
# note l'id retourné

# read
outlook-tool cal list --start 2026-07-29T00:00:00 --end 2026-07-30T00:00:00

# update
outlook-tool cal update <id> --subject "e2e nuit v2"

# delete (toujours nettoyer)
outlook-tool cal delete <id>
```

Vérifier l'invitation reçue côté `seb.morand@gmail.com` (email-manager) et l'absence de
résidu après `delete`.

## Réponse threadée (`draft --reply-to`)

Vérifie que Graph traite bien la réponse comme un vrai fil (pas un nouveau message qui
ressemble à une réponse). Le CLI ne remonte pas `conversationId` (pas dans le `$select`
de `mail get`) : il faut l'interroger directement sur Graph avec le token en cache pour
le comparer, ou se contenter de vérifier sujet + corps via `mail get --json`.

```bash
# 1. Message de référence que l'on contrôle entièrement
TS=$(date +%s)
outlook-tool send --to seb.morand@gmail.com --subject "e2e reply-to setup $TS" \
  --body "<p>Message de reference.</p>"

# 2. Retrouver son id (sentitems) et vérifier son conversationId directement sur Graph
outlook-tool mail list --folder sentitems --top 5 --json   # note l'id
python3 -c "
import json, urllib.request
token = json.load(open('$HOME/.cache/outlook-tool/token.json'))['access_token']
req = urllib.request.Request(
    'https://graph.microsoft.com/v1.0/me/messages/<ORIG_ID>?\$select=id,subject,conversationId',
    headers={'Authorization': f'Bearer {token}'})
print(urllib.request.urlopen(req).read().decode())
"

# 3. Créer le brouillon de réponse (jamais envoyé)
outlook-tool draft --reply-to <ORIG_ID> --body "<p>Ceci est un test e2e --reply-to.</p>"

# 4. Vérifier subject "RE: ", conversationId identique, corps = custom + citation (même script Graph direct)

# 5. Idem avec --reply-all
outlook-tool draft --reply-to <ORIG_ID> --reply-all --body "<p>Test reply-all.</p>"

# 6. Nettoyage : trash fonctionne aussi sur un brouillon (move vers deleteditems)
outlook-tool mail trash <draft_id>
outlook-tool mail trash <draft2_id>
outlook-tool mail trash <ORIG_ID>
```

Critères de succès validés (2026-08-10) : subject `RE: e2e reply-to setup <ts>`,
`conversationId` du brouillon strictement identique à celui du message d'origine, corps
HTML = `<body><p>texte custom</p><hr>...<div id="divRplyFwdMsg">From/Sent/To/Subject...` puis
le corps original cité en dessous (le texte custom est bien au-dessus de la citation, pas un
remplacement). `mail trash` accepte aussi bien un id de draft qu'un id de message normal.

## Checklist

- [ ] mail HTML reçu, rendu correct
- [ ] pièce jointe < 3 Mo reçue
- [ ] pièce jointe > 3 Mo reçue (upload session)
- [ ] event créé visible dans `cal list` + invitation reçue
- [ ] event modifié (sujet mis à jour)
- [ ] event supprimé (plus dans `cal list`)
- [ ] `draft --reply-to` : conversationId identique au message d'origine
- [ ] `draft --reply-to` : sujet préfixé "RE: " automatiquement
- [ ] `draft --reply-to --body ...` : texte custom prépendé au-dessus de la citation, citation intacte
- [ ] `draft --reply-to --reply-all` : brouillon créé avec le bon conversationId
