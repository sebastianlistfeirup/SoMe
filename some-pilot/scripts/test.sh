#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose build
docker compose run --rm --no-deps web pytest -q
