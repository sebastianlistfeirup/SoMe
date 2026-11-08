# Testprotokol — SoMe-maskinen

Dato: 2026-11-08
Miljø: Windows-vært, Docker Engine 29.9.2, container Python 3.11, SQLite, FFmpeg, faster-whisper small/int8, Kokoro-82M ONNX
Testet build: lokal `some-pilot:local` med de nye mobilfiltre og kurateringsscripts. Endelig kodeidentitet dokumenteres af releasecommittet i Git-historikken.
Formål: Adskille faktisk udførte tests fra ikke-verificerede eksterne integrationer.

## Automatiserede tests

Kommando: `docker compose run --rm --no-deps worker pytest -q`
Forventning: Alle tests består uden konti eller betalte API-kald.
Resultat: **45 passed** i den endelige låste Docker-build. Kun en ekstern Starlette TestClient-deprecationwarning.

Dækning: rettigheder, alder, godkendelser, publish-blokering, jobs, budget, downloads/SSRF, læring, klippeplaner, signerede links, login/CSRF, backup, diskstop, upload-afklaring, ti unikke spil, #1/#10-mapping, titelbredde, dynamiske storyboards, autojunk-fri transskription, internetkrav, fuldskærms-crop, safe-layout, to zoom-faser med eksakte varigheder og platformsspecifikke safe areas/tempoer.

## Model- og klipkontrol

- Kokoro-82M v1.0 ONNX fra den officielle `model-files-v1.1`-release.
- Model: 325.505.369 bytes; SHA-256 `beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a`.
- Voices: 28.214.398 bytes; SHA-256 `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d`.
- Apache-2.0-model og MIT `kokoro-onnx 0.6.1`. Ingen betalt API eller stemmeefterligning.
- Ni officielle Steam-gameplayklip er H.264/1080p. Balatro er Playstacks officielle launch trailer fra YouTube i H.264/640×360; en HD-download kunne ikke verificeres og er ikke påstået.
- Alle ti lokale kildefilers SHA-256 matcher `research/top10-legion-go2/rights.json`. Kontaktark og konkrete klippunkter er visuelt gennemgået.

## Færdige platformproduktioner

| Version | ID/varighed | Format og lyd | Kontrol |
|---|---|---|---|
| TikTok `handheld-tiktok-v2` | 15 / 49,2 s | 1080×1920, tæt action, hurtigere Kokoro | rights/technical/safety/quality ALLOW; speak 96,67 %; −16,8 LUFS; −1,0 dBTP |
| Reels `handheld-reels-v2` | 14 / 102,2 s | 1080×1920, fuldskærms-action, gem/del-CTA | rights/technical/safety/quality ALLOW; speak 99,34 %; −16,5 LUFS; −1,0 dBTP |
| YouTube `handheld-youtube-v4` | 18 / 171,4 s | 1920×1080, længere kommentar og landskabsthumbnail | rights/technical/safety/quality ALLOW; speak 99,55 %; −16,4 LUFS; −0,9 dBTP |
| Safe `handheld-safe-v10` | 31 / 102,1 s | 1080×1920, fuld spilbredde og tekst uden beskæring | rights/technical/safety/quality ALLOW; speak 99,51 %; −16,4 LUFS; −1,0 dBTP |
| Zoom `handheld-zoom-v11` | 32 / 102,1 s | 1080×1920, to præcise fuldskærms-zooms pr. spil | rights/technical/safety/quality ALLOW; speak 99,51 %; −16,5 LUFS; −0,9 dBTP |

Alle er H.264 High/yuv420p, AAC 48 kHz og 30 fps med 1:1 pixels. Whisper bruger den faktisk afspillede narration med trim/tempo. Hver version har ni manifestfiler; de 18 nye SHA-256 er kontrolleret, og de tidligere 27 matcher også deres manifester. Alle står i `AWAITING_OWNER`.

Visuelle checks: Zoom-v11 er kontrolleret på fire præcise tidspunkter for hvert spil: bred visning, zoom 1, bred visning og zoom 2. Hades II har gameplay i begge zoom-faser. Safe-v10 er kontrolleret som storyboard og billedserie for hvert sekund; hele spilbredden og tekstkort bevares. Thumbnails er kontrolleret. Dette erstatter ikke ejerens fulde visning.

## Øvrige verificeringer

- Endelig Docker-build med låste afhængigheder bestået.
- Mini-bibel v1.3 PDF/Markdown bygget; 29 sider; mobilregler og danske tegn visuelt kontrolleret på forsiden og side 17-18.
- `research/handheld-content-calendar.json`: 12 oprindelige emner plus 10 nye idéer i `research/handheld-trend-ideas-2026-11-08.json`.
- Trendsignaler: Valves Deck-liste 2.-8. november, 34.376 visninger/7 dage for Deck Wizards top-50 og 30.148/1 måned for HiTechKings Legion Go 2-test. Disse er snapshots, ikke prognoser.
- Lokal AI- og navneresearch er gemt med kilder og tydelige mangler for benchmarks og navneledighed.
- Tidligere fundament: research, Alembic 0001, demo-læring, backup/restore, healthchecks og >90 % diskstop.

## Ikke verificeret / blokeret

- Ejerens fulde visning og godkendelse af versionerne afventer.
- VPS CPU/RAM/tid og deploy: ikke verificeret.
- Claude API og betalte jobs: ikke kaldt.
- YouTube/Meta OAuth, privat upload, publicering og virkelige metrics: ikke testet.
- Krypteret offsite backup: ikke konfigureret.
- Dansk TTS: ikke kvalitetsgodkendt.
- FPS/batteritid på Legion Go 2: ikke målt; listen er redaktionel.

## Regel

“Bestået” betyder udført i det angivne miljø. Der gives ingen 100 % fejlfriheds- eller performancegaranti. Manglende ekstern adgang og ejergodkendelse rapporteres som ikke verificeret, aldrig som succes.
