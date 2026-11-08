SoMe-maskinen — pilot 0.1.0
============================

Formål
------
Research, original videoproduktion, rettigheds- og sikkerhedskontrol, obligatorisk ejergodkendelse, manuel/API-publicering, metrics og versionsstyret læring. Standardtilstand er DRY_RUN=true, PUBLISH_ENABLED=false og PAID_JOBS_ENABLED=false.

Lokal Docker-demo (uden konti eller API-nøgler)
-----------------------------------------------
Kør fra denne mappe:

  docker compose build
  docker compose run --rm --no-deps web python -m app.cli migrate
  docker compose run --rm --no-deps web python -m app.cli doctor
  docker compose run --rm --no-deps web python -m app.cli research --demo --output /data/reports/demo
  docker compose run --rm --no-deps web python -m app.cli demo --produce

Første produktionskørsel henter faster-whisper small fra den officielle Hugging Face-modelkilde. Det kræver net og disk, men ingen API-nøgle. Demovideoen er tydeligt mærket DEMO og stopper i AWAITING_OWNER. Output findes under data/versions.

Opret dashboard-ejer (brug et langt, unikt password; del det ikke i chat):

  Linux/macOS: export APP_ADMIN_PASSWORD='INDSÆT LOKALT STærKT PASSWORD'
  Windows PowerShell: $env:APP_ADMIN_PASSWORD='INDSÆT LOKALT STÆRKT PASSWORD'
  docker compose run --rm --no-deps -e APP_ADMIN_PASSWORD web python -m app.cli init-user --username owner
  docker compose up -d

Åbn http://127.0.0.1:8000. På serveren bruges i stedet SSH-tunnel:

  ssh -N -L 8000:127.0.0.1:8000 -i ~/.ssh/some_pilot deploy@SERVER_IP

Konti og secrets
----------------
Kopiér aldrig .env eller secrets ind i Git. Lokalt bruges den hemmelighedsfrie .env.example. På serveren oprettes /opt/some/secrets/app.env manuelt med chmod 600 og ejer, som deployprocessen kan læse. compose.production.yaml peger på den fil. Direkte konto-/nøglebehov står samlet i ../OWNER_ACTIONS.md.

CLI-kontrakt
------------
  python -m app.cli doctor
  python -m app.cli research --days 30 --output /data/reports
  python -m app.cli produce --topic-id ID --dry-run
  python -m app.cli metrics --due
  python -m app.cli learn --weekly
  python -m app.cli backup --verify
  python -m app.cli pause --all

Yderligere sikre kommandoer: migrate, demo, approve, export, publish, restore, recover-jobs, init-user. Mutationskommandoer skriver maskinlæsbare resultatfiler under data/results. Publicering kræver aktivt enablement, en gyldig ejergodkendelse og en understøttet adapter; ellers bruges ZIP-eksport.

Godkendelse og publicering
--------------------------
Kun en autentificeret ejer kan godkende. Hele videoen skal bekræftes set. Godkendelsen binder SHA-256 for video/thumbnail samt tekst, links, platform og konto. Enhver ændring kræver ny godkendelse. PUBLISH_ENABLED=false, DRY_RUN=true og nødstop kontrolleres centralt igen umiddelbart før upload. Upload-timeout giver RECONCILE_REQUIRED, ikke blind retry.

Lærende hjerne
--------------
Systemet gemmer features før publicering og metrics efter ca. 1, 3, 7 og 28 dage. Ugentlig læring sammenligner kun samme platform/format og samme metricalder, viser median/spredning/sample size og bruger afdæmpede, begrænsede prioritetsmultiplikatorer. Eksterne opslag bruges som researchsignaler, ikke som bevis eller produktionsmateriale. 80 % kendte formater / 20 % nye forsøg er standard. Demo og produktion har separate læringsmodeller og rapport-/promptfiler; kun reel læring kan påvirke produktionsprompts. Der er ingen automatisk fine-tuning, kodeændring eller politikændring.

Backup og gendannelse
---------------------
`backup --verify` bruger SQLite Online Backup API, inkluderer godkendte outputs og kontrollerer ZIP, DB-integrity og filhashes. Uden BACKUP_KEY er lokal backup ukrypteret og ikke produktionsgodkendt. Generér en Fernet-nøgle lokalt og opbevar den separat; offsite upload er bevidst ikke konfigureret uden ejerens valg. Gendan altid til en tom separat mappe med `restore`; publishing og betalte jobs forbliver slået fra via miljøet.

Server
------
Standard er Ubuntu 24.04 LTS, 4 delte x86-vCPU, 8 GB RAM og mindst 80 GB SSD. Ingen GPU. `scripts/install.sh` køres kun på den nye server efter pris-/købsgodkendelse. Det låser ikke SSH ned automatisk. Verificér deploy-login før root/password-login deaktiveres. Brug både cloudfirewall og UFW; dashboardet bindes til loopback. Se scripts/deploy.sh og STATUS.

Tests
-----
  docker compose run --rm --no-deps web pytest -q

Testprotokol og faktiske resultater ligger i TEST_PROTOCOL.md og STATUS.txt. Eksterne integrationer er ikke erklæret verificerede, før relevante private uploads og metrics er gennemført på ejerens konti.

Gameplay-ranking (internetklip som standard)
-------------------------------------------
Produktionen af top-10-videoer bruger `python -m app.cli ranking --plan /research/plan.json --platform reels --output /data/versions/handheld-reels-v2`. Planen skal indeholde præcis ti unikke spil, et lokalt videoklip til hvert spil, officiel clip-URL og politik-URL, rettighedshaver, bevis, kreditering og musikvalg. Manglende eller ugyldige videofiler stopper produktionen. Den gamle Pillow-demo er tydeligt mærket DEMO og er ikke standardproduktion. Almindelig ikke-demo-produktion uden licenserede internetassets blokeres med `licensed_internet_assets_required`.

Platformvarianter: `tiktok` giver kortere/hurtigere kommentar og tæt 9:16-action, `reels` giver fuld 9:16-action med Reels-safe-area og gem/del-CTA, mens `youtube` giver 16:9 med længere kommentar og landskabsthumbnail. `scripts/build_platform_plans.py` laver de redaktionelle planer. `scripts/prepare_kokoro.py` henter den Apache-2.0-licenserede Kokoro-model og genererer neural lokal speak med dokumenteret SHA-256. Stemmehastighed vælges pr. platform. `scripts/New-RankingVoice.ps1` og espeak-ng er kun fallbacks.

`scripts/fetch_steam_gameplay.py` henter kun officielle Steam-udgivervideoer efter rettighedskontrol. `scripts/review_steam_clips.py` laver kontaktark og den redaktionelle plan. Output stopper i AWAITING_OWNER og inkluderer video, thumbnail, SRT, storyboard, rettigheder, checks og manifest. Rigtige klipfiler og stemme-WAV ligger lokalt og er udelukket fra Git. Platform og billedformat gemmes som læringsfeatures.
