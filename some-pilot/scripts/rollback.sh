#!/usr/bin/env bash
# Start the previously deployed image again (no rebuild, no migration).
#   ./scripts/rollback.sh            roll back to the previous tag
#   ./scripts/rollback.sh <tag>      roll back to a specific kept tag
set -euo pipefail
cd "$(dirname "$0")/.."

# sudo resets the environment; IMAGE_TAG must be passed through explicitly.
COMPOSE=(sudo --preserve-env=IMAGE_TAG docker compose -f compose.yaml -f compose.production.yaml)
STATE_DIR="${DEPLOY_STATE_DIR:-/opt/some/deploy-state}"
TARGET="${1:-$(sudo cat "$STATE_DIR/previous_tag" 2>/dev/null || true)}"
CURRENT="$(sudo cat "$STATE_DIR/current_tag" 2>/dev/null || echo unknown)"

if [[ -z "$TARGET" ]]; then
  echo "no previous tag recorded; pass a tag: ./scripts/rollback.sh <tag>" >&2
  exit 1
fi
if ! sudo docker image inspect "some-pilot:$TARGET" >/dev/null 2>&1; then
  echo "image some-pilot:$TARGET is not available on this server" >&2
  sudo docker image ls some-pilot
  exit 1
fi

IMAGE_TAG="$TARGET" "${COMPOSE[@]}" up -d
for _ in $(seq 1 24); do
  if curl -fsS http://127.0.0.1:8000/healthz | grep -q '"status":"ok"'; then
    echo "$CURRENT" | sudo tee "$STATE_DIR/previous_tag" >/dev/null
    echo "$TARGET" | sudo tee "$STATE_DIR/current_tag" >/dev/null
    printf '%s rollback %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TARGET" | sudo tee -a "$STATE_DIR/history" >/dev/null
    echo "rolled back to some-pilot:$TARGET"
    "${COMPOSE[@]}" ps
    exit 0
  fi
  sleep 5
done
echo "rollback target is not healthy; inspect: sudo docker compose -f compose.yaml -f compose.production.yaml logs" >&2
exit 1
