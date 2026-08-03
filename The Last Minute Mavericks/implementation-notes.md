# Implementation notes — ClickStack integration (the 4th leg)

Build log for `teamkit/PLAN_CLICKSTACK.md`. Records what the plan did not predict.
Append only.

## 2026-08-02 · T1–T10

### Deviations from the plan

**Host port is 8081, not 8080.** The plan called 8080 "free — collides with nothing we
run". It is not free. Tailscale holds it on this machine (a Funnel listener on
`100.76.48.126:8080` and the `fd7a:115c:a1e0::` ULA). The failure is silent in three
layers: `docker ps` reports the port published, `lsof` without root shows no owner, and
lima logs `failed to set up forwarding tcp port 8080 (negligible if already forwarded)`.
Only a raw `bind()` reveals `EADDRINUSE`. The compose file now maps `8081:8080`.
Container side is unchanged.

**Langfuse spans leaked into ClickStack.** Not in the plan's failure-mode table.
`trace.set_tracer_provider()` installs a *global* provider; Langfuse v4 is OTel-based, so
its reasoning spans ("RCA scan · rca", one per incident) exported through our collector.
Confirmed by reading `otel_traces` — 8 Langfuse spans alongside our own. The plan's T5
(`blocked_instrumentation_scopes`) only blocks the other direction. Fix: a **private**
`TracerProvider` via `provider.get_tracer(...)`, never the global setter. T5 is kept as
defence in depth.

**Collector-down was not silent.** The plan promised "user sees nothing". Reality with a
stopped container: three red retry tracebacks on stderr and a ~17 s blocked shutdown
(42.8 s vs 25 s baseline). Root cause: we started an exporter we could not reach. Fix is
a 400 ms TCP pre-flight at init — if nothing answers, stay a no-op and print one line.
Re-measured at 26.1 s with no errors.

### Facts worth keeping

- The scan issues **192** ClickHouse queries, not the 56 the plan assumed. At ~154 ms
  average round trip that is essentially the entire wall clock.
- Instrumentation overhead is unmeasurable: OFF 25.6 s / ON 25.2 s, OFF 25.1 s / ON
  24.2 s. An early 18.9 s vs 37.2 s reading was ClickHouse Cloud latency variance, not
  span cost. Do not trust a single paired run on a cloud-backed scan.
- `res.summary` on a `clickhouse_connect` **QueryResult** carries `read_rows`,
  `read_bytes` and `elapsed_ns`. It is an instance attribute, so it does not appear in
  `dir(QueryResult)` — checking the class is misleading, query a live server instead.
- `api/server.py` passed `wall_clock_s=0.0` into every bundle while holding the real
  elapsed time. Now measured.

### Checked, no change needed

`agent/narrate.py:27` builds the evidence string from `id`/`value`/`label` only, not from
the whole dict. The three new numeric keys (`rows_read`, `bytes_read`, `duration_ms`)
therefore never enter the prompt or `_allowed_numbers`. The anti-fabrication whitelist is
not widened. This was the main risk of making evidence objects richer.

### Not instrumented, by design

`ui/data.py` (own raw HTTP query path), `scripts/load_clickhouse.py` and
`scripts/gen_e2e_dataset.py` (own clients). Traces only — no OTel logs or metrics
pipeline. The reachability probe runs once at init, so a collector that starts *after*
the process does not attach without a restart.

## Short-slice baseline (`rca_unseen`, 5 days) — 2026-08-02

**Symptom.** Every investigation on `rca_unseen` came back with
`decomposition_meta.method = "unavailable (a factor is zero or missing)"`, all factor
`deviation_pct` null, `stable: false`. LMDI never ran on the sealed slice.

**Cause.** The slice is 5 consecutive days (Mon 07-06 .. Fri 07-10), so each weekday occurs
exactly ONCE. `baseline_days()` matches same-weekday and excludes the incident window, which
removes the only Wednesday — the weekday-matched set is empty, `_basep()` emits the literal
`0` predicate, every `sumIf(..., 0)` returns 0, and LMDI bails on a zero baseline. The
documented "following same-weekdays" fallback cannot help: there is no second Wednesday
anywhere in a 5-day span. Measured: 12/12 windows empty on `rca_unseen`.

**Fix.** `_flat_baseline_days()` — when weekday matching yields nothing, compare against whole
days outside the window instead. Keeps the coarse weekday/weekend split so a weekend day can't
land in a weekday baseline (the confound weekday-matching exists to prevent); preceding-only,
forward only when the window starts the slice; contaminated days still dropped.

**Blast radius: none on any slice with real history.** The new branch is reachable only where
`baseline_days()` currently returns `[]`. Measured across `rca`, `rca_t1-3`, `rca_d1-2`,
`rca_e2e`, `rca_ts1-2`, windows of 1-7 days: 0 of 224-259 windows empty. `./test-sql/run.sh`
after the change: 6/6 localized, exact magnitudes, 3/3 controls suppressed, 0 false positives;
both `test-sql/*/bundle.json` diffs are timestamps/query_ids/durations only.

**Result on `rca_unseen`.** Same incident set (2 reported, 1 suppressed — the adjudicator's
`+6.1%` mix-shift call survives). Deviations shift ~0.1pp because the baseline is now real days
instead of zero: fill_rate -39.9% -> -40.0%, ecpm -29.4% -> -29.5%. LMDI now computes:
`stable: true`, LMDI-vs-Shapley divergence 0.14%, and the factor table renders the ruled-out
list with numbers (requests -0.5% / 1.0% share, render_rate -0.1% / 0.2%).

**Footnote honesty (the part that nearly shipped wrong).** Three judge-facing strings asserted
"same weekdays" regardless of what ran: the engine's `baseline_window` (hardcoded f-string),
`ui/rca_text.py:_baseline_sentence` (hardcoded lead), and two sites in `ui/diagnosis.py`
(subtitle + KPI caption). All four now derive the wording from what the engine actually did,
via `_baseline_note()` (engine) and `baseline_caption()` (UI). Checks in
`tests/test_short_slice_baseline.py`.

**Open.** `ruled_out[].why` renders "residual - outside it" — a missing number in the template,
present before this change and unrelated to it.
