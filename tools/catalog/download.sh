#!/bin/sh
# Download all sources into <catalog>/downloads and unpack them.
# Usage: sh scripts/download.sh <catalog_dir>
# Uses curl's default User-Agent; sends no personal data.
set -e
C="$1"; D="$C/downloads"; S="$(dirname "$0")"
mkdir -p "$D/rb" "$D/web" "$D/ldraw"
for f in colors parts elements part_relationships; do
  curl -sSfL -o "$D/$f.csv.gz" "https://cdn.rebrickable.com/media/downloads/$f.csv.gz"
  gunzip -c "$D/$f.csv.gz" > "$D/rb/$f.csv"
done
curl -sSfL -o "$D/complete.zip" https://library.ldraw.org/library/updates/complete.zip
python3 -I "$S/unzip.py" "$D/complete.zip" "$D/ldraw"
curl -sSfL -o "$D/web/bl_colors.html" "https://www.bricklink.com/catalogColors.asp"
curl -sSfL -o "$D/web/setdb_colors.html" "https://www.merlinsbricks.com/colors/"
# BrickLink catalog pages for every candidate number (LDraw stem, stripped stem,
# Rebrickable id, LDraw !KEYWORDS BrickLink id)
sh "$S/fetch_bricklink_parts.sh" "$D/web/bl_parts" \
  3005 3004 3622 3010 3009 3008 3003 3002 3001 2456 3007 3024 3023 3023b 3623 3710 3666 3460 \
  3022 3021 3020 3795 3034 3070b 3070 3069b 3069 63864 2431 6636 4162 3068b 3068 26603 87079 \
  3040 3040b 3039 54200 85984 3665 3665b 4286 11477 4073 6141 98138 3062b 3062 3941 6143 59900 \
  4589 4589b 4740 87087 4733 2412b 2412 60897 4085d 15573 14769 85861 3794b
