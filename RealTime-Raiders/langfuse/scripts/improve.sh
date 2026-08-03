#!/usr/bin/env bash
# improve.sh — one-time setup AND incremental improvement in one script.
#
#   bash langfuse/scripts/improve.sh
#
# First run: builds, seeds datasets, runs a baseline.
# Later runs: skips what is done, runs a new challenger, compares, publishes.
# Always safe to re-run.
#
# Flags:
#   --reseed      force dataset reseed (after loading new ClickHouse data)
#   --rebuild     force docker image rebuild
#   --no-judge    deterministic scores only (fast, free, no judge tokens)
#   --yes         skip the interactive gate prompt
#   --reset       wipe state and start over

set -euo pipefail
cd "$(dirname "$0")/.."   # always runs from langfuse/

GRN='\033[0;32m'; YLW='\033[0;33m'; RED='\033[0;31m'; BLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${GRN}==>${NC} $*"; }
warn()  { echo -e "${YLW}-->${NC} $*"; }
fail()  { echo -e "${RED}!!>${NC} $*"; exit 1; }
title() { echo -e "\n${BLD}$*${NC}"; }

# ── Flags ─────────────────────────────────────────────────────────────────────
RESEED=0; REBUILD=0; NOJUDGE=""; AUTOYES=0
for arg in "$@"; do
  case "$arg" in
    --reseed)   RESEED=1 ;;
    --rebuild)  REBUILD=1 ;;
    --no-judge) NOJUDGE="--no-judge" ;;
    --yes|-y)   AUTOYES=1 ;;
    --reset)    rm -f scripts/.pipeline_state; info "State wiped."; ;;
    *) fail "Unknown flag: $arg" ;;
  esac
done

# ── State ─────────────────────────────────────────────────────────────────────
STATE="scripts/.pipeline_state"
touch "$STATE"
get() { grep -m1 "^$1=" "$STATE" 2>/dev/null | cut -d= -f2- || true; }
put() {
  local k="$1" v="$2"
  if grep -q "^$k=" "$STATE" 2>/dev/null; then
    sed -i "s|^$k=.*|$k=$v|" "$STATE"
  else
    echo "$k=$v" >> "$STATE"
  fi
}

DC() { docker compose --profile ops run --rm prompt-ops "$@"; }

DATASETS=("liv-concurrency-evals" "liv-segment-evals")

# ── 1. Image ──────────────────────────────────────────────────────────────────
title "Step 1 — Docker image"
if [[ "$(get image_built)" != "yes" || $REBUILD -eq 1 ]]; then
  info "Building prompt-ops image..."
  docker compose --profile ops build prompt-ops || fail "Build failed."
  put image_built yes
else
  warn "Already built. Use --rebuild to force."
fi

# ── 2. Agent health ───────────────────────────────────────────────────────────
title "Step 2 — Agent health"
DC python -c "
import requests, sys
try:
    d = requests.get('http://lc-agent:3002/health', timeout=15).json()
    print(f\"  supervisor : {d.get('supervisor')}\")
    print(f\"  delegates  : {d.get('delegates')}\")
    print(f\"  tracing    : {d.get('langfuse_tracing')}\")
    if not d.get('langfuse_tracing'):
        print('  WARNING: Langfuse tracing is OFF — experiments will not be scored.')
        sys.exit(1)
except Exception as e:
    print(f'FAIL: {e}', file=sys.stderr); sys.exit(1)
" || fail "lc-agent unhealthy or tracing off. Try: docker compose up -d lc-agent"

# ── 3. Datasets ───────────────────────────────────────────────────────────────
title "Step 3 — Datasets"
if [[ "$(get datasets_seeded)" != "yes" || $RESEED -eq 1 ]]; then
  info "Seeding from ClickHouse ground truth..."
  DC python evals/seed_datasets.py || fail "Seeding failed."
  put datasets_seeded yes
else
  warn "Already seeded. Use --reseed after loading new data."
fi

# Verify the datasets actually have items before running anything against them.
info "Verifying dataset contents..."
DC python -c "
from langfuse_client import client
import sys
lf = client()
bad = False
for name in ['liv-concurrency-evals', 'liv-segment-evals', 'liv-traps']:
    try:
        n = len(lf.get_dataset(name).items)
        print(f'  {name:<26} {n} items')
        if n == 0: bad = True
    except Exception as e:
        print(f'  {name:<26} MISSING ({e})'); bad = True
sys.exit(1 if bad else 0)
" || fail "Datasets empty or missing. Re-run with --reseed."

# ── 4. Run names ──────────────────────────────────────────────────────────────
title "Step 4 — Run names"
BASELINE="$(get last_run_name)"
LAST_N="${BASELINE#v}"
if [[ -z "$BASELINE" ]]; then CHALLENGER="v1"; else CHALLENGER="v$((LAST_N + 1))"; fi
info "Baseline   : ${BASELINE:-<none — this is the first run>}"
info "Challenger : $CHALLENGER"

# ── 5. Trap gate ──────────────────────────────────────────────────────────────
title "Step 5 — Trap gate (deterministic, free)"
info "These are questions with no valid answer. Correct behaviour is refusal."
DC python experiments/run_experiment.py \
    --dataset liv-traps --run-name "traps-$CHALLENGER" --no-judge \
  || fail "Trap experiment failed. Check: docker compose logs lc-agent"

echo ""
warn "If rule_compliance is below 100%, the agent answered something it should"
warn "have refused. That is a correctness bug, not a style problem."
if [[ $AUTOYES -eq 0 ]]; then
  read -rp "$(echo -e "${BLD}Continue to the full evaluation? [y/N]${NC} ")" ok
  [[ "$ok" =~ ^[Yy]$ ]] || { warn "Stopped. Fix the prompt in Langfuse, then re-run."; exit 0; }
fi

# ── 6. Full evaluation ────────────────────────────────────────────────────────
title "Step 6 — Full evaluation ($CHALLENGER)"
for DS in "${DATASETS[@]}"; do
  info "Evaluating $DS ..."
  DC python experiments/run_experiment.py \
      --dataset "$DS" --run-name "$CHALLENGER" $NOJUDGE \
    || fail "Experiment failed on $DS. Nothing was compared or published.
    State is unchanged, so re-running this script retries $CHALLENGER."
done

# Confirm the runs landed in Langfuse before auto_improve tries to read them.
# This is the check that turns a confusing 404 deep inside auto_improve into a
# clear message here.
info "Confirming runs are visible in Langfuse..."
DC python -c "
from langfuse_client import client
import sys
lf = client()
missing = []
for ds in ['${DATASETS[0]}', '${DATASETS[1]}']:
    try:
        run = lf.get_dataset_run(dataset_name=ds, run_name='$CHALLENGER')
        print(f'  {ds:<26} {len(run.dataset_run_items)} items')
    except Exception:
        missing.append(ds)
if missing:
    print('  NOT FOUND: ' + ', '.join(missing), file=sys.stderr)
    sys.exit(1)
" || fail "Runs did not reach Langfuse. Usually LANGFUSE_* keys missing in the
    prompt-ops container, or lf.flush() never ran because the experiment crashed."

# ── 7. Compare and publish ────────────────────────────────────────────────────
title "Step 7 — Auto-improve"

if [[ -z "$BASELINE" ]]; then
  warn "First run — no baseline to compare against."
  warn "$CHALLENGER is now the baseline for the next cycle."
  put last_run_name "$CHALLENGER"
  put last_run_ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
else
  info "Comparing $BASELINE -> $CHALLENGER"
  echo ""

  # agent prompt : dataset it is evaluated against
  PAIRS=(
    "liv-concurrency-agent:liv-concurrency-evals"
    "liv-segment-agent:liv-segment-evals"
    "liv-capacity-agent:liv-concurrency-evals"
    "liv-router-agent:liv-concurrency-evals"
  )

  PUBLISHED=0
  for PAIR in "${PAIRS[@]}"; do
    PROMPT="${PAIR%%:*}"; DS="${PAIR##*:}"
    info "  $PROMPT  (on $DS)"
    # A single prompt failing to improve must not abort the others, so this
    # one call is deliberately allowed to fail.
    if OUT=$(DC python experiments/auto_improve.py \
               --prompt "$PROMPT" --dataset "$DS" \
               --baseline "$BASELINE" --challenger "$CHALLENGER" 2>&1); then
      echo "$OUT"
      grep -q "Published v" <<<"$OUT" && PUBLISHED=1
    else
      echo "$OUT"
      warn "  skipped $PROMPT (see above)"
    fi
    echo ""
  done

  # Advance the baseline only when something actually improved. Otherwise the
  # next challenger would be measured against a run that lost, quietly lowering
  # the bar every cycle.
  if [[ $PUBLISHED -eq 1 ]]; then
    info "New prompt version(s) published. Baseline advances to $CHALLENGER."
    put last_run_name "$CHALLENGER"
    put last_run_ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  else
    warn "Nothing beat the baseline. Baseline stays at $BASELINE."
    warn "Edit a prompt in the Langfuse UI, then re-run to try again."
  fi
fi

# ── 8. Summary ────────────────────────────────────────────────────────────────
title "Done"
echo ""
echo "  state file : langfuse/$STATE"
echo "  baseline   : $(get last_run_name)   ($(get last_run_ts))"
echo "  this run   : $CHALLENGER"
echo ""
echo "  Review the $CHALLENGER experiment in Langfuse. Any prompt published"
echo "  above is already live — lc-agent refetches within its cache TTL."
echo "  Run this script again for the next cycle."