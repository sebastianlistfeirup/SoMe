# Ejerhandlinger — integrationer, medier og sikker drift

Contabo-serveren, Claude, YouTube, Instagram, Facebook og TikTok Sandbox er forbundet og verificeret med ejerens konti. Del aldrig passwords, API-nøgler, client secrets eller refresh tokens i chat eller Git.

## 0. Kreativ status — voiceover afvist

**Kokoro `af_bella` er ikke godkendt kreativt og må ikke bruges til nye produktionsopslag.** Ejeren har valgt ElevenLabs `HfRP3cIhYLmeNHeTvkWK` til gaming og `8CjmkufHc22WbMZEBHbm` til AI. ID'erne er gemt lokalt i konfigurationseksemplet og på serveren; gaming er standard. Der må ikke genereres lyd før API-nøgle, abonnement, pris og kommercielle rettigheder er verificeret. Demo 8 bruger kun espeak som teknisk fallback.

## 1. Cloudserver — købt, installeret og verificeret

**Driftsserver:** Contabo Cloud VPS Plus 6 med EU-lokation og Ubuntu 24.04 LTS.

- 6 vCPU, 12 GB RAM, 300 GB NVMe, fem snapshots, 500 Mbit/s-port og ubegrænset trafik. Kontrolpanelet viser én måneds kontrakt og €23,75/måned, cirka 177 DKK. Endelig faktura og moms er ikke verificeret.
- Serveren overstiger det tidligere 150 DKK-loft. Der skal ikke købes flere servere eller større API-pakker uden ny beslutning.
- Applikationscommit `24a4820` er deployet, **89/89 tests** bestod lokalt og på serveren, web/worker er healthy.
- SSH bruger separat ED25519-nøgle. Root- og passwordlogin over SSH er slået fra. UFW og Fail2ban er aktive.
- Caddy giver gyldig HTTPS på `https://62.171.167.243.sslip.io`. Dashboardbruger er `owner`; initialadgangskoden ligger i root-beskyttet `/opt/some/secrets/initial-admin-password`.
- Caddy’s admin-whitelist skal opdateres, når ejerens IP skifter. Offentlige health-/juridiske ruter og callbacks er adskilt fra ejer-ruterne.
- Krypteret backup og restore er verificeret. Contabos cloudfirewall og offsite backup mangler; der skal ikke købes Auto Backup uden ny prisafklaring.

Claude API er verificeret med 50 DKK-loft. `PAID_JOBS_ENABLED=true`; `DRY_RUN=true` og `PUBLISH_ENABLED=false` er genoprettet efter testuploads.

## 2. Claude Console — samlet server- og API-budget

Links: https://platform.claude.com/docs/en/api/overview og https://console.anthropic.com/

- Appens standard er **50 DKK/måned** og maksimalt **5 DKK/job**. Server + appens API-loft er cirka 227 DKK/måned.
- API-nøglen ligger kun i `/opt/some/secrets/app.env`. Den må ikke kopieres til chat eller Git.
- `claude-sonnet-5-5` bruges til manuskripter/revision: $2 input / $10 output pr. million tokens.
- `claude-haiku-5-5` bruges til research/claimkontrol: $0,10 input / $0,50 output pr. million tokens ved prompts op til 100.000 tokens.

Kilder: https://platform.claude.com/docs/en/about-claude/pricing og https://contabo.com/en/vps/

### Estimat ved 30 videoer/måned

| Del | Forbrugsantagelse | USD/måned | Ca. DKK/måned |
|---|---|---:|---:|
| Contabo Cloud VPS Plus 6 | €23,75 ifølge kontrolpanel | — | 176,94 |
| Haiku research | 20.000 input + 2.000 output pr. dag | $0,09 | 0,60 |
| Sonnet manuskripter | 8.000 input + 1.200 output pr. video | $0,84 | 5,60 |
| Haiku claimkontrol | 12.000 input + 700 output pr. video | $0,0465 | 0,31 |
| **API i alt** | | **$0,9765** | **6,51** |
| **Server + API** | | | **ca. 183,45** |
| **Med dobbelt API-forbrugslager** | retries og ekstra research | | **ca. 189,96** |

DKK-beregningen bruger 7,45 DKK/EUR og referencekursen 6,6661 DKK/USD fra 2026-11-10. Det er et estimat, ikke faktura eller prisgaranti. Samlet kendt Claude-testforbrug inklusive én live opslagsrevision er cirka **0,155439 DKK** af 50 DKK.

## 3. YouTube/Google — verificeret

- Kanal-ID `UCZQSuChELmq1_j676dszTqg`; OAuth og kanaladgang er verificeret.
- Privat testupload `9EEY0uC9Xnc` er `private` og `processed`. Analytics returnerede ni metrikfelter.
- Researchnøglen gav 40 reelle observationer uden fejl.
- YouTube-appen står stadig i Testing. Varig produktion kræver senere token- og appforvaltning.

## 4. Instagram/Meta — verificeret med ejerens konti

- Instagram: `17841457024132563` / `@pixelandparameters`. Testreel `18110461838195602`: https://www.instagram.com/reel/DfmPOXZhJ3e/.
- Facebook-side: `1467423036459990` / Pixel and Parameters. Testreel `1691097949310064` er verificeret.
- Facebook bruger direkte multipart-upload efter Graph-fejl 390 ved URL-upload.
- Meta App Review/Advanced Access er ikke gennemført; tests bruger ejerens konto og Standard Access.

## 5. TikTok — Sandbox og kladde verificeret

- App: `SoMe-maskinen-sandbox`; scopes `user.info.basic` og `video.upload`; målkonto `@pixelandparameters` er accepteret.
- Ejeren har bekræftet **“Din indhold fra SoMe-maskinen er klar”** i TikTok-appen. Det er en API-kladde i inboxen, ikke et offentligt opslag.
- Første upload manglede gemt `publish_id` og blev reconcileret med ejerbevis uden ny upload. Ny kode gemmer `publish_id` og poller længere.
- Direct Post er deaktiveret. Production-appens demo-video og review mangler og fortsættes når ejeren er tilbage.

## 6. Reel medieproduktion — ny obligatorisk standard

- **Mindst 80 % af hver ny videos varighed skal være rigtige videoklip eller rigtige billeder.** Målingen er duration-weighted. En medieplan kan kræve 90–100 %, men aldrig sænke grænsen.
- Producentklip, generiske kontekstklip, egne gameplayoptagelser og rigtige fotos med zoom/pan understøttes. Grafik/title cards må højst fylde 20 %.
- Hver scene skal have kontekst, lokal fil, HTTPS source/policy URL, rettighedshaver, bevis, kreditering og person-/aldersmetadata. `ai_generated=true` kan ikke tælle som reelt.
- `media_composition.json` er obligatorisk i checks, 11-fils manifestet og ZIP-eksport. Approval kræver ALLOW. Review viser reel procent på kort og detaljeside.
- Medieplaner og klip køres foreløbig via CLI med filer i samme mappe. En visuel upload-/biblioteksoplevelse og fuld automatisk medieplanlægning er ikke færdig.
- Eksempel: `research/top10-legion-go2/real-media-demo.json`. På serveren ligger plan og klip under `/data/media-plans/real-demo`.
- **Demo 8** er produceret med 100 % officiel video fra Transistor, Celeste, Slay the Spire, Hollow Knight og Hades. Den har 11 manifestfiler, teknisk ALLOW og rent source-frame som thumbnail. Demo 6 og 7 er erstattede. Demo 8 er ikke publiceret.

## 7. GeForce Now og egne gameplayoptagelser — ikke konfigureret

NVIDIAs vilkår: https://www.nvidia.com/en-us/geforce-now/terms-of-use/

- Vilkårene beskriver personlig, ikke-kommerciel brug, én session ad gangen og forbud mod bl.a. botting. Der laves **ikke** skjult auto-gameplay eller input-automation.
- Den sikre workflow er, at ejeren selv spiller mens OBS optager lokalt. Hvert spils udgiverpolitik og rettigheder skal stadig kontrolleres før klip bruges.
- På samme computer kan OBS window capture fungere mens andre programmer bruges, men minimering/fokus kan afbryde stream eller optagelse. Det er ikke verificeret på denne computer. Brug helst anden skærm eller separat enhed.
- GeForce Now-login, OBS og konkret spil mangler. Kommerciel brug og udgiverpolitik skal afklares før produktion.

## 8. Qwen, Wan, Claude og Codex — roller og betalingsstop

- **Qwen:** valgfri storyboardkontrol for slides, sorte frames, læsbarhed og kontekst. Implementeret med API/workspace/prisblokering, men ikke eksternt aktiveret. Dokumentation: https://www.alibabacloud.com/help/en/model-studio/vision
- **Wan:** mulig senere generativ supplering, aldrig en del af reel medieprocent. API er asynkron med create/poll og resultatlinks, der udløber. Dokumentation: https://www.alibabacloud.com/help/en/model-studio/text-to-video-api-reference
- **Claude:** manuskript, claimkontrol og opslagsrevision. **Codex/Kimi:** kode og pipelineændringer. Ingen af dem gør et AI-billede til et “rigtigt klip”.
- Officiel Wan2.7-pris for International er $0,10/sekund ved 720P og $0,15/sekund ved 1080P. Ti sekunder 1080P koster $1,50, cirka 10 DKK og overstiger 5 DKK-jobloftet. Pris: https://www.alibabacloud.com/help/en/model-studio/model-pricing
- Ingen betalt Qwen/Wan-aktivering uden ejerens API-nøgle, workspace, pris- og budgetaccept. Der er ikke påløbet Qwen-/Wan-omkostning.

## 9. Lokal OBS Capture Bridge — aktiv

- OBS Studio 33.0.1 og FFmpeg 9.0.2 er installeret lokalt. `scripts/capture_bridge.py` overvåger `C:/Users/compu/Videos/SoMe-captures` og behandler nye MKV/MP4/MOV-filer.
- Resultatet ligger under `C:/Users/compu/Videos/SoMe-processed/<spil>/` med `gameplay.mp4`, `contact-sheet.jpg`, `capture-manifest.json` og procesresultat.
- Undermapper understøttes rekursivt, fx `SoMe-captures/Monster Train 2/clip.mp4`. Mappenavnet vælger spilprofil. Alternativt kan filnavne som `hades-*`, `celeste-*` eller `slay-the-spire-*` bruges; andre filnavne bruger standardprofilen Hades.
- Monster Train 2 bruger [Devolvers tilladelsesgenerator](https://canipostandmonetizevideosofdevolvergames.com/). Indsæt kanalnavn og gem den skriftlige tilladelse som bevis. Klippene markeres som rettighedsreview indtil beviset er tilføjet; upload er ikke publicering.
- Den permanente watcher kører med upload aktiveret via eksisterende SSH-nøgle til `/opt/some/data/media-library/<spil>/`. Der er ikke behov for GitHub MCP eller råvideoer i Git.
- Lokal test beviste remux, kontaktark, manifest og upload. Serverens testmappe er slettet. Ingen reel spiloptagelse er publiceret.
- Lokale Grok/Gemini/Qwen CLI-processer kræver tændt computer. De er ikke cloud-API'er og kan ikke køre på VPS uden computeren. Grok CLI viser ingen videogenerering. Separate Veo/Imagine API'er kræver egen pris- og rettighedsafklaring.

## 10. Review-center — klar til ejerens vurdering

- Åbn `https://62.171.167.243.sslip.io/review`. Se video, thumbnail, titel, tekst, hashtags, kilder, platform, konto og medieprocent.
- Platform forhånds vælges, og konto-ID udfyldes. **Godkend opslag** registrerer kun godkendelse; der sker ingen automatisk publicering.
- **Afvis med kommentar** gemmer feedback. **Ret opslag med AI** ændrer kun titel, caption og hashtags; video, lyd og visuals genbruges. Ny version kræver ny godkendelse.
- Demo 8 ligger under `/review/8` som den eneste nye mediedemo. Den er ikke godkendt eller publiceret.

## 11. Backup og offsite lager

- Seneste verificerede krypterede backup er `/data/backups/some-backup-20261111T155413Z.zip.enc`.
- Vælg separat lager med dokumenteret pris og sikker adgang. Behold 7 daglige + 4 ugentlige kopier og udfør restoretest i separat mappe.
- Offsite-overførsel er ikke konfigureret. Backupnøglen skal opbevares separat fra serveren.

## 12. Kvalitet, rettigheder og kommerciel lancering

- Godkend hver færdig version efter at have set hele videoen. Ingen automatisk publicering af DEMO eller AWAITING_OWNER-versioner.
- Kontrollér konkrete stock-, gameplay-, musik- og personrettigheder pr. asset. Der findes ingen 10-sekundersregel.
- Vælg et faktisk affiliateprogram og dokumentér vilkår, provision og reklamemarkering. Ingen RPM, købsrate eller indtjening antages.
- Afklar reklamemarkering, skat/moms og juridiske fortolkninger med relevante fagpersoner før kommerciel lancering.
- ElevenLabs kræver særskilt ejeraccept af voice, kommercielle vilkår og pris. HeyGen og synlige avatarer er udfaset.
- Reelle læringsforbedringer er ikke dokumenteret endnu. Fuld automatisk research → medieplan → rendering → multiplatformsplanlægning er ikke færdig.

## Præcis næste handling — ElevenLabs-nøgle

Læg nøglen direkte på serveren uden at sende den i chat:

1. Kør `ssh -F .codex_tmp/deploy/ssh_config some-contabo-deploy` fra `C:\Users\compu\Documents\SoMe`.
2. Kør `sudo nano /opt/some/secrets/app.env`.
3. Tilføj `ELEVENLABS_API_KEY=din-nøgle` som ny linje. Gem med Ctrl+O, Enter og Ctrl+X.
4. Skriv `exit` og derefter “nøglen er lagt på serveren” i chatten.

Derefter hentes stemmeliste og abonnementsinformation uden at vise nøglen. Officiel API-pris for multilingual TTS er $0,08/1.000 tegn; abonnementets faktiske kvote og kommercielle licens kontrolleres før generering.
