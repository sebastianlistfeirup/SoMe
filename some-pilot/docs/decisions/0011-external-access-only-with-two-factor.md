# Ekstern adgang til dashboardet kun med 2-faktor

Status: gældende · Dato: 2026-11-13

## Kontekst
Ejeren vil kunne bruge dashboardet fra andre steder end sin egen computer, fx godkende fra mobilen. Indtil nu har Caddy kun ladet fire IP-adresser nå dashboardet. Dashboardet kan publicere på ejerens konti, så et password alene er for lidt, når det er åbent for hele internettet.

## Beslutning
Dashboardet åbnes for alle IP-adresser først, når tre ting er på plads:

1. 2-faktor-login (TOTP) er deployet.
2. Ejeren har tilmeldt sin authenticator-app fra et godkendt netværk og gemt sine gendannelseskoder.
3. `REQUIRE_TOTP=true` er sat, så login kun med password afvises.

Hemmeligheden krypteres med en nøgle afledt af `APP_SECRET_KEY`. Brugte koder kan ikke genbruges, og gendannelseskoder virker én gang. Session-cookien er `Secure` og `SameSite=Lax`, så links fra notifikationer virker, og alle formularer kræver CSRF-token. Login-adressen "videre til" accepterer kun interne stier.

## Håndhæves af
- `tests/test_youtube_growth_security.py::test_totp_matches_rfc6238_vector_and_blocks_replay`
- `tests/test_youtube_growth_security.py::test_two_factor_enrolment_and_login_flow`
- `tests/test_youtube_growth_security.py::test_required_two_factor_blocks_unenrolled_login`
- `tests/test_youtube_growth_security.py::test_login_next_cannot_redirect_off_site`
