"""Tests for instrumentation profiler + routes."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from instrumentation_agent.utils.profiler import (
    flatten_record,
    parse_journey_order,
    profile_feature,
)

client = TestClient(app)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "01_express_checkout"
_SPEC = _FIXTURE / "spec.md"
_EVENTS = _FIXTURE / "events.ndjson"


def test_parse_journey_order_express() -> None:
    order = parse_journey_order(_SPEC.read_text(encoding="utf-8"))
    assert order == [
        "express_checkout_shown",
        "express_checkout_selected",
        "saved_method_used",
        "otp_entered",
        "express_payment_confirmed",
    ]


def test_flatten_nested_payment() -> None:
    flat = flatten_record(
        {"event": "x", "payment": {"amount": 1.0, "latency_ms": 10}}
    )
    assert flat["payment_amount"] == 1.0
    assert flat["payment_latency_ms"] == 10
    assert "payment" not in flat


def test_profile_feature_express() -> None:
    profile = profile_feature("01_express_checkout", _SPEC, _EVENTS)
    assert [e.event_name for e in profile.events] == [
        "express_checkout_shown",
        "express_checkout_selected",
        "saved_method_used",
        "otp_entered",
        "express_payment_confirmed",
    ]
    confirmed = profile.events[-1]
    assert "payment_latency_ms" in confirmed.columns
    assert confirmed.row_count == 1
    assert profile.events[0].row_count == 2


def test_sqlglot_validates_create_ddl() -> None:
    from instrumentation_agent.models.domain import EventProfile
    from instrumentation_agent.utils.clickhouse import (
        build_create_activity_events_sql,
        build_create_event_table_if_not_exists_sql,
        build_create_mv_to_activity_sql,
        build_create_table_sql,
    )

    profile = EventProfile(
        event_name="express_checkout_shown",
        journey_order=1,
        columns={"timestamp": "DateTime64(3)", "user_id": "String"},
    )
    ddl = build_create_table_sql(profile, "atlys")
    assert "CREATE TABLE" in ddl
    assert "MergeTree" in ddl

    event_ddl = build_create_event_table_if_not_exists_sql(
        database="atlys",
        ch_table="otp_entered",
        columns={"timestamp": "String", "user_id": "String", "otp_success": "String"},
    )
    assert "CREATE TABLE IF NOT EXISTS" in event_ddl
    assert "DateTime64(3)" in event_ddl

    activity_ddl = build_create_activity_events_sql("atlys")
    assert "activity_events" in activity_ddl

    mv_sql = build_create_mv_to_activity_sql(
        database="atlys",
        event_name="otp_entered",
        ch_table="otp_entered",
        columns={"timestamp": "String", "user_id": "String"},
    )
    assert "CREATE MATERIALIZED VIEW IF NOT EXISTS" in mv_sql
    assert "TO `atlys`.`activity_events`" in mv_sql
    assert "FROM `atlys`.`otp_entered`" in mv_sql


def test_instrument_route_success() -> None:
    from instrumentation_agent.models.schemas import InstrumentResponse

    fake = InstrumentResponse(
        status="ok",
        run_id="00000000-0000-0000-0000-000000000001",
        feature_id="01_express_checkout",
        events=[
            {
                "event_name": "express_checkout_shown",
                "journey_order": 1,
                "ch_table": "express_checkout_shown",
                "row_count": 10,
            }
        ],
        agent_run_id="agent-run-1",
    )
    with (
        patch("instrumentation_agent.routes.instrumentation.validate_instrument_request"),
        patch(
            "instrumentation_agent.routes.instrumentation.run_instrumentation_agent",
            return_value=fake,
        ),
    ):
        response = client.post(
            "/v1/instrument",
            json={"feature_id": "01_express_checkout"},
        )
    assert response.status_code == 200
    assert response.json()["feature_id"] == "01_express_checkout"
    assert response.json()["agent_run_id"] == "agent-run-1"


def test_instrument_route_accepts_spec_path() -> None:
    from instrumentation_agent.models.schemas import InstrumentResponse

    fake = InstrumentResponse(
        status="ok",
        run_id="00000000-0000-0000-0000-000000000002",
        feature_id="01_express_checkout",
        events=[],
    )
    with (
        patch("instrumentation_agent.routes.instrumentation.validate_instrument_request"),
        patch(
            "instrumentation_agent.routes.instrumentation.run_instrumentation_agent",
            return_value=fake,
        ) as mocked,
    ):
        response = client.post(
            "/v1/instrument",
            json={
                "feature_id": "12312",
                "spec_path": str(_SPEC),
            },
        )
    assert response.status_code == 200
    req = mocked.call_args.args[0]
    assert req.feature_id == "12312"
    assert req.spec_path == str(_SPEC)


def test_instrument_route_rejects_unknown_feature_without_spec_path() -> None:
    with patch(
        "instrumentation_agent.routes.instrumentation.validate_instrument_request",
        side_effect=ValueError(
            "Invalid input: feature_id '12312' is not present in the metadata registry"
        ),
    ):
        response = client.post(
            "/v1/instrument",
            json={"feature_id": "12312"},
        )
    assert response.status_code == 422
    assert "Invalid input" in response.json()["detail"]


def test_validate_unknown_feature_requires_spec_path() -> None:
    from instrumentation_agent.interfaces.instrumentation import validate_instrument_request
    from instrumentation_agent.models.schemas import InstrumentRequest

    with patch(
        "instrumentation_agent.interfaces.instrumentation.get_registry",
        return_value=type("R", (), {"feature": None, "events": []})(),
    ):
        with patch(
            "instrumentation_agent.interfaces.instrumentation.feature_paths",
        ) as mocked_paths:
            from instrumentation_agent.models.domain import FeaturePaths

            missing = FeaturePaths(
                feature_id="12312",
                feature_dir=Path("/tmp/missing-12312"),
                spec_path=Path("/tmp/missing-12312/spec.md"),
            )
            mocked_paths.return_value = missing
            try:
                validate_instrument_request(InstrumentRequest(feature_id="12312"))
                raise AssertionError("expected ValueError")
            except ValueError as exc:
                assert "not present in the metadata registry" in str(exc)
                assert "spec_path" in str(exc)


def test_validate_accepts_feature_id_with_spec_path() -> None:
    from instrumentation_agent.interfaces.instrumentation import validate_instrument_request
    from instrumentation_agent.models.schemas import InstrumentRequest

    paths = validate_instrument_request(
        InstrumentRequest(feature_id="12312", spec_path=str(_SPEC))
    )
    assert paths.feature_id == "12312"
    assert paths.spec_path == _SPEC.resolve()


def test_resolve_feature_paths_from_spec() -> None:
    from instrumentation_agent.utils.paths import resolve_feature_paths

    paths = resolve_feature_paths(spec_path=_SPEC)
    assert paths.feature_id == "01_express_checkout"
    assert paths.spec_path == _SPEC.resolve()
    paths.require_exists()


def test_registry_shape() -> None:
    from instrumentation_agent.models.schemas import RegistryResponse

    empty = RegistryResponse(
        feature_id="01_express_checkout", feature=None, events=[]
    )
    with patch(
        "instrumentation_agent.routes.instrumentation.get_registry",
        return_value=empty,
    ):
        response = client.get("/v1/registry/01_express_checkout")
    assert response.status_code == 200
    assert response.json() == empty.model_dump()


def test_health_ok() -> None:
    from instrumentation_agent.models.schemas import HealthResponse

    fake = HealthResponse(
        status="ok",
        postgres="up",
        clickhouse="up",
        specs_root="/tmp/specs",
    )
    with patch(
        "instrumentation_agent.routes.health.health_check",
        return_value=fake,
    ):
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["postgres"] == "up"
    assert body["clickhouse"] == "up"


def test_instrumentation_tools_construct() -> None:
    from instrumentation_agent.tools.instrumentation import InstrumentationTools
    from instrumentation_agent.tools.pipeline import PipelineTools

    tools = InstrumentationTools()
    assert tools.name == "instrumentation_tools"
    assert len(tools.tools) >= 2

    pipeline = PipelineTools()
    assert pipeline.name == "pipeline_tools"
    assert len(pipeline.tools) == 4
    inspected = pipeline.inspect_existing_pipeline("01_express_checkout")
    assert '"mock": true' in inspected or '"mock": True' in inspected or '"exists": false' in inspected.lower()


def test_load_spec_workflow_step() -> None:
    from agno.workflow import StepInput

    from instrumentation_agent.agent.orchestration import load_spec_inputs

    out = load_spec_inputs(
        StepInput(
            input={
                "feature_id": "01_express_checkout",
                "spec_path": str(_SPEC),
            }
        )
    )
    assert out.success
    assert isinstance(out.content, str), "agent steps require string content, not dict"
    assert "feature_id: 01_express_checkout" in out.content
    assert "express_checkout_shown" in out.content
    assert "=== spec.md ===" in out.content


def test_instrumentation_workflow_constructs() -> None:
    from agno.workflow import Condition

    from instrumentation_agent.agent.orchestration import get_instrumentation_workflow

    get_instrumentation_workflow.cache_clear()
    wf = get_instrumentation_workflow()
    assert wf.name == "Instrumentation"
    assert len(wf.steps) == 4
    assert [s.name for s in wf.steps[:3]] == [
        "load_spec",
        "summarize_spec",
        "register_meta",
    ]
    cond = wf.steps[3]
    assert isinstance(cond, Condition)
    assert cond.name == "apply_clickhouse_if_context_added"
    assert [s.name for s in cond.steps] == ["apply_clickhouse", "publish_context"]
    assert [s.name for s in (cond.else_steps or [])] == ["skip_clickhouse"]


def test_register_meta_from_summary_inserts_missing() -> None:
    from instrumentation_agent.interfaces.instrumentation import register_meta_from_summary
    from instrumentation_agent.models.schemas import EventMetaDraft, FeatureSpecMetadata

    metadata = FeatureSpecMetadata(
        feature_id="01_express_checkout",
        feature_summary="Express checkout funnel",
        journey=[
            EventMetaDraft(
                event_name="express_checkout_shown",
                journey_order=1,
                ch_table="express_checkout_shown",
                expected_columns=["placement"],
            ),
            EventMetaDraft(
                event_name="otp_entered",
                journey_order=2,
                ch_table="otp_entered",
            ),
        ],
    )

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _FakeEngine:
        def begin(self):
            return _FakeConn()

    with (
        patch(
            "instrumentation_agent.interfaces.instrumentation.get_engine",
            return_value=_FakeEngine(),
        ),
        patch(
            "instrumentation_agent.interfaces.instrumentation.MetaFeaturesCRUD"
        ) as features_cls,
        patch(
            "instrumentation_agent.interfaces.instrumentation.MetaEventsCRUD"
        ) as events_cls,
    ):
        features = features_cls.return_value
        events = events_cls.return_value
        features.insert_if_missing.return_value = True
        events.insert_if_missing.side_effect = ["created", "exists"]

        result = register_meta_from_summary(
            metadata,
            spec_path=_SPEC,
        )

    assert result == {
        "feature_created": True,
        "events_created": ["express_checkout_shown"],
        "events_linked": [],
        "context_added": True,
    }
    features.insert_if_missing.assert_called_once_with(
        feature_id="01_express_checkout",
        spec_path=str(_SPEC.resolve()),
        journey=[
            {
                "event_name": "express_checkout_shown",
                "journey_order": 1,
                "ch_table": "express_checkout_shown",
            },
            {
                "event_name": "otp_entered",
                "journey_order": 2,
                "ch_table": "otp_entered",
            },
        ],
        conn=features.insert_if_missing.call_args.kwargs["conn"],
    )
    assert events.insert_if_missing.call_count == 2
    first_event_kwargs = events.insert_if_missing.call_args_list[0].kwargs
    assert first_event_kwargs["event_name"] == "express_checkout_shown"
    assert first_event_kwargs["feature_id"] == "01_express_checkout"
    assert first_event_kwargs["ch_table"] == "express_checkout_shown"
    assert "journey_order" not in first_event_kwargs
    assert "run_id" not in first_event_kwargs
    assert "row_count" not in first_event_kwargs
    assert "status" not in first_event_kwargs  # set inside CRUD as "updated"


def test_publish_context_version_tool_from_workflow_json() -> None:
    """Tool derives args from workflow output; return shape stays the publish dict."""
    from context_agent.tools import ContextCatalogTools

    tools = ContextCatalogTools()
    workflow = {
        "register_meta": {
            "context_added": True,
            "events_created": ["express_checkout_shown"],
            "events_linked": [],
            "metadata": {
                "feature_id": "01_express_checkout",
                "feature_summary": "Express checkout",
                "journey": [
                    {
                        "event_name": "express_checkout_shown",
                        "journey_order": 1,
                        "ch_table": "express_checkout_shown",
                    }
                ],
            },
        },
        "pipeline_plan": {
            "action": "create_pipeline",
            "rationale": "created tables",
            "feature_id": "01_express_checkout",
            "events_to_materialize": ["express_checkout_shown"],
            "pipeline_changes": ["CREATE TABLE IF NOT EXISTS activity_events"],
        },
    }
    fake_result = {
        "context_version": "v1",
        "parent_version": None,
        "source": "instrumentation",
        "feature_id": "01_express_checkout",
        "summary": "Instrumentation reconcile for 01_express_checkout",
        "is_current": True,
        "copied_from_parent": 0,
        "upserted": 1,
        "deleted": 0,
        "item_count": 1,
    }
    with (
        patch(
            "context_agent.tools.get_latest_context_items",
            return_value={"context_version": None, "items": []},
        ),
        patch(
            "context_agent.tools.publish_context_version",
            return_value=fake_result,
        ) as mocked,
    ):
        out = tools.publish_context_version(workflow_json=json.dumps(workflow))

    parsed = json.loads(out)
    assert parsed == fake_result
    kwargs = mocked.call_args.kwargs
    assert kwargs["context_version"] == "v1"
    assert kwargs["source"] == "instrumentation"
    assert kwargs["feature_id"] == "01_express_checkout"
    assert kwargs["upserts"][0]["kind"] == "entity"
    assert kwargs["upserts"][0]["item_key"] == "feature:01_express_checkout"
    assert "funnel_step" not in {u["kind"] for u in kwargs["upserts"]}


def test_publish_context_workflow_step() -> None:
    from agno.workflow import StepInput

    from instrumentation_agent.agent.orchestration import publish_context
    from instrumentation_agent.models.schemas import PipelinePlan

    plan = PipelinePlan(
        action="create_pipeline",
        rationale="created",
        feature_id="01_express_checkout",
        events_to_materialize=["express_checkout_shown"],
        pipeline_changes=[],
    )
    register_payload = {
        "context_added": True,
        "metadata": {
            "feature_id": "01_express_checkout",
            "feature_summary": "Express",
            "journey": [],
        },
    }
    fake_tools = MagicMock()
    fake_tools.publish_context_version.return_value = json.dumps(
        {
            "context_version": "v1",
            "parent_version": None,
            "source": "instrumentation",
            "feature_id": "01_express_checkout",
            "summary": "ok",
            "is_current": True,
            "copied_from_parent": 0,
            "upserted": 1,
            "deleted": 0,
            "item_count": 1,
        }
    )

    step_input = StepInput(previous_step_content=plan)
    # Agno StepInput may not wire get_step_content; patch on the instance.
    step_input.get_step_content = MagicMock(return_value=register_payload)  # type: ignore[method-assign]

    with patch(
        "context_agent.get_context_catalog_tools",
        return_value=fake_tools,
    ):
        out = publish_context(step_input)

    assert out.success
    assert out.content["context_version"] == "v1"
    assert out.content["source"] == "instrumentation"
    called = fake_tools.publish_context_version.call_args.kwargs
    assert "workflow_json" in called
    payload = json.loads(called["workflow_json"])
    assert payload["register_meta"]["context_added"] is True
    assert payload["pipeline_plan"]["feature_id"] == "01_express_checkout"


def test_apply_clickhouse_workflow_step() -> None:
    from agno.workflow import StepInput

    from instrumentation_agent.agent.orchestration import apply_clickhouse
    from instrumentation_agent.models.schemas import EventMetaDraft, FeatureSpecMetadata, PipelinePlan

    metadata = FeatureSpecMetadata(
        feature_id="01_express_checkout",
        feature_summary="Express",
        journey=[
            EventMetaDraft(
                event_name="express_checkout_shown",
                journey_order=1,
                ch_table="express_checkout_shown",
            )
        ],
    )
    plan = PipelinePlan(
        action="create_pipeline",
        rationale="created",
        feature_id="01_express_checkout",
        events_to_materialize=["express_checkout_shown"],
        pipeline_changes=["CREATE TABLE IF NOT EXISTS activity_events"],
    )
    with patch(
        "instrumentation_agent.agent.orchestration.apply_clickhouse_from_meta",
        return_value=plan,
    ) as mocked:
        out = apply_clickhouse(
            StepInput(
                input={
                    "context_added": True,
                    "metadata": metadata,
                }
            )
        )
    assert out.success
    assert isinstance(out.content, PipelinePlan)
    assert out.content.action == "create_pipeline"
    mocked.assert_called_once_with("01_express_checkout")


def test_should_apply_clickhouse_flag() -> None:
    from agno.workflow import StepInput

    from instrumentation_agent.agent.orchestration import _should_apply_clickhouse

    assert _should_apply_clickhouse(
        StepInput(previous_step_content={"context_added": True, "metadata": {}})
    )
    assert not _should_apply_clickhouse(
        StepInput(previous_step_content={"context_added": False, "metadata": {}})
    )


def test_register_meta_workflow_step() -> None:
    from agno.workflow import StepInput

    from instrumentation_agent.agent.orchestration import register_meta
    from instrumentation_agent.models.schemas import EventMetaDraft, FeatureSpecMetadata

    metadata = FeatureSpecMetadata(
        feature_id="01_express_checkout",
        feature_summary="Express",
        journey=[
            EventMetaDraft(
                event_name="express_checkout_shown",
                journey_order=1,
                ch_table="express_checkout_shown",
            )
        ],
    )
    with patch(
        "instrumentation_agent.agent.orchestration.register_meta_from_summary",
        return_value={
            "feature_created": True,
            "events_created": ["express_checkout_shown"],
            "events_linked": [],
            "context_added": True,
        },
    ) as mocked:
        out = register_meta(
            StepInput(
                input=metadata,
                additional_data={
                    "feature_id": "01_express_checkout",
                    "spec_path": str(_SPEC),
                },
            )
        )
    assert out.success
    assert isinstance(out.content, dict)
    assert out.content["context_added"] is True
    assert isinstance(out.content["metadata"], FeatureSpecMetadata)
    assert out.content["metadata"].feature_id == "01_express_checkout"
    mocked.assert_called_once_with(metadata, spec_path=_SPEC.resolve())
