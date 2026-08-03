# `v_narration` — column reference & narration rules

One row per incident. Everything the executive summary is allowed to say lives in that row.
The LLM joins columns into sentences; it never computes, infers, or supplies a figure.

---

## 1 · Columns

### What moved

| Column | Type | Definition |
| --- | --- | --- |
| `incident_id` | String | Stable key: `metric\|dim=val@start_date`. Use for traceability, never in prose. |
| `metric` | String | Which metric deviated. Translate before printing — see §3. |
| `window_start` / `window_end` | Date | First and last day the metric was outside its baseline. |
| `days` | UInt16 | Duration. `1` means a single-day event. |
| `metric_change_pct` | Float64 | Move vs baseline, signed %. **This is the blended, company-wide number.** |
| `peak_z` | Float64 | Strongest deviation in σ. Internal confidence only — never publish. |

### Who caused it

| Column | Type | Definition |
| --- | --- | --- |
| `culprit_dim` | String | Dimension holding the cause (`os_version`, `category`, …). Translate — see §3. |
| `culprit_val` | String | The specific value (`Android 15`, `finance`). Print verbatim. |
| `culprit_baseline` | Float64 | That segment's normal level. Format per metric — see §4. |
| `culprit_value` | Float64 | Its level during the incident. |
| `culprit_change_pct` | Float64 | Its own move, signed %. **Always larger than `metric_change_pct`** — a small slice moving hard. |
| `culprit_share_pct` | Float64 | Its share of traffic. The "only X% of volume" clause. |
| `explains_pct` | Float64 | Share of the company-wide move this segment accounts for. **The headline attribution number.** |

### The proof

| Column | Type | Definition |
| --- | --- | --- |
| `global_without_culprit` | Float64 | Company-wide metric recomputed with the segment removed. |
| `global_without_culprit_baseline` | Float64 | What that figure normally is. |
| `clears_anomaly` | UInt8 | `1` = removing the segment restores normal → it accounts for the whole move. `0` = anomaly persists → not the sole cause. |

### What was checked and cleared

| Column | Type | Definition |
| --- | --- | --- |
| `ruled_out_segments` | Array(Tuple(String, Float64)) | Next 5 candidates by contribution, each `(dim=val, explains_pct)`. All investigated, none the cause. |
| `ruled_out_dimensions` | Array(Tuple(String, Float64)) | `(dimension, spread)` — dimensions the drop was **uniform** across. Low spread = that dimension is not a factor. |

### Verdict

| Value | Meaning | Action |
| --- | --- | --- |
| `confirmed` | One segment explains ≥90% and removing it clears the anomaly. | **Publish.** |
| `intersection_descend` | Cause is a *pair* (e.g. OS × region), not one dimension. | **Do not publish.** Re-run attribution on the pair first. |
| `ambiguous_no_slice_clears` | No segment removal restores normal. | **Do not publish as localized.** Report as diffuse, or suppress as noise. |
| `weak` | Top segment explains <90% but does clear. | Publish with hedging: "primarily driven by". |
| `no_attribution` | No diagnosis rows. | Pipeline gap — investigate, don't narrate. |

---

## 2 · Recommended addition: revenue impact

Not in the view yet. An executive summary is weak without money. Add:

```sql
-- join in v_narration
LEFT JOIN (
    SELECT i.incident_id AS incident_id,
           sum(x.r)                                  AS revenue_actual,
           sum(x.r) / (1 + i.worst_effect)           AS revenue_expected,
           sum(x.r) / (1 + i.worst_effect) - sum(x.r) AS revenue_shortfall
    FROM rca_test.incidents AS i
    INNER JOIN (SELECT toDate(ts) AS d, sum(revenue) AS r
                FROM rca_test.seg_hourly WHERE dim = '__all__' GROUP BY d) AS x
            ON x.d >= i.i0
    WHERE x.d <= i.i1
    GROUP BY i.incident_id, i.worst_effect
) AS m USING (incident_id)
```

`revenue_shortfall` is a **counterfactual**, not an observed loss. Phrase it as "roughly", never as an exact figure.

---

## 3 · Translation tables

Never print raw identifiers.

| `metric` | Say |
| --- | --- |
| `requests` | ad requests / traffic volume |
| `fill_rate` | fill rate (share of requests that returned an ad) |
| `render_rate` | render rate (share of ads that displayed) |
| `ctr` | click-through rate |
| `ecpm` | price per thousand impressions (eCPM) |
| `rpr` | revenue per request |
| `revenue` | revenue |

| `culprit_dim` | Say |
| --- | --- |
| `os_version` | operating system |
| `device_model` | device |
| `region` / `country` | region / country |
| `category` | app category |
| `publisher_tier` | publisher tier |
| `ad_format` | ad format |
| `vertical` | advertiser vertical |
| `campaign_type` | campaign type |

---

## 4 · Number formatting

| Metric | `culprit_baseline` / `culprit_value` | Example |
| --- | --- | --- |
| `fill_rate`, `render_rate`, `ctr` | × 100, one decimal, `%` | `0.7850` → **78.5%** |
| `ecpm` | two decimals, no unit | `2.4722` → **2.47** |
| `rpr`, `revenue` | two decimals | `0.0019` → **0.0019** |
| `requests` | thousands separator | `126052` → **126,052** |

All `*_pct` columns are already percentages — print as-is, keep the sign, never round to zero.

---

## 5 · Sentence structure

Five beats, in order. Skip any whose column is null.

```
1 HEADLINE   <culprit_val> caused <metric> to fall <metric_change_pct> over <days> days
2 IMPACT     Revenue came in at <revenue_actual> against an expected <revenue_expected>
3 CAUSE      <culprit_dim>=<culprit_val> went <culprit_baseline> → <culprit_value>
             (<culprit_change_pct>) across <culprit_share_pct> of traffic,
             accounting for <explains_pct> of the company-wide move
4 PROOF      Excluding it, the company-wide figure is <global_without_culprit>
             against a <global_without_culprit_baseline> baseline — the anomaly disappears
5 CLEARED    We checked <ruled_out_segments>; each moves only because it carries the
             affected traffic. The drop was uniform across <ruled_out_dimensions>,
             so those are not factors
```

---

## 6 · Worked example

**Row:**
```
metric=fill_rate  window=2026-06-23→2026-06-25  days=3  metric_change_pct=-4.45
culprit_dim=os_version  culprit_val=Android 15
culprit_baseline=0.7850  culprit_value=0.4333  culprit_change_pct=-44.8
culprit_share_pct=9.6  explains_pct=97.9
global_without_culprit=0.7844  global_without_culprit_baseline=0.7852  clears_anomaly=1
ruled_out_segments=[(publisher_tier=tier_2,46.4),(region=EU,39.3),(ad_format=banner,36.5)]
verdict=confirmed
```

**Narration:**

> **Android 15 stopped filling — 23–25 June, roughly 72 lost.**
>
> Revenue came in at 1,537 against an expected 1,609.
>
> Ad requests from Android 15 devices stopped being filled: the fill rate on those devices
> collapsed from 78.5% to 43.3% for three days, then returned to normal on its own.
> Android 15 is 9.6% of our traffic and explains 98% of the drop in overall fill rate.
>
> Excluding it, our fill rate for the period was 78.4% — against a 78.5% baseline, effectively
> untouched.
>
> We checked and cleared tier-2 publishers, Europe and banner formats; each moved only because
> Android 15 traffic sits inside it. The drop was the same size in every region and on every
> device model, so this was neither geographic nor hardware-specific. Request volume was 4%
> *above* normal, so we did not lose demand — we failed to serve it.

---

## 7 · Rules for the narrator

**Must**

1. Every figure must be a column in the row. No arithmetic, no rounding that changes meaning.
2. Respect `verdict`. `intersection_descend` and `ambiguous_no_slice_clears` are **not publishable**.
3. Lead with impact, not mechanism. Executives read the money first.
4. Always include the cleared list — it is the difference between a claim and a finding.
5. State duration and whether it recovered. "Still ongoing" and "recovered by itself" are different decisions.

**Must not**

1. **Never assert cause-of-cause.** The data locates *where*, never *why*. "Android 15 stopped filling" is supported; "the Android 15 SDK has a bug" is not.
2. Never report a composite metric alongside the factor that drives it. `rpr` and `ecpm` firing on the same window with the same culprit is **one** incident — reporting both double-counts the loss.
3. Never present `revenue_shortfall` as an observed figure. It is a counterfactual.
4. Never publish `peak_z` or `incident_id` in prose.
5. Never fill a gap with a guess. If a column is null, drop that sentence.

---

## 8 · Known gaps

Both understate what happened. Say so rather than implying completeness.

| Gap | Effect on the summary |
| --- | --- |
| `n` counts hours for volume metrics in `v_detect` | Traffic-volume incidents never open. The 21 June platform-wide 44% traffic loss — the largest event in the data — is **absent**. |
| `incidents` filters `dim = '__all__'` | Segment-only incidents can never open. A failure confined to one slice stays invisible if it doesn't move the blended number. |
| No composite suppression | `rpr` and `ecpm` appear as two incidents for one root cause. |
| `uniformity` unpopulated | `ruled_out_dimensions` is empty and `intersection_descend` never fires — an intersectional cause would be published as a single-dimension one. |

Until these are closed, the summary should carry a line: *"Covers metric-quality incidents only; traffic-volume events are not yet monitored."*
