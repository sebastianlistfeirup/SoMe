# Ejerhandlinger — integrationer og sikker drift

Contabo-serveren, Claude, YouTube, Instagram, Facebook og TikTok Sandbox er forbundet og verificeret med ejerens konti. Del aldrig passwords, API-nøgler, client secrets eller refresh tokens i chat eller Git.

## 0. Kreativ status — voiceover afvist

**Kokoro `af_bella` er ikke godkendt kreativt. Ejeren afviser stemmen, og den må ikke bruges til nye produktionsopslag.** Der skal vælges og godkendes separate stemmer til gaming og AI. Eksisterende testopslag var kun integrations-/tekniske tests og er ikke kreative produktionsgodkendelser.

## 1. Cloudserver — købt, installeret og verificeret

**Driftsserver:** Contabo Cloud VPS Plus 6 med EU-lokation og Ubuntu 24.04 LTS.

- 6 vCPU, 12 GB RAM, 300 GB NVMe, fem snapshots, 500 Mbit/s-port og ubegrænset trafik. Kontrolpanelet viser én måneds kontrakt og €23,75/måned, cirka 177 DKK. Endelig faktura og moms er ikke verificeret.
- Serveren overstiger det tidligere 150 DKK-loft. Der skal ikke købes flere servere eller større API-pakker uden ny beslutning.
- Applikationscommit `ab01f5f` er deployet, 81/81 tests bestod lokalt og på serveren, web/worker er healthy.
- SSH bruger separat ED25519-nøgle med fingeraftryk `SHA256:JlwDFKo3YXhjG1DAkgEgbY8B8otWKuiJEgT12w1kF4A`. Root- og passwordlogin over SSH er slået fra. UFW og Fail2ban er aktive.
- Caddy giver gyldig HTTPS på `https://62.171.167.243.sslip.io`. Dashboardbruger er `owner`; initialadgangskoden ligger i root-beskyttet `/opt/some/secrets/initial-admin-password`.
- Caddy’s admin-whitelist skal opdateres, når ejerens IP skifter. Offentlige health-/juridiske ruter og integrationscallbacks forbliver adskilt fra ejer-ruterne.
- Krypteret backup og restore er verificeret. Contabos cloudfirewall og offsite backup mangler; der skal ikke købes Auto Backup uden ny prisafklaring.

Kokoro, Whisper og rendering kører lokalt på serveren. Claude API er verificeret til manuskripter, claimkontrol og opslagsrevision med Sonnet/Haiku og 50 DKK-loft. `PAID_JOBS_ENABLED=true`; `DRY_RUN=true` og `PUBLISH_ENABLED=false` er genoprettet efter de godkendte testuploads.

## 2. Claude Console — samlet server- og API-budget

Links: https://platform.claude.com/docs/en/api/overview og https://console.anthropic.com/

- Appens standard er **50 DKK/måned** og maksimalt **5 DKK/job**. Udbyderens alarms/grænser skal også konfigureres, hvor de understøttes. Server + appens API-loft er cirka 227 DKK/måned.
- API-nøglen ligger kun i `/opt/some/secrets/app.env`. Den må ikke kopieres til chat eller Git.

Modelrouting kontrolleret i officiel dokumentation 2026-11-10:

- `claude-sonnet-5-5` til manuskripter og opslagsrevision: $2 input / $10 output pr. million tokens.
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

Produktionens fire DKK-priser er konfigureret: Sonnet `13.3322` input / `66.661` output og Haiku `0.66661` input / `3.33305` output pr. million tokens. Samlet kendt testforbrug inklusive én live opslagsrevision er cirka **0,155439 DKK** af 50 DKK.

## 3. YouTube/Google — verificeret

- Kanal-ID `UCZQSuChELmq1_j676dszTqg`; OAuth og kanaladgang er verificeret.
- Privat testupload `9EEY0uC9Xnc` er `private` og `processed`. Analytics returnerede ni metrikfelter.
- Den begrænsede researchnøgle gav 40 reelle observationer uden fejl.
- YouTube-appen står stadig i Testing. Varig produktion kræver senere passende token- og appforvaltning.
- Google Trends kan importeres manuelt for den valgte niche: https://trends.google.com/trends/

## 4. Instagram/Meta — verificeret med ejerens konti

- Facebook Login for Business blev brugt, fordi Unified Login returnerede nul konti via `assigned_instagram_accounts`.
- Instagram: `17841457024132563` / `@pixelandparameters`. Testreel `18110461838195602` er verificeret på https://www.instagram.com/reel/DfmPOXZhJ3e/.
- Facebook-side: `1467423036459990` / Pixel and Parameters. Testreel `1691097949310064` er verificeret som `/reel/1691097949310064/`.
- Facebook bruger direkte multipart-upload fra serveren, fordi URL-upload gav Graph-fejl 390.
- Meta App Review/Advanced Access er ikke gennemført; de verificerede tests bruger ejerens egen konto og Standard Access.

## 5. TikTok — Sandbox og kladde verificeret

- App: `SoMe-maskinen-sandbox`; scopes `user.info.basic` og `video.upload`; målkonto `@pixelandparameters` er accepteret.
- OAuth og konto Pixel and Parameters er verificeret. Redirect er `https://62.171.167.243.sslip.io/integrations/tiktok/callback`.
- Ejeren har bekræftet TikTok-appens systemnotifikation **“Din indhold fra SoMe-maskinen er klar”**. Det beviser API-kladden i TikTok-inboxen, ikke et offentligt opslag.
- Første upload havde intet gemt `publish_id` og blev markeret som ufærdig. Den er reconcileret med ejerbevis uden en ekstra upload. Senere kode gemmer `publish_id` og poller i cirka 60 sekunder.
- Direct Post er bevidst deaktiveret. Production-appens obligatoriske demo-video og review mangler. Production må ikke aktiveres før demo og form er færdige.

## 6. Review-center — klar til ejerens vurdering

- Åbn `https://62.171.167.243.sslip.io/review`. Færdige opslag vises med video, thumbnail, titel, opslagstekst, hashtags, kilder, platform og forbundet konto.
- Platform forhånds vælges fra opslagets metadata. Konto-ID hentes fra den verificerede integration og skal ikke tastes manuelt.
- **Godkend opslag** registrerer kun en godkendelse; der sker ingen automatisk publicering fra siden. Hele videoen skal bekræftes set.
- **Afvis med kommentar** gemmer ejerens konkrete feedback. **Ret opslag med AI** laver en ny version med ændret titel, caption og hashtags. Video, lyd og visuals genbruges og ændres ikke af denne revision.
- Den rettede version får nyt manifest og kræver ny godkendelse. Revisionsjobs er idempotente pr. afvisning.
- Demo 5 er afvist som live-test. Demo 6 er den AI-rettede version og ligger klar under `/review/6`. Den er ikke godkendt eller publiceret.

## 7. Backup og offsite lager

- Seneste verificerede krypterede backup er `/data/backups/some-backup-20261111T140525Z.zip.enc`.
- Vælg separat lager med dokumenteret pris og sikker adgang. Behold 7 daglige + 4 ugentlige kopier og udfør restoretest i separat mappe.
- Offsite-overførsel er ikke konfigureret. Backupnøglen skal fortsat opbevares separat fra serveren.

## 8. Kvalitet, rettigheder og kommerciel lancering

- Godkend hver færdig version efter at have set hele videoen. Ingen automatisk publicering af DEMO eller AWAITING_OWNER-versioner.
- Kontrollér konkrete stock-, gameplay-, musik- og personrettigheder pr. asset. Der findes ingen 10-sekundersregel.
- Vælg et faktisk affiliateprogram, dokumentér vilkår, provision og reklamemarkering. Ingen RPM, købsrate eller indtjening antages.
- Afklar reklamemarkering, skat/moms og juridiske fortolkninger med relevante fagpersoner før kommerciel lancering.
- HeyGen og synlige avatarer er udfaset. ElevenLabs er kun en valgfri provider og kræver særskilt ejeraccept af voice, kommercielle vilkår og pris før betalte kald.
- Fuld automatisk research → licenseret produktion → rendering og multiplatformsplanlægning er ikke færdig. Reelle læringsforbedringer er ikke dokumenteret endnu.

## Præcis næste handling

Åbn `https://62.171.167.243.sslip.io/review/6`, log ind som ejer og gennemgå demo 6 i det nye review-center. Herefter fortsættes med TikTok-app-demo og valg af nye stemmer som aftalt.
