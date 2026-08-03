# info.md — the facts behind the deck

Single source of truth for every number, command, ID and claim the other five
files in this folder ask you to fill in. Everything here was **measured on this
build**, not carried over from an earlier design.

Where a presentation file is now wrong, this document says so explicitly under
[Corrections](#corrections-to-the-other-presentation-files) — read that section
before rehearsing, because two of the errors will break the live demo.

Last verified: 2026-08-02, compressed replay at `bucket_seconds=2`.

---

## 1. Numbers to have ready

Fills the placeholder table in `TALKING_POINTS.md`.

| Item | Value | How it was obtained |
|---|---|---|
| Events in dataset | **9,000,000** | `SELECT count() FROM inmobi.ad_events_enriched` |
| Distinct apps | 2,000 | `uniqExact(app_id)` |
| Data span | 840 data-hours (35 days) | `dateDiff('hour', min, max)` on the uncompressed load |
| Planted anomalies found (training) | **3 of 3** | table in §3 |
| Depth-1 slices scanned per factor | **62** | 5 ad_format + 7 category + 3 publisher_tier + 5 region + 16 country + 8 device_model + 8 os_version + 7 vertical + 3 campaign_type |
| Full cross-product (never enumerated) | **767,984** | measured, not estimated |
| End-to-end investigation latency | **2.07 s** | webhook POST → `investigation for revenue` in the agent log, revenue (the deepest path: decomposes into 4 factors) |
| ClickHouse queries per investigation | **~9** for `revenue`, **~5** for a factor metric | derived from the ladder, see §5 |
| Tests | **57 test functions** across 12 files | `RCA/tests/` |
| RCA reports produced in the last full replay | 14 | `data/rca_reports/` |
| Alerts provisioned | **8** on 8 tiles | §4 |

> **Do not claim a false-positive rate.** The honest position is in §6 — we have a
> known false alert and it is better to name it than to be caught by it.

---

## 2. What the detection layer actually is

`SLIDE_TEMPLATE.md` slide 3 and the HyperDX Q&A answer in `TALKING_POINTS.md`
both describe a single chart per metric on the `ALL` bucket. That is the *old*
design. There are now three kinds of tile, all generated from one builder by
`scripts/provision_alerts.py --apply`:

| Tile | Type | Threshold | Asks |
|---|---|---|---|
| **global** — one per alertable metric | `number` | `above_exclusive 0` | did the metric itself move? |
| **marginal sentinel** — one per metric with dimensions | `line`, grouped on `dim_name`/`dim_value` | `above_exclusive 0` | did any depth-1 slice move, *even if the global series did not*? |
| **freshness** — one, total | `number` | `above 1` evaluation window | is data still arriving? |

Live: dashboard `RCA Detection`, id `6a6eba8ea561469a8f4eef82`, 8 tiles, 8 alerts,
all pointing at webhook `RCA Agent Receiver` (`6a6debfdca45b0d18a58579f`).

**Alertable metrics are `revenue`, `requests`, `fill_rate`, `ecpm`.** `ctr`,
`render_rate` and `rpr` are deliberately excluded, driven by the new
`metric_def.alertable` column — not by a hardcoded list. Justification in §6.

### The one slide-worthy fact about the marginal tile

Global-only alerting has a **measured blind spot**:

| iOS 18.1 window (data-hours 672–720) | Result |
|---|---|
| global `fill_rate` tile | **0 anomalies** — never fires |
| marginal sentinel | `os_version=iOS 18.1` at z **9.53** and **10.56** |

An incident confined to a segment too small to move the global number is
invisible to the old design. The agent's depth-1 scan would have found it — but
nothing would ever have woken the agent. This is the strongest single argument
in the deck that the detection layer was designed, not assembled.

Cost of closing it: one extra query per metric. Not 62 — the 62 marginals are one
`ARRAY JOIN` pass, the same fan-out `scan_dims` uses.

---

## 3. Detection results (training data)

Fills slide 8 of `SLIDE_TEMPLATE.md`. Reproduced today on the compressed replay.
Actuals and peak z reproduce the values in `architecture.md` exactly; the Android
15 *expected* comes out at 0.782 against the 0.785 recorded there, because the
seasonal baseline is computed over a slightly different set of matching buckets
under the compressed clock. Quote the measured numbers, not the documented ones —
they are what the trace will show.

| Day(s) | Segment | Actual | Expected | Peak z | Global tile fires? |
|---|---|---|---|---|---|
| Jun 23–25 | `os_version=Android 15` | 0.434 | 0.782 | **28.1** | yes (global z=11.4) |
| Jun 29–30 | `os_version=iOS 18.1` | 0.683 | 0.780 | 10.6 | **no — 0 anomalies** |
| Jun 23–25 | global fill rate | 0.750 | 0.785 | 11.4 | yes |

### The Android 15 walk-through (use this one live)

From report `rca-fill_rate-4cb1b382`, generated end to end this morning:

```
reproduce   global fill_rate 0.7502 vs expected 0.7848,  peak |z| = 11.42
scan        os_version=Android 15    z=28.1  contribution=10697  act 0.4340 exp 0.7819
            publisher_tier=tier_2    z= 7.8  contribution= 4934
            region=EU                z= 8.9  contribution= 4225
            ad_format=banner         z= 8.0  contribution= 3700
            device_model=Galaxy A54  z= 7.8  contribution= 3550
holdout     remove Android 15 -> residual delta -0.00042  vs candidate delta -0.3479
            ratio 0.0012  =>  verdict: localized
cross       no dependent dimension concentrated -> fault is at OS level
ruled out   publisher_tier=tier_2, region=EU, ad_format=banner,
            device_model=Galaxy A54, device_model=Redmi Note 12,
            publisher_tier=tier_1, device_model=Galaxy S23
```

The line to say out loud: **"Five dimensions lit up. One survived the holdout.
The system named it *and* told you why the other four were false leads."**

Note the ranking is by **contribution** (`|delta_abs| × sample_count`), never by
percentage change — that is what stops a noisy 0.1%-of-traffic slice outranking a
real move.

---

## 4. Commands that actually work

### Live demo trigger — **port 8000, not 3002**

```bash
curl -X POST http://localhost:8000/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{"title":"fill_rate alert","body":"metric_id=fill_rate scope=global"}'
```

Verified: `:8000 → 202 Accepted`, `:3002 → 404`. Port 3002 is `rca-api`, which
*serves* reports; it has no webhook route.

Expected response:

```json
{"status":"accepted","delivery_key":"…","investigation":"started",
 "metric_id":"fill_rate","dimension_id":null}
```

A marginal-scope body additionally carries the firing slice:

```bash
curl -X POST http://localhost:8000/webhooks/alerts \
  -H "Content-Type: application/json" \
  -d '{"title":"🚨 fill_rate · marginal sentinel","body":"Group: \"dim_name:os_version, dim_value:Android 15\"\nmetric_id=fill_rate scope=marginal dimension_id=dim_name:os_version, dim_value:Android 15 z=28.08"}'
```

→ `"dimension_id":"os_version"` (the parser strips the `dim_name:` prefix).

### Services

| Service | Port | Purpose |
|---|---|---|
| `rca-agent` | 8000 | webhook receiver + investigation ladder |
| `rca-api` | 3002 | serves persisted reports to the UI |
| `rca-ui` | 8090 | the UI |

```bash
docker compose up -d --build          # all three
curl -s localhost:8000/health         # {"status":"ok"}
docker logs -f rca-agent              # investigation output
```

### Regenerating the detection layer

```bash
./scripts/compress_replay.py --bucket-seconds 2   # 840 data-hours -> 28 min
./scripts/provision_alerts.py --apply             # MANDATORY after any clock change
```

The second command is not optional. `metric_sql._clock_exprs()` bakes the bucket
and seasonality expressions into the **query text**, so every saved tile keeps
scoring the previous clock until re-rendered. The agent needs nothing — it
re-reads `replay_clock` per query.

### Inspecting the semantic layer (for screenshots 02 / 03)

```sql
SELECT metric_id, detector, alertable, z_score_threshold, min_samples,
       min_effect_rel, min_effect_abs
FROM inmobi.metric_def FINAL ORDER BY alertable DESC, metric_id;

SELECT * FROM inmobi.metric_dim_map FINAL ORDER BY metric_id, priority;
```

---

## 5. Where the queries come from

For the "ClickHouse does the work" slide. Per investigation, against
`ad_events_enriched`:

| Step | Queries | Notes |
|---|---|---|
| `get_max_ts` | 1 | `least(now(), max(event_time))` |
| Step 1 reproduce (global) | 1 | |
| Step 2 decompose | 4 | one per funnel factor — **`revenue` only** |
| Step 3 scan_dims | 1 per implicated factor | all 62 slices in ONE `ARRAY JOIN` pass |
| Step 4 holdout | 1 per implicated factor | metric on the complement |
| Step 5 cross_check | 0–3 per implicated factor | stops at the first dimension that concentrates |

`revenue` with one implicated factor ≈ **9 queries**; a factor metric such as
`fill_rate` ≈ **5**. Registry reads (`metric_def`, `metric_dim_map`,
`replay_clock`) are extra but never touch the event table.

Measured aggregate over a 5-minute window: 43 queries, 369M rows read, slowest
6.3 s — but that window also contains the HyperDX alert evaluations firing every
minute, so **do not quote it as per-investigation cost.**

---

## 6. Things to say before a judge finds them

The brief scores honesty (*"shows which possibilities were checked and cleared"*)
and punishes crying wolf. These are real and it is much better to raise them.

### A false positive we know about

`rca-fill_rate-9cd096bf` flagged `os_version=Android 15` at z=6.3 **after** the
incident window had ended. This is the baseline-contamination artifact already
documented in `architecture.md`: a trailing baseline that contains the incident
makes the *recovery* read as an anomaly in the opposite direction.

The fix — exclude already-flagged buckets from future baselines — is designed and
not built. Say that plainly. The marginal tile is what made it visible.

### Why `ctr` and `render_rate` are not alerted on

From `docs/RCA_AGENT_DESIGN.md` §2.2:

| metric | worst incident z | noise floor | separation |
|---|---|---|---|
| fill_rate | 28.1 | ~2.1 | ~13× |
| requests | 11.2 | ~2.0 | ~5.5× |
| eCPM | 10.9 | ~1.7 | ~6.3× |
| render_rate | ~2.0 | ~2.0 | ~1× |
| ctr | ~2.5 | ~3.3 | **<1×** |

`ctr`'s noisiest clean day scores *higher* than its worst real incident, so any
threshold either fires on noise or catches nothing. Confirmed again today: a
`ctr` marginal tile flagged `device_model=Galaxy S23` at a contribution of **9**.
That is now encoded as `metric_def.alertable`, so the decision is registry data
and a judge can read it.

`render_rate` still earns its keep — it is a factor that gets *cleared* during
decomposition, which is evidence, just not a detector.

### Platform limits we work within

- ClickStack's alert interval enum bottoms out at **`1m`** — there is no seconds
  option, so a compressed replay cannot be alerted on at its own pace. At
  `bucket_seconds=2` one evaluation covers 30 data-hours, and
  `metric_sql.lookback_buckets()` widens the agent's window to match.
- A `line` tile alert **must** reference an interval macro; a `number` tile is
  never substituted with one. Both require the window macros.
- The webhook *body* template supports only `{{title}}/{{body}}/{{link}}`, but the
  alert *message* also substitutes `{{group}}` and `{{value}}` — which is how the
  firing slice reaches the agent without one tile per dimension.

### Scope honesty

Depth-3 is not built. The dependency walk goes one level down from the leading
cut and stops; a pair that is still too broad is reported as a pair. The
dependency walk is skipped on additive metrics (`requests`, `revenue`) with a
recorded reason, because an inside-vs-outside comparison needs a rate.

---

## 7. Corrections to the other presentation files

Apply these before rehearsing.

| File | Says | Should say |
|---|---|---|
| `DEMO_SCRIPT.md` Act 2 | `curl … localhost:3002/webhooks/alerts` | **`localhost:8000`** — 3002 returns 404, this breaks the demo |
| `UNSEEN_INCIDENT_PLAN.md` Phase 2 | four curls to `:3002` | **`:8000`** for all four |
| `UNSEEN_INCIDENT_PLAN.md` Phase 1 | `./scripts/replay.sh --data` then done | add `./scripts/compress_replay.py --bucket-seconds 2` **and** `./scripts/provision_alerts.py --apply` |
| `UNSEEN_INCIDENT_PLAN.md` Phase 3 | `docker compose logs rca-api` | **`rca-agent`** — the investigation runs there |
| `SCREENSHOTS_CHECKLIST.md` #26 | "39 tests passing" | **57 test functions**; the count was never re-verified after the rewrite |
| `SCREENSHOTS_CHECKLIST.md` "How to capture" | `docker compose logs rca-api` | **`rca-agent`** |
| `TALKING_POINTS.md` HyperDX Q&A | "one chart per alertable metric … on the ALL bucket" | three tile kinds, §2 |
| `TALKING_POINTS.md` §1 | implies zero false positives | name the recovery false alert, §6 |
| `SLIDE_TEMPLATE.md` slide 8 | 3-column detections table | add the "global tile fires?" column — it is the best slide in the deck |
| `SLIDE_TEMPLATE.md` slide 3 | "5 layers" only | still true; add that detection now has global + marginal + freshness |
| `DEMO_SCRIPT.md` Act 3 step 1 | "peak z of -9.17" | **11.42** on this build |
| `UNSEEN_INCIDENT_PLAN.md` troubleshooting | "anomaly window may not overlap the 24h lookback" | the window is now 24 **data-hours**, widened to cover one alert evaluation; under compression 24 real hours would span the entire dataset |

---

## 8. Unseen-incident runbook (corrected)

Supersedes Phases 1–2 of `UNSEEN_INCIDENT_PLAN.md`.

```bash
# 1. point replay.sh at the new file (edit AD_EVENTS_FILE), then
./scripts/replay.sh --data

# 2. verify
#    SELECT count(), min(event_time), max(event_time) FROM inmobi.ad_events_enriched;

# 3. compress so 840 data-hours stream past a live alert in 28 minutes
./scripts/compress_replay.py --bucket-seconds 2

# 4. re-render every tile against the new clock  — NOT OPTIONAL
./scripts/provision_alerts.py --apply

# 5. either wait for HyperDX (alerts evaluate every 1m), or trigger directly:
for m in fill_rate revenue ecpm requests; do
  curl -sS -X POST http://localhost:8000/webhooks/alerts \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"$m alert\",\"body\":\"metric_id=$m scope=global\"}"; echo
done

# 6. evidence
docker compose logs rca-agent --tail 500 > presentation/fallback_data/unsealed_logs.txt
cp data/rca_reports/*.json presentation/fallback_data/
```

**Timing note.** The baseline needs 8 same-hour-of-day points before it can score
anything — 8 data-days = 192 data-hours = **6.4 minutes** of warm-up at
`bucket_seconds=2`. Nothing fires before that. Budget for it; do not conclude the
system is broken.

`compress_replay.py` is re-runnable: it detects an already-compressed input and
inverts it via `replay_clock` rather than re-reading the calendar. Running it
twice is safe. (Before today it was not — it would have collapsed all 840 buckets
into one.)

---

## 9. Known environment traps

These cost real time today.

- **The webhook is a cloudflare quick tunnel and gets a new hostname on every
  restart.** A dead tunnel presents as `Failed to send webhook notification` on
  every alert while the tiles themselves are perfectly healthy. The path must end
  `/webhooks/alerts`; it was once stored as the literal `/****` and 404'd every
  delivery. If the tunnel cannot be restarted, POST to
  `http://localhost:8000/webhooks/alerts` — the alert state and tile SQL are
  still real, only the transport is stood in for.
- **PyPI is unreachable from some shells on this machine** (TLS-intercepting
  proxy; curl trusts the CA via the macOS keychain, Python/pip do not). This
  breaks `uv run pytest` and `docker compose build` from those shells. Run them
  from a normal terminal.
- **`docker compose build` must be re-run after any `RCA/app/*.py` change** —
  source is baked into the image, not mounted.

---

## 10. Evidence inventory

| Artifact | Location |
|---|---|
| RCA reports (14, incl. both Android 15 runs) | `data/rca_reports/*.json` |
| Detection layer spec, as pushed | `docs/rca_detection_dashboard.json` |
| HyperDX dashboard | `RCA Detection`, `6a6eba8ea561469a8f4eef82` |
| Langfuse | keys and base URL configured in `.env`; one trace per investigation |
| Architecture, as-built | `architecture.md`, `docs/REPLAY_CLOCK.md`, `docs/RCA_AGENT_DESIGN.md` |
| Decomposition derivation | `docs/RCA_DECOMPOSITION_MATH.md` |

For `presentation/fallback_data/`, the two reports worth copying are
`rca-fill_rate-4cb1b382` (unhinted — full candidate list **and** the ruled-out
ledger) and `rca-fill_rate-3eeba4bb` (hinted). Prefer the unhinted one on slides:
it shows what was cleared.
