#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "Usage: $0 BACKUP_FILE EMPTY_RESTORE_DIRECTORY" >&2
  exit 2
fi
cd "$(dirname "$0")/.."
sudo docker compose run --rm -v "$1:/restore-input:ro" -v "$2:/restore-target" web python -m app.cli restore --input /restore-input --target /restore-target
