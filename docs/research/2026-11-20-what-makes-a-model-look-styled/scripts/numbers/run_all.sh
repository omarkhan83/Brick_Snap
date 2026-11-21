#!/bin/sh
# Reproduce the style-numbers study. usage: sh run_all.sh REPO RB_DIR LDRAW_ZIP OMR_DIR
# RB_DIR: Rebrickable catalogue downloads, unpacked (never commit them). Writes rb.pkl, ldraw_index.json,
# models.json and out/ in this folder.
set -e
REPO=$1; RB=$2; ZIP=$3; OMR=$4
PY="uv run --project $REPO python -I"
$PY load_rb.py "$RB" rb.pkl
$PY ldraw_index.py "$ZIP" ldraw_index.json
sh run_models.sh "$REPO" "$OMR"
$PY analyse.py rb.pkl ldraw_index.json models.json out > /dev/null
$PY score.py out > /dev/null
echo "tables in out/tables.md, out/score.md, out/tables/*.csv"
