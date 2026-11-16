# Ejerhandlinger — integrationer, medier og sikker drift

Contabo-serveren, Claude, YouTube, Instagram, Facebook og TikTok Sandbox er forbundet og verificeret med ejerens konti. Del aldrig passwords, API-nøgler, client secrets eller refresh tokens i chat eller Git.

## 0. Kreativ status — voiceover afvist

**Kokoro `af_bella` er ikke godkendt kreativt og må ikke bruges til nye produktionsopslag.** Ejeren har valgt ElevenLabs `HfRP3cIhYLmeNHeTvkWK` til gaming og `8CjmkufHc22WbMZEBHbm` til AI. Stemmerne er fundet som Chris – Fast-Paced Informative Narrator og Nathaniel C – Expressive Social Media Creator og tilføjet via den officielle Voice Library. Gaming er standard. Creator-abonnementet er aktivt, API-nøglen virker, og pris/rettigheder er konfigureret: $0,08/1.000 tegn = 0,533288 DKK pr. 1.000 tegn, verificeret 2026-11-11. Begge teststemmer er genereret med eleven_multilingual_v2; lokale previews er `voice-previews/gaming.wav` og `voice-previews/ai.wav`. De er ikke publiceret.

## 1. Cloudserver — købt, installeret og verificeret

**Driftsserver:** Contabo Cloud VPS Plus 6 med EU-lokation og Ubuntu 24.04 LTS.

- 6 vCPU, 12 GB RAM, 300 GB NVMe, fem snapshots, 500 Mbit/s-port og ubegrænset trafik. Kontrolpanelet viser én måneds kontrakt og €23,75/måned, cirka 177 DKK. Endelig faktura og moms er ikke verificeret.
- Serveren overstiger det tidligere 150 DKK-loft. Der skal ikke købes flere servere eller større API-pakker uden ny beslutning.
- Applikationscommit `8589e38e` er deployet (læring med retention, engagement, subscribers og kohortesammenligning pr. hook oven på MobyGames-forberedelse og cross-platform-regler), **199/199 tests** bestod lokalt og på serveren, web/worker er healthy.
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

### Estimat pr. 1 og 2 minutters opslag

Claude-baseline er ca. **0,207 DKK pr. parent story**: Sonnet-manuskript ca. 0,187 DKK, Haiku claimkontrol ca. 0,010 DKK og researchallokering ca. 0,020 DKK. Fire separate platformadapteringer kan lægges oveni med et skøn på ca. **0,240 DKK**. ElevenLabs koster 0,533288 DKK pr. 1.000 tegn; de målte stemmeeksempler og en almindelig talehastighed giver et arbejdsinterval på ca. 845–1.273 tegn/minut.

| Varighed | Claude-baseline + ElevenLabs | Med fire platformadapteringer + ElevenLabs |
|---|---:|---:|
| 1 minut | ca. 0,76–0,89 DKK | ca. 1,00–1,13 DKK |
| 2 minutter | ca. 1,31–1,57 DKK | ca. 1,55–1,81 DKK |

Priserne er ikke fakturaer. Længere research, flere revisioner, regenerering af stemme, valutakurs og moms kan ændre dem. ElevenLabs-opkrævning kan desuden afhænge af abonnementets kvote og faktureringsregler.

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

## 5. TikTok — automatisk token-fornyelse og Direct Post-review

**Status 2026-11-16:**
- Koden fornyer nu selv TikTok-adgangen. Adgangstokenet (ca. 24 timer) fornyes automatisk med refresh-tokenet (ca. 365 dage), før det udløber, og overlever genstarter.
- Tokens ligger i `/opt/some/data/secrets/tiktok_oauth.json` (kun læsbar for app-brugeren) og vises eller logges aldrig. `app.env` har kun `TIKTOK_OPEN_ID`.
- Godkendelsessiden har et TikTok-panel med kontonavn fra TikTok, valg af synlighed uden standardvalg, Comment/Duet/Stitch, kommerciel mærkning og samtykketeksten "By posting, you agree to TikTok's Music Usage Confirmation". Valgene er låst i godkendelsens SHA-digest ligesom YouTube-synlighed.
- Direct Post er stadig **slået fra** (`TIKTOK_DIRECT_POST_ENABLED/REVIEWED/CONSENT_CONFIRMED=false`). TikTok kan ikke vælges som destination, før TikTok har godkendt reviewet. Ingen TikTok-opslag er sendt.
- Historik: Sandbox-appen `SoMe-maskinen-sandbox` lavede én API-kladde i inboxen (ikke offentlig) med `video.upload`. Inbox-flowet bruges ikke længere.

### 5A. Log ind igen på TikTok (nu, med sandbox-appen) — ca. 5 min

1. Gå til [developers.tiktok.com](https://developers.tiktok.com/) → **Manage apps** → `SoMe-maskinen-sandbox`.
2. Under **Products → Content Posting API**: slå **Direct Post** til. Det giver scopet `video.publish`, som TikTok-panelet skal bruge.
3. Under **Login Kit**: tjek at redirect-URI er præcis `https://62.171.167.243.sslip.io/integrations/tiktok/callback`.
4. Under **Sandbox settings → Target users**: tjek at `@pixelandparameters` stadig står som accepteret.
5. Sig til Claude: **"Start TikTok-login"**. Claude starter login-hjælperen på serveren og sender dig login-linket (fra `/opt/some/secrets/tiktok-login-url.txt`). Linket virker kun én gang.
6. Åbn linket, log ind som **@pixelandparameters** og godkend adgangen. Du indtaster selv adgangskode og 2FA.
7. Du ser siden **"TikTok-forbindelsen er oprettet"**. Sig til Claude, at du er færdig.
8. Claude kører `account-probe` og derefter `account-probe --force-tiktok-refresh`. Begge skal vise TikTok `ok`, og den anden viser at fornyelsen virker.

### 5B. Flyt til en production-app med Direct Post — ca. 30 min

1. På [developers.tiktok.com](https://developers.tiktok.com/) → **Manage apps**: åbn appens **Production**-del (ikke sandbox), eller opret en ny app, hvis sandbox-appen ikke har en production-del.
2. **App details:**
   - App-navn: `Pixel and Parameters`
   - Ikon: `some-pilot/app/static/tiktok-app-icon.png`
   - Kategori: *Entertainment*
   - Beskrivelse (engelsk): *Pixel and Parameters is a private publishing tool for one creator. The creator reviews every video and posts it to their own TikTok account.*
   - Terms of Service URL: `https://62.171.167.243.sslip.io/terms`
   - Privacy Policy URL: `https://62.171.167.243.sslip.io/privacy`
   - Platform: **Web**, website `https://62.171.167.243.sslip.io`
3. **URL properties / domæne-verifikation:**
   - Verificér `https://62.171.167.243.sslip.io/`.
   - Filen `tiktokDNEepLrDLh4SgEN8VZPDcTcL09iuTuaj.txt` ligger allerede i roden.
   - Viser TikTok et **andet** filnavn til production-appen, så send det til Claude. Det kræver en lille kodeændring og et deploy.
4. **Products:**
   - **Login Kit**, med redirect-URI `https://62.171.167.243.sslip.io/integrations/tiktok/callback`.
   - **Content Posting API**, med **Direct Post slået til**.
5. **Scopes:** kun `user.info.basic` og `video.publish`. Tilføj ikke `video.upload`, som ikke bruges længere. Ubrugte scopes er en almindelig afvisningsgrund.
6. **Nøgler:**
   - Giv Claude production-appens **Client key** og **Client secret**.
   - Claude skriver dem i `/opt/some/secrets/app.env` (0600) med backup og viser dem aldrig.
   - Claude genstarter først, når ingen jobs kører.
7. **Log ind igen** som i 5A, nu med production-appen. Det gamle sandbox-token afvises bevidst (`tiktok_client_key_changed_login_required`), fordi tokens hører til én app.

### 5C. Demo-video og review — ca. 30 min

TikTok vil se hele flowet i én skærmoptagelse, mp4/mov. Optag med **Win+Alt+R** (Xbox Game Bar) eller Klippeværktøj → Optag. Optag i engelsk browser, og hold musen rolig. Forløb:

1. Vis login: åbn TikTok-login-linket og log ind som @pixelandparameters, så TikToks samtykkeskærm med scopes ses. Afslut på "TikTok-forbindelsen er oprettet". Brug et nyt link fra Claude, for linket virker kun én gang.
2. Åbn review-centret `https://62.171.167.243.sslip.io/review` og log ind. Klip gerne 2FA-trinnet ud.
3. Åbn en video, der venter på godkendelse. Afspil forhåndsvisningen et par sekunder.
4. Scroll til **TikTok post settings**, og vis i rækkefølge:
   - **Kontonavnet** ("Posting to …"), som kommer fra TikTok.
   - Dropdown **Who can view this video**: vis at intet er valgt, og vælg derefter en mulighed.
   - **Allow users to: Comment / Duet / Stitch**: vis at de starter slået fra, og slå én til. Gråe felter er slået fra i TikTok-kontoens egne indstillinger.
   - **Disclose video content**: slå til, og vis den røde besked om at en type skal vælges.
     - Vælg **Your brand**, og vis mærket "Promotional content".
     - Vælg **Branded content**, og vis mærket "Paid partnership" og at "Only me" bliver utilgængelig.
     - Slå derefter mærkningen fra igen.
   - **Samtykketeksten** "By posting, you agree to TikTok's Music Usage Confirmation". Den ændres til "Branded Content Policy and Music Usage Confirmation", når Branded content er valgt.
5. Sæt flueben i "Jeg har set hele videoen", og tryk **Godkend opslag og publicér**.
6. Vis det færdige opslag på TikTok-profilen. *Det kræver en beslutning fra dig først* (se punkt 9).
7. **Review-formularen** (engelsk tekst, kan kopieres):
   - `user.info.basic`: *Shows the creator which TikTok account is connected (display name) and verifies the connection daily.*
   - `video.publish`: *The creator reviews each video in our web review page, chooses privacy level, interaction settings and commercial content disclosure, and explicitly approves. Only then is the video posted with Direct Post to the creator's own account.*
8. Send reviewet. Svaret kommer typisk på 1–2 uger via e-mail.
9. **Beslutning, før demoen optages:** Så længe Direct Post-flagene er slået fra, er TikTok gråtonet som destination. Panelet kan vises, men godkendelsen kan ikke sendes til TikTok.
   - TikTok vil normalt se hele flowet til og med opslaget (punkt 5–6). Derfor anbefales det at slå flagene til **midlertidigt**:
     - Claude slår dem til, kun mens demoen optages med sandbox-appen.
     - Der postes ét opslag med **Only me**. En ikke-reviewet app kan kun poste privat.
     - Bagefter slår Claude flagene fra igen.
   - Det sker kun, hvis du skriver det udtrykkeligt ("ja, ét Only me-demoopslag"). Ellers stopper demoen ved panelet.

### 5D. Når TikTok har godkendt reviewet

1. Videresend eller beskriv TikToks godkendelses-e-mail til Claude.
2. Claude sætter `TIKTOK_DIRECT_POST_ENABLED`, `TIKTOK_DIRECT_POST_REVIEWED` og `TIKTOK_DIRECT_POST_CONSENT_CONFIRMED` til `true` og genstarter, når ingen jobs kører.
3. Derefter kan TikTok vælges på godkendelsessiden. Synlighed skal vælges aktivt hver gang.
4. Ældre godkendelser uden TikTok-valg publiceres aldrig til TikTok (`tiktok_post_settings_not_approved_reapprove`).

## 6. Godkendt intro/outro — obligatorisk for nye videoer

- Den visuelt godkendte P-kollision og den dæmpede baggrundslyd er låst som brand-ident version `original-collision-v1`. Der må ikke laves alternative P-former eller genindføres den kraftige brumme uden ny ejergodkendelse.
- Alle nye produktionsvideoer får automatisk 3,5 sek. intro og 3,5 sek. outro. Intro siger `GAMING CULTURE × AI`; outro siger `FOLLOW FOR MORE`.
- YouTube bruger 16:9 (1920×1080). TikTok, Instagram Reels og Facebook bruger 9:16 (1080×1920). Den samme godkendte animation skaleres til formatet; eksisterende opslag og eksisterende footage ændres ikke.
- Implementationen ligger i `some-pilot/app/pipeline/brand_ident.py`. Reelle FFmpeg-integrationstests dækker begge formater, 30 fps, H.264/yuv420p, AAC stereo 48 kHz og samlet varighed. Cachen genkender ændringer i både logo og renderer.

## 6A. Reel medieproduktion — ny obligatorisk standard

- **Mindst 80 % af hver ny videos varighed skal være rigtige videoklip eller rigtige billeder.** Målingen er duration-weighted. En medieplan kan kræve 90–100 %, men aldrig sænke grænsen.
- Producentklip, generiske kontekstklip, egne gameplayoptagelser og rigtige fotos med zoom/pan understøttes. Grafik/title cards må højst fylde 20 %.
- Hver scene skal have kontekst, lokal fil, HTTPS source/policy URL, rettighedshaver, bevis, kreditering og person-/aldersmetadata. `ai_generated=true` kan ikke tælle som reelt.
- `media_composition.json` er obligatorisk i checks, det dynamiske artifact-manifest og ZIP-eksport. Approval kræver ALLOW. Review viser reel procent på kort og detaljeside.
- Ikke-demo-produktion kræver desuden `editorial-packet.json` i samme mappe samt alle syv `quality_dimensions` i medieplanen. Pakken skal være `needs_owner_review` eller `approved_draft`, matche Gaming/AI-lane og opnå mindst 85 point. Hvert featured game skal have hørbar reception eller en sand dokumenteret undtagelse. Udløbet evidens giver `editorial_source_refresh_required` ved dispatch.
- Medieplaner og klip køres foreløbig via CLI med filer i samme mappe. En visuel upload-/biblioteksoplevelse og fuld automatisk medieplanlægning er ikke færdig.
- Eksempel: `research/top10-legion-go2/real-media-demo.json`. På serveren ligger plan og klip under `/data/media-plans/real-demo`.
- **Demo 8** er produceret med 100 % officiel video fra Transistor, Celeste, Slay the Spire, Hollow Knight og Hades. Den har 11 manifestfiler, teknisk ALLOW og rent source-frame som thumbnail. Demo 6 og 7 er erstattede. Demo 8 er ikke publiceret.

## 6B. MobyGames og footage på tværs af platforme

- **Hvert featured game skal have en konkret MobyGames-side som en del af researchforberedelsen**, også ældre spil. Eksempel: https://www.mobygames.com/game/2069/disneys-aladdin/.
- `preparation` skal dokumentere review score og fun facts. Hvis MobyGames ikke har oplysningerne, kræves en ærlig note om, at de ikke blev fundet efter søgning. Systemet må ikke opfinde manglende værdier.
- MobyGames viste Cloudflare-botskontrol under den tekniske undersøgelse. Der er ikke bygget en bypass-scraper. Den konkrete side skal være inspiceret og registreret som kilde før produktion.
- **Mappenavnet beskriver kun footage-proveniens.** Et klip i `PS5`, `PS4`, `Switch` eller en anden mappe må bruges til alle dokumenterede udgivelsesplatforme og til generelle emner som remakes.
- Eksempel: Final Fantasy VII Rebirth-footage fra `PS5` må bruges til PC- eller Switch 2-opslag, når den konkrete udgivelse på målplattformen er dokumenteret med en frisk kilde. Uden den dokumentation blokeres opslaget med `platform_release_unverified`.
- Ranking bruger `target_game_platform`, fx `PC`, `Switch 2` eller standardværdien `cross-platform`. Den sociale destination (`youtube`, `reels`, `tiktok`) er en helt separat værdi.
- Capture Bridge gemmer platformmappen som `footage_platform`. Den forsøger at identificere spillet i filnavnet; et ukendt spil stopper med `unknown_game_profile` i stedet for at blive fejlregistreret som standardspillet.

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
- Undermapper understøttes rekursivt. En spilmappe som `Monster Train 2` vælger spilprofil. Platformmapper som `PS5` og `Switch 2` gemmes som footage-proveniens, mens spillet genkendes i filnavnet. Ukendte spil i platformmapper stopper med `unknown_game_profile`; uden platformmappe bruges den konfigurerede standardprofil som hidtil.
- Monster Train 2 bruger [Devolvers tilladelsesgenerator](https://canipostandmonetizevideosofdevolvergames.com/). Indsæt kanalnavn og gem den skriftlige tilladelse som bevis. Klippene markeres som rettighedsreview indtil beviset er tilføjet; upload er ikke publicering.
- Den permanente watcher kører med upload aktiveret via eksisterende SSH-nøgle til `/opt/some/data/media-library/<spil>/`. Der er ikke behov for GitHub MCP eller råvideoer i Git.
- Alle fire Monster Train 2-filer er verificeret byte-for-byte med lokale MP4 SHA-256-hashes. Alle fire AI-filer er uploadet som `owned_screen_recording`. Fejlregistreringer er flyttet til karantæne, og originalerne er uændrede.
- Lokal test beviste remux, kontaktark, manifest og upload. Serverens testmappe er slettet. Ingen reel spiloptagelse er publiceret. **Der produceres ingen nye videoer, før ejeren siger “Nu må du begynde”.**
- Lokale Grok/Gemini/Qwen CLI-processer kræver tændt computer. De er ikke cloud-API'er og kan ikke køre på VPS uden computeren. Grok CLI viser ingen videogenerering. Separate Veo/Imagine API'er kræver egen pris- og rettighedsafklaring.

## 10. Review-center og automatisk publicering

- Åbn `https://62.171.167.243.sslip.io/review`. Se video, thumbnail, titel, tekst, hashtags, kilder, konto og medieprocent. ElevenLabs-narration kan afspilles separat, når den findes.
- Alle fire destinationer er valgt som standard. Fjern markeringen for uønskede platforme, vælg YouTube-synlighed og eventuelt et fremtidigt tidspunkt. Alle valgte destinationer kræver et reelt forbundet konto-ID.
- **Godkend opslag og publicér** låser den præcise revision og opretter automatisk ét idempotent job pr. destination. `DRY_RUN=true` og `PUBLISH_ENABLED=false` blokerer stadig reelle kald; jobs med blokeringer viser den præcise fejlkode.
- Ændret video, thumbnail, tekst, konto, destination, synlighed eller tidspunkt invaliderer godkendelsen. En destination, der allerede er publiceret, uploades ikke igen ved fejl på en anden.
- **Afvis med kommentar** opretter ingen publiceringsjobs. **Ret opslag med AI** ændrer kun titel, caption og hashtags; video, lyd og visuals genbruges. Ny version kræver ny godkendelse.
- TikTok kræver desuden production-review og eksplicit Direct Post-consent. Indtil da er blocker `tiktok_direct_post_not_eligible`; en inbox-kladde er ikke et offentligt opslag.

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

## 13. Ejerbeslutninger efter forbedringsrunden (2026-11-13)

Alt nedenfor er deployet (272 tests på VPS). Intet er slået til uden dig.

- [x] **Push og deploy:** Udført 2026-11-13 (272 tests på VPS, backup før migration 0002, healthy).
- [x] **GitHub CI:** Workflowet er pushet og kører ved hver push.
- [x] **Serverens app.env:** `VOICE_PROVIDER=elevenlabs` sat 2026-11-13 (backup af filen ligger ved siden af). Den ubrugte linje `VOICE_PRESET` er slettet samme dag (backup `app.env.bak-20261113T212412Z`).
- [ ] **Alarmkanal:** Vælg webhook (fx Discord) og/eller e-mail, og sæt `ALERT_*` i `/opt/some/secrets/app.env`.
- [ ] **Offsite backup:** Vælg en udbyder med WebDAV over HTTPS (fx en storage box). Godkend prisen, og sæt `OFFSITE_*`. Kun krypterede backups sendes.
- [x] **Staging:** Kører siden 2026-11-13 på `127.0.0.1:8001` (projekt `some-staging`, data i `/opt/some/staging-data`, `staging.env` uden tokens; publicering og betalte kald er fra). Login kræver en separat staging-bruger: `sudo docker compose -p some-staging -f compose.yaml -f compose.staging.yaml run --rm -e APP_ADMIN_PASSWORD web python -m app.cli init-user`. Åbn via `ssh -N -L 8001:127.0.0.1:8001 <server>`.
- [ ] **Udgiverpolitikker:** Verificér Devolver og Nintendo i `some-pilot/content/PUBLISHER_POLICIES.json` (`verified_at`, `verified_by`, bevis). Indtil da blokeres footage med de rettighedshavere.
- [ ] **AI-mærkning:** Bekræft standarderne eller ret dem: YouTube fra (gælder realistisk syntetisk indhold), TikTok til, Instagram/Facebook manuelt i appen. Du kan ændre det pr. godkendelse.
- [ ] **Serier:** Vælg hvilke forslag i `some-pilot/content/SERIES.json` der skal køre.
- [ ] **Tid:** Log dine minutter pr. trin (Drift-siden eller `timelog add`), så flaskehalsen kan måles.
- [ ] **Pilot:** Når footage er klar, skriv “Nu må du begynde” og følg `docs/PILOT_PLAN.md`.

## 14. Ekstern adgang, YouTube-udvidelser og vækstværktøjer (2026-11-13)

Deployet 2026-11-13 som `71d87757` (295 tests på VPS).

Ekstern adgang, i denne rækkefølge:
- [x] Deploy udført 2026-11-13 (`71d87757`, 295 tests på VPS, backup før migration 0003, healthy).
- [x] 2-faktor tilmeldt af ejeren 2026-11-13 22:33 UTC, med 8 gendannelseskoder.
- [x] Ekstern adgang åbnet 2026-11-13: `REQUIRE_TOTP=true`, `PUBLIC_DASHBOARD_URL` sat, IP-begrænsningen fjernet i Caddy (backup `/etc/caddy/Caddyfile.bak-20261113T223531Z`). Dashboardet kræver nu password og 2-faktor-kode fra alle steder. Mister du telefonen, bruger du en gendannelseskode.
- [ ] Beslut, om SSH (port 22) fortsat skal være åben fra hele internettet. Den er i dag beskyttet af nøgle-login og Fail2ban.

YouTube:
- [ ] Godkend YouTube-appen igen med scope `youtube.force-ssl` (ud over de nuværende). Uden den springes undertekster og serie-playlister over med status `scope_missing_reauthorize`, mens selve uploaden virker som før.

Vækstværktøjer:
- [ ] Udtale: Tilføj en regel i `some-pilot/content/PRONUNCIATIONS.json`, hver gang et navn udtales forkert.
- [ ] Udgivelser: Tilføj kommende spil i `some-pilot/content/RELEASE_CALENDAR.json` med kilde og tjek-dato. IGDB-import kræver en Twitch-app (`IGDB_CLIENT_ID`/`IGDB_CLIENT_SECRET`), og at du har tjekket, at vilkårene tillader kanalens brug (`IGDB_TERMS_CONFIRMED=true`).
- [ ] Affiliate: Registrér programmer i `some-pilot/content/AFFILIATE_PROGRAMS.json` med domæne og oplysningstekst, før du bruger affiliate-links. Uregistrerede links blokeres ved godkendelse.
- [ ] YPP: Tærsklerne i `some-pilot/content/MONETIZATION.json` er læst 2026-11-13. YouTube har annonceret højere tærskler for nye kanaler fra 2027-02-01.
- [ ] Staging-login: Staging har sin egen tomme database, og du opretter brugeren med kommandoen i afsnit 13.

## Præcis næste handling — start produktion når footage er klar

ElevenLabs-nøglen og begge stemmer er allerede konfigureret; der skal ikke ændres i secrets nu. Fortsæt optagelserne som planlagt. Når biblioteket er fyldt, og du vil have den første rigtige pilotproduceret, skriv præcis: **“Nu må du begynde”**. Før det sker, produceres ingen nye videoer og eksisterende footage ændres ikke. TikTok production-demo/review og Direct Post-consent håndteres som et separat efterfølgende punkt.
