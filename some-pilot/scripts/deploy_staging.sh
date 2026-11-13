#!/usr/bin/env bash
# Deploy the current checkout to staging (separate data, port 8001, publishing
# and paid jobs forced off). Run this before ./scripts/deploy.sh when a change
# touches migrations, the worker or the web flow.
set -euo pipefail
cd "$(dirname "$0")/.."

export IMAGE_TAG="$(git rev-parse --short=12 HEAD)"
export WEB_PORT=8001
COMPOSE=(sudo --preserve-env=IMAGE_TAG,WEB_PORT docker compose -p some-staging -f compose.yaml -f compose.staging.yaml)

if ! sudo test -f /opt/some/secrets/staging.env; then
  echo "create /opt/some/secrets/staging.env first (no publishing tokens; chmod 600)" >&2
  exit 1
fi
sudo mkdir -p /opt/some/staging-data
sudo chown 10001:10001 /opt/some/staging-data

"${COMPOSE[@]}" build
"${COMPOSE[@]}" run --rm --no-deps web pytest -q
"${COMPOSE[@]}" run --rm web python -m app.cli migrate
"${COMPOSE[@]}" run --rm web python -m app.cli doctor
"${COMPOSE[@]}" up -d
for _ in $(seq 1 24); do
  if curl -fsS http://127.0.0.1:8001/healthz | grep -q '"publish_enabled":false'; then
    echo "staging healthy at 127.0.0.1:8001 (tag $IMAGE_TAG)"
    "${COMPOSE[@]}" ps
    exit 0
  fi
  sleep 5
done
echo "staging did not become healthy" >&2
exit 1
