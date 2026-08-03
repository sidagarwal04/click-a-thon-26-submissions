#!/usr/bin/env bash
# Build deck/checkpoint1/deck.pdf from deck/checkpoint1/deck.html via headless Chrome.
# Usage: deck/checkpoint1/build.sh   (from anywhere; no arguments)
# Requires: Google Chrome (macOS default path, or set CHROME=/path/to/chrome).
set -euo pipefail

cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

"$CHROME" --headless=new --disable-gpu \
  --no-pdf-header-footer \
  --print-to-pdf="$PWD/deck.pdf" \
  "file://$PWD/deck.html"

# Rules: PDF only, <= 15 slides, <= 20 MB. Verify all three.
pages=$(strings deck.pdf | grep -c '/Type /Page$' || true)
size=$(stat -f%z deck.pdf 2>/dev/null || stat -c%s deck.pdf)
echo "deck.pdf: ${pages} pages, ${size} bytes"
[ "$pages" -le 15 ] || { echo "FAIL: more than 15 pages"; exit 1; }
[ "$size" -le 20971520 ] || { echo "FAIL: over 20 MB"; exit 1; }
echo "OK: within the 15-slide / 20 MB limits"
