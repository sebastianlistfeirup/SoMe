# Ingen omgåelse af botkontrol og ingen opfundne research-data

Status: gældende · Dato: 2026-11-13

## Kontekst
MobyGames viser Cloudflare-botkontrol. Score, trivia og platforme mangler ofte.

## Beslutning
Der bygges ingen scraper, der omgår botkontrol. Score og trivia kræver en værdi eller en eksplicit ikke-fundet-note. Den forudfyldte pakke indeholder ingen fakta, kun krav som blockers.

## Håndhæves af
- `tests/test_game_research.py::test_mobygames_score_and_trivia_require_values_or_explicit_not_found_notes`
- `tests/test_game_research.py::test_only_specific_mobygames_game_entries_are_accepted`
- `tests/test_project_workflow.py::test_prefilled_packet_is_schema_valid_and_contains_no_facts`
