# Editorial-pakken ejer narrationen

Status: gældende · Dato: 2026-11-13

## Kontekst
Claude skrev tidligere narration ud fra view-tal. Gaten krævede bagefter, at pakkens receptionslinjer stod ordret i teksten, så realistiske omskrivninger blev altid blokeret.

## Beslutning
I live-produktion er narrationen pakkens segment-voiceovers ordret, og claims er pakkens claims. Claude skriver kun titel, caption og hook-klassifikation. Claim-reviewet læser pakkens inspicerede kilder.

## Håndhæves af
- `tests/test_packet_script.py::test_live_production_narration_is_locked_to_packet_voiceover`
- `tests/test_packet_script.py::test_packet_claims_become_script_claims_with_inspected_sources`
