#!/bin/sh
# usage: sh run_models.sh REPO OMR_DIR  (writes models.json here)
REPO=$1; OMR=$2
ARGS=""
for p in "$REPO"/projects/*/; do
  if grep -q '"kind": *"free"' "$p/project.json" 2>/dev/null; then
    s=$(basename "$p"); ARGS="$ARGS free:$s=$p/model.ldr"; fi
done
for f in "$REPO"/docs/research/2026-11-19-ai-as-the-builder/*/*.ldr; do
  d=$(basename $(dirname "$f")); b=$(basename "$f" .ldr); ARGS="$ARGS early:$d/$b=$f"; done
for d in "$OMR"/*/; do
  s=$(basename "$d")
  if [ -f "$d/$s-1.mpd" ]; then f="$d/$s-1.mpd"; elif [ "$s" = 31066 ]; then f="$d/31066-1_Shuttle.mpd"; else f=$(ls "$d"/*.mpd | head -1); fi
  ARGS="$ARGS omr:$s=$f"
done
uv run --project "$REPO" python -I models.py rb.pkl ldraw_index.json models.json $ARGS
