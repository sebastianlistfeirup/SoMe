# The best machines for local AI — master script

Voiceover: local Kokoro-82M `af_bella`; no on-screen avatar.

Target master runtime: approximately 90–100 seconds at natural speed.

## Exact spoken script (English)

If you are buying a machine for local AI, ignore the biggest TOPS number. Start with memory.

A four-bit model needs roughly half a byte per parameter before overhead and context. So a seventy-billion-parameter model starts around thirty-five gigabytes — too large to fit entirely inside the RTX 5090's thirty-two gigabytes of VRAM.

Three specs matter most. Usable accelerator memory decides what can load. Memory bandwidth strongly affects how quickly weights can move. And software decides whether your workflow runs at all: CUDA has the broadest support; Apple uses Metal and MLX; AMD depends heavily on your exact runtime.

For maximum CUDA speed when the model fits, build around an RTX 5090: thirty-two gigabytes of GDDR7 and 1.792 terabytes per second.

For the largest compact single-box capacity, Framework Desktop offers 192 gigabytes at 273 gigabytes per second. Framework claims 300-billion-class models at four-bit, but this configuration is Linux-focused and expensive.

For a quiet, turnkey workstation, Mac Studio scales from 128 gigabytes on M5 Max to 512 on M5 Ultra, with up to 1.2 terabytes per second.

For NVIDIA's integrated developer stack, DGX Spark has 128 gigabytes of unified memory; NVIDIA rates it for models up to 200 billion parameters.

The best machine is not the one with the largest TOPS badge. It is the one whose memory, bandwidth and software match the model you actually run.

## Editorial cut map

- TikTok: hook, memory calculation, three-spec framework, RTX 5090 versus Framework, final rule.
- Reels: hook, three-spec framework, all four category picks in compressed visual form, “save before you buy” close.
- YouTube: complete master script with sourced spec-page walkthroughs and explicit qualifications.
- ZOOM and SAFE: complete vertical master with product details protected by SAFE framing and dramatic number-led ZOOM beats.

