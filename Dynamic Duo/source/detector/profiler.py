"""Profiler: measure every monitored series' structure, choose its baseline model,
write rca.series_profile.

Run after every dataset load (incl. the unseen slice):
    python3 -m detector.profiler

The decision table (config.py constants) is deliberately boring:
    not_applicable  metric undefined for the dimension (e.g. fill_rate by vertical),
                    or the series is constant/degenerate
    not_monitored   median volume below the floor — covered via parents + drill-down
    stl_168         weekly+daily structure confirmed (strength >= 0.6) — primary
    stl_24          daily structure only
    flat_robust     no seasonal structure the data can defend
The chosen model is stored, so "why did the detector expect X" is always answerable.
"""
from __future__ import annotations

import math
from pathlib import Path

from . import chdb, config

SQL = Path(__file__).parent / "sql" / "profile_series.sql"


def _num(v):
    """JSON floats may arrive as None/'nan'/'inf' strings — normalize to float|None."""
    if v is None:
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def choose_model(row: dict) -> str:
    dim, metric = row["dimension"], row["metric"]
    if (dim, metric) in config.NOT_APPLICABLE:
        return "not_applicable"
    s24 = _num(row.get("seasonal_strength_24"))
    s168 = _num(row.get("seasonal_strength_168"))
    if s24 is None and s168 is None:      # constant/degenerate series (zero variance)
        return "not_applicable"
    if (_num(row.get("median_hourly_volume")) or 0) < config.VOLUME_FLOOR_HOURLY:
        return "not_monitored"
    if (s168 or 0) >= config.SEASONAL_STRENGTH_MIN:
        return "stl_168"
    if (s24 or 0) >= config.SEASONAL_STRENGTH_MIN:
        return "stl_24"
    return "flat_robust"


def run() -> list[dict]:
    raw = chdb.query_file(SQL, params={"min_nonnull": config.MIN_NONNULL_HOURS})
    out = []
    for r in raw:
        row = {
            "dimension": r["dimension"],
            "value": r["value"],
            "metric": r["metric"],
            "n_hours": int(r["n_hours"]),
            "median_hourly_volume": _num(r["median_hourly_volume"]) or 0.0,
            "fft_period": _num(r["fft_period"]) or 0.0,
            "acf_24": _num(r["acf_24"]) or 0.0,
            "acf_168": _num(r["acf_168"]) or 0.0,
            "seasonal_strength_24": _num(r["seasonal_strength_24"]) or 0.0,
            "seasonal_strength_168": _num(r["seasonal_strength_168"]) or 0.0,
            "trend_slope": _num(r["trend_slope"]) or 0.0,
        }
        row["chosen_model"] = choose_model(r)
        out.append(row)
    chdb.insert_rows("rca.series_profile", out)
    return out


def main():
    rows = run()
    by_model: dict[str, int] = {}
    for r in rows:
        by_model[r["chosen_model"]] = by_model.get(r["chosen_model"], 0) + 1
    print(f"profiled {len(rows)} series")
    for m, n in sorted(by_model.items(), key=lambda kv: -kv[1]):
        print(f"  {m:16s} {n}")
    g = [r for r in rows if r["dimension"] == "global"]
    print("\nglobal series:")
    for r in sorted(g, key=lambda r: r["metric"]):
        print(f"  {r['metric']:12s} model={r['chosen_model']:12s} fft={r['fft_period']:6.1f} "
              f"s24={r['seasonal_strength_24']:.2f} s168={r['seasonal_strength_168']:.2f} "
              f"trend={r['trend_slope']:+.2f}%/wk vol/h={r['median_hourly_volume']:.0f}")


if __name__ == "__main__":
    main()
