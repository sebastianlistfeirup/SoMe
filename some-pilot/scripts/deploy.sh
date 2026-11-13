#!/usr/bin/env bash
# Production deploy with an immutable image tag, a verified backup before
# migration and an automatic rollback when the post-deploy health gate fails.
#
#   ./scripts/deploy.sh             build, test, back up, migrate, start, verify
#   ./scripts/rollback.sh           start the previously deployed image again
#
# Migrations are additive (new tables/columns), so the previous image keeps
# working on a migrated database. If a migration ever is destructive, restore
# the pre-migration backup printed below instead of rolling back the image.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(sudo docker compose -f compose.yaml -f compose.production.yaml)
STATE_DIR="${DEPLOY_STATE_DIR:-/opt/some/deploy-state}"
KEEP_IMAGES="${KEEP_IMAGES:-5}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-120}"

sudo mkdir -p "$STATE_DIR"
TAG="$(git rev-parse --short=12 HEAD)"
PREVIOUS="$(sudo cat "$STATE_DIR/current_tag" 2>/dev/null || echo local)"
export IMAGE_TAG="$TAG"

log() { printf '{"at":"%s","event":"deploy","step":"%s","tag":"%s"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$TAG"; }

health_gate() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT))
  while (( SECONDS < deadline )); do
    local states
    states="$("${COMPOSE[@]}" ps --format '{{.Service}} {{.Status}}' 2>/dev/null || true)"
    if grep -q '^web .*(healthy)' <<<"$states" && grep -q '^worker .*(healthy)' <<<"$states" \
       && curl -fsS http://127.0.0.1:8000/healthz | grep -q '"status":"ok"'; then
      return 0
    fi
    sleep 5
  done
  return 1
}

log build
"${COMPOSE[@]}" build
log test
"${COMPOSE[@]}" run --rm --no-deps web pytest -q
log backup_before_migration
"${COMPOSE[@]}" run --rm --no-deps worker python -m app.cli backup --verify
log migrate
"${COMPOSE[@]}" run --rm web python -m app.cli migrate
log doctor
"${COMPOSE[@]}" run --rm web python -m app.cli doctor
log start
"${COMPOSE[@]}" up -d

if health_gate; then
  echo "$PREVIOUS" | sudo tee "$STATE_DIR/previous_tag" >/dev/null
  echo "$TAG" | sudo tee "$STATE_DIR/current_tag" >/dev/null
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TAG" | sudo tee -a "$STATE_DIR/history" >/dev/null
  log healthy
  # Keep the newest images so a rollback never needs a rebuild.
  sudo docker image ls some-pilot --format '{{.Tag}}' | grep -v -e '^local$' -e "^$TAG$" -e "^$PREVIOUS$" \
    | tail -n +"$KEEP_IMAGES" | xargs -r -I{} sudo docker image rm "some-pilot:{}" >/dev/null 2>&1 || true
  "${COMPOSE[@]}" ps
  exit 0
fi

log health_gate_failed_rolling_back
if [[ "$PREVIOUS" == "$TAG" ]] || ! sudo docker image inspect "some-pilot:$PREVIOUS" >/dev/null 2>&1; then
  log no_previous_image_manual_action_required
  exit 1
fi
IMAGE_TAG="$PREVIOUS" "${COMPOSE[@]}" up -d
if IMAGE_TAG="$PREVIOUS" health_gate; then
  log rolled_back_to_previous
else
  log rollback_unhealthy_manual_action_required
fi
exit 1
