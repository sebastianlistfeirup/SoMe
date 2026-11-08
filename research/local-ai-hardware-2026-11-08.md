# Maskiner til lokal AI — research 8. november 2026

## Kort anbefaling

- **Gaming + hurtig AI på mindre modeller:** en selvbygget pc med RTX 5090, hvis 32 GB VRAM rækker. Det er den mest relevante kombination til kanalens gaming/hardware-indhold, men ikke et universalvalg til 70B-modeller på GPU'en.
- **Største dokumenterede modelkapacitet i en kompakt Windows/Linux-pc:** Framework Desktop med Ryzen AI Max+ PRO 495 og 192 GB. Den danske pris og forudbestillingstiden gør den til et specialkøb, ikke et impulskøb.
- **NVIDIA-udvikling med stor delt hukommelse:** DGX Spark 128 GB. NVIDIA dokumenterer inferens op til 200B-parametre, men en aktuel dansk totalpris og en reel modeltest skal indhentes før køb.
- **Apple/kreativ arbejdsgang og stor samlet hukommelse:** Mac Studio M5 Max 128 GB eller M5 Ultra 256/512 GB. Ikke mit primære valg til en gaming-kanal, og CUDA-specifikke workflows skal erstattes eller testes særskilt.

## Kandidater og dokumenterede data

| Maskine | CPU/GPU/NPU og hukommelse | Realistisk modelstørrelse | Strøm | Pris og tilgængelighed |
|---|---|---|---|---|
| **Framework Desktop, PRO 495 / 192 GB** | 16 Zen 5-kerner/32 tråde, 40 compute units, 192 GB LPDDR5X-8533, 256-bit bus | Framework angiver **300B-class ved 4-bit**. Produktets modeltabel viser bl.a. DeepSeek V4.1 Flash Q2 med 163 GB hukommelsesforbrug. Kvantisering, kontekst og runtime ændrer resultatet. | Aktuelt vægforbrug ikke dokumenteret i den læste produkttekst; skal måles ved stikkontakten. | **59.739 kr.** DIY med 192 GB, uden SSD og strømkabel. Forudbestilling; siden viste batch 3 med afsendelse i december. |
| **NVIDIA DGX Spark, 128 GB** | GB10 Grace Blackwell, op til 20 CPU-kerner, 128 GB samlet hukommelse, op til 1 petaFLOP FP4 | NVIDIA angiver inferens op til **200B-parametre** og finjustering op til 70B. 64 GB-varianten er kun op til 100B ifølge NVIDIA. | Strømforbrug ved konkret workload er ikke målt; PSU-/datasheetværdi må ikke fremstilles som faktisk forbrug. | Ingen verificeret dansk pris i den officielle side læst her. Kræv aktuel pris inkl. moms, SSD og levering før sammenligning. |
| **Desktop med RTX 5090, 32 GB** | Blackwell GPU, 32 GB GDDR7, 1.792 GB/s; CPU/NPU afhænger af resten af bygget | God kandidat til 7B–32B-klassen med passende kvantisering. 32B Q4 er ca. 16 GB rå vægte før runtime/kontekst. 70B Q4 er ca. 35 GB rå vægte og passer derfor **ikke** alene i 32 GB VRAM. Dette er kapacitetsregnestykker, ikke benchmark. | 575 W TGP for GPU'en; det er ikke hele pc'ens faktiske vægforbrug. | NVIDIA viser **fra $1.999 for selve GPU'en**. Dansk færdigbygget pris skal udregnes med CPU, RAM, SSD, PSU, kabinet, køling og moms. |
| **Mac Studio M5 Max, 128 GB** | 18-core CPU, op til 40-core GPU, 16-core Neural Engine, 128 GB samlet hukommelse og 614 GB/s båndbredde i topkonfigurationen | 70B Q4 er ca. 35 GB rå vægte; 128 GB giver plads til større modeller/kontekst, men konkret model/runtime skal testes. Ingen maksimal parameterpåstand fra Apple bruges her. | Apple oplyser maks. **480 W** for Mac Studio-serien; ikke et målt gennemsnit. | M5 Max starter på **21.999 kr.**, men det er ikke prisen på 128 GB-versionen. Konkret konfigurationspris skal indhentes. |
| **Mac Studio M5 Ultra, 256/512 GB** | Op til 36-core CPU, 80-core GPU, 32-core Neural Engine, op til 512 GB samlet hukommelse, 1,2 TB/s | Meget stor hukommelseskapacitet til kvantiserede modeller. Ingen påstand om hastighed eller maksimalt antal parametre uden modeltest. | Maks. **480 W** ifølge Apples specifikationsside; ikke et målt gennemsnit. | M5 Ultra starter på **49.999 kr.** med 96 GB; 256/512 GB koster mere og skal prissættes konkret. |

## Hvad “Q4” betyder

4-bit kvantisering bruger omtrent 0,5 byte pr. parameter før metadata, runtime og kontekst. Et grovt kapacitetstjek er `parametre × bit / 8`, men den samlede hukommelse er ikke det samme som GPU-VRAM, og hele hukommelsen kan ikke altid allokeres til modellen. Kontekstlængde og runtime kan ændre både plads og hastighed væsentligt.

## Tokens/sekund og benchmarks

Der er **ikke publiceret et samlet tokens/sekund-tal her**. De læste produktsider dokumenterer ikke et ensartet, uafhængigt sammenligningsgrundlag for samme model, kvantisering, kontekst, batch og runtime. Framework beskriver sin referencemetode som 2.048 tokens kontekst og batch 1, men de læste tabeldata gav ikke et komplet sammenligneligt tal for alle fire maskiner.

Før en købsvideo eller “bedste maskine”-påstand skal samme test køres lokalt på hver maskine:

1. Samme model- og kvantiseringsfil, runtimeversion og prompt.
2. Kontekst 2.048 og 8.192 tokens, batch 1, minimum fem kørsler efter opvarmning.
3. Time-to-first-token, generation tokens/sekund, anvendt VRAM/RAM og vægforbrug.
4. En mindre model, en 32B-model og den største model alle kandidater kan køre uden CPU-offload.
5. Pris inkl. moms og nødvendige dele, støj, temperatur samt fejl eller afbrudte kørsler.

## Kilder læst 2026-11-08

- Framework produkt og modeltabel: https://frame.work/dk/en/desktop
- Framework dansk DIY-konfiguration: https://frame.work/dk/en/products/desktop-diy-amd-aimax400/configuration/new
- NVIDIA DGX Spark: https://www.nvidia.com/en-us/products/workstations/dgx-spark/
- NVIDIA RTX 5090: https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/
- Apple Mac Studio specifikationer: https://www.apple.com/dk/mac-studio/specs/
- Apple dansk prisside: https://www.apple.com/dk/shop/buy-mac/mac-studio

Dette er produktresearch, ikke et køb eller en uafhængig benchmark. Ingen maskine er bestilt.
