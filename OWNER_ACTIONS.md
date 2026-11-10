# Ejerhandlinger — først når den lokale leverance er gennemgået

Der er ikke foretaget køb, login, OAuth, betalte API-kald eller offentlig publicering. Del aldrig passwords, API-nøgler, client secrets eller refresh tokens i chat eller Git.

## 0. Kreativ status — voiceover godkendt

Kokoro-voiceover uden avatar er godkendt kreativt. Den aktuelle kandidat er `some-pilot/data/versions/handheld-voiceover-v1/video.mp4` på 102,1 sekunder med komplet claim- og voice-kontrol samt ti hash-verificerede manifestfiler. `handheld-zoom-v11` og `handheld-safe-v10` er kreative referencer. Ingen version er publiceret.

## 1. Cloudserver og pris — godkendelse før køb

Primær kandidat: https://contabo.com/en/vps/ (Cloud VPS 4). Hetzner CPX32 er fravalgt på grund af prisen.

- Opret ejerstyret konto, betalingsmiddel, eventuel identitetskontrol og 2FA.
- Projekt: `some-pilot`; EU-lokation; Ubuntu 24.04 LTS.
- Konfiguration: 4 vCPU, 8 GB RAM, 100 GB SSD, ét snapshot, IPv4/IPv6 og ubegrænset trafik. Ingen setup fee er oplyst.
- Vælg kortest mulig bindingsperiode først, så rendering og drift kan verificeres før eventuel 24-måneders binding. Auto Backup er en betalt tilføjelse og er ikke inkluderet i prisen.

**Prisstatus 2026-11-10:** Contabos officielle side viser €5,50/måned inkl. moms for de første 24 måneder, cirka 41 DKK ved 7,45 DKK/EUR. Det samlede loft er **150 DKK/måned inklusive server og Claude API**. Pris, moms, tilgængelighed og bindingsperiode skal kontrolleres igen i checkout før køb. Prisen efter de første 24 måneder og prisen på Auto Backup er ikke verificeret. Der er ikke købt eller oprettet noget endnu.

Kokoro, Whisper og rendering kører lokalt på serveren og kræver ikke Claude/OpenAI. Claude API er valgt til research, manuskripter og claimkontrol; det bruges ikke til selve renderingen. `PAID_JOBS_ENABLED` forbliver `false`, indtil nøgle, verificerede DKK-priser og API-budget er konfigureret.

Alternativer hvis pris/tilgængelighed er dårlig: https://www.scaleway.com/en/pricing/ og https://www.digitalocean.com/pricing

Efter godkendelse: opret separat SSH-nøgle lokalt, upload kun `.pub`, kontrollér hostfingerprint og brug `some-pilot/scripts/install.sh`. Verificér nyt `deploy`-login før SSH root/password-login deaktiveres. Angiv `ADMIN_IP` og konfigurér både cloudfirewall og UFW.

## 2. Claude Console — samlet server- og API-budget

Links: https://platform.claude.com/docs/en/api/overview og https://console.anthropic.com/

- Opret ejerstyret organisation/projekt og aktivér API-betaling. Et Claude-chatabonnement er ikke API-forbrug.
- Appens standard er **50 DKK/måned** og maksimalt **5 DKK/job**. Konfigurér også udbyderens alarms/grænser, hvor de understøttes. Server + appens API-loft er dermed cirka 91 DKK/måned.
- Opret først en projektspecifik nøgle efter accept af API-loftet. Indsæt den direkte i `/opt/some/secrets/app.env` med sikker editor/secret-manager — aldrig i chat eller Git.

Modelrouting kontrolleret i officiel dokumentation 2026-11-10:

- `claude-sonnet-5-5` til manuskripter: $2 input / $10 output pr. million tokens.
- `claude-haiku-5-5` til research og claimkontrol: $0,10 input / $0,50 output pr. million tokens ved prompts op til 100.000 tokens. Over 100.000 tokens er priserne $0,50 input / $2,50 output.

Kilder: https://platform.claude.com/docs/en/about-claude/pricing og https://contabo.com/en/vps/

### Estimat ved 30 videoer/måned

| Del | Forbrugsantagelse | USD/måned | Ca. DKK/måned |
|---|---|---:|---:|
| Contabo Cloud VPS 4 | €5,50 inkl. moms de første 24 måneder | — | 41,00 |
| Haiku research | 20.000 input + 2.000 output pr. dag | $0,09 | 0,58 |
| Sonnet manuskripter | 8.000 input + 1.200 output pr. video | $0,84 | 5,42 |
| Haiku claimkontrol | 12.000 input + 700 output pr. video | $0,0465 | 0,30 |
| **API i alt** | | **$0,9765** | **6,30** |
| **Server + API** | | | **ca. 47** |
| **Med dobbelt API-forbrugslager** | retries og ekstra research | | **ca. 54** |

DKK-beregningen bruger vejledende 7,45 DKK/EUR og 6,45 DKK/USD. Det er et forbrugsestimat, ikke en prisgaranti; faktisk pris afhænger af tokens, valutakurs, moms og checkout. Selv med appens API-loft på 50 DKK bliver den samlede pris cirka 91 DKK/måned.

Appen kræver separat verificerede DKK-priser for hver modelrute: `CLAUDE_INPUT_DKK_PER_MILLION`, `CLAUDE_OUTPUT_DKK_PER_MILLION`, `CLAUDE_RESEARCH_INPUT_DKK_PER_MILLION` og `CLAUDE_RESEARCH_OUTPUT_DKK_PER_MILLION`. Omregn med en dokumenteret valutakurs på konfigurationsdagen. Start med små evals. Betalte jobs forbliver `false`, indtil dette er godkendt.

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
- Aktivér først `PAID_JOBS_ENABLED=true` efter budgettest. Aktivér `PUBLISH_ENABLED=true` og `DRY_RUN=false` først efter verificeret privat upload og konkret ejergodkendelse.
- HeyGen og synlige avatarer er udfaset. Kokoro er den lokale standardstemme. ElevenLabs er kun en valgfri provider og kræver særskilt ejeraccept af voice, kommercielle vilkår og pris før paid jobs aktiveres.

## Præcis næste handling

Kokoro-voiceover er godkendt kreativt. Næste enlige opgave er punkt 1: opret Contabo-konto med 2FA, vælg Cloud VPS 4 med Ubuntu 24.04 og kortest mulig bindingsperiode. Kontrollér checkout-totalen mod den oplyste pris på cirka 41 DKK/måned, og godkend kun købet, hvis pris og binding er acceptabel. Claude-nøgle og API-loft på 50 DKK/måned konfigureres som den næste separate opgave; samlet server + API estimeres til 47–54 DKK/måned.
