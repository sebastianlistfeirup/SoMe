SoMe-maskinen
Mini-bibel til en
AI-udviklingstjeneste

VERSION 1.3 · 8. NOVEMBER 2026 · DANSK

Byg et billigt cloudsystem, der undersøger aktuelle trends, producerer originale videoer, klargør opslag
og lærer af resultaterne. Målet er dokumenteret mulighed for afkast uden at skade ejerens professionelle
omdømme.

Grundmodellen er én Linux-server, gratis software og Claude API. Ejerens computer skal kunne være
slukket. Start med én niche, ét hovedsprog, to platforme og 20-30 originale videoer i et 60-dages forsøg.

Dette er en selvstændig bygge- og driftsinstruktion. Den kræver ikke adgang til den samtale, den
kommer fra. Den beskriver det system, der skal implementeres; den er ikke et allerede installeret
produkt.

Til den udførende AI: Læs hele dokumentet. Begynd med kapitel 1 og markedsundersøgelsen i kapitel 3.
Brug standardvalgene, medmindre dokumenterede forhold kræver en ændring. Fortsæt med alle
opgaver, som ikke afhænger af manglende konti eller nøgler.

En AI-tjeneste skal have adgang til web, kodefiler og et terminal-/deploymiljø for selv at udføre hele
byggeriet. En ren chatmodel kan udarbejde kode og instruktioner, men kan ikke købe en server,
gennemføre identitetskontrol eller godkende OAuth på ejerens vegne.

Alle beløb er planlægningsrammer. Leverandørpriser, modelnavne og platformkrav kontrolleres igen på
udførelsesdagen. Dokumentet giver ikke garanti for monetisering, indtjening eller fejlfri automatisk
moderation.

FØRSTE LEVERANCE: EN DATERET RAPPORT OM, HVAD DER ER POPULÆRT NU.

---

1. Arbejdsordre og faste grænser

Byg et fungerende system, ikke blot en præsentation. Lever et versionsstyret kodeprojekt,
installationsscripts, en lokal demo, en cloudinstallation når adgangen foreligger, testresultater og en kort
driftsvejledning.

· Første opgave: undersøg aktuelle emner og forretningsmuligheder. Gaming, fodbold, badminton,
dokumentarer, pc-hardware og handhelds er interessefelter, ikke et på forhånd låst nichevalg.

· Popularitet og momentum skal styre emnevalget blandt lovlige og omdømmemæssigt acceptable
muligheder. Vurder samtidig konkurrence, produktionspris og konkrete indtægtsmuligheder.

· Alt materiale skal have dokumenterede brugsrettigheder. Ingen mindreårige, seksualisering,
pornografi, privatlivskrænkelser, grafisk vold, had, ydmygelse eller vildledende økonomiske løfter.

· Ejeren godkender hver færdig publiceringsversion. Systemet må ikke ændre disse grænser for at opnå
flere visninger. Ingen automatiske beskeder, kommentarer eller sponsorhenvendelser.

· Indfør DRY_RUN=true, PUBLISH_ENABLED=false og PAID_JOBS_ENABLED=false fra start. Mock-data
skal mærkes som demo og må aldrig fremstå som reelle trends, API-forbindelser eller resultater.

Spørg samlet efter nødvendige konti, når deres brug er konkret. Køb, identitetskontrol, accept af
leverandørvilkår og OAuth-samtykke skal udføres eller udtrykkeligt autoriseres af ejeren. Brug en sikker
secret-funktion eller serverfil til nøgler; bed aldrig om dem i almindelig chat.

Opret en STATUS.txt med: udført, verificeret, mangler, blokeret og præcis næste handling. Notér
antagelser og ændringer. Hvis en platform ikke tillader ønsket automatisering, lever en manuel eksport
og fortsæt resten af byggeriet.

---

2. Den billige arkitektur og økonomi

Standard: én x86-64 VPS i EU, Ubuntu 24.04 LTS, cirka 4 delte vCPU, 8 GB RAM og mindst 80 GB SSD.
Ingen GPU. 4 GB RAM kan afprøves med mindre modeller og ét job ad gangen, men er ikke standard for
hele kæden.

Docker Compose kører to processer fra samme applikationsimage: web og worker. FastAPI med
Jinja2/HTMX giver et enkelt dashboard. SQLite i WAL-tilstand gemmer data på den lokale SSD. Én worker
håndterer jobkø, tidsplan og tung videobehandling; ingen Redis, Kubernetes eller separat
databaseabonnement i første version.

Claude API laver tekst- og billedanalyse. FFmpeg klipper video. faster-whisper laver transskription på
CPU. Kokoro er den første TTS-kandidat for understøttede sprog. Alle tre køres på serveren. Undgå
Ollama og en lokal stor sprogmodel i piloten.

Foreløbig økonomi: server 100-300 kr./måned, ekstra lager/backup 0-75 kr., gratis software 0 kr. Claude
betales efter faktisk brug. Domæne, betalt søgning, musik, stock og ekstra TTS er valgfrie og ikke
inkluderet. Moms, IPv4 og backup kan være ekstra poster.

Indhent en konkret pris med moms og alle tilvalg. Målsætningen er højst 375 kr./måned eksklusive
Claude; dette er et forslag, ikke allerede autoriseret forbrug. Foreslå separat Claude-loft på 150
kr./måned i starten og ingen betalte søgninger uden et særskilt budget.

Gem faktiske omkostninger pr. job og måned. Applikationen kan stoppe nye API-kald, men kan ikke
stoppe VPS-huslejen ved blot at stoppe job. En slukket server og tilbageværende diske/backups kan
stadig koste penge. Nedlukning af abonnement kræver særskilt sletning af de fakturerede ressourcer.

Gem data i /opt/some/data og modeller i /opt/some/models. Begræns rendering til ét job ad gangen. Tilføj
lageralarmer og automatisk oprydning i midlertidige filer.

---

3. Første undersøgelse: populært nu

Dater undersøgelsen på den dag, den udføres. Rapporten må ikke bruge denne PDF som evidens for,
hvad der er populært. Sammenlign de seneste 7 og 30 dage med op til 90 dages baggrund, hvor
datagrundlaget tillader det.

Undersøg ejerens seks interessefelter og mindst to andre sikre nicher. Sammenlign dansk og engelsk
separat. Se efter både efterspørgsel og momentum, eksempelvis nye spil, patches, hardwarelanceringer,
turneringer og konkrete spørgsmål, som seerne søger svar på.

Kilder: officielle YouTube API-data, Google Trends via tilgængelig officiel adgang eller manuel eksport,
Steam Charts, relevante officielle RSS-feeds, udgivelses- og turneringskalendere samt platformenes
offentligt tilgængelige trendværktøjer. TikTok/Instagram/Facebook har ikke en garanteret universel
trend-API. Byg aldrig en afhængighed på en API, der ikke er verificeret.

Start med op til 20 nyere opslag pr. niche fra flere forskellige skabere, tilpasset kvoter og budget. Gem
udvælgelseskriterier. Et lille udvalg er et markedssignal, ikke en repræsentativ måling af hele
internettet. Brug også almindelige og svage opslag til sammenligning; undersøg ikke kun vindere.

Gem for hver observation: source_url, platform, collected_at_utc, published_at, country, language, topic,
metric_name, metric_value, unit, method, confidence og limitations. Ukendte værdier er NULL. Visninger
pr. time kræver gentagne observationer; samlet visninger/alder er kun et groft gennemsnit.

Lever research.json, research.csv og en læsbar rapport med 10 konkrete emne/formatmuligheder,
dokumentation, konkurrence, lovligt materiale, indtægtsmodel og usikkerhed. Anbefal én hovedniche, én
reserve, ét sprog og to platforme. Inkludér 10 første videoidéer.

Kræv mindst to uafhængige signaler for en stærk anbefaling. Hvis kun én platform kan undersøges, skal
rapporten sige det. Ingen opdigtede kilder, søgetal, målgruppeprofiler eller indtægter.

---

4. Emnevalg og søgemotor

Implementér adapters med et fælles interface: discover(), fetch_metadata(), refresh_metrics() og
capabilities(). Hver adapter skal oplyse, hvilke data den faktisk kan levere, og om resultatet er API-data,
manuel import eller demo.

Prioritér officielle API'er og RSS. Brug yt-dlp kun til materialer, hvor download og viderebrug er tilladt.
Respektér vilkår, rettigheder, kvoter og robots-regler, hvor relevante; robots.txt er ikke i sig selv en
ophavsretlig tilladelse. Omgå ikke login, CAPTCHA, betalingsmure eller blokeringer.

Adskil researchkilder fra produktionsmateriale. Et opslag kan inspirere en emneidé uden at videoen må
downloades eller genbruges. Stocklicens, gameplaytilladelse, kommerciel brug, musik og
personrettigheder kontrolleres særskilt.

priority = 0.35 * demand + 0.25 * momentum
                + 0.20 * monetization + 0.10 * opportunity
                + 0.10 * production_feasibility

Delscorer er 0-100 inden for sammenlignelige platform/sprog/format-grupper. Dokumentér
normalisering og de input, der skaber hver score. Popularitet og momentum vejer tilsammen 60 %.
Rettigheds- og sikkerhedskrav er absolutte filtre før scoring. Usikkerhed vises separat og må ikke skjules
i decimaler.

En indtjeningsscore kræver en konkret mekanisme: eksempelvis et tilgængeligt affiliateprogram,
relevant købsintention eller faktisk platformberettigelse. Antag aldrig en bestemt RPM eller købsrate
uden kilde eller egne resultater.

Kør research dagligt kl. 06:00 Europe/Copenhagen og en ugentlig opsamling mandag kl. 08:00. Gem
tider i UTC og håndtér sommertid. Vælg aktuelle emner inden for kanalens målgruppe. Skift ikke niche
automatisk hver dag; større ændringer kræver ejerens stillingtagen.

Data fra internettet er ubetroet input. En webside eller transskription må ikke instruere agenten i at
ændre politik, hente secrets eller starte publicering. Claude returnerer forslag som valideret JSON;
applikationskode afgør tilladte handlinger.

---

5. Konti og adgang, der skal oprettes

Udfør gratis research og byg en demo først. Når konti er nødvendige, vis ejeren denne samlede liste med
direkte links og status. Konti skal ejes af ejeren, ikke af udviklingstjenestens medarbejder.

· Cloudkonto: start med Hetzner Cloud [01]. Sammenlign en tilsvarende x86-server hos Scaleway eller
DigitalOcean, hvis pris eller tilgængelighed er dårlig. Registrér konto, betalingsmiddel og eventuel
identitetskontrol. Aktivér totrinslogin.

· Claude Console [03-05]: opret organisation/projekt til SoMe, aktivér API-betaling og opret en
projektspecifik API-nøgle. Et abonnement til Claude-chat er ikke det samme som API-forbrug.

· YouTube/Google: opret eller vælg kanal og et Google Cloud-projekt. Aktivér YouTube Data API v3 og
YouTube Analytics API. Publicering og egne analyser bruger ejerens OAuth-samtykke.

· Meta: Instagram Professional-konto og/eller Facebook-side samt en udviklerapp. Vælg en understøttet
loginvariant; krav til sidekobling og scopes afhænger af den valgte integration.

· TikTok: udviklerapp og kontotilladelser, hvis platformen vælges. Undersøg først, om en intern uploader
til egen konto passer til gældende regler. Direkte publicering er ikke en garanteret
godkendelsesmulighed [12-13].

· Backup: et separat lager med dokumenteret pris og sikker adgang. Et domæne er valgfrit i den private
SSH-baserede pilot.

Gem offentlige identifikatorer og status i config/accounts.yaml. Gem nøgler, klienthemmeligheder og
refresh tokens uden for Git. Brug kun nødvendige scopes. Skeln mellem "konto oprettet", "forbundet",
"privat upload testet" og "offentlig publicering verificeret".

Bed ejeren om budget, konto-/kanalvalg og de nødvendige loginhandlinger i én kort opsamling. Hvis svar
mangler, fortsæt med research, kode, fixtures og lokale tests. En betalingsautorisation eller et
OAuth-samtykke må ikke antages.

---

6. Find og opret cloudserveren

Åbn Hetzner Cloud [01], opret projektet "some-pilot" og vælg en EU-lokation. Find en shared
x86-64-server med cirka 4 vCPU, 8 GB RAM og 80 GB disk. Brug ikke et bestemt SKU-navn ukritisk;
kontrollér dagens pris og faktisk tilgængelighed.

Vælg Ubuntu 24.04 LTS, tilføj en SSH-public key, og aktivér backup efter den godkendte prisramme. IPv4
er den enkleste pilotopsætning, men kan være et tilvalg. Dokumentér samlet månedlig pris, timepris,
moms, lager, trafik og backup før køb.

Generér en separat SSH-nøgle på den maskine, hvor ejeren eller AI-tjenesten sikkert administrerer
serveren. Den private nøgle må ikke deles i chat eller lægges i repository. Brug en passphrase, når
adgangsmetoden understøtter det.

ssh-keygen -t ed25519 -f ~/.ssh/some_pilot
# Upload kun some_pilot.pub til cloududbyderen.
ssh -i ~/.ssh/some_pilot root@SERVER_IP

Kontrollér SSH-hostfingerprint mod cloudkonsollen. Erstat SERVER_IP med den faktiske adresse. Kør
derefter som root på den nye, tomme server:

apt-get update
apt-get upgrade -y
apt-get install -y ca-certificates curl git ufw \

   unattended-upgrades python3 python3-venv
adduser deploy
usermod -aG sudo deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys

Åbn en ny SSH-session som deploy og verificér sudo. Deaktivér først derefter root-login og
password-login via en sshd_config.d-fil, kør sshd -t og genindlæs SSH. Behold den oprindelige session
åben, indtil den nye adgang virker.

---

7. Firewall og Docker-installation

Pilotens dashboard bindes kun til serverens loopback-adresse. Cloudfirewall og UFW må kun tillade SSH
fra ejerens/administratorens godkendte IP-adresse. Behold konsoladgang som redningsvej. Er
IP-adressen skiftende, dokumentér en sikker procedure for at opdatere reglen.

sudo ufw default deny incoming
sudo ufw default allow outgoing
# Erstat ADMIN_IP med din faktiske offentlige IP.
sudo ufw allow from ADMIN_IP to any port 22 proto tcp
sudo ufw enable
sudo ufw status

Installér Docker Engine og Compose fra Dockers officielle apt-repository [02]. Nedenstående gælder
Ubuntu; kontrollér den officielle vejledning ved ændringer. Ingen blind "curl | sh"-installation.

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \

   -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
ARCH=$(dpkg --print-architecture)
printf "%s\n" \

   "Types: deb" \
   "URIs: https://download.docker.com/linux/ubuntu" \
   "Suites: $VERSION_CODENAME" \
   "Components: stable" \
   "Architectures: $ARCH" \
   "Signed-By: /etc/apt/keyrings/docker.asc" | \
   sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
   docker-buildx-plugin docker-compose-plugin
sudo docker run --rm hello-world
sudo docker compose version

Brug sudo docker. Medlemskab af docker-gruppen svarer i praksis til omfattende systemadgang. Publicér
aldrig Docker-socket eller databaseporte. Docker-portmapping kan omgå forventninger til UFW; brug
både cloudfirewall og eksplicit 127.0.0.1-binding.

---

8. Claude API: konto, nøgle og test

Åbn Claude Console [03]. Tilføj betaling/credits i Billing, kontrollér auto-reload og opsæt de
forbrugsgrænser og alarmer, kontoen tilbyder. Opret en nøgle til dette projekt. API-forbrug er separat fra
chatabonnement [05].

Opret en fil uden for repository: /opt/some/secrets/app.env. Brug chmod 600 og en ejer, som
deployprocessen kan læse. Indsæt nøglen med en sikker editor eller AI-tjenestens secret-manager. Vis
aldrig filen med cat, i logs, screenshots eller Git.

ANTHROPIC_API_KEY=INDSAET_SIKKERT
CLAUDE_MODEL_TEXT=VERIFICERET_MODEL_ID
CLAUDE_MODEL_VISION=VERIFICERET_MODEL_ID
DRY_RUN=true
PUBLISH_ENABLED=false
PAID_JOBS_ENABLED=false
MONTHLY_AI_BUDGET_DKK=150
MAX_JOB_AI_COST_DKK=5
APP_TIMEZONE=Europe/Copenhagen
DATABASE_URL=sqlite:////data/some.db
MODEL_CACHE_DIR=/models
WORKER_CONCURRENCY=1

Vælg den billigste aktuelle model, der klarer opgaven tilfredsstillende. Verificér model-ID og pris gennem
den officielle modeloversigt/API [03-04]. Gem valget og datoen; hardcod ikke et modelnavn fra en
gammel tutorial. Brug Anthropic Python SDK.

import os
from anthropic import Anthropic
client = Anthropic()
# Udfoer kun efter aktivering af API-budget.
reply = client.messages.create(

       model=os.environ["CLAUDE_MODEL_TEXT"],
       max_tokens=32,
       messages=[{"role": "user", "content": "Svar kun: OK"}],
)
print(reply.content[0].text)
print(reply.usage.input_tokens, reply.usage.output_tokens)

Testkoden kræver et miljø, hvor env-filen er indlæst sikkert, eksempelvis Compose-servicen. Reservér et
prisestimat før hvert kald, og afregn faktisk tokenforbrug bagefter. Begræns input, output, billeder og
retries. Maksimalt tre forsøg ved midlertidige fejl. Ukendt forbrugsstatus efter timeout må ikke udløse
ubegrænsede gentagelser.

Claude Messages har ikke automatisk internetadgang. Research-adapterne henter kilder og sender
relevante uddrag til Claude. Et særskilt web-search-tool kan have ekstra pris og kræver egen
budgetbeslutning.

---

9. Værktøjer, modeller og sprog

Byg et image på python:3.11-slim og fastlås den afprøvede imageversion/digest ved levering. Installér
OS-pakker til ffmpeg, libsndfile1, espeak-ng, ca-certificates og fonts-dejavu-core. Kontrollér licenser for
de faktiske komponenter og modeller [06-09].

Python-afhængigheder: fastapi, uvicorn, jinja2, sqlalchemy, alembic, pydantic-settings, anthropic, httpx,
feedparser, faster-whisper, yt-dlp, soundfile og pytest. Tilføj Kokoro og en CPU-udgave af PyTorch efter
kompatibilitetstest. Brug en lockfil med konkrete versioner; ingen flydende latest i produktion.

from faster_whisper import WhisperModel
model = WhisperModel(

       "small", device="cpu", compute_type="int8",
       download_root="/models/whisper",
)
segments, info = model.transcribe(
       "/data/input.wav", word_timestamps=True, vad_filter=True
)
segments = list(segments)

Start med small/int8 og en samtidighed på én. Mål RAM, varighed og fejl på dansk/engelsk. Skift til base
eller optimer inputlængde før større server. Undertekster skal faktatjekkes; transskription kan fejlfortolke
navne og tal.

Kokoro-82M er en kandidat med åbne modelvægte [07], men sprog og konkrete stemmer skal
verificeres. Antag ikke dansk understøttelse. Hvis dansk vinder markedsundersøgelsen, afprøv en
dokumenteret dansk lokal TTS-model med passende licens, brug ejerens indtaling eller prissæt en
ekstern TTS-tjeneste særskilt. Kvaliteten skal godkendes på en 20-sekunders prøve.

Hent modelvægte fra officielle projekt-/modelkilder, pin revision og registrér licens, checksum og
diskforbrug i models.lock. Download kun første gang og genbrug cache. Vælg ikke tilfældige
modelmirrors. Start uden baggrundsmusik; det gør både rettigheder og lydkontrol enklere.

Smoke tests: ffmpeg -version, ffprobe på en prøvefil, 10 sekunders transskription og 20 sekunders speak.
Vis målt tid og RAM. Disse skal virke på CPU uden GPU.

---

10. Kodeprojekt og kommandokontrakt

Implementér følgende struktur. Filnavnene er en leverancekontrakt; de eksisterer ikke alene, fordi de
nævnes i denne PDF.

some-pilot/           # dashboard + auth
   app/               # vedvarende jobkoe og scheduler
       main.py        # nedenstaaende kommandoer
       worker.py      # modeller + migrationer
       cli.py         # research, Claude, platforme
       db/            # script, media, render, checks
       adapters/      # dashboard
       pipeline/      # policy, priser, platformkrav
       templates/     # egne/syntetiske testmaterialer
   config/            # install, backup, restore, deploy
   tests/fixtures/
   scripts/           # ingen hemmeligheder
   Dockerfile
   compose.yaml
   requirements.lock
   .env.example
   README.txt
   STATUS.txt

Implementér en CLI med disse kontrakter. Alle mutationskommandoer skal kunne køres i dry-run og
skrive en maskinlæsbar resultatfil:

python -m app.cli doctor
python -m app.cli research --days 30 --output /data/reports
python -m app.cli produce --topic-id ID --dry-run
python -m app.cli metrics --due
python -m app.cli learn --weekly
python -m app.cli backup --verify
python -m app.cli pause --all

doctor kontrollerer konfiguration, modelsprog, FFmpeg, disk, DB, migrationsstatus, budget og
integrationskapabiliteter. Den må ikke bruge betalte API-kald uden særskilt flag og aktivt budget.
Resultatet viser manglende konfiguration uden at udskrive secrets.

Første demo skal fungere uden nøgler med tydeligt mærkede fixtures. Herefter erstattes én adapter ad
gangen med virkelige forbindelser. Vis aldrig en grøn "forbundet"-status uden en faktisk gennemført,
relevant test.

---

11. Compose og deployment

Nedenstående er en minimal driftskontrakt til den implementerede app. Web og worker skal køre som
uid/gid 10001. Opret data- og modelmapper med matchende ejerskab; giv ikke world-write. Fastlås
images, afhængigheder og releaseversion inden drift.

services:                                            --port  8000
   web:
       build: .
       image: some-pilot:local
       command: uvicorn app.main:app --host 0.0.0.0
       user: "10001:10001"
       env_file: /opt/some/secrets/app.env
       ports: ["127.0.0.1:8000:8000"]
       volumes: ["/opt/some/data:/data"]
       restart: unless-stopped
       mem_limit: 1g
       security_opt: ["no-new-privileges:true"]
       cap_drop: ["ALL"]
       logging:
          options: {max-size: "10m", max-file: "3"}
   worker:
       image: some-pilot:local
       command: python -m app.worker
       user: "10001:10001"
       env_file: /opt/some/secrets/app.env
       volumes:
          - /opt/some/data:/data
          - /opt/some/models:/models
       restart: unless-stopped
       mem_limit: 5g
       cpus: "3.0"
       security_opt: ["no-new-privileges:true"]
       cap_drop: ["ALL"]
       logging:
          options: {max-size: "10m", max-file: "3"}

sudo docker compose build
sudo docker compose run --rm web python -m app.cli migrate
sudo docker compose run --rm web python -m app.cli doctor
sudo docker compose up -d
sudo docker compose ps

Tilføj healthcheck for /healthz og worker-heartbeat. Manglende secrets skal give klar opsætningsstatus,
ikke crash-loop. Opbevar Git-koden i /opt/some/app og kør Compose derfra. En rollback må ikke rulle
databasen tilbage uden en kompatibel migrations-/backupplan.

---

12. Database, job og godkendelser

Brug SQLAlchemy og Alembic. SQLite ligger på lokal disk, aldrig på et netværksfilsystem. Aktivér
foreign_keys, WAL og busy_timeout. Hold transaktioner korte. Web og worker må dele DB, men
renderingen sker uden en åben DB-transaktion.

Tabeller: sources, observations, topics, assets, licenses, scripts, video_versions, reviews, publications,
metric_snapshots, experiments, costs, revenues, jobs, audit_events og settings. Hver video peger på
præcise asset- og scriptversioner samt model/prompt-version.

Jobfelter: id, kind, payload, status, created_at, due_at, attempts, max_attempts, lease_until,
idempotency_key, error_code og result_path. Brug en unik idempotency_key og atomisk claim af job.
Scheduler opretter højst ét job pr. opgavetype og planlagt tidspunkt.

DISCOVERED -> RIGHTS_CHECKED -> SCRIPTED -> RENDERED
-> TECH_CHECKED -> SAFETY_REVIEWED -> AWAITING_OWNER
-> APPROVED -> SCHEDULED -> PUBLISHING -> PUBLISHED

Side-status: BLOCKED, REJECTED, FAILED, PAUSED
Usikkert uploadresultat: RECONCILE_REQUIRED

Kun ejeren kan oprette APPROVED. Godkendelsesobjektet indeholder reviewer, tidspunkt og SHA-256 for
video, thumbnail, tekst, links, platform og målkanal. Ændres en del, bliver godkendelsen ugyldig.
Publiceringskoden kontrollerer hash og politik igen umiddelbart før upload.

Publicering har unik nøgle pr. video-version, platform og konto. Gem fjern-ID, uploadsession og API-svar i
redigeret form. Hvis netværket fejler efter en mulig upload, må systemet ikke bare gentage. Afklar status
eller kræv manuel gennemgang. Præcis én ekstern publicering kan ikke garanteres ved alene at bruge
en lokal DB-nøgle.

Blokering må ikke springes over via en anden CLI eller API-rute. Tilladelser håndhæves centralt i
backend. Test ugyldige statusskift og parallelle godkendelser.

---

13. Fra emne til færdig video

1) Vælg en godkendt emnekandidat. Saml faktakilder og lovligt materiale. Produktionsvideoer skal ALTID som standard bygges på rigtige klip fra internettet med dokumenteret tilladelse. Download til karantæne med størrelses- og tidsgrænser. Valider URL, indholdstype, filsignatur og faktisk medieformat; blokér private netværksadresser og cloud-metadata-endpoints.

Tilladte standardkilder er:
· Stockklip med en konkret licens til kommerciel brug og bearbejdning.
· Public domain eller CC-materiale, når det konkrete værks vilkår tillader formålet og efterleves fuldt ud.
· Gameplay, når udgiverens aktuelle regler tillader videoformatet, redigering, monetisering og den konkrete musikbrug.
· Producentens pressemateriale, når licensen konkret tillader den planlagte brug.

Klip fra tilfældige streamere, seere eller repost-konti er ikke standardmateriale, selv om spiludgiveren tillader gameplayvideoer. Den enkelte klipskabers rettigheder skal også være afklaret. Brug helst egne optagelser, udgiverens officielle gameplayklip eller pressemateriale med eksplicit tilladelse. Gem kilde- og licensbevis for hvert enkelt klip før download og render.

2) Lad Claude lave en original vinkel, manuskript og påstandsoversigt. Hver verificerbar påstand skal
referere til en kilde. Opfind ikke hardwaremålinger, egne erfaringer, sportsresultater, citater eller
sponsorater. En anden kontrolpassage undersøger påstandene; den erstatter ikke kildekontrol.

3) Returnér en Pydantic-valideret klippeplan: scene_id, asset_id, start_ms, end_ms, narration, overlay,
claim_ids og transition. Ingen shellkommandoer fra modellen. Appen kalder FFmpeg med argumentlister,
ikke interpoleret shelltekst.

4) Generér speak eller brug godkendt indtaling. Transskriber den faktiske lyd og lav tidskodede
undertekster. Vurder udtale, navne, tal, pauser og overensstemmelse med manuskript. Brug ikke en
kendt persons stemme uden tilladelse.

5) Render 1080 × 1920, H.264, yuv420p, AAC og 30 fps som udgangspunkt. Brug CRF cirka 22 og et
CPU-venligt preset. Mål lyd til omtrent -16 LUFS og højst -1 dBTP som intern startstandard, ikke som
universelt platformkrav.

6) Brug en læsbar tekstskabelon med høj kontrast og højst to tekstlinjer ad gangen. Gem
platformspecifikke safe areas i config. Lav både undertekstfil og indbrændt version. Længde vælges ud
fra format, platform og monetiseringsregler; startforsøg kan være 30-60 sekunder, men ikke som fast
regel.


PLATFORMFORMAT OG BILLEDKOMPOSITION v1.3
Vertikale gamingvideoer skal som hovedregel bruge dynamisk fuldskærms-gameplay med et dokumenteret fokuspunkt pr. klip. Et lille 16:9-udsnit med stor tom flade må ikke være eneste version. Tekst og undertekster skal ligge i platformens safe areas uden at skjule den vigtigste action.

Lav ved behov to vertikale varianter. ZOOM veksler mellem fuld originalbredde og mindst to tydelige fuldskærms-zooms pr. spil eller emne. Hver fase skal have en eksakt varighed og synkron tidskode, så den anden zoom ikke forsvinder eller forskyder lyden. SAFE viser hele spillets originale bredde på op til 1040 pixels med dæmpet, sløret udfyldning bagved. SAFE er obligatorisk når tekstkort, brugerflade eller vigtig action ellers ville blive beskåret. Begge varianter skal kontrolleres som faktiske billedserier, ikke kun som filterkode.

Lav separate redaktionelle varianter: TikTok med kortere og hurtigere kommentar, Instagram Reels med vertikal action og gem/del-CTA, og YouTube med 16:9, længere kommentar og eget landskabsthumbnail. Gem platform, mobiltilstand, antal zooms og CTA som features før publicering, så resultaterne kan sammenlignes korrekt.

Brug en naturlig og energisk stemme med dokumenteret modellicens og kvalitetsgodkendt udtale. Generisk eller kedelig oplæsning er ikke færdig produktionskvalitet. Kokoro kan køre lokalt på CPU med Apache-2.0-modellicens; hver stemme og hastighed skal evalueres. Ingen stemmeefterligning af en virkelig person uden tilladelse.

7) Kontrollér ffprobe, lyd, sortbilleder, beskæring, tekst uden for billedet, kildereferencer og gentagelser.
Lav automatisk storyboard til gennemgang og kræv, at ejeren ser hele det færdige klip før publicering.

Output pr. version: video.mp4, captions.srt, thumbnail.jpg, post.json, claims.json, rights.json, checks.json
og manifest.json. Originalitet skal være substans: forklaring, analyse eller demonstration; nye
undertekster alene er ikke nok.

---

14. Rettigheder og omdømmekontrol

Der findes ingen generel regel om fri brug af klip under 10 sekunder. Kreditering, beskæring, spejling,
hastighedsændring og AI-speak skaber ikke automatisk rettigheder. Citatret kræver konkret vurdering af
formål og omfang; systemet må ikke automatisk godkende den [14-16].

Registrér rettighedshaver, kilde, licensbevis, kommerciel brug, bearbejdning, platforme, territorier, udløb
og kreditering. Licensens faktiske tekst har forrang for et AI-resumé. CC-NC er ikke standardegnet til
kommerciel brug; andre CC-vilkår skal også efterleves.

Fodbold- og badmintonudsendelser, dokumentarfilm, streamerklip og pressevideoer må ikke behandles som frit materiale. Egne gameplayoptagelser kræver kontrol af udgiverens regler og musik.

Egne motion graphics, illustrationer, farvede baggrunde og PowerPoint-lignende slideshows er KUN en absolut fallback, når der efter en reel søgning ikke findes passende internetklip med dokumenteret licens. De må ikke være standarden for at spare tid. Et statisk slideshow uden animationer må ikke præsenteres som en færdig gameplayvideo. En ranking skal have et rigtigt, rettighedsryddet klip for hvert enkelt objekt; ellers standses produktionen eller ændres listen efter ny rettighedskontrol.

Overgange, titler, thumbnails og grafik skal understøtte det rigtige klipmateriale og dets historie – aldrig erstatte det. Kvalitet og engagement er mål, men visninger, likes og abonnementer kan ikke garanteres.

Kør et særskilt kontroltrin på transskription, sceneudsnit, OCR-tekst, links, thumbnail og slutrender.
Politikresultatet er ALLOW, REVIEW eller BLOCK med konkrete årsager. Ved manglende analyse eller
ukendt alder skal resultatet mindst være REVIEW og publicering blokeret.

Ingen mindreårige må indgå i publiceret indhold, heller ikke i baggrund, interviews, ungdomssport eller
streamerklip. Alder må ikke anses som verificeret ud fra ansigtet alene. Vælg helst materiale uden
mennesker; afvis tilfælde, der ikke kan afklares forsvarligt.

Forbud: pornografi, nøgenhed, seksualisering, grafisk vold, had, udstilling af privatpersoner, private
beskeder, farlige udfordringer, gamblingpromovering og udokumenterede beskyldninger. Reglerne
gælder også virtuelle figurer og spilscener, hvor relevant.

Ingen automatisk scanning giver en "aldrig"-garanti. Ejergennemgang er obligatorisk. Klager eller
rettighedskrav pauser det berørte materiale og dets varianter; vis publiceringslinks og en konkret
fjernelsesprocedure. Gem revisionsspor, men ikke unødvendige personoplysninger.

---

15. Dashboard og sikker adgang

Byg et enkelt dashboard med syv visninger: muligheder, produktionskø, gennemgang, kalender,
resultater, økonomi og indstillinger. Alle data skal være virkelige eller tydeligt markerede demoer. Giv
fejlkoder en forståelig forklaring og et næste skridt.

Gennemgang viser hele videoen, thumbnail, tekst, links, kilde-/rettighedskort, påstande,
kontrolresultater og estimeret omkostning. Knapper: godkend denne version, afvis, anmod om ændring
og stop alle publiceringer. Ingen forhåndsafkrydset godkendelse.

Billigste adgang er gennem en SSH-tunnel. Serveren fortsætter sine job, når ejerens computer er slukket;
tunnelen skal kun være åben, mens dashboardet bruges.

ssh -N -L 8000:127.0.0.1:8000 \
   -i ~/.ssh/some_pilot deploy@SERVER_IP

# Aabn derefter http://127.0.0.1:8000

Implementér alligevel app-login, stærkt password med Argon2-hash, sessionsudløb, ratebegrænsning og
CSRF-beskyttelse. Brug server-side sessions; brug ikke en offentlig bypass til "demo". OAuth-callbacks til
lokal tunnel skal passe præcist til den valgte provider og klienttype.

Hvis mobiladgang eller offentlige OAuth-callbacks er nødvendige, tilføj et domæne og Caddy med HTTPS
efter et konkret prisvalg. Åbn kun 80/443 til proxyen, sæt sikre cookies og præcise redirect-URL'er. Ingen
anonym adgang til videoarkiv eller adminroutes.

Platforme som Meta kan kræve, at den godkendte videofil kan hentes via HTTPS. Brug et tidsbegrænset,
signeret downloadlink til kun det godkendte materiale, eller en understøttet uploadmetode. Hold
preview- og kildemateriale privat. Et lukket dashboard er ikke i sig selv en brugbar offentlig medie-URL.

En nødstopsindstilling kontrolleres både før produktion og umiddelbart før publicering. Stop nye opgaver
og kølagte uploads. Et allerede afsendt API-kald kan kræve afklaring eller fjernelse bagefter.

---

16. YouTube: opsætning og test

1) Opret projekt i Google Cloud Console. Aktivér YouTube Data API v3 til metadata/upload og YouTube
Analytics API til egne resultater. Konfigurér OAuth consent screen med korrekt ejer, nødvendige
kontaktoplysninger og de domæner, som den valgte integration kræver [10-11].

2) Vælg en understøttet OAuth-klienttype og præcis redirect-URL. Brug mindst mulige scopes,
eksempelvis youtube.upload til upload og yt-analytics.readonly til analyse; kontrollér aktuelle scopes i
dokumentationen. Brug ikke en service account som erstatning for kanalens ejer-OAuth.

3) Lad ejeren gennemføre login og samtykke. Gem refresh token og klienthemmelighed sikkert, og
implementér tokenfornyelse. Test og dokumentér, om appens test-/verifikationsstatus medfører
tokenudløb eller brugerbegrænsninger.

4) Test først kanalidentitet og læseadgang. Upload en egen/syntetisk testvideo som eksplicit PRIVATE
med separat testgodkendelse. Sæt altid privacyStatus; stol ikke på en API-default. Upload via en
genoptagelig session og gem sessionens status.

5) Kontrollér i kanalens interface, at filen, konto, synlighed og metadata er korrekte. Bekræft gældende
revisions-/auditkrav i de aktuelle officielle docs og i det konkrete projekt. Ældre og nyere dokumentation
kan afvige; rapportér konflikter og antag ikke offentlig adgang uden test.

6) Implementér publicering af en godkendt version, indsamling af egne analysetal og en manuel
uploadpakke som fallback. Gennemfør eventuel nødvendig verifikation, før systemet erklæres klar til
offentlig drift.

Trend research via Data API bruger egne kvoter. Budgettér søgninger, batch metadataopslag og cache
efter gældende vilkår. Undgå at gensøge samme emne unødigt. Egen Analytics giver ikke adgang til
konkurrenters retention eller salg.

Monetisering vurderes separat: kontoberettigelse, originalitet, gentaget indhold og rettigheder [15].
Systemet må ikke kalde en video "monetiserbar" alene, fordi upload lykkes. Vis i stedet dokumenteret
kontostatus og kendte begrænsninger.

---

17. Meta og TikTok: realistisk integration

Instagram/Facebook: opret Meta-app, vælg relevant produkt og loginvariant, forbind den rigtige
professionelle konto/side, og konfigurer redirect-URL. Følg de aktuelle officielle publishing- og
insights-vejledninger [17-18]. Scopes og krav til sidekobling varierer; undgå en forældet standardliste.

Implementér tokenfornyelse og vis udløb. Hvis integrationen bruger mediecontainere: opret container,
poll til færdigbehandlet, publicér én gang og gem fjern-ID. Log ikke access tokens i URL'er. Test
videoformat, konto, tekst og de konkrete tilgængelige insights.

Facebook og Instagram skal have hver sin kapabilitetsstatus. En fungerende Instagram-integration
beviser ikke, at Facebook-publicering eller alle analysetal virker. Brug Meta Business Suite og officiel
eksport, hvis API-adgang afventer godkendelse.

TikTok: læs både Content Posting API og Content Sharing Guidelines før udvikling [12-13]. Registrér
appen, vælg understøttet flow, anmod om relevante scopes, og lad ejeren autorisere kontoen. Følg
platformens krav til creator-info, samtykkeskærm, tekstredigering og privacyvalg.

Unaudited TikTok-klienter har private-publiceringsbegrænsninger. Undersøg også, om et internt værktøj
kun til egne konti kan opfylde den aktuelle godkendelsespolitik. Lov ikke, at Direct Post-audit vil blive
godkendt. Undgå automatiseret browserlogin eller skjulte uploadmetoder som omgåelse.

Fallback for alle platforme: generér en ZIP med video, cover, undertekster, tekst, hashtags,
reklamemarkering, eventuel AI-mærkning og publiceringsinstruktion. Ejeren uploader og indtaster
publicerings-URL/ID. Efterfølgende måling kan ske via API eller valideret CSV-import.

Tilføj ikke en betalt planlægningstjeneste uden ejerens budgetvalg. Sammenlign dens faktiske
API-funktioner med behovet, før den købes. Officiel adgang kan være gratis inden for kvoter, men
konto-/appgodkendelse og specifikke funktioner er ikke garanteret.

Implementér de to platforme, som markedsrapporten anbefaler. De øvrige får dokumenterede interfaces
og manuel eksport, indtil de er relevante.

---

18. Statistik og læring

Hent resultater efter cirka 24 timer, 72 timer, 7 dage og 28 dage, når API'et understøtter det. Gem
collected_at og metric_definition_version. En ændret definition af "view" skal ikke blandes tavst med
gamle tal.

Mål tilgængelige visninger, seertid, retention, gennemførsel, delinger, gemninger, følgerændringer, klik,
salg og indtægter. Ukendt er NULL. Nogle tal kan kun fås for egne konti, nogle kun manuelt, og nogle
findes ikke for det valgte format.

Gem features før publicering: niche, topic, hook_type, length_seconds, format, language, pacing, voice,
CTA, publish_time, platform, script_version og production_cost. Det gør det muligt at sammenligne uden
bagefter at opfinde forklaringer.

Lav en ugentlig rapport med: hvad vi observerede, mulige forklaringer, usikkerhed, hvad der skal
gentages, og ét konkret næste forsøg. Claude læser de faktiske data og foreslår ændringer; beregninger
udføres i kode, ikke som frie modelgæt.

Sammenlign opslag med samme alder på samme platform og i samme format. Markér betalt promotion
særskilt. Retention, længde og trafikkilde hænger sammen. Vis medianer, spredning og sample size, og
undgå sikker kausalitet fra et lille antal organiske opslag.

Start med omtrent 80 % kendte formater og 20 % nye forsøg. Test fx åbning, fortællestruktur eller
længde, helst én større ændring ad gangen. Et enkelt viralt opslag er et spor, ikke bevis. Øg først
produktion ved gentagne lovende resultater og inden for budget.

Læring betyder først en opdateret prioriteringsmodel og versionsstyrede prompts med sporbar
begrundelse. Ingen automatisk fine-tuning eller ukontrolleret agent, som selv ændrer kode og
sikkerhedspolitik. Nye strategier skal kunne rulles tilbage.

Indtægter spores via faktisk platformrapport eller affiliateafregning, eventuelt UTM/sub-ID hvor tilladt.
Linkklik er ikke et salg. Gem valuta, kursdato, provision, refundering og udbetalingsstatus. Undgå
unødvendige persondata og skjult sporing.

---

19. Drift, backup og hændelser

Hver dag: kontrollér heartbeat, fejlede job, diskforbrug, budget, tokens og næste planlagte kørsel. Vis
alarm ved mere end 80 % diskforbrug og stop nye renderjobs ved 90 %. Slet kun regenererbare
midlertidige filer automatisk.

Backup: brug SQLite Online Backup API eller konsistent backupkommando; kopiér ikke blot en aktiv
databasefil med WAL. Tag krypteret backup af DB, konfiguration, godkendte videoer og
rettighedsbeviser til et separat lager. Modelcache kan gendownloades.

Start med daglig backup og en retention som 7 daglige og 4 ugentlige kopier, tilpasset platformenes
dataregler og det konkrete behov. Gem backupnøglen separat. Server-snapshot er nyttigt, men ikke en
erstatning for en afprøvet restore.

Lav en restoretest til en separat mappe eller testsystem: verificér DB-integritet, filhashes, referencer og
adgang. Hold PUBLISH_ENABLED=false og PAID_JOBS_ENABLED=false i en gendannet kopi, så backup
ikke skaber dobbeltpublicering.

Opdatér sikkerhedspakker automatisk efter en kontrolleret politik. Planlæg genstart uden aktive uploads.
Test dependency-opdateringer i et testimage, tag backup før migration og behold tidligere releaseimage.
Undgå daglige automatiske opgraderinger af modelvægte og hele Python-stacken.

HTTP 429/5xx: begrænset retry med backoff og jitter. HTTP 401/403: stop relevant integration, forny eller
anmod om samtykke; forsøg ikke alternative konti. Timeout efter upload: RECONCILE_REQUIRED.
Manglende licens eller moderation: BLOCKED/REVIEW. RAM-fejl: mindre model eller input, ikke
automatisk større abonnement.

Ved klage: pause materialet og varianter, fremfind rettighedsbevis, vis alle publiceringslinks og
gennemfør nødvendig fjernelse gennem den autoriserede konto. Ved kompromitteret nøgle: stop jobs,
tilbagekald nøglen, opret ny, gennemgå logs og dokumentér hændelsen.

Privatliv: opbevar kun nødvendige oplysninger, fastsæt slettefrister og følg API'ernes krav til
opdatering/sletning. En EU-server gør ikke i sig selv alle underleverandører EU-baserede; gennemgå
databehandlerforhold før persondata sendes til modeller.

---

20. Testkrav og leverancebevis

Test de egenskaber, som har reel betydning for udgift, rettigheder, publicering og datakvalitet. Brug
egne eller syntetiske fixtures; hent ikke problematisk indhold blot for at teste et filter.

· En ukendt/udløbet licens blokerer. En kort varighed på 5 eller 10 sekunder må ikke ophæve
blokeringen. Manglende aldersafklaring og manglende sikkerhedskontrol kan ikke nå APPROVED
automatisk.

· En ændret video, thumbnail, tekst, konto eller URL ophæver godkendelsen. En gammel godkendelse
kan ikke genbruges via CLI eller API. PUBLISH_ENABLED=false stopper alle publiceringsveje.

· Budgetreservation forhindrer parallel overskridelse af appens API-loft. Retries har et loft. Timed-out
kald registreres som mulig omkostning. Stopknappen blokerer nye job.

· Upload-timeout efter mulig succes giver afklaring frem for blind gentagelse. Genstart af worker giver
ikke dublerede schedulerjobs eller publiceringer.

· Ingen secrets i logs, fejlrapporter, testfixtures eller repository. Webindhold kan ikke ændre
instruktioner. Downloadere afviser private IP-adresser, redirects til interne mål og for store filer.

· Render og undertekster virker på den valgte CPU-server. Ejeren kan afspille slutvideoen. Dashboard
kræver login. Servergenstart bevarer data og jobstatus.

· API-fejl og ikke-understøttede metrics vises som begrænsninger. Demoresultater blandes ikke med
produktion. Gendannelse fra backup er faktisk afprøvet.

End-to-end: kør en egen/syntetisk video gennem pipeline, ejergodkendelse, privat testupload og
registrering af fjern-ID. Hent virkelige metrics, hvis tilgængelige; ellers verificér importen og dokumentér
ventetid/begrænsning. Offentlig test kræver godkendelse af det konkrete opslag.

Aflever testprotokol med dato, releasehash, miljø, kommando, forventning, resultat og logreference.
"Testet" betyder udført; manglende kontoadgang skal stå som ikke verificeret.

---

21. Milepæle og økonomisk evaluering

M0 - Research: dateret trendrapport, kilder, datamangler, niche/sprog/platform-anbefaling og ti
videoidéer. Gør dette før serverkøb, så infrastrukturen kan tilpasses den reelle opgave.

M1 - Fundament: repository, lokal demo, budgetkonfiguration, rettighedsregister og database. Lever en
konkret serverordre med samlet pris, og lad ejeren oprette konti og sikre nøgler.

M2 - Produktion: én gennemarbejdet video, transskription, speak, kildekort og privat gennemgang.
Afprøv CPU-tid og kvalitet på den valgte VPS. Benchmark målt pris og tid pr. video.

M3 - Drift: dashboard, planlægning, første platformadapter, backup og alarmer. Integrér platform
nummer to. Hvis en audit forsinker publicering, brug manuel upload og fortsæt statistikarbejdet.

M4 - Læring: mål de første opslag, lever ugentlig rapport og gennemfør et afgrænset forbedringsforsøg.
Planlæg 20-30 originale videoer over 60 dage; platformsversioner tæller ikke som selvstændige originale
videoer.

Efter 30 dage: vurder datakvalitet, relevant publikumsinteresse, seertid, følgerudvikling, klik, tidsforbrug
og driftsudgift. Justér formatet, hvis det er begrundet. Manglende indtægt tidligt er ikke automatisk
succes eller fiasko; se på den konkrete monetiseringsvej.

Efter 60 dage: beregn faktisk indtægt minus API, server, licenser, tjenester og øvrige direkte udgifter. Vis
også resultat med ejerens tidsforbrug og udviklingsomkostning. Antag ikke, at 60 dage eller 30 videoer
beviser fremtidig rentabilitet.

Anbefal fortsættelse, ændring eller stop med begrundelse. Nye abonnementer, mere volumen eller
større server kræver en konkret prisbeslutning. Ved stop eksporteres kode, data og rettighedsbeviser,
nøgler tilbagekaldes, og fakturerede ressourcer slettes efter ejerens godkendelse.

Inden kommerciel lancering: afklar reklamemarkering, affiliatevilkår, skat/moms, platformenes aktuelle
monetiseringskrav og eventuelle rettighedsfortolkninger med relevante fagpersoner. Systemets tekniske
kontrol er ikke en juridisk forhåndsgodkendelse.

---

22. Startinstruktion til den næste AI

KOPIÉR DENNE INSTRUKTION SAMMEN MED PDF'EN

Du er ansvarlig for at implementere systemet i den vedhæftede PDF. Læs hele dokumentet, og brug det
som produktkrav og driftskontrakt. Start med handlinger, som kan udføres uden betaling eller
kontoadgang.

Først: registrér dine tilgængelige værktøjer til web, terminal, filer og deployment. Sig præcist, hvis en
kapabilitet mangler. Foretag derefter den daterede markedsundersøgelse og lever dokumenteret
anbefaling af niche, sprog og to platforme. Påstå ikke at have undersøgt data, du ikke har adgang til.

Opret derefter projektfiler, konfiguration, database, demo og tests. Brug én billig x86-cloudserver,
Python/FastAPI, SQLite, Docker Compose, FFmpeg, faster-whisper, passende lokal TTS og Claude API.
Ingen ekstra abonnementer som standard.

Brug standardvalg uden at spørge om små implementeringsdetaljer. Når en konto eller nøgle er
nødvendig, giv en samlet liste med direkte links, nødvendige rettigheder og sikker indsættelsesmetode.
Vis en konkret samlet pris før køb. Fortsæt samtidig med alle uafhængige opgaver.

Implementér en komplet vertikal funktion først: emne  originalt manuskript  lovligt materiale  render
 kontroller  ejergodkendelse  privat testupload  måling. Udbyg derefter research, flere platforme
og ugentlig læring. Brug manuel eksport, hvor API-adgang er blokeret.

Hold publicering og betalte job deaktiveret indtil de relevante konti, budgetter og konkrete handlinger er
godkendt. Gem aldrig secrets i Git eller chat. Der findes ingen 10-sekundersregel. Ukendte rettigheder,
mindreårige og forbudt indhold må ikke publiceres.

Aflever en fungerende installation eller et præcist dokumenteret lokalt resultat med konkrete
blokeringer. Medtag repository, installationsscripts, konfigurationseksempel, driftsvejledning,
testprotokol og STATUS.txt. Skeln skarpt mellem implementeret, testet, deployet og verificeret i
produktion.

Din første tilbagemelding skal indeholde: hvad du kan udføre i dit miljø, hvad du går i gang med nu, og
hvilke oplysninger der eventuelt bliver nødvendige senere. Stop ikke ved en generel plan.

---

23. Kilder og opslagsværk

Officielle referencepunkter. Henvisninger i teksten er angivet som [nummer]. Centrale leverandør-, API-
og modeloplysninger er undersøgt ved udarbejdelsen; den udførende AI skal genkontrollere aktuelle
versioner, priser, adgang og regler før brug. Links er klikbare i PDF'en.

[01] Cloudserver og aktuelle priser
https://www.hetzner.com/cloud/

[02] Docker Engine på Ubuntu
https://docs.docker.com/engine/install/ubuntu/

[03] Claude API - oversigt og adgang
https://platform.claude.com/docs/en/api/overview

[04] Claude API - priser
https://platform.claude.com/docs/en/about-claude/pricing

[05] Claude API - betaling
https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage

[06] faster-whisper - officiel kode og CPU-brug
https://github.com/SYSTRAN/faster-whisper

[07] Kokoro-82M - modelkort og licens
https://huggingface.co/hexgrad/Kokoro-82M

[08] FFmpeg - dokumentation
https://ffmpeg.org/documentation.html

[09] yt-dlp - officiel kode
https://github.com/yt-dlp/yt-dlp

[10] YouTube Data API - upload
https://developers.google.com/youtube/data/reference/rest/v3/videos/insert

---

24. Kilder og opslagsværk - fortsat

Officielle referencepunkter. Henvisninger i teksten er angivet som [nummer]. Centrale leverandør-, API-
og modeloplysninger er undersøgt ved udarbejdelsen; den udførende AI skal genkontrollere aktuelle
versioner, priser, adgang og regler før brug. Links er klikbare i PDF'en.

[11] YouTube Analytics - adgang
https://developers.google.com/youtube/analytics/guides/authorization

[12] TikTok - Content Posting API
https://developers.tiktok.com/doc/content-posting-api-get-started

[13] TikTok - Content Sharing Guidelines
https://developers.tiktok.com/doc/content-sharing-guidelines

[14] YouTube - ophavsretsmyter
https://support.google.com/youtube/answer/2797449

[15] YouTube - monetiseringsregler
https://support.google.com/youtube/answer/1311392

[16] Kulturministeriet - ophavsret og film
https://kum.dk/kulturomraader/ophavsret/film

[17] Meta - Instagram Platform
https://developers.facebook.com/docs/instagram-platform/

[18] Meta - Facebook Pages API
https://developers.facebook.com/docs/pages-api/

[19] Steam - aktuelle charts
https://store.steampowered.com/charts/

[20] Google Trends
https://trends.google.com/trends/
