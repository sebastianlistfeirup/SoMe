# Mindst 80 % rigtige medier; AI tæller aldrig

Status: gældende · Dato: 2026-11-11

## Kontekst
Kanalen skal bygge på rigtig footage, ikke genererede billeder.

## Beslutning
Mindst 80 % af varigheden skal være rigtige videoklip eller rigtige billeder (målt pr. varighed). AI-genereret indhold kan ikke tælle som reelt.

## Håndhæves af
- `tests/test_real_media.py::test_duration_weighted_coverage_allows_exactly_eighty_percent`
- `tests/test_real_media.py::test_coverage_blocks_below_eighty_percent_and_plan_cannot_lower_limit`
