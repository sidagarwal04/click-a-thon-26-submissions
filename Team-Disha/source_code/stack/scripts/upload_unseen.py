"""Load Day-2 InMobi unseen_data into eda as a SEPARATE dataset (replace, no append).

- Truncates eda.ad_events and loads ONLY unseen Jul 6–10 events
- Replaces apps / advertisers / geo_device with regenerated CSVs from the release
- Does NOT touch default.*

Spec: click-a-thon-2026/InMobi/unseen_data/spec.md
Restore original later: uv run python stack/scripts/restore_eda_from_default.py
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

DEFAULT_UNSEEN = ROOT.parent / "click-a-thon-2026" / "InMobi" / "unseen_data"
FALLBACK_UNSEEN = ROOT.parent / "InMobi" / "unseen_data"
BATCH = 250_000


def _find_unseen() -> Path:
    for cand in (
        Path(sys.argv[1]) if len(sys.argv) > 1 else None,
        DEFAULT_UNSEEN,
        FALLBACK_UNSEEN,
        ROOT / "data" / "unseen_data",
    ):
        if cand and (cand / "ad_events.parquet").is_file():
            return cand
    raise FileNotFoundError(
        "unseen_data not found — pass path as argv[1] or clone "
        "sidagarwal04/click-a-thon-2026 with InMobi/unseen_data/"
    )


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    ts = pd.to_datetime(df["event_time"])
    return pd.DataFrame(
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
            "event_dow": (ts.dt.dayofweek + 1).astype("uint8"),
            "is_weekend": ts.dt.dayofweek.isin([5, 6]).astype("uint8"),
            "has_advertiser": (df["advertiser_id"].fillna("").astype(str) != "").astype("uint8"),
        }
    )


def _load_dims(client, unseen: Path) -> None:
    print("REPLACE dims from unseen CSVs (regenerated attributes) ...")
    apps = pd.read_csv(unseen / "apps.csv")
    advertisers = pd.read_csv(unseen / "advertisers.csv")
    geo = pd.read_csv(unseen / "geo_device.csv")
    for frame in (apps, advertisers, geo):
        for col in frame.columns:
            frame[col] = frame[col].astype(str)

    command("TRUNCATE TABLE apps")
    client.insert_df("apps", apps)
    command("TRUNCATE TABLE advertisers")
    client.insert_df("advertisers", advertisers)
    command("TRUNCATE TABLE geo_device")
    client.insert_df("geo_device", geo)
    print(f"  apps={len(apps)} advertisers={len(advertisers)} geo_device={len(geo)}")


def main() -> int:
    settings = get_settings()
    if settings.clickhouse_rca_database != "eda":
        print("safety: CLICKHOUSE_RCA_DATABASE must be eda", file=sys.stderr)
        return 1

    unseen = _find_unseen()
    print(f"unseen dir: {unseen}")

    client = get_client()
    before = query_one(
        "SELECT count() AS c, min(event_date) AS mn, max(event_date) AS mx FROM ad_events"
    )
    print(f"eda.ad_events before: {before}")

    _load_dims(client, unseen)

    print(f"reading {unseen / 'ad_events.parquet'} ...")
    raw = pd.read_parquet(unseen / "ad_events.parquet")
    print(f"rows={len(raw):,} range={raw['event_time'].min()} → {raw['event_time'].max()}")
    enriched = _enrich(raw)

    print("TRUNCATE eda.ad_events and load ONLY unseen (no append) ...")
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

    after = query_one(
        """
        SELECT
          count() AS c,
          min(event_date) AS mn,
          max(event_date) AS mx
        FROM ad_events
        """
    )
    print(f"eda.ad_events after: {after}")
    print("Next: uv run clickathon materialize --rollup")
    print("Restore original later: uv run python stack/scripts/restore_eda_from_default.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
