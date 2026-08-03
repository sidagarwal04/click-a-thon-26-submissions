#!/usr/bin/env bash
# Evidence writer. Every script that produces a number calls this, so the number lands in a
# committed file stamped with when it ran, which code produced it, and WHICH DATA it saw.
#
#   . scripts/lib/evidence.sh
#   some_command | evidence parity_batch "oracle vs serving, batch path"
#
# Reads stdin, writes evidence/<name>__<UTC-ts>__<sha>.tsv, echoes the path on stdout and
# stderr (stderr so a caller that captures the path still shows it in the console).
#
# The sha carries a -dirty suffix when the tree has uncommitted changes: an artifact that
# claims a clean sha but came from uncommitted code is exactly the failure this repo is
# fixing. --porcelain, not `diff --quiet`: an untracked script is uncommitted code too.
#
# The data stamp exists because a git sha pins the CODE and says nothing about the DATA. The
# team ingests into phoenix.raw_events continuously, so an artifact without a row count is
# not reproducible: re-running it tomorrow measures a different dataset and the numbers move
# with no indication that anything changed.
#
# Set EVIDENCE_DB=0 to skip the data stamp (offline runs, clickhouse-local-only scripts).

# Queried once per shell, not once per artifact: a script writing four artifacts should not
# make four round trips, and the four should agree with each other.
_EV_DATA_STAMP=""
_ev_data_stamp() {
  [ -n "$_EV_DATA_STAMP" ] && { printf '%s' "$_EV_DATA_STAMP"; return; }
  [ "${EVIDENCE_DB:-1}" = "0" ] && { _EV_DATA_STAMP="# data: not queried (EVIDENCE_DB=0)
"; printf '%s' "$_EV_DATA_STAMP"; return; }

  local row
  # Stamp the database the run actually measured, not a hardcoded one. An artifact produced
  # against phoenix_next that reports phoenix's row count and watermark is worse than an
  # unstamped one: it is a stamp that says the wrong thing with full confidence.
  # EVIDENCE_STAMP_DB pins it explicitly when a script spans two databases and the stamp
  # should name the source rather than whichever database the last call happened to set.
  row="$(CH_DATABASE="${EVIDENCE_STAMP_DB:-${CH_DATABASE:-phoenix}}" ./scripts/ch.sh --format TSVRaw --query "
    SELECT count(),
           toString(max(event_timestamp)),
           toString(max(ingested_at)),
           countIf(event_timestamp < {frozen_before:String})
    FROM raw_events" 2>/dev/null | head -1)" || true

  if [ -z "$row" ]; then
    _EV_DATA_STAMP="# data: UNAVAILABLE (could not reach the service)
"
  else
    _EV_DATA_STAMP="# row_count: $(echo "$row" | cut -f1)
# event_watermark: $(echo "$row" | cut -f2)
# frozen_before: ${FROZEN_BEFORE:-2026-08-01}
# frozen_slice_rows: $(echo "$row" | cut -f4)   (event_timestamp < frozen_before, the validated corpus)
# ingest_watermark: $(echo "$row" | cut -f3)   (NOT REPRODUCIBLE, see below)
# ingest_watermark_warning: ingested_at was added by ALTER after the July rows were loaded.
#   ClickHouse does not rewrite existing parts, so for those 905,558 rows the DEFAULT now()
#   is evaluated AT READ TIME and the column equals the wall clock of whichever query reads
#   it. Proven in evidence/ingested_at_nondeterminism. Do not filter on it.
"
  fi
  printf '%s' "$_EV_DATA_STAMP"
}

# The ledger is written from in here, not by each caller, because a traceability index that
# depends on every script remembering to append a row is an index that goes stale. This way
# an artifact and its ledger row cannot diverge: there is one code path that produces both.
#
# claim_id is the evidence name, which is what docs/ cites. One row per claim_id, replaced
# in place on re-run: a judge following a [V] tag wants the current artifact in one hop, and
# superseded rows are still in git history where an audit trail belongs.
LEDGER="evidence/LEDGER.tsv"
#
# fail_kind sits between status and verified_at_sha, per TASK.md 0.3: `finding` means the gate
# worked and recorded a real negative result, `broken` means the gate itself is broken. Empty for
# anything that is not FAIL.
#
# THIS COLUMN WAS ADDED TO THE DATA BEFORE IT WAS ADDED HERE, and every row written in between
# came out with 7 fields instead of 8, which silently shifted the sha into the fail_kind column for
# 10 rows. check_docs.sh did not notice because it reads artifact_path at column 4, which is
# unaffected either way. That is why it now asserts the field count too: a ledger that is ragged in
# its last columns still passes every check that only looks at its first four.
_ev_ledger() {
  local claim_id="$1" claim="$2" script="$3" artifact="$4" status="$5" sha="$6" utc="$7" fail_kind="${8:-}"
  mkdir -p evidence
  [ -f "$LEDGER" ] || printf 'claim_id\tclaim\tcommand_or_script\tartifact_path\tstatus\tfail_kind\tverified_at_sha\tverified_at_utc\n' > "$LEDGER"
  # A FAIL with no explicit kind defaults to `finding`: a gate that ran and returned a negative
  # result is the common case, and defaulting to `broken` would cry rot on every honest red row.
  [ "$status" = FAIL ] && [ -z "$fail_kind" ] && fail_kind=finding
  local tmp="${LEDGER}.tmp.$$"
  awk -F'\t' -v id="$claim_id" 'NR==1 || $1 != id' "$LEDGER" > "$tmp"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$claim_id" "$claim" "$script" "$artifact" "$status" "$fail_kind" "$sha" "$utc" >> "$tmp"
  mv "$tmp" "$LEDGER"
}

# PASS/FAIL is read back out of the artifact rather than passed in, so the ledger cannot
# claim a gate passed while the artifact it points at says otherwise.
#
# Scripts write a verdict two different ways: as a `verdict`/`gate` ROW (open_sessions), or
# as a verdict COLUMN with one row per comparison (oracle_parity). So this scans every field
# of every data line rather than assuming a layout. FAIL wins over PASS: an artifact with
# three passes and one failure is a failure, and the ledger must not round that up.
#
# RECORDED is the honest answer for an artifact that reports measurements and asserts no
# gate at all (naive_vs_foreground, adpause_impact). It is not a synonym for "unknown".
_ev_status() {
  awk -F'\t' '
    /^#/ { next }
    { for (i = 1; i <= NF; i++) {
        if ($i == "FAIL") { fail = 1 }
        else if ($i == "PASS") { pass = 1 } } }
    END { print fail ? "FAIL" : (pass ? "PASS" : "RECORDED") }
  ' "$1" 2>/dev/null
}

evidence() {
  local name="$1" desc="${2:-}"
  local ts sha out utc status script
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  utc="$(date -u +'%Y-%m-%d %H:%M:%S')"
  sha="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
  [ -z "$(git status --porcelain 2>/dev/null)" ] || sha="${sha}-dirty"
  out="evidence/${name}__${ts}__${sha}.tsv"
  mkdir -p evidence
  {
    echo "# evidence: ${name}"
    [ -n "$desc" ] && echo "# what: ${desc}"
    echo "# run_utc: ${utc}"
    echo "# git: ${sha}"
    echo "# host: $(uname -n)"
    _ev_data_stamp
    cat
  } > "$out"

  status="$(_ev_status "$out")"
  script="${EV_SCRIPT:-$(basename "${BASH_SOURCE[-1]:-$0}")}"
  _ev_ledger "$name" "${desc:-$name}" "$script" "$out" "${status:-RECORDED}" "$sha" "$utc"

  echo "wrote $out" >&2
  echo "$out"
}
