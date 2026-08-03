"""PostgreSQL schema for the InMobi star schema."""

SCHEMA_NAME = "clickathon"

TABLES = ("apps", "advertisers", "geo_device", "ad_events")

CREATE_SCHEMA = f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};"

DROP_TABLES = "\n".join(
    f"DROP TABLE IF EXISTS {SCHEMA_NAME}.{table} CASCADE;" for table in reversed(TABLES)
)

CREATE_TABLES = f"""
CREATE TABLE {SCHEMA_NAME}.apps (
    app_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    publisher_tier TEXT NOT NULL
);

CREATE TABLE {SCHEMA_NAME}.advertisers (
    advertiser_id TEXT PRIMARY KEY,
    vertical TEXT NOT NULL,
    campaign_type TEXT NOT NULL
);

CREATE TABLE {SCHEMA_NAME}.geo_device (
    geo_device_id TEXT PRIMARY KEY,
    region TEXT NOT NULL,
    country TEXT NOT NULL,
    device_model TEXT NOT NULL,
    os_version TEXT NOT NULL
);

CREATE TABLE {SCHEMA_NAME}.ad_events (
    id BIGSERIAL PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL,
    app_id TEXT NOT NULL,
    geo_device_id TEXT NOT NULL,
    advertiser_id TEXT,
    ad_format TEXT NOT NULL,
    is_filled SMALLINT NOT NULL,
    is_impression SMALLINT NOT NULL,
    is_click SMALLINT NOT NULL,
    revenue DOUBLE PRECISION NOT NULL
);

CREATE INDEX idx_ad_events_event_time ON {SCHEMA_NAME}.ad_events (event_time);
CREATE INDEX idx_ad_events_app_id ON {SCHEMA_NAME}.ad_events (app_id);
CREATE INDEX idx_ad_events_geo_device_id ON {SCHEMA_NAME}.ad_events (geo_device_id);
CREATE INDEX idx_ad_events_advertiser_id ON {SCHEMA_NAME}.ad_events (advertiser_id);
CREATE INDEX idx_ad_events_ad_format ON {SCHEMA_NAME}.ad_events (ad_format);
"""
