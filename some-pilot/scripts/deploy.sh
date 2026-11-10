#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
sudo docker compose -f compose.yaml -f compose.production.yaml build
sudo docker compose -f compose.yaml -f compose.production.yaml run --rm --no-deps web pytest -q
sudo docker compose -f compose.yaml -f compose.production.yaml run --rm web python -m app.cli migrate
sudo docker compose -f compose.yaml -f compose.production.yaml run --rm web python -m app.cli doctor
sudo docker compose -f compose.yaml -f compose.production.yaml up -d
sudo docker compose -f compose.yaml -f compose.production.yaml ps
