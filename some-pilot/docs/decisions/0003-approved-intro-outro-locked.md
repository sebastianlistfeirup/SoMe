# Den godkendte intro/outro er låst

Status: gældende · Dato: 2026-11-13

## Kontekst
Ejeren har visuelt godkendt P-kollisionen, `GAMING CULTURE × AI`, `FOLLOW FOR MORE` og den dæmpede lyd (version `original-collision-v1`).

## Beslutning
Alle nye videoer får intro og outro på 3,5 sek. fra `brand_ident.py`. Ændringer kræver ny visuel ejergodkendelse. Retention måles fra intro-slut (`hookRetention3s`), så identen ikke forveksles med hooket.

## Håndhæves af
- `tests/test_brand_ident.py::test_ident_metadata_tracks_approved_version_and_formats`
- `tests/test_brand_ident.py::test_approved_idents_concat_with_real_video_in_every_format`
- `tests/test_retention_experiments_governance.py::test_retention_summary_measures_hook_after_the_brand_intro_and_scene_drops`
