"""The strong validation layer — business rules run on an already-normalized,
schema-typed record. Every function returns the FULL list of violations
(never fail-fast), so a rejected record's dead-letter entry shows everything
wrong with it at once, not just the first problem found.
"""

from typing import Any, Dict, List

from .config import Config

Row = Dict[str, Any]


def validate_ad_event(record: Row, cfg: Config) -> List[str]:
    errors: List[str] = []

    if not record.get("app_id"):
        errors.append("app_id must be non-empty")
    if not record.get("geo_device_id"):
        errors.append("geo_device_id must be non-empty")

    fmt = record.get("ad_format")
    if fmt not in cfg.AD_FORMATS:
        errors.append(f"ad_format '{fmt}' not in allowed set {sorted(cfg.AD_FORMATS)}")

    filled, impression, click = record.get("is_filled"), record.get("is_impression"), record.get("is_click")
    if not (click <= impression <= filled):
        errors.append(
            f"funnel violated: is_click={click} <= is_impression={impression} <= "
            f"is_filled={filled} does not hold"
        )

    revenue = record.get("revenue", 0)
    if impression == 0 and revenue != 0:
        errors.append(f"revenue must be 0 when is_impression=0, got {revenue}")
    if revenue < 0:
        errors.append(f"revenue must be >= 0, got {revenue}")

    advertiser_id = record.get("advertiser_id", "")
    if filled == 0 and advertiser_id != "":
        errors.append(f"advertiser_id must be empty when is_filled=0, got '{advertiser_id}'")
    if filled == 1 and advertiser_id == "":
        errors.append("advertiser_id must be non-empty when is_filled=1")

    return errors


def validate_app(record: Row, cfg: Config) -> List[str]:
    errors: List[str] = []
    if not record.get("app_id"):
        errors.append("app_id must be non-empty")
    if record.get("category") not in cfg.CATEGORIES:
        errors.append(f"category '{record.get('category')}' not in allowed set {sorted(cfg.CATEGORIES)}")
    if record.get("publisher_tier") not in cfg.PUBLISHER_TIERS:
        errors.append(
            f"publisher_tier '{record.get('publisher_tier')}' not in allowed set {sorted(cfg.PUBLISHER_TIERS)}"
        )
    return errors


def validate_advertiser(record: Row, cfg: Config) -> List[str]:
    errors: List[str] = []
    if not record.get("advertiser_id"):
        errors.append("advertiser_id must be non-empty")
    if record.get("vertical") not in cfg.VERTICALS:
        errors.append(f"vertical '{record.get('vertical')}' not in allowed set {sorted(cfg.VERTICALS)}")
    if record.get("campaign_type") not in cfg.CAMPAIGN_TYPES:
        errors.append(
            f"campaign_type '{record.get('campaign_type')}' not in allowed set {sorted(cfg.CAMPAIGN_TYPES)}"
        )
    return errors


def validate_geo_device(record: Row, cfg: Config) -> List[str]:
    errors: List[str] = []
    if not record.get("geo_device_id"):
        errors.append("geo_device_id must be non-empty")

    region = record.get("region")
    if region == "NA":
        errors.append("region 'NA' is invalid -- 'NA' is commonly misread as null; did you mean 'NAM'?")
    elif region not in cfg.REGIONS:
        errors.append(f"region '{region}' not in allowed set {sorted(cfg.REGIONS)}")

    return errors


VALIDATE_BY_ENTITY = {
    "ad_events": validate_ad_event,
    "apps": validate_app,
    "advertisers": validate_advertiser,
    "geo_device": validate_geo_device,
}


def validate(entity: str, record: Row, cfg: Config) -> List[str]:
    fn = VALIDATE_BY_ENTITY.get(entity)
    if fn is None:
        raise ValueError(f"unknown entity '{entity}'")
    return fn(record, cfg)
