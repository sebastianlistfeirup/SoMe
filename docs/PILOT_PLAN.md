# Pilot: 12 videoer over 4 uger

**Status:** Klar, ikke startet. Der produceres intet, før ejeren skriver **“Nu må du begynde”**.

## Hvorfor

Alle gates er bygget, men læringen har ingen rigtige data. En afgrænset pilot giver de første sammenlignelige målinger. Den tester også hele kæden i praksis: pakke, footage, stemme, godkendelse, publicering, metrics, læring og scorecard. Der bygges ikke flere funktioner, før piloten har kørt.

## Design: 2 hooks × 2 længder

To forhåndsregistrerede eksperimenter kører samtidig. Hver historie får begge tildelinger (faktorielt design).

| Eksperiment | Variabel | Varianter | Primær metrik | Guardrails |
|---|---|---|---|---|
| A — `content/pilot/pilot-hook.json` | `hook_type` | `bold_claim` (kontrol) / `question` | `hook_retention_3s` | retention, netto-subs pr. 1.000 views |
| B — `content/pilot/pilot-length.json` | `duration_bucket` | `short` ≤ 35 s (kontrol) / `medium` 36–60 s | netto-subs pr. 1.000 views | engagement pr. 1.000 views |

- **Omfang:** 12 historier, 6 pr. variant i hvert eksperiment, cirka 3 om ugen.
- **Destinationer:** Samme 9:16-video til YouTube Shorts, Reels, TikTok og Facebook Reels med platformvarianter af teksten. Hver platform er sin egen kohorte i læringen.
- **Idéer:** Fra `python -m app.cli ideas --next 12`, ca. 8 udnyt og 4 udforsk.
- **Tidsmåling:** Ejeren logger minutter pr. trin med `timelog`.

## Kørsel, trin for trin

1. Registrér eksperimenterne (én gang):
   ```bash
   python -m app.cli experiment create --spec content/pilot/pilot-hook.json
   python -m app.cli experiment create --spec content/pilot/pilot-length.json
   ```
2. For hver historie: `prefill-packet --idea <ID>`, research og footage. Derefter `experiment assign --id <A> --story <story_id>` og `--id <B>` samme historie. Skriv åbning og længde efter tildelingen.
3. Sæt begge tildelinger i medieplanen:
   ```json
   "experiments": [{"experiment_id": 1, "variant_id": "question"}, {"experiment_id": 2, "variant_id": "medium"}]
   ```
   Produktionen blokerer, hvis hook eller færdig længde ikke matcher tildelingen.
4. Ejeren ser hele videoen og godkender eller afviser med kategorier.
5. Metrics hentes automatisk ved dag 1, 3, 7 og 28 (YouTube inkl. retention-kurve). Meta/TikTok importeres via CSV, indtil API-adgang er på plads.
6. Ugentlig læring (mandag) viser scorecard, eksperimentstatus og næste idéer.

## Stop og beslutning

- **Når et eksperiment stopper:** Når begge varianter har mindst 6 målinger. Eller efter 42 dage, hvorefter resultatet er “inconclusive”.
- **Hvad evalueringen må:** Den anbefaler kun. Ejeren beslutter, om vinderen bliver standard. Rollback-teksten i specifikationen gælder ellers.
- **Forventning:** Med 6 pr. variant er kun store forskelle synlige. Et “ingen forskel” er et gyldigt og nyttigt resultat.

## Hvad piloten kræver af ejeren

- Footage og udgiverpolitik for hvert spil (`content/PUBLISHER_POLICIES.json`).
- MobyGames-research pr. spil (manuel inspektion, ingen scraping).
- Godkendelse af hver video.
- Beslutning om publicering. `PUBLISH_ENABLED` er fra. TikTok Direct Post kræver review og samtykke, og Meta kræver App Review for fuld adgang.
