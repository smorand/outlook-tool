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

## Checklist

- [ ] mail HTML reçu, rendu correct
- [ ] pièce jointe < 3 Mo reçue
- [ ] pièce jointe > 3 Mo reçue (upload session)
- [ ] event créé visible dans `cal list` + invitation reçue
- [ ] event modifié (sujet mis à jour)
- [ ] event supprimé (plus dans `cal list`)
