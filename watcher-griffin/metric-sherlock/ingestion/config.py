"""Own config for the ingestion module — env-driven, no imports from engine/config.py.

Every enum set and threshold below is a default that env vars can override, so
an unseen dataset with a new dimension value or a different throughput profile
doesn't require a code change.
"""

import os
from typing import Iterable, Set


def _env_set(name: str, default: Iterable[str]) -> Set[str]:
    raw = os.environ.get(name)
    if not raw:
        return set(default)
    return {v.strip() for v in raw.split(",") if v.strip()}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


class Config:
    def __init__(self) -> None:
        self.AD_FORMATS = _env_set(
            "INGEST_AD_FORMATS", ["banner", "interstitial", "native", "rewarded", "video"]
        )
        self.CATEGORIES = _env_set(
            "INGEST_CATEGORIES",
            ["gaming", "social", "entertainment", "news", "ecommerce", "utility", "finance"],
        )
        self.PUBLISHER_TIERS = _env_set("INGEST_PUBLISHER_TIERS", ["tier_1", "tier_2", "tier_3"])
        self.VERTICALS = _env_set(
            "INGEST_VERTICALS",
            ["gaming", "ecommerce", "finance", "travel", "entertainment", "auto", "cpg"],
        )
        self.CAMPAIGN_TYPES = _env_set("INGEST_CAMPAIGN_TYPES", ["CPM", "CPC", "CPI"])
        self.REGIONS = _env_set("INGEST_REGIONS", ["NAM", "EU", "APAC", "LATAM", "MEA"])

        self.BATCH_MAX_ROWS = _env_int("INGEST_BATCH_MAX_ROWS", 5000)
        self.BATCH_MAX_SECONDS = _env_float("INGEST_BATCH_MAX_SECONDS", 5.0)
        self.POLL_INTERVAL_SECONDS = _env_float("INGEST_POLL_INTERVAL_SECONDS", 2.0)
        self.FILE_CHUNK_SIZE = _env_int("INGEST_FILE_CHUNK_SIZE", 10000)


def load_config() -> Config:
    return Config()
