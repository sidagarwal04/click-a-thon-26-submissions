"""Incremental ingest via HTTP - the complement to scripts/load_data.sh's
bulk file drop, for data that arrives event-by-event instead of as a file."""
from . import db, schemas

_COLUMNS = [
    "event_time",
    "app_id",
    "geo_device_id",
    "advertiser_id",
    "ad_format",
    "is_filled",
    "is_impression",
    "is_click",
    "revenue",
]


def insert_events(events: list[schemas.EventIn]) -> dict:
    admin = db.get_admin_client()
    rows = [
        [
            e.event_time,
            e.app_id,
            e.geo_device_id,
            e.advertiser_id,
            e.ad_format,
            e.is_filled,
            e.is_impression,
            e.is_click,
            e.revenue,
        ]
        for e in events
    ]
    admin.insert("inmobi_rca.ad_events", rows, column_names=_COLUMNS)
    return {"inserted": len(rows)}
