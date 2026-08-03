"""ML detector: scikit-learn IsolationForest over per-hour features.

An actual trained estimator (unlike seasonal_ml's hand-rolled median model). Unsupervised — it fits
on all historical hours and scores the target hour's outlierness. Two feature modes, toggleable via
config.detection.isolation_forest.features:

  * univariate   — per hour: [value, seasonal-expected, residual, hour-of-day, weekday] for the chosen
                   metric. Detection = the forest flags it AND the metric moved >= min_pct_delta.
  * multivariate — per hour: the ratio vector (fill_rate, ctr, ecpm, ...). Flags hours whose metric
                   COMBINATION is unusual even if the single metric looks normal (no pct floor).

Deterministic given random_state; the pulled series SQL is logged for traceability. ClickHouse
aggregates to hourly; sklearn only sees the small hourly frame.
"""
from __future__ import annotations

from datetime import datetime
from functools import cache

import pandas as pd
from sklearn.ensemble import IsolationForest

from config import config
from config import hourly_source as _hourly
from data.calibration import effect_threshold
from data.client import run_query
from metrics import metric_sql
from models import Anomaly, Window
from rca.robust import pct_delta

_PARAM_KEYS = ("n_estimators", "contamination", "random_state", "min_pct_delta")


def _seasonal(df: pd.DataFrame, cutoff=None) -> pd.Series:
    """Per (weekday, hour) median — the expected value each row is compared against.

    With a cutoff the medians come from HISTORY ONLY. Taken over the whole frame, a streamed
    hour sits inside its own cell's median and drags its expectation toward itself, shrinking
    exactly the deviation we are trying to detect.
    """
    cell = list(zip(df["hour"].dt.dayofweek, df["hour"].dt.hour))
    framed = df.assign(_cell=cell)
    everything = framed.groupby("_cell")["value"].transform("median")
    if cutoff is None:
        return everything
    history = framed[framed["hour"] < cutoff]
    if history.empty:
        return everything
    # Cells with no history at all fall back to the all-rows median, so scoring never breaks.
    return framed["_cell"].map(history.groupby("_cell")["value"].median()).fillna(everything)


def _feature_matrix(df: pd.DataFrame, seasonal: pd.Series, mode: str, feature_cols: list[str]) -> pd.DataFrame:
    if mode == "multivariate":
        return df[feature_cols].astype(float)
    return pd.DataFrame({
        "value": df["value"], "seasonal": seasonal, "residual": df["value"] - seasonal,
        "hod": df["hour"].dt.hour, "wd": df["hour"].dt.dayofweek,
    })


def score_frame(df: pd.DataFrame, target_hour: datetime, mode: str, feature_cols: list[str], params: dict) -> Anomaly:
    """Fit IsolationForest on the frame and score `target_hour` (pure — no DB)."""
    df = df.reset_index(drop=True).copy()
    df["hour"] = pd.to_datetime(df["hour"])
    seasonal = _seasonal(df)
    features = _feature_matrix(df, seasonal, mode, feature_cols).fillna(0.0)

    model = IsolationForest(
        n_estimators=params.get("n_estimators", 200),
        contamination=params.get("contamination", "auto"),
        random_state=params.get("random_state", 42),
    ).fit(features)

    idx = df.index[df["hour"] == pd.Timestamp(target_hour)]
    if len(idx) == 0:
        raise ValueError(f"target hour {target_hour} not present in series")
    i = int(idx[0])
    xt = features.iloc[[i]]
    score = float(-model.decision_function(xt)[0])   # > 0 => more anomalous
    flagged = int(model.predict(xt)[0]) == -1

    observed = float(df["value"].iloc[i])
    expected = float(seasonal.iloc[i])
    pct = pct_delta(observed, expected)
    # univariate ties detection to the metric's own move; multivariate is about the combination.
    detected = flagged and (abs(pct) >= params.get("min_pct_delta", 0.05)) if mode == "univariate" else flagged

    return Anomaly(
        detected=detected, observed=observed, expected=expected,
        abs_delta=observed - expected, pct_delta=pct, score=score,
        direction="drop" if observed < expected else "spike",
    )


def _series_sql(metric: str, mode: str, feature_cols: list[str]) -> str:
    cols = [f"{metric_sql(metric, 'rollup')} AS value"]
    if mode == "multivariate":
        cols += [f"{metric_sql(name, 'rollup')} AS {name}" for name in feature_cols]
    # A ratio col like `sum(requests) AS requests` shadows the source column inside other ratios;
    # prefer the column so sum(requests) isn't read as sum(sum(requests)) (illegal nested aggregation).
    return (f"SELECT hour, {', '.join(cols)} FROM {_hourly()} GROUP BY hour ORDER BY hour "
            f"SETTINGS prefer_column_name_to_alias = 1")


@cache
def _cached_series(metric: str, mode: str, feature_cols: tuple[str, ...]) -> tuple[tuple, tuple, str]:
    """The historical series is identical for every target hour scored against the same
    metric+mode — only the query result matters here, not which hour is being tested.

    Sweeping N buckets for one metric (rca.incidents.scan_incidents_with_method, /dev/mega's
    several-hours-per-case loop) was refetching + refitting on that same ~840-row series every
    single call: measured 5 calls at ~1.2s each, all identical data. Caching just the query
    (network round-trip is the dominant cost, not the fit) turns an O(buckets) DB cost into
    O(1) per metric. Row/columns as tuples, not the DataFrame itself, so this stays a plain
    hashable-args lru_cache — rebuild the (small, ~840-row) DataFrame per call, which is cheap.
    """
    res = run_query(_series_sql(metric, mode, list(feature_cols)))
    return tuple(map(tuple, res["rows"])), tuple(res["columns"]), res["resolved_sql"]


@cache
def fit_cutoff() -> pd.Timestamp | None:
    """First hour of the TARGET dataset, or None when target and history are the same dataset.

    Rows at/after this hour are streamed data and are excluded from the fit. Without it a
    streaming run trains the model on the very hours it is about to judge: IsolationForest is
    unsupervised, so an anomaly present in its training set is learned as normal and stops
    looking anomalous — the detector quietly grades its own homework.

    Cached: the boundary is fixed for a run (the datasets are disjoint in time), and this is on
    the per-metric fit path. `reset_cache()` clears it.
    """
    from config import baseline_hourly, target_hourly

    target, history = target_hourly(), baseline_hourly()
    if target == history:
        return None
    count, lo = run_query(f"SELECT count(), min(hour) FROM {target}")["rows"][0]
    return pd.Timestamp(lo) if count else None


def frame(metric: str, mode: str, feature_cols: tuple[str, ...]):
    """(df, features, seasonal, resolved_sql) built from the CURRENT series.

    Rebuilt per call rather than cached alongside the model: in a stream the frame gains an hour
    every batch, and a cached frame is why streamed hours were reported as "not present in
    series". The fit stays cached — history does not change — so this costs a DataFrame rebuild,
    not a refit.
    """
    rows, columns, sql = _cached_series(metric, mode, feature_cols)
    df = pd.DataFrame(list(rows), columns=list(columns))
    df["hour"] = pd.to_datetime(df["hour"])
    seasonal = _seasonal(df, fit_cutoff())
    features = _feature_matrix(df, seasonal, mode, list(feature_cols)).fillna(0.0)
    return df, features, seasonal, sql


@cache
def _cached_fit(
    metric: str, mode: str, feature_cols: tuple[str, ...],
    n_estimators: int, contamination, random_state: int,
) -> IsolationForest:
    """The FIT is exactly as redundant as the fetch — profiled at ~0.77s, roughly matching the
    ~0.69s DB round trip, so caching only _cached_series left half the waste in place (measured:
    a 10-day sweep dropped from 96s to 60s with data-only caching, not the ~15s a fetch-only fix
    should give if fit were free). IsolationForest is deterministic given fixed random_state, so
    the fitted model is exactly reusable across every target hour in a sweep — nothing about
    fitting depends on which hour is later being scored.
    """
    df, features, _seasonal_values, _sql = frame(metric, mode, feature_cols)

    # Fit on history only; score anything. The frame keeps every hour so a streamed target row
    # is still scoreable, but the model never sees streamed rows while learning what normal is.
    cutoff = fit_cutoff()
    train = features[df["hour"] < cutoff] if cutoff is not None else features
    if train.empty:  # nothing pre-dates the target — fall back rather than fail the detector
        train = features
    return IsolationForest(
        n_estimators=n_estimators, contamination=contamination, random_state=random_state
    ).fit(train)


def invalidate_series() -> None:
    """Drop the cached SERIES but keep the fitted model.

    A stream adds an hour at a time, so the cached series goes stale immediately and `run()`
    fails with "target hour not present in series" — measured as 2 successful checks across 19
    streamed batches, silently skipped. The model deliberately survives: it is fitted on history
    only (see fit_cutoff), which does not change as the stream advances, so refitting per batch
    would burn ~0.8s a metric to relearn exactly the same thing.
    """
    _cached_series.cache_clear()


def reset_cache() -> None:
    """Drop the cached series and fitted models. Call after loading a new dataset within a
    running process — same lifecycle as data.calibration.reset_calibration()."""
    _cached_series.cache_clear()
    _cached_fit.cache_clear()
    fit_cutoff.cache_clear()


def run(metric: str, target: Window) -> tuple[Anomaly, list[dict]]:
    """Score the GLOBAL metric at the target hour via IsolationForest. Returns (Anomaly, queries)."""
    cfg = config()["detection"]["isolation_forest"]  # read fresh so in-memory overrides take effect
    mode = cfg["features"]
    feature_cols = cfg["feature_columns"]
    df, features, seasonal, resolved_sql = frame(metric, mode, tuple(feature_cols))
    model = _cached_fit(
        metric, mode, tuple(feature_cols),
        cfg["n_estimators"], cfg["contamination"], cfg["random_state"],
    )

    idx = df.index[df["hour"] == pd.Timestamp(target.start)]
    if len(idx) == 0:
        raise ValueError(f"target hour {target.start} not present in series")
    i = int(idx[0])
    xt = features.iloc[[i]]
    score = float(-model.decision_function(xt)[0])
    flagged = int(model.predict(xt)[0]) == -1

    observed = float(df["value"].iloc[i])
    expected = float(seasonal.iloc[i])
    pct = pct_delta(observed, expected)
    # Same fix as seasonal_ml: the pct floor is the calibrated per-metric one (data.calibration),
    # not the flat 5% in config — see score_frame's twin logic / module docstring history.
    # multivariate ignores the pct floor entirely (see score_frame) — this only bites univariate.
    min_pct = effect_threshold(metric)
    detected = (flagged and abs(pct) >= min_pct) if mode == "univariate" else flagged

    anomaly = Anomaly(
        detected=detected, observed=observed, expected=expected,
        abs_delta=observed - expected, pct_delta=pct, score=score,
        direction="drop" if observed < expected else "spike",
    )
    # resolved_sql is the query that actually produced this data — logged every call for
    # traceability even when both fetch and fit were served from cache, since it's the same
    # real query and the same deterministic fit that ran the first time.
    query = {"id": "q_iforest_features", "sql": resolved_sql,
             "result_summary": {"mode": mode, "n_hours": len(df), "score": anomaly.score}}
    return anomaly, [query]
