SoMe-maskinen — pilot 0.1.0
============================

Formål
------
Research, rettighedssikker videoproduktion med rigtige medier, obligatorisk ejergodkendelse, manuel/API-publicering, metrics og versionsstyret læring. Standardtilstand er DRY_RUN=true, PUBLISH_ENABLED=false og PAID_JOBS_ENABLED=false.

Lokal Docker-demo (uden konti eller API-nøgler)
-----------------------------------------------
Kør fra denne mappe:

  docker compose build
  docker compose run --rm --no-deps worker python -m app.cli migrate
  docker compose run --rm --no-deps worker python -m app.cli doctor
  docker compose run --rm --no-deps worker python -m app.cli research --demo --output /data/reports/demo
  docker compose run --rm --no-deps worker python -m app.cli demo --produce --media-plan /data/media-plans/real-demo/real-media-demo.json

En medieplan og dens lokale, rettighedsgodkendte videofiler skal ligge i samme mappe. `research/top10-legion-go2/real-media-demo.json` er et konkret eksempel med fem officielle udgiverklip. Kopier planen og klipmappen til /data/media-plans/real-demo når den køres i containeren. Første produktionskørsel henter faster-whisper small fra den officielle Hugging Face-modelkilde. Demovideoen er tydeligt mærket DEMO og stopper i AWAITING_OWNER. Output findes under data/versions.

Opret dashboard-ejer (brug et langt, unikt password; del det ikke i chat):

  Linux/macOS: export APP_ADMIN_PASSWORD='INDSÆT LOKALT STærKT PASSWORD'
  Windows PowerShell: $env:APP_ADMIN_PASSWORD='INDSÆT LOKALT STÆRKT PASSWORD'
  docker compose run --rm --no-deps -e APP_ADMIN_PASSWORD worker python -m app.cli init-user --username owner
  docker compose up -d

Åbn http://127.0.0.1:8000. På serveren bruges i stedet SSH-tunnel:

  ssh -N -L 8000:127.0.0.1:8000 -i ~/.ssh/some_pilot deploy@SERVER_IP

Konti og secrets
----------------
Kopiér aldrig .env eller secrets ind i Git. Lokalt bruges den hemmelighedsfrie .env.example. På serveren oprettes /opt/some/secrets/app.env manuelt med chmod 600 og ejer, som deployprocessen kan læse. compose.production.yaml peger på den fil. Direkte konto-/nøglebehov står samlet i ../OWNER_ACTIONS.md.

Claude er rutet med Sonnet til manuskripter/revision og Haiku til research/claimkontrol. Modellerne har separate DKK-tokenpriser. Standardbudgettet er 50 DKK/måned og 5 DKK/job. Paid jobs er slået fra, og kald blokeres før netværk uden API-nøgle og verificerede priser. Qwen-storyboardreview kræver desuden DASHSCOPE_API_KEY, QWEN_WORKSPACE_ID og separate verificerede tokenpriser. Qwen er ikke konfigureret som standard. Kokoro, Whisper og FFmpeg kræver ingen betalt AI API.

Reel medieproduktion — obligatorisk 80 %
------------------------------------------
Al ny produktion kræver `--media-plan`. Den gamle Pillow-slide-produktion er ikke standardgenvejen. Hver scene kan være:

- `real_video`: producentklip, generisk kontekstklip eller eget gameplay.
- `real_image`: et rigtigt foto med `static`, `zoom_in`, `zoom_out`, `pan_left` eller `pan_right`.
- `graphic`: en kort title card, som højst må fylde 20 % af den samlede tidslinje.

Mindst 80 % af varigheden skal være real_video/real_image. Planens `minimum_real_ratio` kan være højere, men aldrig lavere. Andelen måles pr. varighed, ikke pr. antal scener. `ai_generated=true` kan ikke bruges til at tælle AI-video som reel. Filsignatur, kildepath, videostream og source duration valideres. Hvert asset har kontekst, HTTPS source/policy URL, rettighedshaver, bevis, kreditering og aldersmetadata. Rettigheder og medieprocent skal være ALLOW før rendering og ved godkendelse.

`media_composition.json` dokumenterer procent, varighed, scenetyper og kontekst. Manifestet har 11 hashed leverancefiler. Thumbnail vælges som et rent frame fra originalkilden uden undertekster/titeloverlay. Review-kort og detailvisning viser reel medieprocent; ældre formater markeres som ældre.

CLI-kontrakt
------------
  python -m app.cli doctor
  python -m app.cli research --days 30 --output /data/reports
  python -m app.cli produce --topic-id ID --dry-run --media-plan /data/media-plans/PLAN.json
  python -m app.cli metrics --due
  python -m app.cli learn --weekly
  python -m app.cli backup --verify
  python -m app.cli pause --all

Yderligere sikre kommandoer: migrate, demo, approve, export, publish, restore, recover-jobs, init-user. `demo --produce` kræver også `--media-plan`. Mutationskommandoer skriver maskinlæsbare resultatfiler under data/results. Publicering kræver aktivt enablement, gyldig ejergodkendelse og understøttet adapter; ellers bruges ZIP-eksport med media_composition.

Review-center, godkendelse og publicering
-----------------------------------------
`/review` samler færdige opslag med video, thumbnail, titel, opslagstekst, hashtags, kilder, platform, konto og medieprocent. Platform forhånds vælges fra metadata, og konto-ID udfyldes fra integrationen. Ejeren kan godkende eller afvise med konkret kommentar. `revise_post` omskriver kun titel, caption og hashtags, genbruger video/lyd/visuals og kræver ny godkendelse. Selve afvisningen eller rettelsen publicerer aldrig noget.

Kun en autentificeret ejer kan godkende. Hele videoen skal bekræftes set. Godkendelsen binder SHA-256 for video/thumbnail samt tekst, links, platform og konto. Checks inkluderer media_composition. Enhver ændring kræver ny godkendelse. PUBLISH_ENABLED=false, DRY_RUN=true og nødstop kontrolleres centralt før upload. Upload-timeout giver RECONCILE_REQUIRED, ikke blind retry. Revisionsjobs er idempotente pr. afvisning.

Lærende hjerne
--------------
Systemet gemmer features før publicering og metrics efter ca. 1, 3, 7 og 28 dage. Ugentlig læring sammenligner kun samme platform/format og metricalder, viser median/spredning/sample size og bruger afdæmpede prioritetsmultiplikatorer. Eksterne opslag er researchsignaler, ikke bevis eller produktionsmateriale. 80 % kendte formater / 20 % nye forsøg er standard. Demo og produktion har separate læringsmodeller; kun reel læring kan påvirke produktionsprompts. Der er ingen automatisk fine-tuning, kodeændring eller politikændring.

Backup og gendannelse
---------------------
`backup --verify` bruger SQLite Online Backup API, inkluderer godkendte outputs og kontrollerer ZIP, DB-integrity og filhashes. Uden BACKUP_KEY er lokal backup ukrypteret og ikke produktionsgodkendt. Generér en Fernet-nøgle lokalt og opbevar den separat; offsite upload er bevidst ikke konfigureret uden ejerens valg. Gendan altid til en tom separat mappe med `restore`; publishing og betalte jobs forbliver slået fra via miljøet.

Server
------
Produktionen kører Contabo Cloud VPS Plus 6 med Ubuntu 24.04, 6 vCPU, 12 GB RAM og 300 GB NVMe. Se scripts/deploy.sh og STATUS. Dashboardet bindes til loopback bag Caddy, og ejerens aktuelle IP skal være whitelistet.

Tests
-----
  docker compose build
  docker compose run --rm --no-deps worker pytest -q

Den aktuelle pakke har 89 tests. Testprotokol og faktiske resultater ligger i TEST_PROTOCOL.md og STATUS.txt. Eksterne integrationer er ikke erklæret verificerede, før relevante private uploads og metrics er gennemført på ejerens konti.

Gameplay-ranking (internetklip og lokal voiceover)
-------------------------------------------------
Top-10-videoer bruger voiceover uden avatar. **Kokoro `af_bella` er afvist kreativt af ejeren og må ikke bruges til nye produktionsopslag.** Den tekniske provider findes til tidligere tests, men der skal vælges en ny godkendt stemme før ny produktion. En eksisterende stemmemappe genbruges kun når alle 11 segmenter har matchende manuskriptmetadata, gyldig WAV, lydstream, varighed, sample rate, teksthash og SHA-256. Den eksisterende tekniske CLI-kontrakt er:

  python -m app.cli ranking --plan /research/plan.json --platform reels --mobile-style zoom --voice-provider kokoro --output /data/versions/NY-VERSION

Når `voice_dir` udelades, genereres nye segmenter lokalt. `voice_assets.json` dokumenterer provider, teksthash, varighed, sample rate, filhash og licens og indgår i de 11 manifestfiler. ElevenLabs er valgfri og kræver eksplicit provider, paid jobs, API-nøgle, voice-ID og dateret pris inden for budget. Der er ikke verificeret et betalt ElevenLabs-kald.

Rankingplanen kræver ti unikke spil og officielle klip-/politik-URL'er, rettighedshaver, bevis, kreditering og claims. Den skriver 100 % reel mediedækning for de ti rigtige videoklip. Manglende eller ugyldige filer stopper produktionen. Platformvarianter er TikTok 9:16, Reels 9:16 og YouTube 16:9 med forskellige crops og thumbnails. Rigtige klipfiler og stemme-WAV er udelukket fra Git.

GeForce Now, Qwen og Wan
------------------------
GeForce Now er ikke konfigureret. NVIDIAs vilkår beskriver personlig, ikke-kommerciel brug, én session ad gangen og forbud mod botting. Der laves ingen skjult auto-gameplay. En senere optagelse skal være ejerstyret med OBS og kontrol af spillets politik. Se https://www.nvidia.com/en-us/geforce-now/terms-of-use/

Qwen-storyboardreview er implementeret, men ikke konfigureret eller eksternt verificeret. Qwen Vision: https://www.alibabacloud.com/help/en/model-studio/vision. Wan text-to-video er asynkron API: https://www.alibabacloud.com/help/en/model-studio/text-to-video-api-reference. Wan2.7 koster ifølge den officielle prisside $0,10/sekund ved 720P og $0,15/sekund ved 1080P: https://www.alibabacloud.com/help/en/model-studio/model-pricing. Betalte kald kræver separat pris- og budgetaccept, og AI-output tæller ikke som reel medieprocent.


Lokal OBS Capture Bridge
------------------------
OBS og FFmpeg behandler nye optagelser på Windows via `scripts/capture_bridge.py`. Konfigurationen ligger som `capture_bridge.example.json`; den faktiske lokale konfiguration og SSH-nøglen ligger uden for Git.

  python scripts/capture_bridge.py --config /path/capture_bridge.json --input /path/hades-run.mkv --game hades
  python scripts/capture_bridge.py --config /path/capture_bridge.json --watch --upload

Nye filer i `C:/Users/compu/Videos/SoMe-captures` overvåges, ventes skriveferdige og konverteres til MP4 med kontaktark og `some-capture-v1` manifest. Output ligger i `SoMe-processed/<spil>/` og kan uploades via eksisterende SSH-forbindelse til `/opt/some/data/media-library/<spil>/`. Brug filnavne som `hades-*`, `celeste-*` eller `slay-the-spire-*`; andre filnavne bruger standardprofilen. Upload kan udelades ved at undlade `--upload`. Ingen optagelse publiceres automatisk, og rettigheds-/ejergodkendelse er stadig obligatorisk.

Grok, Gemini og Qwen CLI er lokale processer og kan ikke køre med computeren slukket. Et CLI-abonnement er ikke en cloud-API eller en videogenereringskontrakt. Separate Veo/Imagine API'er kræver egen nøgle, pris og rettighedsafklaring. ElevenLabs bruger den eksisterende paid-/pris-/rettighedsblokerede adapter og aktiveres først efter hemmelig nøgleopsætning og kontrol af abonnementet.
