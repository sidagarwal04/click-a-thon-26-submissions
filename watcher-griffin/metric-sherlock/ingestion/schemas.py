"""Typed record shapes, defined locally (not imported from clickhouse/schema.sql).

Field names/types mirror the star schema in clickhouse/schema.sql. Enum
membership is deliberately NOT enforced here via Literal types — that would
hardcode the dimension values at class-definition time. Enum checks live in
validators.py against config.py's (env-overridable) value sets instead.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class AdEventRecord(BaseModel):
    # Explicit, documented policy: unexpected columns are dropped, not an
    # error. transformers.py already whitelists known fields before this
    # model is ever constructed -- this is defense in depth, not the only
    # place the policy is enforced.
    model_config = ConfigDict(extra="ignore")

    event_time: datetime
    app_id: str
    geo_device_id: str
    advertiser_id: str = ""
    ad_format: str
    is_filled: int
    is_impression: int
    is_click: int
    revenue: float

    @field_validator("is_filled", "is_impression", "is_click")
    @classmethod
    def _must_be_binary(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError(f"must be 0 or 1, got {v!r}")
        return v


class AppRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app_id: str
    category: str
    publisher_tier: str


class AdvertiserRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    advertiser_id: str
    vertical: str
    campaign_type: str


class GeoDeviceRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    geo_device_id: str
    region: str
    country: str
    device_model: str
    os_version: str


MODEL_BY_ENTITY = {
    "ad_events": AdEventRecord,
    "apps": AppRecord,
    "advertisers": AdvertiserRecord,
    "geo_device": GeoDeviceRecord,
}

ENTITIES = tuple(MODEL_BY_ENTITY.keys())
