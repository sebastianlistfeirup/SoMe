# SoMe-maskinen — komplet håndoff til Codex

**Dato for håndoff:** 2026-11-09  
**Formål med dette dokument:** Codex skal kunne fortsætte projektet uden adgang til den tidligere samtale eller dens sessionslogs.  
**Repository:** https://github.com/sebastianlistfeirup/SoMe  
**Kodebaseline ved håndoff:** `9477675224917e3f415e05a69b8dbd1ffb6ae10d` (`9477675`, “Add verified zoom and safe mobile video variants”). Dette håndoff-dokument tilføjes efter baseline.

---

## Overstyring 2026-11-10 — voiceover og backendstatus

Den aktuelle produktionsretning er voiceover uden avatar. HeyGen, avatar-MP4, PIP, `--avatar-dir` og `avatar-request` er ikke længere en del af den aktive produktionsvej. Kokoro er lokal standardprovider; ElevenLabs er valgfri og kræver paid jobs, API-nøgle, voice-ID, stemmerettigheder og dateret pris før netværk.

- `app/pipeline/voice.py` håndterer lydprovider, teksthash, WAV-/lydvalidering, varighed, sample rate og filhash.
- Ranking og almindelig produktion skriver begge `voice_assets.json`, og filen indgår i manifestet som den tiende hash-verificerede fil.
- Den tidligere åbne `claim_control`-blokering er rettet med `ranking_claims.py`. Approval kræver nu både `claim_control` og `voice` samt øvrige checks.
- `handheld-voiceover-v1` er den aktuelle lokale reference: video_id=33, 102,1 sekunder, Kokoro, speakmatch 99,51 %, ti verificerede manifesthashes og status AWAITING_OWNER.
- Gaming og lokal AI testposts er bygget i alle fem formater med nye Kokoro-timingdata og uden avatar.
- 62 tests består. Backup/restore og live `/healthz` er også verificeret.
- Eksterne konti, OAuth, privat upload, publicering, reelle metrics og paid API-kald er stadig ikke verificeret eller aktiveret.

Læs den aktuelle `STATUS.txt`, `TEST_PROTOCOL.md` og `OWNER_ACTIONS.md` før nye opgaver. Resten af dette dokument er den historiske baseline og må ikke tolkes som et krav om avatar eller som en åben `claim_control`-fejl.

---

## 1. Start her — instruktioner til Codex

Læs hele dette dokument før du ændrer noget. Det er den aktuelle arbejdskontrakt og status, ikke et ønske om at genopbygge projektet fra bunden.

- Arbejd i `C:\Users\compu\Documents\SoMe` på den eksisterende Windows-maskine, hvis du har adgang til den. Brug Git Bash og Unix-syntaks i Bash.
- Tjek altid `git status`, aktuel branch og eventuelle nye `AGENTS.md`, før du arbejder. Der lå ingen projekt-`AGENTS.md` med særlige instruktioner ved baseline.
- Hvis du arbejder et andet sted end den originale maskine, kan du **ikke** regne med at videoer, kildeklip, stemme-WAV'er, databasen eller modelcache findes i en almindelig Git-klone. Læs afsnit 7, før du lover at kunne rendere.
- Genopbyg ikke eksisterende funktionalitet uden en konkret årsag. Ret først de åbne kontrolpunkter, og behold eksisterende struktur og navngivning.
- Brug `worker`-containeren til tests og rendering. Brug ikke `web` som erstatning for den verificerede worker-kommando.
- Kør kun én videoproduktion ad gangen. SQLite har tidligere givet `database is locked`, når en afbrudt render fortsatte i baggrunden.
- Publicér **aldrig** på sociale medier uden en ny, konkret ejergodkendelse. Et GitHub-push er ikke social publicering.
- Køb ingen servere, hardware, API-forbrug eller abonnementer uden ejerens udtrykkelige godkendelse af den konkrete pris.
- Bed aldrig om passwords, API-nøgler, client secrets eller refresh tokens i chatten. De skal ind i en sikker secret-fil/secret-manager direkte af ejeren.
- Giv aldrig garanti for 100 % fejlfrihed, views, likes, abonnementer, monetisering eller indtjening.
- Brugeren vil have **én konkret opgave af gangen** at forholde sig til. Gør resten selv, men bed kun om én handling ad gangen.

### Aktuel sikkerhedstilstand

Behold disse værdier, indtil ejeren udtrykkeligt godkender ændringen:

```text
DRY_RUN=true
PUBLISH_ENABLED=false
PAID_JOBS_ENABLED=false
WORKER_CONCURRENCY=1
```

Budgetterne i `.env.example` er 150 DKK/måned for AI og 5 DKK/job. De er ikke bevis for at betaling eller API-adgang er konfigureret.

---

## 2. Hvad projektet skal blive

SoMe-maskinen er en delvis implementeret videofabrik og et beslutningssystem til en kanal om:

1. Gaming, især handheld gaming.
2. Pc-hardware.
3. Lokal AI.

Den langsigtede vision er en **lærende hjerne**, der undersøger aktuelle emner, producerer originale videoer med lovligt materiale, måler reelle resultater og bruger statistikken til at forbedre senere emner, hooks, formater og udgivelser.

Kvalitetsmålet er stærke klip, dynamisk redigering, gode thumbnails, titler og levende narration. Det skal ikke blive en maskine til generiske PowerPoint-videoer.

### Ufravigelige indholdsregler

- Produktionsvideoer skal som standard bygges på **rigtige klip fra internettet med dokumenteret tilladelse** til kommerciel brug og bearbejdning.
- Tilladte kilder er konkret licenseret stockmateriale, public domain/CC under de faktiske vilkår, gameplay under udgiverens regler og producentens pressemateriale med passende tilladelse.
- Tilfældige streamer-, seer- og repost-klip er ikke standardkilder. Klipskabers rettigheder skal også være afklaret.
- PowerPoint-lignende slideshows og syntetiske baggrunde er kun absolut fallback, aldrig standarden for en gamingvideo.
- Ingen “10-sekundersregel” eller antagelse om fair use. Kontrollér hver konkret rettighed og musikbrug.
- FPS, batteritid, kompatibilitet og hardwareperformance må ikke opdigtes eller overføres fra andres test som egne målinger.
- Andres trendvideoer bruges kun som markedssignaler, **ikke** som footage i vores videoer.
- Hver endelig video kræver ejerens fulde visning og godkendelse før publicering.

Den redaktionelle hovedregel findes også i `docs/SoMe-mini-bibel-v1.3.md` og `docs/SoMe-mini-bibel-v1.3.pdf`.

---

## 3. Faktisk status lige nu

### Færdigt og verificeret

- FastAPI-dashboard, SQLite/Alembic, jobs og worker.
- Research med observationer, scoring, fixture/demo og YouTube-adapter, hvor nøgle konfigureres.
- Rettigheds- og sikkerhedskontroller, godkendelsesflow og nødstop.
- Rankingpipeline med rigtige klip, narration, overgange, captions, thumbnails og storyboards.
- TikTok-, Reels-, YouTube- og to nye vertikale mobilvarianter.
- Manuel ZIP-eksport samt uverificerede YouTube- og Instagram-udgivere.
- Metricsimport, YouTube Analytics-kode, ugentlig dæmpet læring og versionsstyrede promptdokumenter.
- Budgetreservationer, backup/restore, signerede medielinks og basis login/CSRF.
- 45 automatiske tests bestod i den testede Docker-build.
- Ti kildefilers SHA-256 matcher rettighedsdokumentationen.
- 18 manifestfiler i de to nye mobilversioner er hash-verificeret. De tre ældre versioner har 27 verificerede manifestfiler.
- Mini-bibel v1.3 er bygget som 29-siders PDF og visuelt kontrolleret på forsiden og side 17–18.

### Ikke verificeret eller ikke gjort

- Ingen social publicering, privat upload, OAuth eller reelle metrics er gennemført.
- Ingen betalte API-kald eller hardware/serverkøb er foretaget.
- Ingen VPS-deploy eller produktionsdeploy er verificeret.
- Ingen virkelig læring fra egne publicerede opslag har fundet sted endnu.
- Ingen uafhængige tokens/sekund-benchmarks for lokal AI-hardware er udført.
- Ingen kanal eller konto er oprettet/koblet til. Kanalnavn er ikke valgt eller checket for ledighed.
- Dansk TTS er ikke kvalitetsgodkendt. Den aktuelle engelske stemme er Kokoro `af_bella`.
- Krypteret offsite backup, `BACKUP_KEY`, affiliate, skat/moms og kontomonetisering mangler.
- Ejerens fulde visning og kreative godkendelse af de to nye mobilvarianter afventer.

**Vigtigt:** `AWAITING_OWNER` betyder ikke publiceringsklar. Det betyder kun at de automatiske trin er gennemført, og at ejeren stadig skal vurdere den konkrete video.

---

## 4. De fem eksisterende videoversioner

Alle står i `AWAITING_OWNER` og ligger lokalt under `some-pilot/data/versions/`.

| Version | Video ID | Varighed | Format og kontrol |
|---|---:|---:|---|
| `handheld-tiktok-v2` | 15 | 49,2 s | 1080×1920, kortere/hurtigere narration; speakmatch 96,67 %; −16,8 LUFS; −1,0 dBTP |
| `handheld-reels-v2` | 14 | 102,2 s | 1080×1920, ældre fuldskærms-action; speakmatch 99,34 %; −16,5 LUFS; −1,0 dBTP |
| `handheld-youtube-v4` | 18 | 171,4 s | 1920×1080, længere narration og landskabsthumbnail; speakmatch 99,55 %; −16,4 LUFS; −0,9 dBTP |
| `handheld-safe-v10` | 31 | 102,1 s | Komplet spilbredde og tekst over dæmpet baggrund; speakmatch 99,51 %; −16,4 LUFS; −1,0 dBTP |
| `handheld-zoom-v11` | 32 | 102,1 s | To præcise fuldskærms-zooms pr. spil; speakmatch 99,51 %; −16,5 LUFS; −0,9 dBTP |

### De to nye mobilvarianter — vigtigste leverance

**Zoom:**

```text
some-pilot/data/versions/handheld-zoom-v11/video.mp4
```

- Vekslende bred visning og to fuldskærms-zooms pr. spil.
- Alle ti spil er kontrolleret på fire tidspunkter: 9 %, 32 %, 56 % og 83 % af hver scenes varighed.
- Celeste bruger reel platform-action fra 32 sekunder.
- Slay the Spire og Balatro er flyttet væk fra review-citater og store tekstkort.
- Slay the Spire 2 bruger et kamp-/kort-/belønningsforløb fra 18 sekunder.
- Hades II bruger 77 sekunder i zoom, så begge zoomfaser viser gameplay frem for titelkort.

**Safe:**

```text
some-pilot/data/versions/handheld-safe-v10/video.mp4
```

- Hele gameplaybredden vises på op til 1040 px med dæmpet, sløret udfyldning.
- Tekstkort og vigtig brugerflade beskæres ikke.
- Kontrolleret som storyboard og billedserie for hvert sekund.

**Forskel med vilje:** Safe-v10 bruger Hades II fra 73 sekunder, mens zoom-v11 bruger 77 sekunder. Det er en formatkorrigering, ikke en fejl eller hash-mismatch. Brug hver versions egen `clip_plan.json` som bevis.

### Manifestfiler pr. version

De ni filer, hvis SHA-256 står i `manifest.json`:

```text
video.mp4
captions.srt
thumbnail.jpg
post.json
claims.json
rights.json
checks.json
clip_plan.json
storyboard.jpg
```

Der findes også bl.a. `editorial.json`, `narration.wav`, `transcription.srt` og `work/` i mapperne. De er ikke alle med i manifestet.

### Advarsel om gamle databaseposter

Databasen indeholder mange forkastede prøveversioner fra iterationsprocessen. Fysiske prøvemapper er ryddet, men gamle databaseposter kan stadig stå som `AWAITING_OWNER`. Brug kun de fem mapper ovenfor som leverancer. Bulk-godkend eller slet ikke gamle poster uden backup og konkret gennemgang.

---

## 5. Præcis næste opgave og prioriteret rækkefølge

### Trin 0 — ejerens kreative valg

Ejerens næste eneste opgave er:

> Se `some-pilot/data/versions/handheld-zoom-v11/video.mp4`, se derefter `some-pilot/data/versions/handheld-safe-v10/video.mp4`, og sig om du foretrækker zoom eller safe.

Codex må ikke erstatte ejerens visning eller markere videoen som set af ejeren. Hvis der gives konkret feedback, ret den først og lav en ny versionsmappe.

### Trin 1 — ret godkendelsesblokering før faktisk approval

Ved håndoff er der et konkret kontrolpunkt i `some-pilot/app/pipeline/approvals.py:100`:

```python
for name in ("rights", "technical", "layout", "safety", "quality", "claim_control"):
```

`produce_ranking` i `some-pilot/app/pipeline/production_ranking.py` skriver dog ikke et `claim_control`-objekt i `checks.json`. Det er bekræftet at `handheld-zoom-v11/checks.json` ikke indeholder feltet. En approval vil derfor blive stoppet med:

```text
check_not_allowed:claim_control
```

**Dette er ikke rettet.** Før faktisk approval skal Codex:

1. Implementere en reel redaktionel claimkontrol for rankingproduktionen, ikke bare et tomt `ALLOW`.
2. Dokumentere kontrollen af navne, tal, Hades II Deck-status og de subjektive rangeringer.
3. Tilføje tests for både rankingoutput og hele approvalflowet.
4. Producere nye versioner/checks gennem den normale pipeline og hash-verificere dem. Ret ikke bare gamle godkendelser eller manifester manuelt.
5. Bekræfte at `approve()` accepterer først efter gyldige checks og `owner_watched_full_video=True`, og at enhver ændring af video/thumbnail/tekst/links/konto ugyldiggør hashen.

Den almindelige `production.py` har allerede et `claim_control`-mønster, men rankingens redaktionelle model er `human-reviewed-template`; antag ikke at generisk Claude-kontrol er kørt.

### Trin 2 — næste indholdsproduktion

Når variant og approvalflow er afklaret, er den naturlige første kandidat `handheld-013`:

> “Steam Deck's #1 this week: why Slay the Spire 2 is everywhere.”

Før produktion:

- Hent en ny dato og ny Valve-rank. Den gamle #1 er kun et snapshot fra 2.–8. november 2026.
- Tjek udgiverpolitik og konkrete klip igen.
- Skriv originalt manuskript og claims med faktakilder.
- Lav en ny plan/stemmemappe, hvis narrationen ændres.
- Lav platformtilpassede varianter efter ejerens foretrukne mobilformat.
- Gennemgå den faktiske video visuelt og kontrollér manifestet.

### Trin 3 — kanalbrand

Anbefalingen er **Pixel & Parameters**, men ejeren har ikke valgt. Tjek navneledighed, handles, domæner og varemærker før konti eller grafisk identitet oprettes. De ti kandidater står i afsnit 12.

### Trin 4 — eksterne integrationer, én ad gangen

Følg `OWNER_ACTIONS.md`:

1. Cloudserver og dokumenteret totalpris.
2. Claude Console og separat API-budget.
3. YouTube/Google research, OAuth og eksplicit privat uploadtest.
4. Instagram/Meta.
5. Krypteret offsite backup.
6. Affiliate, skat/moms og kommerciel lancering.

Hvert punkt kræver ejerens handling eller godkendelse. Spring ikke over privat upload eller metricsverificering.

---

## 6. Arkitektur og vigtige filer

### Applikation og infrastruktur

| Sti | Funktion |
|---|---|
| `some-pilot/app/main.py` | FastAPI, login, dashboard, review, beskyttede medier og publish endpoints |
| `some-pilot/app/worker.py` | Workerloop, jobplanlægning, metrics, ugentlig læring, backup og maintenance |
| `some-pilot/app/cli.py` | Kommandolinje for research, produktion, metrics, læring, backup, approval, eksport og publicering |
| `some-pilot/app/config.py` | Settings, sikre defaults, budget og integrationsfelter |
| `some-pilot/app/db/models.py` | SQLAlchemy-modeller for topics, assets, licenser, scripts, videoer, publications, metrics, jobs, reviews m.m. |
| `some-pilot/compose.yaml` | Web/worker, CPU/RAM-grænser, volumes og sikkerhedsindstillinger |
| `some-pilot/Dockerfile` | Python 3.11, FFmpeg, espeak-ng og låste pip-afhængigheder |
| `some-pilot/requirements.lock` | Låste afhængigheder; antag ikke at nye biblioteker findes |
| `some-pilot/config/platforms.json` | Interne format- og safe-area-startværdier, ikke universelle platformkrav |
| `some-pilot/config/accounts.yaml` | Viser at konti/cloud/backup ikke er oprettet eller forbundet |

### Video og rettigheder

| Sti | Funktion |
|---|---|
| `some-pilot/app/pipeline/ranking.py` | Rankingplan, validering, scene/render, overgange, captions, SRT og tekniske checks |
| `some-pilot/app/pipeline/mobile.py` | `zoom` og `safe`; præcis fasevarighed og frame-tidskoder |
| `some-pilot/app/pipeline/production_ranking.py` | DB/assets/licenser, rights/safety/quality, thumbnails, checks og manifester |
| `some-pilot/app/pipeline/ranking_art.py` | Thumbnails og storyboards |
| `some-pilot/app/pipeline/media.py` | FFmpeg/probe, TTS, transskription, render og tekniske kontroller |
| `some-pilot/app/pipeline/policy.py` | Rettigheds- og indholdspolitik |
| `some-pilot/app/pipeline/approvals.py` | Statusflow, nødstop, approvalhash og publiceringsblokering |
| `some-pilot/app/pipeline/platforms.py` | Manuel eksport, YouTube/Instagram og TikTok-blokering indtil aktuel audit |
| `some-pilot/scripts/curate_mobile_clips.py` | Kuraterede klippunkter og Balatro-kildemetadata |
| `some-pilot/scripts/build_platform_plans.py` | TikTok-/YouTube-varianter af hovedplanen |
| `some-pilot/scripts/prepare_kokoro.py` | Sikker modeldownload og lokal Kokoro-stemme |
| `research/top10-legion-go2/rights.json` | Politikker, klipkilder, beviser, mediedata og SHA-256 |

### Research, metrics og læring

| Sti | Funktion |
|---|---|
| `some-pilot/app/pipeline/research.py` | Observationer, import/eksport og prioritets-score |
| `some-pilot/app/adapters/youtube.py` | YouTube-research når API-nøgle findes |
| `some-pilot/app/pipeline/metrics.py` | CSV-import og YouTube Analytics på dag 1, 3, 7 og 28 |
| `some-pilot/app/pipeline/learning.py` | Ugentlige grupper, medianer, dæmpede hook-multiplikatorer og rapporter |
| `some-pilot/app/pipeline/ai.py` | Claude JSON-manuskript, claimreview og brug af læringsmultiplikatorer |
| `research/handheld-content-calendar.json` | 12 oprindelige emner og produktionsregler |
| `research/handheld-trend-ideas-2026-11-08.json` | 10 nye idéer med konkrete markedssignaler |
| `research/local-ai-hardware-2026-11-08.md` | Hardwarekandidater, priser, kapacitet og benchmarkmetode |
| `research/channel-name-candidates.md` | 10 navne og anbefaling |

---

## 7. Lokale filer, Git og overførsel til et andet miljø

`.gitignore` udelukker bl.a.:

```text
some-pilot/data/
some-pilot/models/
research/**/clips/
research/**/voice*/
research/**/previews/
```

Derfor findes følgende normalt **ikke** i GitHub:

- De færdige MP4/WAV/JPEG-filer og SQLite-databasen.
- De ti kildevideoer.
- Kokoro-model og Whisper-cache.
- De godkendte stemme-WAV'er.
- Kontaktark og andre midlertidige previews.

### Hvis Codex bruger samme maskine

Brug de eksisterende mapper. Lav ikke nye downloads uden grund, og slet ikke modeller eller kildefiler.

### Hvis Codex bruger en anden maskine eller kun har en Git-klone

Før render skal ejeren overføre nødvendige lokale assets sikkert uden at lægge dem i Git:

```text
some-pilot/models/
research/top10-legion-go2/clips/
research/top10-legion-go2/voice-kokoro/
research/top10-legion-go2/voice-tiktok/
research/top10-legion-go2/voice-youtube/
```

Kun hvis de eksisterende videoer eller databasen også skal bruges:

```text
some-pilot/data/versions/
some-pilot/data/some.db
```

Lav backup før databaseflytning. Alternativt kan kildeklip og stemmer genskabes, men det er ikke den samme verificerede leverance uden ny kontrol. Store mediefiler skal forblive uden for Git.

---

## 8. Klipplan, stemme og kuratering

### Nuværende klippunkter i `plan.json`

| Spil | Rank | Kilde/start |
|---|---:|---:|
| Hades II | 1 | 77 s |
| Hollow Knight: Silksong | 2 | 52 s |
| Balatro | 3 | 18 s |
| Stardew Valley | 4 | 27 s |
| Slay the Spire 2 | 5 | 18 s |
| Hades | 6 | 78 s |
| Hollow Knight | 7 | 72 s |
| Slay the Spire | 8 | 10 s |
| Celeste | 9 | 32 s |
| Transistor | 10 | 59 s |

Renderrækkefølgen er #10 til #1 med en separat hook baseret på #1, altså 11 segmenter.

### Rettigheder og kvalitet

- Ni klip er officielle Steam-gameplayklip i H.264/1080p.
- Balatro er **Playstacks officielle launch trailer fra YouTube**, `https://www.youtube.com/watch?v=2n9pkiuSZLU`.
- Balatro-kopien er 640×360, 67,570068 sekunder og har SHA-256 `abd7f6d2b010228cc3c3107695642522e81c45d5af41b7ea7d518724e854450c`.
- En HD-download af Balatro kunne ikke verificeres. Omgå ikke begrænsninger, og kald den ikke HD.
- Musik er slået fra, hvor konkret brug ikke er dokumenteret. Publisherpolitikker er beviser, ikke juridiske garantier; kontrollér dem igen før publicering.

### Stemme

- Lokal Kokoro-82M v1.0 ONNX, `af_bella`, hastighed 1.08 i hovedplanen.
- Model: 325.505.369 bytes; SHA-256 `beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a`.
- Voices: 28.214.398 bytes; SHA-256 `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d`.
- Apache-2.0-model og MIT `kokoro-onnx 0.6.1`.
- `plan.json` bruger `voice-kokoro`, TikTok bruger `voice-tiktok`, YouTube bruger `voice-youtube`.

**Vigtig faldgrube:** `prepare_kokoro.py` genbruger en WAV, hvis filnavnet allerede findes, uden at sammenligne narrationsteksten. Hvis manuskriptet ændres, skal du bruge et nyt `voice_dir` eller bevidst generere nye stemmer i en ny mappe. Ellers kan gammel narration ende i ny video.

### Mobilfilter

`some-pilot/app/pipeline/mobile.py`:

- `safe`: fuld kildebredde op til 1040 px over sløret baggrund.
- `zoom`: faseandele 18 % bred, 28 % zoom, 20 % bred, 34 % zoom.
- Zoom bruger `d=1`, så hvert inputframe ikke bliver gentaget forkert.
- Alle fire faser er begrænset med `trim=duration=...` og `setpts=N/(30*TB)`, så anden zoom ikke forsvinder eller forskyder lyden.
- Ændr ikke dette uden både enhedstests og en rigtig billedserie.

---

## 9. Kommandoer — byg, test og render

### Miljø

På Windows Git Bash:

```bash
cd /c/Users/compu/Documents/SoMe/some-pilot
```

Brug `MSYS_NO_PATHCONV=1` ved Docker-kommandoer. Brug workercontaineren og låste dependencies.

### Byg og tests

```bash
MSYS_NO_PATHCONV=1 docker compose build
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps worker pytest -q
```

Seneste resultat: **45 passed**, kun en ekstern Starlette TestClient-deprecationwarning.

`some-pilot/scripts/test.sh` findes, men den verificerede kommando ovenfor bruger `worker`, ikke `web`.

### Kuratér klippunkter og kildeoplysninger

Denne kommando skriver til `plan.json`, `plan-tiktok.json`, `plan-youtube.json` og `rights.json`. Brug kun når en faktisk kurateringsændring er nødvendig:

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps \
  -v "$PWD/../research/top10-legion-go2:/research" \
  worker python -m scripts.curate_mobile_clips --root /research
```

Scriptet skal køres som `python -m scripts.curate_mobile_clips`, ikke som en direkte filsti uden modulsti. Husk at Docker imaget skal genbygges efter scriptændringer, eller mount den aktuelle scriptmappe eksplicit. En ældre build kørte tidligere et ældre klippunkt.

### Render zoom

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps \
  -v "$PWD/../research/top10-legion-go2:/research:ro" \
  worker python -m app.cli ranking \
  --plan /research/plan.json \
  --platform reels \
  --mobile-style zoom \
  --output /data/versions/handheld-zoom-v11
```

### Render safe

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps \
  -v "$PWD/../research/top10-legion-go2:/research:ro" \
  worker python -m app.cli ranking \
  --plan /research/plan.json \
  --platform reels \
  --mobile-style safe \
  --output /data/versions/handheld-safe-v10
```

**Disse to mapper findes allerede.** Brug dem ikke som output igen uden bevidst versionsstyring. `work/` oprettes med `exist_ok=False`; vælg et nyt versionsnavn ved ændringer.

### Regler ved fejl og timeouts

- Kør ikke to renders samtidig. Databasen er SQLite og kan låses.
- Hvis et værktøjstimeout rammer, kan Docker-processen fortsætte. Kontrollér `docker ps`, vent på den konkrete container og kontrollér output før retry.
- Slet ikke en mappe, mens en container skriver til den.
- Omgå ikke diskstoppet ved ≥90 % forbrug.
- Fejlede prøveversioner må ikke leveres som færdige. Gem kun rene versionsmapper.
- `DRY_RUN`, `PUBLISH_ENABLED` og `PAID_JOBS_ENABLED` må ikke ændres som en “fejlretning”.

---

## 10. Verificeringskrav før en version kaldes færdig

En kompileret kodefil eller en `ffprobe` er ikke nok.

### Automatisk

1. Byg den aktuelle Docker-image.
2. Kør alle tests og ret relevante fejl.
3. Kontrollér rettigheder, teknik, layout, safety, quality og den manglende claimkontrol når den er implementeret.
4. Kontrollér codec, opløsning, fps, pixel format, varighed og lydniveau.
5. Kontrollér transskription mod den faktisk afspillede narration.
6. Kontrollér alle ni manifestfiler med SHA-256.
7. Kontrollér JSON og `git diff --check`.

### Visuelt og redaktionelt

- Se storyboard og thumbnail.
- Lav billedserier fra den faktiske video, ikke kun kildetraileren.
- For zoom kontrolleres 9 %, 32 %, 56 % og 83 % af hver scene: bred, zoom 1, bred, zoom 2.
- For safe kontrolleres at hele spilbredden og alle tekstkort bevares.
- Kontrollér Celeste-action, sorte flader, overgange, undertekster og store tekstkort.
- Kontrollér navne, tal og udtale; Whisper-match er ikke bevis for korrekt navn eller faktum.
- Ejeren skal se og lytte til hele videoen før approval/publicering.

### Dokumentation og Git

Efter en reel ændring opdateres relevante dele af:

```text
STATUS.txt
TEST_PROTOCOL.md
OWNER_ACTIONS.md
research/handheld-content-calendar.json
docs/SoMe-mini-bibel-v1.3.md og PDF, hvis reglerne er ændret
```

Slet kun egne midlertidige kontaktark, fejlede prøver og logs. Lad brugerens øvrige filer være. Kontrollér `git status` efter tests/build. Commit/push kun når opgaven og brugerens tilladelse dækker det; social publicering kræver altid separat ejergodkendelse.

### Mini-bibel build

`docs/build_mini_bible.py` bruger `reportlab==5.1.0` fra `docs/requirements.txt` og Windows-fontene:

```text
C:/Windows/Fonts/arial.ttf
C:/Windows/Fonts/arialbd.ttf
```

På Linux skal fontstierne gøres portable eller tilpasses eksplicit. Byg og visuelt kontrollér PDF'en igen efter ændringer; nøjes ikke med Markdown.

---

## 11. Den “lærende hjerne” — hvad der faktisk er implementeret

Der skal ikke markedsføres en selvforbedrende AI, som endnu ikke har lært af egne resultater.

### Implementeret

`metrics.py` indsamler/importerer bl.a.:

- Views.
- estimatedMinutesWatched.
- averageViewDuration og averageViewPercentage.
- subscribersGained/Lost.
- likes, comments og shares.

Målpunkter er dag 1, 3, 7 og 28. YouTube Analytics kræver publiceret `remote_id`, publiceringsdato og OAuth.

`learning.py`:

- Grupperer ca. 7-dages views efter platform, format, hook og længdebucket.
- Bruger medianer og sample size.
- Dæmper opdateringen med `n/(n+5)`.
- Begrænser hook-multiplikatorer til 0,75–1,25.
- Allokerer 80 % kendte formater og 20 % eksperimenter.
- Skriver versionsstyrede læringsrapporter og prompt-JSON med mulighed for eksplicit rollback.
- Bruge eksterne observationer som inspirationssignaler med begrænsninger, ikke kausalitet.

`ai.py` bruger reelle multiplikatorer som ekstra guidance i generisk Claude-manuskript og ændrer promptversionen. Den ændrer ikke automatisk kode eller politik.

### Begrænsningerne

- Der findes endnu ingen publicerede opslag eller reelle metrics, så den rigtige læringsmodel har ikke lært noget endnu.
- Den kuraterede rankingpipeline bruger `human-reviewed-template` og bliver ikke automatisk omskrevet af læringsmodellen.
- En høj visningssum beviser ikke at hooket eller formatet forårsagede resultatet.
- Start med små sammenlignelige grupper og test én åbningsvariation ad gangen.
- Øg ikke produktionen på baggrund af ét viralt opslag eller en lille, skæv stikprøve.

### Næste korrekte læringscyklus

1. Publicér først efter ejergodkendelse og privat integrationstest.
2. Indsaml metrics på dag 1, 3, 7 og 28.
3. Sammenlign inden for samme platform/format/hook/længde.
4. Kør ugentlig dæmpet læring og gem version.
5. Test én konkret ændring i næste produktion.
6. Behold rettigheder, sikkerhed og redaktionel kontrol uændret.

---

## 12. Research, idéer, hardware og navne

### De 10 nye gamingidéer

Alle kræver opdateret research/manuskript; de er ikke producerede videoer:

1. `handheld-013` — Steam Deck's #1 this week: why Slay the Spire 2 is everywhere.
2. `handheld-014` — Slay the Spire 2 vs Slay the Spire: the Deck chart rematch.
3. `handheld-015` — Three games in this week's Deck top 10 for your next short session.
4. `handheld-016` — Hades II vs Hades: which one are Deck players choosing this week?
5. `handheld-017` — Silksong vs Hollow Knight: sequel or original first?
6. `handheld-018` — Five non-AAA games in this week's Deck top 30.
7. `handheld-019` — Cozy or chaos: Stardew Valley vs Hades II.
8. `handheld-020` — Why Balatro is still a Deck top-10 game.
9. `handheld-021` — We followed the Deck chart: five games to install next.
10. `handheld-022` — The Steam Deck chart tournament: you choose the winner.

Markedssignaler fra 2026-11-08:

- Valve Deck top played 2.–8. november: Slay the Spire 2 #1, Stardew Valley #5, Balatro #10, Hades II #26, Slay the Spire #29, Hades #30, Silksong #44 og Hollow Knight #45.
- Deck Wizard top-50: 34.376 visninger efter 7 dage, `https://www.youtube.com/watch?v=hs6O4dS7zxs`.
- HiTechKing Legion Go 2 AAA-test: 30.148 visninger efter 1 måned, `https://www.youtube.com/watch?v=-rN3yjQwKUc`.

Opdatér snapshots før nye titler. Brug ikke de to YouTube-videoer som footage.

### Lokal AI-hardware

Researchfilen er `research/local-ai-hardware-2026-11-08.md`.

| Kandidat | Dokumenteret udgangspunkt | Begrænsning |
|---|---|---|
| RTX 5090, 32 GB GDDR7 | Fra $1.999 for GPU; god til gaming og 7B–32B-klassen med passende kvantisering | 70B Q4 passer ikke alene i 32 GB VRAM; hele pc-prisen og vægforbruget skal beregnes/måles |
| Framework Desktop PRO 495/192 GB | 59.739 DKK DIY; 16 Zen 5-kerner, 40 CU; producenten angiver 300B-class ved 4-bit | Forudbestilling, uden SSD/strømkabel; uafhængig hastighed og strøm ikke målt |
| NVIDIA DGX Spark 128 GB | 20-core Grace Blackwell, op til 1 petaFLOP FP4; inferens op til 200B og finjustering op til 70B | Ingen verificeret dansk pris eller ensartet benchmark |
| Mac Studio M5 Max 128 GB | Op til 18 CPU-/40 GPU-kerner og 614 GB/s; M5 Max starter på 21.999 DKK med lavere hukommelse | 128 GB-pris skal konfigureres; ikke primært gamingvalg, ingen CUDA-garanti |
| Mac Studio M5 Ultra 256/512 GB | Op til 36 CPU-/80 GPU-kerner og 1,2 TB/s; M5 Ultra starter på 49.999 DKK med 96 GB | 256/512 GB koster mere; ingen modelhastighed påstået |

Ingen af disse er købt. Der findes ikke et samlet uafhængigt tokens/sekund-resultat. Før “bedste maskine”-påstande skal samme model, kvantisering, runtime, prompt, kontekst og batch måles på alle kandidater.

### Kanalnavne

1. **Pixel & Parameters** — anbefalet hovedbrand.
2. Silicon Sidequest.
3. Frame / Token.
4. Cache & Controller.
5. Neural Frame Lab.
6. TokenPlay Hardware.
7. GPU Sidequest.
8. FrameForge AI.
9. Handheld Intelligence.
10. Bitrate & Bytes.

Navneledighed, domæner, handles og varemærker er ikke kontrolleret.

---

## 13. Kendte risici og åbne kontrolpunkter

Prioriteret, uden at påstå at de er rettede:

1. **`claim_control` mangler i rankingens checks.** Det blokerer faktisk approval. Læs trin 1 i afsnit 5.
2. **Database indeholder forkastede poster.** Brug kun de fem leverancemapper; ryd ikke databasen uden backup.
3. **Voice-WAV genbruges pr. filnavn.** Nyt manuskript kræver ny stemmemappe.
4. **Balatro er 360p.** Undgå skarpsheds-/HD-påstande.
5. **Safe og zoom har forskelligt Hades II-start.** Det er bevidst; kontrollér mod deres egne clip plans.
6. **Trenddata bliver forældede.** Rank og visningstal skal opdateres før nye scripts.
7. **Publisherpolitikker kan ændres.** Recheck før publicering; Celeste-licensen er desuden revokerbar.
8. **Ranking er subjektiv.** Det er ikke en Legion Go 2 FPS- eller batteritest.
9. **Generic production og ranking er forskellige.** Læring/claimreview i `production.py` betyder ikke at ranking automatisk har samme kontrol.
10. **TikTok er ikke aktivt publiceringsintegreret.** Brug manuel eksport indtil aktuel audit/API-tilladelse.
11. **Instagram kræver offentlig HTTPS-medie-URL og aktuel Graph-konfiguration.** En signert lokal sti er ikke nok.
12. **Docker-image kan være forældet efter scriptændringer.** Genbyg eller mount aktuelle scripts; kontrollér scriptets faktiske output.
13. **Mini-biblens fontstier er Windows-specifikke.** Tilpas ved deploy/build på Linux.

---

## 14. Definition of done for Codex' næste arbejdstrin

Et trin er først færdigt når:

- Den konkrete brugerændring er implementeret uden at udvide opgaven vilkårligt.
- Standardbuild og relevante tests er kørt på det aktuelle deliverable.
- Rigtige kald/renders er kontrolleret, ikke kun imports eller kompilering.
- Den visuelle, redaktionelle og retlige kontrol er dokumenteret.
- Ingen fejlende relevante tests eller uafklarede blokeringer skjules.
- Nye manifester og hashes er kontrolleret ved medieændringer.
- `STATUS.txt`, `TEST_PROTOCOL.md` og relevante ejerinstruktioner beskriver den nye virkelighed.
- Kun egne midlertidige filer er ryddet, og Git-status er kontrolleret.
- Der gives én kort næste ejeropgave, hvis en ejerhandling er nødvendig.

### Den umiddelbare håndoff i én sætning

**Videoerne `handheld-zoom-v11` og `handheld-safe-v10` er produceret og kontrolleret, men ejerens kreative valg afventer, og rankingens manglende `claim_control` skal rettes før faktisk approval; derefter kan `handheld-013` produceres med friske trenddata — uden nogen automatisk social publicering.**
