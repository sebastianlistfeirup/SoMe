# Læring er dæmpet, skygge-testet og kan rulles tilbage

Status: gældende · Dato: 2026-11-13

## Kontekst
Små organiske datamængder giver let falske mønstre.

## Beslutning
Signaler dæmpes med n/(n+5), begrænses til 0,75–1,25 og sammenlignes kun inden for platform, format og længde, korrigeret for kanalvækst. En ny model kører en uge i skygge, før den aktiveres. Ved to ugentlige fald i træk rulles den tilbage. Prompts bruger kun den aktive model.

## Håndhæves af
- `tests/test_learning_signals.py::test_views_only_matches_previous_damped_formula`
- `tests/test_learning_signals.py::test_platform_reach_differences_are_not_credited_to_hooks`
- `tests/test_learning_signals.py::test_growth_correction_removes_channel_growth_from_hook_comparison`
- `tests/test_retention_experiments_governance.py::test_candidate_runs_in_shadow_before_activation`
- `tests/test_retention_experiments_governance.py::test_two_consecutive_weekly_declines_roll_back`
- `tests/test_retention_experiments_governance.py::test_prompt_guidance_uses_only_the_active_model`
