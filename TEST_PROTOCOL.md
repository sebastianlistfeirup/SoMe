# Testprotokol — SoMe-maskinen

Dato: 2026-11-08
Miljø: Windows-vært, Docker Engine 29.9.2, container Python 3.11, SQLite, FFmpeg, espeak-ng
Releasehash: registreres efter endeligt commit
Formål: Adskille faktisk udførte tests fra ikke-verificerede eksterne integrationer.

## Automatiserede tests

Kommando: `docker compose run --rm --no-deps web pytest -q`
Forventning: Alle tests består uden net, konti eller betalte API-kald.
Resultat: **30 passed** i den låste container. En ekstern Starlette TestClient-deprecationwarning fra testværktøjet; ingen testfejl.

Dækning:

- Ukendt/udløbet licens og 5-sekundsmateriale blokeres.
- Mindreårige/forbudt indhold og ukendt alder kan ikke passere automatisk.
- Ejergodkendelse kræver fuld visning; ændret video/konto og ugyldige statusskift blokeres.
- `PUBLISH_ENABLED=false` og nødstop blokerer central publicering og produktion.
- Job-idempotens og parallelle claims giver kun én worker.
- Budgetloft håndhæves også ved parallelle reservationer; betalte jobs er slået fra som standard.
- Private/loopback/cloud-metadata-URL'er, HTTP og fil-signaturmanipulation afvises.
- Læring viser sample size/median og laver versionsstyrede, ikke-kausale opdateringer.
- Demo-læring og produktionslæring/metrics holdes adskilt.
- Klippeplaner valideres; talændringer i transskription kræver review.
- Signerede medielinks kræver aktuel godkendelse og afviser manipulation/ændringer.
- Login, CSRF og beskyttet medieadgang er testet.
- Backup verificeres og gendannes til separat mappe med publishing/paid jobs slået fra.
- Render stopper ved 90 % diskforbrug.
- Upload-timeout giver `RECONCILE_REQUIRED` og blokerer blind genupload.

## Udførte runtime-kontroller

| Kommando/scenario | Forventning | Resultat |
|---|---|---|
| `docker compose build` | Låst image bygges | Bestået |
| `python -m app.cli migrate` | Initial Alembic-migration | Bestået, revision 0001 |
| `python -m app.cli doctor` | Ingen secrets eller betalt kald | Bestået; rapporterede diskblokering og manglende integrationer |
| `research --demo` | Tydelig fixture-demo | Bestået, 1 DEMO-observation |
| Import af `research/2026-11-08/research.json` | Reelle observationer og topics | Bestået, 43 observationer, 14 scores |
| `learn --weekly --demo` | Ingen konklusion uden metrics | Bestået; rapport uden modelopdatering |
| `metrics --due` | Ingen opdigtede metrics | Bestået; ingen due/publications |
| `backup --verify` | Konsistent DB og verificeret arkiv | Bestået; lokal ukrypteret testbackup |
| `demo --produce` på >90 % disk | Stop før nyt renderjob | Bestået som forventet blokering |
| Restore til separat mappe | DB-integrity og sikker config | Bestået; `integrity=ok`, publishing/paid jobs false |
| `docker compose up -d`, `/healthz`, `/login` | Rigtige web/worker-processer og HTTP | Bestået; web + worker `healthy`, health JSON og login HTTP 200; containere stoppet efter test |

## Ikke verificeret / blokeret

- Faktisk video-render, Whisper-download/transskription, lydmåling og storyboard på det lokale miljø: **blokeret af >90 % diskforbrug**. Koden er implementeret, men må ikke markeres som medieverificeret.
- CPU RAM/tid på Hetzner VPS: ikke målt.
- Claude API: ikke kaldt; ingen nøgle eller betaling.
- YouTube/Meta OAuth, privat upload, publicering og virkelige metrics: ikke testet.
- Krypteret offsite backup: ikke konfigureret; lokal backup-test er ikke offsite bevis.
- Kokoro og dansk TTS: ikke installeret/kvalitetsgodkendt.
- End-to-end privat testupload kan først udføres efter medie- og kontoblokeringer er løst.

## Regel

“Bestået” ovenfor betyder udført i det angivne miljø. Der gives ingen 100 % fejlfriheds- eller performancegaranti. Manglende ekstern adgang rapporteres som ikke verificeret, aldrig som succes.
