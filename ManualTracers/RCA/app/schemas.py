from datetime import datetime

from pydantic import BaseModel


class ClickStackAlertPayload(BaseModel):
    """Body ClickStack sends. Its webhook template only exposes {{title}}, {{body}}, {{link}} —
    no structured metric/segment fields — so that's all this model can carry for now."""

    title: str
    body: str
    link: str | None = None


class GlobalSeriesRequest(BaseModel):
    """docs/RCA_UI_TEMPLATE.md Step 3 — backs POST /internal/global-series."""

    metric_id: str
    start: datetime
    end: datetime


class SegmentSeriesRequest(GlobalSeriesRequest):
    """Backs POST /internal/segment-series. dim_name is validated against the registry
    whitelist inside investigate.reproduce_segment, not here — this model only shapes the
    request."""

    dim_name: str
    dim_values: list[str] | None = None
