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

Resultat: **62 passed**. Kun en ekstern Starlette TestClient-deprecationwarning.

Dækning: rettigheder, alder, statusflow, approvalhash, publish-blokering, jobs, budget, downloads/SSRF, backup/restore, ZIP path traversal, idempotent metricsimport, demo/produktionsadskillelse, SAFE, ZOOM, claim control, voice providers, teksthash, WAV/lydstream, sample rate, segmentdækning, ElevenLabs paid-/pris-/rettighedsblokering, PCM-konvertering, ranking til approval, testpost-timing, doctor og dashboardruter.

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
- `python -m app.cli doctor`: migration 0001, FFmpeg/ffprobe/espeak-ng, modelcache og sikre defaults bekræftet. Diskforbrug var 87,03 % (alarm, men under 90 % renderstop).

## Ikke verificeret / blokeret

- Ejerens fulde visning og lytning af de nye videoer afventer.
- ElevenLabs eksternt API, faktisk leverandørfaktura og stemmekvalitet er ikke testet.
- Claude API og paid jobs er ikke kaldt.
- YouTube/Meta OAuth, privat upload, publicering og virkelige metrics er ikke testet. TikTok bruger manuel eksport.
- VPS-deploy, offsite krypteret backup og produktionsdeploy er ikke verificeret.
- Ingen reelle publicerede datapunkter eller dokumenteret læringsforbedring findes endnu.
- Dansk TTS er ikke kvalitetsgodkendt.
- FPS/batteritid på Legion Go 2 er ikke målt; rangeringen er redaktionel.

## Regel

“Bestået” betyder udført i det angivne miljø. Der gives ingen 100 % fejlfriheds-, integrations- eller performancegaranti. Manglende ekstern adgang og ejergodkendelse rapporteres som åbne punkter, aldrig som succes.
