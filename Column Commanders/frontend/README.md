# Frontend — Root-Cause Analyst UI

Two pages: **Detect** (find and localise anomalies) and **Explore** (browse metrics by dimension).

## Running it

No build step, no `npm install`:

```bash
cp frontend/config.example.js frontend/config.js   # fill in your HyperDX API key
open frontend/index.html
```

React and Babel load from unpkg, so an internet connection is required on first load.

## Files

| File | Purpose |
|---|---|
| `index.html` | The whole app — UI, chart, detection and attribution logic |
| `data.js` | 4,550 pre-aggregated rollup rows exported from ClickHouse (`window.RCA_DATA`) |
| `config.js` | Local-only, gitignored. Sets `window.RCA_CONFIG` (HyperDX API key/URL). Copy from `config.example.js` |

`data.js` holds **counters only** — `reqs, fills, imps, clicks, revenue` per `(day, dim, val)`.
Every ratio is derived in the browser as `sum(num)/sum(den)`, never as an average of per-day
ratios, so weekly and monthly rollups stay exact. Regenerate it with:

```sql
SELECT toDate(e.event_time) AS day, dv.1 AS dim, dv.2 AS val,
       count() AS reqs, sum(is_filled) AS fills, sum(is_impression) AS imps,
       sum(is_click) AS clicks, round(sum(revenue),4) AS revenue
FROM ad_events e
LEFT JOIN geo_device g USING(geo_device_id)
LEFT JOIN apps       a USING(app_id)
LEFT JOIN advertisers ad USING(advertiser_id)
ARRAY JOIN [('__global__','all'),
  ('os_version', toString(g.os_version)), ('region', toString(g.region)),
  ('country', toString(g.country)), ('device_model', toString(g.device_model)),
  ('ad_format', toString(e.ad_format)), ('app_category', toString(a.category)),
  ('publisher_tier', toString(a.publisher_tier)),
  ('vertical', toString(ad.vertical)), ('campaign_type', toString(ad.campaign_type)),
  ('os_version x region', concat(toString(g.os_version),' x ',toString(g.region))),
  ('ad_format x region', concat(toString(e.ad_format), ' x ',toString(g.region)))] AS dv
GROUP BY day, dim, val ORDER BY dim, val, day FORMAT JSONCompact
```

## Wiring to the backend

The Detect page uses the selected live backend pipeline. In v1 mode it scans the requested days
through `/api/v1/detect`, then polls incident details until deterministic drilldown and optional
LLM narration are complete. Explore and the all-anomalies reference view still use `data.js`.

| UI action | Endpoint |
|---|---|
| Detect Anomalies (v1) | `POST /api/v1/detect` |
| V1 final verdict | `GET /api/v1/incidents/{id}` (polled) |
| Detect Anomalies (v2) | `POST /api/v2/detect/historical` |
| Explore table | local `data.js` rollup |

## Behaviour worth knowing before changing it

**Detection always runs daily, whatever the chart shows.** Weekly buckets dilute a one-day event
about sevenfold — the Jun 21 request collapse reads as −44.8% daily and −4.6% weekly, under any
sane threshold. Switching the interval re-maps existing findings onto the new buckets rather than
re-detecting, so incidents never disappear because of a display choice.

**Three gates must all pass to alarm:** `|robust z| ≥ 4`, `|change| ≥ min_effect`, and
`denominator ≥ min_den`. The z-score uses **MAD**, not standard deviation — stddev is computed
over residuals that include the anomaly, so a large excursion inflates its own yardstick. On this
dataset the Jun 23 fill-rate drop scores 26σ under MAD and 2.4σ under stddev: found, or missed.

**`min_den` differs sharply per metric.** Relative standard error is `sqrt((1-p)/(p·n))`, so fill
rate (p≈0.785) is trustworthy at ~110 samples while CTR (p≈0.011) needs ~36,000 — a 330× gap.
Without that floor the UI reports CTR incidents built on a few dozen clicks.

**Attribution ranks by a counterfactual, not by percentage change:**

```
score(s) = volume_s × (baseline_rate_s − window_rate_s) / total_volume
```

Ranking on percentage alone promotes tiny segments; ranking on volume alone promotes big innocent
ones. Among candidates within 5% of the top score, the **smallest** wins — the tightest hypothesis
explaining the same movement. Without that tie-break, a two-way cell loses to its own parent.

**`GLOBAL` is a real verdict.** When every segment moves together (coefficient of variation < 0.10)
no segment is named. On Jun 21 the CV is 0.017; naming the largest segment there would be a
fabrication.

**Advertiser dimensions are blocked for fill and volume metrics.** `vertical` and `campaign_type`
exist only on filled rows, so slicing fill rate by them returns 1.000 for every value — a silent
false negative rather than an obvious error. The UI disables the Detect button and explains why.
