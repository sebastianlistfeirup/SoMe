# SoMe-markedsundersøgelse — 8. november 2026

## Konklusion

**Foreløbig hovedniche:** engelsksproget købsvejledning inden for pc-hardware og håndholdt gaming.
**Reserve:** engelsksprogede gaming-explainers og indstillingsguides.
**Platforme:** YouTube først, Instagram som nummer to. Manuel eksport er standard, indtil ejerens OAuth og privat upload er verificeret.

Anbefalingen har **middel/foreløbig sikkerhed**, ikke statistisk sikkerhed. Den bygger på uafhængige signaler fra Steams officielle aktuelle spilletal, nyere hardwareanmeldelser, søgeresultater og danske detailpriser. Der mangler officielle YouTube API-data og en Google Trends-eksport. Ingen indtjening eller performance loves.

## Datagrundlag og afgrænsning

Research blev udført 2026-11-08 ca. 09:37–09:41 UTC. De seneste 7 og 30 dage blev prioriteret; ældre resultater op til og ældre end 90 dage bruges kun som baggrund. Der er 43 observationer i `research.json` og samme kerneobservationer i `research.csv`.

- Steam-tal er én officiel øjebliksmåling, ikke en tidsserie.
- YouTube-visninger er afrundede søgeresultat-snippets, ikke API-data. Kanalstørrelse og præcise publiceringstidspunkter er ukendte.
- Google AI-oversigter er ikke brugt som fakta. Kun synlige webresultater og officielle sider indgår.
- Der er ingen Google Trends-eksport og dermed ingen hævdede søgetal.
- Meta/TikTok-trendværktøjer og YouTube API kræver senere konto-/nøgleadgang.
- Udvalgene er små og ikke tilfældige. Svage opslag er medtaget, men resultaterne er ikke repræsentative.
- Ukendte værdier er `NULL`/tomme. Visninger pr. time er ikke beregnet.

## Nichesammenligning

Scoreformel: `0,35*demand + 0,25*momentum + 0,20*monetization + 0,10*opportunity + 0,10*production_feasibility`. Delscorerne er dokumenteret redaktionelle 0–100-vurderinger inden for denne lille pilot, ikke normaliserede markeds målinger. Rettigheds- og sikkerhedsfilter sker før konkret emneproduktion; en høj niche-score er ikke en licens.

| Niche | Sprog | Demand | Momentum | Monetisering | Mulighed | Produktion | Prioritet | Usikkerhed |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Gaming | EN | 95 | 92 | 55 | 65 | 60 | 79,75 | Middel |
| PC-hardware | EN | 75 | 88 | 80 | 70 | 75 | 78,75 | Middel |
| Håndholdte | EN | 72 | 65 | 85 | 78 | 82 | 74,45 | Middel |
| Indendørs have | EN | 60 | 60 | 65 | 70 | 90 | 65,00 | Lav |
| Fodbold | DA | 85 | 90 | 30 | 35 | 25 | 64,25 | Lav |
| Gaming | DA | 65 | 78 | 40 | 55 | 60 | 61,75 | Lav |
| Kaffe | EN | 55 | 45 | 80 | 65 | 85 | 61,50 | Lav |
| Indendørs have | DA | 50 | 65 | 55 | 70 | 90 | 60,75 | Lav |
| Dokumentarer | EN | 70 | 82 | 35 | 40 | 30 | 59,00 | Lav |
| Håndholdte | DA | 50 | 50 | 70 | 70 | 75 | 58,50 | Lav |
| Kaffe | DA | 45 | 40 | 70 | 60 | 85 | 54,25 | Lav |
| PC-hardware | DA | 45 | 55 | 60 | 55 | 70 | 54,00 | Lav |
| Dokumentarer | DA | 60 | 75 | 30 | 45 | 35 | 53,75 | Lav |
| Badminton | DA | 55 | 80 | 25 | 55 | 30 | 52,75 | Lav |

### Hvad dataene faktisk viser

- **Gaming:** Counter-Strike 2, Dota 2 og PUBG havde høj aktuel spilleraktivitet; Phantom Blade Zero viste et stærkt nyt signal. Udgivelser og patches giver løbende emner. Konkurrencen og gameplay-/musikrettigheder er dog væsentlige.
- **PC-hardware:** RTX Spark-anmeldelser og købsadvarsler fra flere kanaler i de seneste uger viser aktuel informationsinteresse. Både svage og stærkere resultater findes. Specifikationer og benchmarkpåstande skal genverificeres hos producent og uafhængige tests.
- **Håndholdte:** Evergreen købsguides har historisk kunnet få mange visninger, mens flere nyere generiske top-5-videoer har meget få. Muligheden er derfor konkrete beslutningsguides, ikke endnu en generel liste. Dansk detailtilgængelighed dokumenterer produkter og priser, ikke efterspørgsel.
- **Fodbold/badminton:** Aktuelle turneringer og landslagsnyheder giver momentum, men rettigheder til udsendelser, billeder og klip gør billig original produktion vanskelig. Kun egne grafikker og kildebelagt analyse bør overvejes.
- **Dokumentarer:** Nye trailers kan få opmærksomhed, men trailerens performance kan ikke overføres til analysevideoer. Klip, plakater, musik og person-/mindreårigeforhold kræver streng kontrol.
- **Kaffe:** Tydelig købsintention og nemme egne optagelser, men de observerede nyere generiske lister havde lave visninger. Kræver egne produkter eller dokumenterede stills for at være troværdig.
- **Indendørs have:** Sikker, sæsonaktuel og billig at producere med egne planter. Et muligt senere eksperiment, men ikke ejerens primære interesse og med svagt aktuelt datagrundlag.

## Ti emne-/formatmuligheder

1. **“Steam Deck OLED eller ROG Xbox Ally: vælg ud fra dine tre vigtigste spil”** — egne beslutningsgrafikker; officielle specifikationer; affiliate først når program og links er godkendt.
2. **“RTX Spark til gaming: hvem bør vente?”** — egen animation over kompatibilitet og pris; producentkilder plus uafhængige tests; ingen egne benchmarks uden måling.
3. **“Fem Steam-spil med stor aktuel aktivitet — og hvad nybegyndere bør vide”** — Steam Chart-snapshot og egne forklaringer; gameplay kun efter udgiverregeltjek.
4. **“Handheld til 45 minutter ad gangen: batteri, vægt og UI”** — egen scoregrafik; målte data kun med kilde.
5. **“Windows-handheld eller SteamOS: en 60-sekunders beslutningsmodel”** — egne ikoner og kompatibilitetsflow; konkrete spil verificeres samme dag.
6. **“Phantom Blade Zero: hvorfor den er højt på Steam lige nu”** — dateret chart og offentlige producentfakta; ingen kopierede trailere.
7. **“GPU-prisguide: fem spørgsmål før et køb”** — daterede prislinks og egen grafik; ingen prisgaranti.
8. **“Sådan læser du et Steam Chart uden at overfortolke det”** — egen skærmgrafik/metodedemo; stærkt tillidssignal.
9. **“Tre handheld-tilbehør, der løser konkrete problemer”** — egne produktfotos eller tilladte stills; reklamemarkering og faktisk affiliateadgang kræves.
10. **“Ugens hardwarenyhed: påstand, kilde, betydning”** — fast kildekortformat med ét produkt og tydelig usikkerhed.

## Første ti videoidéer i produktionsrækkefølge

1. Steam Deck OLED vs. ROG Xbox Ally: Which one fits your games?
2. SteamOS vs. Windows handhelds in 60 seconds.
3. Don’t buy a handheld before checking these three game-compatibility facts.
4. RTX Spark: why gamers and AI buyers need different advice.
5. Five questions to ask before paying for a new GPU.
6. What Steam’s current most-played chart does—and does not—tell you.
7. Phantom Blade Zero’s current Steam signal, explained without hype.
8. Handheld battery claims: how to compare reviews without inventing numbers.
9. The best handheld is different for travel, couch and desk play.
10. This week’s PC-hardware claim check: source, evidence, buyer impact.

## Produktions- og indtægtsvilkår

Start med egne grafikker, egne skærmoptagelser og kildebelagte forklaringer. Ingen baggrundsmusik i piloten. Engelsk TTS skal godkendes på en 20-sekunders prøve. Priser, specifikationer og kompatibilitet genkontrolleres på produktionsdagen. Affiliateindtægt kræver et konkret, tilgængeligt program, korrekt reklamemarkering og faktiske salgsdata; platformmonetisering kræver separat kontoeligibilitet.

## Næste validering

Når ejerens konti er klar: hent op til 20 nyere YouTube-opslag pr. valgt niche via Data API fra flere skabere, gentag målinger for momentum, gem udvælgelseskriterier, importér Google Trends manuelt for DK/US og EN/DA, og genberegn scorene. Indtil da er dette en dokumenteret pilotbeslutning, ikke et rentabilitetsbevis.
