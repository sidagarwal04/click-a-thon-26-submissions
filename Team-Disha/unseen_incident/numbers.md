# Numbers behind the unseen diagnosis

All figures from ClickHouse `eda.rca_*` after materialize on the unseen-only load.  
Baseline rule: **same weekday − 7** (`same_dow_minus_7`). Probe metrics from `eda`; T−7 from `default.ad_events` when not present in `eda`.

## One-command verify (preferred)

From `source_code/` (with `.env` → your ClickHouse Cloud):

```bash
uv run python stack/scripts/verify_unseen_rca.py
```

Re-runs the catalog / WoW / counterfactual / top-localization queries and prints
numbers to compare with this file and `diagnosis.md`. Also writes
`stack/scripts/verify_unseen_rca_last.json`.

## Reproducible SQL (same queries the script runs)

```sql
-- Incident catalog
SELECT id, window_start, window_end, probe_day, primary_factor, segment,
       req_chg, fill_chg, ecpm_chg, rev_chg,
       share_requests, share_fill_rate, share_ecpm, severity
FROM eda.rca_incidents
ORDER BY window_start, id;

-- Global WoW for a probe day
SELECT event_date, baseline_day, requests, base_requests, req_chg,
       fill_rate, base_fill_rate, fill_chg,
       ecpm, base_ecpm, ecpm_chg,
       revenue, base_revenue, rev_chg, is_anomaly_gated
FROM eda.rca_daily_wow
WHERE event_date BETWEEN '2026-07-06' AND '2026-07-10'
ORDER BY event_date;

-- Counterfactuals
SELECT *
FROM eda.rca_counterfactual
ORDER BY probe_day;

-- Top fill segments on 2026-07-08
SELECT dimension, dim_value, fill_t, fill_b, fill_chg, fill_impact, d_rev
FROM eda.rca_segment_day
WHERE event_date = '2026-07-08'
ORDER BY fill_impact DESC
LIMIT 10;

-- Top eCPM combos on 2026-07-07 / 2026-07-10
SELECT combo_kind, segment, ecpm_t, ecpm_b, ecpm_chg, d_rev
FROM eda.rca_combo_day
WHERE event_date IN ('2026-07-07', '2026-07-10')
ORDER BY abs(d_rev) DESC
LIMIT 15;
```

## Key numbers (from materialize)

| Id | Probe | Baseline | Factor | Segment | req_chg | fill_chg | ecpm_chg | rev_chg |
|---|---|---|---|---|---|---|---|---|
| A | 2026-07-07 | 2026-06-30 | ecpm | video × APAC | +5.6% | +1.85 pp | −22.2¢ | −1.5% |
| B | 2026-07-08 | 2026-07-01 | fill_rate | iOS 17.5 | +5.4% | −5.32 pp | −16.3¢ | −8.3% |
| C | 2026-07-10 | 2026-07-03 | ecpm | video × APAC | +5.5% | +0.92 pp | −32.1¢ | −7.1% |

### Incident A counterfactual (probe 2026-07-07)

| Scenario | Revenue |
|---|---|
| Actual | 537.84 |
| If fill @ T−7 | 535.90 |
| If eCPM @ T−7 | **602.20** |
| If requests @ T−7 | 519.71 |
| Primary explained Δ | −64.36 |

### Incident B localization (2026-07-08)

| Segment | fill_t | fill_b | fill_chg | fill_impact |
|---|---|---|---|---|
| iOS 17.5 | 0.478 | 0.786 | −30.80 pp | ~17,984 |
| iOS 17.5 × APAC | 0.476 | 0.786 | −31.04 pp | ~12,943 |
| region=APAC | 0.677 | 0.785 | −10.82 pp | ~12,334 |

### Incident C counterfactual (probe 2026-07-10)

| Scenario | Revenue |
|---|---|
| Actual | 486.90 |
| If eCPM @ T−7 | **570.75** |
| Primary explained Δ | −83.86 |

## Row counts after load

| Table | Count |
|---|---|
| `eda.ad_events` | 1,500,000 (2026-07-06 … 2026-07-10 only) |
| `eda.rca_daily_wow` | 5 |
| `eda.rca_incidents` | 3 |
| `eda.rca_counterfactual` | 3 |
