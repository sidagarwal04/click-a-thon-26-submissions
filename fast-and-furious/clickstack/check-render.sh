#!/usr/bin/env bash
# check-render.sh — assert each dashboard actually RENDERS in the ClickStack UI.
#
#   ./clickstack/check-render.sh
#
# This exists because neither of the other two checks catches a UI-side failure.
# `check-tiles.sh` proves the SQL is valid, and the API's own
# POST /dashboards/validate proves the payload is well formed — and a dashboard can
# pass both while the UI renders it as an empty "Untitled" page with zero tiles.
# Measured: raw-SQL `pie` and `bar` tiles do exactly that, and they take the WHOLE
# dashboard down rather than the one tile.
#
# It drives the gstack browse daemon, so it needs a logged-in ClickStack session.
# Firefox keeps cookies in plain SQLite, so if that is where you are signed in:
#
#   python3 tools/ff-cookies.py clickhouse.cloud /private/tmp/ch-cookies.json
#   <browse> cookie-import /private/tmp/ch-cookies.json
#
# Otherwise use `<browse> handoff` and sign in by hand once; the session persists.
#
# A dashboard passes when its own name appears in the document title AND a probe
# string unique to one of its tiles appears in the body. The title alone is not
# enough: a failed dashboard still renders a page, it just calls it "Dashboard".
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
B="${BROWSE_BIN:-$HOME/.claude/skills/gstack/browse/dist/browse}"
[[ -x "$B" ]] || { echo "check-render.sh: browse binary not found at $B" >&2; exit 2; }

host="${CLICKSTACK_HOST:-https://hyperdx.clickhouse.cloud}"

# name<TAB>probe — the probe is a tile name that appears nowhere else.
probes=$(cat <<'EOF'
SonyLIV — Live concurrency	Concurrent now
SonyLIV — Concurrency analytics (lagged)	Average concurrency
SonyLIV — Pipeline & query observability	Ingest lag
SonyLIV — Grouped viewers	Platform totals
SonyLIV — Benchmark answers	Peak by dimension value
SonyLIV — Viewer-drop alerts	Breaching slices, any dimension
EOF
)

dashboards="$("$here/csapi.sh" GET /dashboards)"
pass=0; fail=0

while IFS=$'\t' read -r name probe; do
  [[ -z "$name" ]] && continue
  id="$(printf '%s' "$dashboards" | python3 -c '
import json, sys
for d in json.load(sys.stdin).get("result", []):
    if d.get("name") == sys.argv[1]:
        print(d["id"]); break
' "$name")"
  if [[ -z "$id" ]]; then
    printf 'MISSING  %s\n' "$name"; fail=$((fail + 1)); continue
  fi

  "$B" goto "$host/dashboards/$id" >/dev/null 2>&1 || true
  # Settle. NOT `wait svg` -- the sidebar has SVG icons from the first paint, so
  # that returns instantly and the probe then reads an unmounted page, which makes
  # every dashboard look broken. --networkidle blocks until the SPA stops fetching
  # (or 15s), which is long enough for the tiles to mount. It reports a timeout on a
  # dashboard that polls forever; that is expected and ignored.
  "$B" wait --networkidle >/dev/null 2>&1 || true

  verdict="$("$B" js "JSON.stringify({t: document.title, p: document.body.innerText.indexOf($(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$probe")) >= 0})" 2>/dev/null | tail -1)"
  ok="$(printf '%s' "$verdict" | python3 -c '
import json, sys
try:
    v = json.loads(sys.stdin.read().strip())
except Exception:
    print("no"); raise SystemExit
name = sys.argv[1]
print("yes" if v.get("p") and name.split(" — ")[-1][:12] in v.get("t", "") else "no")
' "$name")"

  if [[ "$ok" == "yes" ]]; then
    printf 'RENDERS  %-46s %s\n' "$name" "$id"; pass=$((pass + 1))
  else
    printf 'BROKEN   %-46s %s   title=%s\n' "$name" "$id" "$verdict"; fail=$((fail + 1))
  fi
done <<< "$probes"

echo
echo "$pass render, $fail broken"
[[ "$fail" == "0" ]]
