"""Copy InMobi ad_events.parquet and plant NEW anomaly types (v2 test set).

Existing planted (leave intact): Android 15 fill, iOS×APAC fill, interstitial×EU eCPM, Jun-21 volume.
New plants (answer key written beside the parquet):
  P1 fill_rate  — Android 14 (single OS)           2026-07-01..02
  P2 fill_rate  — Android 13 x NAM (combo)         2026-07-03..04
  P3 ecpm       — video x NAM (format x region)    2026-06-10..12
  P4 requests   — global volume drop               2026-07-05
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(r"F:\Clickhouse hackathon\click-a-thon-2026\InMobi\data\ad_events.parquet")
GEO = Path(r"F:\Clickhouse hackathon\click-a-thon-2026\InMobi\data\geo_device.csv")
OUT_DIR = ROOT / "data"
OUT_PARQUET = OUT_DIR / "ad_events_planted_v2.parquet"
OUT_KEY = OUT_DIR / "planted_v2_answer_key.json"

RNG = np.random.default_rng(20260802)


def _unfill(df: pd.DataFrame, mask: pd.Series) -> int:
    n = int(mask.sum())
    if n == 0:
        return 0
    df.loc[mask, "is_filled"] = 0
    df.loc[mask, "is_impression"] = 0
    df.loc[mask, "is_click"] = 0
    df.loc[mask, "revenue"] = 0.0
    df.loc[mask, "advertiser_id"] = ""
    return n


def main() -> int:
    if not SRC.exists():
        print(f"missing source parquet: {SRC}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"reading {SRC} ...")
    df = pd.read_parquet(SRC)
    geo = pd.read_csv(GEO)
    df = df.merge(geo[["geo_device_id", "os_version", "region"]], on="geo_device_id", how="left")
    df["event_date"] = pd.to_datetime(df["event_time"]).dt.normalize()
    n0 = len(df)
    print(f"rows={n0:,}")

    plants: list[dict] = []

    # P1 — Android 14 fill collapse (single-OS), Jul 1-2
    m1 = (
        df["os_version"].eq("Android 14")
        & df["event_date"].isin(pd.to_datetime(["2026-07-01", "2026-07-02"]))
        & df["is_filled"].eq(1)
        & (RNG.random(len(df)) < 0.72)
    )
    n1 = _unfill(df, m1)
    plants.append(
        {
            "id": "P1",
            "label": "android14_fill",
            "factor": "fill_rate",
            "window_start": "2026-07-01",
            "window_end": "2026-07-02",
            "segment_any": ["Android 14"],
            "mechanism": "unfill ~72% of Android 14 filled requests",
            "rows_touched": n1,
        }
    )
    print(f"P1 Android 14 fill: unfilled {n1:,}")

    # P2 — Android 13 x NAM fill combo, Jul 3-4
    m2 = (
        df["os_version"].eq("Android 13")
        & df["region"].eq("NAM")
        & df["event_date"].isin(pd.to_datetime(["2026-07-03", "2026-07-04"]))
        & df["is_filled"].eq(1)
        & (RNG.random(len(df)) < 0.78)
    )
    n2 = _unfill(df, m2)
    plants.append(
        {
            "id": "P2",
            "label": "android13_nam_fill",
            "factor": "fill_rate",
            "window_start": "2026-07-03",
            "window_end": "2026-07-04",
            "segment_any": ["Android 13", "NAM"],
            "mechanism": "unfill ~78% of Android 13 x NAM filled requests",
            "rows_touched": n2,
        }
    )
    print(f"P2 Android 13 x NAM fill: unfilled {n2:,}")

    # P3 — video x NAM eCPM crash, Jun 10-12 (cut revenue on impressions)
    m3 = (
        df["ad_format"].eq("video")
        & df["region"].eq("NAM")
        & df["event_date"].isin(pd.to_datetime(["2026-06-10", "2026-06-11", "2026-06-12"]))
        & df["is_impression"].eq(1)
        & df["revenue"].gt(0)
    )
    n3 = int(m3.sum())
    df.loc[m3, "revenue"] = df.loc[m3, "revenue"] * 0.35
    plants.append(
        {
            "id": "P3",
            "label": "video_nam_ecpm",
            "factor": "ecpm",
            "window_start": "2026-06-10",
            "window_end": "2026-06-12",
            "segment_any": ["video", "NAM"],
            "mechanism": "multiply revenue by 0.35 on video x NAM impressions",
            "rows_touched": n3,
        }
    )
    print(f"P3 video x NAM eCPM: scaled {n3:,} impression rows")

    # P4 — global volume drop Jul 5 (drop ~28% of all requests that day)
    m4 = df["event_date"].eq(pd.Timestamp("2026-07-05"))
    drop4 = m4 & (RNG.random(len(df)) < 0.28)
    n4 = int(drop4.sum())
    df = df.loc[~drop4].copy()
    plants.append(
        {
            "id": "P4",
            "label": "global_volume_jul5",
            "factor": "requests",
            "window_start": "2026-07-05",
            "window_end": "2026-07-05",
            "segment_any": ["ALL", "global"],
            "mechanism": "delete ~28% of all events on 2026-07-05",
            "rows_touched": n4,
        }
    )
    print(f"P4 global volume Jul 5: deleted {n4:,} rows; remaining {len(df):,}")

    # Drop helper cols before write (match original parquet schema)
    out = df.drop(columns=["os_version", "region", "event_date"])
    print(f"writing {OUT_PARQUET} ...")
    out.to_parquet(OUT_PARQUET, index=False)

    key = {
        "source": str(SRC),
        "output": str(OUT_PARQUET),
        "rows_in": n0,
        "rows_out": len(out),
        "note": (
            "NEW anomalies only. Original planted incidents in the source parquet remain. "
            "Pipeline should find P1-P4 in addition to prior calibration windows."
        ),
        "anomalies": plants,
    }
    OUT_KEY.write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"wrote answer key {OUT_KEY}")
    print(json.dumps(plants, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
