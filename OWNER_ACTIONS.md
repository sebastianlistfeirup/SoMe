# Ejerhandlinger — først når den lokale leverance er gennemgået

Der er ikke foretaget køb, login, OAuth, betalte API-kald eller offentlig publicering. Del aldrig passwords, API-nøgler, client secrets eller refresh tokens i chat eller Git.

## 0. Lokal diskblokering

Docker-rapporteringen viste 8. november 2026 ca. 34–36 GB fri plads og over 99 % forbrug. Systemet stopper derfor nye renderjobs som designet. Frigør tilstrækkelig plads på det valgte rendermiljø, eller fortsæt på den godkendte VPS. Ændr ikke 90 %-grænsen for at fremtvinge produktion. Kør derefter `doctor` og demo-pipeline igen.

## 1. Cloudserver og pris — godkendelse før køb

Link: https://www.hetzner.com/cloud/ og https://console.hetzner.cloud/

- Opret ejerstyret konto, betalingsmiddel, eventuel identitetskontrol og 2FA.
- Projekt: `some-pilot`; EU-lokation; Ubuntu 24.04 LTS.
- Vælg shared x86-64 med ca. 4 vCPU, 8 GB RAM og mindst 80 GB SSD. CPX32 er kun et udgangspunkt; brug aktuel tilgængelighed.
- Vælg backup og beslut IPv4. Inkludér moms, timepris, trafik, lager og backup i den samlede pris.
- Mål: højst 375 DKK/måned eksklusive Claude, men det er endnu ikke en autorisation.

**Prisstatus 2026-11-08:** Hetzners side viste CPX02 til €5,99/måned ekskl. moms, men den er for lille. En gyldig total for den valgte 4-vCPU/8-GB-server kunne ikke dokumenteres uden konto/token. Der må derfor ikke købes på baggrund af tredjepartspriser. Udfyld den konkrete konsole-pris og godkend den før bestilling.

Alternativer hvis pris/tilgængelighed er dårlig: https://www.scaleway.com/en/pricing/ og https://www.digitalocean.com/pricing

Efter godkendelse: opret separat SSH-nøgle lokalt, upload kun `.pub`, kontrollér hostfingerprint og brug `some-pilot/scripts/install.sh`. Verificér nyt `deploy`-login før SSH root/password-login deaktiveres. Angiv `ADMIN_IP` og konfigurér både cloudfirewall og UFW.

## 2. Claude Console — separat API-budget

Links: https://platform.claude.com/docs/en/api/overview og https://console.anthropic.com/

- Opret ejerstyret organisation/projekt og aktivér API-betaling. Et Claude-chatabonnement er ikke API-forbrug.
- Sæt appens foreslåede loft til 150 DKK/måned og maksimalt 5 DKK/job; konfigurér også udbyderens alarms/grænser.
- Opret projektspecifik nøgle og indsæt den direkte i `/opt/some/secrets/app.env` med sikker editor/secret-manager.

Modelkandidater kontrolleret i officiel dokumentation 2026-11-08:

- `claude-haiku-5-5`: $0,10 input / $0,50 output pr. million tokens for prompts op til 100.000. Kandidat til klassifikation/ekstraktion.
- `claude-sonnet-5-5`: $2 input / $10 output pr. million tokens. Kandidat til bedre manuskriptkvalitet.

Kilder: https://platform.claude.com/docs/en/models/overview og https://platform.claude.com/docs/en/about-claude/pricing

Appen kræver verificerede DKK-priser i `CLAUDE_INPUT_DKK_PER_MILLION` og `CLAUDE_OUTPUT_DKK_PER_MILLION`. Omregn med en dokumenteret valutakurs på konfigurationsdagen. Start med små evals, og vælg den billigste model der består. Betalte jobs forbliver `false`, indtil dette er godkendt.

## 3. YouTube/Google — research, OAuth og privat test

Links: https://console.cloud.google.com/ og https://developers.google.com/youtube/data/reference/rest/v3/videos/insert

- Opret/vælg ejerens kanal og Google Cloud-projekt.
- Aktivér YouTube Data API v3 og YouTube Analytics API.
- Konfigurér OAuth consent screen og en understøttet klienttype med præcis redirect-URL.
- Brug mindst mulige scopes; kanalens ejer skal gennemføre samtykke. Service account er ikke en erstatning.
- Indsæt API-nøgle, client ID/secret og refresh token sikkert i serverens secret-fil.
- Test først læseadgang og kanalidentitet. Upload derefter en egen/syntetisk video som eksplicit `PRIVATE` med separat godkendelse.
- Kontrollér fil, konto, privacy og metadata i kanalen. Først derefter markeres privat upload som verificeret.
- Importér Google Trends manuelt for den valgte niche: https://trends.google.com/trends/

## 4. Instagram/Meta — anden platform

Links: https://developers.facebook.com/docs/instagram-platform/ og https://developers.facebook.com/apps/

- Opret/vælg ejerens Instagram Professional-konto og Meta-udviklerapp.
- Vælg aktuel understøttet loginvariant, nødvendige scopes og præcis redirect-URL.
- Gennemfør ejer-OAuth og test container/mediaflow på den rigtige konto.
- Meta kan kræve offentlig HTTPS-medie-URL. Det tidsbegrænsede signerede link er implementeret; konfigurér `PUBLIC_BASE_URL` og aktuel `META_GRAPH_VERSION` først efter konkret domæne-/sikkerhedsbeslutning.
- Brug indtil da ZIP-eksport. En Instagram-status siger intet om Facebook, som ikke er implementeret som aktiv adapter.

## 5. Backup og offsite lager

- Vælg separat lager med dokumenteret pris og sikker adgang.
- Generér en Fernet-kompatibel backupnøgle lokalt og gem den separat fra serveren.
- Uden `BACKUP_KEY` er lokale ZIP-backups ukrypterede og ikke produktionsgodkendte.
- Konfigurér offsite-overførsel først efter leverandørvalg. Behold 7 daglige + 4 ugentlige kopier og udfør restoretest i separat mappe.

## 6. Kvalitet, rettigheder og kommerciel lancering

- Godkend engelsk speak på en 20-sekunders prøve. Espeak-ng er kun en funktionel demo; Kokoro/dansk TTS er ikke antaget understøttet.
- Godkend hver færdig version i dashboardet efter at have set hele videoen. Ingen automatisk publicering af DEMO.
- Kontrollér konkrete stock-, gameplay-, musik- og personrettigheder pr. asset. Der findes ingen 10-sekundersregel.
- Vælg et faktisk affiliateprogram, dokumentér vilkår, provision og reklamemarkering. Ingen RPM, købsrate eller indtjening antages.
- Afklar reklamemarkering, skat/moms og juridiske fortolkninger med relevante fagpersoner før kommerciel lancering.
- Aktivér først `PAID_JOBS_ENABLED=true` efter budgettest. Aktivér `PUBLISH_ENABLED=true` og `DRY_RUN=false` først efter verificeret privat upload og konkret ejergodkendelse.

## Præcis næste handling

Start med punkt 0 eller en prisgodkendt VPS. Derefter kan den fulde mediepipeline køres og benchmarkes. Kontopunkterne kan derefter klares samlet uden at ændre arkitekturen.
