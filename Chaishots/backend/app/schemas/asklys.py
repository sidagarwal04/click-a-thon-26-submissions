from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class AsklysModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


AsklysIntent = Literal["funnel", "trend", "user_path", "text"]


class AsklysColumn(AsklysModel):
    name: str
    data_type: str


class AsklysContextItem(AsklysModel):
    kind: Literal["table", "column"]
    label: str
    table: str
    column: str | None = None
    data_type: str | None = None
    description: str


class AsklysContextResponse(AsklysModel):
    database: str
    connected: bool = True
    items: list[AsklysContextItem] = Field(default_factory=list)


class AsklysContextRef(AsklysModel):
    kind: Literal["table", "column"]
    table: str
    column: str | None = None


class AsklysConversationMessage(AsklysModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AsklysQueryRequest(AsklysModel):
    question: str = Field(min_length=1, max_length=4000)
    context: list[AsklysContextRef] = Field(default_factory=list, max_length=12)
    conversation: list[AsklysConversationMessage] = Field(
        default_factory=list, max_length=12
    )


class AsklysPlan(AsklysModel):
    intent: AsklysIntent
    title: str = Field(min_length=1, max_length=120)
    sql: str | None = None
    reasoning: str = Field(min_length=1, max_length=800)
    metric_definition: str = Field(min_length=1, max_length=500)
    assumptions: list[str] = Field(default_factory=list, max_length=8)
    direct_answer: str | None = Field(default=None, max_length=1200)

    @model_validator(mode="after")
    def require_sql(self) -> "AsklysPlan":
        if self.intent != "text" and not self.sql:
            raise ValueError("Visual responses require SQL")
        return self


class AsklysReview(AsklysModel):
    decision: Literal["accept", "retry"]
    reason: str = Field(min_length=1, max_length=700)
    revised_sql: str | None = None

    @model_validator(mode="after")
    def require_revised_sql(self) -> "AsklysReview":
        if self.decision == "retry" and not self.revised_sql:
            raise ValueError("A retry decision requires revised SQL")
        return self


class AsklysNarrative(AsklysModel):
    answer: str = Field(min_length=1, max_length=1200)


class AsklysFunnelStep(AsklysModel):
    name: str
    value: float
    conversion_rate: float = Field(ge=0.0)
    previous_conversion_rate: float = Field(ge=0.0)
    dropoff: float = Field(ge=0.0)
    dropoff_rate: float = Field(ge=0.0)


class AsklysTrendPoint(AsklysModel):
    x: str
    y: float


class AsklysTrendSeries(AsklysModel):
    name: str
    points: list[AsklysTrendPoint]


class AsklysPathLink(AsklysModel):
    source: str
    target: str
    value: float


class AsklysVisualization(AsklysModel):
    kind: AsklysIntent
    funnel: list[AsklysFunnelStep] = Field(default_factory=list)
    series: list[AsklysTrendSeries] = Field(default_factory=list)
    paths: list[AsklysPathLink] = Field(default_factory=list)


class AsklysQueryResponse(AsklysModel):
    intent: AsklysIntent
    title: str
    answer: str
    visualization: AsklysVisualization | None = None
    sql: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, JsonValue]] = Field(default_factory=list)
    database: str
    context_used: list[str] = Field(default_factory=list)
    analysis_steps: list[str] = Field(default_factory=list)
    query_attempts: int = Field(default=0, ge=0)
    model: str
    langfuse_trace_id: str | None = None
