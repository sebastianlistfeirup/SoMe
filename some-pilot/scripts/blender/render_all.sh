#!/usr/bin/env bash
# Final renders: three machines x two formats, beauty + masks.
set -e
cd "$(dirname "$0")"
B="${BLENDER:-/c/Program Files/Blender Foundation/Blender 5.2/blender.exe}"
OUT="$(cd ../.. && pwd -W)/assets/graphics/ai/hardware/renders"
OUT="${1:-$OUT}"
SAMPLES="${SAMPLES:-192}"
python pp_textures.py >/dev/null
for scene in mini_pc laptop desktop; do
  for fmt in 16x9 9x16; do
    "$B" -b -P "scene_${scene}.py" -- --format "$fmt" --samples "$SAMPLES" --out "$OUT/$scene/$fmt" --masks 2>&1 | grep -E "Saved|Error|Traceback" || true
  done
done
