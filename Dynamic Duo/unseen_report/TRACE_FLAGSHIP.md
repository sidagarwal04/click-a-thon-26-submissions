# Flagship trace — `inc_20260708T00_fill_rate_global`

The complete, system-written investigation record for the unseen slice's headline incident (the Jul 8–9 global fill-rate trench). Every row below is one entry in `rca.investigation_steps`, exactly as the runner logged it — hypothesis, the exact SQL, the result rows it saw, and the decision it took. The other ten incidents' traces are in [`traces_investigation_steps.jsonl`](traces_investigation_steps.jsonl).

**Verdict** `INTERACTION` · numbers_verified: `True` · trace id `inc_20260708T00_fill_rate_global-run-8ab8f0b4`

> Global fill_rate downturn driven by iOS 17.5 × iPhone 13 interaction, magnitude 0.0095 residual. Checked dimensions: os_version, device_model, region, ad_format; all residuals ruled out except interac

---

### step 00 · detect · 2026-08-02 03:41:55.275 · 0 ms

**Hypothesis:** sweep[day] global fill_rate: 2 flagged day(s), source=primary

*-- detector/sql/score_day params: pre_z=2.5, naive_z=3.0; gates: z_hi=3.0, practical=('abs', 0.005), vol_floor=2000*

**Result:** `{"model_median_z": {"naive": -8.21, "hod": null, "how": -0.5, "stl": -3.25, "flat": -13.48, "primary": -13.48}, "corroborating": [{"scope": "global", "metric": "fill_rate", "grain": "hour", "window": ["2026-07-08 00:00:00", "2026-07-10 00:00:00"], "z": -10.89, "verdict": "anomaly"}, {"scope": "global", "metric": "ecpm", "grain": "day", "window": ["2026-07-06 00:00:00", "2026-07-11 00:00:00"], "z": -25.93, "verdict": "anomaly"}, {"scope": "global", "metric": "ecpm", "grain": "hour", "window": ["2026-07-06 00:00:00", "2026-07-11 00:00:00"], "z": -10.2, "verdict": "anomaly"}, {"scope": "country=AR", "metric": "revenue", "grain": "hour", "window": ["2026-07-08 19:00:00", "2026-07-09 03:00:00"], "z": -6.73, "verdict": "anomaly"}, {"scope": "country=AR", "metric": "revenue", "grain": "hour", "window": ["2026-07-07 14:00:00", "2026-07-07 16:00:00"], "z": 6.13, "verdict": "anomaly"}, {"scope": "device_model=Pixel 8", "metric": "revenue", "grain": "hour", "window": ["2026-07-07 07:00:00", "2026-07-07 14:00:00"], "z": 6.12, "verdict": "anomaly"}, {"scope": "country=ID", "metric": "revenue", "grain": "hour", "window": ["2026-07-07 05:00:00", "2026-07-07 18:00:00"], "z": 5.99, "verdict": "anom… (truncated; full row in the JSONL export)`

**Decision:** verdict=anomaly -> status=detected; 275 corroborating signal(s) attached

---

### step 01 · rule_out · 2026-08-02 03:43:27.185 · 5 ms

**Hypothesis:** Baseline hygiene: which past dates are already-diagnosed incident windows (they must not contaminate baselines)?

```sql
SELECT groupUniqArray(d) AS excluded_dates
FROM (
  SELECT arrayJoin(
           arrayMap(x -> toDate(window_start) + x,
                    range(toUInt32(dateDiff('day', toDate(window_start),
                                            toDate(window_end)) + 1)))) AS d
  FROM rca.incidents FINAL
  WHERE status = 'diagnosed'
    AND incident_id IN (
      SELECT incident_id FROM rca.diagnoses FINAL
      WHERE verdict_code IN ('CAUSE_CONFIRMED', 'INTERACTION', 'MIX_SHIFT',
                             'MIX_INTERACTION', 'DEMAND_PULLOUT',
                             'VOLUME_CANDIDATE', 'GLOBAL_MOVEMENT')
    )
    AND toDate(window_start) < {before_date:Date}
)
WHERE d < {before_date:Date}
```

**Result:** `{"excluded_dates": ["2026-06-17", "2026-06-18", "2026-06-19", "2026-06-20", "2026-06-21", "2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25", "2026-06-26", "2026-06-28", "2026-06-29", "2026-06-30", "2026-07-05", "2026-07-06", "2026-07-07"], "readmitted_dates": ["2026-07-01"]}`

**Decision:** 16 date(s) excluded from baselines: ['2026-06-17', '2026-06-18', '2026-06-19', '2026-06-20', '2026-06-21', '2026-06-22', '2026-06-23', '2026-06-24', '2026-06-25', '2026-06-26', '2026-06-28', '2026-06-29', '2026-06-30', '2026-07-05', '2026-07-06', '2026-07-07']; re-admitted ['2026-07-01'] to keep every weekday's pool >= 2 (hygiene must not starve baselines)

---

### step 02 · decompose · 2026-08-02 03:43:27.375 · 182 ms

**Hypothesis:** Which lever of Revenue = Requests × Fill × Render × eCPM moved over ['2026-07-08', '2026-07-09'] (scope global)?

```sql
WITH
  inc_dates AS (
    SELECT event_date AS d, toDayOfWeek(event_date) AS dow
    FROM rca.ad_events_enriched
    WHERE event_date IN ({flagged_dates:Array(Date)}) AND dataset IN ({datasets:Array(String)})
    GROUP BY d
  ),
  base_days AS (
    SELECT event_date AS d, toDayOfWeek(event_date) AS dow
    FROM rca.ad_events_enriched
    WHERE dataset IN ({datasets:Array(String)})
      AND toDayOfWeek(event_date) IN (SELECT DISTINCT dow FROM inc_dates)
      AND event_date <  (SELECT min(d) FROM inc_dates)
      AND event_date >= addWeeks((SELECT min(d) FROM inc_dates), -4)
      AND event_date NOT IN ({excluded_dates:Array(Date)})
    GROUP BY d, dow
  ),
  inc AS (
    SELECT count() AS req, sum(is_filled) AS fills,
           sum(is_impression) AS imps, sum(revenue) AS rev
    FROM rca.ad_events_enriched
    WHERE event_date IN (SELECT d FROM inc_dates) AND dataset IN ({datasets:Array(String)}) AND 1
  ),
  base_per_day AS (
    SELECT event_date AS d, toDayOfWeek(event_date) AS dow,
           count() AS req, sum(is_filled) AS fills,
           sum(is_impression) AS imps, sum(revenue) AS rev
    FROM rca.ad_events_enriched
    WHERE event_date IN (SELECT d FROM base_days) AND dataset IN ({datasets:Array(String)}) AND 1
    GROUP BY d, dow
  ),
  base_per_dow AS (
    SELECT dow, median(req) AS req, median(fills) AS fills,
           median(imps) AS imps, median(rev) AS rev
    FROM base_per_day GROUP BY dow
  ),
  inc_dow_counts AS (SELECT dow, count() AS n FROM inc_dates GROUP BY dow),
  base AS (
    SELECT sum(b.req * i.n) AS req, sum(b.fills * i.n) AS fills,
           sum(b.imps * i.n) AS imps, sum(b.rev * i.n) AS rev
    FROM base_per_dow b JOIN inc_dow_counts i USING (dow)
  ),
  pool_check AS (SELECT dow, count() AS clean_days FROM base_per_day GROUP BY dow),
  lg AS (
    SELECT log(inc.req / base.req)                                  AS d_req,
           log((inc.fills / inc.req)   / (base.fills / base.req))   AS d_fill,
           log((inc.imps  / inc.fills) / (base.imps  / base.fills)) AS d_render,
           log((inc.rev   / inc.imps)  / (base.rev   / base.imps))  AS d_ecpm,
           log(inc.rev / base.rev)                                  AS d_rev,
           isFinite(d_req + d_fill + d_render + d_ecpm + d_rev)     AS shares_valid
    FROM inc, base
  )
SELECT
  round((inc.req / base.req - 1) * 100, 2)                                        AS requests_pct,
  round((inc.fills/inc.req - base.fills/base.req) * 100, 3)                       AS fill_rate_delta_pp,
  round((inc.imps/nullIf(inc.fills,0) - base.imps/nullIf(base.fills,0)) * 100, 3) AS render_rate_delta_pp,
  round(inc.rev/nullIf(inc.imps,0)*1000 - base.rev/nullIf(base.imps,0)*1000, 4)   AS ecpm_delta,
  round((inc.rev / base.rev - 1) * 100, 2)                                        AS revenue_pct,
  round(inc.fills / inc.req, 4)                                                   AS inc_fill_rate,
  round(base.fills / base.req, 4)                                                 AS base_fill_rate,
  inc.req                                                                         AS inc_requests,
  round(base.req, 0)                                                              AS base_requests_expected,
  if(abs(lg.d_rev) < 0.01 OR NOT lg.shares_valid, NULL, round(lg.d_req    / lg.d_rev * 100, 1)) AS log_share_requests,
  if(abs(lg.d_rev) < 0.01 OR NOT lg.shares_valid, NULL, round(lg.d_fill   / lg.d_rev * 100, 1)) AS log_share_fill,
  if(abs(lg.d_rev) < 0.01 OR NOT lg.shares_valid, NULL, round(lg.d_render / lg.d_rev * 100, 1)) AS log_share_render,
  if(abs(lg.d_rev) < 0.01 OR NOT lg.shares_valid, NULL, round(lg.d_ecpm   / lg.d_rev * 100, 1)) AS log_share_ecpm,
  round(lg.d_rev, 4)                                                              AS revenue_log_delta,
  (SELECT min(coalesce(p.clean_days, 0))
   FROM inc_dow_counts i LEFT JOIN pool_check p USING (dow))                      AS min_clean_days_per_dow,
  (SELECT groupArray(d) FROM (SELECT d FROM base_days ORDER BY d))                AS base_days_used
FROM inc, base, lg
```

**Result:** `{"requests_pct": 8.46, "fill_rate_delta_pp": -5.283, "render_rate_delta_pp": -0.057, "ecpm_delta": -0.2322, "revenue_pct": -8.37, "inc_fill_rate": 0.7319, "base_fill_rate": 0.7847, "inc_requests": 602668, "base_requests_expected": 555638, "log_share_requests": -92.9, "log_share_fill": 79.7, "log_share_render": 0.7, "log_share_ecpm": 112.6, "revenue_log_delta": -0.0874, "min_clean_days_per_dow": 2, "base_days_used": ["2026-06-10", "2026-06-11", "2026-07-01", "2026-07-02"]}`

**Decision:** requests 8.46%, fill -5.283 pp, render -0.057 pp, eCPM -0.2322$; min_clean_days 2 → lever(s) moved: ['fill_rate'] → sweep their dimensions

---

### step 03 · dim_scan · 2026-08-02 03:43:27.461 · 76 ms

**Hypothesis:** Sweep fill_rate by vertical: which segment moved, weighted by its share of the denominator?

```sql
WITH per_day AS (
  SELECT vertical AS seg, event_date AS d, toDayOfWeek(event_date) AS dow,
         sum(is_filled) AS vol
  FROM rca.ad_events_enriched
  WHERE (event_date IN ({inc_dates:Array(Date)}) OR event_date IN ({base_dates:Array(Date)}))
    AND dataset IN ({datasets:Array(String)})
    AND is_filled = 1
  AND 1
  GROUP BY seg, d, dow
),
inc_dow AS (
  SELECT dow, count(DISTINCT d) AS n FROM per_day
  WHERE d IN ({inc_dates:Array(Date)}) GROUP BY dow
),
base_med AS (
  SELECT seg, dow, median(vol) AS med FROM per_day
  WHERE d IN ({base_dates:Array(Date)}) GROUP BY seg, dow
),
expected AS (
  SELECT b.seg, sum(b.med * i.n) AS vol_expected
  FROM base_med b JOIN inc_dow i USING (dow) GROUP BY b.seg
),
actual AS (
  SELECT seg, sum(vol) AS vol_inc FROM per_day
  WHERE d IN ({inc_dates:Array(Date)}) GROUP BY seg
)
SELECT
  a.seg,
  a.vol_inc,
  round(e.vol_expected, 0)                                             AS vol_expected,
  round((a.vol_inc / e.vol_expected - 1) * 100, 2)                     AS pct_change,
  round((a.vol_inc - e.vol_expected)
        / sum(a.vol_inc - e.vol_expected) OVER () * 100, 1)            AS share_of_total_change
FROM actual a
JOIN expected e USING (seg)
ORDER BY pct_change
```

**Result:** `[{"seg": "entertainment", "vol_inc": 62652, "vol_expected": 95605, "pct_change": -34.47, "share_of_total_change": -650.2}, {"seg": "auto", "vol_inc": 58948, "vol_expected": 72836, "pct_change": -19.07, "share_of_total_change": -274}, {"seg": "finance", "vol_inc": 64439, "vol_expected": 68952, "pct_change": -6.54, "share_of_total_change": -89}, {"seg": "travel", "vol_inc": 48862, "vol_expected": 51858, "pct_change": -5.78, "share_of_total_change": -59.1}, {"seg": "gaming", "vol_inc": 25363, "vol_expected": 25671, "pct_change": -1.2, "share_of_total_change": -6.1}, {"seg": "ecommerce", "vol_inc": 118777, "vol_expected": 80258, "pct_change": 47.99, "share_of_total_change": 760.1}, {"seg": "cpg", "vol_inc": 62046, "vol_expected": 40840, "pct_change": 51.93, "share_of_total_change": 418.4}]`

**Decision:** top mover: ecommerce 47.99% vs expected (760.1% of total change); per-segment range -34.47%..51.93%

---

### step 04 · dim_scan · 2026-08-02 03:43:27.467 · 74 ms

**Hypothesis:** Sweep fill_rate by campaign_type: which segment moved, weighted by its share of the denominator?

```sql
WITH per_day AS (
  SELECT campaign_type AS seg, event_date AS d, toDayOfWeek(event_date) AS dow,
         sum(is_filled) AS vol
  FROM rca.ad_events_enriched
  WHERE (event_date IN ({inc_dates:Array(Date)}) OR event_date IN ({base_dates:Array(Date)}))
    AND dataset IN ({datasets:Array(String)})
    AND is_filled = 1
  AND 1
  GROUP BY seg, d, dow
),
inc_dow AS (
  SELECT dow, count(DISTINCT d) AS n FROM per_day
  WHERE d IN ({inc_dates:Array(Date)}) GROUP BY dow
),
base_med AS (
  SELECT seg, dow, median(vol) AS med FROM per_day
  WHERE d IN ({base_dates:Array(Date)}) GROUP BY seg, dow
),
expected AS (
  SELECT b.seg, sum(b.med * i.n) AS vol_expected
  FROM base_med b JOIN inc_dow i USING (dow) GROUP BY b.seg
),
actual AS (
  SELECT seg, sum(vol) AS vol_inc FROM per_day
  WHERE d IN ({inc_dates:Array(Date)}) GROUP BY seg
)
SELECT
  a.seg,
  a.vol_inc,
  round(e.vol_expected, 0)                                             AS vol_expected,
  round((a.vol_inc / e.vol_expected - 1) * 100, 2)                     AS pct_change,
  round((a.vol_inc - e.vol_expected)
        / sum(a.vol_inc - e.vol_expected) OVER () * 100, 1)            AS share_of_total_change
FROM actual a
JOIN expected e USING (seg)
ORDER BY pct_change
```

**Result:** `[{"seg": "CPM", "vol_inc": 172089, "vol_expected": 264580, "pct_change": -34.96, "share_of_total_change": -1825}, {"seg": "CPI", "vol_inc": 76145, "vol_expected": 85264, "pct_change": -10.69, "share_of_total_change": -179.9}, {"seg": "CPC", "vol_inc": 192853, "vol_expected": 86176, "pct_change": 123.79, "share_of_total_change": 2104.9}]`

**Decision:** top mover: CPC 123.79% vs expected (2104.9% of total change); per-segment range -34.96%..123.79%

---

### step 05 · dim_scan · 2026-08-02 03:43:27.473 · 28 ms

**Hypothesis:** Sweep fill_rate by ad_format: which segment moved, weighted by its share of the denominator?

```sql
SELECT
  value AS seg,
  round(sumIf(fills, toDate(window_start) IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(requests, toDate(window_start) IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                    AS val_inc,
  round(sumIf(fills, toDate(window_start) IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(requests, toDate(window_start) IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                    AS val_base,
  round(val_inc - val_base, 4)                                                 AS delta,
  sumIf(requests, toDate(window_start) IN ({inc_dates:Array(Date)}))        AS den_inc,
  round(den_inc / sum(den_inc) OVER () * (val_inc - val_base) * 100
        / {scale:Float64}, 4)                                                  AS contribution_pp
FROM rca.metrics_hourly_by_dim
WHERE dimension = {dim:String}
  AND value != '(none)'
  AND (toDate(window_start) IN ({inc_dates:Array(Date)})
    OR toDate(window_start) IN ({base_dates:Array(Date)}))
GROUP BY seg
HAVING den_inc > {min_volume:UInt32}
ORDER BY abs(contribution_pp) DESC
```

**Result:** `[{"seg": "banner", "val_inc": 0.767, "val_base": 0.8224, "delta": -0.0554, "den_inc": 209247, "contribution_pp": -1.9235}, {"seg": "native", "val_inc": 0.738, "val_base": 0.7911, "delta": -0.0531, "den_inc": 157446, "contribution_pp": -1.3872}, {"seg": "interstitial", "val_inc": 0.7225, "val_base": 0.7734, "delta": -0.0509, "den_inc": 104838, "contribution_pp": -0.8854}, {"seg": "video", "val_inc": 0.6663, "val_base": 0.7145, "delta": -0.0482, "den_inc": 78912, "contribution_pp": -0.6311}, {"seg": "rewarded", "val_inc": 0.6908, "val_base": 0.7431, "delta": -0.0523, "den_inc": 52225, "contribution_pp": -0.4532}]`

**Decision:** top: banner delta -0.0554 (contribution -1.9235 pp, 36.4% of the global move)

---

### step 06 · dim_scan · 2026-08-02 03:43:27.479 · 28 ms

**Hypothesis:** Sweep fill_rate by region: which segment moved, weighted by its share of the denominator?

```sql
SELECT
  value AS seg,
  round(sumIf(fills, toDate(window_start) IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(requests, toDate(window_start) IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                    AS val_inc,
  round(sumIf(fills, toDate(window_start) IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(requests, toDate(window_start) IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                    AS val_base,
  round(val_inc - val_base, 4)                                                 AS delta,
  sumIf(requests, toDate(window_start) IN ({inc_dates:Array(Date)}))        AS den_inc,
  round(den_inc / sum(den_inc) OVER () * (val_inc - val_base) * 100
        / {scale:Float64}, 4)                                                  AS contribution_pp
FROM rca.metrics_hourly_by_dim
WHERE dimension = {dim:String}
  AND value != '(none)'
  AND (toDate(window_start) IN ({inc_dates:Array(Date)})
    OR toDate(window_start) IN ({base_dates:Array(Date)}))
GROUP BY seg
HAVING den_inc > {min_volume:UInt32}
ORDER BY abs(contribution_pp) DESC
```

**Result:** `[{"seg": "APAC", "val_inc": 0.6777, "val_base": 0.785, "delta": -0.1073, "den_inc": 225927, "contribution_pp": -4.0224}, {"seg": "NAM", "val_inc": 0.7614, "val_base": 0.7848, "delta": -0.0234, "den_inc": 153623, "contribution_pp": -0.5965}, {"seg": "EU", "val_inc": 0.7698, "val_base": 0.785, "delta": -0.0152, "den_inc": 97875, "contribution_pp": -0.2469}, {"seg": "LATAM", "val_inc": 0.7683, "val_base": 0.784, "delta": -0.0157, "den_inc": 88476, "contribution_pp": -0.2305}, {"seg": "MEA", "val_inc": 0.753, "val_base": 0.7836, "delta": -0.0306, "den_inc": 36767, "contribution_pp": -0.1867}]`

**Decision:** top: APAC delta -0.1073 (contribution -4.0224 pp, 76.1% of the global move)

---

### step 07 · dim_scan · 2026-08-02 03:43:27.485 · 26 ms

**Hypothesis:** Sweep fill_rate by os_version: which segment moved, weighted by its share of the denominator?

```sql
SELECT
  value AS seg,
  round(sumIf(fills, toDate(window_start) IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(requests, toDate(window_start) IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                    AS val_inc,
  round(sumIf(fills, toDate(window_start) IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(requests, toDate(window_start) IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                    AS val_base,
  round(val_inc - val_base, 4)                                                 AS delta,
  sumIf(requests, toDate(window_start) IN ({inc_dates:Array(Date)}))        AS den_inc,
  round(den_inc / sum(den_inc) OVER () * (val_inc - val_base) * 100
        / {scale:Float64}, 4)                                                  AS contribution_pp
FROM rca.metrics_hourly_by_dim
WHERE dimension = {dim:String}
  AND value != '(none)'
  AND (toDate(window_start) IN ({inc_dates:Array(Date)})
    OR toDate(window_start) IN ({base_dates:Array(Date)}))
GROUP BY seg
HAVING den_inc > {min_volume:UInt32}
ORDER BY abs(contribution_pp) DESC
```

**Result:** `[{"seg": "iOS 17.5", "val_inc": 0.4772, "val_base": 0.7838, "delta": -0.3066, "den_inc": 115642, "contribution_pp": -5.8831}, {"seg": "Android 14", "val_inc": 0.7935, "val_base": 0.7837, "delta": 0.0098, "den_inc": 71581, "contribution_pp": 0.1164}, {"seg": "iOS 16.4", "val_inc": 0.7921, "val_base": 0.7857, "delta": 0.0064, "den_inc": 101655, "contribution_pp": 0.108}, {"seg": "iOS 17.2", "val_inc": 0.7949, "val_base": 0.7848, "delta": 0.0101, "den_inc": 62466, "contribution_pp": 0.1047}, {"seg": "Android 13", "val_inc": 0.7935, "val_base": 0.7853, "delta": 0.0082, "den_inc": 65754, "contribution_pp": 0.0895}, {"seg": "Android 15", "val_inc": 0.7938, "val_base": 0.7868, "delta": 0.007, "den_inc": 61948, "contribution_pp": 0.072}, {"seg": "iOS 18.1", "val_inc": 0.79, "val_base": 0.7826, "delta": 0.0074, "den_inc": 55407, "contribution_pp": 0.068}, {"seg": "Android 12", "val_inc": 0.7887, "val_base": 0.7849, "delta": 0.0038, "den_inc": 68215, "contribution_pp": 0.043}]`

**Decision:** top: iOS 17.5 delta -0.3066 (contribution -5.8831 pp, 111.4% of the global move)

---

### step 08 · dim_scan · 2026-08-02 03:43:27.490 · 25 ms

**Hypothesis:** Sweep fill_rate by device_model: which segment moved, weighted by its share of the denominator?

```sql
SELECT
  value AS seg,
  round(sumIf(fills, toDate(window_start) IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(requests, toDate(window_start) IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                    AS val_inc,
  round(sumIf(fills, toDate(window_start) IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(requests, toDate(window_start) IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                    AS val_base,
  round(val_inc - val_base, 4)                                                 AS delta,
  sumIf(requests, toDate(window_start) IN ({inc_dates:Array(Date)}))        AS den_inc,
  round(den_inc / sum(den_inc) OVER () * (val_inc - val_base) * 100
        / {scale:Float64}, 4)                                                  AS contribution_pp
FROM rca.metrics_hourly_by_dim
WHERE dimension = {dim:String}
  AND value != '(none)'
  AND (toDate(window_start) IN ({inc_dates:Array(Date)})
    OR toDate(window_start) IN ({base_dates:Array(Date)}))
GROUP BY seg
HAVING den_inc > {min_volume:UInt32}
ORDER BY abs(contribution_pp) DESC
```

**Result:** `[{"seg": "iPhone 14", "val_inc": 0.5972, "val_base": 0.7836, "delta": -0.1864, "den_inc": 133500, "contribution_pp": -4.129}, {"seg": "iPhone 13", "val_inc": 0.7436, "val_base": 0.7852, "delta": -0.0416, "den_inc": 119071, "contribution_pp": -0.8219}, {"seg": "iPhone 15", "val_inc": 0.7368, "val_base": 0.7841, "delta": -0.0473, "den_inc": 82599, "contribution_pp": -0.6483}, {"seg": "Pixel 8", "val_inc": 0.7928, "val_base": 0.7833, "delta": 0.0095, "den_inc": 67750, "contribution_pp": 0.1068}, {"seg": "Pixel 7", "val_inc": 0.7927, "val_base": 0.7845, "delta": 0.0082, "den_inc": 77583, "contribution_pp": 0.1056}, {"seg": "Redmi Note 12", "val_inc": 0.7947, "val_base": 0.7859, "delta": 0.0088, "den_inc": 39086, "contribution_pp": 0.0571}, {"seg": "Galaxy A54", "val_inc": 0.7916, "val_base": 0.7848, "delta": 0.0068, "den_inc": 46806, "contribution_pp": 0.0528}, {"seg": "Galaxy S23", "val_inc": 0.7893, "val_base": 0.7866, "delta": 0.0027, "den_inc": 36273, "contribution_pp": 0.0163}]`

**Decision:** top: iPhone 14 delta -0.1864 (contribution -4.129 pp, 78.2% of the global move)

---

### step 09 · rule_out · 2026-08-02 03:43:27.535 · 31 ms

**Hypothesis:** Is ad_format's apparent movement a shadow of iOS 17.5 (os_version)? Re-sweep ad_format with it excluded.

```sql
SELECT
  ad_format AS seg,
  round(sumIf(is_filled, event_date IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(1, event_date IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                            AS val_inc,
  round(sumIf(is_filled, event_date IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(1, event_date IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                            AS val_base,
  round(val_inc - val_base, 4)                                         AS delta_excl_candidate
FROM rca.ad_events_enriched
WHERE (event_date IN ({inc_dates:Array(Date)}) OR event_date IN ({base_dates:Array(Date)}))
  AND dataset IN ({datasets:Array(String)})
  AND 1
  AND 1
  AND os_version != {candidate_value:String}
GROUP BY seg
ORDER BY delta_excl_candidate
```

**Result:** `[{"seg": "rewarded", "val_inc": 0.7486, "val_base": 0.7429, "delta_excl_candidate": 0.0057}, {"seg": "video", "val_inc": 0.7208, "val_base": 0.7146, "delta_excl_candidate": 0.0062}, {"seg": "interstitial", "val_inc": 0.781, "val_base": 0.7732, "delta_excl_candidate": 0.0078}, {"seg": "banner", "val_inc": 0.8304, "val_base": 0.8223, "delta_excl_candidate": 0.0081}, {"seg": "native", "val_inc": 0.7998, "val_base": 0.7916, "delta_excl_candidate": 0.0082}]`

**Decision:** residual 0.0082 persists ≥ 0.005283000000000001 → not a pure shadow

---

### step 10 · rule_out · 2026-08-02 03:43:27.540 · 31 ms

**Hypothesis:** Is region's apparent movement a shadow of iOS 17.5 (os_version)? Re-sweep region with it excluded.

```sql
SELECT
  region AS seg,
  round(sumIf(is_filled, event_date IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(1, event_date IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                            AS val_inc,
  round(sumIf(is_filled, event_date IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(1, event_date IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                            AS val_base,
  round(val_inc - val_base, 4)                                         AS delta_excl_candidate
FROM rca.ad_events_enriched
WHERE (event_date IN ({inc_dates:Array(Date)}) OR event_date IN ({base_dates:Array(Date)}))
  AND dataset IN ({datasets:Array(String)})
  AND 1
  AND 1
  AND os_version != {candidate_value:String}
GROUP BY seg
ORDER BY delta_excl_candidate
```

**Result:** `[{"seg": "NAM", "val_inc": 0.7911, "val_base": 0.7848, "delta_excl_candidate": 0.0063}, {"seg": "EU", "val_inc": 0.7925, "val_base": 0.7851, "delta_excl_candidate": 0.0074}, {"seg": "MEA", "val_inc": 0.7915, "val_base": 0.7837, "delta_excl_candidate": 0.0078}, {"seg": "LATAM", "val_inc": 0.7924, "val_base": 0.7845, "delta_excl_candidate": 0.0079}, {"seg": "APAC", "val_inc": 0.7937, "val_base": 0.785, "delta_excl_candidate": 0.0087}]`

**Decision:** residual 0.0087 persists ≥ 0.005283000000000001 → not a pure shadow

---

### step 11 · rule_out · 2026-08-02 03:43:27.546 · 37 ms

**Hypothesis:** Is device_model's apparent movement a shadow of iOS 17.5 (os_version)? Re-sweep device_model with it excluded.

```sql
SELECT
  device_model AS seg,
  round(sumIf(is_filled, event_date IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(1, event_date IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                            AS val_inc,
  round(sumIf(is_filled, event_date IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(1, event_date IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                            AS val_base,
  round(val_inc - val_base, 4)                                         AS delta_excl_candidate
FROM rca.ad_events_enriched
WHERE (event_date IN ({inc_dates:Array(Date)}) OR event_date IN ({base_dates:Array(Date)}))
  AND dataset IN ({datasets:Array(String)})
  AND 1
  AND 1
  AND os_version != {candidate_value:String}
GROUP BY seg
ORDER BY delta_excl_candidate
```

**Result:** `[{"seg": "Galaxy S23", "val_inc": 0.7893, "val_base": 0.7866, "delta_excl_candidate": 0.0027}, {"seg": "Galaxy A54", "val_inc": 0.7916, "val_base": 0.7848, "delta_excl_candidate": 0.0068}, {"seg": "iPhone 13", "val_inc": 0.7926, "val_base": 0.7854, "delta_excl_candidate": 0.0072}, {"seg": "iPhone 15", "val_inc": 0.7917, "val_base": 0.7838, "delta_excl_candidate": 0.0079}, {"seg": "Pixel 7", "val_inc": 0.7927, "val_base": 0.7845, "delta_excl_candidate": 0.0082}, {"seg": "iPhone 14", "val_inc": 0.7928, "val_base": 0.784, "delta_excl_candidate": 0.0088}, {"seg": "Redmi Note 12", "val_inc": 0.7947, "val_base": 0.7859, "delta_excl_candidate": 0.0088}, {"seg": "Pixel 8", "val_inc": 0.7928, "val_base": 0.7833, "delta_excl_candidate": 0.0095}]`

**Decision:** residual 0.0095 persists ≥ 0.005283000000000001 → not a pure shadow

---

### step 12 · drill_down · 2026-08-02 03:43:27.567 · 14 ms

**Hypothesis:** Residual persists on device_model: drill the cross os_version=iOS 17.5 × device_model — interaction segment?

```sql
SELECT
  device_model AS seg,
  round(sumIf(is_filled, event_date IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(1, event_date IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                     AS val_inc,
  round(sumIf(is_filled, event_date IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(1, event_date IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                     AS val_base,
  round(val_inc - val_base, 4)                                                  AS delta,
  sumIf(1, event_date IN ({inc_dates:Array(Date)}))                AS den_inc,
  round(den_inc / sum(den_inc) OVER () * (val_inc - val_base) * 100
        / {scale:Float64}, 4)                                                   AS contribution_pp
FROM rca.ad_events_enriched
WHERE (event_date IN ({inc_dates:Array(Date)}) OR event_date IN ({base_dates:Array(Date)}))
  AND dataset IN ({datasets:Array(String)})
  AND 1
  AND os_version = 'iOS 17.5'
GROUP BY seg
HAVING den_inc > {min_volume:UInt32}
ORDER BY abs(contribution_pp) DESC
```

**Result:** `[{"seg": "iPhone 13", "val_inc": 0.477, "val_base": 0.784, "delta": -0.307, "den_inc": 18481, "contribution_pp": -4.9062}, {"seg": "iPhone 15", "val_inc": 0.479, "val_base": 0.7855, "delta": -0.3065, "den_inc": 14500, "contribution_pp": -3.8431}, {"seg": "iPhone 14", "val_inc": 0.4769, "val_base": 0.7817, "delta": -0.3048, "den_inc": 82661, "contribution_pp": -21.7871}]`

**Decision:** cross segment iOS 17.5 × iPhone 13: delta -0.307

---

### step 13 · narrate · 2026-08-02 03:43:29.419 · 1841 ms

**Hypothesis:** LLM narrates from the evidence bundle; computes nothing

*-- no SQL: input is the evidence bundle (see result)*

**Result:** `{"model": "gpt-5-nano-2025-08-07", "usage": {"input": 4601, "output": 139}}`

**Decision:** narrative drafted (695 chars), pending guardrail

---

### step 14 · verify · 2026-08-02 03:43:29.429 · 0 ms

**Hypothesis:** Guardrail: every figure in the narrative must exist in the evidence bundle (fabricated numbers block publication)

*-- detector/guardrail.verify(narrative, evidence)*

**Result:** `{"ok": true, "n_checked": 3, "misses": []}`

**Decision:** 3 figure(s) checked, all present in evidence → publishable
