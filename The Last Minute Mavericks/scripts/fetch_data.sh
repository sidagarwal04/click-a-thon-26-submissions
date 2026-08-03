#!/usr/bin/env bash
# Fetch the organizer's SAMPLE dataset into a repo-relative ./data/ (gitignored).
# Run this once after cloning:  bash scripts/fetch_data.sh
# Everyone gets identical data at the SAME path (./data/) — no machine-specific absolute
# paths, and the 98 MB parquet never bloats git. All code reads ./data/.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p data

SRC="sidagarwal04/click-a-thon-2026/main/InMobi/data"
RAW="https://raw.githubusercontent.com/$SRC"          # parquet is a normal git blob here
MEDIA="https://media.githubusercontent.com/media/$SRC" # CSVs are Git LFS -> media endpoint

echo "Fetching sample data into ./data/ ..."
# 98 MB fact table (regular blob on raw)
if [ ! -f data/ad_events.parquet ]; then
  curl -fSL --retry 3 "$RAW/ad_events.parquet" -o data/ad_events.parquet
fi
# dimension CSVs (LFS -> media serves real content; raw would return a pointer stub)
for f in apps advertisers geo_device; do
  [ -f "data/$f.csv" ] || curl -fSL --retry 3 "$MEDIA/$f.csv" -o "data/$f.csv"
done

echo "--- verify ---"
sz=$(wc -c < data/ad_events.parquet)
printf 'ad_events.parquet: %d MB\n' "$((sz/1024/1024))"
if [ "$sz" -lt 90000000 ]; then
  echo "ERROR: parquet is $sz bytes — looks like a pointer stub, not the real file." >&2
  echo "       Delete data/ad_events.parquet and re-run, or check the source repo." >&2
  exit 1
fi
for f in apps advertisers geo_device; do
  printf '%s.csv: %s rows\n' "$f" "$(($(wc -l < "data/$f.csv") - 1))"
done
echo "OK — sample data ready in ./data/  (gitignored; load it into ClickHouse next)"
