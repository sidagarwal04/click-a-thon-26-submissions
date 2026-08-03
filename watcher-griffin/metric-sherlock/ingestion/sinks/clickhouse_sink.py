"""Real sink: batched INSERTs into ClickHouse via clickhouse-connect.

The pipeline already micro-batches (BATCH_MAX_ROWS/BATCH_MAX_SECONDS), so
each write() is one bounded, retried INSERT -- never a bare client call
(repo principle: bounded, resilient ClickHouse access).
"""

import time
from typing import Any, Dict, List

from . import Sink

COLUMNS_BY_ENTITY = {
    "ad_events": (
        "event_time", "app_id", "geo_device_id", "advertiser_id", "ad_format",
        "is_filled", "is_impression", "is_click", "revenue",
    ),
    "apps": ("app_id", "category", "publisher_tier"),
    "advertisers": ("advertiser_id", "vertical", "campaign_type"),
    "geo_device": ("geo_device_id", "region", "country", "device_model", "os_version"),
}


class ClickHouseSink(Sink):
    def __init__(self, client, max_retries: int = 3, backoff_seconds: float = 0.5, sleep=time.sleep):
        self.client = client
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep

    def write(self, entity: str, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        columns = COLUMNS_BY_ENTITY[entity]
        data = [[row[c] for c in columns] for row in rows]
        for attempt in range(self.max_retries):
            try:
                self.client.insert(entity, data, column_names=list(columns))
                return
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                self.sleep(self.backoff_seconds * (2 ** attempt))
