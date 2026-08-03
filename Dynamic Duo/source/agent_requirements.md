# RCA Agent — Requirements

## Data model

- One row in `ad_events` = one ad request. Funnel is strictly sequential — four states only:
  - `is_filled=0` — unfilled (22%): auction ran, no advertiser bid or bid below floor
  - `is_filled=1, is_impression=0` — filled, never rendered on device (1.6%)
  - `is_filled=1, is_impression=1, is_click=0` — impression, no click (75.7%)
  - `is_filled=1, is_impression=1, is_click=1` — click (0.8%)
- `advertiser_id` empty when `is_filled=0` → filter `is_filled=1` before any vertical/campaign_type metric
- Revenue is earned at impression

## Metrics — always sum/sum over the full window, never averages of ratios

| metric | formula |
|---|---|
| fill_rate | `sum(is_filled) / count(*)` |
| render_rate | `sum(is_impression) / sum(is_filled)` |
| CTR | `sum(is_click) / sum(is_impression)` |
| eCPM | `sum(revenue) / sum(is_impression) * 1000` |
| RPR | `sum(revenue) / count(*)` |

## Revenue identity — decompose first, sweep second

```
Revenue = Requests × Fill rate × Render rate × eCPM / 1000
```

Compare each lever incident vs baseline; sweep dimensions only for the lever that moved.

| lever moved | problem | dimensions to sweep |
|---|---|---|
| Requests | volume | `region`, `country`, `category`, `publisher_tier`, `app_id` |
| Fill rate | demand (no bids) | `vertical`, `campaign_type`, `ad_format`, `region`, `os_version`, `device_model` |
| Render rate | device/SDK | `device_model`, `os_version`, `ad_format` |
| eCPM | price | `vertical`, `campaign_type`, `ad_format`, `publisher_tier` |
| CTR (context signal only) | engagement | `category`, `publisher_tier`, `ad_format`, `device_model` |

Two levers moved → investigate each independently, check if one segment explains both.

**Example (Jun 23–25):** requests +4%, render/eCPM flat, fill −3.44 pp → sweep fill dims only → `Android 15` (fill 0.43 vs 0.79, 98% of the drop). Other levers ruled out without touching their dimensions.

## Dimensions

| column | table | values |
|---|---|---|
| `ad_format` | `ad_events` | banner, interstitial, native, rewarded, video |
| `category` | `apps` | 7 values (gaming … finance) |
| `publisher_tier` | `apps` | tier_1/2/3 |
| `vertical` | `advertisers` | 7 values (gaming … cpg) |
| `campaign_type` | `advertisers` | CPM, CPC, CPI |
| `region` | `geo_device` | NAM, EU, APAC, LATAM, MEA — note `NAM`, not `NA` |
| `country` | `geo_device` | 16 values |
| `device_model` | `geo_device` | 8 values |
| `os_version` | `geo_device` | 8 values (iOS 16.4–18.1, Android 12–15) |

`app_id` (2K) / `advertiser_id` (500) — sweep only when the above find nothing; raise volume floor.

## Investigation sequence

1. **Detect** — metric vs same-weekday baseline (alert or on-demand)
2. **Decompose** — revenue identity → which lever; log shares give each lever's exact % of
   the revenue move (rank when several cross thresholds); no lever moved = `SEASONAL_EXPECTED`, report + close
3. **Sweep** — segments ranked by contribution (weight × delta), for the moved lever only
4. **Mix-shift gate** — all sweep deltas ≈ 0? split within/mix/interaction before ever
   declaring GLOBAL; `|mix|` dominant = traffic reshuffle, find whose share changed
5. **Confounder-eliminate** — exclude top candidate, re-run other dims; residuals collapse = shadows
6. **Narrate** — LLM writes prose from query results only

## Verdict rules

- Name segment + numbers; "fill rate dropped" alone = 0 points
- Rank by contribution, not raw delta — a tiny segment with a huge delta can explain nothing
- Uniform move across every dim (no segment ≥50% of it) → `GLOBAL`, never force-name a segment
- Every clean dimension recorded: name + max residual → OTel span + narrative ("checked and ruled out")

## Parameterize from the row — the agent never dismisses

Every incident (sweep or live-triggered targeted sweep) arrives classifier-passed with a
bucket-merged window. The agent's job is measurement; wrong parameterization is the main
way a correct incident measures as "nothing":

- **Scope** — segment-scoped row → scoped q1 from the start (−20 pp in a 7%-share
  country = −1.4 pp global: invisible unscoped)
- **Grain** — window < 24 h → whole-day q1 dilutes it (3 h of a −3.4 pp incident =
  −0.43 pp daily) → measure on the row's hour window, not calendar days
- **Metric** — `ctr` is not a revenue lever → skip the lever gate, q2a(clicks/impressions) directly
- **Trend-model incidents** — the ramp sits inside q1's own baseline pool (ramp days not
  yet diagnosed) → first-half vs second-half comparison is the right measurement

If the correctly-parameterized q1 still shows no lever: **DISAGREEMENT flag** — log both
sides' numbers, human eyes. The agent issues no seasonality verdicts and no dismissals;
`ruled_out_seasonal` comes from the detector's classifier (the agent narrates it).

## Latency budget — "diagnosed in seconds" is scored

Target ≈ 4 s: SQL < 0.5 s + one LLM call (~3 s).

- ≈ 10 queries in 3 round-trips: q6+q1 serial → q2 ×6 parallel → q3 ×~3 parallel
  (short-history path swaps q4 in for q2; live path identical after the targeted sweep)
- No boundary queries — windows are detection's output in both modes (q0 deleted;
  segment-level onset detail, if narrated, comes from detection's own scored buckets)
- q4 only when min_clean_days < 2 — there it does both jobs: peer sweep, then a second
  pass with the outlier excluded as the confound analog (q2/q3/q5 all need baseline
  windows that don't exist on a short slice)
- q3 only for dims that showed signal in q2 (flat dims are ruled out by their q2 numbers)
- q5 only on all-flat sweep or failed additivity assert
- Rollup variant on the hot path (q2a)
- Never investigate twice: deterministic incident_id + q6 verdicts short-circuit re-fired alerts
- **Zero LLM-in-the-loop** — the LLM appears once, at the end, with the finished bundle

## History-free path — required for unseen incident

Unseen slice may have no trailing history. Peer comparison (segment vs sibling median, same window, ratio metrics only) must work standalone.

## Windows & baselines (noise measured on normal days Jun 1–18)

Hourly global (~10.7K req): fill 0.41 pp, eCPM 1.0%, CTR 11.6%. Per-os-segment hourly: fill 1.2 pp. Daily global: fill 0.07 pp, CTR 1.6%.

- **Fast alert**: trailing 1h, every 5–15 min — requests (>15%), fill (>2 pp), eCPM (>3–5%). Never CTR.
- **Slow alert**: daily — all metrics incl. CTR (>5%); catches multi-day drifts invisible hourly (Jun 28–30 −1.2 pp)
- **Boundaries**: after alert, hourly scan → onset/offset → investigate the full span, not the alert window
- **Segment trust floor**: ≥10K requests in-window for tight thresholds; below that only large deltas count
- **Baselines**: same weekday (hourly: + same hour), trailing 4 weeks, median **per weekday** then weighted by the window's weekday mix — never pooled across weekday types, never a flat average, never a single prior week. Excluded dates = the detector's own past verdicts, applied chronologically; ≥2 clean days per weekday or fall back to peer comparison

## LLM & traceability

- LLM: query results in, one paragraph out. No computation, no raw rows. A number not returned by a query = fabricated = worse than a miss.
- Every step = one OTel span: SQL, params, result numbers, verdict. Trace id stored on the diagnosis. No trace = no credit.

## Unseen-data robustness — dev data is NOT the source of truth

The 5 dev anomalies are all clean single-dimension step-changes. The unseen slice owes us
nothing. Cases the agent must survive:

- **Mix shift** — global ratio moves, no segment's own rate changed (traffic reshuffled
  between segments). Q2 reads it as "uniform" → run mix-shift check (Q5) before ever
  declaring GLOBAL; if mix dominates, find whose share changed instead
- **Interaction segments** — cause = `Android 15 × EU`, not one dimension value. Signature:
  Q3 residuals shrink but don't collapse → drill the cross of the top-2 candidates
- **Multiple simultaneous incidents** — after CAUSE_CONFIRMED, re-run Q1 excluding the
  confirmed segment; if a lever still moves, open a second investigation
- **Spikes, not just drops** — thresholds are `abs()`; narrative must handle up-moves
  (bot traffic = request spike; click fraud = CTR spike with flat revenue)
- **Slow ramps** — a drift over days evades step detection; compare first half vs second
  half of the window as a trend check
- **Partial-day onset** — never assume whole days; hourly boundary scan first
- **New dimension values** — `Android 16`, unseen countries: LEFT JOIN + `unknown` bucket,
  never inner join (silently drops the very events that changed)
- **Different scale/seasonality** — nothing hardcoded: no absolute volumes, no weekend
  factor; everything relative to baselines computed from the slice itself; verify the
  diurnal curve before trusting hour-of-day baselines
- **No history at all** — peer comparison (Q4) is the primary detector, already required

## Data validation on load — run BEFORE any investigation

Assumptions verified on dev data that may not hold on unseen data; each violation changes
interpretation:

- Funnel invariants: no click without impression, no impression without fill
- Revenue only on `is_impression=1` rows (else eCPM formula needs a filter)
- `advertiser_id` empty ⟺ `is_filled=0`
- Dim coverage: % of events whose keys miss the dim tables (feeds `unknown` bucket)
- Hourly continuity: gaps = ingestion holes (a "volume drop" that's actually missing data)
- Duplicate check: sudden 2× volume with identical rows = double ingestion, not real traffic

## Performance

- Every query returns in seconds; slow query = fix schema first
- Planned: `event_date Date MATERIALIZED`, `ORDER BY (event_date, app_id)`, monthly partitions
