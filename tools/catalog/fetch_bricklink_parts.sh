#!/bin/sh
# Fetch BrickLink catalog pages for candidate part numbers (cached, 3 s apart).
# Usage: fetch_bricklink_parts.sh <out_dir> <id> [<id> ...]
# Uses curl's default User-Agent; sends no personal data.
out="$1"; shift
mkdir -p "$out"
for p in "$@"; do
  f="$out/$p.html"
  [ -s "$f" ] && continue
  curl -sS -o "$f" -w "$p %{http_code} %{size_download}\n" "https://www.bricklink.com/v2/catalog/catalogitem.page?P=$p"
  sleep 3
done
