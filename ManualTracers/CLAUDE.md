# CLAUDE.md — InMobi Click-a-thon 2026

Automated root-cause analyst. A metric moves → detect it → drill down in ClickHouse
to isolate the responsible segment → emit an evidence-backed diagnosis where every
number is computed, not narrated into existence.

24-hour hackathon. Two people: Harsh (data engineering, through the webhook) and one
ML/AI engineer (webhook onward). Deadline pressure is real — prefer working over
elegant, but never trade away correctness or traceability, which are what is scored.

## Read first

| File | What it is |
|---|---|
| `InMobi/PROBLEM_STATEMENT.md` | The brief and the five judging criteria |
| `InMobi/metrics_glossary.md` | **Authoritative** metric formulas — never restate them elsewhere |
| `architecture.md` | System design and the reasoning behind it |
| `docs/RCA_AGENT_DESIGN.md` | **As-built.** What actually runs today (`RCA/app/`), vs. what's still to build |
| `docs/RCA_DECOMPOSITION_MATH.md` | Derivation of the log-share revenue decomposition |
| `docs/REPLAY_CLOCK.md` | How the time shift and `replay_clock` bucket math work, and how compressed replay will plug in |

## Hard constraints

- **ClickHouse is the primary datastore and the analytical engine.** The drill-down
  must run as ClickHouse queries. Judges explicitly check that the engine is doing
  the real work, not the LLM.
- **ClickHouse computes, the LLM narrates.** The model never sees a raw row, never
  does arithmetic, never picks the next step. One fabricated number costs more than
  a missed anomaly.
- **No trace, no credit.** The sealed-dataset diagnosis must demonstrably come out
  of the pipeline. Langfuse trace per incident, flushed.
- **Build for the unseen incident**, not the four anomalies visible in this data.
  No hardcoded dates, segments, or thresholds tuned to what we found.
- All repo code must be written inside the 24-hour window.

## Layers

```
ad_events                       raw, replayed, the only table loaded
  └─ MV1 ─▶ ad_events_enriched  dictGet-denormalised · event_time indexed
                                EVERYTHING reads this: metrics, baselines, drill-downs

metric_def                      metric_id · sql · dependencies · z_score_threshold + guard rails
metric_dim_map                  (metric_id, dim_id) · priority · dependencies
       │
       ▼  RCA/app/metric_sql.py renders one query: series → baseline → z → is_anomaly
   HyperDX chart + alert (above_exclusive 0, static metric_id in the message)
       │
       ▼
   webhook ─▶ RCA agent (RCA/app/) ─▶ narrator + grounding ─▶ Langfuse trace
```

**No metric views, no rollup, no incident table.** `metric_def.sql` executes
directly against `ad_events_enriched`. The detection maths exists in exactly one
place — `RCA/app/metric_sql.py` — rendered twice: with bound parameters by the
agent, with `now()`-relative bounds by `scripts/metric_query.py` for HyperDX.
Do not reintroduce a view or a materialised rollup without moving the builder
behind it; two copies of a formula is the failure this design exists to avoid.

Files: `sql/01_schema` → `02_dictionaries` → `03_silver` → `04_semantic_layer`.
Apply in order; `scripts/replay.sh` does it.

The RCA agent is its own `uv` project in `RCA/` — `main.py` (webhook),
`investigate.py` (reproduce → decompose → scan → holdout → dependency walk),
`metric_sql.py` (the query builder), `registry.py` (`metric_def` /
`metric_dim_map` lookups).

`scripts/metric_query.py` renders every detection query from the same builder:
`alert` (global tile), `marginal` (per-slice sentinel tile), `freshness` (ops
tile), `scan` (ranked segment scan; `replay.sh` runs it as post-load
verification). `scripts/provision_alerts.py --apply` renders all of them from
the registry and pushes the dashboard + alerts to ClickStack.

## Non-negotiable design rules

1. **Alert on the global series *and* on the marginals — never on the
   cross-product.** That cross-product is 767,984 combos (measured); the
   marginals are 62 and cost one `ARRAY JOIN` pass. Global-only alerting was the
   original rule and it silently missed segment-confined incidents: measured on
   the replay, the planted `os_version=iOS 18.1` fault scores **0 anomalies on
   the global `fill_rate` tile** while the marginal tile catches it at z 8.1–9.5.
   So there are two tiles per metric. Depth 2 is still never enumerated — it
   crosses only what `metric_dim_map.dependencies` says is entangled with the cut
   that led. The marginal tile emits `LIMIT 1 BY` the top-contribution slice per
   bucket, because a correlated fault lights up several slices at once and each
   surviving group is its own webhook and its own RCA run.
2. **Cardinality budget:** a dimension is a candidate only if it has a row in
   `metric_dim_map`, and only dimensions with ≤ ~50 distinct values get one.
   `app_id` (2,000), `geo_device_id` (5,000), `advertiser_id` (500) are absent by
   design — reachable for a manual drill, never enumerated.
3. **Ratios are sum/sum, always.** Never average a ratio. `metric_def.sql` is a
   single aggregate expression over raw rows, so this is structurally enforced.
4. **`min_samples` guards degenerate slices — it is not a confidence knob.**
   `proportionsZTest` supplies confidence. At 5,000 it silently hid the largest
   planted incident (Android 15, ~1,025 req/hr). To cut noise, tighten `z` or the
   effect-size floors instead.
5. **Decompose before slicing.** A metric with `metric_def.dependencies`
   (`revenue`) walks the identity `Requests × Fill rate × Render rate × eCPM/1000`
   *before* any dimension is cut. Otherwise one fault reports as three
   independent incidents.
6. **You can only rule out what you enumerated.** Every candidate gets a verdict:
   `implicated | cleared | inconclusive`. The ledger is simultaneously the LLM's
   input and the Langfuse trace.

## Environment gotchas

- **Both ClickHouse MCPs are SELECT-only.** DDL must run from the local machine via
  `scripts/replay.sh`. Do not try to create objects through an MCP.
- **`mcp__clickhouse__query` points at the HealthKart *work* cluster**, not the
  hackathon service. Never write there. The hackathon service is reached through
  the ClickStack connection (`Manual Tracers`) or `.env` credentials.
- **git-lfs is not installed in the Cowork sandbox.** `InMobi/data/*.csv` are
  LFS-tracked. A bare `git add -A` from the sandbox replaces the 130-byte pointers
  with full file content and corrupts LFS. **Always `git restore --staged
  InMobi/data/` before committing from the sandbox.** (This already happened once
  and was repaired in commit `6a9c7a4`.)
- **The sandbox cannot reach ClickHouse Cloud** (proxy 403). Validate SQL by running
  it as a SELECT through the ClickStack MCP; execute DDL locally. A rendered
  deviation query can be smoke-tested with no tables at all by swapping
  `inmobi.ad_events_enriched` for a `numbers()` subquery that fabricates the
  columns — that validates the whole CTE/window/z-test shape.
- Pushing needs Harsh's SSH key — the sandbox has none.
- **The webhook is a cloudflare quick tunnel, and quick tunnels get a new random
  hostname every restart.** When the agent stops receiving, check the stored
  webhook URL first — a dead tunnel shows up as `Failed to send webhook
  notification` on every alert while the tiles themselves are perfectly healthy.
  The path matters too: it must end `/webhooks/alerts` (`main.py`), not the
  literal `/****` that was stored at one point and produced a 404 on every
  delivery. Restarting the tunnel from some networks fails entirely — QUIC is
  blocked and the HTTP/2 edge times out, so `--protocol http2` is not always a
  rescue. Fallback for a demo: POST to `http://localhost:8000/webhooks/alerts`
  directly; the alert state and the tile SQL are still the real thing, only the
  transport is stood in for.
- **PyPI is unreachable from the Cowork sandbox and from Docker builds** —
  a TLS-intercepting proxy presents a CA that curl (macOS keychain) trusts and
  Python/pip do not (`CERTIFICATE_VERIFY_FAILED: self-signed certificate in
  certificate chain`). `uv run pytest` and `docker compose build` therefore only
  work from Harsh's own shell, and any script that must run from either place
  should shell out to `curl` rather than use `urllib` for HTTPS —
  `provision_alerts.py` does exactly that, deliberately.
- **`curl --data-binary @path` can fail to open large files in some sandboxed
  shells** (`curl: option --data-binary: error encountered when reading a file`,
  even though the file exists and is readable). `replay.sh` streams both the
  dimension CSVs and `AD_EVENTS_FILE` via stdin redirection (`--data-binary @- <
  "$file"`) instead — functionally identical, just avoids curl's own file-open
  path. Don't revert this to `@"$file"` on the sealed-dataset run.
- **The webhook *body* template supports only `{{title}}`/`{{body}}`/`{{link}}`,
  but the alert *message* also substitutes `{{group}}` and `{{value}}`.** These
  are two different templates and conflating them cost a design detour. The
  message is what gets interpolated into `{{body}}`, so a grouped tile *can*
  name the slice that fired — `scripts/provision_alerts.py` sends
  `dimension_id={{group}} z={{value}}`. A two-column group renders as
  `dim_name:country, dim_value:CA`, which is why `main.py::DIMENSION_ID_RE`
  strips an optional `dim_name:` prefix. `metric_id=<x>` is still a static
  string per alert.
- **ClickStack's alert interval enum bottoms out at `1m`** (`1m, 5m, 15m, 30m,
  1h, 6h, 12h, 1d`). There is no seconds option, so a compressed replay cannot
  be alerted on at its own pace: at `bucket_seconds=2` one evaluation covers 30
  data-hours. `metric_sql.lookback_buckets()` widens the agent's window to match,
  because investigating a narrower window than the alert scored reports a real
  incident as `not_reproducible`.
- **A `line` tile alert must reference an interval macro; a `number` tile must
  not.** Time-series alerts are rejected without `$__timeInterval`/
  `{intervalSeconds}` (each bucket is scored independently, so the boundaries
  have to be known). A `number` tile is only substituted with the
  start/end pair — asking it for `{intervalSeconds}` passes validation and then
  fails at run time with ``Substitution `intervalSeconds` is not set``. Both
  kinds still require the window macros: no time macro at all is rejected.
- **Tile SQL is clock-dependent.** `metric_sql._clock_exprs()` bakes the bucket,
  hour-of-day and weekend expressions into the query text at render time, so
  every `compress_replay.py` run leaves every saved tile scoring the previous
  clock. Compression must always be followed by
  `./scripts/provision_alerts.py --apply`. The agent needs nothing — it re-reads
  `replay_clock` per query.

## Data facts worth knowing

- 9,000,000 events, 2026-06-01 → 2026-07-05 (35 days, 840 hours), ~10.7K req/hour.
- `advertiser_id` is `''` (empty string, **not NULL**) on unfilled requests.
- Region is `NAM`, never `NA`.
- Dimensions: 5 ad_format, 7 category, 3 publisher_tier, 5 region, 16 country,
  8 device_model, 8 os_version, 7 vertical, 3 campaign_type = **62 slices at depth 1**.
  Exhaustive depth-1 enumeration is cheap — do not build clever pruning.
- `vertical` / `campaign_type` exist only on filled requests, so `fill_rate` is
  meaningless for them (`invalid_dims` in the registry).

## Confirmed detections (9M rows — measured before the rebuild, re-confirm after ingest)

| Day(s) | Segment | Actual | Expected | Peak z | Global tile fires? |
|---|---|---|---|---|---|
| Jun 23–25 | `os_version=Android 15` | 0.434 | 0.785 | 28.1 | yes (global z=11.4) |
| Jun 29–30 | `os_version=iOS 18.1` | 0.683 | 0.780 | 10.6 | **no — 0 anomalies** |
| Jun 23–25 | global fill rate | 0.750 | 0.785 | 11.4 | yes |

The last column is why the marginal sentinel exists, and it is measured on the
compressed replay, not argued: over the iOS 18.1 window the global `fill_rate`
tile returns `anomaly_count = 0` while the marginal tile returns
`os_version=iOS 18.1` at z 8.1–9.5. Global-only alerting misses that incident
entirely — the agent's depth-1 scan would find it, but nothing would ever wake
the agent.

## Known traps

- **Correlated dimensions.** Android 15 drags `device_model` (Galaxy A54/S23,
  Redmi Note 12) and `region=EU` with it — those devices run Android 15. Condition
  on the parent and check the residual before naming a child slice.
- **Rank by contribution, not percentage change.**
  `delta_contribution = (actual − expected) × traffic_share`. Otherwise a tiny noisy
  slice outranks a large real one.
- **Simpson's paradox.** Fill rate varies by app category at baseline; a mix shift
  moves the global number with no segment misbehaving. Emit rate effect and mix
  effect separately.
- **Baseline contamination.** A trailing baseline containing the incident makes
  recovery look like a spike (Android 15 scores z=7.9 *upward* on Jun 26). Exclude
  already-flagged points from future baselines.
- **Global incidents have no culprit.** The Jun 21 −44% volume collapse is uniform
  across every dimension. Output "global movement, no localising segment" — do not
  invent one.
- **ClickStack alerts evaluate on wall clock.** The data ends 2026-07-05, so an
  unshifted load can never fire an alert. `TIME_SHIFT_WEEKS` in `replay.sh` fixes it,
  and must be **whole weeks** or day-of-week alignment breaks and the seasonal
  baseline silently corrupts.

## Commands

```bash
# Compressed replay, end to end. Re-runnable: compress_replay inverts a previous
# compression via replay_clock rather than re-reading the calendar, so this whole
# block is what to run again when the sealed dataset lands.
./scripts/compress_replay.py --bucket-seconds 2   # 840 data-hours -> 28 min
./scripts/provision_alerts.py --apply             # MANDATORY after any clock change

./scripts/replay.sh --schema    # DDL only
./scripts/replay.sh             # DDL + replay AD_EVENTS_FILE through MV1
./scripts/replay.sh --data      # replay only
./scripts/replay.sh --dims      # also reload the dimension CSVs
./scripts/suggest_shift.sh      # compute TIME_SHIFT_WEEKS

./scripts/metric_query.py alert fill_rate   # SQL to paste into a HyperDX chart
./scripts/metric_query.py scan  fill_rate   # ranked segment scan (replay.sh uses this)

cd RCA && uv run pytest -q                  # 39 tests, no ClickHouse needed
```

Sealed dataset: change `AD_EVENTS_FILE` at the top of `replay.sh`, truncate manually
(helper at the bottom of the script), re-run. The script never truncates by itself.

## Style

- Comment the *why*, not the *what* — especially any non-obvious statistical or
  schema choice, since judges read for design reasoning.
- Prefer one clear SQL file over a clever abstraction.
- Do not add a UI. Polished frontends are explicitly out of scope and unscored.
