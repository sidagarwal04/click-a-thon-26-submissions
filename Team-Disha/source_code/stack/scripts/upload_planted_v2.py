"""Upload data/ad_events_planted_v2.parquet into eda.ad_events (enriched).

Does NOT touch default.ad_events. Restore with:
  uv run python stack/scripts/restore_eda_from_default.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from clickathon.ch import command, get_client, query_one  # noqa: E402
from clickathon.config import get_settings  # noqa: E402

PARQUET = ROOT / "data" / "ad_events_planted_v2.parquet"
BATCH = 250_000


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    ts = pd.to_datetime(df["event_time"])
    out = pd.DataFrame(
        {
            "event_time": ts,
            "app_id": df["app_id"].astype(str),
            "geo_device_id": df["geo_device_id"].astype(str),
            "advertiser_id": df["advertiser_id"].fillna("").astype(str),
            "ad_format": df["ad_format"].astype(str),
            "is_filled": df["is_filled"].astype("uint8"),
            "is_impression": df["is_impression"].astype("uint8"),
            "is_click": df["is_click"].astype("uint8"),
            "revenue": df["revenue"].astype("float64"),
            "event_date": ts.dt.date,
            "event_hour": ts.dt.hour.astype("uint8"),
            # pandas Mon=0..Sun=6 -> ClickHouse toDayOfWeek Mon=1..Sun=7
            "event_dow": (ts.dt.dayofweek + 1).astype("uint8"),
            "is_weekend": ts.dt.dayofweek.isin([5, 6]).astype("uint8"),
            "has_advertiser": (df["advertiser_id"].fillna("").astype(str) != "").astype("uint8"),
        }
    )
    return out


def main() -> int:
    if not PARQUET.exists():
        print(f"missing {PARQUET} — run plant_anomalies_v2.py first", file=sys.stderr)
        return 1

    settings = get_settings()
    if settings.clickhouse_rca_database != "eda":
        print("safety: CLICKHOUSE_RCA_DATABASE must be eda for this upload", file=sys.stderr)
        return 1

    client = get_client()
    print("refresh dims from default.* ...")
    command("TRUNCATE TABLE apps")
    command("INSERT INTO apps SELECT * FROM default.apps")
    command("TRUNCATE TABLE advertisers")
    command("INSERT INTO advertisers SELECT * FROM default.advertisers")
    command("TRUNCATE TABLE geo_device")
    command("INSERT INTO geo_device SELECT * FROM default.geo_device")

    print(f"reading {PARQUET} ...")
    raw = pd.read_parquet(PARQUET)
    print(f"rows={len(raw):,}")
    enriched = _enrich(raw)

    print("TRUNCATE eda.ad_events ...")
    command("TRUNCATE TABLE ad_events")

    t0 = time.perf_counter()
    inserted = 0
    for start in range(0, len(enriched), BATCH):
        chunk = enriched.iloc[start : start + BATCH]
        client.insert_df("ad_events", chunk)
        inserted += len(chunk)
        elapsed = time.perf_counter() - t0
        rate = inserted / max(elapsed, 1e-6)
        print(f"  inserted {inserted:,}/{len(enriched):,} ({rate:,.0f} rows/s)")

    n = int(query_one("SELECT count() AS c FROM ad_events")["c"])
    print(f"eda.ad_events count={n}")
    print("Next: uv run clickathon materialize --rollup")
    print("Then:  uv run python stack/scripts/test_planted_v2.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
