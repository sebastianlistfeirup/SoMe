# AI-grafikker — Pixel & Parameters

Alt findes i 16:9 (YouTube, 1920×1080) og 9:16 (Shorts/Reels/TikTok, 1080×1920).

## 1. Hardware: åben mini-PC, bærbar og desktop (`hardware/`)

Fotorealistiske 3D-renders fra Blender/Cycles. Det er modeller af typisk hardware, ikke fotos af et bestemt produkt. Hver maskine ligger i `hardware/<mini_pc|laptop|desktop>/<16x9|9x16>/`:

| Fil | Brug |
|---|---|
| `clean.png` | Ren render uden effekter. Basis for egne animationer. |
| `highlight-ram.png` / `-cpu` / `-ssd` | Én komponent fremhævet. Resten er dæmpet, og der er cyan glød plus en navnelabel (RAM, CPU eller SSD). |
| `highlight-all.png` | Alle tre er nummereret: 1 RAM, 2 CPU, 3 SSD. |
| `glow-<del>.png` | Kun gløden, gennemsigtig PNG. Læg den over `clean.png` i editoren og fade den ind. |
| `matte-<del>.png` | Hvid-på-sort maske til tracking, zoom eller egne effekter. |

**Videoforslag:** Start på `clean.png`, fade `glow-ram.png` ind og hold lidt. Skift til `glow-cpu`, så `glow-ssd`. Slut på `highlight-all.png`.

## 2. Kort: navne, logoer og tal (`cards/`)

Kanalen er på engelsk. Kortene har ingen forklarende tekst, så titler og forklaringer lægges på i videoredigeringen.

- **`models-lineup-*`:** Frontier-modeller med logo og navn. Data ligger i `content/AI_MODELS_LINEUP.json`.
- **`ratings-models-*`:** Top 10 modeller efter Artificial Analysis Intelligence Index, aflæst 2026-11-15.
- **`ratings-labs-*`:** Hvert laboratoriums bedste model på samme indeks.
  - Begge rating-grafikker findes også som `-transparent.png` til animation.
  - Data ligger i `content/AI_RATINGS.json`.
  - Kildelinjen nederst kan slås fra med `"show_source": false`.
- **`checklist-local-ai-*`:** RAM 32 GB+, CPU NPU / iGPU og SSD NVMe · 1 TB+, nummereret på mini-PC'en.

**Logoer:** Logoerne ligger i `assets/brand/ai-logos/` og er hentet fra Wikimedia Commons. Kilder og licenser står i README'en der. Hvert billede leveres som sin egen fil, aldrig som en samling.

**Opdatér tallene før publicering.** Ret JSON-filerne og kør scriptet igen.

## 3. Baggrunde uden tekst (`backdrops/`)

Filmiske baggrunde med plads til titler. De passer til forskellige AI-opslag:

| Fil | Motiv | Passer til |
|---|---|---|
| `ai_core-*` | Glødende AI-chip under glas, svævende pixel-kuber og bokeh | Nye modeller · "hvad er AI" · lokal AI · hardware |
| `datacenter-*` | Serverrum med LED-rækker og tåge | Cloud mod lokal · træning · strøm og pris · store lanceringer |
| `glass_panels-*` | Række af frostede glaspaneler med glødende kanter | Sammenligninger · værktøjsoversigter · lister · dueller |

## Genskab eller ret

Blender 5.2 skal være installeret. Kør fra `some-pilot/`:

```bash
bash scripts/blender/render_all.sh
python scripts/blender/compose_hardware.py
python scripts/blender/compose_ai_cards.py
```

- `render_all.sh` laver hardware-renders og masker. Det tager ca. 4 min. på RTX 5090.
- `compose_hardware.py` laver highlights, glød og mattes.
- `compose_ai_cards.py` laver kortene.
- Baggrunde laves med: `blender -b -P scripts/blender/scene_ai_backdrops.py -- --scene <ai_core|datacenter|glass_panels> --format <16x9|9x16> --out <mappe>`.
- Nye modeller i line-up'en: ret `content/AI_MODELS_LINEUP.json` og kør `compose_ai_cards.py` igen.

## Ældre procedurale grafikker (v1)

`01-…` til `05-…` er de første 2D-grafikker fra `scripts/render_ai_graphics.py`. De kan stadig bruges som simple baggrunde.

## Regler for brug

- Alt her er **grafik, ikke rigtige medier**. Det tæller i budgettet for grafik på højst 20 % af en video (`kind: "graphic"`, `source_type: "synthetic"`).
- **I 9:16:** Hold vigtige elementer fri af platformens knapper i højre side og nederste femtedel. Kortene respekterer det allerede.
- Alt er lavet af kanalen selv med kode og 3D. Der er ingen stock-materiale, ingen AI-billedgenerering og ingen firmalogoer.
