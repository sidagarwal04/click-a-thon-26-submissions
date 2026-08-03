from __future__ import annotations

import json
from typing import Any

from zentra_domain_agent_execution import (
    SemanticCatalog,
    SemanticDimension,
    SemanticFilter,
    SemanticMeasure,
    SemanticQuery,
    SemanticTimeDimension,
)


class MalformedAgentResponseError(ValueError):
    """The model returned text that does not satisfy the declared schema."""


def _nullable(inner: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [inner, {"type": "null"}]}


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_STRINGS = {"type": "array", "items": {"type": "string"}}

SEMANTIC_QUERY_SCHEMA = _obj(
    {
        "measures": _STRINGS,
        "dimensions": _STRINGS,
        "time_dimensions": {
            "type": "array",
            "items": _obj(
                {
                    "dimension": {"type": "string"},
                    "granularity": _nullable({"type": "string"}),
                    "date_range": _nullable(_STRINGS),
                }
            ),
        },
        "filters": {
            "type": "array",
            "items": _obj(
                {
                    "member": {"type": "string"},
                    "operator": {"type": "string"},
                    "values": _STRINGS,
                }
            ),
        },
    }
)

# The labels are nullable rather than absent: _obj requires every property, which
# strict structured output demands, so nullability is how the schema says "you
# must answer, and 'this is not a period comparison' is an answer".
METRIC_COMPARISON_SCHEMA = _obj(
    {
        "metric": {"type": "string"},
        "previous_value": {"type": "string"},
        "previous_label": _nullable({"type": "string"}),
        "current_value": {"type": "string"},
        "current_label": _nullable({"type": "string"}),
        "unit": {"type": "string"},
    }
)

# `QUERY_PLAN_SCHEMA` was the shape of a separate "plan the query" model call.
# Both agents that made one now reach the semantic layer through a tool, whose
# arguments are `SEMANTIC_QUERY_SCHEMA` directly, so there is no plan step left
# to validate (ADR-0024).

# sample_size is extraction, not introspection: reading how many underlying
# records an aggregate covers is something models do reliably, unlike scoring
# their own confidence. Code turns it into a ceiling the model cannot argue with.
ANALYSIS_SCHEMA = _obj(
    {
        "result_summary": {"type": "string"},
        "metrics": {"type": "array", "items": METRIC_COMPARISON_SCHEMA},
        "sample_size": {"type": "integer"},
        "confidence": {"type": "number"},
    }
)

RECHECK_SCHEMA = _obj(
    {
        "recheck_passed": {"type": "boolean"},
        "discrepancy_pct": {"type": "number"},
        "sample_size": {"type": "integer"},
        "confidence": {"type": "number"},
        "issues": _STRINGS,
    }
)

TASK_LEDGER_SCHEMA = _obj(
    {
        "tasks": {
            "type": "array",
            "items": _obj(
                {
                    "role": {"type": "string"},
                    "objective": {"type": "string"},
                }
            ),
        }
    }
)

# Intake's structured decision: whether a message resolves inside the scoped
# catalog it was given. `normalized_question` and `clarification` are
# mutually exclusive in practice (one is null depending on `disposition`),
# nullable rather than split into two schemas so one call always returns one
# shape.
INTAKE_SCHEMA = _obj(
    {
        "disposition": {
            "type": "string",
            "enum": ["resolved", "ambiguous", "unsupported"],
        },
        "normalized_question": _nullable({"type": "string"}),
        "clarification": _nullable({"type": "string"}),
        "reasoning": {"type": "string"},
    }
)

# `SYNTHESIS_SCHEMA` was the Orchestrator's. It is gone with the node that
# used it; the Insight Agent's `DRAFT_FINDING_SCHEMA` is the only shape a
# conclusion now takes.

# The Insight Agent's structured output.
#
# `kind` is required on every claim rather than inferred, because the
# observed/interpretation split is the one thing a reader cannot re-derive from
# prose. `metric` and `value` exist so a claim can be checked against the
# validated aggregate it says it rests on — a claim naming no governed metric,
# or naming a value the aggregate does not carry, is refused rather than shown.
#
# `root_cause_resolved` is asked for precisely so it can be refused: ADR 0011
# admits no Root Cause Claim until a causal-evidence standard is accepted, so a
# model asserting one has overclaimed and the whole draft fails closed.
DRAFT_FINDING_SCHEMA = _obj(
    {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "claims": {
            "type": "array",
            "items": _obj(
                {
                    "kind": {
                        "type": "string",
                        "enum": ["observed", "interpretation"],
                    },
                    "text": {"type": "string"},
                    "metric": _nullable({"type": "string"}),
                    "value": _nullable({"type": "string"}),
                    "period": _nullable({"type": "string"}),
                }
            ),
        },
        "contradictions": _STRINGS,
        "root_cause_resolved": {"type": "boolean"},
        "confidence": {"type": "number"},
    }
)


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise MalformedAgentResponseError(
            "Agent response was not valid JSON"
        ) from error
    if not isinstance(parsed, dict):
        raise MalformedAgentResponseError("Agent response was not a JSON object")
    return parsed


def semantic_query_from_json(payload: dict[str, Any]) -> SemanticQuery:
    try:
        return SemanticQuery(
            measures=tuple(payload.get("measures", ())),
            dimensions=tuple(payload.get("dimensions", ())),
            time_dimensions=tuple(
                SemanticTimeDimension(
                    dimension=item["dimension"],
                    granularity=item.get("granularity"),
                    date_range=(
                        (item["date_range"][0], item["date_range"][1])
                        if item.get("date_range")
                        else None
                    ),
                )
                for item in payload.get("time_dimensions", ())
            ),
            filters=tuple(
                SemanticFilter(
                    member=item["member"],
                    operator=item["operator"],
                    values=tuple(item.get("values", ())),
                )
                for item in payload.get("filters", ())
            ),
        )
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise MalformedAgentResponseError(
            f"Agent proposed an unusable semantic query: {error}"
        ) from error


def render_measure(measure: SemanticMeasure) -> str:
    line = f"- {measure.name} ({measure.type})"
    if measure.description:
        return f"{line} — {measure.description}"
    return line


def render_dimension(dimension: SemanticDimension) -> str:
    """Name, type, what it means, and the values it holds where few enough.

    Without the values an agent can only guess how they are spelled — a filter
    on "North America" against data storing "NA" returns zero rows rather than
    an error, and the agent correctly reports that it found nothing.

    The description matters for the same reason at one level up: across a
    tenant's own harvested tables, two plausible columns can carry the same
    name, and choosing the wrong one answers a different question confidently.
    """
    line = f"- {dimension.name} ({dimension.type})"
    if dimension.description:
        line = f"{line} — {dimension.description}"
    if dimension.values:
        return f"{line} — one of: {', '.join(dimension.values)}"
    return line


def render_catalog(catalog: SemanticCatalog) -> str:
    measures = "\n".join(render_measure(measure) for measure in catalog.measures)
    dimensions = "\n".join(
        render_dimension(dimension) for dimension in catalog.dimensions
    )
    return f"Measures:\n{measures}\n\nDimensions:\n{dimensions}"
