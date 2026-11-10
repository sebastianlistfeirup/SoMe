# Testprotokol — SoMe-maskinen

Dato: 2026-11-10
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

Resultat: **70 passed**. Kun en ekstern Starlette TestClient-deprecationwarning.

Dækning: rettigheder, alder, statusflow, approvalhash, publish-blokering, jobs, budget, downloads/SSRF, backup/restore, ZIP path traversal, idempotent metricsimport, demo/produktionsadskillelse, SAFE, ZOOM, claim control, voice providers, teksthash, WAV/lydstream, sample rate, segmentdækning, ElevenLabs paid-/pris-/rettighedsblokering, PCM-konvertering, ranking til approval, testpost-timing, Claude-modelrouting og modelpriser, doctor og dashboardruter.

## Claude-modelrouting og omkostninger

- `claude_draft` kalder `claude-sonnet-5-5`; `review_draft` kalder `claude-haiku-5-5` via research-ruten.
- En mocktest med 1.000 input- og 100 outputtokens pr. model bekræfter Sonnet-pris 0,01935 DKK og Haiku-pris 0,0009675 DKK med de særskilt konfigurerede testtakster.
- Paid jobs slået fra, tom API-nøgle og manglende input-/outputpris for hver rute blokerer før `Anthropic` instantieres. Ingen costreservation eller netværkskald opstår i disse seks negative testtilfælde.
- Standard er `MONTHLY_AI_BUDGET_DKK=50`, `MAX_JOB_AI_COST_DKK=5` og `PAID_JOBS_ENABLED=false`.
- Doctor rapporterer script-/researchmodel og om nøgle og DKK-priser er konfigureret, men aldrig selve nøglen.
- Tests bruger udelukkende mocks. Claude API, faktisk leverandørfaktura og produktionskvalitet er ikke eksternt verificeret.
- Den købte Contabo Cloud VPS Plus 6 har skærmpris €23,75/måned, cirka 177 DKK. Ved 30 videoer/måned er Claude-estimatet 6,30 DKK og totalen cirka 183 DKK. Dobbelt API-forbrugslager giver cirka 190 DKK samlet. Det er et estimat med vejledende valutakurser, ikke en verificeret faktura; se OWNER_ACTIONS.md for tokenantagelser og kilder.

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

- Cloud VPS Plus 6: 6 vCPU, 12 GB RAM, 300 GB NVMe, Ubuntu 24.04. Commit `ec6312a` er deployet med `./scripts/deploy.sh` og **70/70 tests bestod** på serveren.
- Den første serverkørsel gav 68 passed og 1 failed, fordi backup-testen arvede produktionens BACKUP_KEY. Testen er gjort miljøuafhængig, separat krypteret verify/restore er tilføjet, og både lokal og server-suite er derefter 70/70 grøn.
- Executable-bit er rettet på alle fem shellscripts. Standarddeployment fungerer derefter uden Bash-workaround.
- SSH: verificeret ED25519-hostfingerprint, separat deploynøgle, `PermitRootLogin no`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`. UFW er aktiv med default deny og kun ejerens admin-IP på port 22.
- Web/worker er healthy. `/healthz` svarer ok med publishing og paid jobs fra. Kun 127.0.0.1:8000 er åbent for web; ingen offentlig webport.
- En demokørsel i web-containeren stoppede med exit 137 på grund af 1 GB-grænsen. Den korrekte worker-service med 5 GB gennemførte `topic-2-v1`, video_id=1: 17,533 sekunder, 1080×1920, H.264 + AAC, AWAITING_OWNER, 10/10 manifesthashes og alle syv kontroller ALLOW.
- Kokoro `af_bella` genereret på VPS: 3,679 sekunder, 24 kHz mono, kontrol ALLOW, paid_call=false og cost_dkk=0.
- Krypteret backup `/data/backups/some-backup-20261110T211132Z.zip.enc`: encrypted=true og verified=true. Restore integrity=ok; midlertidig restoremappe er fjernet. Offsite=false.
- Dashboard-ejer `owner` er oprettet uden at vise adgangskoden. Initialkoden er kun i serverens root-beskyttede secret-mappe.
- Claude-prissætning er konfigureret med Frankfurter/ECB-kurs 2026-11-10, 1 USD=6,6661 DKK. Sonnet: 13,3322 input og 66,661 output DKK/million. Haiku: 0,66661 input og 3,33305 output DKK/million. Doctor viser begge prisruter=true, API-nøgle=false, paid=false og forbrug=0.

## Ikke verificeret / blokeret

- Kokoro-stemmen er kreativt godkendt; platformsspecifik approval efter ejerens fulde visning afventer fortsat.
- ElevenLabs eksternt API, faktisk leverandørfaktura og stemmekvalitet er ikke testet.
- Claude API og paid jobs er ikke kaldt. Der findes ingen API-nøgle eller bekræftet leverandørfaktura. Faktisk bankkurs og eventuel moms kan afvige fra den dokumenterede referencekurs.
- YouTube/Meta OAuth, privat upload, publicering og virkelige metrics er ikke testet. TikTok bruger manuel eksport.
- Contabos cloudfirewall og offsite backup er ikke konfigureret. Endelig faktura og moms er ikke verificeret; kontrolpanelet viser én måneds kontrakt.
- Ingen reelle publicerede datapunkter eller dokumenteret læringsforbedring findes endnu.
- Dansk TTS er ikke kvalitetsgodkendt.
- FPS/batteritid på Legion Go 2 er ikke målt; rangeringen er redaktionel.

## Regel

“Bestået” betyder udført i det angivne miljø. Der gives ingen 100 % fejlfriheds-, integrations- eller performancegaranti. Manglende ekstern adgang og ejergodkendelse rapporteres som åbne punkter, aldrig som succes.
