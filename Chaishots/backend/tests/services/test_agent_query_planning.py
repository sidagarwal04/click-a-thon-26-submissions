from typing import Any

from app.agents.fireworks import FireworksAgentError
from app.schemas.agents import AnalysisPlan, AnalysisQuery
from app.services.full_feature_workflow import FullFeatureWorkflow

_COLUMNS = {"checkout_events": ["event", "application_id", "device_type"]}
_ALLOWED = ["checkout_events"]


class _StubAgents:
    """Return canned plans and record what each attempt was given."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.inputs: list[Any] = []

    def complete(
        self,
        output_type: Any,
        *,
        name: str,
        system_prompt: str,
        input_payload: Any,
        max_tokens: int = 4096,
    ) -> Any:
        self.inputs.append(input_payload)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _workflow(responses: list[Any]) -> FullFeatureWorkflow:
    workflow = FullFeatureWorkflow.__new__(FullFeatureWorkflow)
    workflow._agents = _StubAgents(responses)  # type: ignore[assignment]
    return workflow


def _valid(query_id: str = "good") -> AnalysisQuery:
    return AnalysisQuery(
        query_id=query_id,
        analysis_type="funnel",
        purpose="p",
        sql=(
            "SELECT event, uniqExact(application_id) AS n FROM checkout_events "
            "GROUP BY event"
        ),
    )


def _invalid(query_id: str = "bad") -> AnalysisQuery:
    return AnalysisQuery(
        query_id=query_id,
        analysis_type="trend",
        purpose="p",
        sql="SELECT nonexistent_col FROM checkout_events",
    )


def test_invalid_agent_sql_is_fed_back_and_the_retry_is_accepted() -> None:
    corrected = AnalysisQuery(
        query_id="bad",
        analysis_type="trend",
        purpose="p",
        sql="SELECT device_type, count() AS n FROM checkout_events GROUP BY device_type",
    )
    workflow = _workflow(
        [
            AnalysisPlan(analyses=[_valid(), _invalid()]),
            AnalysisPlan(analyses=[corrected]),
        ]
    )

    _, accepted, rejections = workflow._plan_agent_queries(
        {"specification": "s"},
        allowed_tables=_ALLOWED,
        table_columns=_COLUMNS,
        reserved_ids=set(),
    )

    assert [analysis.query_id for analysis in accepted] == ["good", "bad"]
    assert [rejection["query_id"] for rejection in rejections] == ["bad"]  # type: ignore[index]
    # The retry must be told precisely which column was wrong.
    feedback = str(workflow._agents.inputs[1]["validation_feedback"])  # type: ignore[attr-defined,index]
    assert "nonexistent_col" in feedback
    # Accepted SQL is bounded even when the agent omitted a limit.
    assert accepted[0].sql.endswith("LIMIT 200")


def test_a_query_that_never_validates_is_dropped_not_fatal() -> None:
    workflow = _workflow(
        [
            AnalysisPlan(analyses=[_valid(), _invalid()]),
            AnalysisPlan(analyses=[_valid(), _invalid()]),
        ]
    )

    _, accepted, rejections = workflow._plan_agent_queries(
        {"specification": "s"},
        allowed_tables=_ALLOWED,
        table_columns=_COLUMNS,
        reserved_ids=set(),
    )

    assert [analysis.query_id for analysis in accepted] == ["good"]
    assert len(rejections) == 2


def test_an_unavailable_planning_agent_does_not_fail_the_run() -> None:
    """Primitives already guarantee a plan, so a failed agent call degrades."""

    workflow = _workflow([FireworksAgentError("upstream unavailable")])

    proposed, accepted, rejections = workflow._plan_agent_queries(
        {"specification": "s"},
        allowed_tables=_ALLOWED,
        table_columns=_COLUMNS,
        reserved_ids=set(),
    )

    assert proposed is None
    assert accepted == []
    assert len(rejections) == 1


def test_agent_queries_cannot_shadow_a_deterministic_primitive() -> None:
    workflow = _workflow([AnalysisPlan(analyses=[_valid(query_id="funnel")])])

    _, accepted, _ = workflow._plan_agent_queries(
        {"specification": "s"},
        allowed_tables=_ALLOWED,
        table_columns=_COLUMNS,
        reserved_ids={"funnel"},
    )

    assert accepted == []
