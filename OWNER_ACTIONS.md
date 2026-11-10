# Ejerhandlinger — integrationer og sikker drift

Contabo-serveren og Claude API er installeret og verificeret. Der er ikke foretaget OAuth eller social publicering. Del aldrig passwords, API-nøgler, client secrets eller refresh tokens i chat eller Git.

## 0. Kreativ status — voiceover godkendt

Kokoro-voiceover uden avatar er godkendt kreativt. Den aktuelle kandidat er `some-pilot/data/versions/handheld-voiceover-v1/video.mp4` på 102,1 sekunder med komplet claim- og voice-kontrol samt ti hash-verificerede manifestfiler. `handheld-zoom-v11` og `handheld-safe-v10` er kreative referencer. Ingen version er publiceret.

## 1. Cloudserver — købt, installeret og verificeret

**Driftsserver 2026-11-10:** Contabo Cloud VPS Plus 6 med EU-lokation og Ubuntu 24.04 LTS.

- 6 vCPU, 12 GB RAM, 300 GB NVMe, fem snapshots, 500 Mbit/s-port og ubegrænset trafik. Kontrolpanelet viser én måneds kontrakt og €23,75/måned, cirka 177 DKK. Endelig faktura og moms er ikke verificeret.
- Serveren overstiger det tidligere 150 DKK-loft. Efter ejerens besked om at fortsætte bruges den købte server; der skal ikke købes flere servere eller større API-pakker.
- Commit `9e194f3` er deployet, 73/73 tests bestod på serveren, web/worker er healthy, og en reel demovideo samt Kokoro-lyd er produceret og kontrolleret.
- SSH bruger separat ED25519-nøgle med fingeraftryk `SHA256:JlwDFKo3YXhjG1DAkgEgbY8B8otWKuiJEgT12w1kF4A`. Root- og passwordlogin over SSH er slået fra. UFW tillader kun SSH fra ejerens aktuelle admin-IP.
- Dashboardet er kun tilgængeligt via SSH-tunnel på `http://127.0.0.1:8000`. Bruger er `owner`; den tilfældige initialadgangskode ligger i root-beskyttet `/opt/some/secrets/initial-admin-password` på serveren.
- Krypteret backup og restore er verificeret. Contabos cloudfirewall og offsite backup mangler; der skal ikke købes Auto Backup uden ny prisafklaring.

Kokoro, Whisper og rendering kører lokalt på serveren. Claude API er verificeret til manuskripter og claimkontrol med Sonnet/Haiku og 50 DKK-loft. `PAID_JOBS_ENABLED=true`; `DRY_RUN=true` og `PUBLISH_ENABLED=false` ændres ikke uden separat privat uploadtest og ejergodkendelse.

## 2. Claude Console — samlet server- og API-budget

Links: https://platform.claude.com/docs/en/api/overview og https://console.anthropic.com/

- Opret ejerstyret organisation/projekt og aktivér API-betaling. Et Claude-chatabonnement er ikke API-forbrug.
- Appens standard er **50 DKK/måned** og maksimalt **5 DKK/job**. Konfigurér også udbyderens alarms/grænser, hvor de understøttes. Den købte server + appens API-loft er dermed cirka 227 DKK/måned.
- Opret først en projektspecifik nøgle efter accept af API-loftet. Indsæt den direkte i `/opt/some/secrets/app.env` med sikker editor/secret-manager — aldrig i chat eller Git.

Modelrouting kontrolleret i officiel dokumentation 2026-11-10:

- `claude-sonnet-5-5` til manuskripter: $2 input / $10 output pr. million tokens.
- `claude-haiku-5-5` til research og claimkontrol: $0,10 input / $0,50 output pr. million tokens ved prompts op til 100.000 tokens. Over 100.000 tokens er priserne $0,50 input / $2,50 output.

Kilder: https://platform.claude.com/docs/en/about-claude/pricing og https://contabo.com/en/vps/

### Estimat ved 30 videoer/måned

| Del | Forbrugsantagelse | USD/måned | Ca. DKK/måned |
|---|---|---:|---:|
| Købt Contabo Cloud VPS Plus 6 | €23,75 ifølge kontrolpanel | — | 176,94 |
| Haiku research | 20.000 input + 2.000 output pr. dag | $0,09 | 0,60 |
| Sonnet manuskripter | 8.000 input + 1.200 output pr. video | $0,84 | 5,60 |
| Haiku claimkontrol | 12.000 input + 700 output pr. video | $0,0465 | 0,31 |
| **API i alt** | | **$0,9765** | **6,51** |
| **Server + API** | | | **ca. 183,45** |
| **Med dobbelt API-forbrugslager** | retries og ekstra research | | **ca. 189,96** |

DKK-beregningen bruger 7,45 DKK/EUR og referencekursen 6,6661 DKK/USD fra https://api.frankfurter.app/latest?from=USD&to=DKK (2026-11-10). Det er et forbrugsestimat, ikke en verificeret faktura eller prisgaranti; faktisk pris afhænger af tokens, bankkurs, moms og fakturering. Selv med appens API-loft på 50 DKK bliver den samlede pris cirka 227 DKK/måned.

Produktionens fire DKK-priser er konfigureret: Sonnet `13.3322` input / `66.661` output og Haiku `0.66661` input / `3.33305` output pr. million tokens. API-nøglen er indsat uden at være vist, `PAID_JOBS_ENABLED=true`, og både healthchecks og komplet syntetisk manuskript → claimkontrol er bestået. Samlet testforbrug er 0,142267 DKK af 50 DKK.

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

- Den nye engelske platformpakke bruger lokal Kokoro `af_bella`. Espeak-ng og Microsoft Zira er kun fallbacks; dansk TTS er ikke kvalitetsgodkendt.
- Godkend hver færdig version i dashboardet efter at have set hele videoen. Ingen automatisk publicering af DEMO eller AWAITING_OWNER-versioner.
- Kontrollér konkrete stock-, gameplay-, musik- og personrettigheder pr. asset. Der findes ingen 10-sekundersregel.
- Vælg et faktisk affiliateprogram, dokumentér vilkår, provision og reklamemarkering. Ingen RPM, købsrate eller indtjening antages.
- Afklar reklamemarkering, skat/moms og juridiske fortolkninger med relevante fagpersoner før kommerciel lancering.
- `PAID_JOBS_ENABLED=true` er aktiveret efter budgettest. Aktivér `PUBLISH_ENABLED=true` og `DRY_RUN=false` først efter verificeret privat upload og konkret ejergodkendelse.
- HeyGen og synlige avatarer er udfaset. Kokoro er den lokale standardstemme. ElevenLabs er kun en valgfri provider og kræver særskilt ejeraccept af voice, kommercielle vilkår og pris før paid jobs aktiveres.

## Præcis næste handling

Claude API er verificeret. Næste enlige opgave er YouTube/Google: opret/vælg ejerens kanal og Google Cloud-projekt, aktivér YouTube Data API v3 og YouTube Analytics API og konfigurér ejerstyret OAuth med mindst mulige scopes. Første upload skal være PRIVATE med separat godkendelse. Indtil da bruges manuel eksport.
