# Bronze — raw landing (`default`)

ClickPipes syncs from **ClickHouse managed Postgres** (`clickathon` schema) into these tables:

| File | Table | Source |
|------|-------|--------|
| `01_clickathon_ad_events.sql` | `default.clickathon_ad_events` | ~9M ad request rows |
| `02_clickathon_advertisers.sql` | `default.clickathon_advertisers` | 500 advertisers |
| `03_clickathon_apps.sql` | `default.clickathon_apps` | 2,000 apps |
| `04_clickathon_geo_device.sql` | `default.clickathon_geo_device` | 5,000 geo/device profiles |

Engine: `SharedReplacingMergeTree` with `_peerdb_version` for CDC deduplication.

**Upstream:** load Postgres first with `inmobi-ingest` (see repo root `README.md`), then configure ClickPipes destination to these table names.
