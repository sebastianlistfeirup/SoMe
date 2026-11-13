# Eksperimenter ændrer én ting, og ejeren beslutter

Status: gældende · Dato: 2026-11-13

## Kontekst
Uden forhåndsregistrering kan resultater tilpasses bagefter.

## Beslutning
Eksperimenter forhåndsregistreres med hash (hypotese, én variabel, varianter, primær metrik, guardrails, stopregel, rollback). Tildeling er balanceret pr. historie og verificeres ved produktion. Evalueringen anbefaler kun; ejeren beslutter adoption.

## Håndhæves af
- `tests/test_retention_experiments_governance.py::test_registration_is_hashed_immutable_and_one_per_variable`
- `tests/test_retention_experiments_governance.py::test_assignment_is_balanced_stable_and_verified_at_production`
- `tests/test_retention_experiments_governance.py::test_evaluation_waits_for_samples_then_recommends_without_adopting`
