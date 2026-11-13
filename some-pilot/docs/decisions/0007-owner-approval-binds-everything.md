# Ejergodkendelse binder alt, og publicering er slået fra som standard

Status: gældende · Dato: 2026-11-12

## Kontekst
Systemet kan publicere automatisk, men kun det præcise, ejeren har set.

## Beslutning
Godkendelsen hasher video, thumbnail, tekst, links, destinationer, konti, synlighed, tidspunkt og (fra digest v2) teksten pr. platform og AI-mærket. Enhver ændring kræver ny godkendelse. `DRY_RUN`, `PUBLISH_ENABLED` og nødstop blokerer alle ruter.

## Håndhæves af
- `tests/test_policy_and_approval.py::test_owner_approval_and_hash_invalidation`
- `tests/test_policy_and_approval.py::test_global_publish_flag_and_pause_block_every_route`
- `tests/test_variants_labels_voice.py::test_v2_digest_binds_variant_text_and_ai_label`
