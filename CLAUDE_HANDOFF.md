# Handoff til Claude — SoMe-maskinen

Opdateret: 2026-11-13
Repository: https://github.com/sebastianlistfeirup/SoMe
Lokal arbejdsmappe: `C:\Users\compu\Documents\SoMe`

Denne fil er beregnet som startkontekst for en ny Claude-session. Del aldrig API-nøgler, passwords, OAuth-tokens eller SSH-private-keys i chat, logs eller Git. Eksisterende secrets ligger uden for repository.

## 1. Projektets formål og kreative retning

SoMe-maskinen skal producere rettighedssikre, redaktionelt gennemarbejdede videoer til **Pixel and Parameters**:

- Gaming, retro gaming, handheld gaming og lokal/PC-AI.
- Kanalen er ikke en ren repost-maskine: Opslag skal have egen pointe, dokumenterede påstande, reel footage, menneskelig godkendelse og platformtilpasning.
- Målet er bedre hooks, retention, watch time, engagement og subscribers gennem kontrollerede eksperimenter og reel læring.
- Der må ikke gives garantier om vækst, likes eller subscriptions. Langtidsforbedring er endnu ikke dokumenteret.

Standard sikkerhedstilstand:

- `DRY_RUN=true`
- `PUBLISH_ENABLED=false`
- `PAID_JOBS_ENABLED=true` på serveren
- `WORKER_CONCURRENCY=1`

Der må **ikke** produceres nye redaktionelle ejervideoer, før ejeren eksplicit skriver: **“Nu må du begynde”**. Korte syntetiske integrationstestklip er tilladt. Eksisterende footage i `C:\Users\compu\Videos\SoMe-captures` må ikke ændres.

## 2. Aktuel verificeret status

Seneste relevante applikationscommit:

- `918bd2c9` — `Require MobyGames research and verify cross-platform footage`
- `ca3b639` — dokumentationsopdatering efter deployment

Verificeret både lokalt og på Contabo-VPS:

- **197/197 tests består** (efter `72a3269c`)
- Standard Docker-build består
- Migration 0001 er OK
- `doctor` er OK
- Web og worker er healthy
- Intern og offentlig HTTPS-health svarer `status=ok`
- Publishing er slået fra
- TikTok Direct Post er stadig ikke eligible

Seneste store funktioner:

1. Ejergodkendt intro/outro er integreret i alle nye videoer.
2. MobyGames-research er obligatorisk for hvert featured game.
3. Footage kan genbruges på tværs af platforme, men kun når målplattformens udgivelse er dokumenteret.
4. Capture Bridge behandler platformmapper som footage-proveniens, ikke som spilnavn eller udgivelsesbevis.

## 3. Server og grundlæggende kommandoer

Server:

- Contabo Cloud VPS Plus 6
- IP: `62.171.167.243`
- HTTPS: `https://62.171.167.243.sslip.io`
- App på serveren: `/opt/some/app`
- Produktion: `/opt/some/app/some-pilot`

SSH fra lokal mappe:

```bash
ssh -F .codex_tmp/deploy/ssh_config some-contabo-deploy
```

Lokal standardtest fra repository-roden:

```bash
MSYS_NO_PATHCONV=1 docker compose -f some-pilot/compose.yaml build --quiet
MSYS_NO_PATHCONV=1 docker compose -f some-pilot/compose.yaml run --rm --no-deps worker pytest -q
```

Deployment:

```bash
ssh -F .codex_tmp/deploy/ssh_config some-contabo-deploy \
  'set -e; cd /opt/some/app; git pull --ff-only origin main; cd some-pilot; ./scripts/deploy.sh'
```

Sundhed på serveren:

```bash
ssh -F .codex_tmp/deploy/ssh_config some-contabo-deploy \
  'cd /opt/some/app/some-pilot && sudo docker compose -f compose.yaml -f compose.production.yaml ps; curl -fsS http://127.0.0.1:8000/healthz'
```

`deploy.sh` bygger, kører hele testpakken, migrerer, kører doctor og genstarter web/worker. Deploy ikke uden fuld lokal test, `git diff --check`, commit og push.

## 4. Vigtig kodekort

### Produktion og godkendelse

- `some-pilot/app/pipeline/production.py`
  - Almindelig reel medieproduktion.
  - Kræver medieplan og editorial-pakke.
  - Bruger ElevenLabs i ikke-demo-flow.
  - Tilføjer obligatorisk brand-intro/outro.
- `some-pilot/app/pipeline/production_ranking.py`
  - Top-10/rankingflow.
  - Bruger ElevenLabs voiceover, 10 rigtige klip og editorial gates.
  - Vælger 16:9 intro/outro til YouTube og 9:16 til andre.
- `some-pilot/app/pipeline/real_media.py`
  - Reel medieplan og mindst 80 % reel medieprocent.
  - AI-genereret indhold tæller ikke som reel media.
- `some-pilot/app/pipeline/editorial.py`
  - Content Bible scoring, freshness, reception og MobyGames gates.
- `some-pilot/app/pipeline/ranking.py`
  - Rankingplan, scenevalidering og rendering.
- `some-pilot/app/pipeline/game_research.py`
  - Ny fælles MobyGames- og platformsresearchkontrakt.

### Branding

- `some-pilot/app/pipeline/brand_ident.py`
  - Ejergodkendt 3,5 sek. intro og outro.
  - 9:16: 1080×1920.
  - 16:9: 1920×1080.
  - `GAMING CULTURE × AI` i intro.
  - `FOLLOW FOR MORE` i outro.
  - Cachen invalideres ved ændret logo eller renderer.
- `some-pilot/assets/brand/pixel-and-parameters-primary-logo-v1.png`

Den godkendte visuelle version må ikke ændres uden ny ejergodkendelse. Ingen alternativ P-animation eller kraftigere baggrundsbrumme.

### Research, metrics og læring

- `some-pilot/app/pipeline/metrics.py`
  - YouTube Analytics kan hente views, watch time, retention, likes, comments, shares og subscribers gained/lost.
- `some-pilot/app/pipeline/learning.py`
  - Ugens læring bruger views, retention, watch time pr. view, engagement og netto-subscribers pr. 1.000 views omkring dag 7 (én værdi pr. publicering), kombineret via vægtet geometrisk gennemsnit (`learning-signals-v1`). Hooks sammenlignes kun inden for samme platform/format/længde og samles pr. hook på tværs af kohorter.
  - Grupper: platform, format, hook og længdebucket.
  - Multiplikatorer begrænses til 0,75–1,25.
  - Minimum to samples; lille datamængde dæmpes med `n/(n+5)`.
  - 80 % kendte formater / 20 % eksperimenter.
- `some-pilot/app/pipeline/ai.py`
  - Claude Sonnet til manuskripter/revision.
  - Claude Haiku til research/claimkontrol.
  - Paid/pris/nøgle-gates før eksterne kald.

Læringen er ikke færdig som dokumenteret selvforbedrende hjerne. Første store forbedring bør være native retention-, watchtime-, likes- og subscriptionsdata på alle platforme, efterfulgt af sammenlignelige A/B-tests.

### Publicering og review

- Review-center: `/review`
- Ejer skal se hele videoen før godkendelse.
- Immutable approvalhash binder video, thumbnail, tekst, links, destinationer, konto-ID’er, YouTube-synlighed og tidspunkt.
- Godkendelse opretter ét idempotent job pr. destination.
- Afvisning opretter ingen publiceringsjobs.
- `revise_post` ændrer kun titel, caption og hashtags; video, lyd og visuals genbruges.
- En destination, der allerede er publiceret, uploades ikke igen ved fejl på en anden.

### Capture Bridge

- `some-pilot/scripts/capture_bridge.py`
- Lokal konfiguration: `.codex_tmp/deploy/capture_bridge.json`
- Input: `C:/Users/compu/Videos/SoMe-captures`
- Output: `C:/Users/compu/Videos/SoMe-processed/<spil>/`
- Upload til server: `/opt/some/data/media-library/<spil>/`

Platformmapper som `PS5`, `Switch 2`, `PS4` osv. er footage-proveniens. Spillet genkendes primært i filnavnet. Et ukendt spil i en platformmappe stopper med `unknown_game_profile` i stedet for at blive registreret som standardspillet.

Capture Bridge kørte efter deployment som lokal baggrundsproces. Hvis computeren eller sessionen genstartes, startes den igen med:

```bash
python some-pilot/scripts/capture_bridge.py --config .codex_tmp/deploy/capture_bridge.json --watch --upload
```

## 5. Obligatorisk MobyGames-research

Alle featured games skal have et `preparation`-objekt, både i almindelige editorial-pakker og rankingplaner.

Krav:

- Konkret HTTPS MobyGames-spilside under `/game/`.
- Review score **eller** eksplicit ikke-fundet-note.
- Fun facts/trivia **eller** eksplicit ikke-fundet-note.
- Observationstidspunkt; maks. 168 timer gammel.
- Mindst én dokumenteret udgivelsesplatform.
- Platformsevidence maks. 720 timer gammel.
- Almindelige editorial-pakker skal have MobyGames- og release-URL’er registreret som inspicerede kilder.
- Systemet må aldrig opfinde score, trivia eller platforme.

Vigtig begrænsning: MobyGames viste Cloudflare-botskontrol under undersøgelsen. Der er ikke bygget en bypass-scraper. Den konkrete side skal være inspiceret manuelt eller gennem en lovlig, understøttet datakilde før produktion.

Central implementering:

- `some-pilot/app/pipeline/game_research.py`

Centrale fejl:

- `mobygames_refresh_required`
- `mobygames_review_score_or_not_found_note_required`
- `mobygames_fun_facts_or_not_found_note_required`
- `platform_release_refresh_required:<platform>`
- `platform_release_unverified:<target>`
- `game_preparation_invalid`
- `research_source_not_registered:<url>`
- `research_source_not_inspected:<url>`

## 6. Footage på tværs af platforme

Mappenavnet er kun proveniens:

- `PS5`-footage må bruges til PC-opslag, når PC-udgivelsen er dokumenteret.
- Samme footage må bruges til Switch 2-opslag, når Switch 2-udgivelsen er dokumenteret.
- Det må bruges til generelle opslag som “Best Remakes of All Time”, hvor målet er `cross-platform`.
- Det må aldrig antages, at et spil findes på en anden platform, fordi mappenavnet findes.

I ranking bruges:

- `target_game_platform="PC"`
- `target_game_platform="Switch 2"`
- `target_game_platform="cross-platform"` som standard

Den sociale destination (`youtube`, `reels`, `tiktok`) er separat fra spillets målplattform.

Relevante tests i `some-pilot/tests/test_game_research.py` beviser:

- PS5-footage kan bruges til dokumenteret PC-opslag.
- Switch 2 uden dokumentation blokeres.
- `cross-platform` kræver ikke én bestemt konsol.
- Gamle researchdata kræver refresh.
- Manglende MobyGames-score/trivia kræver ikke-fundet-noter.

## 7. Content Bible og editorial gates

Content Bible/Kimi Kit:

- 20 recipes
- 120 idéer
- 58 kilder

Vigtige filer:

- `some-pilot/content/RECIPE_INDEX.json`
- `some-pilot/content/IDEA_BANK.json`
- `some-pilot/content/SOURCE_REGISTER.json`
- `some-pilot/content/config.json`
- `some-pilot/content/schemas/packet.schema.json`

Ikke-demo-produktion kræver:

- `editorial-packet.json`
- `needs_owner_review` eller `approved_draft`
- Lane-match: gaming, AI eller crossover
- Alle syv `quality_dimensions`
- Mindst 85 point
- Friske inspicerede kilder
- Hørbar reception eller sand dokumenteret undtagelse pr. featured game
- MobyGames-preparation
- Dokumenteret målplattform hvor relevant

Research-eksemplet i `content/examples` er ikke et gyldigt produktionsinput.

## 8. Medie- og rettighedsregler

Ny produktion kræver medieplan:

- Mindst 80 % af varigheden skal være rigtige videoklip eller rigtige billeder.
- AI-genereret indhold tæller ikke som reel media.
- Hvert aktiv skal have kontekst, lokal fil, HTTPS source/policy URL, rettighedshaver, bevis, kreditering og person-/aldersmetadata.
- Rettigheder og medieprocent skal være `ALLOW` før godkendelse.
- `media_composition.json` er obligatorisk.

Egne gameplayoptagelser kan have separat footage-platform og målplattform. Udgiverpolitik og platformbevis skal stadig verificeres pr. produktion.

## 9. Stemmer og avatarregler

Godkendte produktionsstemmer:

- Gaming ElevenLabs: `HfRP3cIhYLmeNHeTvkWK`
- AI ElevenLabs: `8CjmkufHc22WbMZEBHbm`

Regler:

- Kokoro `af_bella` er kreativt afvist til nye produktionsopslag.
- Kokoro må kun bruges til gamle/tekniske demo-flows.
- HeyGen og synlige avatarer er udfaset.
- Nye produktionsopslag skal være voiceover uden avatar.
- ElevenLabs kræver paid jobs, API-nøgle, voice-ID, rettighedsbekræftelse og dateret pris inden for budget.

## 10. Platformstatus

### YouTube

- OAuth og kanaladgang verificeret.
- Privat testupload er processed.
- Analytics kan læses.
- App står i Testing; produktionsforvaltning kræver senere opfølgning.

### Instagram og Facebook

- Ejerens konti er verificeret.
- Testreels er publiceret og verificeret.
- Meta App Review/Advanced Access mangler.

### TikTok

- Sandbox/inbox-kladde er verificeret.
- En inbox-kladde er ikke et offentligt opslag.
- Direct Post kræver production-review og eksplicit ejerconsent.
- Aktuel blocker: `tiktok_direct_post_not_eligible`.

## 11. Sikkerhed og drift

- SSH bruger separat ED25519-nøgle.
- Root- og passwordlogin over SSH er slået fra.
- UFW og Fail2ban er aktive.
- Caddy giver HTTPS.
- Web bindes til loopback på serveren.
- Krypteret lokal backup er verificeret.
- Offsite backup er ikke konfigureret.
- Contabos cloudfirewall er ikke konfigureret.

Opbevar aldrig følgende i repository eller chat:

- `.env`
- App passwords
- API keys
- Client secrets
- OAuth refresh tokens
- SSH private keys
- Backup keys

## 12. Arbejdsregler for Claude

1. Start med `git status --short` og `git log -3 --oneline`.
2. Rør ikke ejerens lokale footage eller WIP-mapper.
3. Brug fælles værktøjer og eksisterende konventioner frem for nye dependencies.
4. Ændringer i produktionskode skal have relevante regressionstests.
5. Kør standardbuild og hele testpakken før commit.
6. Kør `git diff --check`.
7. Commit kun relevante filer — ikke `.codex_tmp`, `brand`, `tools`, voice-previews eller brugerens WIP.
8. Deploy først efter commit og push.
9. Kræv samme testresultat på VPS.
10. Opdatér `STATUS.txt`, `OWNER_ACTIONS.md`, `TEST_PROTOCOL.md` og `some-pilot/README.txt`, hvis drift eller kontrakter ændres.

## 13. Lokale untracked filer der ikke hører til commit

Disse eksisterede før denne handoff og skal ikke slettes eller committes uden ejerbesked:

- `.codex_tmp/`
- `.tools/`
- `Grok Mini-PC/`
- `KIMI_HANDOFF_SOME_MASKINEN.docx`
- `Pixel and Parameters - AI/`
- `brand/`
- `research/heygen-*.png`
- `tools/`
- `voice-previews/`

## 14. Prioriterede næste opgaver

### Højeste prioritet: læring og metrics

1. Implementér native retention-, watchtime-, likes- og subscriptionsindsamling for YouTube og undersøg Meta/TikTok API-kapacitet.
2. ~~Udvid `weekly_learning` fra kun views til engagement-, retention- og subscriber-signaler med samme dampede, non-kausale metode.~~ Implementeret og deployet i `72a3269c` (197 tests lokalt og på VPS).
3. Opret kontrolleret A/B-eksperimentmodel med én ændring ad gangen.
4. Gem eksperimenthypotese, variant, randomisering, resultat og rollback.

### Backend

5. Platformvariant-preview før godkendelse.
6. Visuelt mediebibliotek med rettigheder, kontaktark og tidligere brug.
7. Afvisningskategorier der kan ændre video/klip/stemme — ikke kun tekst.
8. Jobovervågning, dead-letter-håndtering og bedre reconciliation.
9. Konto-/tokenstatus uden at vise secrets.
10. Offsite backup og restorecenter.

### Opslagsmotor

11. Hookoptimering baseret på 1/3/5-sekunders retention.
12. Destinationspecifikke scripts, captions, covers og CTA’er.
13. Clip- og scene-ranking fra faktisk retention.
14. Automatisk visuel kvalitetskontrol for crops, sorte frames, gentagelser og læsbarhed.
15. Stemme-/udtalekontrol for spilnavne, tal og tempo.

### Eksterne punkter

16. TikTok production-demo/review og Direct Post-consent.
17. Meta App Review/Advanced Access.
18. YouTube-appens overgang fra Testing.
19. Offsite backup.

## 15. Hvad Claude ikke skal gøre

- Producer ikke nye ejervideoer uden eksplicit go.
- Publicer ikke noget.
- Omgå ikke MobyGames’ botskontrol.
- Fabrikér ikke review scores, fun facts, platforme eller reception.
- Brug ikke Kokoro `af_bella` til nye produktionsopslag.
- Tilføj ikke nye dependencies uden at kontrollere manifest og eksisterende idiom.
- Markér ikke et TikTok-inbox-draft som offentligt publiceret.
- Antag ikke platformudgivelse fra mappenavn.
- Ændr ikke den godkendte intro/outro uden ny visuel ejergodkendelse.
- Giv ikke garanti for likes, subscribers eller fejlfri drift.

## 16. Hurtig sundhedssjek ved genoptagelse

```bash
git status --short
git log -3 --oneline
MSYS_NO_PATHCONV=1 docker compose -f some-pilot/compose.yaml build --quiet
MSYS_NO_PATHCONV=1 docker compose -f some-pilot/compose.yaml run --rm --no-deps worker pytest -q
ssh -F .codex_tmp/deploy/ssh_config some-contabo-deploy 'curl -fsS http://127.0.0.1:8000/healthz'
```

Forventet baseline på genoptagelsestidspunktet: **199 tests** lokalt (VPS: 197 indtil næste deploy).
