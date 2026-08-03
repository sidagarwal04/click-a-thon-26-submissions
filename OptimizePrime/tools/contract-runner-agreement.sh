#!/usr/bin/env bash
# ============================================================================
# tools/contract-runner-agreement.sh — the two entry points must agree about
# what a valid file is.
#
#   tools/contract-runner-agreement.sh [fixture.csv ...]
#
# THE INVARIANT, in one line:
#
#     anything the contract gate PASSES, the real runner must ACCEPT.
#
# WHY THIS EXISTS. There are two ways a file enters this repo, and they used to
# disagree:
#
#   the contract gate   docs/RUNBOOK_UNSEEN.md §0 — a scratch database,
#                       tools/load.sh, then tools/validate-source-contract.sh.
#                       This is the PRE-FLIGHT: the thing you run first, on a
#                       day where the answer is due, to find out whether the
#                       file is what you think it is.
#
#   the real runner     tools/unseen-run.sh — the advertised one-command path
#                       that actually produces the submitted number.
#
# Codex validation 006 found two files that the gate passed and the runner then
# refused: a valid RFC-4180 CSV carrying a quoted embedded newline, and a valid
# file carrying a new filter column (which ADR 0024 exists to support, and which
# dataset_details.md:43 says in writing will happen). Both are reproduced in
# evidence/q37/before/ and fixed in evidence/q37/after/.
#
# A green pre-flight followed by a failed run is close to the worst sequence
# available on a day with one attempt. It burns the time the pre-flight was
# meant to save, and it teaches the operator that the check means nothing. That
# is strictly worse than having no pre-flight, because it converts "we do not
# know" into false confidence.
#
# WHAT THIS ASSERTS, and what it deliberately does not:
#
#   VIOLATION      gate ACCEPTED and the runner REFUSED THE FILE. Exit 1.
#   fine           both accept.
#   fine           both refuse (the file is genuinely bad; they agree on that).
#   fine           gate refused, runner accepted. The gate is allowed to be the
#                  stricter of the two — stopping early costs nothing but time.
#                  The dangerous direction is the other one, and only that one
#                  fails this script.
#
# A runner failure LATER than the load — the reconcile gate disagreeing, say —
# is NOT a file-acceptance question and is reported as RAN/FAILED rather than
# counted as a violation. The failing phase is read out of the runner's own
# banner to tell the two apart, so this script cannot manufacture a violation
# out of an unrelated model bug.
#
# ISOLATION. Two scratch databases, named below, dropped and recreated on every
# run. Never `sonyliv`: this script refuses to name it at all.
#
# COST. Roughly 1–2 minutes per fixture the runner accepts (it is a full
# pipeline, on purpose — the regression must exercise the REAL runner, not a
# short-circuit mode of it, because a mode that stops early is one more place
# for the two paths to drift apart).
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
. tools/evidence.sh
REPO="$PWD"

GATE_DB="sonyliv_q37_agree_gate"
RUN_DB="sonyliv_q37_agree_runner"
PROD="sonyliv"
OUT="${AGREE_OUT:-evidence/q37/agreement.txt}"

die() { printf 'contract-runner-agreement: %s\n' "$*" >&2; exit 2; }
for db in "$GATE_DB" "$RUN_DB"; do
  [ "$db" != "$PROD" ] || die "refusing to use the graded database"
done

[ -f .env ] || die "no .env — this needs Cloud credentials (see .env.example)"
set -a; . ./.env; set +a
for v in CH_HOST CH_PORT CH_USER CH_PASSWORD; do
  [ -n "${!v:-}" ] || die "$v is unset — fill in .env"
done
docker inspect ch >/dev/null 2>&1 || die "the 'ch' docker container is not running"

H="${CH_HOST#https://}"; H="${H#http://}"; H="${H%/}"
sysq() { curl -sS --fail-with-body "https://${H}:${CH_PORT}/?database=default" \
           --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$1"; }

mkdir -p "$(dirname "$OUT")"
: > "$OUT"
say() { printf '%s\n' "$*" | tee -a "$OUT"; }

TMP="$(mktemp -d)"; chmod 700 "$TMP"
trap 'rm -rf "$TMP"' EXIT

# ---------------------------------------------------------------------------
# FIXTURES. cruel-gen already generates the two shapes this is about, so they
# are taken from there rather than hand-rolled; the both-refuse controls are
# derived from cruel-gen's own output so they differ from it in exactly one way.
# ---------------------------------------------------------------------------
if [ $# -gt 0 ]; then
  FIXTURES=("$@")
else
  for k in newline newcol; do
    [ -f "data/cruel-$k-raw.csv" ] || tools/cruel-gen.sh gen "$k" >/dev/null 2>&1 || \
      die "could not generate data/cruel-$k-raw.csv (tools/cruel-gen.sh gen $k)"
  done
  # Controls: files BOTH paths must refuse. They exist so a "they agree!" verdict
  # cannot be earned by a guard that simply stopped guarding — the point of the
  # fix was to make the runner match the loader, not to make it accept anything.
  python3 - "$TMP" <<'PY'
import csv, sys
tmp = sys.argv[1]
rows = list(csv.reader(open("data/cruel-newcol-raw.csv", newline="")))
hdr, data = rows[0][:13], [r[:13] for r in rows[1:]]
def w(name, h, d):
    with open(f"{tmp}/{name}.csv", "w", newline="") as f:
        cw = csv.writer(f); cw.writerow(h); cw.writerows(d)
# a missing non-essential column: announced by the runner, refused by the loader
w("ctl-misscol", [c for c in hdr if c != "country"],
  [[v for c, v in zip(hdr, r) if c != "country"] for r in data])
# a duplicate header column: refused by both, at their own front doors
w("ctl-dupecol", hdr + ["country"], [r + [r[8]] for r in data])
PY
  FIXTURES=(data/cruel-newline-raw.csv data/cruel-newcol-raw.csv \
            "$TMP/ctl-misscol.csv" "$TMP/ctl-dupecol.csv")
fi

CONTENT="data/cruel-content.csv"
[ -f "$CONTENT" ] || tools/cruel-gen.sh gen newcol >/dev/null 2>&1 || true
[ -f "$CONTENT" ] || die "missing $CONTENT"

# ---------------------------------------------------------------------------
# gate_verdict <csv> -> ACCEPT | REFUSE   (RUNBOOK_UNSEEN.md §0, verbatim shape)
# ---------------------------------------------------------------------------
gate_verdict() {
  local csv="$1" log="$2" rc=0
  sysq "DROP DATABASE IF EXISTS ${GATE_DB}" >/dev/null
  sysq "CREATE DATABASE ${GATE_DB}" >/dev/null
  CH_DATABASE="$GATE_DB" TARGET=cloud tools/apply-sql.sh --database "$GATE_DB" \
    sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql >>"$log" 2>&1 || { echo REFUSE; return; }
  set +e
  CH_DATABASE="$GATE_DB" TARGET=cloud tools/load.sh --database "$GATE_DB" \
    "$csv" "$CONTENT" >>"$log" 2>&1
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then echo REFUSE; return 0; fi
  set +e
  tools/validate-source-contract.sh -c --database "$GATE_DB" >>"$log" 2>&1
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then echo ACCEPT; else echo REFUSE; fi
  return 0
}

# ---------------------------------------------------------------------------
# runner_verdict <csv> -> ACCEPT | REFUSE-FILE | RAN-BUT-FAILED
#
# The distinction matters: only REFUSE-FILE can violate the invariant. The
# runner names its failing phase in a banner ("=== FAILED: 2 load ==="), and a
# failure at preflight or at the load IS a statement about the file. A failure
# at any later phase is a statement about the model.
# ---------------------------------------------------------------------------
runner_verdict() {
  local csv="$1" log="$2" rc=0
  sysq "DROP DATABASE IF EXISTS ${RUN_DB}" >/dev/null
  set +e
  UNSEEN_DB="$RUN_DB" UNSEEN_OUT="$log" tools/unseen-run.sh "$csv" "$CONTENT" >/dev/null 2>"$log.err"
  rc=$?
  set -e
  # if/fi, NOT `[ ... ] && { ... }`. These functions run inside `$( )`, and a
  # trailing `&&` list that evaluates false returns 1 for the whole statement —
  # `set -e` then kills the SUBSHELL, the assignment inherits status 1, and the
  # script dies silently mid-loop with no verdict printed. That is the same trap
  # that stopped phase 2b of tools/unseen-run.sh from ever running its contract
  # gate (evidence/q37/README.md, case 3); it bit this script too, on its first
  # both-refuse fixture. Worth the four extra characters.
  if [ "$rc" -eq 0 ]; then echo ACCEPT; return 0; fi

  # A refusal by tools/load.sh does NOT reach the runner's die() banner: phase 2
  # pipes the loader through `tee`, and with `set -o pipefail` the failing
  # pipeline trips `set -e` and kills the script before die() ever runs. So the
  # banner is only one of the two signatures worth reading, and a classifier
  # that trusts it alone calls a plain file refusal "RAN-BUT-FAILED".
  #
  # That direction is the safe one — it can only UNDER-report violations, never
  # invent them — but under-reporting is exactly how this regression would go
  # quiet on the defect it exists to catch. So the loader's own refusal markers
  # count too.
  # The loader writes its refusal to STDERR, which never reaches UNSEEN_OUT
  # (phase 2 tees stdout only), so runner_verdict captures stderr separately.
  if grep -q 'REFUSING:\|=== load.sh FAILED ===' "$log" "$log.err" 2>/dev/null; then
    echo "REFUSE-FILE"; return 0
  fi
  local phase
  phase="$(grep -m1 '=== FAILED:' "$log" 2>/dev/null | sed 's/.*=== FAILED: //; s/ ===.*//' || true)"
  # Default RAN-BUT-FAILED on anything unrecognised, INCLUDING an absent banner.
  # The reconcile gate fails with "VERDICT — GATE FAILED" and no banner at all;
  # calling that a file refusal would manufacture a violation out of a model bug,
  # which is the one error this script must never make.
  case "$phase" in
    preflight|*load*) echo "REFUSE-FILE" ;;
    *)                echo "RAN-BUT-FAILED" ;;
  esac
  return 0
}

# ---------------------------------------------------------------------------
say "CONTRACT GATE vs REAL RUNNER — do they agree about what a valid file is?"
say "generated $(date -u '+%Y-%m-%dT%H:%M:%SZ')   commit $(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
say "invariant: anything the gate PASSES, the runner must ACCEPT"
say "gate db ${GATE_DB} · runner db ${RUN_DB}"
say "--------------------------------------------------------------------------"
say ""
printf '%s\n' "  fixture                        gate      runner           verdict" | tee -a "$OUT"

VIOLATIONS=0
for csv in "${FIXTURES[@]}"; do
  [ -f "$csv" ] || die "no such fixture: $csv"
  name="$(basename "$csv")"
  glog="$TMP/gate-$name.log"; rlog="$TMP/run-$name.log"
  : > "$glog"

  G="$(gate_verdict "$csv" "$glog")"
  R="$(runner_verdict "$csv" "$rlog")"

  if [ "$G" = ACCEPT ] && [ "$R" = "REFUSE-FILE" ]; then
    V="VIOLATION"; VIOLATIONS=$((VIOLATIONS + 1))
  else
    V="ok"
  fi
  printf '  %-30s %-9s %-16s %s\n' "$name" "$G" "$R" "$V" | tee -a "$OUT"

  if [ "$V" = VIOLATION ]; then
    say "      the gate passed this file and the runner refused it, at:"
    say "      $(grep -m1 -A3 '=== FAILED:' "$rlog" | sed 's/^/        /' | tr '\n' ' ')"
  fi
done

say ""
say "--------------------------------------------------------------------------"
if [ "$VIOLATIONS" -gt 0 ]; then
  say "VERDICT: FAIL — ${VIOLATIONS} file(s) the gate passed and the runner refused."
  say "The pre-flight is lying. Fix whichever side is wrong; do NOT loosen the gate"
  say "to make them agree — a gate that passes everything is the same as no gate."
  echo "agreement FAILED · $OUT" >&2
  exit 1
fi
say "VERDICT: PASS — no file was passed by the gate and refused by the runner."
say ""
say "Read the both-refuse rows as load-bearing: they are the proof that agreement"
say "was reached by making the runner match the loader, not by making either stop"
say "checking. If those rows ever read ACCEPT/ACCEPT, this script has stopped"
say "testing anything."
evidence_seal "$OUT"   # LAST thing a successful run does — see tools/evidence.sh
echo
echo "agreement PASSED · evidence written to $OUT"
