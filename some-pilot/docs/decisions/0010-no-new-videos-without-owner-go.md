# Ingen nye redaktionelle videoer uden ejerens go

Status: gældende · Dato: 2026-11-11

## Kontekst
Systemet kan producere fuldt automatisk, men ejeren styrer, hvornår rigtige videoer laves.

## Beslutning
Der produceres ingen nye redaktionelle videoer, før ejeren skriver “Nu må du begynde”. Produktion som job sættes i kø som demo, medmindre ejeren eksplicit vælger rigtig produktion. Eksisterende footage ændres ikke.

## Håndhæves af
- `tests/test_operations.py::test_operations_page_retry_and_produce_routes`
