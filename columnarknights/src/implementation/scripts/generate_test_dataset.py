#!/usr/bin/env python3
"""Generates a synthetic ad-events dataset for pre-flight validation of the
RCA pipeline ahead of tomorrow's real (unseen) batch dataset.

Reuses the existing dimension tables (data/apps.csv, data/advertisers.csv,
data/geo_device.csv) as the universe of apps/advertisers/devices -- only the
event stream itself is regenerated, over a NEW date range disjoint from the
real sample data, with a handful of DELIBERATELY PLANTED anomalies whose
ground truth (window, metric, dimension, value, mechanism) is known in
advance and written to a manifest. That lets scripts/validate_test_dataset.py
run the real pipeline against this data and assert it found the right
answer, not just that it ran without crashing.

Output:
  data/test_ad_events.parquet        -- same schema as data/ad_events.parquet
  implementation/test_data_ground_truth.json

Usage: python3 scripts/generate_test_dataset.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
DATA_DIR = ROOT / "data"
OUT_PARQUET = DATA_DIR / "test_ad_events.parquet"
OUT_MANIFEST = Path(__file__).resolve().parent.parent / "test_data_ground_truth.json"

RNG = np.random.default_rng(20260105)

START_DATE = pd.Timestamp("2026-01-05")  # Monday
N_DAYS = 49  # 7 full weeks: 4 clean baseline weeks + 3 weeks carrying the planted anomalies
EVENTS_PER_DAY_BASE = 50_000

# Baseline rates, matched to the real sample dataset's observed values
# (see data/ad_events.parquet: fill_rate~0.781, render_rate~0.980, ctr~0.0109,
# revenue/impression~0.00247).
BASE_FILL_RATE = 0.78
BASE_RENDER_RATE = 0.98
BASE_CTR = 0.011
BASE_REVENUE_PER_IMPRESSION = 0.0025

AD_FORMATS = ["native", "video", "banner", "interstitial", "rewarded"]


def load_dimension_tables():
    apps = pd.read_csv(DATA_DIR / "apps.csv")
    advertisers = pd.read_csv(DATA_DIR / "advertisers.csv")
    geo = pd.read_csv(DATA_DIR / "geo_device.csv")
    return apps, advertisers, geo


def day_seasonality(dates: pd.DatetimeIndex) -> np.ndarray:
    """Weekday demand ~1.0x, weekend ~0.85x -- so a real judge poking at a
    weekend dip doesn't mistake ordinary seasonality for an incident."""
    dow = dates.dayofweek.values  # 0=Mon .. 6=Sun
    return np.where(dow >= 5, 0.85, 1.0)


def generate():
    apps, advertisers, geo = load_dimension_tables()
    dates = pd.date_range(START_DATE, periods=N_DAYS, freq="D")
    seasonality = day_seasonality(dates)

    manifest = {"date_range": [str(dates[0].date()), str(dates[-1].date())], "scenarios": []}

    all_frames = []
    for day_idx, day in enumerate(dates):
        n_events = int(EVENTS_PER_DAY_BASE * seasonality[day_idx] * RNG.normal(1.0, 0.03))

        # ---- Scenario C: broad-based request-volume crash, single day ----
        if day == pd.Timestamp("2026-02-09"):
            n_events = int(n_events * 0.55)  # -45% across the board, no dimension bias

        app_rows = apps.sample(n=n_events, replace=True, random_state=RNG.integers(1e9)).reset_index(drop=True)
        geo_rows = geo.sample(n=n_events, replace=True, random_state=RNG.integers(1e9)).reset_index(drop=True)
        adv_rows = advertisers.sample(n=n_events, replace=True, random_state=RNG.integers(1e9)).reset_index(drop=True)
        ad_format = RNG.choice(AD_FORMATS, size=n_events)

        event_time = day + pd.to_timedelta(RNG.integers(0, 86_400_000, size=n_events), unit="ms")

        fill_rate = np.full(n_events, BASE_FILL_RATE)
        render_rate = np.full(n_events, BASE_RENDER_RATE)
        ctr = np.full(n_events, BASE_CTR)
        revenue_per_impr = np.full(n_events, BASE_REVENUE_PER_IMPRESSION)

        # ---- Scenario A: localized fill_rate drop, os_version=Android 12 ----
        if pd.Timestamp("2026-02-03") <= day <= pd.Timestamp("2026-02-05"):
            mask = geo_rows["os_version"].values == "Android 12"
            fill_rate = np.where(mask, 0.45, fill_rate)

        # ---- Scenario B: localized eCPM/revenue drop, category=finance x ad_format=video ----
        if pd.Timestamp("2026-02-10") <= day <= pd.Timestamp("2026-02-12"):
            mask = (app_rows["category"].values == "finance") & (ad_format == "video")
            revenue_per_impr = np.where(mask, BASE_REVENUE_PER_IMPRESSION * 0.4, revenue_per_impr)

        # ---- Scenario D: localized CTR spike, country=DE ----
        if pd.Timestamp("2026-02-17") <= day <= pd.Timestamp("2026-02-18"):
            mask = geo_rows["country"].values == "DE"
            ctr = np.where(mask, BASE_CTR * 2.6, ctr)

        # daily noise on top of the (possibly overridden) rates
        fill_rate = np.clip(fill_rate * RNG.normal(1.0, 0.015, size=n_events), 0, 1)
        render_rate = np.clip(render_rate * RNG.normal(1.0, 0.01, size=n_events), 0, 1)
        ctr = np.clip(ctr * RNG.normal(1.0, 0.02, size=n_events), 0, 1)

        is_filled = (RNG.random(n_events) < fill_rate).astype("uint8")
        is_impression = ((RNG.random(n_events) < render_rate) & (is_filled == 1)).astype("uint8")
        is_click = ((RNG.random(n_events) < ctr) & (is_impression == 1)).astype("uint8")
        revenue = np.where(
            is_impression == 1,
            np.clip(revenue_per_impr * RNG.normal(1.0, 0.15, size=n_events), 0, None),
            0.0,
        )

        frame = pd.DataFrame({
            "event_time": event_time,
            "app_id": app_rows["app_id"].values,
            "geo_device_id": geo_rows["geo_device_id"].values,
            "advertiser_id": np.where(is_filled == 1, adv_rows["advertiser_id"].values, ""),
            "ad_format": ad_format,
            "is_filled": is_filled,
            "is_impression": is_impression,
            "is_click": is_click,
            "revenue": revenue.astype("float64"),
        })
        all_frames.append(frame)

    full = pd.concat(all_frames, ignore_index=True).sort_values("event_time").reset_index(drop=True)
    full["event_time"] = full["event_time"].astype("datetime64[ms]")
    full.to_parquet(OUT_PARQUET, index=False)

    manifest["scenarios"] = [
        {
            "name": "A_fill_rate_localized",
            "metric": "fill_rate",
            "window": ["2026-02-03", "2026-02-05"],
            "expected_direction": "down",
            "expected_dimension": "os_version",
            "expected_value": "Android 12",
            "expected_depth": 1,
            "mechanism": "fill probability dropped 0.78 -> 0.45 for os_version=Android 12 only",
        },
        {
            "name": "B_ecpm_revenue_localized_2level",
            "metric": "ecpm",
            "window": ["2026-02-10", "2026-02-12"],
            "expected_direction": "down",
            "expected_dimension_path": [["category", "finance"], ["ad_format", "video"]],
            "expected_depth": 2,
            "mechanism": "revenue-per-impression cut 60% for category=finance AND ad_format=video only",
        },
        {
            "name": "C_requests_broad_based",
            "metric": "requests",
            "window": ["2026-02-09", "2026-02-09"],
            "expected_direction": "down",
            "expected_dimension": None,
            "expected_depth": 0,
            "mechanism": "total row count cut 45% uniformly at random, no dimension bias -- must NOT localize",
        },
        {
            "name": "D_ctr_localized_spike",
            "metric": "ctr",
            "window": ["2026-02-17", "2026-02-18"],
            "expected_direction": "up",
            "expected_dimension": "country",
            "expected_value": "DE",
            "expected_depth": 1,
            "mechanism": "click probability raised ~2.6x for country=DE only",
        },
    ]
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2))

    print(f"Wrote {len(full):,} rows to {OUT_PARQUET}")
    print(f"Wrote ground truth manifest to {OUT_MANIFEST}")
    print(f"Date range: {dates[0].date()} .. {dates[-1].date()}")


if __name__ == "__main__":
    generate()
