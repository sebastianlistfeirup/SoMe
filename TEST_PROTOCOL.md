# Testprotokol — SoMe-maskinen

Dato: 2026-11-08
Miljø: Windows-vært, Docker Engine 29.9.2, container Python 3.11, SQLite, FFmpeg, faster-whisper small/int8, Microsoft Zira Desktop
Releasehash: registreres i det endelige releasecommit før push.
Formål: Adskille faktisk udførte tests fra ikke-verificerede eksterne integrationer.

## Automatiserede tests

Kommando: `docker compose run --rm --no-deps worker pytest -q`
Forventning: Alle tests består uden konti eller betalte API-kald.
Resultat: **40 passed** i den endelige låste Docker-build. Kun en ekstern Starlette TestClient-deprecationwarning.

Dækning omfatter rettigheder, alder, ejergodkendelse, statusskift, publish-blokering, job-idempotens, budget, SSRF/downloads, læring, klippeplaner, signerede links, login/CSRF, backup/restore, diskstop, upload-afklaring, ti unikke spil, korrekt #1/#10-mapping, titelbredde, dynamiske storyboards, lang transskription uden autojunk og blokering af ikke-demo uden internetassets.

## Udførte runtime-kontroller

| Kommando/scenario | Forventning | Resultat |
|---|---|---|
| `docker compose build` | Endeligt låst image | Bestået |
| `python -m app.cli doctor` | Konfiguration uden secrets/betalt kald | Bestået; DB/migration OK; 85,69 % disk; stop_render=false |
| `scripts/fetch_steam_gameplay.py --output /research` | Ti officielle Steam-klip med gyldigt format | Bestået; ti H.264/1080p-filer |
| `scripts/review_steam_clips.py review` | Kontaktark for hvert spil | Bestået; ti kontaktark visuelt gennemgået |
| `scripts/review_steam_clips.py plan` | Redaktionel plan og rettigheder | Bestået; ti unikke spil |
| `New-RankingVoice.ps1` | Lokal engelsk speak | Bestået; elleve WAV-filer |
| `python -m app.cli ranking --plan /research/plan.json --output /data/versions/legion-go2-top10-v6` | Komplet video og alle kontroller | Bestået; video_id=13, AWAITING_OWNER |
| Whisper på faktisk narration | Sprog og manuskriptmatch | Bestået; en=0,99955, lighed=97,47 % |
| Teknisk mediekontrol | Vertikal H.264/AAC og lydstandard | Bestået; 96,2 s, 1080×1920, yuv420p, 30 fps, 48 kHz, −16,3 LUFS, −0,8 dBTP |
| Visuel inspektion | Rigtige klip, titler, rangorden og thumbnail | Bestået på storyboard/thumbnail; fuld ejervisning afventer |
| Manifest og SHA-256 | Ni intakte leverancefiler | Bestået; alle hashes matcher |
| Mini-bibel v1.1 build | PDF/Markdown med internetklip som standard | Bestået; 29 sider, visuel kontrol med danske tegn |

Endelig video: `some-pilot/data/versions/legion-go2-top10-v6/video.mp4`
Thumbnail/storyboard/checks/rights ligger i samme mappe. `manifest.json` indeholder ni verificerede filhashes. Ingen publicering er foretaget.

## Tidligere verificeret fundament

Research med 43 reelle observationer, Alembic 0001, demo-research/læring, metrics uden opdigtede tal, lokal backup og separat restore, web/worker healthchecks samt blokering ved >90 % disk er tidligere udført og dokumenteret. Den gamle blå demo er ikke denne top-10-produktion.

## Ikke verificeret / blokeret

- Ejeren har endnu ikke set og godkendt hele den endelige video.
- VPS CPU/RAM/tid og deploy: ikke verificeret.
- Claude API og betalte jobs: ikke kaldt.
- YouTube/Meta OAuth, privat upload, publicering og virkelige metrics: ikke testet.
- Krypteret offsite backup: ikke konfigureret.
- Server-TTS/Kokoro og dansk speak: ikke kvalitetsgodkendt.
- FPS/batteritid på Legion Go 2: ikke målt; listen er redaktionel.

## Regel

“Bestået” betyder udført i det angivne miljø. Der gives ingen 100 % fejlfriheds- eller performancegaranti. Manglende ekstern adgang og ejergodkendelse rapporteres som ikke verificeret, aldrig som succes.
