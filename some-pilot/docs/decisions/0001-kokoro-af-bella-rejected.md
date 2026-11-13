# Kokoro af_bella er afvist til produktion

Status: gældende · Dato: 2026-11-11 (ejerbeslutning), håndhævet 2026-11-13

## Kontekst
Ejeren har afvist Kokoro `af_bella` kreativt. Produktion bruger ElevenLabs: gaming `HfRP3cIhYLmeNHeTvkWK`, AI `8CjmkufHc22WbMZEBHbm`.

## Beslutning
Produktionens stemme er altid ElevenLabs. Kokoro må kun bruges i gamle tekniske demoer, og godkendelse afviser enhver video med Kokoro- eller espeak-stemme. HeyGen og synlige avatarer er fjernet.

## Håndhæves af
- `tests/test_variants_labels_voice.py::test_videos_with_rejected_kokoro_voice_can_never_be_approved`
- `tests/test_variants_labels_voice.py::test_rejected_tools_are_not_defaults`
- `tests/test_real_media.py::test_live_production_uses_ai_elevenlabs_voice_and_records_cost`
