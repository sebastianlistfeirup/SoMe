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

## 4. Ti ekstra grafikker (`extras/` og `hardware/gpu/`)

Hver er sin egen fil i 16:9 og 9:16, med kun navne, logoer og tal.

| Fil | Motiv | Data |
|---|---|---|
| `extras/vram-tetris-*` | 3D: 8B og 32B passer ned i et 32 GB-kort, mens 70B rager langt op | Cirka Q4-størrelser af vægtene (4,9 / 19,9 / 42,5 GB), uden KV-cache |
| `hardware/gpu/<fmt>/` | 3D: grafikkortet skilt ad i bagplade, printplade og køler. GPU og VRAM fremhæves som de andre hardware-renders (`clean`, `highlight-gpu`, `highlight-vram`, `highlight-all`, `glow-*`, `matte-*`) | – |
| `extras/price-vs-score-*` | Score mod pris pr. opgave på logaritmisk akse, med logoer | Artificial Analysis |
| `extras/speed-*` | De 10 hurtigste efter tid pr. opgave, også som `-transparent` | Artificial Analysis |
| `extras/duel-*-vs-*` | Duel-kort med to logoer, navne, score og pixel-VS. Nye par tilføjes under `"duels"` | Artificial Analysis |
| `extras/context-books-*` | 3D: 128K, 1M og 10M tokens vist som 1, 8 og 78 bøger | Ca. 500 tokens pr. side og 256 sider pr. bog |
| `extras/agent-team-*` | 3D: Planner, Coder og Reviewer som glødende knuder med beskeder imellem | – |
| `extras/open-vs-closed-*` | 3D: åben og låst hængelås med de bedste modeller med åbne og lukkede vægte | Artificial Analysis |
| `extras/timeline-2026-*` | Udgivelsesmåned for hver model, august til november 2026 | Artificial Analysis |
| `extras/podium-top3-*` | 3D-podie med top 3 og deres score | Artificial Analysis |

Alle tal ligger i `content/AI_RATINGS.json` under `catalog`, `vram`, `context_books`, `timeline_models` og `duels`. Opdatér dem før publicering.

## 5. Ti grafikker mere (`extras/` og `hardware/handheld/`)

| Fil | Motiv | Data |
|---|---|---|
| `extras/thumbnails/thumb-*.png` | YouTube-thumbnails i 1280×720: én pr. model (stort logo), duellen og 11 emner (lokal AI, GPU, handheld, VRAM, kvantisering, kontekst, agenter, åben/lukket, lokal/cloud, retro, datacenter). Plads til titeltekst til venstre | – |
| `extras/nameplates/<model>-*.png` | Gennemsigtige navneskilte (lower thirds) med logo, modelnavn og laboratorium, ét pr. model | – |
| `extras/quant-ladder-*` | 3D: samme 32B-model i FP16, Q8, Q4 og Q2 | Filstørrelser fra Hugging Face (Qwen2.5 32B GGUF): 65,5 / 34,8 / 19,9 / 12,3 GB |
| `hardware/handheld/<fmt>/` | 3D: åben gaming-handheld med RAM, CPU og SSD fremhævet, i samme sæt filer som de andre maskiner | – |
| `extras/local-vs-cloud-*` | 3D: mini-PC på et skrivebord og serverrack, forbundet af en databue | – |
| `extras/cost-100-tasks-*` | Pris for 100 opgaver pr. model, også som `-transparent` | Artificial Analysis |
| `extras/token-conveyor-*` | 3D: tokens kører ind i en chip, og nye kommer ud. Uden tekst | – |
| `extras/retro-ai-*` | 3D: CRT-skærm med en pixel-AI-chip og en retrokonsol. Uden tekst | – |
| `extras/glitch-*` | Fejl-frame med glitch, røde revner og pixelstøj. Uden tekst | – |
| `extras/local-tokens-per-second-*` | Tokens pr. sekund pr. maskine, også som `-transparent` | llama.cpp-benchmarks (Llama 2 7B Q4_0) |

Logikken ligger i `scripts/blender/compose_ai_more.py`. Tallene ligger i `content/AI_RATINGS.json` under `quant`, `local_speed` og `cost100_models`.

## 6. Handhelds (`assets/graphics/handhelds/`)

De bedste handhelds på markedet lige nu. Point og specifikationer kommer fra Notebookcheck's egne tests (aflæst 2026-11-15). Billederne er producenternes officielle produktbilleder.

| Fil | Indhold |
|---|---|
| `lineup-*` | Oversigt over alle 11 modeller med produktbillede, producentlogo og navn |
| `specs-*` | Tech specs for alle modeller: chip, grafik, RAM, lager, skærm, batteri, vægt og pris |
| `ranking-*` | Rangeret efter Notebookcheck-point, også som `-transparent`. AYANEO NEXT 2 er ikke med, fordi Notebookcheck ikke har testet den |
| `<model>-*` | Én pr. model: handhelden til venstre og specs til højre (i 9:16 ovenover og nedenunder), med point |

AYANEO NEXT 2's specs kommer fra AYANEO selv (64 GB / 1 TB-udgaven til $2.699). Vægten er ikke oplyst officielt og står som "—". Data ligger i `content/HANDHELDS.json`. Produktbilleder og kilder ligger i `assets/brand/handhelds/`, og producentlogoer i `assets/brand/handheld-logos/`. Lav dem igen med `python scripts/blender/compose_handhelds.py`.

### Ti handheld-grafikker mere (`assets/graphics/handhelds/`)

Logikken ligger i `scripts/blender/compose_handhelds_more.py`, og data i `content/HANDHELDS.json`.

| Fil | Indhold | Data |
|---|---|---|
| `value-*` | Point for pengene: Notebookcheck-point mod listepris, med produktbilleder | Notebookcheck |
| `size-*` | Alle modeller side om side i rigtig indbyrdes bredde | Mål i mm fra Notebookcheck. NEXT 2: 341,7 mm |
| `chips-*` | Modellerne grupperet efter chip, med AMD- og Intel-logo | – |
| `battery-weight-*` | Batteri (Wh) og vægt (g) pr. model | NEXT 2's vægt er ca. 1,43 kg (Notebookcheck news) og står med "~" |
| `screens-*` | Skærmene i rigtig indbyrdes størrelse. OLED er koral, og IPS er cyan | – |
| `duel-<a>-vs-<b>-*` | Duel-kort med produktbilleder, pixel-VS og point. Nye par tilføjes under `"duels"` | Notebookcheck |
| `generations-*` | Forgænger → efterfølger med pointspring: Legion Go → Go 2, Ally X → X20 og Claw 8 AI+ → 8 EX AI+ | Notebookcheck |
| `fps-strange-brigade-*` og `fps-cyberpunk-2077-*` | Spil-fps ved 1080p Ultra, også som `-transparent`. Cyberpunk mangler Steam Deck og Legion Go, fordi Notebookcheck ikke har målt dem ved samme indstilling | Notebookcheck-spiltests |
| `local-ai-*` | Tokens pr. sekund pr. handheld-chip, også som `-transparent` | llama.cpp Vulkan (Llama 2 7B Q4_0), målt pr. chipfamilie |
| `thumbnails/thumb-*.png` | 1280×720 YouTube-thumbnails, én pr. model og én pr. duel, med plads til titel til venstre | – |
| `nameplates/<model>-*.png` | Gennemsigtige navneskilte med producentlogo | – |

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
- **3D-motiver til de ekstra grafikker:**
  - Render med `blender -b -P scripts/blender/scene_ai_props.py -- --scene <gpu|vram|books|agents|podium|locks> --format <16x9|9x16> --out <mappe>`.
  - `gpu` skal i `hardware/renders/gpu/<fmt>`. De andre skal i `renders3d/<scene>/<fmt>`.
  - Hver scene skriver også `anchors.json` med positionerne for labels.
  - `--anchors-only` opdaterer kun positionerne, uden at rendere igen.
- Derefter laves de ekstra grafikker med `python scripts/blender/compose_ai_extras.py`.
- Nye tal: ret `content/AI_RATINGS.json` og kør kun `compose_ai_extras.py` igen. 3D'en skal ikke renderes igen.

## Ældre procedurale grafikker (v1)

`01-…` til `05-…` er de første 2D-grafikker fra `scripts/render_ai_graphics.py`. De kan stadig bruges som simple baggrunde.

## Regler for brug

- Alt her er **grafik, ikke rigtige medier**. Det tæller i budgettet for grafik på højst 20 % af en video (`kind: "graphic"`, `source_type: "synthetic"`).
- **I 9:16:** Hold vigtige elementer fri af platformens knapper i højre side og nederste femtedel. Kortene respekterer det allerede.
- Alt er lavet af kanalen selv med kode og 3D. Der er ingen stock-materiale, ingen AI-billedgenerering og ingen firmalogoer.
