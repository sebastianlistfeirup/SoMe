# Footage-mappen er proveniens, ikke udgivelsesbevis

Status: gældende · Dato: 2026-11-13

## Kontekst
Capture Bridge sorterer optagelser i mapper som `PS5` og `Switch 2`. Det fristede til at antage, at spillet findes på den platform.

## Beslutning
Mappenavnet gemmes kun som `footage_platform`. Et opslag om en bestemt platform kræver frisk dokumentation for netop den platform. `cross-platform` kræver ingen bestemt konsol.

## Håndhæves af
- `tests/test_capture_bridge.py::test_platform_folder_is_provenance_not_game_identity_or_release_permission`
- `tests/test_game_research.py::test_ps5_footage_can_support_a_pc_post_when_pc_release_is_verified`
- `tests/test_game_research.py::test_switch_2_post_is_blocked_without_a_verified_switch_2_release`
- `tests/test_game_research.py::test_cross_platform_post_does_not_require_one_target_console`
