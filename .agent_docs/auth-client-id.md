# Dépendance au client ID public (risque et fallbacks)

## Le risque

`outlook-tool` n'enregistre pas sa propre app Azure AD. Il **emprunte** un client ID
Microsoft first-party public, par défaut celui de Microsoft Office
(`d3590ed6-52b3-4102-aeff-aad2292ab01c`), et obtient un token délégué via device code flow.

Ce client ID ne nous appartient pas. Un tenant Microsoft 365 peut décider de bloquer les
apps tierces/non approuvées via:

- **App consent policy** / restriction d'applications d'entreprise,
- **Conditional Access** ciblant l'app ou le type de client,
- désactivation du device code flow (`Block device code flow` dans les Authentication
  Methods policies).

Le client Office passe sur la plupart des tenants (le bloquer casserait les vraies apps
Office), mais ce n'est **pas garanti**. Testé OK sur un tenant M365 verrouillé standard.
Rien n'empêche un admin de durcir la politique plus tard: l'outil peut cesser de marcher
du jour au lendemain, sans changement de code de notre part.

## Comment détecter le blocage

Au `outlook-tool login`, le blocage apparaît **côté navigateur** (message d'erreur
"Need admin approval" / "AADSTS65004" / "AADSTS7000112" ou équivalent), pas forcément dans
le terminal: quand l'admin refuse, l'endpoint device code reste souvent en
`authorization_pending` jusqu'à expiration. La source de vérité est le navigateur.

Codes typiques:

- `AADSTS65001` / `AADSTS65004` : consentement requis / refusé par l'utilisateur ou l'admin.
- `AADSTS7000112` : application désactivée dans le tenant.
- `AADSTS50059` / `AADSTS900023` : problème de tenant.
- `AADSTS70016` (`authorization_pending`) : normal pendant l'attente; anormal s'il ne
  finit jamais alors que le navigateur affiche une erreur.

## Fallbacks (par ordre de préférence)

1. **Changer de client ID public.** Essayer un autre first-party/public connu via
   l'environnement, sans toucher au code:

   ```bash
   # Azure CLI (souvent bloqué sur tenants stricts, mais à tester)
   OUTLOOK_TOOL_CLIENT_ID=04b07795-8ddb-461a-bbee-02f9e1bf7b46 outlook-tool login
   # Thunderbird (scopes SMTP/IMAP/POP surtout, pas idéal pour Graph)
   OUTLOOK_TOOL_CLIENT_ID=9e5f94bc-e8a4-4e73-b8be-63364c29d753 outlook-tool login
   ```

2. **Enregistrer ta propre app publique** (si tu obtiens le droit, même sans secret):
   App Registration → type "public client / mobile & desktop", activer "Allow public
   client flows", scopes délégués `Mail.ReadWrite`, `Mail.Send`, `Calendars.ReadWrite`.
   Puis `OUTLOOK_TOOL_CLIENT_ID=<ton-app-id>`. C'est la solution stable et propre: elle
   supprime entièrement ce risque.

3. **Plan B navigateur (non implémenté).** Si tout token OAuth est refusé mais qu'OWA
   fonctionne dans le navigateur, rejouer l'API interne OWA en réutilisant la session
   (cookies + canary `X-OWA-CANARY`). Fragile, non documenté par Microsoft, à ne faire
   qu'en dernier recours. Voir l'historique de conception du projet.

## Où c'est configuré

`src/config.py`: `DEFAULT_OFFICE_CLIENT_ID`, `DEFAULT_SCOPES`. Surchargeable par
`OUTLOOK_TOOL_CLIENT_ID` et `OUTLOOK_TOOL_SCOPES` (voir README).
