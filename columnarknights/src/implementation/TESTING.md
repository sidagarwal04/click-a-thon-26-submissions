# Testing checklist — for tomorrow's real batch dataset

Prepared in advance of receiving the real (unseen) dataset. Two parts: a
pre-flight validation already run against a synthetic dataset (below), and a
checklist to run through once the real data lands.

## Pre-flight: synthetic dataset with known ground truth

Before the real data arrives, the pipeline was validated end-to-end (real
ClickHouse queries, real drill-down, real LLM narration — not mocked)
against a synthetic dataset with 4 deliberately planted anomalies whose
ground truth is known in advance:

```bash
python3 scripts/generate_test_dataset.py   # writes data/test_ad_events.parquet
                                            # + test_data_ground_truth.json
scripts/load_test_dataset.sh               # loads into clickathon_test -- a
                                            # separate database, never touches
                                            # the real one configured in .env
python3 scripts/validate_test_dataset.py   # runs the real pipeline, checks its
                                            # answers against the planted ground truth
```

**Result:** attribution (the actual root-cause finding — dimension, value,
depth) was **100% correct on all 4 scenarios**, including a two-level nested
case (category=finance → ad_format=video). Found and fixed one real bug
along the way: `pipeline.scan()` could return incidents dated before its own
requested `start` (its lookback buffer wasn't filtered back out) — fixed,
doesn't affect the dashboard's default full-range scan but would have on any
narrower one.

**Known limitation surfaced, not a bug to chase further right now:** a
borderline day within a real anomaly's window can occasionally not clear
`scan()`'s aggregate detection threshold, if that day's trailing
same-weekday history happens to have a coincidental noisy drift that the OLS
trend fit absorbs. This is more likely on noisy, low-count metrics (CTR
especially — clicks are rare events). **`investigate()` on the correct
window still finds the right answer regardless** — this only affects
whether `scan()` auto-flags it, not whether investigating a known date range
works. Practical implication for tomorrow: if a judge names a specific
date/metric that doesn't show up in the auto-scanned incident list, don't
conclude it's broken — manually investigate that exact window first
(`rca investigate --metric X --start Y --end Z`, or `POST /api/investigate`)
before assuming detection missed something real.

## Checklist once the real dataset lands

### 1. Data sanity, before loading
- [ ] Confirm column schema matches: `event_time, app_id, geo_device_id, advertiser_id, ad_format, is_filled, is_impression, is_click, revenue`
- [ ] Confirm whether new `apps.csv`/`advertisers.csv`/`geo_device.csv` are provided, or the existing ones still apply
- [ ] Row count and date range sanity (`min(event_time)`, `max(event_time)`, `count()`) — is it the scale you expect?
- [ ] Funnel consistency: `is_impression=1` should imply `is_filled=1`; `is_click=1` should imply `is_impression=1`. If this doesn't hold, the rate calculations (`fill_rate`, `render_rate`, `ctr`) will misbehave.
- [ ] `revenue` should be `0` wherever `is_impression=0` (the eCPM formula assumes revenue only accrues on impressions — a click-based or install-based cost model would need `attribution._FACTOR_FIELD_MAP`/`_num_den` revisited).

### 2. Loading
- [ ] If the new file isn't named `ad_events.parquet`, either rename it or update the hardcoded filename in `scripts/load_data.sh`
- [ ] Run `scripts/load_data.sh` (⚠️ **destructive** — drops and recreates `apps`/`advertisers`/`geo_device`/`ad_events_raw`/`fact_events` in whichever `CLICKHOUSE_DATABASE` is in `.env`. Double-check that's the real database, not `clickathon_test`.)
- [ ] Confirm `fact_events` row count == `ad_events_raw` row count (no silent join drops)

### 3. Pipeline functional checks
- [ ] `rca scan` across the full loaded range, for each of the 5 default metrics — does it return a plausible number of incidents (not zero across the board, not hundreds)?
- [ ] For each detected incident, `rca investigate` — narrative reads sensibly, decomposition's `revenue_delta` sign matches the stated direction, drill-down either localizes to a specific segment or explicitly says broad-based (never silently empty/wrong)
- [ ] `rca latency-report` — confirm p50/p95/p99 are still in the "seconds" ballpark on this dataset's actual size; the LLM-narration tail latency (free-tier rate limits) is the one to watch
- [ ] Severity/confidence sanity: no negative percentages, confidence always 0-100 or `None` for broad-based (already clamped server-side, but worth eyeballing on real data)

### 4. UI checks
- [ ] Dashboard loads, KPI tiles show real numbers matching what you'd compute by hand from `/api/incidents`
- [ ] Chart renders with the baseline dashed line for the new date range
- [ ] Click into a few incidents of different shapes (localized 1-level, localized 2-level, broad-based) — Investigation Path tree renders correctly for each
- [ ] Download / Export / Langfuse trace / Follow-up AI buttons still work against real data
- [ ] "Scan for incidents" completes without timing out (real ClickHouse Cloud round-trip latency, not local)

### 5. Edge cases worth being aware of (not necessarily bugs)
- [ ] The earliest ~2-4 weeks of any new date range will have partial or no baseline (not enough same-weekday history yet) — `baseline_expected` will legitimately be `null` there. Expected behavior, not a bug.
- [ ] A real issue confined to a very small segment (a few % of volume) may not move the *aggregate* metric enough to trigger `scan()` at all, even though drilling into that specific segment would show it clearly — there's no general fix for this beyond knowing to check a named segment directly if asked.
- [ ] Brand-new dimension values (countries/os_versions/ad_formats not seen in the sample data) are handled automatically — `DIMENSIONS` is a fixed list of *dimension names*, not allowed *values*, so nothing needs to change for new values within them.

### 6. Rollback safety
- The synthetic validation lives entirely in a separate `clickathon_test` ClickHouse database — safe to leave alongside the real `clickathon` database, or drop it once no longer needed. Loading the real batch dataset never touches it.
