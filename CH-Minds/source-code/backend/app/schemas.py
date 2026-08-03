from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    since_day: Optional[date] = None


class MetricThreshold(BaseModel):
    pct_threshold: float
    volume_floor: int
    n_samples: int
    dynamic: bool


class PartialDay(BaseModel):
    day: str
    note: Optional[str] = None


class ScanCoverage(BaseModel):
    days_loaded: int
    partial_days: list[PartialDay]
    skipped_insufficient_history: int
    min_baseline_samples: int


class ScanResponse(BaseModel):
    scanned: int
    new_candidates: int
    thresholds: dict[str, MetricThreshold]
    coverage: ScanCoverage


class InvestigateRequest(BaseModel):
    metric: str
    day: date
    anomaly_candidate_id: Optional[str] = None


class AskContext(BaseModel):
    metric: Optional[str] = None
    day: Optional[date] = None
    dimension: Optional[str] = None
    value: Optional[str] = None


class AskRequest(BaseModel):
    question: str
    context: Optional[AskContext] = None


class EventIn(BaseModel):
    event_time: datetime
    app_id: str
    geo_device_id: str
    advertiser_id: str = ""
    ad_format: Literal["banner", "interstitial", "native", "rewarded", "video"]
    is_filled: Literal[0, 1]
    is_impression: Literal[0, 1]
    is_click: Literal[0, 1]
    revenue: float = 0.0


class IngestEventsRequest(BaseModel):
    events: list[EventIn] = Field(min_length=1)


class IngestEventsResponse(BaseModel):
    inserted: int
