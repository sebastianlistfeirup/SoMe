# Local-AI claim and evidence ledger

Verified 2026-11-09. Manufacturer claims are identified as such. No cross-machine performance ranking is asserted without a like-for-like benchmark.

| Spoken/visual claim | Official evidence | Qualification shown in edit |
|---|---|---|
| RTX 5090 has 32 GB GDDR7 and 1,792 GB/s bandwidth | NVIDIA GeForce RTX 5090 specifications: https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/ | GPU specification, not whole-system performance |
| A 70B model at 4-bit starts around 35 GB | Capacity calculation: 70 billion × 4 bits ÷ 8 | Raw weights only; runtime, metadata, cache and context add memory |
| Framework Desktop PRO 495 offers 192 GB LPDDR5X and 273 GB/s | Framework Desktop specs: https://frame.work/desktop?slug=desktop-amd-aimax400&tab=specs | Soldered memory; exact runtime and quantization still matter |
| Framework says 300B-class at 4-bit | Framework Desktop machine-learning page: https://frame.work/desktop | Manufacturer claim; not an independent benchmark |
| Mac Studio M5 Max offers up to 128 GB / 614 GB/s; M5 Ultra up to 512 GB / 1.2 TB/s | Apple Mac Studio product/spec pages: https://www.apple.com/dk/mac-studio/ and https://www.apple.com/dk/mac-studio/specs/ | Apple does not provide a universal maximum-model claim; CUDA-only software needs an alternative |
| DGX Spark has up to 128 GB unified memory and NVIDIA rates it up to 200B parameters | NVIDIA DGX Spark: https://www.nvidia.com/en-us/products/workstations/dgx-spark/ | Manufacturer capacity claim; speed depends on model, quantization, context and runtime |
| “Best” depends on memory, bandwidth and software | Editorial decision framework derived from the constraints above | Price, noise, power, availability and actual benchmark remain buyer checks |

## Required on-screen source treatment

- Product/spec page source slug appears briefly during each document reveal.
- Manufacturer maximum-model claims carry a visible `manufacturer claim` label.
- `~35 GB raw weights` is always shown with `before overhead + context`.
- No “X times faster” language is permitted without the same model, quantization, context, batch and runtime.

