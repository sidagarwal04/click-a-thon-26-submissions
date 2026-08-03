"""Inspect CH dims + local parquet for anomaly planting."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from clickathon.ch import query_rows  # noqa: E402


def main() -> None:
    queries = [
        "SELECT min(event_date) AS a, max(event_date) AS b, count() AS c FROM ad_events",
        "SELECT ad_format, count() AS c FROM ad_events GROUP BY 1 ORDER BY c DESC",
        """
        SELECT g.os_version AS os_version, count() AS c
        FROM ad_events AS e
        INNER JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id
        GROUP BY 1 ORDER BY c DESC LIMIT 15
        """,
        """
        SELECT g.region AS region, count() AS c
        FROM ad_events AS e
        INNER JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id
        GROUP BY 1 ORDER BY c DESC
        """,
        """
        SELECT a.category AS category, count() AS c
        FROM ad_events AS e
        INNER JOIN apps AS a ON e.app_id = a.app_id
        GROUP BY 1 ORDER BY c DESC LIMIT 12
        """,
        """
        SELECT g.os_version, g.region, count() AS c
        FROM ad_events AS e
        INNER JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id
        WHERE g.os_version IN ('Android 14', 'iOS 17.4', 'iOS 16.7', 'Android 13')
        GROUP BY 1, 2 ORDER BY c DESC LIMIT 20
        """,
        """
        SELECT e.ad_format, g.region, count() AS c, sum(e.revenue) AS rev
        FROM ad_events AS e
        INNER JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id
        WHERE e.ad_format IN ('rewarded', 'banner', 'native', 'video')
        GROUP BY 1, 2 ORDER BY rev DESC LIMIT 20
        """,
    ]
    for q in queries:
        print("====")
        print(q.strip()[:120])
        for row in query_rows(q):
            print(row)


if __name__ == "__main__":
    main()
