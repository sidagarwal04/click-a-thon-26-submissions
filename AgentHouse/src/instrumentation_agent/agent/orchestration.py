"""Instrumentation Agno Workflow — invoked by POST /v1/instrument.

See https://docs.agno.com/workflows/overview

Steps:
1. Load ``spec.md`` (+ path context) as a **string** prompt for the next agent.
2. Summarize the spec into structured event / feature metadata JSON.
3. Register missing ``meta_features`` / ``meta_events`` rows from that JSON.
4. When meta context changed: create ClickHouse event tables + activity_events MVs,
   then publish a living-context version via Context ``publish_context_version``.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from agno.agent import Agent
from agno.models.google import Gemini
from agno.workflow import Condition, Step, StepInput, StepOutput, Workflow

from instrumentation_agent.interfaces.instrumentation import (
    apply_clickhouse_from_meta,
    register_meta_from_summary,
)
from instrumentation_agent.models.schemas import (
    EventSummary,
    FeatureSpecMetadata,
    InstrumentRequest,
    InstrumentResponse,
    PipelinePlan,
)
from instrumentation_agent.settings import get_settings
from instrumentation_agent.utils.paths import resolve_feature_paths

_SUMMARIZE_INSTRUCTIONS = """\
You are the Spec Metadata agent for Atlys AgentHouse (Click-a-thon).

You receive the feature pack context including the full `spec.md` text.
Produce structured JSON metadata for the feature and each journey event.

Rules:
- Use ONLY events listed in the spec journey / user-actions bullets.
- Preserve journey order (1-based).
- Set ch_table to the event_name unless the spec explicitly says otherwise.
- Do NOT invent columns that are not hinted by the spec; expected_columns may be empty.
- Always include the shared join envelope in join_keys when present in contest guidance:
  user_id, application_id, device_type, os, geoip_country_code, destination, timestamp.
- the other columns are not in the join_keys must be added to the expected_columns
- feature_id must match the provided feature_id.
"""

def _ensure_google_api_key() -> None:
    settings = get_settings()
    if settings.google_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key


def _gemini() -> Gemini:
    settings = get_settings()
    return Gemini(id=settings.gemini_model, api_key=settings.google_api_key or None)


def _format_step_value(value: object) -> str:
    if value is None:
        return "<none>"
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json(indent=2)  # type: ignore[no-any-return]
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    return str(value)


def _log_step_io(step_name: str, direction: str, value: object) -> None:
    print(f"===== {direction} {step_name} =====")
    print(_format_step_value(value))
    print(f"===== END {direction} {step_name} =====")


def _agent_message(value: object) -> str:
    """Coerce step content to a string so Gemini never sees a bare dict/Message."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json(indent=2)  # type: ignore[no-any-return]
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    return str(value)


def load_spec_inputs(step_input: StepInput) -> StepOutput:
    """Resolve dataset/spec paths and load ``spec.md`` for the summarizer.

    Important: Agno agent steps treat dict inputs as ``Message`` objects (require
    ``role``). Always return a **string** so Gemini receives valid contents.
    """
    _log_step_io(
        "load_spec",
        "IN",
        {
            "input": step_input.input,
            "additional_data": step_input.additional_data,
        },
    )

    payload = _as_dict(step_input.input)
    extra = step_input.additional_data or {}
    feature_id = payload.get("feature_id") or extra.get("feature_id")
    spec_path = payload.get("spec_path") or extra.get("spec_path")

    paths = resolve_feature_paths(
        feature_id=feature_id,
        spec_path=spec_path,
    )
    paths.require_exists()
    spec_text = paths.spec_path.read_text(encoding="utf-8")

    # Plain text prompt — do NOT return a dict (breaks Gemini Message validation).
    prompt = (
        f"Summarize this feature pack into FeatureSpecMetadata JSON.\n\n"
        f"feature_id: {paths.feature_id}\n"
        f"spec_path: {paths.spec_path}\n"
        f"=== spec.md ===\n{spec_text}\n"
    )

    print("START prompt")
    print("prompt", prompt)
    print("END prompt")

    _log_step_io("load_spec", "OUT", prompt)
    return StepOutput(content=prompt)





@lru_cache
def get_summarize_agent() -> Agent:
    _ensure_google_api_key()
    return Agent(
        name="SpecMetadata",
        model=_gemini(),
        instructions=_SUMMARIZE_INSTRUCTIONS,
        output_schema=FeatureSpecMetadata,
        markdown=False,
    )


def _make_summarize_spec(agent: Agent):
    def summarize_spec(step_input: StepInput) -> StepOutput:
        inbound = step_input.previous_step_content or step_input.input
        _log_step_io("summarize_spec", "IN", inbound)
        message = _agent_message(inbound)
        run = agent.run(message)
        content = run.content
        _log_step_io("summarize_spec", "OUT", content)
        return StepOutput(content=content)

    return summarize_spec


def _metadata_from_register_payload(inbound: object) -> FeatureSpecMetadata | None:
    """Extract FeatureSpecMetadata from register_meta dict or bare metadata."""
    if isinstance(inbound, dict) and "metadata" in inbound:
        return _parse_model(inbound.get("metadata"), FeatureSpecMetadata)
    return _parse_model(inbound, FeatureSpecMetadata)


def _context_added_from_payload(inbound: object) -> bool:
    if isinstance(inbound, dict) and "context_added" in inbound:
        return bool(inbound.get("context_added"))
    return False


def register_meta(step_input: StepInput) -> StepOutput:
    """Ensure Postgres meta registry has the feature + any missing events.

    Output includes ``context_added`` so ClickHouse apply runs only when meta changed.
    """
    inbound = step_input.previous_step_content or step_input.input
    _log_step_io("register_meta", "IN", inbound)

    metadata = _parse_model(inbound, FeatureSpecMetadata)
    if metadata is None:
        raise RuntimeError(
            "register_meta requires FeatureSpecMetadata from summarize_spec; "
            f"got {type(inbound).__name__}"
        )

    extra = step_input.additional_data or {}
    paths = resolve_feature_paths(
        feature_id=metadata.feature_id or extra.get("feature_id"),
        spec_path=extra.get("spec_path"),
    )
    result = register_meta_from_summary(
        metadata,
        spec_path=paths.spec_path,
    )
    context_added = bool(result.get("context_added"))
    payload = {
        "context_added": context_added,
        "feature_created": result.get("feature_created", False),
        "events_created": result.get("events_created", []),
        "events_linked": result.get("events_linked", []),
        "metadata": metadata,
    }
    _log_step_io("register_meta", "OUT", payload)
    return StepOutput(content=payload)


def _should_apply_clickhouse(step_input: StepInput) -> bool:
    """True when register_meta added a feature and/or event context."""
    inbound = step_input.previous_step_content
    if inbound is None:
        inbound = step_input.get_step_content("register_meta")
    return _context_added_from_payload(inbound)


def apply_clickhouse(step_input: StepInput) -> StepOutput:
    """Create event tables + MVs into ``activity_events`` from ``meta_events``."""
    inbound = step_input.previous_step_content or step_input.input
    _log_step_io("apply_clickhouse", "IN", inbound)

    metadata = _metadata_from_register_payload(inbound)
    if metadata is None:
        raise RuntimeError(
            "apply_clickhouse requires FeatureSpecMetadata from register_meta; "
            f"got {type(inbound).__name__}"
        )

    plan = apply_clickhouse_from_meta(metadata.feature_id)
    _log_step_io("apply_clickhouse", "OUT", plan)
    return StepOutput(content=plan)


def skip_clickhouse(step_input: StepInput) -> StepOutput:
    """No-op when register_meta made no feature/event changes."""
    inbound = step_input.previous_step_content or step_input.input
    metadata = _metadata_from_register_payload(inbound)
    feature_id = metadata.feature_id if metadata is not None else "unknown"
    plan = PipelinePlan(
        action="skip_pipeline",
        rationale=(
            "No new feature or event meta was registered "
            "(context_added=false); ClickHouse pipeline left unchanged."
        ),
        feature_id=feature_id,
        events_to_materialize=[],
        pipeline_changes=[],
        tool_choices=[],
    )
    _log_step_io("skip_clickhouse", "OUT", plan)
    return StepOutput(content=plan)


def _jsonable(value: object) -> Any:
    """Serialize step content for ``workflow_json`` (models → dicts)."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def publish_context(step_input: StepInput) -> StepOutput:
    """Publish living context via Context ``publish_context_version`` tool.

    Runs only on the ClickHouse-apply branch. Supplies workflow outputs
    (register_meta + apply_clickhouse plan) to the tool as ``workflow_json``.
    """
    from context_agent import get_context_catalog_tools

    plan = step_input.previous_step_content or step_input.input
    register_payload = step_input.get_step_content("register_meta")
    if register_payload is None:
        register_payload = step_input.additional_data or {}

    workflow_payload = {
        "pipeline_plan": _jsonable(plan),
        "apply_clickhouse": _jsonable(plan),
        "register_meta": _jsonable(register_payload),
    }
    _log_step_io("publish_context", "IN", workflow_payload)

    tools = get_context_catalog_tools()
    result_json = tools.publish_context_version(
        workflow_json=json.dumps(workflow_payload, default=str),
    )
    try:
        result = json.loads(result_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"publish_context_version returned non-JSON: {result_json!r}"
        ) from exc
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError(f"publish_context_version failed: {result['error']}")

    _log_step_io("publish_context", "OUT", result)
    return StepOutput(content=result)


@lru_cache
def get_instrumentation_workflow() -> Workflow:
    """Build the Instrumentation workflow (cached)."""
    return Workflow(
        name="Instrumentation",
        description=(
            "Summarize spec.md into event metadata JSON, register "
            "meta_features/meta_events, then create ClickHouse event tables "
            "and activity_events materialized views only when meta context changed; "
            "publish a context version after a successful ClickHouse apply."
        ),
        steps=[
            Step(name="load_spec", executor=load_spec_inputs, on_error="fail", max_retries=0),
            Step(
                name="summarize_spec",
                executor=_make_summarize_spec(get_summarize_agent()),
                on_error="fail",
            ),
            Step(
                name="register_meta",
                executor=register_meta,
                on_error="fail",
                max_retries=0,
            ),
            Condition(
                name="apply_clickhouse_if_context_added",
                description=(
                    "Run ClickHouse DDL/MVs + publish_context_version only when "
                    "register_meta added a feature and/or event context."
                ),
                evaluator=_should_apply_clickhouse,
                steps=[
                    Step(
                        name="apply_clickhouse",
                        executor=apply_clickhouse,
                        on_error="fail",
                        max_retries=0,
                    ),
                    Step(
                        name="publish_context",
                        executor=publish_context,
                        on_error="fail",
                        max_retries=0,
                    ),
                ],
                else_steps=[
                    Step(
                        name="skip_clickhouse",
                        executor=skip_clickhouse,
                        on_error="fail",
                        max_retries=0,
                    ),
                ],
            ),
        ],
    )


def run_instrumentation_agent(request: InstrumentRequest) -> InstrumentResponse:
    """Run the Instrumentation workflow for a dataset path + spec.md (or feature_id)."""
    get_settings.cache_clear()
    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError(
            "GOOGLE_API_KEY is not set. Add a Gemini API key from "
            "https://aistudio.google.com/apikey to .env"
        )

    get_summarize_agent.cache_clear()
    get_instrumentation_workflow.cache_clear()
    workflow = get_instrumentation_workflow()

    # String input only — dict payloads are mis-validated as Message(role=...).
    run = workflow.run(
        input=(
            "Load the feature pack, summarize spec.md into FeatureSpecMetadata, "
            "register Postgres meta, then create ClickHouse tables and "
            "activity_events materialized views."
        ),
        additional_data={
            "feature_id": request.feature_id,
            "spec_path": request.spec_path,
        },
    )
    return _response_from_workflow(run, request)


def _step_failure_detail(step: object) -> str:
    """Surface nested Condition/Router child errors, not just the summary content."""
    nested = list(getattr(step, "steps", None) or [])
    child_errors = []
    for child in nested:
        if getattr(child, "success", True) is False:
            child_name = getattr(child, "step_name", "step")
            child_err = (
                getattr(child, "error", None)
                or getattr(child, "content", None)
                or "unknown error"
            )
            child_errors.append(f"{child_name}: {child_err}")
    if child_errors:
        return "; ".join(child_errors)
    return str(getattr(step, "error", None) or getattr(step, "content", None) or "unknown error")


def _response_from_workflow(
    run: object,
    request: InstrumentRequest,
) -> InstrumentResponse:
    status = getattr(getattr(run, "status", None), "value", None) or str(
        getattr(run, "status", "") or ""
    )
    if status and status.lower() in {"error", "failed", "cancelled"}:
        content = getattr(run, "content", None) or status
        raise RuntimeError(f"Instrumentation workflow failed ({status}): {content}")

    run_id = getattr(run, "run_id", None) or str(uuid4())
    step_results = list(getattr(run, "step_results", None) or [])
    for step in step_results:
        if getattr(step, "success", True) is False:
            name = getattr(step, "step_name", "step")
            err = _step_failure_detail(step)
            raise RuntimeError(f"Workflow step '{name}' failed: {err}")

    by_name = {
        getattr(step, "step_name", None): getattr(step, "content", None)
        for step in step_results
        if getattr(step, "step_name", None)
    }

    load_text = by_name.get("load_spec")
    feature_id = request.feature_id
    if isinstance(load_text, str) and "feature_id:" in load_text:
        for line in load_text.splitlines():
            if line.startswith("feature_id:"):
                feature_id = line.split(":", 1)[1].strip() or feature_id
                break
    if not feature_id and request.spec_path:
        feature_id = Path(request.spec_path).parent.name
    feature_id = feature_id or "unknown"

    spec_metadata = _parse_model(by_name.get("summarize_spec"), FeatureSpecMetadata)
    if spec_metadata is None:
        reg_payload = by_name.get("register_meta")
        if isinstance(reg_payload, dict) and "metadata" in reg_payload:
            spec_metadata = _parse_model(reg_payload.get("metadata"), FeatureSpecMetadata)
        else:
            spec_metadata = _parse_model(reg_payload, FeatureSpecMetadata)
    if spec_metadata is None:
        spec_metadata = _parse_model(getattr(run, "content", None), FeatureSpecMetadata)

    # Condition nests apply/skip; also scan nested step_results.
    pipeline_plan = _parse_model(by_name.get("apply_clickhouse"), PipelinePlan)
    if pipeline_plan is None:
        pipeline_plan = _parse_model(by_name.get("skip_clickhouse"), PipelinePlan)
    if pipeline_plan is None:
        for step in step_results:
            nested = list(getattr(step, "steps", None) or [])
            for child in nested:
                name = getattr(child, "step_name", None)
                if name in {"apply_clickhouse", "skip_clickhouse"}:
                    pipeline_plan = _parse_model(
                        getattr(child, "content", None), PipelinePlan
                    )
                    if pipeline_plan is not None:
                        break
            if pipeline_plan is not None:
                break
    if pipeline_plan is None:
        pipeline_plan = _parse_model(getattr(run, "content", None), PipelinePlan)

    if spec_metadata is None:
        raise RuntimeError(
            "summarize_spec produced no FeatureSpecMetadata. "
            "Check GOOGLE_API_KEY (Gemini Developer API). "
            "Keys starting with 'AQ.' often return 401 ACCESS_TOKEN_TYPE_UNSUPPORTED — "
            "create/regenerate a key at https://aistudio.google.com/apikey."
        )

    events = [
        EventSummary(
            event_name=e.event_name,
            journey_order=e.journey_order,
            ch_table=e.ch_table,
            row_count=0,
        )
        for e in spec_metadata.journey
    ]

    response_status = "planned"
    if pipeline_plan is not None:
        response_status = pipeline_plan.action

    return InstrumentResponse(
        status=response_status,
        run_id=str(run_id),
        feature_id=feature_id,
        events=events,
        agent_run_id=str(run_id),
        spec_metadata=spec_metadata,
        pipeline_plan=pipeline_plan,
    )


def _as_dict(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()  # type: ignore[no-any-return]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_model(value: object, model_cls: type) -> Any | None:
    if value is None:
        return None
    if isinstance(value, model_cls):
        return value
    if isinstance(value, dict):
        try:
            return model_cls.model_validate(value)
        except Exception:  # noqa: BLE001
            return None
    if isinstance(value, str):
        try:
            return model_cls.model_validate_json(value)
        except Exception:  # noqa: BLE001
            try:
                return model_cls.model_validate(json.loads(value))
            except Exception:  # noqa: BLE001
                return None
    if hasattr(value, "model_dump"):
        try:
            return model_cls.model_validate(value.model_dump())
        except Exception:  # noqa: BLE001
            return None
    return None


# Back-compat alias
get_instrumentation_agent = get_instrumentation_workflow
