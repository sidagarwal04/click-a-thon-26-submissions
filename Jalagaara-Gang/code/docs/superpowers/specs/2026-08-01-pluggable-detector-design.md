# Design — Pluggable anomaly detector (robust-z ⇄ seasonal-ML)

**Date:** 2026-08-01 · **Ticket:** JAL-27 (anomaly scorer) · **Lane:** B (Detection & RCA)
**Author:** Rohan M Rao

## Problem

`rca/detection.py::detect(metric, target)` is a stub. It must return the `Anomaly` the Evidence
Bundle needs, plus the `queries[]` that produced every number. JAL-26 already delivered the robust
like-for-like baseline primitive (`rca/baseline.py`, `rca/robust.py`).

Two additional asks shape this work:

1. **Two detection strategies, switchable via config** — the deterministic robust-z path *and* an
   unsupervised ML path, selected by `config.detection.method`. Both emit the identical `Anomaly`
   contract so everything downstream (decomposition, drill-down, bundle) is agnostic to which ran.
2. **No hardcoded constants** — values like `_MAD_SCALE` in `robust.py` must come from config.

## Goals / non-goals

**Goals**
- `detect()` returns a schema-valid `Anomaly` + logged `queries[]` for the *global* metric at the
  target hour (segment-level localization is drill-down's job, not detection's).
- A config switch chooses `robust_z` (default, deterministic, fully traceable) or `seasonal_ml`.
- The ML detector is unsupervised (no labels exist) and estimates residual noise over **all**
  history — directly mitigating the n=3 MAD-collapse behind JAL-74.
- All statistical constants live in config.

**Non-goals**
- No supervised model (only ~4 known anomalies; can't train trustworthily).
- No change to the LLM's role — it remains prose-only narrator, computes nothing.
- Not implementing JAL-74's robust-z gate fix here (separate ticket); the seasonal path uses its
  own AND-gate.
- No factor decomposition / drill-down (later tickets).

## Architecture

`detection.py` becomes a thin **dispatcher**. Detector implementations live in `rca/detectors/`:

```
rca/
  detection.py          # detect(metric, target) -> dispatch on config.detection.method
  detectors/
    __init__.py
    robust_z.py         # wraps baseline.score()  -> (Anomaly, queries)
    seasonal_ml.py      # pandas seasonal decomposition -> (Anomaly, queries)
```

```
detect(metric, target)
  └─ method = config.detection.method
     ├─ "robust_z"     -> detectors.robust_z.run(metric, target)
     └─ "seasonal_ml"  -> detectors.seasonal_ml.run(metric, target)
        -> (Anomaly, list[{id, sql, result_summary}])
```

Both detectors expose the same callable `run(metric, target) -> tuple[Anomaly, list[dict]]`. An
unknown `method` raises `ValueError` (fail loud, no silent default).

## Detector 1 — `robust_z` (deterministic, default)

Thin adapter over JAL-26. Calls `baseline.score(metric, target.start, segment=None)` and maps the
resulting `Stat` onto `Anomaly`. Returns the `Result.queries` unchanged — traceability already
built in.

## Detector 2 — `seasonal_ml` (unsupervised, pandas)

For the global metric across **all** available history at hourly grain:

1. **Pull the series** — one logged SQL query: `SELECT hour, <metric_expr> AS value FROM
   <hourly_table> GROUP BY hour ORDER BY hour`. (ClickHouse aggregates to hourly; Python only models
   the small hourly series — never raw events.)
2. **Seasonal component** — group by `(weekday, hour-of-day)` cell; `expected` for each cell = the
   robust center (median) of that cell across all weeks. (168 cells for a full week.)
3. **Residuals** — `residual = value − seasonal_expected` for every hour.
4. **Residual scale** — MAD of *all* residuals × `mad_scale`. Estimated over the whole series, so it
   does not collapse the way n=3 does.
5. **Score the target hour** — `score = residual_robust_z` of `target.start`. `detected` when
   `|score| ≥ residual_z_threshold` **AND** `|pct_delta| ≥ min_pct_delta` (the JAL-74 AND-gate).
   `direction = drop` if observed < seasonal_expected else `spike`.

Implemented with pandas/numpy (already dependencies — no new package). Deterministic and reproducible
from the logged series + config params: defensible to a judge even though the arithmetic runs in
Python rather than SQL.

## `Anomaly` field mapping

| Field | `robust_z` | `seasonal_ml` |
|---|---|---|
| `observed` | value at target hour | value at target hour |
| `expected` | same weekday+hour median (trailing 3wk) | seasonal component (weekday+hour median, all history) |
| `abs_delta` | observed − expected | observed − expected |
| `pct_delta` | (observed − expected)/expected | same |
| `score` | robust z of the value | robust z of the residual |
| `direction` | drop / spike | drop / spike |
| `detected` | JAL-26 gate | `|z|≥thr AND |pct|≥floor` |

## Config changes

`config.detection` gains `method` + `mad_scale` and a `seasonal_ml` block; existing robust-z keys
stay flat (minimal churn to `baseline.py`):

```json
"detection": {
  "grain": "hour",
  "method": "robust_z",
  "mad_scale": 1.4826,
  "baseline_method": "same_weekday_trailing_weeks",
  "baseline_weeks": 3,
  "mad_z_threshold": 3.5,
  "min_pct_delta": 0.1,
  "seasonal_ml": {
    "season_keys": ["weekday", "hour"],
    "residual_z_threshold": 3.5,
    "min_pct_delta": 0.05
  }
}
```

## `robust.py` config-ification (keep the primitive pure)

`robust.py` stays dependency-free and unit-testable without config. `_MAD_SCALE` is removed;
`robust_z` takes `scale` as an explicit parameter:

```python
def robust_z(value: float, center: float, mad_value: float, scale: float) -> float:
    denom = mad_value * scale
    return (value - center) / denom if denom else 0.0
```

The value lives in config (`detection.mad_scale`); callers (`baseline.py`, `seasonal_ml.py`) read it
and pass it in. `test_robust.py` updated to pass an explicit scale.

## Window semantics

`target: Window` is treated as a **single incident hour** — `target.start` is the hour scored,
matching JAL-26's per-hour design. Multi-hour ranges are out of scope for now.

## Testing

- `test_robust.py` — updated for the new `scale` parameter.
- `detectors/robust_z` — mapping from `Stat` → `Anomaly` on a synthetic baseline (no DB).
- `detectors/seasonal_ml` — hand-built hourly series with a known injected residual; assert
  `expected`, `score` sign, and `detected`; assert a normal hour is NOT flagged (n-stability).
- `detection.detect` — dispatch honors `config.detection.method`; unknown method raises.
- Live smoke: run both methods against `hourly_summary`, eyeball the `Anomaly` + logged SQL.

## Rollout order (low-risk first)

1. Config-ify `mad_scale` + update `robust.py`/`baseline.py`/`test_robust.py` (pure refactor, green).
2. `detection.py` dispatcher + `detectors/robust_z.py` (completes JAL-27's deterministic path).
3. `detectors/seasonal_ml.py` + config `seasonal_ml` block + tests.

## Risks

- **Traceability of the ML path** — mitigated: log the series SQL, keep the model deterministic and
  parameterized from config; document the residual math. Default stays `robust_z`.
- **Short history (~5 weeks)** — seasonal cells have ~5 samples each, but residual scale pools across
  all cells, so it is still far more stable than n=3.
