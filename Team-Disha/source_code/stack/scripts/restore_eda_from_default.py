"""Restore eda.ad_events (+ dims/rollup) from default.* after a planted upload."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from clickathon.ch import command, query_one  # noqa: E402
from clickathon.config import get_settings  # noqa: E402


def main() -> int:
    if get_settings().clickhouse_rca_database != "eda":
        print("safety: expected CLICKHOUSE_RCA_DATABASE=eda", file=sys.stderr)
        return 1

    print("refresh dims ...")
    command("TRUNCATE TABLE apps")
    command("INSERT INTO apps SELECT * FROM default.apps")
    command("TRUNCATE TABLE advertisers")
    command("INSERT INTO advertisers SELECT * FROM default.advertisers")
    command("TRUNCATE TABLE geo_device")
    command("INSERT INTO geo_device SELECT * FROM default.geo_device")

    print("rebuild eda.ad_events from default.ad_events ...")
    command("TRUNCATE TABLE ad_events")
    command(
        """
        INSERT INTO ad_events
        SELECT
          event_time,
          app_id,
          geo_device_id,
          advertiser_id,
          ad_format,
          is_filled,
          is_impression,
          is_click,
          revenue,
          toDate(event_time) AS event_date,
          toUInt8(toHour(event_time)) AS event_hour,
          toUInt8(toDayOfWeek(event_time)) AS event_dow,
          toUInt8(toDayOfWeek(event_time) IN (6, 7)) AS is_weekend,
          toUInt8(advertiser_id != '') AS has_advertiser
        FROM default.ad_events
        """
    )
    n = query_one("SELECT count() AS c FROM ad_events")["c"]
    print(f"eda.ad_events={n}")
    print("Next: uv run clickathon materialize --rollup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
