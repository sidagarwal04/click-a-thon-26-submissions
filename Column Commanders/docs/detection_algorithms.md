# Detection Algorithms — Specification
## Anomaly Detection Service · InMobi Click-a-thon 2026

---

## Why Three Detectors

No single statistical method covers all anomaly shapes present in the InMobi dataset. The three detectors are chosen to cover three distinct anomaly profiles, all validated against real planted anomalies in the training data.

| Detector | Targets | Anomaly Shape | Evidence from Data |
|----------|---------|---------------|--------------------|
| A: Robust Z-Score | fill_rate, eCPM, CTR | Abrupt single-window drop/spike | Android 15 crash: z = −163 on day 1 |
| B: Trend-Corrected Z-Score | requests | Volume drop/spike with organic growth trend | Jun 21 volume drop: req_z = −42 |
| C: Directional CUSUM | fill_rate, eCPM | Persistent multi-window drift | eCPM drift Jun 19–22: single-day z = −165 but MIN_DEVIATION_PCT guard blocked it; CUSUM fires on day 4 |

---

## Detector A — Robust Z-Score

### Why "robust"

Standard z-score uses `mean` and `stddevPop`. One contaminated baseline day (e.g. Jun 23, Android 15 crash) inflates sigma by 180× and makes real anomalies invisible.

Example (Wednesday baseline for Jul 1):
```
With Jun 24 (anomalous) in baseline: mean=77.45%, sigma=1.599%, z(Jul 1) = +0.63  → MISS
Without Jun 24:                      mean=78.58%, sigma=0.009%, z(Jul 1) = -14.2  → DETECT
```

Solution: replace `avg()` with `quantile(0.5)` (median), and `stddevPop()` with `(Q3-Q1)/1.35` (normalized IQR). Median of {75%, 78.5%, 78.5%} = 78.5% — the outlier is ignored.

### Formula

```
baseline_median = quantile(0.5)(prior same-period fill_rate values)
baseline_sigma  = (quantile(0.75) - quantile(0.25)) / 1.35
z = (current_fill_rate - baseline_median) / baseline_sigma
```

The 1.35 divisor is the asymptotically consistent normalization factor: for a standard normal distribution, `IQR ≈ 1.35 × σ`.

### Why minimum n = 3

With n = 2 observations, stddev (and IQR) is estimated from 2 points. If those 2 points happen to be nearly identical (Jun 9 = 78.528%, Jun 16 = 78.480%), then sigma = 0.021% — any fluctuation of 0.06% gives z = 2.9. Jun 16 (a completely normal Tuesday) produced z = −16.53 with n = 2.

With n ≥ 3, the IQR estimate stabilizes and normal days stay at |z| < 3.

### Thresholds

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| fill_rate | |z| > 5 | Very low natural variance; 5σ almost never occurs normally |
| eCPM | |z| > 5 | Same — very stable metric |
| CTR | |z| > 8 | Non-Gaussian distribution; Jun 22 (normal day) had z = −7.77; need higher bar |

---

## Detector B — Trend-Corrected Z-Score

### The trend problem

Monday requests: 263,979 (Jun 1) → 281,083 (Jun 22) = +6.5% over 3 weeks.

If we compare Jun 22 against a 3-week-old baseline, the naive z-score sees:
```
z = (281,083 - 263,979) / 9,185 = +1.86
```
A normal Monday appears slightly high every week. More importantly, a real volume drop looks smaller than it is.

### Trend correction

The baseline provider uses `simpleLinearRegression(timestamp, requests)` on the prior same-weekday observations to estimate the weekly growth rate. The corrected baseline:

```
baseline_adj = baseline_median + slope × (target_timestamp - baseline_midpoint_timestamp)
z = (current_requests - baseline_adj) / sigma
```

The `baseline_midpoint_timestamp` is the mean Unix timestamp of the prior observations — the "center of mass" of the baseline set.

---

## Detector C — Directional CUSUM

### Why CUSUM is needed

The eCPM drop of Jun 19–22 was −2.6% per day. Each day individually:
- z-scores: −164, −31, −26, −21 (first day high because n=2 makes sigma tiny)
- With a stable n=3 baseline and the 5% MIN_DEVIATION_PCT guard: MISSED

CUSUM (Cumulative Sum control chart) accumulates evidence of sustained drift:
```
Day 19: CUSUM = −0.058
Day 20: CUSUM = −0.122
Day 21: CUSUM = −0.179
Day 22: CUSUM = −0.234  → crosses threshold of −0.20 → ALERT
```

### Parameters

```
k (slack)     = 0.5σ   — ignore noise below half a standard deviation
h (threshold) = 4σ     — fire when accumulated evidence = 4 standard deviations
rolling_window = 7     — only accumulate over last 7 windows (prevents stale alerts)
```

The rolling window is critical. Without it, the CUSUM stays in alert mode after the anomaly recovers — making it impossible to detect a NEW anomaly starting later.

### Two-sided

Both directions are monitored:
- `cusum_down` fires on sustained drops (negative drift) — e.g. eCPM repricing event
- `cusum_up` fires on sustained rises (positive drift) — e.g. bot traffic inflating fill_rate

---

## Configurable Window Model

All detectors share the same window abstraction:

```
Window W (configurable: 1h, 6h, 12h, 1d)
Current window:  [now - W, now]  where "now" = last complete boundary

Comparison set:  All prior windows where:
  - Same hour-of-day (controls daily seasonality)
  - Same day-of-week (controls weekly seasonality)
  - Not overlapping with current window
  - Within trailing 3 weeks
  - Count ≥ 3
```

This means comparing 14:00–15:00 Tuesday Jun 23 against 14:00–15:00 from prior Tuesdays (Jun 16, Jun 9, Jun 2) — not against the immediately prior hour. The immediately prior hour comparison would falsely alarm on normal intra-day variation.

---

## Statistical Properties of the InMobi Dataset

From direct measurement (9M events, Jun 1 – Jul 5, 2026):

| Metric | Mean | Daily StdDev | Distribution | Notes |
|--------|------|-------------|--------------|-------|
| fill_rate | 78.1% | 0.009–0.024% | Near-Gaussian | Extremely stable; low noise floor |
| eCPM | 2.476 | 0.009–0.027 | Near-Gaussian | Extremely stable |
| CTR | 1.09% | 0.009–0.051% | Non-Gaussian | 5× range in sigma; heavy tails |
| requests | 265K/day | 5,000–9,000 | Near-Gaussian + linear trend | +8-9%/week growth |

The low natural variance of fill_rate and eCPM is why even a 2.6% eCPM drop produces z = −164 — the distribution is so tight that any deviation is statistically extreme.
