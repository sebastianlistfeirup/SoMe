# Testprotokol — SoMe-maskinen

Dato: 2026-11-10 til 2026-11-11
Miljø: Windows-vært, Git Bash, Docker Desktop Linux containers, Python 3.11, SQLite/WAL, FFmpeg, faster-whisper small/int8, Kokoro-82M ONNX
Formål: Skelne mellem faktisk udførte lokale kontroller og integrationer, der stadig kræver ejerens konti og godkendelser.

## Baseline og bevarelse af WIP

- Udgangspunkt: commit `2b601349cfffdc332ef9b348bdf0498331b45c5b` plus værdifuldt ikke-committed WIP.
- Maskinlæsbart snapshot: `.codex_tmp/kimi-worktree-snapshot-2026-11-10.json` med 46 ændrede/untracked stier. Det er et lokalt checkpoint, ikke en Git-commit.
- Ingen reset, checkout eller sletning af andres WIP er udført.
- Docker var stoppet ved første testforsøg. Efter start af Docker Desktop blev build og tests kørt på den faktiske nye kode.

## Standardbuild og automatiske tests

Kørsel fra `some-pilot`:

```bash
MSYS_NO_PATHCONV=1 docker compose build
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps worker pytest -q
```

Resultat: **73 passed**. Kun en ekstern Starlette TestClient-deprecationwarning.

Dækning: rettigheder, alder, statusflow, approvalhash, publish-blokering, jobs, budget, downloads/SSRF, backup/restore, ZIP path traversal, idempotent metricsimport, demo/produktionsadskillelse, SAFE, ZOOM, claim control, voice providers, teksthash, WAV/lydstream, sample rate, segmentdækning, ElevenLabs paid-/pris-/rettighedsblokering, PCM-konvertering, ranking til approval, testpost-timing, Claude-modelrouting og modelpriser, doctor og dashboardruter.

## Claude-modelrouting og omkostninger

- `claude_draft` kalder `claude-sonnet-5-5`; `review_draft` kalder `claude-haiku-5-5` via research-ruten med 2.000 outputtokens.
- Mocktests dækker separate modelpriser, thinking-blok efterfulgt af tekst, præcise claim- og review-skemaer og outputgrænsen. Promptversion er `claude-json-v3-controlled`.
- Paid jobs slået fra, tom API-nøgle og manglende input-/outputpris for hver rute blokerer før `Anthropic` instantieres. Ingen costreservation eller netværkskald opstår i disse negative testtilfælde.
- Sikker standard er `MONTHLY_AI_BUDGET_DKK=50` og `MAX_JOB_AI_COST_DKK=5`. Produktion har paid jobs aktiveret efter ejerens nøgle og budgetaccept; publishing forbliver fra.
- Doctor rapporterer script-/researchmodel og om nøgle og DKK-priser er konfigureret, men aldrig selve nøglen.
- Automatiske tests bruger mocks. Separat live Sonnet-/Haiku-healthcheck og syntetisk manuskript → claimkontrol er verificeret på VPS; se Contabo-afsnittet.
- Den købte Contabo Cloud VPS Plus 6 har skærmpris €23,75/måned, cirka 177 DKK. Ved 30 videoer/måned er Claude-estimatet 6,51 DKK og totalen cirka 183,45 DKK. Dobbelt API-forbrugslager giver cirka 189,96 DKK samlet. Det er et estimat, ikke en verificeret faktura; se OWNER_ACTIONS.md.

## Voiceover og approval

- `app/pipeline/voice.py` tester lokal Kokoro og valgfri ElevenLabs uden betalt netværkskald.
- Kokoro-genbrug kræver matchende manuskriptmetadata, alle 11 segmenter og gyldig WAV med lyd, varighed og sample rate.
- ElevenLabs kræver paid jobs, API-nøgle, voice-ID, `ELEVENLABS_VOICE_RIGHTS_CONFIRMED=true` og dateret pris inden for budget. Mocktest bekræfter PCM 24 kHz og prisregistrering; det er ikke en ekstern leverandørtest.
- Ranking når `AWAITING_OWNER` uden avatar og passerer den rigtige `approve()` med gyldige checks og approvalhash.
- Almindelig produktion har samme voice-provenance som ranking. `voice_assets.json` er obligatorisk i manifestet, som dermed har ti filer.

## Rigtige videoproduktioner

### Rankingreference

`some-pilot/data/versions/handheld-voiceover-v1`:

- video_id=33; 102,1 sekunder; 1080×1920; H.264 High/yuv420p; AAC 48 kHz; 30 fps.
- Kokoro `af_bella`; voice_only=true; avatar_present=false.
- Speakmatch 99,51 %; −16,5 LUFS; −0,9 dBTP.
- Rights, technical, layout, safety, quality, claim_control og voice er ALLOW.
- Alle ti manifestfiler er SHA-256-verificeret efter regenerering via den normale leverancefunktion.
- Thumbnail og storyboard er visuelt kontrolleret. Status AWAITING_OWNER; ikke uploadet.

### Almindelig demo

`some-pilot/data/versions/topic-49-v1`:

- video_id=34; espeak-ng som teknisk fallback; voice control ALLOW og ti manifestfiler.
- Status AWAITING_OWNER; ikke uploadet.

### Testpost-familier

`some-pilot/data/outputs/test-posts-2026-11-09/manifest.json` bekræfter voice_only=true, avatar_present=false og provider=kokoro.

- Gaming: syv godkendte voice-segmenter. YouTube, TikTok, Reels, ZOOM og SAFE er produceret. Thumbnail og TikTok-billedserie er visuelt kontrolleret.
- Lokal AI: otte godkendte voice-segmenter og samme fem formater. Thumbnail og Reels-billedserie er visuelt kontrolleret.
- Alle ti videoer findes som rigtige filer over 1 MB. Ingen HeyGen-master eller avatar-overlay bruges.

## Backup, restore og live drift

- `python -m app.cli backup --verify`: rigtig backup `/data/backups/some-backup-20261110T161035Z.zip` er verificeret, ukrypteret og ikke offsite.
- `python -m app.cli restore --input ... --target /data/restore-verification-20261110`: integrity=ok. Den midlertidige restoremappe er ryddet.
- Negativtest med `../outside.txt` i ZIP blokeres både ved verify og restore; ingen fil skrives uden for målmappen.
- Web og worker er genstartet med nyeste build. `GET http://127.0.0.1:8000/healthz` returnerer `status=ok`, `publish_enabled=false`, `paid_jobs_enabled=false`.
- `python -m app.cli doctor`: migration 0001, FFmpeg/ffprobe/espeak-ng og modelcache bekræftet. Budget 50 DKK, forbrug 0 DKK, Sonnet/Haiku-modelnavne samt paid_jobs_enabled=false blev rapporteret uden secrets. Diskforbrug var 87,68 % (alarm, men under 90 % renderstop).

## Contabo-produktion 2026-11-10

- Cloud VPS Plus 6: 6 vCPU, 12 GB RAM, 300 GB NVMe, Ubuntu 24.04. Commit `9e194f3` er deployet med `./scripts/deploy.sh` og **73/73 tests bestod** på serveren.
- Første serverkørsel gav 68 passed + 1 failed, fordi backup-testen arvede BACKUP_KEY. Testen er isoleret, separat krypteret verify/restore er tilføjet, og paid-konfigurationen er også dækket. Slutresultatet er 73/73 lokalt og på serveren.
- Executable-bit er rettet på alle fem shellscripts. Standarddeployment fungerer uden Bash-workaround.
- SSH: verificeret ED25519-hostfingerprint, separat deploynøgle, `PermitRootLogin no`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`. UFW er aktiv med default deny og kun ejerens admin-IP på port 22.
- Web/worker er healthy. `/healthz` svarer ok med publishing=false og paid_jobs=true. Kun 127.0.0.1:8000 er åbent for web; ingen offentlig webport.
- En demokørsel i web-containeren stoppede med exit 137 på grund af 1 GB-grænsen. Den korrekte worker-service med 5 GB gennemførte `topic-2-v1`, video_id=1: 17,533 sekunder, 1080×1920, H.264 + AAC, AWAITING_OWNER, 10/10 manifesthashes og alle syv kontroller ALLOW.
- Kokoro `af_bella` genereret på VPS: 3,679 sekunder, 24 kHz mono, kontrol ALLOW, paid_call=false og cost_dkk=0.
- Krypteret backup `/data/backups/some-backup-20261110T211132Z.zip.enc`: encrypted=true og verified=true. Restore integrity=ok; midlertidig restoremappe er fjernet. Offsite=false.
- Dashboard-ejer `owner` er oprettet uden at vise adgangskoden. Initialkoden er kun i serverens root-beskyttede secret-mappe.
- Claude-prissætning: Frankfurter/ECB-kurs 2026-11-10, 1 USD=6,6661 DKK. Sonnet 13,3322/66,661 og Haiku 0,66661/3,33305 DKK pr. million input/output. API-nøgle er konfigureret uden at være vist.
- Sonnet-healthcheck: reply OK, 16 input + 4 outputtokens, 0,000480 DKK. Haiku-healthcheck: valid JSON, 33 input + 97 outputtokens, 0,000345 DKK.
- Live Haiku afslørede thinking-blokke; parseren vælger nu tekstblokke. En 50-token probe var for lille, mens 700 tokens virkede. Claimreview bruger nu 2.000 tokens for at undgå afkortet JSON.
- Live manuskriptevaluering afslørede manglende præcision i claim-skemaet. Promptversion v3 kræver nu id/text/source_url/verified. Reviewprompten kræver en flad issues-liste af strenge. Regressionstests dækker alle tre kontrakter.
- Komplet syntetisk eval: Sonnet skrev validt manuskript og claim; Haiku svarede ALLOW, issues=[]. Manuskript: 354 input + 402 outputtokens, 0,031517 DKK. Review: 707 input + 387 outputtokens, 0,001761 DKK.
- Samlet månedligt API-forbrug inklusive alle sundheds-, fejl- og evalkald: **0,142267 DKK** af 50 DKK. Alle costs er SETTLED; paid jobs er aktiveret. Ingen eval er publiceret eller gemt som socialt opslag.

## Live SoMe-integrationer — 2026-11-11

- **YouTube:** OAuth og kanaladgang verificeret. Privat upload `9EEY0uC9Xnc` er PRIVATE og processed. Ni Analytics-metrikker kunne læses. Begrænset researchnøgle gav 40 reelle observationer uden fejl.
- **Instagram:** Facebook Login for Business med systembrugertoken; konto `17841457024132563` / `@pixelandparameters` verificeret via Graph. Testreel `18110461838195602` er publiceret og verificeret på https://www.instagram.com/reel/DfmPOXZhJ3e/.
- **Facebook:** Side `1467423036459990` og koblingen til Instagram verificeret. Første URL-upload gav Graph-fejl 390; direkte multipart-upload er implementeret. Testreel `1691097949310064` er publiceret og verificeret som `/reel/1691097949310064/`.
- **TikTok:** Sandbox OAuth og målkonto `@pixelandparameters` er verificeret. Ejeren har vist TikTok-appens systemnotifikation “Din indhold fra SoMe-maskinen er klar”, som beviser kladde-levering til inboxen. Første upload havde intet gemt publish_id; publication 4 og video 4 er reconcileret med ejerbevis og audit event, uden en ny upload. `external_visibility=tiktok_draft_inbox`; det er ikke et offentligt opslag. Direct Post er slået fra.
- **Retry-sikkerhed:** Graph-fejldetaljer rapporteres uden tokens; FAILED video + publication kan genoptages uden dublet. Regressionstests dækker direct upload, Graph-fejl og retry.
- **Meta Unified Login:** Tokenudveksling virkede, men `assigned_instagram_accounts` gav nul konti. Derfor blev den understøttede Facebook Login-route med Page og linked Instagram brugt til den faktiske verificerede løsning.
- **Netværk/sikkerhed:** Caddy HTTPS er verificeret. Efter skiftende admin-IP'er er SSH nøglebaseret med root/password fra, UFW og Fail2ban aktive. `doctor` viser YouTube, Instagram, Facebook og TikTok som verificerede. Publishing er slået fra igen efter testene.
- **Backup:** `/data/backups/some-backup-20261111T140525Z.zip.enc` er encrypted=true og verified=true; offsite=false.
- **Vigtigt:** Testopslagene var integrationstests med særskilt ejergodkendelse. De er ikke kreative produktionsgodkendelser. **Kokoro-stemmen er efterfølgende afvist af ejeren og må ikke bruges til nye produktionsopslag.**

## Review-center og reel opslagsrevision — 2026-11-11

- Commit `ab01f5f` er deployet. Standardbuild og `docker compose run --rm --no-deps worker pytest -q` gav **81 passed** lokalt; deploymentens standardtest gav **81 passed** på VPS. Web/worker er healthy.
- Automatiske HTTP-tests dækker login/CSRF, komplet opslagsvisning, forbundet konto, tom afvisningskommentar, afvisning, revisionskø, worker, nyt manifest, idempotens, ny godkendelse og approvalhash. Video/thumbnail og alle ti manifestfiler hashes.
- En rigtig HTTPS-test oprettede demo 5 via normal CLI. Med midlertidig ejerkonto blev demo 5 afvist med kommentaren “Make the title shorter and the caption more direct. Keep it practical and use relevant gaming hashtags.”
- `/review/5/revise` sendte jobbet til den rigtige worker. Claude svarede med en ny titel/caption/hashtags. `revise_post` lykkedes på første forsøg og oprettede demo 6 med status AWAITING_OWNER og `revision_scope=title_caption_hashtags`.
- Demo 6 har titlen “Gaming Handheld Buying Checklist”, caption “Choosing a gaming handheld? Check your games, budget, operating system and play sessions first. Verify current details before you buy.” og hashtags `gaming`, `handheldgaming`, `gamingtips`, `buyingguide`, `checklist`, `tech`.
- Live revision kostede **0,0131722136 DKK**. Samlet kendt Claude-testforbrug er cirka **0,155439 DKK**. Testen godkendte eller publicerede ikke demo 6. Den midlertidige testkonto og dens sessions er slettet.
- Beskyttede HTTPS-kald bekræftede `/review`, `/review/6`, `/static/style.css`, `/static/app.js`, `/media/6/thumbnail.jpg` og `/media/6/video.mp4`. Video er 2.065.008 bytes, thumbnail er 62.345 bytes og MIME-typerne er korrekte. Thumbnail er visuelt læst. Kimi Desktop-browserens visuelle panel viste et tomt dokument og kunne ikke bruges som screenshotbevis; dette er ikke markeret som visuel browserverificering.

## Reel mediepipeline og 100 % demo — 2026-11-11

- Commits `95ff191`, `4de19fe` og `24a4820` er pushet og deployet. Standardbuild og hele testpakken gav **89 passed** lokalt og på VPS. Web/worker er healthy.
- Ny produktion kræver `--media-plan`; `demo --produce` kræver samme plan. Pillow-slide-fallback er ikke længere standardproduktion. Ranking skriver 100 % reel dækning for sine ti rigtige klip.
- Tests bekræfter exact 80 % ALLOW, 75 % BLOCK, forbud mod lavere grænse, `ai_generated_cannot_count_as_real`, HTTPS source/policy, path containment, filsignatur, source duration og caption/scene-match.
- FFmpeg-test producerer faktisk 1080×1920 H.264/AAC med real_video + real_image/zoom_in. JPEG full-range konverteres eksplicit til begrænset `yuv420p`; den oprindelige pixel-formatfejl er rettet uden at svække testen.
- `media_composition.json` er den 11. manifestfil. Approval kræver ALLOW for media_composition, og ZIP-eksport kræver filen. Review viser procent på kort og detaljeside; ældre formater markeres som ældre.
- Qwen-storyboardreview har mocktest for API/workspace/prisblokering, billedpayload, endpoint, JSON og DKK-settlement. `doctor` viser alle tre Qwen-konfigurationer som false. Der er ikke foretaget et eksternt Qwen-/Wan-kald eller påløbet omkostning.
- Den konkrete plan `research/top10-legion-go2/real-media-demo.json` kræver 100 % og bruger fem officielle udgiverklip. Demo 8 er produceret på VPS med Transistor, Celeste, Slay the Spire, Hollow Knight og Hades.
- Demo 8: video_id=8, topic_id=8, 17,5 sekunders reel tidslinje, 17,6 sekunders output, fem real_video, nul real_image, nul graphic, **100 % reel mediedækning**, 11 manifestfiler og teknisk ALLOW. MP4 er 10.375.109 bytes.
- MP4, storyboard og thumbnail er downloadet og visuelt kontrolleret. Titel/caption-kontrast er forbedret. Thumbnail er et rent frame fra Hollow Knight-originalklippet ved 74,639 sekunder uden captions eller titeloverlay; manifesthash er opdateret.
- Demo 6 (syntetisk) og demo 7 (første reel rendering) er markeret REJECTED som erstattede af demo 8 med audit events. Demo 8 er AWAITING_OWNER, ikke godkendt og ikke publiceret.
- Ny krypteret backup `/data/backups/some-backup-20261111T155413Z.zip.enc` er verified=true og external_offsite=false.
- Officielle kilder for senere arbejde: NVIDIA GeForce NOW-vilkår https://www.nvidia.com/en-us/geforce-now/terms-of-use/ (personlig, ikke-kommerciel, én session, ingen botting); Qwen Vision https://www.alibabacloud.com/help/en/model-studio/vision; Wan async API https://www.alibabacloud.com/help/en/model-studio/text-to-video-api-reference; priser https://www.alibabacloud.com/help/en/model-studio/model-pricing. Wan2.7 1080P er $0,15/sekund, så 10 sekunder koster $1,50, cirka 10 DKK og overstiger 5 DKK-jobloftet.

## Lokal OBS Capture Bridge — 2026-11-11

- OBS Studio 33.0.1 er fundet på `C:/Program Files/obs-studio/bin/64bit/obs64.exe`. FFmpeg 9.0.2 er installeret via winget med verificeret pakkehash.
- `scripts/capture_bridge.py` er commitet med hemmelighedsfri eksempelkonfiguration. Tests dækker HTTPS-konfiguration, MKV→MP4, kontaktark, manifest, idempotens og spilvalg via filnavn. Hele pakken er **94 passed** på det nybyggede image.
- Lokal Windows-test med en kort syntetisk MKV gav MP4 på 1.557.388 bytes, kontaktark og `some-capture-v1` manifest med `source_type=owned_gameplay`, `ai_generated=false` og `publication_allowed=false`.
- Første upload stoppede på remote ejerskab. Upload er rettet til midlertidig deploy-ejer før SCP og containerbruger 10001 bagefter; genforsøg kan genbruge den lokale outputmappe. Andet forsøg lykkedes, og filerne blev verificeret på VPS.
- Serverens midlertidige testmappe `/opt/some/data/media-library/hades/20261111-193934-bridge-selftest` er slettet. De lokale testinput/output er også fjernet. Ingen reel spiloptagelse eller publicering er foretaget.
- Watcher er startet med upload aktiveret. Den overvåger `C:/Users/compu/Videos/SoMe-captures`, gemmer under `SoMe-processed` og uploader via eksisterende SSH-nøgle uden at læse eller vise den. Nye filer navngives `hades-*`, `celeste-*` eller `slay-the-spire-*`.
- Grok CLI blev kontrolleret med `grok --help`: headless prompt findes, men det er en lokal proces og viser ingen videogenerering. Lokale CLI'er kan ikke køre med computeren slukket. Veo/Imagine skal vurderes separat som cloud-API med egen nøgle og pris.
- ElevenLabs API er verificeret med aktivt Creator-abonnement, character_limit 121.003 og kommerciel licens. De valgte ID'er blev først fundet via `/v1/shared-voices`, fordi de ikke lå i det personlige bibliotek. `POST /v1/voices/add/{public_user_id}/{voice_id}` returnerede 200 for begge med originale ID'er intakt.
- Gaming er Chris – Fast-Paced Informative Narrator (`HfRP3cIhYLmeNHeTvkWK`); AI er Nathaniel C – Expressive Social Media Creator (`8CjmkufHc22WbMZEBHbm`). Pris er konfigureret til 0,533288 DKK/1.000 tegn, rettigheder er bekræftet, og begge WAV-tests er ALLOW.
- Gamingtest: 3,437 sekunder, 48 kHz mono og 0,031464 DKK. AI-test: 3,158 sekunder, 48 kHz mono og 0,03573 DKK. Samlet beregnet testpris er 0,067194 DKK. Lokale previews er `voice-previews/gaming.wav` og `voice-previews/ai.wav`. Intet er publiceret.
- ElevenLabs svarede uden `x-request-id`, hvilket afslørede at adapteren fejlagtigt rapporterede `paid_call=false` og actual_cost=null. Adapteren registrerer nu succesfulde HTTP-kald med `successful_provider_calls`; regressionstest dækker manglende request-ID og korrekt omkostningsregistrering. Hele pakken er **96 passed**.
- Capture Bridge er udvidet til rekursive spilmapper og ukendte mapper stopper i stedet for at blive fejlregistreret som Hades. Hele testpakken er **96 passed**.
- Alle fire Monster Train 2-klip er uploadet. Lokale MP4-hashes er identiske med serverens hashes: `4e5e8b26`, `2c51c88f`, `5c232681` og `fbd6f930`. Filerne er dermed verificeret byte-for-byte.
- Alle fire AI-optagelser er uploadet med `source_type=owned_screen_recording`. Ældre Hades-kopier og den uklassificerede rodfil er flyttet til karantæne, og originalerne er uændrede. Watcher er genstartet med den nyeste kode. Der produceres ingen nye videoer før ejerens go.

## Ikke verificeret / blokeret

- Kokoro er afvist til fremtidig produktion. ElevenLabs-stemmerne er valgt af ejeren og verificeret med korte live tests; længere produktionskvalitet og faktisk leverandørfaktura er ikke verificeret.
- Claude er verificeret med syntetisk eval og én live opslagsrevision, men faktisk leverandørfaktura og produktionskvalitet på rigtige researchkilder er ikke verificeret. Bankkurs og eventuel moms kan afvige.
- TikTok production-demo og app-review mangler. YouTube Testing-token og Meta App Review/Advanced Access kræver senere produktionsforvaltning. Reelle langtidsmetrics og dokumenteret læringsforbedring findes ikke endnu.
- Fuld automatisk research → licenseret produktion → rendering og multiplatformsplanlægning er ikke implementeret. Revisionsfunktionen retter kun posttekst og genbruger video/lyd/visuals.
- Contabos cloudfirewall og offsite backup er ikke konfigureret. Endelig faktura og moms er ikke verificeret.
- Dansk TTS er ikke kvalitetsgodkendt. FPS/batteritid på Legion Go 2 er ikke målt; rangeringen er redaktionel.

## Regel

“Bestået” betyder udført i det angivne miljø. Der gives ingen 100 % fejlfriheds-, integrations- eller performancegaranti. Manglende ekstern adgang og ejergodkendelse rapporteres som åbne punkter, aldrig som succes.


## Content Bible v1.1, immutable multi-publicering og ElevenLabs — 2026-11-12

- Content Bible/Kimi Kit er integreret med 20 recipes, 120 idéer, 57 kilder og 46 kit-kontrakttests. Steam reception og friskheds-/receptionsgates har separate negative tests.
- Multi-approval dækker alle fire destinationer, konkrete konto-ID'er, YouTube-synlighed og UTC-schedule. Tests beviser at afvisning ikke opretter jobs, dubletapproval ikke opretter dubletjobs, og ændret video/thumbnail/destination/konto/visibility/tidspunkt blokerer dispatch.
- Delvis succes og delvis fejl er testet. Pakken bliver først PUBLISHED når alle valgte destination/konto-par er bekræftet. YouTube-coverfejl efter upload giver RECONCILE_REQUIRED fremfor blind reupload.
- TikTok Sandbox/inbox er ikke længere en gyldig published-tilstand i den aktive adapter. Uden alle eligibility-flag er blocker `tiktok_direct_post_not_eligible`. En fuldt mocket eligible test bruger creator_info og Direct Post-endpointet og accepterer kun PUBLISH_COMPLETE. Der er ikke foretaget et nyt TikTok-kald.
- ElevenLabs mocktests bruger `/with-timestamps`, Base64-PCM, request-ID, rå/normaliseret alignment, varighed, succesfulde kald og tegnbaseret DKK-pris. Alignment skaber faktiske SRT-cues og tekstmismatch blokerer. En fuld syntetisk AI-produktion vælger `8CjmkufHc22WbMZEBHbm`, gemmer cost og artifacts.
- YouTube mocktest afventer `processingStatus=succeeded` og kalder `thumbnails.set` med godkendt JPEG. Instagram mocktest sender både video_url og cover_url. Signet thumbnail er bundet til multi-approvalhashen og ændringer blokerer.
- Standardbuild og fuld pakke i frisk container: **178 passed**. Kun Starlette TestClient-deprecationwarning.
- Ingen nye ejervideoer er produceret, og `C:/Users/compu/Videos/SoMe-captures` er ikke ændret. Reel pilotproduktion og publicering afventer ejerens eksplicitte go samt platformspecifikke eligibility-forhold.

- Deployment `0fcc524` på VPS gav ligeledes **178 passed**. Første serverkørsel fangede miljøafhængighed i ElevenLabs-guard-testen; testen sætter nu eksplicit pris/dato/rettigheder til tomme værdier og bestod både lokalt og på VPS efter rettelsen.
- Standarddeployment fuldførte migration 0001 og doctor. Web og worker blev efterfølgende kontrolleret som healthy. `GET /healthz` på loopback og HTTPS returnerede `status=ok`, `publish_enabled=false`, `paid_jobs_enabled=true`.
- VPS doctor: `direct_post_eligible=false`, `direct_post_blocker=tiktok_direct_post_not_eligible`; ElevenLabs konfigureret. Ingen ny ekstern publicering eller betalt produktion blev udført under deployment.

- Endelig auditrevision `0fcc524`: Editorial-pakke er koblet til ikke-demo-produktion med JSON Schema, lane-match, 85-pointsgate, inspected sources og receptionskrav. Ranking har samme gates pr. featured game. Tests dækker research-state, udløb, manglende spoken reception, ændret narrationartifact og blokeret dispatch efter evidensudløb. Resultat lokalt og på VPS: **178 passed**; web/worker healthy.

## Ejergodkendt intro/outro i alle nye formater — 2026-11-13

- Den godkendte animation/lyd er flyttet til den fælles produktionskomponent `app/pipeline/brand_ident.py`; den gamle testpost-renderer delegerer til samme kilde. Der er ikke lavet en alternativ visuel version.
- Almindelig reel medieproduktion og editorial ranking tilføjer automatisk 3,5 sek. intro og outro. YouTube vælger 1920×1080; øvrige destinationsformater bruger 1080×1920.
- To parametriserede integrationstests opretter korte syntetiske testklip og udfører den rigtige FFmpeg-sammenføjning i begge formater. Tests kontrollerer opløsning, H.264, yuv420p, 30 fps, 240 frames, AAC stereo 48 kHz og varighed. 3,5 + 1,0 + 3,5 sek. giver 8 sek.; den målte 8,021333 sek. er AAC-padding og ligger inden for den korrekte tolerance 7,9–8,1 sek.
- Den første testforventning på 8,3–8,7 sek. var en regnefejl og er rettet efter ffprobe af intro, indhold, outro og resultat. Produktionsvideoernes indhold ændredes ikke for at passe testen.
- Ident-cachen afhænger af både logo- og rendererhash. Testdata-dir respekteres, så testen ikke utilsigtet genbruger serverens gamle identer. `content.mp4` bevares som det rene redaktionelle indhold, mens det endelige `video.mp4` indeholder ident + indhold + ident.
- Standardbuild og hele pakken: **181 passed**, kun den kendte Starlette TestClient-deprecationwarning. Ingen nye redaktionelle ejervideoer er produceret, eksisterende opslag er ikke ændret, og `C:/Users/compu/Videos/SoMe-captures` er urørt.
- Commit `12d4b0b4` er pushet og deployet med `./scripts/deploy.sh`. Hele pakken bestod også på VPS: **181 passed**. Migration 0001 og doctor er OK. Web og worker er healthy, og loopback samt offentlig HTTPS-health returnerer `status=ok`, `publish_enabled=false`, `paid_jobs_enabled=true`. Ingen publicering eller betalt produktion blev udført.

## MobyGames-forberedelse og cross-platform-footage — 2026-11-13

- `app/pipeline/game_research.py` er en fælles kontrakt for konkret MobyGames-spilside, review score/not-found-note, fun facts/not-found-note, observationstidspunkt og dokumenterede udgivelsesplatforme.
- Både almindelig editorial-pakke og ranking kræver research for hvert featured game. Forkert kildevært, manglende preparation, udløbet research og udokumenteret målplattform blokerer. Almindelige pakker skal desuden have MobyGames- og release-URL'er registreret som inspicerede kilder.
- Tests beviser at PS5-footage må bruges til et PC-opslag med dokumenteret PC-udgivelse, mens et Switch 2-opslag uden Switch 2-dokumentation blokeres. `cross-platform` kræver ingen bestemt konsol. Aliaser som PlayStation 5, Nintendo Switch 2, PC games og X box Series X normaliseres.
- Capture Bridge behandler platformmapper som proveniens. Tests beviser genkendelse af spilnavn i et PS5-filnavn og sikker `unknown`-stop ved et ukendt spil i Switch 2-mappen. Manifestet markerer at release_platforms kræver separat verificering.
- MobyGames åbnede med Cloudflare-botskontrol. Der er ikke udført bypass eller automatisk scraping. Den konkrete MobyGames-URL til Into the Breach blev fundet via almindelig websøgning; testpakkens score/trivia er syntetiske og hævder ingen rigtige værdier.
- Standardbuild og hele testpakken: **191 passed**, kun den kendte Starlette TestClient-deprecationwarning. Ingen redaktionelle videoer, eksisterende opslag eller ejerfootage er produceret eller ændret.
